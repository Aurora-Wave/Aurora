
from PySide6.QtCore import QObject, Signal as QtSignal
import numpy as np


class ChunkLoader(QObject):
    """
    Loads chunks of data lazily from file via DataManager.
    Emits a signal when chunk is ready.
    """

    chunk_loaded = QtSignal(int, int, dict)  # start, end, {channel: chunk}

    def __init__(self, manager, file_path, channel_names, chunk_size=30, parent=None):
        """
        Args:
            manager (DataManager): Instance of the DataManager.
            file_path (str): Path to the loaded file.
            channel_names (list[str]): List of channels to load.
            chunk_size (int): Chunk duration in seconds.
        """
        super().__init__(parent)
        self.manager = manager
        self.file_path = file_path
        self.channel_names = channel_names
        self.chunk_size = chunk_size

    def request_chunk(self, start_time, end_time):
        """
        Request a chunk of data for all channels.

        Args:
            start_time (float): Start time in seconds.
            end_time (float): End time in seconds.
        """
        result = {}
        for ch in self.channel_names:
            try:
                chunk = self.manager.get_chunk(
                    self.file_path,
                    ch,
                    start_time,
                    end_time - start_time
                )
                result[ch] = chunk
            except Exception as e:
                print(f"⚠️ Error loading chunk for channel '{ch}': {e}")
                result[ch] = np.array([])

        self.chunk_loaded.emit(int(start_time), int(end_time), result)
