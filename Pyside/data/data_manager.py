import os
import logging
from collections import deque
from Pyside.data.aditch_loader import AditchLoader


# from .edf_loader import EDFLoader

MAX_HR_CACHE = 5  # Maximum HR_gen configurations to cache


class DataManager:
    def __init__(self):
        self._files = {}
        self._loader_registry = {
            ".adicht": AditchLoader,
            # ".edf": EDFLoader,
        }
        self.logger = logging.getLogger(__name__)

    def load_file(self, path: str):
        """
        Load a file, extract signals and metadata, and initialize caches.
        """
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._loader_registry:
            raise ValueError(f"Unsupported file type: {ext}")
        if path in self._files:
            return

        loader = self._loader_registry[ext]()
        loader.load(path)
        # Initialize caches and metadata for this file
        self._files[path] = {
            "loader": loader,
            "signal_cache": {},
            "metadata": loader.get_metadata(),
            "comments": loader.get_all_comments(),
            "hr_cache": {},  # dict: key (config tuple) -> Signal
            "hr_cache_keys": deque(maxlen=MAX_HR_CACHE),  # order of keys for eviction
        }
        # If the file already has HR_gen, cache it as canonical
        if "HR_gen" in self._files[path]["metadata"].get("channels", []):
            sig = loader.get_full_trace("HR_gen")
            self._files[path]["signal_cache"]["HR_gen"] = sig

    def get_trace(self, path: str, channel: str, **kwargs):
        """
        Get a signal trace. For HR_gen, support parameterized caching.
        """
        entry = self._files[path]
        cache = entry["signal_cache"]

        # Special handling for HR_gen (parameterized)
        if channel.upper() == "HR_GEN":
            # Create a unique, hashable key from configuration
            key = tuple(sorted(kwargs.items()))
            hr_cache = entry["hr_cache"]
            hr_keys = entry["hr_cache_keys"]

            # If version for this config exists, return it
            if key in hr_cache:
                return hr_cache[key]

            # Otherwise, generate, cache and manage eviction
            sig = entry["loader"].get_full_trace(channel, **kwargs)
            hr_cache[key] = sig
            hr_keys.append(key)
            # Enforce cache size
            while len(hr_keys) > MAX_HR_CACHE:
                old_key = hr_keys.popleft()
                hr_cache.pop(old_key, None)

            # If config is default, update canonical HR_gen in signal_cache
            if self._is_default_hr_config(**kwargs):
                cache[channel] = sig
                # Ensure HR_gen is in metadata
                if "HR_gen" not in entry["metadata"]["channels"]:
                    entry["metadata"]["channels"].append("HR_gen")
                self.logger.info(
                    f"HR_gen added to metadata from {path} file [default config]"
                )

            return sig

        # Any other channel: load and cache if not already present
        if channel not in cache:
            sig = entry["loader"].get_full_trace(channel)
            cache[channel] = sig
        return cache[channel]

    def promote_hr_as_main(self, path, hr_sig, **kwargs):
        """
        Promote a parameterized HR_gen as the canonical HR_gen in signal_cache.
        """
        key = tuple(sorted(kwargs.items()))
        entry = self._files[path]
        # Save as canonical
        entry["signal_cache"]["HR_gen"] = hr_sig
        # Make sure HR_gen is in metadata channels
        if "HR_gen" not in entry["metadata"]["channels"]:
            entry["metadata"]["channels"].append("HR_gen")
        # Update hr_cache and keys if not already present
        if key not in entry["hr_cache"]:
            entry["hr_cache"][key] = hr_sig
            entry["hr_cache_keys"].append(key)
        self.logger.info(f"Promoted HR_gen with config {key} as main (canonical)")

    def _is_default_hr_config(self, **kwargs):
        """
        Check if current configuration matches the default for HR_gen.
        """
        # Define the default config here
        defaults = {
            "wavelet": "db3",
            "swt_level": 3,
            "min_rr_sec": 0.4,
            # Add other defaults if needed
        }
        # If no params, treat as default
        if not kwargs:
            return True
        return all(kwargs.get(k, defaults[k]) == defaults[k] for k in defaults)

    def get_comments(self, path: str):
        """
        Get all annotations/comments for a file.
        """
        return self._files[path]["comments"]

    def get_metadata(self, path: str):
        """
        Get metadata (channels, fs, etc.) for a file.
        """
        return self._files[path]["metadata"]

    def get_available_channels(self, path: str):
        """
        List available channels according to file metadata, including computed signals.
        """
        base_channels = self._files[path]["metadata"].get("channels", [])

        # Agregar canales computados disponibles (evitando duplicados)
        computed_channels = []
        if "ECG" in base_channels and "HR_gen" not in base_channels:
            computed_channels.append("HR_gen")

        return base_channels + computed_channels

    def unload_file(self, path: str):
        """
        Remove a file and its caches from the manager.
        """
        if path in self._files:
            del self._files[path]

    def list_loaded_files(self):
        """
        List all currently loaded file paths.
        """
        return list(self._files.keys())

    def clear_all(self):
        """
        Clear manager of all loaded files and caches.
        """
        self._files.clear()

    def update_hr_cache(self, path, hr_sig, **kwargs):
        """
        Update or add a HR_gen version to the parameterized cache.
        """
        key = tuple(sorted(kwargs.items()))
        entry = self._files[path]
        entry["hr_cache"][key] = hr_sig

        if "HR_gen" not in entry["metadata"]["channels"]:
            entry["metadata"]["channels"].append("HR_gen")
            self.logger.info(f"HR_gen added to metadata from {path} file")

        if key in entry["hr_cache_keys"]:
            entry["hr_cache_keys"].remove(key)
        entry["hr_cache_keys"].append(key)
        self.logger.info(f"Updating HR_cache with key {key}")
