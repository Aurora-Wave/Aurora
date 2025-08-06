"""
Intelligent Downsampling Utilities for Visualization Performance.
Provides adaptive downsampling based on plot resolution and data characteristics.
"""

import numpy as np
from typing import Tuple, Optional
from Pyside.core import get_user_logger


class IntelligentDownsampler:
    """
    Adaptive downsampling for optimal visualization performance.
    Adjusts point density based on plot resolution and data complexity.
    """

    def __init__(self):
        self.logger = get_user_logger(self.__class__.__name__)

        # Default configuration
        self.min_points = 100  # Minimum points to preserve data shape
        self.max_points_per_pixel = 2  # Maximum points per display pixel
        self.complexity_threshold = 0.1  # Threshold for data complexity analysis

    def calculate_optimal_points(
        self, data_length: int, plot_width_pixels: int = 800
    ) -> int:
        """
        Calculate optimal number of points based on plot resolution.

        Args:
            data_length: Original data length
            plot_width_pixels: Width of plot in pixels

        Returns:
            Optimal number of points for visualization
        """
        # Base calculation: 2 points per pixel for smooth curves
        optimal_points = plot_width_pixels * self.max_points_per_pixel

        # Ensure minimum points for data integrity
        optimal_points = max(optimal_points, self.min_points)

        # Don't downsample if data is already smaller
        optimal_points = min(optimal_points, data_length)

        self.logger.debug(
            f"Optimal points: {optimal_points} for data length {data_length}, plot width {plot_width_pixels}px"
        )

        return optimal_points

    def downsample_intelligent(
        self,
        time_data: np.ndarray,
        signal_data: np.ndarray,
        target_points: int,
        preserve_peaks: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Intelligently downsample data preserving important features.

        Args:
            time_data: Time axis data
            signal_data: Signal amplitude data
            target_points: Target number of points
            preserve_peaks: Whether to preserve local maxima/minima

        Returns:
            Tuple of (downsampled_time, downsampled_signal)
        """
        if len(signal_data) <= target_points:
            return time_data, signal_data

        if preserve_peaks and len(signal_data) > target_points * 2:
            return self._downsample_with_peak_preservation(
                time_data, signal_data, target_points
            )
        else:
            return self._downsample_uniform(time_data, signal_data, target_points)

    def _downsample_uniform(
        self, time_data: np.ndarray, signal_data: np.ndarray, target_points: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simple uniform downsampling - FIXED to preserve endpoints."""
        if len(signal_data) <= target_points:
            return time_data, signal_data

        # Always include first and last points
        if target_points >= 2:
            # Create indices that always include start and end
            indices = np.linspace(0, len(signal_data) - 1, target_points, dtype=int)
        else:
            indices = np.array([0], dtype=int)

        return time_data[indices], signal_data[indices]

    def _downsample_with_peak_preservation(
        self, time_data: np.ndarray, signal_data: np.ndarray, target_points: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Advanced downsampling that preserves important peaks and valleys.
        FIXED to be deterministic and preserve endpoints.
        """
        if len(signal_data) <= target_points:
            return time_data, signal_data

        # Always preserve first and last points
        required_indices = {0, len(signal_data) - 1}

        # Allocate remaining points: 70% uniform, 30% for peaks
        remaining_points = target_points - len(required_indices)
        if remaining_points <= 0:
            indices = np.array(list(required_indices), dtype=int)
            return time_data[indices], signal_data[indices]

        uniform_points = max(1, int(remaining_points * 0.7))
        peak_points = remaining_points - uniform_points

        # Uniform sampling base (excluding endpoints)
        if uniform_points > 0:
            uniform_indices = np.linspace(
                1, len(signal_data) - 2, uniform_points, dtype=int
            )
            required_indices.update(uniform_indices)

        # Find significant peaks and valleys with deterministic selection
        if peak_points > 0:
            peak_indices = self._find_significant_peaks(signal_data, peak_points // 2)
            valley_indices = self._find_significant_valleys(
                signal_data, peak_points - len(peak_indices)
            )
            required_indices.update(peak_indices)
            required_indices.update(valley_indices)

        # Convert to sorted array
        all_indices = np.array(sorted(required_indices), dtype=int)

        # Ensure we don't exceed target_points
        if len(all_indices) > target_points:
            # Keep evenly distributed subset, always preserving endpoints
            if target_points >= 2:
                step = (
                    (len(all_indices) - 2) // (target_points - 2)
                    if target_points > 2
                    else 1
                )
                selected = [all_indices[0]]  # First point
                for i in range(1, len(all_indices) - 1, step):
                    if len(selected) < target_points - 1:
                        selected.append(all_indices[i])
                selected.append(all_indices[-1])  # Last point
                all_indices = np.array(selected, dtype=int)
            else:
                all_indices = all_indices[:target_points]

        return time_data[all_indices], signal_data[all_indices]

    def _find_significant_peaks(self, data: np.ndarray, max_peaks: int) -> np.ndarray:
        """Find significant local maxima - DETERMINISTIC version."""
        if max_peaks <= 0 or len(data) < 3:
            return np.array([], dtype=int)

        # Simple peak detection - find points higher than neighbors
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1]:
                peaks.append((i, data[i]))

        # Sort by prominence (height) then by index for deterministic behavior
        peaks.sort(
            key=lambda x: (-x[1], x[0])
        )  # Descending by value, ascending by index
        peak_indices = [p[0] for p in peaks[:max_peaks]]

        return np.array(peak_indices, dtype=int)

    def _find_significant_valleys(
        self, data: np.ndarray, max_valleys: int
    ) -> np.ndarray:
        """Find significant local minima - DETERMINISTIC version."""
        if max_valleys <= 0 or len(data) < 3:
            return np.array([], dtype=int)

        # Simple valley detection - find points lower than neighbors
        valleys = []
        for i in range(1, len(data) - 1):
            if data[i] < data[i - 1] and data[i] < data[i + 1]:
                valleys.append((i, data[i]))

        # Sort by prominence (lowest values) then by index for deterministic behavior
        valleys.sort(
            key=lambda x: (x[1], x[0])
        )  # Ascending by value, ascending by index
        valley_indices = [v[0] for v in valleys[:max_valleys]]

        return np.array(valley_indices, dtype=int)

    def analyze_data_complexity(self, data: np.ndarray) -> float:
        """
        Analyze data complexity to determine if peak preservation is needed.

        Returns:
            Complexity score (0-1, higher = more complex)
        """
        if len(data) < 10:
            return 0.0

        # Calculate local variance as complexity measure
        local_variance = np.var(np.diff(data))
        global_variance = np.var(data)

        if global_variance == 0:
            return 0.0

        complexity = min(local_variance / global_variance, 1.0)
        return complexity

    def downsample_adaptive(
        self,
        time_data: np.ndarray,
        signal_data: np.ndarray,
        plot_width_pixels: int = 800,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Adaptive downsampling that considers data complexity and plot resolution.

        Args:
            time_data: Time axis data
            signal_data: Signal amplitude data
            plot_width_pixels: Width of plot in pixels

        Returns:
            Tuple of (downsampled_time, downsampled_signal)
        """
        # Calculate optimal points based on plot resolution
        target_points = self.calculate_optimal_points(
            len(signal_data), plot_width_pixels
        )

        # Analyze data complexity
        complexity = self.analyze_data_complexity(signal_data)
        preserve_peaks = complexity > self.complexity_threshold

        self.logger.debug(
            f"Data complexity: {complexity:.3f}, preserve_peaks: {preserve_peaks}"
        )

        # Apply intelligent downsampling
        return self.downsample_intelligent(
            time_data, signal_data, target_points, preserve_peaks
        )


# Global instance for easy access
default_downsampler = IntelligentDownsampler()
