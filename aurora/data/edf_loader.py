"""
EDF+ Loader for Aurora
Supports loading of EDF/EDF+ files with annotations and signal data.
"""

import numpy as np
import mne
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from aurora.core.signal import Signal, HR_Gen_Signal
from aurora.core.comments import EMSComment
from aurora.data.base_loader import BaseLoader


class EDFLoader(BaseLoader):
    """
    Loader for EDF/EDF+ files using MNE-Python.
    
    Features:
    - Load signal data from EDF/EDF+ files
    - Extract annotations as comments
    - Support for multiple channel types (ECG, EEG, EMG, etc.)
    - Automatic unit conversion
    - HR_gen derivation from ECG when available
    """
    
    def __init__(self):
        self.path: Optional[str] = None
        self.raw_data: Optional[mne.io.BaseRaw] = None
        self.metadata: Dict[str, Any] = {}
        self.comments: List[EMSComment] = []
        self.logger = logging.getLogger(f"aurora.data.{self.__class__.__name__}")
        
    def load(self, path: str) -> None:
        """
        Load EDF/EDF+ file and extract metadata, signals, and annotations.
        
        Args:
            path: Path to EDF/EDF+ file
        """
        try:
            self.path = path
            self.logger.info(f"Loading EDF+ file: {path}")
            
            # Load using MNE with preload=False for memory efficiency
            self.raw_data = mne.io.read_raw_edf(path, preload=False, verbose=False)
            
            # Extract basic metadata
            info = self.raw_data.info
            self.metadata = {
                "channels": info["ch_names"],
                "fs": {ch_name: info["sfreq"] for ch_name in info["ch_names"]},
                "n_records": len(self.raw_data.times),
                "duration": self.raw_data.times[-1] if len(self.raw_data.times) > 0 else 0.0,
                "subject_info": info.get("subject_info", {}),
                "meas_date": info.get("meas_date"),
                "description": info.get("description", "")
            }
            
            # Extract annotations as comments
            self._extract_annotations()
            
            self.logger.info(f"EDF+ loaded: {len(self.metadata['channels'])} channels, "
                           f"{self.metadata['duration']:.1f}s duration, "
                           f"{len(self.comments)} annotations")
            
        except Exception as e:
            self.logger.error(f"Failed to load EDF+ file {path}: {e}")
            raise
    
    def _extract_annotations(self) -> None:
        """Extract annotations from EDF+ file as EMSComment objects."""
        self.comments = []
        
        if self.raw_data.annotations is None:
            return
        
        annotations = self.raw_data.annotations
        
        for i, (onset, duration, description) in enumerate(zip(
            annotations.onset, annotations.duration, annotations.description
        )):
            comment = EMSComment(
                text=description,
                time_sec=float(onset),
                comment_id=i + 1,
                user_defined=False  # EDF+ annotations are from file, not user-created
            )
            self.comments.append(comment)
            
        self.logger.debug(f"Extracted {len(self.comments)} annotations from EDF+")
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return file metadata."""
        return self.metadata
    
    def get_all_comments(self) -> List[EMSComment]:
        """Return all comments/annotations from the file."""
        return self.comments
    
    def get_full_trace(self, channel: str, gap_length: int = 3, **kwargs) -> Signal:
        """
        Return a full Signal for the given channel.
        
        Args:
            channel: Channel name to extract
            gap_length: Gap length (unused for EDF, kept for compatibility)
            **kwargs: Additional parameters for HR_gen derivation
            
        Returns:
            Signal object with data, time, and metadata
        """
        upper = channel.upper()
        
        # Handle HR_gen derivation from ECG
        if upper == "HR_GEN" and self._has_ecg_channel():
            return self._derive_hr_signal(**kwargs)
        
        # Load raw channel data
        if channel not in self.metadata["channels"]:
            raise ValueError(f"Channel '{channel}' not found in EDF+ file. "
                           f"Available channels: {self.metadata['channels']}")
        
        # Load data for specific channel
        channel_idx = self.metadata["channels"].index(channel)
        
        # Load all data if not already loaded
        if not self.raw_data.preload:
            self.raw_data.load_data()
        
        # Extract channel data
        data = self.raw_data.get_data(picks=[channel_idx])[0]  # Shape: (1, n_samples) -> (n_samples,)
        fs = self.metadata["fs"][channel]
        
        # Create time array
        time = np.arange(len(data)) / fs
        
        # Get channel info for units
        ch_info = self.raw_data.info["chs"][channel_idx]
        units = self._get_channel_units(ch_info)
        
        # Create Signal object
        signal = Signal(
            name=channel,
            data=data,
            time=time,
            units=units,
            fs=fs
        )
        
        # Add comments as marker data (compatible with existing system)
        signal.MarkerData = self.comments
        
        self.logger.debug(f"Loaded signal '{channel}': {len(data)} samples, fs={fs}Hz")
        
        return signal
    
    def _has_ecg_channel(self) -> bool:
        """Check if file contains ECG channel for HR derivation."""
        ecg_patterns = ["ECG", "EKG", "ecg", "ekg"]
        return any(pattern in self.metadata["channels"] for pattern in ecg_patterns)
    
    def _get_ecg_channel_name(self) -> Optional[str]:
        """Find ECG channel name in the file."""
        ecg_patterns = ["ECG", "EKG", "ecg", "ekg"]
        for channel in self.metadata["channels"]:
            if any(pattern in channel for pattern in ecg_patterns):
                return channel
        return None
    
    def _derive_hr_signal(self, **kwargs) -> HR_Gen_Signal:
        """
        Derive HR signal from ECG using existing HR_Gen_Signal class.
        
        Args:
            **kwargs: Parameters for HR derivation (wavelet, swt_level, min_rr_sec)
            
        Returns:
            HR_Gen_Signal object with derived HR data
        """
        ecg_channel = self._get_ecg_channel_name()
        if not ecg_channel:
            raise ValueError("No ECG channel found for HR derivation")
        
        # Load ECG signal
        ecg_signal = self.get_full_trace(ecg_channel)
        
        # Extract HR parameters
        wavelet = kwargs.get('wavelet', 'haar')
        swt_level = kwargs.get('swt_level', 4)
        min_rr_sec = kwargs.get('min_rr_sec', 0.6)
        
        # Create HR_Gen_Signal
        hr_signal = HR_Gen_Signal(
            name="HR_gen",
            ecg_data=ecg_signal.data,
            ecg_time=ecg_signal.time,
            units="bpm",
            fs=ecg_signal.fs
        )
        
        # Set R-peaks and derive HR
        hr_signal.set_r_peaks(
            ecg_signal,
            wavelet=wavelet,
            swt_level=swt_level,
            min_rr_sec=min_rr_sec
        )
        
        # Copy marker data
        hr_signal.MarkerData = ecg_signal.MarkerData
        
        # Update metadata to include HR_gen channel
        if "HR_gen" not in self.metadata["channels"]:
            self.metadata["channels"].append("HR_gen")
            self.metadata["fs"]["HR_gen"] = hr_signal.fs
        
        self.logger.info(f"Derived HR signal from ECG using wavelet='{wavelet}', "
                        f"swt_level={swt_level}, min_rr_sec={min_rr_sec}")
        
        return hr_signal
    
    def _get_channel_units(self, ch_info: Dict[str, Any]) -> str:
        """
        Extract channel units from MNE channel info.
        
        Args:
            ch_info: Channel information dictionary from MNE
            
        Returns:
            Unit string (V, mV, µV, etc.)
        """
        # MNE unit constants to string mapping
        unit_mapping = {
            mne.io.constants.FIFF.FIFF_UNIT_V: "V",
            mne.io.constants.FIFF.FIFF_UNIT_T: "T",  # Tesla for MEG
            0: "unknown"  # Default for unknown units
        }
        
        # Get base unit
        base_unit = ch_info.get("unit", 0)
        unit_mul = ch_info.get("unit_mul", 0)
        
        base_str = unit_mapping.get(base_unit, "unknown")
        
        # Apply multiplier to get proper unit
        if base_str == "V" and unit_mul != 0:
            if unit_mul == -3:
                return "mV"
            elif unit_mul == -6:
                return "µV"
            elif unit_mul == -9:
                return "nV"
        
        return base_str
    
    def cleanup(self) -> None:
        """Clean up resources when loader is no longer needed."""
        try:
            if self.raw_data is not None:
                self.raw_data.close()
                self.raw_data = None
            
            self.metadata.clear()
            self.comments.clear()
            self.path = None
            
            self.logger.debug("EDFLoader cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during EDFLoader cleanup: {e}")