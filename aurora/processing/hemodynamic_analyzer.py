"""
hemodynamic_analyzer.py
-----------------------
Análisis hemodinámico para exportación compatible con formato RedCap.
Implementa los cálculos requeridos según extract_stand_tilt.m
"""

import numpy as np
from typing import Dict, Tuple, List, Optional, Any
import logging
from aurora.core.signal import Signal


class HemodynamicAnalyzer:
    """
    Analizador hemodinámico que implementa cálculos específicos
    para protocolos ortostáticos (Stand/Tilt/LBNP).
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def calculate_rr_intervals(
        hr_signal: Signal, ecg_signal: Signal = None
    ) -> np.ndarray:
        """
        Calcula intervalos RR desde HR_gen o ECG.

        Args:
            hr_signal: Señal HR_gen generada
            ecg_signal: Señal ECG opcional para validación

        Returns:
            np.ndarray: Intervalos RR en milisegundos
        """
        if not isinstance(hr_signal, Signal):
            raise ValueError("hr_signal debe ser una instancia de Signal")

        # Si es HR_Gen_Signal, usar r_peaks directamente
        if hasattr(hr_signal, "r_peaks") and len(hr_signal.r_peaks) > 1:
            peaks = hr_signal.r_peaks
            rr_intervals = np.diff(peaks) / hr_signal.fs * 1000  # Convertir a ms
            return rr_intervals

        # Alternativamente, calcular desde datos HR
        hr_data = hr_signal.data
        time_data = hr_signal.time

        # Encontrar cambios en HR (indicativo de nuevos latidos)
        hr_changes = np.where(np.diff(hr_data) != 0)[0]

        if len(hr_changes) > 1:
            # Calcular RR desde cambios de HR
            rr_times = time_data[hr_changes]
            rr_intervals = np.diff(rr_times) * 1000  # Convertir a ms
            return rr_intervals

        return np.array([])

    @staticmethod
    def extract_systolic_diastolic(
        fbp_signal: Signal, map_signal: Signal = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extrae presión sistólica y diastólica desde FBP.

        Args:
            fbp_signal: Señal de presión arterial continua
            map_signal: Señal MAP opcional para validación

        Returns:
            Tuple[np.ndarray, np.ndarray]: (sistólica, diastólica)
        """
        if not isinstance(fbp_signal, Signal):
            raise ValueError("fbp_signal debe ser una instancia de Signal")

        fbp_data = fbp_signal.data
        fs = fbp_signal.fs

        # Ventana para detectar picos (aprox 1 segundo)
        window_size = int(fs)

        # Inicializar arrays
        systolic = []
        diastolic = []

        # Procesar en ventanas deslizantes
        for i in range(0, len(fbp_data) - window_size, window_size // 2):
            window = fbp_data[i : i + window_size]

            # Detectar pico sistólico (máximo)
            sys_val = np.max(window)
            systolic.append(sys_val)

            # Detectar valle diastólico (mínimo)
            dias_val = np.min(window)
            diastolic.append(dias_val)

        return np.array(systolic), np.array(diastolic)

    @staticmethod
    def find_nadir_events(
        sbp_data: np.ndarray, time_data: np.ndarray, window_sec: float = 60.0
    ) -> Dict[str, Any]:
        """
        Encuentra eventos de nadir (mínimo de presión sistólica) según MATLAB.

        Args:
            sbp_data: Datos de presión sistólica
            time_data: Array de tiempo correspondiente
            window_sec: Ventana temporal para búsqueda de nadir

        Returns:
            Dict con información del nadir
        """
        # Buscar en los primeros window_sec segundos
        mask = time_data <= window_sec
        windowed_sbp = sbp_data[mask]
        windowed_time = time_data[mask]

        if len(windowed_sbp) == 0:
            return {"found": False}

        # Encontrar índice de mínimo
        nadir_idx = np.argmin(windowed_sbp)

        return {
            "found": True,
            "time": float(windowed_time[nadir_idx]),
            "sbp": float(windowed_sbp[nadir_idx]),
            "index": int(nadir_idx),
        }

    @staticmethod
    def find_peak_hr_events(
        hr_data: np.ndarray, time_data: np.ndarray, nadir_time: float = None
    ) -> Dict[str, Any]:
        """
        Encuentra picos de HR después del nadir según protocolo MATLAB.

        Args:
            hr_data: Datos de frecuencia cardíaca
            time_data: Array de tiempo
            nadir_time: Tiempo del nadir SBP (para buscar pico posterior)

        Returns:
            Dict con información de picos HR
        """
        results = {}

        # Pico HR en primeros 60 segundos
        mask_60s = time_data <= 60.0
        if np.any(mask_60s):
            hr_60s = hr_data[mask_60s]
            time_60s = time_data[mask_60s]

            peak_idx_60s = np.argmax(hr_60s)
            results["peak_hr_60s"] = {
                "hr": float(hr_60s[peak_idx_60s]),
                "time": float(time_60s[peak_idx_60s]),
            }

        # Pico HR después del nadir (si se proporciona)
        if nadir_time is not None:
            mask_post_nadir = time_data > nadir_time
            if np.any(mask_post_nadir):
                hr_post = hr_data[mask_post_nadir]
                time_post = time_data[mask_post_nadir]

                # Buscar en ventana de 60s después del nadir
                mask_window = time_post <= (nadir_time + 60.0)
                if np.any(mask_window):
                    hr_window = hr_post[mask_window]
                    time_window = time_post[mask_window]

                    peak_idx = np.argmax(hr_window)
                    results["peak_hr_after_nadir"] = {
                        "hr": float(hr_window[peak_idx]),
                        "time": float(time_window[peak_idx]),
                    }

        # Pico HR en últimos 5 minutos (5-10 min)
        mask_last5m = (time_data >= 300.0) & (time_data <= 600.0)
        if np.any(mask_last5m):
            hr_last5m = hr_data[mask_last5m]
            time_last5m = time_data[mask_last5m]

            peak_idx_last5m = np.argmax(hr_last5m)
            results["peak_hr_last5m"] = {
                "hr": float(hr_last5m[peak_idx_last5m]),
                "time": float(time_last5m[peak_idx_last5m]) / 60.0,  # En minutos
            }

        return results

    @staticmethod
    def extract_temporal_windows(
        signal: Signal, time_points: List[float]
    ) -> Dict[float, float]:
        """
        Extrae valores de señal en puntos temporales específicos (20s, 30s, etc.).

        Args:
            signal: Señal a analizar
            time_points: Lista de tiempos en segundos [20, 30, 40, 50]

        Returns:
            Dict[float, float]: {tiempo: valor}
        """
        results = {}

        for time_point in time_points:
            # Encontrar índice más cercano al tiempo solicitado
            time_diff = np.abs(signal.time - time_point)
            closest_idx = np.argmin(time_diff)

            # Verificar que esté dentro de un margen razonable (±2s)
            if time_diff[closest_idx] <= 2.0:
                results[time_point] = float(signal.data[closest_idx])
            else:
                results[time_point] = np.nan

        return results

    @staticmethod
    def calculate_statistics_in_window(
        signal: Signal, start_time: float, end_time: float
    ) -> Dict[str, float]:
        """
        Calcula estadísticas (mean, max, min) en ventana temporal.

        Args:
            signal: Señal a analizar
            start_time: Tiempo inicial en segundos
            end_time: Tiempo final en segundos

        Returns:
            Dict con estadísticas calculadas
        """
        mask = (signal.time >= start_time) & (signal.time <= end_time)

        if not np.any(mask):
            return {"mean": np.nan, "max": np.nan, "min": np.nan}

        windowed_data = signal.data[mask]

        return {
            "mean": float(np.nanmean(windowed_data)),
            "max": float(np.nanmax(windowed_data)),
            "min": float(np.nanmin(windowed_data)),
        }

    def prepare_hemodynamic_analysis(
        self, signals: Dict[str, Signal], protocol: str = "stand"
    ) -> Dict[str, Any]:
        """
        Prepara análisis hemodinámico completo para un protocolo específico.

        Args:
            signals: Diccionario de señales {nombre: Signal}
            protocol: Tipo de protocolo ("stand", "tilt", "lbnp")

        Returns:
            Dict con todos los cálculos hemodinámicos
        """
        self.logger.info(f"Iniciando análisis hemodinámico para protocolo: {protocol}")

        results = {
            "protocol": protocol,
            "temporal_windows": {},
            "nadir_events": {},
            "peak_events": {},
            "statistics": {},
        }

        # Verificar señales requeridas
        required_signals = ["HR_gen", "FBP"]
        available_signals = list(signals.keys())

        missing = [sig for sig in required_signals if sig not in available_signals]
        if missing:
            self.logger.warning(f"Señales faltantes para análisis completo: {missing}")

        # Análisis de presión arterial
        if "FBP" in signals:
            fbp_signal = signals["FBP"]
            map_signal = signals.get("MAP")

            try:
                systolic, diastolic = self.extract_systolic_diastolic(
                    fbp_signal, map_signal
                )

                # Crear señales derivadas temporales
                time_sys = np.linspace(0, fbp_signal.time[-1], len(systolic))

                # Buscar nadir
                nadir_info = self.find_nadir_events(systolic, time_sys)
                results["nadir_events"] = nadir_info

                self.logger.debug(f"Nadir encontrado: {nadir_info}")

            except Exception as e:
                self.logger.error(f"Error en análisis de presión arterial: {e}")

        # Análisis de HR
        if "HR_gen" in signals:
            hr_signal = signals["HR_gen"]

            try:
                # Buscar picos HR
                nadir_time = results["nadir_events"].get("time")
                peak_info = self.find_peak_hr_events(
                    hr_signal.data, hr_signal.time, nadir_time
                )
                results["peak_events"] = peak_info

                # Ventanas temporales estándar
                time_points = [20, 30, 40, 50]
                temporal_hr = self.extract_temporal_windows(hr_signal, time_points)
                results["temporal_windows"]["HR"] = temporal_hr

                self.logger.debug(
                    f"Análisis HR completado: {len(peak_info)} eventos encontrados"
                )

            except Exception as e:
                self.logger.error(f"Error en análisis de HR: {e}")

        # Análisis de otras señales
        signal_names = ["CO", "SV", "SVR", "ETCO2"]
        time_points = [20, 30, 40, 50]

        for sig_name in signal_names:
            if sig_name in signals:
                try:
                    temporal_values = self.extract_temporal_windows(
                        signals[sig_name], time_points
                    )
                    results["temporal_windows"][sig_name] = temporal_values

                    # Estadísticas en últimos 5 minutos
                    stats_5m = self.calculate_statistics_in_window(
                        signals[sig_name], 300, 600
                    )
                    results["statistics"][f"{sig_name}_last5m"] = stats_5m

                except Exception as e:
                    self.logger.error(f"Error analizando {sig_name}: {e}")

        self.logger.info("Análisis hemodinámico completado")
        return results
