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
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal as QtSignal
from aurora.core.session import Session



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

    # Qt Signals for asynchronous communication (simplified like working tree)
    chunk_loaded = QtSignal(float, float, dict)  # start_sec, end_sec, {channel: chunk_data}
    chunk_error = QtSignal(str)  # error_message

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
        self.logger.info(f"ChunkLoader.__init__ starting with session: {session.session_id}")
        self.logger.debug(f"ChunkLoader parent QObject initialization completed")

        # Simple cache like working tree
        self._cache: Dict[str, Tuple[float, float, Dict[str, np.ndarray]]] = {}
        self._cache_order = []  # For LRU tracking
        self._max_cache_size = 50
        
        # Configuration - optimized for responsive navigation
        self.max_points_per_plot = 20000  # Points before downsampling
        
        self.logger.info(f"ChunkLoader initialization completed successfully for session {session.session_id}")
        self.logger.debug(f"ChunkLoader config: cache_size={self._max_cache_size}, max_points={self.max_points_per_plot}")

    def _generate_cache_key(
        self, file_path: str, channel_names: list, start_sec: float, duration_sec: float
    ) -> str:
        """Generate a unique cache key for the chunk request (like working tree)."""
        import hashlib
        key_data = f"{file_path}|{sorted(channel_names)}|{start_sec:.2f}|{duration_sec:.2f}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Tuple[float, float, Dict[str, np.ndarray]]]:
        """Retrieve chunk from cache if available."""
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._cache[cache_key]
        return None

    def _store_in_cache(self, cache_key: str, start: float, end: float, data: Dict[str, np.ndarray]):
        """Store chunk data in cache with LRU eviction."""
        if cache_key in self._cache:
            self._cache_order.remove(cache_key)
        elif len(self._cache) >= self._max_cache_size:
            # Evict oldest entry
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]
        
        self._cache[cache_key] = (start, end, data)
        self._cache_order.append(cache_key)

    def request_chunk(
        self,
        channel_names: List[str],
        start_sec: float,
        duration_sec: float,
        **hr_params,
    ) -> None:
        """
        Simplified chunk request like working tree.
        """
        try:
            # Check cache first
            file_path = self.session.file_path
            cache_key = self._generate_cache_key(file_path, channel_names, start_sec, duration_sec)
            cached_result = self._get_from_cache(cache_key)

            if cached_result is not None:
                start_cached, end_cached, data_cached = cached_result
                self.chunk_loaded.emit(start_cached, end_cached, data_cached)
                return

            # Process chunk if not in cache - SIMPLE like working tree
            result = {}
            data_manager = self.session.data_manager
            
            for ch in channel_names:
                try:
                    # Get signal from data manager (like working tree)
                    if ch.upper() == "HR_GEN":
                        sig = data_manager.get_trace(file_path, ch, **hr_params)
                    else:
                        sig = data_manager.get_trace(file_path, ch)

                    if sig is None:
                        continue

                    # Extract chunk using simple indices (like working tree)
                    fs = sig.fs
                    start_idx = int(start_sec * fs)
                    end_idx = int((start_sec + duration_sec) * fs)
                    chunk = sig.data[start_idx:end_idx]

                    # Apply downsampling if needed
                    if len(chunk) > self.max_points_per_plot:
                        chunk = self._apply_downsampling(chunk, fs, start_sec, ch)

                    result[ch] = chunk

                except Exception as e:
                    self.logger.error(f"Error processing channel {ch}: {e}")
                    continue

            # Store in cache and emit
            self._store_in_cache(cache_key, start_sec, start_sec + duration_sec, result)
            self.chunk_loaded.emit(start_sec, start_sec + duration_sec, result)

        except Exception as e:
            self.logger.error(f"Chunk request failed: {e}")
            self.chunk_error.emit(str(e))


    def _apply_downsampling(
        self, chunk: np.ndarray, fs: float, start_sec: float, channel_name: str = ""
    ) -> np.ndarray:
        """
        Apply intelligent downsampling to chunk data for visualization performance.
        
        Uses adaptive decimation strategy:
        - Small datasets: no downsampling
        - Medium datasets: simple decimation  
        - Large datasets: block averaging to preserve signal characteristics
        
        Args:
            chunk: Original chunk data
            fs: Sampling frequency
            start_sec: Start time for time axis generation
            channel_name: Name of the channel (for logging)

        Returns:
            Downsampled chunk data optimized for visualization
        """
        if len(chunk) <= self.max_points_per_plot:
            # No downsampling needed
            return chunk
        
        # Calculate downsampling factor
        step = max(1, int(np.ceil(len(chunk) / self.max_points_per_plot)))
        
        self.logger.debug(
            f"Downsampling {channel_name}: {len(chunk)} → ~{len(chunk)//step} points (step={step})"
        )
        
        # Apply intelligent decimation based on step size
        if step <= 2:
            # Simple decimation for small factors - preserves peaks
            downsampled = chunk[::step]
        else:
            # For larger factors, use min-max decimation to preserve signal envelope
            # This prevents losing important peaks and valleys
            n_blocks = len(chunk) // step
            remainder = len(chunk) % step
            
            if n_blocks > 0:
                # Reshape data into blocks for min-max extraction
                reshaped = chunk[:n_blocks * step].reshape(n_blocks, step)
                
                # Extract min and max from each block
                mins = np.min(reshaped, axis=1)
                maxs = np.max(reshaped, axis=1)
                
                # Interleave mins and maxs to preserve envelope
                downsampled = np.empty(n_blocks * 2)
                downsampled[0::2] = mins
                downsampled[1::2] = maxs
                
                # Add remaining samples if any
                if remainder > 0:
                    remaining_chunk = chunk[n_blocks * step:]
                    remaining_min = np.min(remaining_chunk)
                    remaining_max = np.max(remaining_chunk)
                    downsampled = np.append(downsampled, [remaining_min, remaining_max])
            else:
                # Fallback for very small chunks
                downsampled = np.array([np.min(chunk), np.max(chunk)])
        
        self.logger.debug(
            f"Downsampled {channel_name}: {len(chunk)} → {len(downsampled)} points"
        )
        
        return downsampled

    def _create_downsampled_time_axis(
        self, original_chunk: np.ndarray, downsampled_chunk: np.ndarray, fs: float, start_sec: float
    ) -> np.ndarray:
        """
        Create appropriate time axis for downsampled data.
        
        Args:
            original_chunk: Original data before downsampling
            downsampled_chunk: Data after downsampling
            fs: Original sampling frequency
            start_sec: Start time
            
        Returns:
            Time axis matching downsampled data length
        """
        original_len = len(original_chunk)
        downsampled_len = len(downsampled_chunk)
        
        if downsampled_len == original_len:
            # No downsampling
            return np.arange(downsampled_len) / fs + start_sec
        
        step = original_len / self.max_points_per_plot
        
        if step <= 2:
            # Simple decimation - linear time mapping
            step_int = int(np.ceil(step))
            time_indices = np.arange(0, original_len, step_int)[:downsampled_len]
            return time_indices / fs + start_sec
        else:
            # Min-max decimation - each pair represents a time block
            n_blocks = downsampled_len // 2
            block_duration = (original_len / fs) / n_blocks if n_blocks > 0 else 1.0
            
            # Create time points for min-max pairs
            time_axis = np.empty(downsampled_len)
            for i in range(n_blocks):
                block_start_time = start_sec + (i * block_duration)
                time_axis[i*2] = block_start_time  # min time
                time_axis[i*2 + 1] = block_start_time + block_duration * 0.5  # mid-block time
            
            # Handle any remaining points
            if downsampled_len % 2 != 0:
                time_axis[-1] = start_sec + (original_len - 1) / fs
                
            return time_axis

    def clear_cache(self) -> None:
        """Clear all cached chunk data."""
        self._cache.clear()
        self._cache_order.clear()
        self.logger.info("Chunk cache cleared")
