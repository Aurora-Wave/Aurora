"""
SelectableViewBox - Custom ViewBox with synchronized region selection and scroll navigation.
Adapted for Aurora PlotContainer architecture.
"""

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from typing import Optional, TYPE_CHECKING

# Avoid circular import
if TYPE_CHECKING:
    from aurora.ui.widgets.plot_container_widget import PlotContainerWidget


class SelectableViewBox(pg.ViewBox):
    """
    Custom ViewBox that supports:
    1. Synchronized region selection across multiple plots in a PlotContainer
    2. Mouse wheel scrolling for temporal navigation
    3. Future: Right-click context menu integration
    """
    
    # Scroll configuration constants
    SCROLL_SENSITIVITY = 5.0    # seconds per wheel notch
    NATURAL_SCROLLING = True    # True = natural, False = traditional
    SCROLL_THRESHOLD = 0.1      # minimum threshold to trigger scroll
    
    # Signals
    region_selected = Signal(float, float)  # start_time, end_time
    region_cleared = Signal()
    
    def __init__(self, plot_container: 'PlotContainerWidget', plot_index: int):
        """
        Args:
            plot_container: Reference to the PlotContainerWidget that contains this plot
            plot_index: Index of this plot within the container
        """
        super().__init__()
        
        self.plot_container = plot_container
        self.plot_index = plot_index
        
        # Set default mouse mode to pan
        self.setMouseMode(self.PanMode)
        
        # Selection state
        self._dragging = False
        self._drag_start = None
        
        # Mouse tracking for wheel events
        self._mouse_inside = False
        
        # Enable mouse tracking for better interaction
        self.setMouseEnabled(x=True, y=True)
        
        # Enable hover events for mouse tracking
        self.setAcceptHoverEvents(True)

    def _get_scroll_amount(self, delta):
        """
        Calculate scroll amount based on wheel delta.
        
        Args:
            delta: Wheel event delta
            
        Returns:
            float: Scroll amount in seconds
        """
        # Calculate base scroll amount (delta is typically 120 for one notch)
        scroll_amount = (delta / 120.0) * self.SCROLL_SENSITIVITY
        
        # Apply natural scrolling direction
        if self.NATURAL_SCROLLING:
            scroll_amount = -scroll_amount
            
        return scroll_amount

    def _should_scroll(self, scroll_amount):
        """Check if scroll amount exceeds minimum threshold."""
        return abs(scroll_amount) >= self.SCROLL_THRESHOLD

    def hoverEvent(self, ev):
        """Handle mouse hover events to track mouse position."""
        if ev.isExit():
            self._mouse_inside = False
        else:
            self._mouse_inside = True
        # ViewBox doesn't have hoverEvent, so we don't call super()

    def wheelEvent(self, ev, axis=None):
        """
        Handle mouse wheel for synchronized temporal navigation.
        Only active when mouse is inside this ViewBox.
        """
        # Only handle wheel events if mouse is inside this ViewBox
        if not self._mouse_inside:
            ev.ignore()
            return
            
        # Check if PlotContainer has navigation controls
        if not hasattr(self.plot_container, 'position_slider') or self.plot_container.position_slider is None:
            ev.ignore()
            return
        
        # Calculate scroll amount
        delta = ev.delta()
        scroll_amount = self._get_scroll_amount(delta)
        
        # Check minimum threshold
        if not self._should_scroll(scroll_amount):
            ev.accept()
            return
        
        # Get current time position
        current_time = self.plot_container.start_time
        new_time = current_time + scroll_amount
        
        # Apply bounds (0 to max duration - chunk_size)
        max_time = max(0, self.plot_container.duration - self.plot_container.chunk_size)
        new_time = max(0, min(max_time, new_time))
        
        # Only update if there's significant change
        if abs(new_time - current_time) >= 0.1:
            # Update via PlotContainer's slider
            self.plot_container.position_slider.setValue(int(new_time))
        
        ev.accept()

    def mouseDragEvent(self, ev, axis=None):
        """
        Handle mouse drag for synchronized region selection across all plots.
        """
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return
        
        if ev.isStart():
            self._start_region_selection(ev)
            
        elif ev.isFinish():
            self._finish_region_selection(ev)
            
        elif self._dragging and self._drag_start is not None:
            self._update_region_selection(ev)
            
        ev.accept()

    def _start_region_selection(self, ev):
        """Start region selection across all plots."""
        self._dragging = True
        self._drag_start = self.mapToView(ev.buttonDownPos())
        
        # Clear existing regions in all plots
        self.plot_container.clear_all_regions()
        
        # Create new regions in all plots
        start_x = self._drag_start.x()
        self.plot_container.create_regions_at([start_x, start_x])

    def _finish_region_selection(self, ev):
        """Finish region selection and emit signal."""
        if self._dragging and self._drag_start is not None:
            end_pos = self.mapToView(ev.pos())
            start_time = min(self._drag_start.x(), end_pos.x())
            end_time = max(self._drag_start.x(), end_pos.x())
            
            # Only emit if region has meaningful size (> 0.1 seconds)
            if abs(end_time - start_time) > 0.1:
                self.region_selected.emit(start_time, end_time)
        
        self._dragging = False
        self._drag_start = None

    def _update_region_selection(self, ev):
        """Update region selection during drag."""
        current_pos = self.mapToView(ev.pos())
        start_x = self._drag_start.x()
        end_x = current_pos.x()
        
        # Update all regions in PlotContainer
        self.plot_container.update_all_regions([start_x, end_x])

    def mouseClickEvent(self, ev):
        """
        Handle mouse clicks:
        - Left click: Always clear all regions (unless we just finished dragging)
        - Right click: Future context menu integration
        """
        if ev.button() == Qt.LeftButton:
            # Always clear regions on any left click (unless drag just finished)
            if not self._dragging:
                self.plot_container.clear_all_regions()
                self.region_cleared.emit()
                ev.accept()
                return
        
        # Let parent handle other cases
        super().mouseClickEvent(ev)

    def get_selected_region(self) -> Optional[tuple]:
        """
        Get currently selected region coordinates.
        
        Returns:
            tuple: (start_time, end_time) or None if no region selected
        """
        return self.plot_container.get_current_region()

    def clear_region(self):
        """Clear region selection in this viewbox."""
        # Delegate to container for synchronized clearing
        self.plot_container.clear_all_regions()