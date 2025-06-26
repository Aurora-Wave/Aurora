"""
adicht_loader.py
----------------
Loader for .adicht files using adi.read_file.
Parses LabChart signals and comments into Signal and SignalGroup objects.
"""

import numpy as np
import adi

from core.signal import Signal, SignalGroup
from core.comments import EMSComment
from processing.ecg_analyzer import ECGAnalyzer

# Global cache to avoid redundant loading
_adicht_cache = {}

<<<<<<< Updated upstream
class TraceSignal:
    """
    Representa una señal individual dentro de un archivo .adicht.
    Atributos principales: nombre, unidades, datos, frecuencia de muestreo, etc.
=======
def load_adicht(path, preload=True, gap_length=3):
>>>>>>> Stashed changes
    """
    Load a .adicht LabChart file and return a SignalGroup object.

<<<<<<< Updated upstream
    def __init__(self):
        self.Name = ""
        self.Animal = "Human"
        self.EBL = None
        self.Units = ""
        self.RawFileType = "Labchart"
        self.PreProcess = ""
        self.RawDataRow = 1
        self.Marker = []
        self.MarkerData = []
        self.BB = []
        self.AB = []
        self.ProData = []
        self.TimeSec = []
        self.EU = ""
        self.TSRf = 0
        self.TSR = 0
        self.SRD = 1
        self.SX = 0
        self.EX = 0
        self.Resampled = 0
        self.FMxI = []
        self.NFEE = []
        self.FEE = []
        self.TimeShift = 0


class Trace:
    """
    Representa el conjunto de señales y metadatos de un archivo .adicht.
    """

    def __init__(self):
        self.Signal = []
        self.ProFileName = ""
        self.FileName = ""
        self.SignalIndex = 0
        self.EBL = 0
        self.FMxI = []
        self.FEE = []
        self.NFEE = []
        self.EMS = []
        self.ECGSI = 0


class EMSComment:
    """
    Representa un comentario EMS asociado a un tiempo específico.
    """

    def __init__(self, seconds, comment, number):
        self.DateTime = ""
        self.Seconds = seconds
        self.Comment = comment
        self.CommentNum = number
        self.CommentBoxText = f"{comment:<50}{seconds:.2f}"


def detect_r_peaks(ecg_signal, fs):
    """
    Detecta picos R en una señal ECG usando umbral absoluto.
=======
>>>>>>> Stashed changes
    Args:
        path (str): Path to the .adicht file.
        preload (bool): Unused.
        gap_length (int): Seconds of zero-padding between records.

<<<<<<< Updated upstream

def load_labchart_adicht_extended(file_path, gap_length=3):
    """
    Carga un archivo .adicht y lo parsea a objetos Trace y TraceSignal.
    Args:
        file_path (str): Ruta del archivo .adicht.
        gap_length (int): Longitud de huecos entre registros (en segundos).
    Returns:
        Trace: Objeto con todas las señales y metadatos.
    """
    file_data = adi.read_file(file_path)
    trace = Trace()
    trace.ProFileName = file_path.split("\\")[-1]
    trace.FileName = trace.ProFileName.split(".")[0]
    total_records = file_data.n_records
    assumed_tsr = None
    for i, channel in enumerate(file_data.channels):
        signal = TraceSignal()
        signal.Name = channel.name
        signal.Units = channel.units
        signal.TSRf = channel.fs[0]
        signal.TSR = int(round(signal.TSRf))
        signal.EU = signal.Units
        assumed_tsr = assumed_tsr or signal.TSR
=======
    Returns:
        SignalGroup: Group of Signal objects with metadata and comments.
    """
    global _adicht_cache
    if path in _adicht_cache:
        return _adicht_cache[path]

    file_data = adi.read_file(path)
    signals = []
    total_records = file_data.n_records
    ecg_signal = None

    for channel in file_data.channels:
        name = channel.name
        units = channel.units
        fs = channel.fs[0]
        fs_int = int(round(fs))

        # Concatenate records with gap
>>>>>>> Stashed changes
        full_data = []
        for record_id in range(1, total_records + 1):
            data = channel.get_data(record_id)
            if data is not None:
                full_data.append(data)
                if record_id < total_records:
                    full_data.append(np.zeros(gap_length * fs_int))
        full_data = np.concatenate(full_data)
