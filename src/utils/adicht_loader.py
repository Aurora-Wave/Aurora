import numpy as np
import pandas as pd
import adi

def load_channel_from_path(path, label):
    """
    Loads a specific signal channel by label from a .adicht file on disk.

    Parameters:
        path (str): Absolute path to the .adicht file.
        label (str): Channel label to extract (e.g. 'ECG', 'FBP').

    Returns:
        pd.DataFrame: DataFrame with 'Time' and <label> columns.
    """
    f = adi.read_file(path)

    for ch in f.channels:
            if ch.name.strip().lower() == label.strip().lower():
                last_record_id = len(ch.records) - 1
                data = ch.get_data(last_record_id)

                sampling_rate = ch.fs[last_record_id]
                time = np.arange(len(data)) / sampling_rate
                return pd.DataFrame({'Time': time, label: data})

    raise ValueError(f"Channel '{label}' not found in the file.")
