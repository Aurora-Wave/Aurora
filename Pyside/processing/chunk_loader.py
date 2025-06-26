"""
chunk_loader.py
---------------
Efficient loading of chunks of physiological signals using the new SignalGroup structure.
"""

from PySide6.QtCore import QObject, Signal as QtSignal
import numpy as np
from data.adicht_loader import load_adicht


class ChunkLoader(QObject):
    """
    Chunk loader for physiological signals.
    Loads only the necessary data portion for efficient visualization.
    Compatible with the new SignalGroup structure.
    """

    chunk_loaded = QtSignal(int, int, dict)  # start_sec, end_sec, {channel_name: chunk}

    def __init__(self, file_path, channel_names, chunk_size, parent=None, signal_group=None):
        """
        Args:
            file_path (str): Path to .adicht file.
            channel_names (list[str]): Names of channels to extract.
            chunk_size (int): Chunk duration in seconds.
            parent: Optional parent object.
            signal_group (SignalGroup): Preloaded signals (optional).
        """
        super().__init__(parent)
        self.file_path = file_path
        self.channel_names = channel_names
        self.chunk_size = chunk_size
        self.signal_group = signal_group
        self._cache = {}  # (channel_name, start, end): data

    def set_signal_group(self, signal_group):
        """Update the SignalGroup object used for chunking."""
        self.signal_group = signal_group

    def load_signal_group(self):
        """Load the signal group from disk if not yet available."""
        if self.signal_group is None:
            self.signal_group = load_adicht(self.file_path)

    def request_chunk(self, start_sec, end_sec):
        """Emit a chunk of data between start_sec and end_sec for all requested channels."""
        self.load_signal_group()
        result = {}

        for name in self.channel_names:
            signal = self.signal_group.get(name)
            if signal is not None:
                fs = signal.fs
                full_data = signal.get_full_signal()
                start_idx = int(start_sec * fs)
                end_idx = int(end_sec * fs)
                chunk = full_data[start_idx:end_idx]
                result[name] = chunk.astype(np.float32)

        self.chunk_loaded.emit(start_sec, end_sec, result)
