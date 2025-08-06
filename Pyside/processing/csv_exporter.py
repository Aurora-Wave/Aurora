"""
CSV Export Module for AuroraWave
Handles the export of signal statistics to CSV format.
"""

import csv
import logging
from typing import List, Tuple, Dict, Any, Optional
from Pyside.processing.interval_extractor import extract_event_intervals


class CSVExporter:
    """Handles CSV export functionality for signal data."""

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)

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

    def calculate_signal_statistics(
        self,
        file_path: str,
        channel: str,
        start_time: float,
        end_time: Optional[float],
        segments: int,
        segment_duration: float = 60.0,  # Nueva opción configurable
    ) -> List[str]:
        """Calculate statistics for a signal within specified time range."""
        row_data = []

        for seg_idx in range(segments):
            seg_start = start_time + (seg_idx * segment_duration)
            seg_end = (
                min(start_time + ((seg_idx + 1) * segment_duration), end_time)
                if end_time
                else seg_start + segment_duration
            )

            try:
                # Manejar HR_gen con parámetros por defecto
                if channel.upper() == "HR_GEN":
                    sig = self.data_manager.get_trace(
                        file_path, channel, wavelet="haar", swt_level=4, min_rr_sec=0.5
                    )
                else:
                    sig = self.data_manager.get_trace(file_path, channel)

                data = sig.data
                fs = sig.fs
                i0 = int(seg_start * fs)
                i1 = int(seg_end * fs)
                seg = data[i0:i1] if i1 <= len(data) else data[i0:]

                if seg.size > 0:
                    row_data.extend(
                        [
                            f"{float(seg.mean()):.6f}",
                            f"{float(seg.max()):.6f}",
                        ]
                    )
                else:
                    row_data.extend(["", ""])

            except Exception as ex:
                self.logger.warning(f"Error processing {channel}: {ex}")
                row_data.extend(["ERROR", "ERROR"])

        return row_data

    def calculate_full_signal_statistics(
        self, file_path: str, channel: str
    ) -> List[str]:
        """Calculate statistics for complete signal."""
        try:
            # Manejar HR_gen con parámetros por defecto
            if channel.upper() == "HR_GEN":
                sig = self.data_manager.get_trace(
                    file_path, channel, wavelet="haar", swt_level=4, min_rr_sec=0.5
                )
            else:
                sig = self.data_manager.get_trace(file_path, channel)

            data = sig.data
            if data.size > 0:
                return [
                    f"{float(data.mean()):.6f}",
                    f"{float(data.max()):.6f}",
                ]
            else:
                return ["", ""]

        except Exception as ex:
            self.logger.warning(f"Error processing {channel}: {ex}")
            return ["ERROR", "ERROR"]

    def generate_headers(
        self,
        selected_signals: List[str],
        export_intervals: List[Tuple[str, float, Optional[float]]],
        segment_duration: float = 60.0,  # Nueva opción configurable
    ) -> List[str]:
        """Generate CSV headers based on export configuration."""
        headers = []

        if not export_intervals:
            return headers

        # Usar el primer intervalo para determinar la estructura
        test_name, start_time, end_time = export_intervals[0]

        if end_time is not None:
            # Export por segmentos configurables
            duration = end_time - start_time
            segments = int(duration / segment_duration) + 1

            # Determinar nombre del segmento
            if segment_duration == 60.0:
                seg_name = "min"
            elif segment_duration == 30.0:
                seg_name = "30s"
            else:
                seg_name = f"{int(segment_duration)}s"

            for seg_idx in range(segments):
                for channel in selected_signals:
                    headers.extend(
                        [
                            f"{channel}_mean_{seg_name}{seg_idx+1}",
                            f"{channel}_max_{seg_name}{seg_idx+1}",
                        ]
                    )
        else:
            # Export de señal completa
            for channel in selected_signals:
                headers.extend([f"{channel}_mean_full", f"{channel}_max_full"])

        return headers

    def export_to_csv(
        self,
        file_path: str,
        selected_signals: List[str],
        selected_tests: List[str],
        test_entries: List[Tuple[str, Dict[str, Any]]],
        save_path: str,
        minute_duration: float = 60.0,  # Nueva opción configurable
    ) -> None:
        """Export selected signals and tests to CSV file."""

        # Preparar intervalos de exportación
        export_intervals = self.prepare_export_intervals(selected_tests, test_entries)

        if not export_intervals:
            raise ValueError("No valid intervals found for export")

        # Generar headers y filas
        headers = self.generate_headers(
            selected_signals, export_intervals, minute_duration
        )
        rows = []

        for test_name, start_time, end_time in export_intervals:
            row = []

            if end_time is not None:
                # Calcular estadísticas por segmentos configurables (antes eran minutos fijos)
                duration = end_time - start_time
                segments = int(duration / minute_duration) + 1

                for channel in selected_signals:
                    row_data = self.calculate_signal_statistics(
                        file_path,
                        channel,
                        start_time,
                        end_time,
                        segments,
                        minute_duration,
                    )
                    row.extend(row_data)
            else:
                # Señal completa
                for channel in selected_signals:
                    row_data = self.calculate_full_signal_statistics(file_path, channel)
                    row.extend(row_data)

            rows.append(row)

        # Escribir archivo CSV
        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)

        self.logger.info(
            f"CSV exported successfully: {len(rows)} rows, {len(selected_signals)} signals"
        )
