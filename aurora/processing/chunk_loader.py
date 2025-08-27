"""
ChunkLoader - Efficient chunk-based data loading for Aurora sessions.

This module provides optimized chunk loading for physiological signal visualization
with support for the new session-based architecture. Features include:

- Session-isolated chunk loading
- Asynchronous and synchronous interfaces
- Intelligent downsampling for smooth visualization
- Memory-efficient caching with LRU eviction
- Support for parameterized HR_gen signals
- Qt signal-based communication with UI components

Architecture:
- Integrated with Session and DataManager
- Compatible with VisualizationBaseTab and PlotContainerWidget
- Throttled requests to prevent UI blocking
- Automatic memory management per session
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict
from PySide6.QtCore import QObject, Signal as QtSignal, QTimer
from aurora.core.session import Session


class ChunkCache:
    """
    LRU cache for chunk data with session-based memory limits.
    """

    def __init__(self, max_size: int = 50):
        """
        Initialize chunk cache.

        Args:
            max_size: Maximum number of cached chunks
        """
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.logger = logging.getLogger("aurora.processing.ChunkCache")

    def get(self, key: str) -> Optional[Dict[str, np.ndarray]]:
        """Get cached chunk data, updating LRU order."""
        if key in self.cache:
            # Move to end (most recently used)
            chunk_data = self.cache.pop(key)
            self.cache[key] = chunk_data
            return chunk_data
        return None

    def put(self, key: str, data: Dict[str, np.ndarray]) -> None:
        """Store chunk data with LRU eviction."""
        if key in self.cache:
            # Update existing entry
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            # Evict oldest entry
            oldest_key = next(iter(self.cache))
            evicted_data = self.cache.pop(oldest_key)
            self.logger.debug(f"Evicted chunk cache entry: {oldest_key}")

        self.cache[key] = data
        self.logger.debug(f"Cached chunk: {key}")

    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        self.logger.debug("Chunk cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "utilization": (
                len(self.cache) / self.max_size if self.max_size > 0 else 0.0
            ),
        }


class ChunkLoader(QObject):
    """
    Session-integrated chunk loader for efficient signal visualization.

    This class provides optimized chunk loading for physiological signals with
    support for the Aurora session architecture. Features include:

    - Session-isolated data access through Session.data_manager
    - Asynchronous chunk loading with Qt signals
    - Intelligent downsampling for smooth visualization
    - LRU caching with memory limits
    - Support for HR_gen with different parameters
    - Request throttling to prevent UI blocking

    Signals:
        chunk_loaded: Emitted when chunk data is ready (start_sec, end_sec, data_dict)
        chunk_error: Emitted when chunk loading fails (error_message)
        cache_stats_updated: Emitted when cache statistics change (stats_dict)
    """

    # Qt Signals for asynchronous communication
    chunk_loaded = QtSignal(
        float, float, dict
    )  # start_sec, end_sec, {channel: chunk_data}
    chunk_error = QtSignal(str)  # error_message
    cache_stats_updated = QtSignal(dict)  # cache statistics

    def __init__(self, session: Session, parent=None):
        """
        Initialize ChunkLoader for a specific session.

        Args:
            session: Session object containing data_manager and configuration
            parent: Parent QObject for Qt ownership
        """
        super().__init__(parent)

        self.session = session
        self.logger = logging.getLogger(
            f"aurora.processing.ChunkLoader.{session.session_id}"
        )

        # Get cache configuration from session
        cache_size = session.get_config("chunk_cache_size", 50)
        self.cache = ChunkCache(cache_size)

        # Request throttling to prevent UI blocking
        self.request_timer = QTimer()
        self.request_timer.setSingleShot(True)
        self.request_timer.timeout.connect(self._process_pending_request)
        self.pending_request: Optional[Tuple] = None

        # Configuration - optimized for responsive navigation
        self.throttle_delay_ms = 5  # Minimal delay for responsive UI (was 50ms)
        # Unified limit for all signals - optimized for performance and visual quality
        self.max_points_per_plot = 20000  # Points before downsampling - all signals equal

        self.logger.debug(f"ChunkLoader initialized for session {session.session_id}")

    @staticmethod
    def get_chunk(
        session: Session,
        channel_names: List[str],
        start_sec: float,
        duration_sec: float,
        **hr_params,
    ) -> Dict[str, np.ndarray]:
        """
        Synchronously extract chunk data (blocking call).

        This static method provides immediate access to chunk data for cases
        where synchronous access is needed (e.g., analysis operations).

        Args:
            session: Session containing data_manager and file_path
            channel_names: Names of channels to extract
            start_sec: Start time in seconds
            duration_sec: Duration in seconds
            **hr_params: Parameters for HR_gen signal generation

        Returns:
            Dictionary mapping channel names to numpy arrays

        Raises:
            ValueError: If session or channels are invalid
            Exception: If data extraction fails
        """
        if not session or not session.data_manager:
            raise ValueError("Invalid session or data_manager")

        if not session.file_path:
            raise ValueError("No file loaded in session")

        results = {}
        data_manager = session.data_manager
        file_path = session.file_path

        for ch in channel_names:
            try:
                # Get signal from data manager
                if ch.upper() == "HR_GEN":
                    sig = data_manager.get_trace(file_path, ch, **hr_params)
                else:
                    sig = data_manager.get_trace(file_path, ch)

                if sig is None:
                    continue

                # Extract chunk from signal
                fs = sig.fs
                data = sig.data

                # Calculate indices with bounds checking
                start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
                end_idx = int(
                    max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data)))
                )

                # Extract chunk
                chunk = data[start_idx:end_idx]
                results[ch] = chunk

            except Exception as e:
                # Log error but continue with other channels
                logger = logging.getLogger("aurora.processing.ChunkLoader")
                logger.warning(f"Failed to extract chunk for channel {ch}: {e}")
                continue

        return results

    def request_chunk(
        self,
        channel_names: List[str],
        start_sec: float,
        duration_sec: float,
        **hr_params,
    ) -> None:
        """
        Asynchronously request chunk data with throttling.

        This method queues a chunk request and processes it after a short delay
        to prevent overwhelming the system with rapid requests (e.g., during
        fast scrolling or resizing).

        Args:
            channel_names: Names of channels to extract
            start_sec: Start time in seconds
            duration_sec: Duration in seconds
            **hr_params: Parameters for HR_gen signal generation
        """
        # Store pending request (overwrites any existing pending request)
        self.pending_request = (channel_names, start_sec, duration_sec, hr_params)

        # Start or restart throttling timer
        self.request_timer.start(self.throttle_delay_ms)

        self.logger.debug(
            f"Chunk request queued: channels={channel_names}, start={start_sec:.2f}s"
        )

    def _process_pending_request(self) -> None:
        """Process the pending chunk request."""
        if not self.pending_request:
            return

        channel_names, start_sec, duration_sec, hr_params = self.pending_request
        self.pending_request = None

        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                channel_names, start_sec, duration_sec, hr_params
            )

            # Check cache first
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                self.logger.debug(f"Using cached chunk: {cache_key}")
                self.chunk_loaded.emit(start_sec, start_sec + duration_sec, cached_data)
                return

            # Extract chunk data
            chunk_data = self._extract_chunk_data(
                channel_names, start_sec, duration_sec, hr_params
            )

            # Cache the result
            self.cache.put(cache_key, chunk_data)

            # Emit cache statistics
            self.cache_stats_updated.emit(self.cache.get_cache_info())

            # Emit chunk data
            self.chunk_loaded.emit(start_sec, start_sec + duration_sec, chunk_data)

            self.logger.debug(
                f"Chunk processed: {len(chunk_data)} channels, {start_sec:.2f}-{start_sec + duration_sec:.2f}s"
            )

        except Exception as e:
            error_msg = f"Failed to process chunk request: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.chunk_error.emit(error_msg)

    def _extract_chunk_data(
        self,
        channel_names: List[str],
        start_sec: float,
        duration_sec: float,
        hr_params: Dict,
    ) -> Dict[str, np.ndarray]:
        """Extract and process chunk data from session data manager."""
        results = {}
        data_manager = self.session.data_manager
        file_path = self.session.file_path

        for ch in channel_names:
            try:
                # Get signal from data manager
                if ch.upper() == "HR_GEN":
                    sig = data_manager.get_trace(file_path, ch, **hr_params)
                else:
                    sig = data_manager.get_trace(file_path, ch)

                if sig is None:
                    self.logger.warning(f"No signal found for channel: {ch}")
                    continue

                # Extract chunk from signal
                fs = sig.fs
                data = sig.data

                # Calculate indices with bounds checking
                start_idx = int(max(0, min(start_sec * fs, len(data) - 1)))
                end_idx = int(
                    max(start_idx + 1, min((start_sec + duration_sec) * fs, len(data)))
                )

                # Extract chunk
                chunk = data[start_idx:end_idx]

                # Apply downsampling if chunk is too large
                chunk_downsampled = self._apply_downsampling(chunk, fs, start_sec, ch)

                results[ch] = chunk_downsampled

            except Exception as e:
                self.logger.error(f"Error extracting chunk for channel {ch}: {e}")
                # Continue with other channels instead of failing completely
                continue

        return results

    def _apply_downsampling(
        self, chunk: np.ndarray, fs: float, start_sec: float, channel_name: str = ""
    ) -> np.ndarray:
        """
        Apply uniform downsampling to chunk data for visualization performance.
        
        TODO: FIXME - DOWNSAMPLING ALGORITHM IS BROKEN
        Current algorithm causes high-resolution signals (ECG) to display "at half size"
        while lower resolution signals display correctly.
        
        TEMPORARY SOLUTION: Return original chunk without downsampling
        This ensures all signals display correctly but may impact performance
        with very large datasets.
        
        ISSUES TO FIX:
        1. Algorithm treats all signals equally but results are inconsistent
        2. High-res signals (ECG 1000Hz) appear truncated/compressed
        3. Low-res signals (others) appear normal
        4. Possible issue with time axis alignment or plot range setting
        
        Args:
            chunk: Original chunk data
            fs: Sampling frequency
            start_sec: Start time for time axis generation
            channel_name: Name of the channel (for logging only)

        Returns:
            Original chunk data (no downsampling applied)
        """
        # TEMPORARY: Return original data without downsampling
        self.logger.debug(
            f"TEMP BYPASS: {channel_name} returning {len(chunk)} points "
            f"(fs={fs:.1f}Hz) - no downsampling applied"
        )
        
        return chunk
        
        # BROKEN CODE DISABLED:
        # if len(chunk) <= self.max_points_per_plot:
        #     return chunk
        # 
        # # Calculate downsampling factor
        # step = max(1, int(np.ceil(len(chunk) / self.max_points_per_plot)))
        # 
        # # Apply intelligent decimation
        # if step <= 2:
        #     # Simple decimation for small factors
        #     downsampled = chunk[::step]
        # else:
        #     # For larger factors, use average-based decimation
        #     trim_length = len(chunk) - (len(chunk) % step)
        #     trimmed_chunk = chunk[:trim_length]
        #     reshaped = trimmed_chunk.reshape(-1, step)
        #     downsampled = np.mean(reshaped, axis=1)
        #     
        #     # Add any remaining samples
        #     if trim_length < len(chunk):
        #         remaining_mean = np.mean(chunk[trim_length:])
        #         downsampled = np.append(downsampled, remaining_mean)
        # 
        # return downsampled

    def _generate_cache_key(
        self,
        channel_names: List[str],
        start_sec: float,
        duration_sec: float,
        hr_params: Dict,
    ) -> str:
        """Generate unique cache key for chunk request."""
        channels_str = "|".join(sorted(channel_names))

        # Round times to avoid cache misses due to floating point precision
        start_rounded = round(start_sec, 2)
        duration_rounded = round(duration_sec, 2)

        # Include HR parameters in key if present
        if hr_params:
            hr_str = "|".join(f"{k}={v}" for k, v in sorted(hr_params.items()))
            return f"{channels_str}_{start_rounded}_{duration_rounded}_{hr_str}"
        else:
            return f"{channels_str}_{start_rounded}_{duration_rounded}"

    def clear_cache(self) -> None:
        """Clear all cached chunk data."""
        self.cache.clear()
        self.cache_stats_updated.emit(self.cache.get_cache_info())
        self.logger.info("Chunk cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        return self.cache.get_cache_info()

    def set_max_points(self, max_points: int) -> None:
        """Set maximum points per plot before downsampling."""
        self.max_points_per_plot = max(10000, max_points)  # Minimum 10k points for good visual quality
        self.logger.debug(f"Max points per plot set to: {self.max_points_per_plot}")

    def set_throttle_delay(self, delay_ms: int) -> None:
        """Set throttling delay for chunk requests."""
        self.throttle_delay_ms = max(1, delay_ms)  # Minimum 1ms for responsiveness
        self.logger.debug(f"Throttle delay set to: {self.throttle_delay_ms}ms")

    def cleanup(self) -> None:
        """Cleanup resources when chunk loader is no longer needed."""
        try:
            # Stop any pending requests
            self.request_timer.stop()
            self.pending_request = None

            # Clear cache
            self.clear_cache()

            self.logger.debug(
                f"ChunkLoader cleanup completed for session {self.session.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Error during ChunkLoader cleanup: {e}")
