import os
from collections import deque

from .aditch_loader import AditchLoader

# from .edf_loader import EDFLoader

MAX_CHUNKS_PER_CHANNEL = 5
MAX_HR_CACHE = 5  # Max HR configurations to cache


class DataManager:
    def __init__(self):
        self._files = {}
        self._loader_registry = {
            ".adicht": AditchLoader,
            # ".edf": EDFLoader,
        }

    def load_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._loader_registry:
            raise ValueError(f"Unsupported file type: {ext}")
        if path in self._files:
            return

        loader = self._loader_registry[ext]()
        loader.load(path)
        self._files[path] = {
            "loader": loader,
            "signal_cache": {},
            "metadata": loader.get_metadata(),
            "comments": loader.get_all_comments(),
            "hr_cache": {},  # dict: key → Signal
            "hr_cache_keys": deque(maxlen=MAX_HR_CACHE),  # orden de las keys
        }

    def get_trace(self, path: str, channel: str, **kwargs):
        entry = self._files[path]
        cache = entry["signal_cache"]

        # HR_gen: use special cache per configuration
        if channel.upper() == "HR_GEN":
            hr_cache = entry["hr_cache"]
            hr_keys = entry["hr_cache_keys"]

            # Unique hashable key from kwargs (tuple sorted)
            key = tuple(sorted(kwargs.items()))

            if key not in hr_cache:
                sig = entry["loader"].get_full_trace(channel, **kwargs)
                hr_cache[key] = sig
                hr_keys.append(key)
                # Enforce max cache size: if the deque popped a key, remove from dict too
                while len(hr_keys) > MAX_HR_CACHE:
                    old_key = hr_keys.popleft()
                    hr_cache.pop(old_key, None)
            return hr_cache[key]

        # Any other channel: normal cache
        if channel not in cache:
            sig = entry["loader"].get_full_trace(channel)
            cache[channel] = sig
        return cache[channel]

    def get_comments(self, path: str):
        """Get all annotations/comments for a file."""
        return self._files[path]["comments"]

    def get_metadata(self, path: str):
        """Get metadata (channels, fs, etc.) for a file."""
        return self._files[path]["metadata"]

    def get_available_channels(self, path: str):
        """List channels according to file metadata, including computed signals."""
        base_channels = self._files[path]["metadata"].get("channels", [])

        # Agregar canales computados disponibles
        computed_channels = []
        if "ECG" in base_channels:
            computed_channels.append("HR_gen")

        return base_channels + computed_channels

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
