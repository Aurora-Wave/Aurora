# utils/trace_api.py
from utils.adicht_loader import get_trace_from_path
import numpy as np


def get_ecg_full(trace):
    """Devuelve la señal ECG completa (BB + ProData + AB) del objeto Trace."""
    ecg_signal = trace.Signal[trace.ECGSI]
    return np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])


def get_r_peaks(trace):
    """Devuelve los índices de los picos R detectados en la señal ECG."""
    return trace.FMxI


def get_ecg_comments(trace):
    """Devuelve los comentarios asociados a la señal ECG."""
    ecg_signal = trace.Signal[trace.ECGSI]
    return ecg_signal.MarkerData