<<<<<<< Updated upstream
        signal.BB = full_data[: signal.TSR]
        signal.AB = full_data[-signal.TSR :]
        signal.ProData = full_data[signal.TSR : -signal.TSR]
        n_samples = len(signal.ProData)
        signal.TimeSec = np.linspace(1 / signal.TSR, n_samples / signal.TSR, n_samples)
        trace.Signal.append(signal)
    for i, sig in enumerate(trace.Signal):
        if "ECG" in sig.Name.upper():
            trace.SignalIndex = i
            trace.ECGSI = i
            break
    else:
        trace.SignalIndex = 0
        trace.ECGSI = 0

    ecg_signal = trace.Signal[trace.ECGSI]
    ecg_full = np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])
    peaks = detect_r_peaks(ecg_full, ecg_signal.TSR)
    trace.FMxI = peaks
    trace.Signal[trace.ECGSI].FMxI = peaks
    rr_intervals = np.diff(peaks)
    valid_rr = rr_intervals[(peaks[1:] > 200) & (peaks[1:] < len(ecg_full) - 200)]
    trace.CL = valid_rr
    trace.CLI = peaks[1 : len(valid_rr) + 1]
    trace.CLT = trace.CLI / ecg_signal.TSR
    trace.EBL = ecg_signal.TSR
    # Asignar comentarios por señal (canal)
    for ch_idx, ch in enumerate(file_data.channels):
        signal_comments = []
        for rec_idx, rec in enumerate(ch.records):
=======

        # Split into BB, ProData, AB
        bb = full_data[:fs_int]
        ab = full_data[-fs_int:]
        pro_data = full_data[fs_int:-fs_int]
        time = np.linspace(1 / fs, len(pro_data) / fs, len(pro_data))

        # Create Signal object
        sig = Signal(name=name, data=pro_data, time=time, units=units, fs=fs)
        sig.BB = bb
        sig.AB = ab

        # Load EMS comments
        comments = []
        for rec_idx, rec in enumerate(channel.records):
>>>>>>> Stashed changes
            if hasattr(rec, "comments") and rec.comments:
                for idx, c in enumerate(rec.comments):
                    tick_dt = getattr(c, "tick_dt", 1.0 / channel.fs[rec_idx])
                    tick_pos = getattr(c, "tick_position", 0)
<<<<<<< Updated upstream
                    seconds = (
                        tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                    )
                    comment_str = getattr(c, "str", "")
                    signal_comments.append(EMSComment(seconds, comment_str, idx + 1))
        if ch_idx < len(trace.Signal):
            trace.Signal[ch_idx].MarkerData = signal_comments
    return trace
=======
                    text = getattr(c, "text", "")
                    time_sec = tick_pos * tick_dt + rec_idx * channel.n_samples[rec_idx] * tick_dt
                    comments.append(EMSComment(
                        text=text,
                        tick_position=tick_pos,
                        channel=name,
                        comment_id=idx + 1,
                        tick_dt=tick_dt,
                        time_sec=time_sec,
                        user_defined=False
                    ))
        sig.MarkerData = comments
>>>>>>> Stashed changes

        # If it's an ECG, process R-peaks
        if "ECG" in name.upper():
            ecg_full = np.concatenate([bb, pro_data, ab])
            peaks = ECGAnalyzer.detect_rr_peaks(ecg_full, fs_int)
            sig.FMxI = peaks
            sig.CL = np.diff(peaks)
            sig.CLI = peaks[1 : len(sig.CL) + 1]
            sig.CLT = sig.CLI / fs
            ecg_signal = sig  # Save for HR_GEN

<<<<<<< Updated upstream
def get_trace_from_path(path, gap_length=3):
    """
    Devuelve un objeto Trace (estructura orientada a objetos) a partir de un archivo .adicht.
    Usa caché en memoria para evitar leer el archivo repetidamente.
    """
    global _df_cache
    cache_key = f"trace::{path}"
    if cache_key in _df_cache:
        return _df_cache[cache_key]
    trace = load_labchart_adicht_extended(path, gap_length=gap_length)
    _df_cache[cache_key] = trace
    return trace
=======
        signals.append(sig)
>>>>>>> Stashed changes

    # Create HR_GEN if ECG present
    if ecg_signal and ecg_signal.FMxI is not None and len(ecg_signal.FMxI) >= 3:
        peaks = ecg_signal.FMxI
        hr_data = []
        hr_time = []
        for i in range(1, len(peaks) - 1):
            idx_start = peaks[i]
            idx_end = peaks[i + 1]
            t_start = idx_start / ecg_signal.fs
            t_end = idx_end / ecg_signal.fs
            rr = t_end - t_start
            hr = 60 / rr if rr > 0 else 0
            hr_data.extend([hr, hr])
            hr_time.extend([t_start, t_end])
        hr_signal = Signal(name="HR_GEN", data=hr_data, time=hr_time, units="bpm", fs=1.0)
        signals.append(hr_signal)

<<<<<<< Updated upstream
# Ejemplo de uso en una página/callback:
# from utils.adicht_loader import get_trace_from_path
# trace = get_trace_from_path(path)
# ecg_signal = trace.Signal[trace.ECGSI]
# ecg_full = np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])
# r_peaks = trace.FMxI
# comentarios = ecg_signal.MarkerData

# Si quieres exponer la API orientada a objetos en toda la app, puedes importar get_trace_from_path en las páginas donde lo necesites.
=======
    signal_group = SignalGroup(signals)
    _adicht_cache[path] = signal_group
    return signal_group
>>>>>>> Stashed changes
