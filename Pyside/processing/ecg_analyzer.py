"""
ecg_analyzer.py
---------------
Utilities for ECG signal analysis: R-peak detection and wavelet transforms.
"""

import numpy as np
from scipy.signal import find_peaks
import pywt

class ECGAnalyzer:
    """
    Utility class for analyzing ECG signals.
    Provides static methods for RR peak detection and wavelet-based transformation.
    """
    @staticmethod
    def detect_rr_peaks(ecg_signal: np.ndarray, fs: float, distance_sec: float = 0.4, wavelet: str = "haar", level: int = 5) -> np.ndarray:
        """
        Detects R-peaks in an ECG signal using wavelet transform and adaptive thresholding.

        Args:
            ecg_signal (np.ndarray): Raw ECG signal array.
            fs (float): Sampling frequency in Hz.
            distance_sec (float): Minimum distance between peaks in seconds (default 0.4s).
            wavelet (str): Wavelet type (default 'haar').
            level (int): Decomposition level for wavelet transform (default 5).

        Returns:
            np.ndarray: Indices of detected R-peaks.
        """
        coeffs = pywt.wavedec(ecg_signal, wavelet, level=level)
        D5 = coeffs[1]
        upsample_factor = int(np.ceil(len(ecg_signal) / len(D5)))
        D5 = np.repeat(D5, upsample_factor)[:len(ecg_signal)]

        D5_sq = D5 ** 2
        threshold = np.percentile(D5_sq, 95)
        cleaned = np.where(D5_sq >= threshold, D5_sq, 0)

        r_peaks, _ = find_peaks(cleaned, distance=int(distance_sec * fs))
        return r_peaks

    @staticmethod
    def wavelet_transform(ecg_signal: np.ndarray, wavelet: str = 'db4', level: int = 4):
        """
        Applies discrete wavelet transform to an ECG signal and reconstructs the detail components.

        Args:
            ecg_signal (np.ndarray): Raw ECG signal.
            wavelet (str): Name of the wavelet to use (default 'db4').
            level (int): Decomposition level (default 4).

        Returns:
            tuple: (Reconstructed signal from detail coefficients, list of all wavelet coefficients)
        """
        coeffs = pywt.wavedec(ecg_signal, wavelet, level=level)
        details = [np.zeros_like(c) if i == 0 else c for i, c in enumerate(coeffs)]
        reconstructed = pywt.waverec(details, wavelet)
        return reconstructed, coeffs
