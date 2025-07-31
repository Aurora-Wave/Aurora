"""
Unified scrollbar utilities for consistent navigation across visualization tabs.
Provides standardized scrollbar configuration and event handling.
"""

from PySide6.QtWidgets import QScrollBar
from PySide6.QtCore import Qt, QObject, Signal
import logging


class ScrollbarManager(QObject):
    """
    Centralized scrollbar management for visualization tabs.
    Provides consistent behavior and styling across different tabs.
    """

    # Signal emitted when scrollbar value changes
    scroll_changed = Signal(float)  # new_offset

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.ScrollbarManager")

        # Scrollbar configuration
        self._min_height = 20
        self._max_height = 20
        self._min_width = 300

        # Navigation state
        self._total_duration = 0.0
        self._chunk_size = 60.0
        self._current_offset = 0.0

        # Scrollbar reference
        self._scrollbar: QScrollBar = None

    def setup_scrollbar(
        self, scrollbar: QScrollBar, total_duration: float, chunk_size: float
    ):
        """
        Configure scrollbar with standardized settings.

        Args:
            scrollbar: The QScrollBar widget to configure
            total_duration: Total time duration available for scrolling
            chunk_size: Size of visible time window
        """
        self._scrollbar = scrollbar
        self._total_duration = total_duration
        self._chunk_size = chunk_size

        # Apply consistent styling
        scrollbar.setOrientation(Qt.Horizontal)
        scrollbar.setMinimumHeight(self._min_height)
        scrollbar.setMaximumHeight(self._max_height)
        scrollbar.setMinimumWidth(self._min_width)

        # Calculate scrollable range
        max_scroll = max(int(total_duration - chunk_size), 0)

        # Disconnect existing signals to avoid recursion
        try:
            scrollbar.valueChanged.disconnect()
        except TypeError:
            pass  # No connections exist

        # Configure range and step
        scrollbar.setRange(0, max_scroll)
        scrollbar.setPageStep(int(chunk_size))
        scrollbar.setSingleStep(max(1, int(chunk_size / 10)))  # 10% of chunk size

        # Set initial position
        target_value = int(min(max(self._current_offset, 0), max_scroll))
        scrollbar.setValue(target_value)

        # Connect to our unified handler
        scrollbar.valueChanged.connect(self._on_scrollbar_changed)

        self.logger.debug(
            f"Configured scrollbar: range=0-{max_scroll}, chunk={chunk_size}, offset={self._current_offset}"
        )

    def update_offset(self, new_offset: float, emit_signal: bool = True):
        """
        Update current offset and sync scrollbar.

        Args:
            new_offset: New time offset value
            emit_signal: Whether to emit scroll_changed signal
        """
        # Clamp offset to valid range
        max_offset = max(self._total_duration - self._chunk_size, 0)
        self._current_offset = max(0, min(new_offset, max_offset))

        # Update scrollbar without triggering signals
        if self._scrollbar:
            self._scrollbar.blockSignals(True)
            self._scrollbar.setValue(int(self._current_offset))
            self._scrollbar.blockSignals(False)

        # Emit change signal if requested
        if emit_signal:
            self.scroll_changed.emit(self._current_offset)

    def update_chunk_size(self, new_chunk_size: float):
        """Update chunk size and reconfigure scrollbar."""
        self._chunk_size = new_chunk_size

        if self._scrollbar and self._total_duration > 0:
            self.setup_scrollbar(
                self._scrollbar, self._total_duration, self._chunk_size
            )

    def update_duration(self, new_duration: float):
        """Update total duration and reconfigure scrollbar."""
        self._total_duration = new_duration

        if self._scrollbar and self._chunk_size > 0:
            self.setup_scrollbar(
                self._scrollbar, self._total_duration, self._chunk_size
            )

    def handle_wheel_scroll(self, delta: int, scroll_factor: float = 2.0) -> bool:
        """
        Handle mouse wheel scrolling with consistent behavior.

        Args:
            delta: Wheel delta value
            scroll_factor: Seconds per wheel step

        Returns:
            True if scroll was handled, False otherwise
        """
        if self._total_duration <= 0:
            return False

        # Calculate scroll amount
        scroll_amount = (delta / 120.0) * scroll_factor
        new_offset = self._current_offset + scroll_amount

        # Apply limits
        max_offset = max(self._total_duration - self._chunk_size, 0)
        new_offset = max(0, min(new_offset, max_offset))

        # Only update if there's a significant change
        if abs(new_offset - self._current_offset) > 0.1:
            self.update_offset(new_offset, emit_signal=True)
            return True

        return False

    def scroll_to_time(self, target_time: float):
        """Scroll to show a specific time point."""
        # Calculate offset to center the target time
        new_offset = target_time - (self._chunk_size / 2)
        self.update_offset(new_offset, emit_signal=True)

    def scroll_to_start(self):
        """Scroll to the beginning."""
        self.update_offset(0, emit_signal=True)

    def scroll_to_end(self):
        """Scroll to the end."""
        max_offset = max(self._total_duration - self._chunk_size, 0)
        self.update_offset(max_offset, emit_signal=True)

    def _on_scrollbar_changed(self, value: int):
        """Internal handler for scrollbar value changes."""
        new_offset = float(value)

        # Update internal state without triggering scrollbar update
        max_offset = max(self._total_duration - self._chunk_size, 0)
        self._current_offset = max(0, min(new_offset, max_offset))

        # Emit signal for external handlers
        self.scroll_changed.emit(self._current_offset)

    @property
    def current_offset(self) -> float:
        """Get current time offset."""
        return self._current_offset

    @property
    def chunk_size(self) -> float:
        """Get current chunk size."""
        return self._chunk_size

    @property
    def total_duration(self) -> float:
        """Get total duration."""
        return self._total_duration
