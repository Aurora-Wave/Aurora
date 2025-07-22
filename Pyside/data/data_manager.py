import os
import numpy as np
from collections import defaultdict, deque

from .aditch_loader import AditchLoader
# from .edf_loader import EDFLoader  # for future formats
from core.signal import Signal
from processing.ecg_analyzer import ECGAnalyzer

MAX_CHUNKS_PER_CHANNEL = 5
MAX_HR_CACHE = 5  # maximum distinct HR_gen configurations to keep

class DataManager:
    def __init__(self):
        # English comment: initialize file registry and loader mappings
        self._files = {}
        self._loader_registry = {
            ".adicht": AditchLoader,
            # ".edf": EDFLoader,
        }

    def load_file(self, path: str):
        """Load a file if not already in manager."""
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._loader_registry:
            raise ValueError(f"Unsupported file type: {ext}")
        if path in self._files:
            return

        loader = self._loader_registry[ext]()
        loader.load(path)

        # store loader, caches, metadata, comments, and HR cache tracker
        self._files[path] = {
            "loader": loader,
            "chunk_cache": defaultdict(list),
            "signal_cache": {},
            "metadata": loader.get_metadata(),
            "comments": loader.get_all_comments(),
            "hr_cache_keys": deque()
        }

    def get_chunk(self, path: str, channel: str, start: float, duration: float):
        """Retrieve a segment of the signal, caching recent requests."""
        entry = self._files[path]
        cache = entry["chunk_cache"][channel]

        # return cached chunk if available
        for s, d, c in cache:
            if s == start and d == duration:
                return c

        # load new chunk and maintain cache size
        chunk = entry["loader"].get_chunk(channel, start, duration)
        cache.append((start, duration, chunk))
        if len(cache) > MAX_CHUNKS_PER_CHANNEL:
            cache.pop(0)
        return chunk

    def get_trace(
        self,
        path: str,
        channel: str,
        *,
        wavelet: str = "haar",
        swt_level: int = 4,
        min_rr_sec: float = 0.5
    ):
        """
        Retrieve full trace or lazily compute HR_gen with parameterized caching.
        Maintains up to MAX_HR_CACHE distinct HR_gen configurations.
        Updates metadata to include HR_gen when generated.
        """
        entry = self._files[path]

        if channel == "HR_gen":
            # build cache key including parameters
            key = f"HR_gen|{wavelet}|{swt_level}|{min_rr_sec}"
            # compute and cache if missing
            if key not in entry["signal_cache"]:
                # enforce cache size
                keys_q = entry["hr_cache_keys"]
                if len(keys_q) >= MAX_HR_CACHE:
                    old_key = keys_q.popleft()
                    entry["signal_cache"].pop(old_key, None)

                # fetch full ECG signal recursively
                ecg_signal = self.get_trace(path, "ECG")
                # assemble full data including buffers
                ecg_full = (
                    np.concatenate([ecg_signal.BB, ecg_signal._data, ecg_signal.AB])
                    if ecg_signal.BB.size or ecg_signal.AB.size
                    else ecg_signal._data
                )
                # detect R-peaks as sample indices
                peaks = ECGAnalyzer.detect_rr_peaks(
                    ecg_full,
                    ecg_signal.fs,
                    wavelet,
                    swt_level,
                    min_rr_sec
                )
                # build HR time series by filling constant HR between peaks
                hr_data = []
                hr_time = []
                for i in range(len(peaks) - 1):
                    idx_start = peaks[i]
                    idx_end = peaks[i + 1]
                    t_start = idx_start / ecg_signal.fs
                    t_end = idx_end   / ecg_signal.fs
                    rr = t_end - t_start
                    hr = 60.0 / rr if rr > 0 else 0.0
                    count = idx_end - idx_start
                    times = np.arange(idx_start, idx_end) / ecg_signal.fs
                    hr_data.extend([hr] * count)
                    hr_time.extend(times.tolist())
                hr_data = np.array(hr_data)
                hr_time = np.array(hr_time)
                # create and cache HR signal object
                hr_sig = Signal("HR_gen", hr_data, hr_time, units="bpm", fs=1.0)
                entry["signal_cache"][key] = hr_sig
                keys_q.append(key)

                # update metadata to include HR_gen channel
                md = entry["metadata"]
                if "channels" in md and "HR_gen" not in md["channels"]:
                    md["channels"].append("HR_gen")

            return entry["signal_cache"][key]

        # for other channels, return cached or load full trace
        if channel in entry["signal_cache"]:
            return entry["signal_cache"][channel]

        trace = entry["loader"].get_full_trace(channel)
        entry["signal_cache"][channel] = trace
        return trace

    def get_comments(self, path: str):
        """Get all annotations/comments for a file."""
        return self._files[path]["comments"]

    def get_metadata(self, path: str):
        """Get metadata (channels, fs, etc.) for a file."""
        return self._files[path]["metadata"]

    def get_available_channels(self, path: str):
        """Convenience method to list channels."""
        return self._files[path]["metadata"].get("channels", [])

    def unload_file(self, path: str):
        """Remove a file and its caches from the manager."""
        if path in self._files:
            del self._files[path]

    def list_loaded_files(self):
        """List all currently loaded file paths."""
        return list(self._files.keys())

    def clear_all(self):
        """Clear manager of all loaded files and caches."""
        self._files.clear()
