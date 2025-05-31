"""
ecg_analyzer.py
---------------
Utilidades para análisis de señales ECG: detección de RR peaks y transformada wavelet.
"""

import numpy as np
from scipy.signal import find_peaks

class ECGAnalyzer:
    """
    Clase utilitaria para análisis de señales ECG.
    Provee métodos para detección de RR peaks y transformada wavelet.
    """
    @staticmethod
    def detect_rr_peaks(ecg_signal, fs, distance_sec=0.3, height=None):
        """
        Detecta los picos R (RR peaks) en una señal ECG.
        Args:
            ecg_signal (np.ndarray): Señal ECG cruda.
            fs (float): Frecuencia de muestreo en Hz.
            distance_sec (float): Distancia mínima entre picos en segundos (default 0.3s).
            height (float|None): Altura mínima del pico (opcional).
        Returns:
            np.ndarray: Índices de los picos detectados.
        """
        distance = int(distance_sec * fs)
        peaks, _ = find_peaks(ecg_signal, distance=distance, height=height)
        return peaks

    @staticmethod
    def wavelet_transform(ecg_signal, wavelet='db4', level=4):
        """
        Aplica la transformada wavelet discreta a la señal ECG.
        Args:
            ecg_signal (np.ndarray): Señal ECG cruda.
            wavelet (str): Nombre del wavelet a usar (default 'db4').
            level (int): Nivel de descomposición (default 4).
        Returns:
            tuple: (reconstrucción usando solo los detalles, lista de coeficientes wavelet)
        """
        import pywt
        coeffs = pywt.wavedec(ecg_signal, wavelet, level=level)
        # Reconstruir la señal a partir de los detalles (ajustable según visualización deseada)
        details = [np.zeros_like(c) if i == 0 else c for i, c in enumerate(coeffs)]
        reconstructed = pywt.waverec(details, wavelet)
        return reconstructed, coeffs
