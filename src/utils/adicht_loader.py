import numpy as np
import pandas as pd
import adi
import scipy.signal

# --- CACHE GLOBAL EN MEMORIA (solo para la sesión actual del proceso) ---
_df_cache = {}


def load_channel_from_path(path, label):
    """
    Devuelve un DataFrame con la columna 'Time' y la columna del canal solicitado, usando el DataFrame global de todos los canales.
    Si el canal no existe, lanza un ValueError.
    """
    df = load_all_channels_from_path(path)
    # Buscar el canal ignorando mayúsculas/minúsculas y espacios
    col_map = {c.strip().lower(): c for c in df.columns}
    label_key = label.strip().lower()
    if label_key not in col_map:
        raise ValueError(f"Channel '{label}' not found in the file.")
    canal_col = col_map[label_key]
    # Si existe columna 'Time', usarla
    if "Time" in df.columns:
        return df[["Time", canal_col]].copy()
    # Si no existe 'Time', solo el canal
    return df[[canal_col]].copy()


def load_all_channels_from_path(path):
    """
    Carga todos los canales de un archivo .adicht y los combina en un único DataFrame.
    Usa caché en memoria para evitar leer el archivo repetidamente.
    """
    global _df_cache
    if path in _df_cache:
        return _df_cache[path]
    f = adi.read_file(path)
    channel_names = [ch.name.strip() for ch in f.channels][1:]
    channel_data = [ch.get_data(2) for ch in f.channels][1:]
    if len(f.channels) > 1:
        fs = f.channels[1].fs[2]
        max_len = max(len(data) for data in channel_data)
        channel_data_padded = [
            np.pad(data, (0, max_len - len(data)), constant_values=np.nan)
            for data in channel_data
        ]
        time = np.arange(max_len) / fs
        df_channels = pd.DataFrame(
            {name: data for name, data in zip(channel_names, channel_data_padded)}
        )
        df_channels["Time"] = time
        cols = ["Time"] + [c for c in df_channels.columns if c != "Time"]
        df_channels = df_channels[cols]
        _df_cache[path] = df_channels
        return df_channels
    df = pd.DataFrame({name: data for name, data in zip(channel_names, channel_data)})
    _df_cache[path] = df
    return df


class TraceSignal:
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
    def __init__(self, seconds, comment, number):
        self.DateTime = ""
        self.Seconds = seconds
        self.Comment = comment
        self.CommentNum = number
        self.CommentBoxText = f"{comment:<50}{seconds:.2f}"


def detect_r_peaks(ecg_signal, fs):
    ecg_abs = np.abs(ecg_signal - np.mean(ecg_signal))
    threshold = np.percentile(ecg_abs, 95)
    peaks, _ = scipy.signal.find_peaks(
        ecg_abs, height=threshold, distance=int(0.25 * fs)
    )
    return peaks


def load_labchart_adicht_extended(file_path, gap_length=3):
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
        signal.TSRf = channel.fs[1]
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
            if hasattr(rec, "comments") and rec.comments:
                for idx, c in enumerate(rec.comments):
                    tick_dt = getattr(
                        c, "tick_dt", 1.0 / ch.fs[rec_idx] if hasattr(ch, "fs") else 1.0
                    )
                    tick_pos = getattr(c, "tick_position", 0)
                    seconds = (
                        tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                    )
                    comment_str = getattr(c, "str", "")
                    signal_comments.append(EMSComment(seconds, comment_str, idx + 1))
        if ch_idx < len(trace.Signal):
            trace.Signal[ch_idx].MarkerData = signal_comments
    return trace


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


# Ejemplo de uso en una página/callback:
# from utils.adicht_loader import get_trace_from_path
# trace = get_trace_from_path(path)
# ecg_signal = trace.Signal[trace.ECGSI]
# ecg_full = np.concatenate([ecg_signal.BB, ecg_signal.ProData, ecg_signal.AB])
# r_peaks = trace.FMxI
# comentarios = ecg_signal.MarkerData

# Si quieres exponer la API orientada a objetos en toda la app, puedes importar get_trace_from_path en las páginas donde lo necesites.
