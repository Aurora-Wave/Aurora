"""
Data Manager Module for AuroraWave

This module provides centralized data management capabilities for physiological signal files.
It handles caching, signal extraction, and metadata management with support
for multiple file formats and parameterized signal generation.

Classes:
    DataManager: Main data management class with file loading, caching and signal extraction

Example:
    >>> dm = DataManager()
    >>> dm.load_file("path/to/signal.adicht")
    >>> ecg_signal = dm.get_trace("path/to/signal.adicht", "ECG")
    >>> hr_signal = dm.get_trace("path/to/signal.adicht", "hr_aurora", wavelet="haar", level=4)  # (formerly HR_gen)
"""

import os
import bisect
from collections import deque
from typing import Dict, Any, List, Optional, Tuple, Union, TYPE_CHECKING
from pathlib import Path
from PySide6.QtCore import QObject, Signal as QtSignal
from aurora.core import get_user_logger, get_current_session
from aurora.core.config_manager import get_config_manager
from aurora.core.comments import get_comment_manager, EMSComment
from aurora.data.aditch_loader import AditchLoader
from aurora.data.edf_loader import EDFLoader

if TYPE_CHECKING:
    from aurora.core.signal import Signal


class DataManager(QObject):
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

    Signals:
        data_updated: Emitted when data is loaded/updated (file_path, metadata_dict)
        metadata_changed: Emitted when metadata changes (file_path, metadata_dict)

    Example:
        >>> dm = DataManager()
        >>> dm.load_file("/path/to/data.adicht")
        >>> ecg = dm.get_trace("/path/to/data.adicht", "ECG")
    >>> hr = dm.get_trace("/path/to/data.adicht", "hr_aurora", wavelet="db4", level=5)  # (formerly HR_gen)
    """

    # Comment change notification signals
    comments_changed = QtSignal(str)  # (file_path)
    comment_added = QtSignal(str, object)  # (file_path, comment)
    comment_updated = QtSignal(str, object)  # (file_path, comment)
    comment_removed = QtSignal(str, str)  # (file_path, comment_id)

    # Qt Signals for data change notifications
    data_updated = QtSignal(str, dict)  # file_path, metadata_dict
    metadata_changed = QtSignal(str, dict)  # file_path, metadata_dict

    def __init__(self) -> None:
        """
        Initialize the DataManager.

        Sets up file storage, loader registry, logging, and configuration management.
        Initializes empty caches for efficient data access.
        """
        super().__init__()
        self._files: Dict[str, Dict[str, Any]] = {}
        self._loader_registry: Dict[str, type] = {
            ".adicht": AditchLoader,
            ".edf": EDFLoader,
            ".edf+": EDFLoader,  # EDF+ files often use .edf extension
        }
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.config_manager = get_config_manager()

        # Time range cache for performance optimization during navigation
        self._time_cache = (
            {}
        )  # path -> {'start_time', 'end_time', 'comments', 'cache_version'}
        self._cache_version = 0  # Incremented when comments change

        # Subscribe to CommentManager change notifications
        comment_manager = get_comment_manager()
        comment_manager.set_data_manager(self)  # Inject dependency
        comment_manager.comment_created.connect(self._update_comment_cache_create)
        comment_manager.comment_updated.connect(self._update_comment_cache_update)
        comment_manager.comment_deleted.connect(self._update_comment_cache_delete)

    def load_file(self, path: str) -> None:
        """
                Load a physiological signal file and initialize its caches.

                Loads the specified file using the appropriate loader based on file extension.
                Creates internal data structures for caching signals, metadata, and computed
        parameters like hr_aurora (formerly HR_gen) with different configurations.

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
        max_hr_cache = self.config_manager.get_hr_cache_size()

        # Load comments directly from loader
        loaded_comments = loader.get_all_comments()
        # Build ID → Comment mapping for fast CRUD operations
        id_to_comment_map = {str(c.comment_id): c for c in loaded_comments}

        self._files[path] = {
            "loader": loader,
            "signal_cache": {},
            "metadata": loader.get_metadata(),
            "comments": loaded_comments,  # Sorted by time for binary search
            "id_to_comment": id_to_comment_map,  # Fast ID → Comment lookup
            "hr_cache": {},  # dict: key (config tuple) -> Signal
            "hr_cache_keys": deque(maxlen=max_hr_cache),  # order of keys for eviction
            "intervals_cache": None,  # Cache for extracted intervals
            "intervals_cache_key": None,  # Key for cache invalidation
        }
        # If file already contains hr_aurora / HR_gen, cache it as canonical hr_aurora
        meta_ch = [c.lower() for c in self._files[path]["metadata"].get("channels", [])]
        if "hr_aurora" in meta_ch:
            original_name = next(
                c
                for c in self._files[path]["metadata"]["channels"]
                if c.lower() == "hr_aurora"
            )
            sig = loader.get_full_trace(original_name)
            self._files[path]["signal_cache"]["hr_aurora"] = sig
        elif "hr_gen" in meta_ch:
            original_name = next(
                c
                for c in self._files[path]["metadata"]["channels"]
                if c.lower() == "hr_gen"
            )
            sig = loader.get_full_trace(original_name)
            self._files[path]["signal_cache"]["hr_aurora"] = sig

        # Emit data_updated signal with metadata for ChunkLoader
        self.logger.debug(f"Emitting data_updated signal for: {path}")
        self.data_updated.emit(path, self._files[path]["metadata"])

    def get_trace(self, path: str, channel: str, **kwargs) -> "Signal":
        """
                Get a signal trace with optional parameterized generation.

            Retrieves the specified signal channel from the loaded file. For hr_aurora signals
        (formerly HR_gen),
                supports parameterized generation with different algorithms and caching of
                multiple parameter configurations.

                Args:
                    path: Absolute path to the loaded signal file
                    channel: Name of the signal channel to retrieve
                    **kwargs: Optional parameters for signal generation (used for hr_aurora / HR_gen)
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
                    >>> hr_default = dm.get_trace("/path/file.adicht", "hr_aurora")
                    >>> hr_custom = dm.get_trace("/path/file.adicht", "hr_aurora",
                    ...                        wavelet="db4", level=5, min_rr_sec=0.8)
        """
        entry = self._files[path]
        cache = entry["signal_cache"]

        # Normalize HR_gen alias → hr_aurora
        if channel.lower() == "hr_gen":
            # Backward-compatibility: emit warning only once per session
            if not getattr(self, "_hr_gen_deprecation_warned", False):
                self.logger.warning(
                    "'HR_gen' is deprecated; use 'hr_aurora'. Maintaining temporary compatibility."
                )
                self._hr_gen_deprecation_warned = True
            channel = "hr_aurora"

        # Special handling for hr_aurora (parameterized)
        if channel.lower() == "hr_aurora":
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

            # If config is default, update canonical hr_aurora in signal_cache
            if self._is_default_hr_config(**kwargs):
                cache[channel] = sig
                # Ensure hr_aurora present in metadata
                if not any(
                    c.lower() == "hr_aurora" for c in entry["metadata"]["channels"]
                ):
                    entry["metadata"]["channels"].append("hr_aurora")
                    self.logger.info(
                        f"hr_aurora added to metadata from {path} file [default config]"
                    )
                    # Emit metadata_changed signal when hr_aurora is added
                    self.logger.debug(
                        f"Emitting metadata_changed signal for hr_aurora: {path}"
                    )
                    self.metadata_changed.emit(path, entry["metadata"])

            return sig

        # Any other channel: load and cache if not already present
        if channel not in cache:
            sig = entry["loader"].get_full_trace(channel)
            cache[channel] = sig
        return cache[channel]

    def promote_hr_as_main(self, path, hr_sig, **kwargs):
        """
        Promote a parameterized hr_aurora as the canonical hr_aurora in signal_cache.
        """
        key = tuple(sorted(kwargs.items()))
        entry = self._files[path]
        # Save as canonical
        entry["signal_cache"]["hr_aurora"] = hr_sig
        # Make sure hr_aurora is in metadata channels
        if not any(c.lower() == "hr_aurora" for c in entry["metadata"]["channels"]):
            entry["metadata"]["channels"].append("hr_aurora")
            # Emit metadata_changed signal when hr_aurora is promoted
            self.logger.debug(
                f"Emitting metadata_changed signal for promoted hr_aurora: {path}"
            )
            self.metadata_changed.emit(path, entry["metadata"])
        # Update hr_cache and keys if not already present
        if key not in entry["hr_cache"]:
            entry["hr_cache"][key] = hr_sig
            entry["hr_cache_keys"].append(key)
        self.logger.info(f"Promoted hr_aurora with config {key} as main (canonical)")

    def _is_default_hr_config(self, **kwargs):
        """
        Check if current configuration matches the default for hr_aurora (HR_gen).
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
        Get all comments for a file (cached in DataManager).
        Comments are guaranteed to be sorted by time for O(log n) binary search.
        """
        return self._files[path]["comments"]

    def get_comments_in_time_range(
        self, path: str, start_time: float, end_time: float
    ) -> List[EMSComment]:
        """
        Get comments in time range with time cache optimization for slider navigation.
        Uses cache to avoid repeated binary searches when time ranges overlap.

        Args:
            path: File path
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            List of EMSComment objects in time range, already sorted by time
        """
        if path not in self._files:
            return []

        comments = self._files[path]["comments"]
        if not comments:
            return []

        # Check cache for overlapping range
        cache_key = path
        if cache_key in self._time_cache:
            cache_entry = self._time_cache[cache_key]
            # Cache hit if ranges overlap and cache is current
            if (
                cache_entry["cache_version"] == self._cache_version
                and start_time >= cache_entry["start_time"]
                and end_time <= cache_entry["end_time"]
            ):
                # Filter cached comments to exact range
                return [
                    c
                    for c in cache_entry["comments"]
                    if start_time <= c.time <= end_time
                ]

        # Cache miss - perform binary search and cache larger range
        times = [c.time for c in comments]
        start_idx = bisect.bisect_left(times, start_time)
        end_idx = bisect.bisect_right(times, end_time)

        # Cache a larger range (2x) to improve future hit rate during navigation
        cache_expansion = (end_time - start_time) * 0.5  # Expand by 50% on each side
        cache_start = max(0, start_time - cache_expansion)
        cache_end = end_time + cache_expansion

        # Get expanded range for cache
        cache_start_idx = bisect.bisect_left(times, cache_start)
        cache_end_idx = bisect.bisect_right(times, cache_end)
        cached_comments = comments[cache_start_idx:cache_end_idx]

        # Update cache
        self._time_cache[cache_key] = {
            "start_time": cache_start,
            "end_time": cache_end,
            "comments": cached_comments,
            "cache_version": self._cache_version,
        }

        return comments[start_idx:end_idx]

    def get_comments_in_range(self, path: str, start_time: float, end_time: float):
        """
        Get comments within a specific time range using optimized binary search.

        Args:
            path: File path
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            list: Filtered comments using O(log n + k) binary search
        """
        return self.get_comments_in_time_range(path, start_time, end_time)

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
        # Note: Currently only hr_aurora is suggested as a derived/computed channel.
        # Future additions (e.g., resp_rate) could follow the same logic.
        # Agregar canales computados disponibles (evitando duplicados)
        computed_channels = []
        # Add hr_aurora if an ECG exists and it's not already present
        if any(ch.lower() == "ecg" for ch in base_channels) and not any(
            ch.lower() == "hr_aurora" for ch in base_channels
        ):
            computed_channels.append("hr_aurora")

        return base_channels + computed_channels

    def get_available_channels_for_export(self, path: str):
        """
        List available channels for export, including distinct hr_aurora (HR_gen) configurations.
        """
        base_channels = self._files[path]["metadata"].get("channels", [])
        # Get all non-hr_aurora channels
        export_channels = [ch for ch in base_channels if ch.lower() != "hr_aurora"]

        # Add available hr_aurora configurations with descriptive names
        if any(ch.lower() == "ecg" for ch in base_channels):
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

                    descriptive_name = f"hr_aurora_{wavelet}_lv{level}_rr{min_rr}"
                    export_channels.append(descriptive_name)
            else:
                # No cached configurations, add generic hr_aurora
                export_channels.append("hr_aurora")

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
        Update or add a hr_aurora version to the parameterized cache.
        """
        key = tuple(sorted(kwargs.items()))
        entry = self._files[path]
        entry["hr_cache"][key] = hr_sig

        if not any(c.lower() == "hr_aurora" for c in entry["metadata"]["channels"]):
            entry["metadata"]["channels"].append("hr_aurora")
            self.logger.info(f"hr_aurora added to metadata from {path} file")
            # Emit metadata_changed signal when hr_aurora is added to cache
            self.logger.debug(
                f"Emitting metadata_changed signal for cached hr_aurora: {path}"
            )
            self.metadata_changed.emit(path, entry["metadata"])

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
        from aurora.processing.interval_extractor import extract_event_intervals
        import os

        if path not in self._files:
            raise ValueError(f"File {path} not loaded")

        entry = self._files[path]

        # Use default channels if none specified
        if channel_names is None:
            available = set(self.get_available_channels(path))
            if "hr_aurora" in {k.split("|")[0].lower() for k in entry["signal_cache"]}:
                available.add("hr_aurora")
            channel_names = [
                ch for ch in ["ECG", "hr_aurora", "FBP", "Valsalva"] if ch in available
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
            if ch.lower() in ("hr_gen", "hr_aurora"):
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

    ####### Comments Signal Response ######

    def _invalidate_time_cache(self, file_path: str = None):
        """Invalidate time cache when comments change"""
        self._cache_version += 1
        if file_path and file_path in self._time_cache:
            del self._time_cache[file_path]

    def _update_comment_cache_create(self, file_path: str, comment):
        """Update cache after comment creation by CommentManager"""
        if file_path not in self._files:
            self.logger.error(f"File {file_path} not loaded")
            return

        # Insert in sorted position for O(log n) binary search later
        comments = self._files[file_path]["comments"]
        insert_pos = bisect.bisect_left([c.time for c in comments], comment.time)
        comments.insert(insert_pos, comment)

        # Update ID → Comment mapping
        id_to_comment = self._files[file_path]["id_to_comment"]
        id_to_comment[str(comment.comment_id)] = comment

        # Invalidate cache after modification
        self._invalidate_time_cache(file_path)

        # Emit signals
        self.comment_added.emit(file_path, comment)
        self.comments_changed.emit(file_path)

        self.logger.debug(
            f"Cache updated: comment {comment.comment_id} added at {comment.time:.2f}s"
        )

    def _update_comment_cache_update(
        self, file_path: str, comment_id: str, updates: dict
    ):
        """Update cache after comment update by CommentManager"""
        if file_path not in self._files:
            self.logger.error(f"File {file_path} not loaded")
            return

        target_id_str = str(comment_id)
        id_to_comment = self._files[file_path]["id_to_comment"]

        # Fast O(1) lookup by ID
        comment = id_to_comment.get(target_id_str)
        if not comment:
            self.logger.warning(
                f"Comment '{target_id_str}' not found in cache for update"
            )
            return

        # Find position in sorted list (only when time changes)
        comments = self._files[file_path]["comments"]

        # If time changes, need to reposition for sorted order
        if "time_sec" in updates:
            comment_index = comments.index(comment)
            # Remove from current position
            comments.pop(comment_index)

            # Update time
            comment.time = updates["time_sec"]

            # Insert at new sorted position
            insert_pos = bisect.bisect_left([c.time for c in comments], comment.time)
            comments.insert(insert_pos, comment)

            self.logger.debug(
                f"Comment {comment_id} repositioned from {comment_index} to {insert_pos}"
            )

        # Update other fields
        if "text" in updates:
            comment.text = updates["text"]
        if "label" in updates:
            comment.label = updates["label"]

        # Invalidate cache after modification
        self._invalidate_time_cache(file_path)

        # Emit signals
        self.comment_updated.emit(file_path, comment)
        self.comments_changed.emit(file_path)

        self.logger.debug(f"Cache updated: comment {comment_id} modified")

    def _update_comment_cache_delete(self, file_path: str, comment_id: str):
        """Update cache after comment deletion by CommentManager"""
        if file_path not in self._files:
            self.logger.error(f"File {file_path} not loaded")
            return

        target_id_str = str(comment_id)

        # Use fast ID mapping to find comment
        id_to_comment = self._files[file_path]["id_to_comment"]
        comment = id_to_comment.get(target_id_str)

        if not comment:
            self.logger.warning(
                f"Comment '{target_id_str}' not found in cache for deletion"
            )
            return

        # Remove from both data structures
        comments = self._files[file_path]["comments"]
        comments.remove(comment)  # O(n) removal from sorted list
        del id_to_comment[target_id_str]  # O(1) removal from mapping

        # Invalidate cache after modification
        self._invalidate_time_cache(file_path)

        # Emit signals
        self.comment_removed.emit(file_path, comment_id)
        self.comments_changed.emit(file_path)

        self.logger.debug(f"Cache updated: comment {comment_id} removed")
