"""
CSV Export Module for AuroraWave
Handles the export of signal statistics to CSV format.
"""

import csv
from typing import List, Tuple, Dict, Any, Optional
from Pyside.core import get_user_logger
from Pyside.processing.interval_extractor import extract_event_intervals


class CSVExporter:
    """Handles CSV export functionality for signal data."""

    def __init__(self, data_manager, hr_params=None):
        self.data_manager = data_manager
        self.logger = get_user_logger(self.__class__.__name__)
        self.hr_params = hr_params or {}
        
    def _parse_hr_channel_name(self, channel_name: str):
        """
        Parse a descriptive HR channel name back to channel and parameters.
        
        Args:
            channel_name: Either "HR_gen" or "HR_gen_wavelet_lv#_rr#"
            
        Returns:
            (base_channel, hr_params_dict)
        """
        if not channel_name.upper().startswith("HR_GEN"):
            return channel_name, {}
            
        if channel_name.upper() == "HR_GEN":
            return "HR_gen", self.hr_params
            
        # Parse descriptive name like "HR_gen_db5_lv1_rr0.6"
        parts = channel_name.split('_')
        if len(parts) >= 5:  # HR_gen_wavelet_lv#_rr#
            try:
                wavelet = parts[2]
                level_str = parts[3][2:]  # Remove "lv" prefix
                rr_str = parts[4][2:]     # Remove "rr" prefix
                
                hr_params = {
                    "wavelet": wavelet,
                    "swt_level": int(level_str),
                    "min_rr_sec": float(rr_str)
                }
                return "HR_gen", hr_params
            except (ValueError, IndexError):
                self.logger.warning(f"Could not parse HR channel name: {channel_name}")
                return "HR_gen", self.hr_params
        
        return "HR_gen", self.hr_params

    def extract_test_entries(self, file_path: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Extract test entries from file for selection dialog."""
        try:
            # Solo cargamos ECG para extraer comentarios (es más liviano)
            ecg_trace = self.data_manager.get_trace(file_path, "ECG")
            intervals = extract_event_intervals([ecg_trace])

            test_entries = []
            for iv in intervals:
                evento = iv.get("evento")
                if evento:
                    # Crear identificador único con tiempo de inicio
                    t_start = iv.get("t_evento") or iv.get("t_tilt_angle", 0)
                    # Formatear tiempo en minutos:segundos
                    tiempo_str = f"{int(t_start//60):02d}:{int(t_start%60):02d}"
                    display_name = f"{evento} (at {tiempo_str})"
                    test_entries.append((display_name, iv))

            # Ordenar por tiempo de inicio
            test_entries.sort(
                key=lambda x: x[1].get("t_evento", 0) or x[1].get("t_tilt_angle", 0)
            )
            return test_entries

        except Exception as e:
            self.logger.warning(f"Could not extract events: {str(e)}")
            return []

    def prepare_export_intervals(
        self, selected_tests: List[str], test_entries: List[Tuple[str, Dict[str, Any]]]
    ) -> List[Tuple[str, float, Optional[float]]]:
        """Prepare intervals for export based on selected tests."""
        export_intervals = []

        if selected_tests and test_entries:
            # Crear mapeo de nombres de display a intervalos
            test_map = {entry[0]: entry[1] for entry in test_entries}

            for test_name in selected_tests:
                if test_name in test_map:
                    iv = test_map[test_name]
                    # Obtener tiempos según el tipo de test
                    if iv.get("tipo") == "tilt_angle":
                        s = iv.get("t_evento") or iv.get("t_tilt_angle")
                        e = iv.get("t_tilt_down")
                    else:  # tipo "coms"
                        s = iv.get("t_evento")
                        e = iv.get("t_recovery")

                    if s is not None and e is not None:
                        # Usar el nombre original del evento
                        original_name = iv.get("evento", test_name.split(" (at ")[0])
                        export_intervals.append((original_name, s, e))
        else:
            # Si no hay tests seleccionados, exportar señal completa
            export_intervals.append(("Full_Signal", 0, None))

        return export_intervals

    # Note: calculate_signal_statistics and calculate_full_signal_statistics methods
    # have been consolidated into the export_to_csv method for better organization
    # and to support the new row-based CSV format

    def generate_headers(
        self,
        selected_signals: List[str],
        export_intervals: List[Tuple[str, float, Optional[float]]],
        segment_duration: float = 60.0,  # Nueva opción configurable
    ) -> List[str]:
        """Generate CSV headers for row-based format with event and channel identification."""
        # Row-based format with explicit columns for better data organization
        headers = [
            "Event",           # Source event name
            "Channel",         # Signal channel name
            "Segment",         # Segment number or "Full"
            "Start_Time_s",    # Segment start time in seconds
            "End_Time_s",      # Segment end time in seconds
            "Duration_s",      # Segment duration in seconds
            "Mean",            # Mean value
            "Max"              # Maximum value
        ]
        
        return headers
    
    def _get_descriptive_channel_name(self, channel: str) -> str:
        """
        Return the channel name as-is since channels are already descriptive.
        
        Args:
            channel: Channel name (already descriptive for HR_gen variants)
            
        Returns:
            Channel name for use in CSV headers
        """
        return channel

    def export_to_csv(
        self,
        file_path: str,
        selected_signals: List[str],
        selected_tests: List[str],
        test_entries: List[Tuple[str, Dict[str, Any]]],
        save_path: str,
        minute_duration: float = 60.0,  # Nueva opción configurable
    ) -> None:
        """Export selected signals and tests to CSV file with row-based format."""

        # Preparar intervalos de exportación
        export_intervals = self.prepare_export_intervals(selected_tests, test_entries)

        if not export_intervals:
            raise ValueError("No valid intervals found for export")

        # Generar headers para formato basado en filas
        headers = self.generate_headers(
            selected_signals, export_intervals, minute_duration
        )
        rows = []

        # Generate one row per channel per segment per event
        for test_name, start_time, end_time in export_intervals:
            for channel in selected_signals:
                if end_time is not None:
                    # Segmented analysis
                    duration = end_time - start_time
                    segments = int(duration / minute_duration) + 1

                    for seg_idx in range(segments):
                        seg_start = start_time + (seg_idx * minute_duration)
                        seg_end = (
                            min(start_time + ((seg_idx + 1) * minute_duration), end_time)
                            if end_time
                            else seg_start + minute_duration
                        )
                        seg_duration = seg_end - seg_start

                        # Calculate statistics for this specific segment
                        try:
                            # Parse channel name to get base channel and HR parameters
                            base_channel, hr_params = self._parse_hr_channel_name(channel)
                            
                            if base_channel.upper() == "HR_GEN":
                                sig = self.data_manager.get_trace(file_path, base_channel, **hr_params)
                            else:
                                sig = self.data_manager.get_trace(file_path, base_channel)

                            data = sig.data
                            fs = sig.fs
                            i0 = int(seg_start * fs)
                            i1 = int(seg_end * fs)
                            seg_data = data[i0:i1] if i1 <= len(data) else data[i0:]

                            if seg_data.size > 0:
                                mean_val = float(seg_data.mean())
                                max_val = float(seg_data.max())
                            else:
                                mean_val = ""
                                max_val = ""

                        except Exception as ex:
                            base_channel, _ = self._parse_hr_channel_name(channel)
                            self.logger.warning(f"Error processing {channel} (base: {base_channel}) segment {seg_idx+1}: {ex}")
                            mean_val = "ERROR"
                            max_val = "ERROR"

                        # Create row: Event, Channel, Segment, Start_Time_s, End_Time_s, Duration_s, Mean, Max
                        row = [
                            test_name,
                            self._get_descriptive_channel_name(channel),
                            f"Seg_{seg_idx+1}",
                            f"{seg_start:.2f}",
                            f"{seg_end:.2f}",
                            f"{seg_duration:.2f}",
                            f"{mean_val:.6f}" if isinstance(mean_val, float) else mean_val,
                            f"{max_val:.6f}" if isinstance(max_val, float) else max_val
                        ]
                        rows.append(row)

                else:
                    # Full signal analysis
                    try:
                        # Parse channel name to get base channel and HR parameters
                        base_channel, hr_params = self._parse_hr_channel_name(channel)
                        
                        if base_channel.upper() == "HR_GEN":
                            sig = self.data_manager.get_trace(file_path, base_channel, **hr_params)
                        else:
                            sig = self.data_manager.get_trace(file_path, base_channel)

                        data = sig.data
                        if data.size > 0:
                            mean_val = float(data.mean())
                            max_val = float(data.max())
                            duration = len(data) / sig.fs
                        else:
                            mean_val = ""
                            max_val = ""
                            duration = 0

                    except Exception as ex:
                        base_channel, _ = self._parse_hr_channel_name(channel)
                        self.logger.warning(f"Error processing full signal {channel} (base: {base_channel}): {ex}")
                        mean_val = "ERROR"
                        max_val = "ERROR"
                        duration = 0

                    # Create row: Event, Channel, Segment, Start_Time_s, End_Time_s, Duration_s, Mean, Max
                    row = [
                        test_name,
                        self._get_descriptive_channel_name(channel),
                        "Full",
                        "0.00",
                        f"{duration:.2f}",
                        f"{duration:.2f}",
                        f"{mean_val:.6f}" if isinstance(mean_val, float) else mean_val,
                        f"{max_val:.6f}" if isinstance(max_val, float) else max_val
                    ]
                    rows.append(row)

        # Write CSV file
        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)

        total_measurements = len(rows)
        unique_events = len(set(row[0] for row in rows))
        unique_channels = len(set(row[1] for row in rows))
        
        self.logger.info(
            f"CSV exported successfully: {total_measurements} measurements from {unique_events} events and {unique_channels} channels"
        )
