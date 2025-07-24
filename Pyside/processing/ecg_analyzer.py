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
                        **kwargs) -> np.ndarray:
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
        method = kwargs.get("method","wavelet")
        wv = kwargs.get("wavelet","haar")
        lv = kwargs.get("level",4)
        dist = kwargs.get("min_dist",0.5)

        #if method == "wavelet":
        #    # 1) Determine max possible SWT level given the signal length
        #    max_lvl = pywt.swt_max_level(len(ecg_signal))
        #    lvl = min(lv, max_lvl) if max_lvl >= 1 else 1
        #    # 2) Perform undecimated SWT
        #    coeffs = pywt.swt(ecg_signal, wv, level=lvl)
        #    # 3) Reconstruct the signal with ISWT
        #    reconstructed = pywt.iswt(coeffs, wv)
        #    # 4) Convert minimum RR interval from seconds to samples
        #    min_dist = int(dist * fs)
        #    # 5) Detect peaks with the given minimum distance constraint
        #    peaks, _ = find_peaks(reconstructed, distance=min_dist)
        if method == "wavelet":
        #    # 1) Determine max possible SWT level given the signal length
        #    max_lvl = pywt.swt_max_level(len(ecg_signal))
        #    lvl = min(lv, max_lvl) if max_lvl >= 1 else 1
        #    # 2) Perform undecimated SWT
            coeffs = pywt.wavedec(ecg_signal, wv, level=5)
        #    # 3) Reconstruct the signal with ISWT
            reconstructed = pywt.waverec(coeffs,wv)
        #    # 4) Convert minimum RR interval from seconds to samples
            min_dist = int(dist * fs)
        #    # 5) Detect peaks with the given minimum distance constraint
            peaks, _ = find_peaks(reconstructed, distance=min_dist)
        
        
        if method == "pan_tonkins":
            raise NotImplementedError
        return peaks
