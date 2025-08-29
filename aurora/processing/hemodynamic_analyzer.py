"""
hemodynamic_analyzer.py
-----------------------
Hemodynamic analysis for RedCap-compatible export.
Implements calculations required per extract_stand_tilt.m
"""

import numpy as np
from typing import Dict, Tuple, List, Optional, Any
import logging
from aurora.core.signal import Signal


class HemodynamicAnalyzer:
    """Hemodynamic analyzer implementing protocol-specific calculations
    for orthostatic protocols (Stand/Tilt/LBNP)."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def calculate_rr_intervals(
        hr_signal: Signal, ecg_signal: Signal = None
    ) -> np.ndarray:
        """
        Compute RR intervals from hr_aurora (formerly HR_gen) or ECG.

            Args:
                hr_signal: hr_aurora signal (legacy alias HR_gen) generated
                ecg_signal: Optional ECG signal for validation

            Returns:
                np.ndarray: RR intervals in milliseconds
        """
        if not isinstance(hr_signal, Signal):
            raise ValueError("hr_signal must be a Signal instance")

        # If HRAuroraSignal/HR_Gen_Signal, use r_peaks directly
        if hasattr(hr_signal, "r_peaks") and len(hr_signal.r_peaks) > 1:
            peaks = hr_signal.r_peaks
            rr_intervals = np.diff(peaks) / hr_signal.fs * 1000  # ms
            return rr_intervals

        # Alternatively compute from HR data
        hr_data = hr_signal.data
        time_data = hr_signal.time

        # Find HR changes (beat boundaries)
        hr_changes = np.where(np.diff(hr_data) != 0)[0]

        if len(hr_changes) > 1:
            # Compute RR from HR changes
            rr_times = time_data[hr_changes]
            rr_intervals = np.diff(rr_times) * 1000  # ms
            return rr_intervals

        return np.array([])

    @staticmethod
    def extract_systolic_diastolic(
        fbp_signal: Signal, map_signal: Signal = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract systolic and diastolic pressure from FBP.

            Args:
                fbp_signal: Continuous blood pressure signal
                map_signal: Optional MAP signal for validation

            Returns:
                Tuple[np.ndarray, np.ndarray]: (systolic, diastolic)
        """
        if not isinstance(fbp_signal, Signal):
            raise ValueError("fbp_signal must be a Signal instance")

        fbp_data = fbp_signal.data
        fs = fbp_signal.fs

        # Window (~1 second) for peak detection
        window_size = int(fs)

        # Initialize arrays
        systolic = []
        diastolic = []

        # Sliding window processing
        for i in range(0, len(fbp_data) - window_size, window_size // 2):
            window = fbp_data[i : i + window_size]

            # Detect systolic peak (max)
            sys_val = np.max(window)
            systolic.append(sys_val)

            # Detect diastolic trough (min)
            dias_val = np.min(window)
            diastolic.append(dias_val)

        return np.array(systolic), np.array(diastolic)

    @staticmethod
    def find_nadir_events(
        sbp_data: np.ndarray, time_data: np.ndarray, window_sec: float = 60.0
    ) -> Dict[str, Any]:
        """
        Find nadir events (minimum systolic pressure) per MATLAB logic.

            Args:
                sbp_data: Systolic blood pressure data
                time_data: Corresponding time array
                window_sec: Time window for nadir search

            Returns:
                Dict with nadir information
        """
        # Search first window_sec seconds
        mask = time_data <= window_sec
        windowed_sbp = sbp_data[mask]
        windowed_time = time_data[mask]

        if len(windowed_sbp) == 0:
            return {"found": False}

        # Find index of minimum
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
        Find HR peaks after nadir per MATLAB protocol logic.

            Args:
                hr_data: Heart rate data
                time_data: Time array
                nadir_time: SBP nadir time (for subsequent peak search)

            Returns:
                Dict with HR peak information
        """
        results = {}

        # HR peak in first 60 seconds
        mask_60s = time_data <= 60.0
        if np.any(mask_60s):
            hr_60s = hr_data[mask_60s]
            time_60s = time_data[mask_60s]

            peak_idx_60s = np.argmax(hr_60s)
            results["peak_hr_60s"] = {
                "hr": float(hr_60s[peak_idx_60s]),
                "time": float(time_60s[peak_idx_60s]),
            }

        # HR peak after nadir (if provided)
        if nadir_time is not None:
            mask_post_nadir = time_data > nadir_time
            if np.any(mask_post_nadir):
                hr_post = hr_data[mask_post_nadir]
                time_post = time_data[mask_post_nadir]

                # Search 60s window after nadir
                mask_window = time_post <= (nadir_time + 60.0)
                if np.any(mask_window):
                    hr_window = hr_post[mask_window]
                    time_window = time_post[mask_window]

                    peak_idx = np.argmax(hr_window)
                    results["peak_hr_after_nadir"] = {
                        "hr": float(hr_window[peak_idx]),
                        "time": float(time_window[peak_idx]),
                    }

        # HR peak in last 5 minutes (5-10 min)
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
        Extract signal values at specific temporal points (20s, 30s, etc.).

            Args:
                signal: Signal to analyze
                time_points: Time points in seconds [20, 30, 40, 50]

            Returns:
                Dict[float, float]: {time: value}
        """
        results = {}

        for time_point in time_points:
            # Find closest index to requested time
            time_diff = np.abs(signal.time - time_point)
            closest_idx = np.argmin(time_diff)

            # Ensure within ±2s tolerance
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
        Compute statistics (mean, max, min) in temporal window.

            Args:
                signal: Signal to analyze
                start_time: Start time (s)
                end_time: End time (s)

            Returns:
                Dict with computed statistics
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
        Prepare complete hemodynamic analysis for a specific protocol.

        Args:
            signals: Dict of signals {name: Signal}
            protocol: Protocol type ("stand", "tilt", "lbnp")

        Returns:
            Dict with all hemodynamic calculations
        """
        self.logger.info(f"Starting hemodynamic analysis for protocol: {protocol}")

        results = {
            "protocol": protocol,
            "temporal_windows": {},
            "nadir_events": {},
            "peak_events": {},
            "statistics": {},
        }

        # Verify required signals
        required_signals = ["hr_aurora", "FBP"]
        available_signals = list(signals.keys())

        missing = [sig for sig in required_signals if sig not in available_signals]
        if missing:
            self.logger.warning(f"Missing signals for full analysis: {missing}")

        # Blood pressure analysis
        if "FBP" in signals:
            fbp_signal = signals["FBP"]
            map_signal = signals.get("MAP")

            try:
                systolic, diastolic = self.extract_systolic_diastolic(
                    fbp_signal, map_signal
                )

                # Create temporary derived signals
                time_sys = np.linspace(0, fbp_signal.time[-1], len(systolic))

                # Find nadir
                nadir_info = self.find_nadir_events(systolic, time_sys)
                results["nadir_events"] = nadir_info

                self.logger.debug(f"Nadir found: {nadir_info}")

            except Exception as e:
                self.logger.error(f"Error in blood pressure analysis: {e}")

        # HR analysis
        if "hr_aurora" in signals or "HR_gen" in signals:
            hr_signal = signals.get("hr_aurora") or signals.get("HR_gen")

            try:
                # Find HR peaks
                nadir_time = results["nadir_events"].get("time")
                peak_info = self.find_peak_hr_events(
                    hr_signal.data, hr_signal.time, nadir_time
                )
                results["peak_events"] = peak_info

                # Standard temporal windows
                time_points = [20, 30, 40, 50]
                temporal_hr = self.extract_temporal_windows(hr_signal, time_points)
                results["temporal_windows"]["HR"] = temporal_hr

                self.logger.debug(
                    f"HR analysis complete: {len(peak_info)} events found"
                )

            except Exception as e:
                self.logger.error(f"Error in HR analysis: {e}")

        # Other signals analysis
        signal_names = ["CO", "SV", "SVR", "ETCO2"]
        time_points = [20, 30, 40, 50]

        for sig_name in signal_names:
            if sig_name in signals:
                try:
                    temporal_values = self.extract_temporal_windows(
                        signals[sig_name], time_points
                    )
                    results["temporal_windows"][sig_name] = temporal_values

                    # Statistics in last 5 minutes
                    stats_5m = self.calculate_statistics_in_window(
                        signals[sig_name], 300, 600
                    )
                    results["statistics"][f"{sig_name}_last5m"] = stats_5m

                except Exception as e:
                    self.logger.error(f"Error analyzing {sig_name}: {e}")

        self.logger.info("Hemodynamic analysis completed")
        return results
