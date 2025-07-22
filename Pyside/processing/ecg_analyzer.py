# processing/ecg_analyzer.py

import numpy as np
import pywt
from scipy.signal import find_peaks

class ECGAnalyzer:
    """
    Utility class for ECG processing:
    performs SWT→ISWT reconstruction and R-peak detection in one call.
    """
    @staticmethod
    def detect_rr_peaks(ecg_signal: np.ndarray,
                        fs: float,
                        wavelet: str = 'haar',
                        swt_level: int = 4,
                        min_rr_sec: float = 0.5
                       ) -> np.ndarray:
        """
        1) Adjusts decomposition level to the maximum allowed by the signal length.
        2) Computes undecimated SWT of ecg_signal.
        3) Reconstructs the signal with ISWT.
        4) Detects R-peaks in the reconstructed signal using a minimum time separation.

        Args:
            ecg_signal:   Raw ECG signal, 1D numpy array.
            fs:           Sampling frequency (Hz).
            wavelet:      Wavelet name (e.g. 'db3', 'haar').
            swt_level:    SWT decomposition level.
            min_rr_sec:   Minimum allowed time between R-peaks in seconds.

        Returns:
            peaks: Array of sample indices where R-peaks are detected.
        """
        # 1) Determine max possible SWT level given the signal length
        max_lvl = pywt.swt_max_level(len(ecg_signal))
        lvl = min(swt_level, max_lvl) if max_lvl >= 1 else 1

        # 2) Perform undecimated SWT
        coeffs = pywt.swt(ecg_signal, wavelet, level=lvl)

        # 3) Reconstruct the signal with ISWT
        reconstructed = pywt.iswt(coeffs, wavelet)

        # 4) Convert minimum RR interval from seconds to samples
        min_dist = int(min_rr_sec * fs)

        # 5) Detect peaks with the given minimum distance constraint
        peaks, _ = find_peaks(reconstructed, distance=min_dist)

        return peaks
