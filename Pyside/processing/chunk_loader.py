from PySide6.QtCore import QObject, Signal as QtSignal
import numpy as np
from typing import Dict, Any, Tuple, Optional
import hashlib


class ChunkLoader(QObject):
    """
    Qt-based chunk loader for physiological signals with caching.
    Includes both synchronous (static) and asynchronous (QtSignal) interfaces.
    Features LRU cache to avoid redundant data processing.
    """

    chunk_loaded = QtSignal(float, float, dict)  # start_sec, end_sec, {channel: chunk}

    def __init__(self, parent=None, cache_size: int = 50):
        super().__init__(parent)

        # Simple LRU cache for chunk data
        self._cache: Dict[str, Tuple[float, float, Dict[str, np.ndarray]]] = {}
        self._cache_order = []  # For LRU tracking
        self._max_cache_size = cache_size

    def _generate_cache_key(
        self,
        file_path: str,
        channel_names: list[str],
        start_sec: float,
        duration_sec: float,
    ) -> str:
        """Generate a unique cache key for the chunk request."""
        # Create a deterministic key based on request parameters
        key_data = (
            f"{file_path}|{sorted(channel_names)}|{start_sec:.2f}|{duration_sec:.2f}"
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_cache(
        self, cache_key: str
    ) -> Optional[Tuple[float, float, Dict[str, np.ndarray]]]:
        """Retrieve chunk from cache if available."""
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._cache[cache_key]
        return None

    def _store_in_cache(
        self,
        cache_key: str,
        start_sec: float,
        end_sec: float,
        data: Dict[str, np.ndarray],
    ):
        """Store chunk in cache with LRU eviction."""
        # Remove oldest entries if cache is full
        while len(self._cache) >= self._max_cache_size:
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]

        # Store new entry
        self._cache[cache_key] = (start_sec, end_sec, data.copy())
        self._cache_order.append(cache_key)

    def clear_cache(self):
        """Clear all cached chunks."""
        self._cache.clear()
        self._cache_order.clear()

    @staticmethod
    def get_chunk(
        data_manager,
        file_path: str,
        channel_names: list[str],
        start_sec: float,
        duration_sec: float,
        hr_params: dict = None,
    ):
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
        hr_params = hr_params or {}
        for ch in channel_names:
            # Use HR parameters for HR_GEN signals
            if ch.upper() == "HR_GEN":
                sig = data_manager.get_trace(file_path, ch, **hr_params)
            else:
                sig = data_manager.get_trace(file_path, ch)
            if sig is None:
                continue
            fs = sig.fs
            data = sig.data
            start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
            end_idx = int(
                max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data)))
            )
            chunk = data[start_idx:end_idx]
            results[ch] = chunk

        if len(results) == 1:
            return next(iter(results.values()))
        return results

    def request_chunk(
        self,
        data_manager,
        file_path: str,
        channel_names: list[str],
        start_sec: float,
        duration_sec: float,
        hr_params: dict = None,
    ):
        """
        Asynchronously extract the chunk(s) and emit result via QtSignal.
        Uses cache to avoid redundant processing.
        """
        # Check cache first
        cache_key = self._generate_cache_key(
            file_path, channel_names, start_sec, duration_sec
        )
        cached_result = self._get_from_cache(cache_key)

        if cached_result is not None:
            start_cached, end_cached, data_cached = cached_result
            self.chunk_loaded.emit(start_cached, end_cached, data_cached)
            return

        # Process chunk if not in cache
        result = {}
        hr_params = hr_params or {}
        for ch in channel_names:
            # Use HR parameters for HR_GEN signals
            if ch.upper() == "HR_GEN":
                sig = data_manager.get_trace(file_path, ch, **hr_params)
            else:
                sig = data_manager.get_trace(file_path, ch)
            if sig is None:
                continue
            fs = sig.fs
            data = sig.data
            start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
            end_idx = int(
                max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data)))
            )
            chunk = data[start_idx:end_idx]
            result[ch] = chunk

        # Store in cache
        end_sec = start_sec + duration_sec
        self._store_in_cache(cache_key, start_sec, end_sec, result)

        self.chunk_loaded.emit(start_sec, end_sec, result)
