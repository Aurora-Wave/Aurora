"""
chunk_loader.py
--------------
Efficient loading of chunks of physiological signals from .adicht files.
Loads only the necessary portion for efficient visualization.
"""

from PySide6.QtCore import QObject, Signal
import numpy as np
from data.adicht_loader import get_data_record_from_path


class ChunkLoader(QObject):
    """
    Chunk loader for physiological signals.
    Loads only the necessary data portion for efficient visualization.
    Can reuse an already loaded data_record object for maximum efficiency.
    """

    chunk_loaded = Signal(int, int, dict)  # start_idx, end_idx, {channel_name: data}

    def __init__(
        self, file_path, channel_names, chunk_size, parent=None, data_record=None
    ):
        """
        Args:
            file_path (str): Absolute path of the .adicht file.
            channel_names (list): List of signal names to load.
            chunk_size (int): Chunk duration in seconds.
            parent: QObject parent (optional).
            data_record: Already loaded data object (optional).
        """
        super().__init__(parent)
        self.file_path = file_path
        self.channel_names = channel_names
        self.chunk_size = chunk_size
        self.data_record = data_record  # Reuse provided data_record if given
        self._cache = {}  # (channel_name, start, end): data

    def set_data_record(self, data_record):
        """Updates the data_record object to reuse the one already loaded in the app."""
        self.data_record = data_record

    def load_data_record(self):
        if self.data_record is None:
            self.data_record = get_data_record_from_path(self.file_path)

    def request_chunk(self, start_sec, end_sec):
        if self.data_record is None:
            self.load_data_record()
        result = {}
        for channel_name in self.channel_names:
            for sig in self.data_record.Signals:
                if channel_name.upper() in sig.Name.upper():
                    fs = getattr(sig, "TSR", 1000)
                    full_signal = np.concatenate([sig.BB, sig.ProData, sig.AB])
                    start_idx = int(start_sec * fs)
                    end_idx = int(end_sec * fs)
                    chunk = full_signal[start_idx:end_idx]
                    result[channel_name] = chunk.astype(np.float32)
        self.chunk_loaded.emit(start_sec, end_sec, result)
