"""
Data Manager Module for AuroraWave

This module provides centralized data management capabilities for physiological signal files.
It handles file loading, caching, signal extraction, and metadata management with support
for multiple file formats and parameterized signal generation.

Classes:
    DataManager: Main data management class with file loading, caching and signal extraction

Example:
    >>> dm = DataManager()
    >>> dm.load_file("path/to/signal.adicht")
    >>> ecg_signal = dm.get_trace("path/to/signal.adicht", "ECG")
    >>> hr_signal = dm.get_trace("path/to/signal.adicht", "HR_gen", wavelet="haar", level=4)
"""

import os
from collections import deque
from typing import Dict, Any, List, Optional, Tuple, Union, TYPE_CHECKING
from pathlib import Path
from Pyside.core import get_user_logger, get_current_session
from Pyside.core.config_manager import get_config_manager
from Pyside.data.aditch_loader import AditchLoader

if TYPE_CHECKING:
    from Pyside.core.signal import Signal


# from .edf_loader import EDFLoader


class DataManager:
    """
    Centralized data management for physiological signal files.

    This class provides a unified interface for loading, caching, and accessing
    physiological signal data from multiple file formats. It includes advanced
    features like parameterized HR generation, intelligent caching, and metadata
    management.

    Attributes:
        _files (Dict[str, Dict]): Internal storage for loaded files and their metadata
        _loader_registry (Dict[str, type]): Registry of file format loaders
        logger: Logger instance for this class
        session: Current user session
        config_manager: Configuration manager instance

    Example:
        >>> dm = DataManager()
        >>> dm.load_file("/path/to/data.adicht")
        >>> ecg = dm.get_trace("/path/to/data.adicht", "ECG")
        >>> hr = dm.get_trace("/path/to/data.adicht", "HR_gen", wavelet="db4", level=5)
    """

    def __init__(self) -> None:
        """
        Initialize the DataManager.

        Sets up file storage, loader registry, logging, and configuration management.
        Initializes empty caches for efficient data access.
        """
        self._files: Dict[str, Dict[str, Any]] = {}
        self._loader_registry: Dict[str, type] = {
            ".adicht": AditchLoader,
            # ".edf": EDFLoader,
        }
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.config_manager = get_config_manager()

    def load_file(self, path: str) -> None:
        """
        Load a physiological signal file and initialize its caches.

        Loads the specified file using the appropriate loader based on file extension.
        Creates internal data structures for caching signals, metadata, and computed
        parameters like HR_gen with different configurations.

        Args:
            path: Absolute path to the signal file to load

        Raises:
            ValueError: If file extension is not supported
            FileNotFoundError: If file does not exist
            Exception: If file loading fails

        Example:
            >>> dm.load_file("/data/patient_001.adicht")
        """
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._loader_registry:
            raise ValueError(f"Unsupported file type: {ext}")
        if path in self._files:
            return

        loader = self._loader_registry[ext]()
        loader.load(path)
        self.session.log_action(
            f"File loaded by DataManager: {os.path.basename(path)}", self.logger
        )
        # Initialize caches and metadata for this file
        max_hr_cache = self.config_manager.get_hr_cache_size()
        self._files[path] = {
            "loader": loader,
            "signal_cache": {},
            "metadata": loader.get_metadata(),
            "comments": loader.get_all_comments(),
            "hr_cache": {},  # dict: key (config tuple) -> Signal
            "hr_cache_keys": deque(maxlen=max_hr_cache),  # order of keys for eviction
            "intervals_cache": None,  # Cache for extracted intervals
            "intervals_cache_key": None,  # Key for cache invalidation
        }
        # If the file already has HR_gen, cache it as canonical
        if "HR_gen" in self._files[path]["metadata"].get("channels", []):
            sig = loader.get_full_trace("HR_gen")
            self._files[path]["signal_cache"]["HR_gen"] = sig

    def get_trace(self, path: str, channel: str, **kwargs) -> "Signal":
        """
        Get a signal trace with optional parameterized generation.

        Retrieves the specified signal channel from the loaded file. For HR_gen signals,
        supports parameterized generation with different algorithms and caching of
        multiple parameter configurations.

        Args:
            path: Absolute path to the loaded signal file
            channel: Name of the signal channel to retrieve
            **kwargs: Optional parameters for signal generation (used for HR_gen)
                - wavelet (str): Wavelet type for HR generation (default: "haar")
                - level (int): Decomposition level (default: 4)
                - min_rr_sec (float): Minimum RR interval in seconds (default: 0.6)

        Returns:
            Signal: Signal object containing data, sampling frequency, and metadata

        Raises:
            KeyError: If file not loaded or channel not found
            ValueError: If invalid parameters provided

        Example:
            >>> ecg = dm.get_trace("/path/file.adicht", "ECG")
            >>> hr_default = dm.get_trace("/path/file.adicht", "HR_gen")
            >>> hr_custom = dm.get_trace("/path/file.adicht", "HR_gen",
            ...                        wavelet="db4", level=5, min_rr_sec=0.8)
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
            max_hr_cache = self.config_manager.get_hr_cache_size()
            while len(hr_keys) > max_hr_cache:
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
        # Get defaults from centralized config
        defaults = self.config_manager.get_default_hr_config()

        # If no params, treat as default
        if not kwargs:
            return True

        # Check if all provided parameters match defaults
        # Handle both 'level' and 'swt_level' parameter names
        for key, value in kwargs.items():
            if key == "swt_level":
                # Check against both 'level' and 'swt_level' in defaults
                default_val = defaults.get("swt_level", defaults.get("level", 4))
            else:
                default_val = defaults.get(key)

            if default_val is None or value != default_val:
                return False

        return True

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

    def get_available_channels_for_export(self, path: str):
        """
        List available channels for export, including distinct HR_gen configurations.
        """
        base_channels = self._files[path]["metadata"].get("channels", [])

        # Get all non-HR_gen channels
        export_channels = [ch for ch in base_channels if ch.upper() != "HR_GEN"]

        # Add available HR_gen configurations with descriptive names
        if "ECG" in base_channels:
            entry = self._files[path]
            hr_cache = entry.get("hr_cache", {})

            if hr_cache:
                # Add each cached HR configuration with descriptive name
                for hr_config_key in hr_cache.keys():
                    # Convert config key to descriptive name
                    config_dict = dict(hr_config_key)
                    wavelet = config_dict.get("wavelet", "haar")
                    level = config_dict.get("swt_level", config_dict.get("level", 4))
                    min_rr = config_dict.get("min_rr_sec", 0.6)

                    descriptive_name = f"HR_gen_{wavelet}_lv{level}_rr{min_rr}"
                    export_channels.append(descriptive_name)
            else:
                # No cached configurations, add generic HR_gen
                export_channels.append("HR_gen")

        return export_channels

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

    def get_event_intervals(self, path, channel_names=None, **hr_params):
        """
        Get event intervals with caching support.

        Args:
            path: File path
            channel_names: List of channel names to analyze
            **hr_params: HR generation parameters for cache key

        Returns:
            List of interval dictionaries
        """
        from Pyside.processing.interval_extractor import extract_event_intervals
        import os

        if path not in self._files:
            raise ValueError(f"File {path} not loaded")

        entry = self._files[path]

        # Use default channels if none specified
        if channel_names is None:
            available = set(self.get_available_channels(path))
            if "HR_gen" in {k.split("|")[0] for k in entry["signal_cache"]}:
                available.add("HR_gen")
            channel_names = [
                ch for ch in ["ECG", "HR_gen", "FBP", "Valsalva"] if ch in available
            ]

        # Create cache key based on channels and HR parameters
        cache_key = (tuple(sorted(channel_names)), tuple(sorted(hr_params.items())))

        # Check if cached intervals are valid
        if (
            entry["intervals_cache"] is not None
            and entry["intervals_cache_key"] == cache_key
        ):
            self.logger.debug(f"Using cached intervals for {os.path.basename(path)}")
            return entry["intervals_cache"]

        # Extract intervals and cache them
        self.logger.debug(
            f"Extracting intervals for {os.path.basename(path)} with channels {channel_names}"
        )
        signals = []
        for ch in channel_names:
            if ch.upper() == "HR_GEN":
                sig = self.get_trace(path, ch, **hr_params)
            else:
                sig = self.get_trace(path, ch)
            signals.append(sig)

        intervals = extract_event_intervals(signals)

        # Cache the results
        entry["intervals_cache"] = intervals
        entry["intervals_cache_key"] = cache_key

        self.logger.debug(
            f"Cached {len(intervals)} intervals for {os.path.basename(path)}"
        )
        return intervals

    def clear_intervals_cache(self, path):
        """Clear intervals cache for a specific file."""
        if path in self._files:
            self._files[path]["intervals_cache"] = None
            self._files[path]["intervals_cache_key"] = None
            self.logger.debug(f"Cleared intervals cache for {os.path.basename(path)}")

    def clear_all_intervals_cache(self):
        """Clear intervals cache for all files."""
        for path in self._files:
            self.clear_intervals_cache(path)
