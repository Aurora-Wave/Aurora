"""
EDF+ Exporter for Aurora
Robust export functionality for clean signal data with filtered comments.
"""

import numpy as np
import mne
from typing import List, Dict, Any, Optional, Union, Set
from pathlib import Path
import datetime as dt
import logging

from aurora.core.signal import Signal, HR_Gen_Signal
from aurora.core.comments import EMSComment
from aurora.data.data_manager import DataManager


class EDFExporter:
    """
    Robust EDF+ exporter with support for signal cleaning and comment filtering.
    
    Features:
    - Export all or selected channels from DataManager
    - Filter comments based on user selection (clean signal export)
    - Automatic resampling for mixed sampling rates
    - Accurate unit conversion based on Aurora signal analysis
    - Patient and recording metadata support
    - Time range selection for partial exports
    """
    
    def __init__(self, data_manager: DataManager):
        """
        Initialize exporter with DataManager reference.
        
        Args:
            data_manager: DataManager instance with loaded file data
        """
        self.data_manager = data_manager
        self.logger = logging.getLogger(f"aurora.data.{self.__class__.__name__}")
        
        # Simplified channel type - all as misc for maximum compatibility
        self.default_channel_type = "misc"
        
        # Unit mapping based on actual Aurora signal analysis
        # Handles both list format ['mV'] and string format 'bpm'
        self.unit_map = {
            # Voltage units (list format)
            "['V']": (mne.io.constants.FIFF.FIFF_UNIT_V, 0),
            "['mV']": (mne.io.constants.FIFF.FIFF_UNIT_V, -3),
            "['µV']": (mne.io.constants.FIFF.FIFF_UNIT_V, -6),
            "['uV']": (mne.io.constants.FIFF.FIFF_UNIT_V, -6),
            # Multi-record format (some files have multiple records)
            "['V', 'V', 'V']": (mne.io.constants.FIFF.FIFF_UNIT_V, 0),
            "['mV', 'mV', 'mV']": (mne.io.constants.FIFF.FIFF_UNIT_V, -3),
            # String format
            "V": (mne.io.constants.FIFF.FIFF_UNIT_V, 0),
            "mV": (mne.io.constants.FIFF.FIFF_UNIT_V, -3),
            "µV": (mne.io.constants.FIFF.FIFF_UNIT_V, -6),
            "uV": (mne.io.constants.FIFF.FIFF_UNIT_V, -6),
            # Physiological units (dimensionless in EDF+)
            "bpm": (0, 0),  # Heart rate
            "['mmHg']": (0, 0),  # Pressure
            "['mmHg', 'mmHg', 'mmHg']": (0, 0),  # Pressure (multi-record)
            "['%']": (0, 0),  # Percentage (SPO2)
            "['%', '%', '%']": (0, 0),  # Percentage (multi-record)
            "['L/min']": (0, 0),  # Flow rate (CO)
            "['L/min', 'L/min', 'L/min']": (0, 0),  # Flow rate (multi-record)
            "['mL']": (0, 0),  # Volume (SV)
            "['mL', 'mL', 'mL']": (0, 0),  # Volume (multi-record)
            "['cm/s']": (0, 0),  # Velocity (MCA)
            "['cm/s', 'cm/s', 'cm/s']": (0, 0),  # Velocity (multi-record)
            "['deg']": (0, 0),  # Angle (Tilt)
            "['deg', 'deg', 'deg']": (0, 0),  # Angle (multi-record)
            "['dyn']": (0, 0),  # Resistance (SVR)
            "['dyn', 'dyn', 'dyn']": (0, 0),  # Resistance (multi-record)
            # Fallback
            "unknown": (0, 0)
        }
    
    def export_clean_signals(
        self,
        file_path: str,
        output_path: str,
        channels: Optional[List[str]] = None,
        excluded_comment_ids: Optional[Set[int]] = None,
        time_range: Optional[tuple] = None,
        resample_enable: bool = True,
        target_fs: Optional[float] = None,
        patient_id: str = "AuroraClean",
        recording_info: Optional[str] = None,
        overwrite: bool = True,
        **hr_params
    ) -> str:
        """
        Export clean signals to EDF+ with filtered comments.
        
        Args:
            file_path: Path to source file in DataManager
            output_path: Output EDF+ file path
            channels: List of channels to export (None = all channels)
            excluded_comment_ids: Set of comment IDs to exclude from export
            time_range: Tuple (start_sec, end_sec) for partial export
            resample_enable: Enable resampling for mixed sampling rates
            target_fs: Target sampling frequency (None = auto-detect max)
            patient_id: Patient identifier for EDF+ header
            recording_info: Recording description
            overwrite: Overwrite existing file
            **hr_params: Parameters for HR_gen derivation
            
        Returns:
            Path to exported EDF+ file
        """
        try:
            self.logger.info(f"Starting EDF+ export: {file_path} -> {output_path}")
            
            # 1. Validate inputs
            loaded_files = self.data_manager.list_loaded_files()
            if file_path not in loaded_files:
                raise ValueError(f"File not loaded in DataManager: {file_path}. Loaded files: {loaded_files}")
            
            # 2. Get channel list
            available_channels = self.data_manager.get_available_channels(file_path)
            export_channels = channels or available_channels
            
            self.logger.info(f"Exporting {len(export_channels)} channels: {export_channels}")
            
            # 3. Load signal data
            signal_data, channel_info = self._load_signals(
                file_path, export_channels, time_range, **hr_params
            )
            
            # 4. Handle resampling
            if resample_enable:
                signal_data, channel_info = self._resample_signals(
                    signal_data, channel_info, target_fs
                )
            
            # 5. Create MNE Raw object
            raw = self._create_mne_raw(
                signal_data, channel_info, patient_id, recording_info
            )
            
            # 6. Add filtered annotations
            self._add_filtered_annotations(
                raw, file_path, excluded_comment_ids, time_range
            )
            
            # 7. Export to EDF+
            self._export_raw_to_edf(raw, output_path, overwrite)
            
            self.logger.info(f"EDF+ export completed: {output_path}")
            return output_path
            
        except Exception as e:
            error_msg = f"Failed to export EDF+: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _normalize_units(self, units: Any) -> str:
        """
        Normalize units to string format for mapping.
        
        Args:
            units: Units in any format (list, string, etc.)
            
        Returns:
            Normalized string representation
        """
        units_str = str(units)
        
        # Handle common list formats by extracting first element if all are the same
        if units_str.startswith("['") and units_str.endswith("']"):
            # Check if all elements in the list are the same
            try:
                # Convert string representation back to evaluate the list
                import ast
                units_list = ast.literal_eval(units_str)
                if isinstance(units_list, list) and len(set(units_list)) == 1:
                    # All elements are the same, use the first one
                    return f"['{units_list[0]}']"
            except (ValueError, SyntaxError):
                pass
        
        return units_str
    
    def _load_signals(
        self, 
        file_path: str, 
        channels: List[str], 
        time_range: Optional[tuple], 
        **hr_params
    ) -> tuple:
        """
        Load signal data from DataManager.
        
        Returns:
            Tuple of (signal_data_dict, channel_info_dict)
        """
        signal_data = {}
        channel_info = {}
        
        for channel_name in channels:
            try:
                # Load full signal
                if channel_name.upper() == "HR_GEN":
                    signal = self.data_manager.get_trace(file_path, channel_name, **hr_params)
                else:
                    signal = self.data_manager.get_trace(file_path, channel_name)
                
                if signal is None:
                    self.logger.warning(f"Could not load signal: {channel_name}")
                    continue
                
                # Apply time range if specified
                if time_range is not None:
                    signal = self._apply_time_range(signal, time_range)
                
                # Normalize units for consistent mapping
                normalized_units = self._normalize_units(signal.units)
                
                signal_data[channel_name] = signal.data
                channel_info[channel_name] = {
                    'fs': signal.fs,
                    'units': normalized_units,
                    'name': signal.name,
                    'length': len(signal.data)
                }
                
                self.logger.debug(f"Loaded {channel_name}: {len(signal.data)} samples, fs={signal.fs}, units={normalized_units}")
                
            except Exception as e:
                self.logger.error(f"Failed to load signal {channel_name}: {e}")
                continue
        
        if not signal_data:
            raise ValueError("No signals could be loaded for export")
        
        return signal_data, channel_info
    
    def _apply_time_range(self, signal: Signal, time_range: tuple) -> Signal:
        """
        Extract time range from signal.
        
        Args:
            signal: Input signal
            time_range: Tuple (start_sec, end_sec)
            
        Returns:
            Signal with extracted time range
        """
        start_sec, end_sec = time_range
        
        # Convert time to sample indices
        start_idx = int(start_sec * signal.fs)
        end_idx = int(end_sec * signal.fs)
        
        # Clamp indices
        start_idx = max(0, start_idx)
        end_idx = min(len(signal.data), end_idx)
        
        if start_idx >= end_idx:
            raise ValueError(f"Invalid time range: {time_range}")
        
        # Extract data and time
        extracted_data = signal.data[start_idx:end_idx]
        extracted_time = np.arange(len(extracted_data)) / signal.fs + start_sec
        
        # Create new signal
        new_signal = Signal(
            name=signal.name,
            data=extracted_data,
            time=extracted_time,
            units=signal.units,
            fs=signal.fs
        )
        
        # Copy marker data
        new_signal.MarkerData = signal.MarkerData
        
        return new_signal
    
    def _resample_signals(self, signal_data: dict, channel_info: dict, target_fs: Optional[float]) -> tuple:
        """
        Resample signals to common sampling frequency.
        
        Args:
            signal_data: Dictionary of channel_name -> data arrays
            channel_info: Dictionary of channel metadata
            target_fs: Target sampling frequency (None = auto-detect)
            
        Returns:
            Tuple of (resampled_signal_data, updated_channel_info)
        """
        # Determine target frequency
        fs_values = [info['fs'] for info in channel_info.values()]
        unique_fs = list(set(fs_values))
        
        if len(unique_fs) == 1:
            # All signals have same fs, no resampling needed
            self.logger.debug(f"All signals have same fs: {unique_fs[0]}Hz, no resampling needed")
            return signal_data, channel_info
        
        if target_fs is None:
            target_fs = max(unique_fs)
        
        self.logger.info(f"Resampling signals to {target_fs}Hz (from {unique_fs})")
        
        resampled_data = {}
        updated_info = {}
        
        for channel_name, data in signal_data.items():
            original_fs = channel_info[channel_name]['fs']
            
            if original_fs == target_fs:
                # No resampling needed
                resampled_data[channel_name] = data
            else:
                # Resample using MNE (convert to float64 for MNE compatibility)
                data_float64 = data.astype(np.float64)
                resampled_data[channel_name] = mne.filter.resample(
                    data_float64, up=int(target_fs), down=int(original_fs), verbose=False
                )
                
                self.logger.debug(f"Resampled {channel_name}: {len(data)} -> {len(resampled_data[channel_name])} samples")
            
            # Update channel info
            updated_info[channel_name] = channel_info[channel_name].copy()
            updated_info[channel_name]['fs'] = target_fs
            updated_info[channel_name]['length'] = len(resampled_data[channel_name])
        
        return resampled_data, updated_info
    
    def _create_mne_raw(self, signal_data: dict, channel_info: dict, patient_id: str, recording_info: Optional[str]) -> mne.io.RawArray:
        """
        Create MNE Raw object from signal data.
        
        Args:
            signal_data: Dictionary of channel_name -> data arrays
            channel_info: Dictionary of channel metadata
            patient_id: Patient identifier
            recording_info: Recording description
            
        Returns:
            MNE RawArray object
        """
        # Prepare data for MNE
        channel_names = list(signal_data.keys())
        data_matrix = np.vstack([signal_data[name] for name in channel_names])
        
        # Get sampling frequency (should be uniform after resampling)
        sfreq = channel_info[channel_names[0]]['fs']
        
        # All channels as 'misc' type for maximum compatibility
        ch_types = [self.default_channel_type] * len(channel_names)
        
        # Create MNE info
        info = mne.create_info(ch_names=channel_names, sfreq=sfreq, ch_types=ch_types)
        
        # Set metadata (don't set meas_date in info directly)
        info["subject_info"] = {"his_id": patient_id}
        if recording_info:
            info["description"] = recording_info
        
        # Apply units to channels
        for idx, name in enumerate(channel_names):
            units_str = channel_info[name]['units']
            base_unit, unit_mul = self.unit_map.get(units_str, (0, 0))
            
            info["chs"][idx]["unit"] = base_unit
            info["chs"][idx]["unit_mul"] = unit_mul
            
            self.logger.debug(f"Channel {name}: units='{units_str}' -> base={base_unit}, mul={unit_mul}")
        
        # Create Raw object
        raw = mne.io.RawArray(data_matrix, info)
        
        # TODO: meas_date debería ser cuando se tomó la grabación (info del .adicht), 
        # pero no estoy seguro si está disponible. Por ahora usar tiempo actual en UTC.
        raw.set_meas_date(dt.datetime.now(dt.timezone.utc))
        
        self.logger.debug(f"Created MNE Raw: {len(channel_names)} channels, {data_matrix.shape[1]} samples, {sfreq}Hz (all as 'misc' type)")
        
        return raw
    
    def _add_filtered_annotations(
        self, 
        raw: mne.io.RawArray, 
        file_path: str, 
        excluded_comment_ids: Optional[Set[int]], 
        time_range: Optional[tuple]
    ) -> None:
        """
        Add filtered annotations to MNE Raw object.
        
        Args:
            raw: MNE Raw object to add annotations to
            file_path: Source file path
            excluded_comment_ids: Set of comment IDs to exclude
            time_range: Time range for filtering annotations
        """
        try:
            # Get all comments for the file
            all_comments = self.data_manager.get_comments(file_path)
            
            if not all_comments:
                self.logger.info("No comments found in source file")
                return
            
            # Filter comments
            filtered_comments = []
            excluded_count = 0
            
            for comment in all_comments:
                # Exclude by ID if specified
                if excluded_comment_ids and int(comment.comment_id) in excluded_comment_ids:
                    excluded_count += 1
                    continue
                
                # Filter by time range if specified
                if time_range is not None:
                    start_sec, end_sec = time_range
                    if not (start_sec <= comment.time <= end_sec):
                        continue
                    
                    # Adjust time for time range offset
                    adjusted_comment = EMSComment(
                        text=comment.text,
                        time_sec=comment.time - start_sec,  # Adjust for time offset
                        comment_id=comment.comment_id,
                        user_defined=comment.user_defined
                    )
                    filtered_comments.append(adjusted_comment)
                else:
                    filtered_comments.append(comment)
            
            if filtered_comments:
                # Create MNE annotations
                onsets = [c.time for c in filtered_comments]
                durations = [0.0] * len(filtered_comments)  # Point annotations
                descriptions = [c.text for c in filtered_comments]
                
                annotations = mne.Annotations(onsets, durations, descriptions)
                raw.set_annotations(annotations)
                
                self.logger.info(f"Added {len(filtered_comments)} annotations (excluded {excluded_count})")
            else:
                self.logger.info(f"All {len(all_comments)} comments were filtered out")
        
        except Exception as e:
            self.logger.error(f"Failed to add annotations: {e}")
            # Non-critical error, continue with export
    
    def _export_raw_to_edf(self, raw: mne.io.RawArray, output_path: str, overwrite: bool) -> None:
        """
        Export MNE Raw object to EDF+ file.
        
        Args:
            raw: MNE Raw object to export
            output_path: Output file path
            overwrite: Overwrite existing file
        """
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Export using MNE
            mne.export.export_raw(
                output_path,
                raw,
                fmt="edf",
                physical_range="auto",
                add_ch_type=False,
                overwrite=overwrite,
                verbose=False
            )
            
            self.logger.info(f"EDF+ file exported successfully: {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export EDF+ file: {e}")
            raise
    
    def get_export_info(self, file_path: str, channels: Optional[List[str]] = None) -> dict:
        """
        Get information about what would be exported.
        
        Args:
            file_path: Source file path
            channels: Channels to export (None = all)
            
        Returns:
            Dictionary with export information
        """
        if not self.data_manager.is_file_loaded(file_path):
            raise ValueError(f"File not loaded: {file_path}")
        
        available_channels = self.data_manager.get_available_channels(file_path)
        export_channels = channels or available_channels
        all_comments = self.data_manager.get_comments(file_path)
        
        # Analyze units that would be exported
        units_info = {}
        for channel in export_channels:
            try:
                signal = self.data_manager.get_trace(file_path, channel)
                if signal:
                    normalized_units = self._normalize_units(signal.units)
                    units_info[channel] = {
                        'original_units': str(signal.units),
                        'normalized_units': normalized_units,
                        'mne_mapping': self.unit_map.get(normalized_units, (0, 0))
                    }
            except Exception as e:
                units_info[channel] = {'error': str(e)}
        
        return {
            "file_path": file_path,
            "available_channels": available_channels,
            "export_channels": export_channels,
            "total_comments": len(all_comments),
            "channel_count": len(export_channels),
            "supports_hr_gen": "ECG" in available_channels or "EKG" in available_channels,
            "units_analysis": units_info
        }