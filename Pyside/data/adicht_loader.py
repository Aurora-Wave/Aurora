"""
adicht_loader.py
----------------
Carga y parseo de archivos .adicht (LabChart) a objetos de señales fisiológicas.
Incluye clases de datos y utilidades para manejo de señales y comentarios.
"""

import numpy as np
import adi
import scipy.signal

# --- CACHE GLOBAL EN MEMORIA (solo para la sesión actual del proceso) ---
_df_cache = {}


class Signal:
    """
    Representa una señal individual dentro de un archivo .adicht.
    Atributos principales: nombre, unidades, datos, frecuencia de muestreo, etc.
    """

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


class DataRecord:
    """
    Representa el conjunto de señales y metadatos de un archivo .adicht.
    """

    def __init__(self):
        self.Signals = []
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
    Representa un comentario EMS asociado a un tiempo específico, con todos los campos relevantes de LabChart.
    """

    def __init__(self, text, tick_position, channel_, id_, tick_dt, time):
        self.text = text  # Texto del comentario
        self.tick_position = tick_position  # Posición del tick (índice)
        self.channel_ = channel_  # Canal asociado
        self.id = id_  # ID único o índice
        self.tick_dt = tick_dt  # Duración de cada tick (s)
        self.time = time  # Tiempo absoluto en segundos

    def __repr__(self):
        return f"EMSComment(text={self.text}, tick_position={self.tick_position}, channel_={self.channel_}, id={self.id}, tick_dt={self.tick_dt}, time={self.time})"


def detect_r_peaks(ecg_signal, fs):
    """
    Detecta picos R en una señal ECG usando umbral absoluto.
    Args:
        ecg_signal (np.ndarray): Señal ECG cruda.
        fs (float): Frecuencia de muestreo.
    Returns:
        np.ndarray: Índices de los picos detectados.
    """
    ecg_abs = np.abs(ecg_signal - np.mean(ecg_signal))
    threshold = np.percentile(ecg_abs, 95)
    peaks, _ = scipy.signal.find_peaks(
        ecg_abs, height=threshold, distance=int(0.25 * fs)
    )
    return peaks


def load_labchart_adicht_extended(file_path, gap_length=3):
    """
    Carga un archivo .adicht y lo parsea a objetos DataRecord y Signal.
    Args:
        file_path (str): Ruta del archivo .adicht.
        gap_length (int): Longitud de huecos entre registros (en segundos).
    Returns:
        DataRecord: Objeto con todas las señales y metadatos.
    """
    file_data = adi.read_file(file_path)
    data_record = DataRecord()
    data_record.ProFileName = file_path.split("\\")[-1]
    data_record.FileName = data_record.ProFileName.split(".")[0]
    total_records = file_data.n_records
    assumed_tsr = None
    for i, channel in enumerate(file_data.channels):
        signal = Signal()
        signal.Name = channel.name
        signal.Units = channel.units
        signal.TSRf = channel.fs[0]
        signal.TSR = int(round(signal.TSRf))
        signal.EU = signal.Units
        assumed_tsr = assumed_tsr or signal.TSR
        full_data = []
        for record_id in range(1, total_records + 1):
            data = channel.get_data(record_id)
            if data is not None:
                full_data.append(data)
                if record_id < total_records:
                    full_data.append(np.zeros(gap_length * signal.TSR))
        full_data = np.concatenate(full_data)
        signal.BB = full_data[: signal.TSR]
        signal.AB = full_data[-signal.TSR :]
        signal.ProData = full_data[signal.TSR : -signal.TSR]
        n_samples = len(signal.ProData)
        signal.TimeSec = np.linspace(1 / signal.TSR, n_samples / signal.TSR, n_samples)
        data_record.Signals.append(signal)
    for i, sig in enumerate(data_record.Signals):
        if "ECG" in sig.Name.upper():
            data_record.SignalIndex = i
            data_record.ECGSI = i
            break
    else:
        data_record.SignalIndex = 0
        data_record.ECGSI = 0

    ecg_signal = data_record.Signals[data_record.ECGSI]
    ecg_full = np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])
    peaks = detect_r_peaks(ecg_full, ecg_signal.TSR)
    data_record.FMxI = peaks
    data_record.Signals[data_record.ECGSI].FMxI = peaks
    rr_intervals = np.diff(peaks)
    valid_rr = rr_intervals[(peaks[1:] > 200) & (peaks[1:] < len(ecg_full) - 200)]
    data_record.CL = valid_rr
    data_record.CLI = peaks[1 : len(valid_rr) + 1]
    data_record.CLT = data_record.CLI / ecg_signal.TSR
    data_record.EBL = ecg_signal.TSR
    # Asignar comentarios por señal (canal)
    for ch_idx, ch in enumerate(file_data.channels):
        signal_comments = []
        for rec_idx, rec in enumerate(ch.records):
            if hasattr(rec, "comments") and rec.comments:
                for idx, c in enumerate(rec.comments):
                    tick_dt = getattr(
                        c, "tick_dt", 1.0 / ch.fs[rec_idx] if hasattr(ch, "fs") else 1.0
                    )
                    tick_pos = getattr(c, "tick_position", 0)
                    comment_str = getattr(c, "text", "")
                    # Nuevo: calcular tiempo absoluto
                    time = (
                        tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                    )
                    # Nuevo: crear EMSComment con todos los campos relevantes
                    signal_comments.append(
                        EMSComment(
                            text=comment_str,
                            tick_position=tick_pos,
                            channel_=ch.name,
                            id_=idx + 1,
                            tick_dt=tick_dt,
                            time=time,
                        )
                    )
        if ch_idx < len(data_record.Signals):
            data_record.Signals[ch_idx].MarkerData = signal_comments
    return data_record


def get_data_record_from_path(path, gap_length=3):
    """
    Devuelve un objeto DataRecord (estructura orientada a objetos) a partir de un archivo .adicht.
    Usa caché en memoria para evitar leer el archivo repetidamente.
    """
    global _df_cache
    cache_key = f"datarecord::{path}"
    if cache_key in _df_cache:
        return _df_cache[cache_key]
    data_record = load_labchart_adicht_extended(path, gap_length=gap_length)
    _df_cache[cache_key] = data_record
    return data_record


# Ejemplo de uso en una página/callback:
# from data.adicht_loader import get_data_record_from_path
# data_record = get_data_record_from_path(path)
# ecg_signal = data_record.Signals[data_record.ECGSI]
# ecg_full = np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])
# r_peaks = data_record.FMxI
# comentarios = ecg_signal.MarkerData

# Si quieres exponer la API orientada a objetos en toda la app, puedes importar get_data_record_from_path en las páginas donde lo necesites.
