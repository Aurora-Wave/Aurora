import numpy as np
import pandas as pd
import adi

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
