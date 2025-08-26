from PySide6.QtCore import QObject, Signal as QtSignal
import numpy as np

class ChunkLoader(QObject):
    """
    Qt-based chunk loader for physiological signals.
    Includes both synchronous (static) and asynchronous (QtSignal) interfaces.
    """

    chunk_loaded = QtSignal(float, float, dict)  # start_sec, end_sec, {channel: chunk}

    def __init__(self, parent=None):
        super().__init__(parent)

    @staticmethod
    def get_chunk(data_manager, file_path: str, channel_names: list[str],
                  start_sec: float, duration_sec: float):
        """
        Synchronously extract the chunk(s) of data requested from DataManager.
        Returns the chunk(s) immediately (blocking call).

        Args:
            data_manager: DataManager instance.
            file_path (str): Path to the file loaded in DataManager.
            channel_names (list[str]): Names of channels to extract.
            start_sec (float): Start time (seconds).
            duration_sec (float): Duration (seconds).

        Returns:
            If only one channel: np.ndarray.
            If multiple: dict {channel: np.ndarray}.
        """
        results = {}
        for ch in channel_names:
            sig = data_manager.get_trace(file_path, ch)
            if sig is None:
                continue
            fs = sig.fs
            data = sig.data
            start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
            end_idx = int(max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data))))
            chunk = data[start_idx:end_idx]
            results[ch] = chunk

        if len(results) == 1:
            return next(iter(results.values()))
        return results

    def request_chunk(self, data_manager, file_path: str, channel_names: list[str],
                      start_sec: float, duration_sec: float):
        """
        Asynchronously extract the chunk(s) and emit result via QtSignal.
        """
        result = {}
        for ch in channel_names:
            sig = data_manager.get_trace(file_path, ch)
            if sig is None:
                continue
            fs = sig.fs
            data = sig.data
            start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
            end_idx = int(max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data))))
            chunk = data[start_idx:end_idx]
            result[ch] = chunk

        self.chunk_loaded.emit(start_sec, start_sec + duration_sec, result)
