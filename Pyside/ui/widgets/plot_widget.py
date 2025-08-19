"""
PlotContainerWidget - Sistema modular de plots para Aurora2.0
Contenedor reutilizable que puede especializarse por herencia para diferentes tabs.
"""

import sys
import os

if __name__ == "__main__":
    # Ensure we're using Aurora2.0 imports, not Aurora1
    aurora2_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app/Pyside"
    if aurora2_path not in sys.path:
        sys.path.insert(0, aurora2_path)  # Insert at beginning to take priority
    
    # Also add the parent Aurora_app directory
    aurora2_app_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app"
    if aurora2_app_path not in sys.path:
        sys.path.insert(0, aurora2_app_path)
    
    # Remove any Aurora1 paths that might conflict
    aurora1_paths = [p for p in sys.path if "Aurora/Aurora_app" in p or "Aurora\\Aurora_app" in p]
    for path in aurora1_paths:
        sys.path.remove(path)

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSplitter,
    QLabel, QSpinBox, QScrollBar, QPushButton, QFrame, 
    QColorDialog, QMenu, QComboBox, QCheckBox, QSizePolicy, QApplication,
    QSlider
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint, QEvent, QTimer
from PySide6.QtGui import QDrag, QPixmap, QPainter, QAction
from typing import List, Dict, Optional, Tuple
from Pyside.core.comments import EMSComment
import numpy as np
import os

from Pyside.ui.managers.plot_style_manager import plot_style_manager, PlotStyle, get_plot_style_manager
from Pyside.ui.managers.comment_marker_manager import get_comment_marker_manager
from Pyside.core import get_user_logger
from Pyside.core.comments import EMSComment


class CustomPlot(QWidget):
    """Plot individual personalizable con integración al PlotStyleManager."""
    
    # Signals for operations
    remove_requested = Signal(object)  # self
    color_changed = Signal(object, str)  # self, new_color
    style_changed = Signal(object)  # self
    
    def __init__(self, signal_name: str, custom_style: Optional[PlotStyle] = None):
        super().__init__()
        self.signal_name = signal_name
        self.custom_style = custom_style
        self.current_style = plot_style_manager.get_style_for_signal(signal_name, custom_style)
        self.drag_start_position = None
        
        # Logger
        self.logger = get_user_logger(f"DraggablePlot-{signal_name}")
        
        # Comment visualization
        self.current_file_path = None
        self.comments_enabled = False
        self.comment_markers = []  # List of pg.InfiniteLine markers
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        self.setup_ui()
        
    @property
    def min_height(self):
        """Get height from style manager"""
        return getattr(self.current_style, 'min_plot_height', 150)
    
    def minimumSizeHint(self):
        """Generic size hint for QSplitter - enforces minimum height."""
        from PySide6.QtCore import QSize
        return QSize(200, self.min_height)  # Generic: minimum width + required height
        
    def setup_ui(self):
        """Setup the UI for the individual plot widget."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # ========= Control area (left side) - fixed width =========
        controls_frame = QFrame()
        controls_frame.setFixedWidth(100)
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(2, 2, 2, 2)
        
        # Drag handle
        self.drag_label = QLabel("≡≡≡")
        self.drag_label.setAlignment(Qt.AlignCenter)
        self.drag_label.setToolTip("Drag to reorder")
        self.drag_label.setMaximumHeight(15)
        
        # FIXME Agregar lista desplegable para cambiar la señal
        # Signal name label (clickable for color change)
        self.signal_label = QLabel(self.signal_name)
        self.signal_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; color: {self.current_style.pen_color}; "
            "border: 1px solid transparent; padding: 1px; }"
            "QLabel:hover { border: 1px solid #666; background-color: #333; }"
        )
        # FIXME: Averiguar si hace falto settear un tope maximo
        #self.signal_label.setMaximumHeight(600)
        self.signal_label.setToolTip("Click to change color")
        self.signal_label.mousePressEvent = self.on_label_clicked
        
        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(30, 20)
        self.btn_remove.setStyleSheet("QPushButton { color: red; }")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        self.btn_remove.setToolTip("Remove plot")
        
        controls_layout.addWidget(self.drag_label)
        controls_layout.addWidget(self.signal_label)
        controls_layout.addWidget(self.btn_remove)
        controls_layout.addStretch()
        # ========= Control area (left side) END =========

        # ========= Plot widget (right side) =========
        self.plot_widget = pg.PlotWidget()

        # Configure plot using centralized height management
        self.configure_plot()
        
        # Disable PyQtGraph context menu and setup custom one
        self.plot_widget.getViewBox().setMenuEnabled(False)
        self.setup_context_menu()
        
        # Add to layout
        layout.addWidget(controls_frame)
        layout.addWidget(self.plot_widget)
        
    def configure_plot(self):
        """Configure plot using centralized PlotStyleManager."""
        # Use PlotStyleManager for complete configuration
        plot_style_manager.configure_plot_widget(
            self.plot_widget, 
            self.signal_name, 
            self.current_style
        )
        
        # Set initial signal label (will be updated by container with units if available)
        self.plot_widget.setLabel("left", self.signal_name)

        # Apply to CustomPlot container
        self.setMinimumHeight(self.min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        print(f"[DEBUG] CustomPlot {self.signal_name} minimum height set to: {self.min_height}px")
        
        # Create curve with style from manager
        pen = plot_style_manager.create_plot_pen(self.signal_name, self.custom_style)
        self.curve = self.plot_widget.plot(pen=pen, name=self.signal_name)
        
        self.logger.debug(f"Plot configured for {self.signal_name} using PlotStyleManager")
        
    def setup_context_menu(self):
        """Setup custom context menu for plot."""
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, position):
        """Show custom context menu."""
        menu = QMenu(self)
        
        # Color action
        color_action = QAction("Change Color", self)
        color_action.triggered.connect(self.change_color)
        menu.addAction(color_action)
        
        # Remove action
        remove_action = QAction("Remove Plot", self)
        remove_action.triggered.connect(lambda: self.remove_requested.emit(self))
        menu.addAction(remove_action)
        
        # Show menu
        global_pos = self.plot_widget.mapToGlobal(position)
        menu.exec(global_pos)
        
    def on_label_clicked(self, event):
        """Handle signal label click for color change."""
        if event.button() == Qt.LeftButton:
            self.change_color()
            
    def change_color(self):
        """Open color dialog and change plot color."""
        color_dialog = QColorDialog(self)
        color_dialog.setCurrentColor(self.current_style.pen_color)
        
        if color_dialog.exec():
            new_color = color_dialog.currentColor().name()
            self.update_color(new_color)
            self.color_changed.emit(self, new_color)
            
    def update_color(self, color: str):
        """Update plot color."""
        # Update style manager
        plot_style_manager.update_signal_color(self.signal_name, color)
        
        # Update current style
        self.current_style = plot_style_manager.get_style_for_signal(self.signal_name)
        
        # Update UI elements
        self.signal_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; color: {color}; "
            "border: 1px solid transparent; padding: 1px; }"
            "QLabel:hover { border: 1px solid #666; background-color: #333; }"
        )
        
        # Update plot curve using style manager
        pen = plot_style_manager.create_plot_pen(self.signal_name, self.custom_style)
        self.curve.setPen(pen)
        
    # Drag and Drop Implementation
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.position().toPoint()
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
            
        if not self.drag_start_position:
            return
            
        if ((event.position().toPoint() - self.drag_start_position).manhattanLength() < 
            QApplication.startDragDistance()):
            return
            
        self.start_drag()
        
    def start_drag(self):
        """Start drag operation."""
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText(f"plot:{self.signal_name}")
        drag.setMimeData(mimeData)
        
        # Create drag pixmap
        pixmap = QPixmap(self.size())
        painter = QPainter(pixmap)
        self.render(painter, QPoint(), self.rect())
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.drag_start_position)
        
        # Execute drag
        drag.exec(Qt.MoveAction)
    

    def refresh_min_height(self, new_min: int):
        """Refresh minimum height when style manager updates."""
        # Update current_style to get latest state from manager (includes user modifications)
        self.current_style = plot_style_manager.get_style_for_signal(self.signal_name, self.custom_style)
        
        # Update container minimum height
        self.setMinimumHeight(self.min_height)
        
        # Force Qt to recalculate size hints
        self.updateGeometry()
        
        self.logger.debug(f"Refreshed {self.signal_name} minimum height to: {self.min_height}px")
    
    def _on_color_changed(self, signal_name: str, new_color: str):
        """Handle color change signal from style manager."""
        if signal_name == self.signal_name:
            # Update label color
            self.signal_label.setStyleSheet(
                f"QLabel {{ font-weight: bold; color: {new_color}; "
                "border: 1px solid transparent; padding: 1px; }"
                "QLabel:hover { border: 1px solid #666; background-color: #333; }"
            )
            
            # Update plot curve
            pen = plot_style_manager.create_plot_pen(self.signal_name, self.custom_style)
            self.curve.setPen(pen)
    
    # ========= Comment Integration =========
    
    def enable_comments(self, file_path: str = None, enable: bool = True):
        """Enable or disable comment visualization for this plot."""
        if enable and file_path and not self.comments_enabled:
            # Connect to global comment manager signals
            from Pyside.core.comments import get_comment_manager
            comment_manager = get_comment_manager()
            
            comment_manager.comment_added.connect(self._on_comment_added)
            comment_manager.comment_updated.connect(self._on_comment_updated)
            comment_manager.comment_removed.connect(self._on_comment_removed)
            comment_manager.comments_loaded.connect(self._on_comments_loaded)
            
            self.current_file_path = file_path
            self.comments_enabled = True
            
            # Load existing comments
            self._load_existing_comments()
            
            self.logger.debug(f"Enabled comments for {self.signal_name} with file {file_path}")
            
        elif not enable and self.comments_enabled:
            # Disconnect from signals
            from Pyside.core.comments import get_comment_manager
            comment_manager = get_comment_manager()
            
            try:
                comment_manager.comment_added.disconnect(self._on_comment_added)
                comment_manager.comment_updated.disconnect(self._on_comment_updated)
                comment_manager.comment_removed.disconnect(self._on_comment_removed)
                comment_manager.comments_loaded.disconnect(self._on_comments_loaded)
            except (RuntimeError, TypeError):
                pass  # Signals may not be connected
            
            # Clear all markers
            self.hide_comment_markers()
            self.current_file_path = None
            self.comments_enabled = False
            
            self.logger.debug(f"Disabled comments for {self.signal_name}")
    
    def _load_existing_comments(self):
        """Load existing comments from DataManager and display them."""
        if not self.current_file_path or not self.comments_enabled:
            return
            
        try:
            # Get comments from DataManager through the global comment manager's data manager
            from Pyside.core.comments import get_comment_manager
            comment_manager = get_comment_manager()
            
            if comment_manager._data_manager and self.current_file_path:
                comments = comment_manager._data_manager.get_comments(self.current_file_path)
                self.show_comment_markers(comments)
                self.logger.debug(f"Loaded {len(comments)} existing comments for {self.signal_name}")
        except Exception as e:
            self.logger.error(f"Error loading existing comments: {e}")
    
    def show_comment_markers(self, comments: List[EMSComment], time_range: Tuple[float, float] = None):
        """Show comment markers on this plot."""
        if not self.comments_enabled:
            return
            
        # Clear existing markers first
        self.hide_comment_markers()
        
        plot_item = self.plot_widget.getPlotItem()
        
        for comment in comments:
            # Filter by time range if provided
            if time_range:
                start_time, end_time = time_range
                if not (start_time <= comment.time <= end_time):
                    continue
            
            # Create marker
            marker = self._create_comment_marker(comment)
            if marker:
                plot_item.addItem(marker)
                self.comment_markers.append(marker)
        
        self.logger.debug(f"Showing {len(self.comment_markers)} comment markers on {self.signal_name}")
    
    def hide_comment_markers(self):
        """Hide all comment markers from this plot."""
        plot_item = self.plot_widget.getPlotItem()
        
        for marker in self.comment_markers:
            try:
                plot_item.removeItem(marker)
            except (RuntimeError, AttributeError):
                pass  # Marker may already be removed
        
        self.comment_markers.clear()
        self.logger.debug(f"Hidden comment markers on {self.signal_name}")
    
    def update_comment_markers(self, comments: List[EMSComment], time_range: Tuple[float, float] = None):
        """Update comment markers (convenience method)."""
        if self.comments_enabled:
            self.show_comment_markers(comments, time_range)
    
    def _create_comment_marker(self, comment: EMSComment) -> pg.InfiniteLine:
        """Create a vertical marker line for a comment."""
        try:
            # Choose style based on comment type
            if comment.user_defined:
                # User comment style (green)
                pen = pg.mkPen("#00ff88", width=2, style=pg.QtCore.Qt.DashLine)
                label_opts = {
                    "position": 0.85,
                    "color": (255, 255, 255),
                    "fill": (0, 100, 0, 180),
                    "border": (0, 255, 136, 255),
                    "anchor": (0, 1),
                }
            else:
                # System comment style (orange)
                pen = pg.mkPen("#ff9500", width=1, style=pg.QtCore.Qt.DashLine)
                label_opts = {
                    "position": 0.9,
                    "color": (255, 255, 255),
                    "fill": (80, 40, 0, 180),
                    "border": (255, 149, 0, 255),
                    "anchor": (0, 1),
                }
            
            # Truncate long labels
            label_text = comment.text
            if len(label_text) > 50:
                label_text = label_text[:47] + "..."
            
            # Create marker
            marker = pg.InfiniteLine(
                pos=comment.time,
                angle=90,
                pen=pen,
                label=label_text,
                labelOpts=label_opts,
            )
            
            # Set z-value (user comments on top)
            marker.setZValue(2 if comment.user_defined else 1)
            
            return marker
            
        except Exception as e:
            self.logger.error(f"Error creating comment marker: {e}")
            return None
    
    def _on_comment_added(self, file_path: str, comment: EMSComment):
        """Handle comment added signal."""
        if file_path == self.current_file_path and self.comments_enabled:
            self._load_existing_comments()  # Refresh all markers
    
    def _on_comment_updated(self, file_path: str, comment: EMSComment):
        """Handle comment updated signal."""
        if file_path == self.current_file_path and self.comments_enabled:
            self._load_existing_comments()  # Refresh all markers
    
    def _on_comment_removed(self, file_path: str, comment_id: str):
        """Handle comment removed signal."""
        if file_path == self.current_file_path and self.comments_enabled:
            self._load_existing_comments()  # Refresh all markers
    
    def _on_comments_loaded(self, file_path: str, comments: List[EMSComment]):
        """Handle comments loaded signal."""
        if file_path == self.current_file_path and self.comments_enabled:
            self.show_comment_markers(comments)
        

class PlotContainerWidget(QWidget):
    """
    Base container for plots with standard controls.
    Can be specialized by inheritance for different tabs.
    """
    
    # Signals
    time_changed = Signal(float)  # start_time
    chunk_size_changed = Signal(float)  # chunk_size
    scroll_changed = Signal(float)  # scroll_position
    plots_reordered = Signal(list)  # new_order
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_user_logger("PlotContainer")
        
        # State
        self.start_time = 0.0
        self.chunk_size = 60.0
        self.duration = 100.0
        self.target_signals: List[str] = []
        self.plots: List[CustomPlot] = []
        
        # UI Components
        self.controls_widget = None
        self.plots_splitter = None
        self.scroll_area = None
        
        # Comment Management
        self.tab_id = f"plot_container_{id(self)}"  # Unique tab identifier
        self.comment_manager = get_comment_marker_manager()
        
        # Enable drop in container
        self.setAcceptDrops(True)
        
        self.setup_ui()
        
        # Connect to style manager for global height changes
        # Ensure plot_style_manager is properly initialized
        style_manager = get_plot_style_manager()
        style_manager.minHeightChanged.connect(self._on_global_height_changed)
        
        # Install event filter to detect resize events
        self.scroll_area.installEventFilter(self)
        
    def setup_ui(self):
        """Setup the main UI structure."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Controls area (can be customized by subclasses)
        self.controls_widget = self.create_controls()
        main_layout.addWidget(self.controls_widget)
        
        # Initialize time label after controls are created
        if hasattr(self, 'time_label'):
            self.time_label.setText(f"{int(self.start_time)}.0s")
        
        # Plots area with scroll
        self.setup_plots_area()
        main_layout.addWidget(self.scroll_area)
        
    def create_controls(self) -> QWidget:
        """
        Create standard controls. Override in subclasses to customize.
        """
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(controls_frame)
        
        # Start time control
        layout.addWidget(QLabel("Start (s):"))
        self.start_spinbox = QSpinBox()
        self.start_spinbox.setRange(0, 0)
        self.start_spinbox.setValue(int(self.start_time))
        self.start_spinbox.valueChanged.connect(self._on_start_time_changed)
        layout.addWidget(self.start_spinbox)
        
        # Chunk size control
        layout.addWidget(QLabel("Chunk (s):"))
        self.chunk_spinbox = QSpinBox()
        self.chunk_spinbox.setRange(1, 3600)
        self.chunk_spinbox.setValue(int(self.chunk_size))
        self.chunk_spinbox.valueChanged.connect(self._on_chunk_size_changed)
        layout.addWidget(self.chunk_spinbox)
        
        # Temporal navigation slider - more prominent
        layout.addWidget(QLabel("Navigate:"))
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, int(self.duration - self.chunk_size))
        self.position_slider.setValue(int(self.start_time))
        self.position_slider.setMinimumWidth(200)  # Make it more prominent
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #2b2b2b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4A90E2;
                border: 1px solid #2b2b2b;
                width: 20px;
                height: 14px;
                border-radius: 2px;
                margin: -3px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #5DA3F5;
            }
        """)
        self.position_slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.position_slider)
        
        # Current time display
        self.time_label = QLabel("0.0s")
        self.time_label.setFixedWidth(50)
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)
        
        # Previous/Next buttons
        self.btn_prev = QPushButton("←")
        self.btn_prev.clicked.connect(self.go_previous_chunk)
        layout.addWidget(self.btn_prev)
        
        self.btn_next = QPushButton("→")
        self.btn_next.clicked.connect(self.go_next_chunk)
        layout.addWidget(self.btn_next)
        
        
        layout.addStretch()
        
        return controls_frame
        
    def setup_plots_area(self):
        """Setup plots area with QSplitter for automatic space distribution."""
        # Create scroll area
        self.scroll_area = QScrollArea()
        # Enable resizable for automatic size management
        self.scroll_area.setWidgetResizable(True)
        #self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #FIXME: Sigue funcionando si lo elimino
        #self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create QSplitter for plots (vertical distribution)
        self.plots_splitter = QSplitter(Qt.Vertical)
        self.plots_splitter.setChildrenCollapsible(False)  # Prevent plot collapsing
        self.plots_splitter.setHandleWidth(3)  # Thin resize handles
        
        # Set splitter in scroll area
        self.scroll_area.setWidget(self.plots_splitter)
        
        # Manual resize detection
        self._user_resizing = False
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_timeout)
        
        # Connect splitter signal for manual resize detection
        self.plots_splitter.splitterMoved.connect(self._on_splitter_moved)
        
    def set_signals(self, signal_names: List[str]):
        """Set the signals to display."""
        self.target_signals = signal_names
        self.create_plots()
        
    def create_plots(self):
        """Create plot widgets for target signals."""
        # Clear existing plots
        self.clear_plots()
        
        self.logger.debug(f"Creating plots for signals: {self.target_signals}")
        
        # Create new plots
        for signal_name in self.target_signals:
            plot = CustomPlot(signal_name)
            
            # Configure plot for splitter
            self._configure_plot_for_splitter(plot)
            
            # Connect signals
            plot.remove_requested.connect(self.remove_plot)
            plot.color_changed.connect(self.on_plot_color_changed)
            get_plot_style_manager().minHeightChanged.connect(plot.refresh_min_height)  # connect global min-height signal
            
            # Add to splitter
            self.plots.append(plot)
            self.plots_splitter.addWidget(plot)
            
            # Set stretch factor for equal distribution
            idx = self.plots_splitter.count() - 1
            self.plots_splitter.setStretchFactor(idx, 1)
            
            # Debug: Check splitter state after adding plot
            splitter_size = self.plots_splitter.size()
            plot_sizes = [self.plots_splitter.widget(i).size() for i in range(self.plots_splitter.count())]
            self.logger.debug(f"Created and added plot for {signal_name} to splitter")
            self.logger.debug(f"  - Splitter size: {splitter_size.width()}x{splitter_size.height()}px")
            self.logger.debug(f"  - Plot sizes in splitter: {[(s.width(), s.height()) for s in plot_sizes]}")
        
        self.logger.info(f"Created {len(self.plots)} plots total")
        
        # CRITICAL: Calculate and set total splitter size for scroll area
        self._update_splitter_size()
    
    def _configure_plot_for_splitter(self, plot: CustomPlot):
        """Configure plot for optimal behavior in QSplitter."""
        # Unify size policy: allow full expansion
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # allow full expansion
        
        min_height = plot.minimumHeight()
        size_policy = plot.sizePolicy()
        
        self.logger.debug(f"Plot {plot.signal_name} ready for splitter:")
        self.logger.debug(f"  - minimumHeight(): {min_height}px")
        self.logger.debug(f"  - sizePolicy: H={size_policy.horizontalPolicy()}, V={size_policy.verticalPolicy()}")
        
    def clear_plots(self):
        """Clear all existing plots."""
        for plot in self.plots:
            plot.setParent(None)  # Remove from splitter
            plot.deleteLater()
        self.plots.clear()
        
    def remove_plot(self, plot: CustomPlot):
        """Remove a plot from the container."""
        if plot in self.plots:
            # Unregister from comments first
            plot.unregister_from_comments(self.tab_id)
            
            self.plots.remove(plot)
            plot.setParent(None)  # Remove from splitter
            plot.deleteLater()
            
            # Update target signals
            if plot.signal_name in self.target_signals:
                self.target_signals.remove(plot.signal_name)
            
            self.logger.debug(f"Removed plot {plot.signal_name} from splitter")
            
            # Update splitter size after removing plot
            self._update_splitter_size()
            
    def add_plot(self, signal_name: str):
        """Add a new plot for the given signal."""
        if signal_name not in self.target_signals:
            self.target_signals.append(signal_name)
            
            plot = CustomPlot(signal_name)
            
            # Configure for splitter
            self._configure_plot_for_splitter(plot)
            
            # Connect signals
            plot.remove_requested.connect(self.remove_plot)
            plot.color_changed.connect(self.on_plot_color_changed)
            get_plot_style_manager().minHeightChanged.connect(plot.refresh_min_height)  # connect global min-height signal
            
            # Register for comments
            plot.register_for_comments(self.tab_id)
            
            # Add to splitter
            self.plots.append(plot)
            self.plots_splitter.addWidget(plot)
            
            # Set stretch factor for equal distribution
            idx = self.plots_splitter.count() - 1
            self.plots_splitter.setStretchFactor(idx, 1)
            
            self.logger.debug(f"Added plot {signal_name} to splitter")
            
            # Update splitter size after adding plot
            self._update_splitter_size()
            
                
    def on_plot_color_changed(self, plot: CustomPlot, new_color: str):
        """Handle plot color change."""
        self.logger.debug(f"Plot {plot.signal_name} color changed to {new_color}")
        
    def set_duration(self, duration: float):
        """Set the total duration and update controls."""
        self.duration = duration
        self.start_spinbox.setRange(0, int(duration - self.chunk_size))
        self.position_slider.setRange(0, int(duration - self.chunk_size))
        
    def _on_start_time_changed(self, value: int):
        """Handle start time change."""
        self.start_time = float(value)
        self.position_slider.setValue(value)
        
        # Update time label
        if hasattr(self, 'time_label'):
            self.time_label.setText(f"{value}.0s")
        
        self.time_changed.emit(self.start_time)
        
    def _on_chunk_size_changed(self, value: int):
        """Handle chunk size change."""
        self.chunk_size = float(value)
        self.set_duration(self.duration)  # Update ranges
        self.chunk_size_changed.emit(self.chunk_size)
        
    def _on_slider_changed(self, value: int):
        """Handle slider position change."""
        self.start_time = float(value)
        self.start_spinbox.setValue(value)
        
        # Update time label
        if hasattr(self, 'time_label'):
            self.time_label.setText(f"{value}.0s")
        
        self.time_changed.emit(self.start_time)
        
    def go_previous_chunk(self):
        """Navigate to previous chunk."""
        new_start = max(0, self.start_time - self.chunk_size)
        self.start_spinbox.setValue(int(new_start))
        
    def go_next_chunk(self):
        """Navigate to next chunk."""
        max_start = self.duration - self.chunk_size
        new_start = min(max_start, self.start_time + self.chunk_size)
        self.start_spinbox.setValue(int(new_start))
    
        
    def get_plot_by_signal(self, signal_name: str) -> Optional[CustomPlot]:
        """Get plot widget for specific signal."""
        for plot in self.plots:
            if plot.signal_name == signal_name:
                return plot
        return None
        
    def update_plot_data(self, signal_name: str, time_data: np.ndarray, y_data: np.ndarray):
        """Update data for specific plot."""
        plot = self.get_plot_by_signal(signal_name)
        if plot:
            plot.curve.setData(time_data, y_data)
    
    # Drag and Drop Implementation for Plot Reordering
    def dragEnterEvent(self, event):
        """Handle drag enter for plot reordering."""
        if (event.mimeData().hasText() and 
            event.mimeData().text().startswith("plot:")):
            event.acceptProposedAction()
            self.logger.debug("Drag enter accepted for plot reordering")
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        """Handle drag move for plot reordering."""
        if (event.mimeData().hasText() and 
            event.mimeData().text().startswith("plot:")):
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        """Handle drop for plot reordering in splitter."""
        if not (event.mimeData().hasText() and 
                event.mimeData().text().startswith("plot:")):
            event.ignore()
            return
            
        # Extract signal name from drag data
        drag_text = event.mimeData().text()
        signal_name = drag_text.replace("plot:", "")
        
        # Find the dragged plot
        dragged_plot = self.get_plot_by_signal(signal_name)
        if not dragged_plot:
            event.ignore()
            return
        
        # Find drop position in splitter
        drop_position = event.position()
        target_index = self._get_drop_index(drop_position)
        
        # Reorder plot in splitter
        self._reorder_plot_in_splitter(dragged_plot, target_index)
        
        event.acceptProposedAction()
        self.logger.debug(f"Plot {signal_name} reordered to index {target_index}")
        
        # Emit reorder signal
        new_order = [plot.signal_name for plot in self.plots]
        self.plots_reordered.emit(new_order)
    
    def _get_drop_index(self, drop_position) -> int:
        """Calculate target index based on drop position with precision."""
        # Convert coordinates to splitter coordinate system (works while scrolled)
        splitter_pos = self.plots_splitter.mapFrom(self, drop_position)
        drop_y = splitter_pos.y()
        
        if not self.plots:
            return 0
        
        # Compare drop_position.y() with widget.geometry() borders for precision
        cumulative_y = 0
        for i, plot in enumerate(self.plots):
            plot_geometry = plot.geometry()
            plot_top = cumulative_y
            plot_bottom = cumulative_y + plot_geometry.height()
            
            # If drop is in upper half of this plot, insert before it
            plot_middle = plot_top + plot_geometry.height() // 2
            if drop_y <= plot_middle:
                return i
            
            cumulative_y = plot_bottom
        
        # If we get here, drop is after all plots
        return len(self.plots)
    
    def _reorder_plot_in_splitter(self, plot: CustomPlot, target_index: int):
        """Reorder plot in splitter and update internal list."""
        # Get current index
        current_index = self.plots.index(plot)
        
        if current_index == target_index:
            return  # No change needed
            
        # Remove from splitter and list
        plot.setParent(None)  # Remove from splitter
        self.plots.remove(plot)
        
        # Insert at target position
        target_index = min(target_index, len(self.plots))  # Clamp again
        self.plots.insert(target_index, plot)
        self.plots_splitter.insertWidget(target_index, plot)
        
        # Restore stretch factors for equal distribution
        for i, current_plot in enumerate(self.plots):
            self.plots_splitter.setStretchFactor(i, 1)
            
        self.logger.debug(f"Reordered plot {plot.signal_name}: {current_index} -> {target_index}")

    def _update_splitter_size(self):
        """Update splitter size to accommodate all minimum heights."""
        if not self.plots:
            return
            
        # Skip update if user is manually resizing
        if getattr(self, '_user_resizing', False):
            self.logger.info("🚫 SKIPPING splitter size update - user is resizing")
            return
            
        # Calculate total minimum height needed
        total_min_height = sum(plot.minimumHeight() for plot in self.plots)
        
        # Add padding for splitter handles
        handle_padding = (len(self.plots) - 1) * self.plots_splitter.handleWidth()
        total_height = total_min_height + handle_padding
        
        # Get available height in scroll area viewport
        viewport_height = self.scroll_area.viewport().height()
        
        self.logger.info(f"Splitter size calculation:")
        self.logger.info(f"  - {len(self.plots)} plots")
        self.logger.info(f"  - Individual minimum heights: {[plot.minimumHeight() for plot in self.plots]}")
        self.logger.info(f"  - Total minimum heights: {total_min_height}px")
        self.logger.info(f"  - Handle padding: {handle_padding}px")
        self.logger.info(f"  - Total required: {total_height}px")
        self.logger.info(f"  - Viewport available: {viewport_height}px")
        
        # CRITICAL: Force splitter to respect minimum heights only when necessary
        if total_height > viewport_height:
            # If total required height > viewport, set minimum but don't force sizes
            self.plots_splitter.setMinimumHeight(total_height)
            
            # Only force sizes if plots are below their minimum
            current_sizes = self.plots_splitter.sizes()
            min_sizes = [plot.minimumHeight() for plot in self.plots]
            
            needs_force = any(current < min_size for current, min_size in zip(current_sizes, min_sizes))
            
            if needs_force:
                QTimer.singleShot(10, lambda: self.plots_splitter.setSizes(min_sizes))
                self.logger.info(f"🔒 FORCED individual sizes: {min_sizes}")
            else:
                self.logger.info(f"✅ Current sizes respect minimums: {current_sizes}")
            
            self.logger.info(f"📏 Set minimum height to {total_height}px (viewport: {viewport_height}px)")
        else:
            # If total required height <= viewport, allow normal distribution
            self.plots_splitter.setMinimumHeight(total_min_height)
            self.logger.info(f"✅ Normal distribution: {total_height}px fits in viewport {viewport_height}px")
        
        # Force updates
        self.scroll_area.updateGeometry()
        self.plots_splitter.updateGeometry()
        
        # Additional force update for the scroll area widget
        if hasattr(self.scroll_area, 'widget') and self.scroll_area.widget():
            self.scroll_area.widget().updateGeometry()
    
    def _on_global_height_changed(self, new_min: int):
        """Handle global minimum height change from style manager."""
        self.logger.info(f"Global minimum height changed to {new_min}px, updating splitter size")
        # The individual plots will have already updated their minimum heights
        # Now we need to update the splitter total size
        self._update_splitter_size()
    
    def _on_splitter_moved(self, pos: int, index: int):
        """Handle splitter moved by user."""
        self._user_resizing = True
        self._resize_timer.stop()
        self._resize_timer.start(500)  # 500ms timeout after user stops resizing
        
        # CRITICAL: Remove ALL constraints during user resize
        self.plots_splitter.setMinimumHeight(0)
        
        # Also remove individual plot minimum heights temporarily
        for plot in self.plots:
            plot.setMinimumHeight(0)
        
        # Get current sizes to see what's happening
        current_sizes = self.plots_splitter.sizes()
        
        self.logger.info(f"🖱️ USER RESIZE: pos={pos}, idx={index}")
        self.logger.info(f"🖱️ Current splitter sizes: {current_sizes}")
        self.logger.info(f"🖱️ Removed all minimum height constraints")
    
    def _on_resize_timeout(self):
        """Called when user stops resizing for timeout period."""
        self._user_resizing = False
        
        # Restore individual plot minimum heights
        for plot in self.plots:
            plot.setMinimumHeight(plot.min_height)
        
        self.logger.info("✅ User finished manual resizing, restoring constraints")
        
        # Restore minimum height constraints after user finishes
        QTimer.singleShot(100, self._update_splitter_size)
    
    def eventFilter(self, obj, event):
        """Event filter to detect scroll area resize events."""
        if obj == self.scroll_area and event.type() == QEvent.Type.Resize:
            # Delay the update slightly to ensure the resize is complete
            QTimer.singleShot(10, self._update_splitter_size)
        return super().eventFilter(obj, event)
    
    # ========= Comment Management for All Plots =========
    
    def enable_comments_for_all_plots(self, file_path: str, enable: bool = True):
        """Enable or disable comment visualization for ALL plots in this container."""
        for plot in self.plots:
            try:
                plot.enable_comments(file_path, enable)
                self.logger.debug(f"{'Enabled' if enable else 'Disabled'} comments for plot {plot.signal_name}")
            except Exception as e:
                self.logger.error(f"Error {'enabling' if enable else 'disabling'} comments for {plot.signal_name}: {e}")
        
        if enable:
            self.logger.info(f"Enabled comments for all {len(self.plots)} plots with file {file_path}")
        else:
            self.logger.info(f"Disabled comments for all {len(self.plots)} plots")
    
    def enable_comments_for_signals(self, file_path: str, signal_names: List[str]):
        """Enable comment visualization for specific signals only."""
        # First disable all comments
        self.disable_all_comments()
        
        # Then enable only for specified signals
        enabled_count = 0
        for plot in self.plots:
            if plot.signal_name in signal_names:
                try:
                    plot.enable_comments(file_path, True)
                    enabled_count += 1
                    self.logger.debug(f"Enabled comments for plot {plot.signal_name}")
                except Exception as e:
                    self.logger.error(f"Error enabling comments for {plot.signal_name}: {e}")
        
        self.logger.info(f"Enabled comments for {enabled_count}/{len(self.plots)} plots: {signal_names}")
    
    def disable_all_comments(self):
        """Disable comment visualization for all plots in this container."""
        for plot in self.plots:
            try:
                plot.enable_comments(None, False)
            except Exception as e:
                self.logger.error(f"Error disabling comments for {plot.signal_name}: {e}")
        
        self.logger.info(f"Disabled comments for all {len(self.plots)} plots")
    
    def update_all_plots_comments(self, comments: List[EMSComment], time_range: Tuple[float, float] = None):
        """Update comment markers for all plots that have comments enabled."""
        updated_count = 0
        for plot in self.plots:
            if plot.comments_enabled:
                try:
                    plot.update_comment_markers(comments, time_range)
                    updated_count += 1
                except Exception as e:
                    self.logger.error(f"Error updating comments for {plot.signal_name}: {e}")
        
        self.logger.debug(f"Updated comments for {updated_count} plots with comments enabled")
    
    def get_comments_enabled_plots(self) -> List[str]:
        """Get list of signal names that have comments enabled."""
        return [plot.signal_name for plot in self.plots if plot.comments_enabled]
    
    def get_comments_status(self) -> Dict[str, bool]:
        """Get comment enabled status for all plots."""
        return {plot.signal_name: plot.comments_enabled for plot in self.plots}



if __name__ == "__main__":
    """
    Debug script para probar el PlotContainerWidget con datos reales.
    Ejecutar: python plot_widget.py
    """
    import sys
    import os
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QHBoxLayout, QPushButton
    
    # CRITICAL: Ensure we're using Aurora2.0 imports, not Aurora1
    aurora2_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app/Pyside"
    if aurora2_path not in sys.path:
        sys.path.insert(0, aurora2_path)  # Insert at beginning to take priority
    
    # Remove any Aurora1 paths that might conflict
    aurora1_paths = [p for p in sys.path if "Aurora/Aurora_app" in p or "Aurora\\Aurora_app" in p]
    for path in aurora1_paths:
        sys.path.remove(path)
    
    from Pyside.data.data_manager import DataManager
    from Pyside.core import get_user_logger
    import numpy as np
    
    
    class DebugMainWindow(QMainWindow):
        """Ventana de debug para probar PlotContainerWidget."""
        
        def __init__(self):
            super().__init__()
            self.data_manager = DataManager()
            self.current_file_path = None
            self.plot_container = None
            self.logger = get_user_logger("PlotDebug")
            
            # Auto-load file and plot immediately
            self.auto_file_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app/uploaded_files/archivo_de_prueba.adicht"
            
            self.setup_ui()
            self.resize(1200, 800)
            self.setWindowTitle("Aurora Plot Widget Debug - Auto Mode")
            
            # Auto load and plot immediately
            self.auto_load_and_plot()
            
        def setup_ui(self):
            """Setup debug UI."""
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            
            # Status label
            self.status_label = QPushButton("Auto-loading...")
            self.status_label.setEnabled(False)
            layout.addWidget(self.status_label)
            
            # Plot container placeholder
            self.plot_area = QWidget()
            layout.addWidget(self.plot_area)
            
        def auto_load_and_plot(self):
            """Auto-load file and plot signals immediately."""
            try:
                self.logger.info(f"Auto-loading file: {self.auto_file_path}")
                self.data_manager.load_file(self.auto_file_path)
                self.current_file_path = self.auto_file_path
                
                # Get available channels
                channels = self.data_manager.get_available_channels(self.auto_file_path)
                self.logger.info(f"Available channels: {channels}")
                
                self.status_label.setText(f"Loaded: {len(channels)} channels available")
                
                # Auto plot signals
                self.plot_signals()
                
            except Exception as e:
                self.logger.error(f"Error auto-loading file: {e}")
                self.status_label.setText(f"ERROR: {str(e)}")
            
        def load_file(self):
            """Load .adicht file using file dialog."""
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select .adicht file", 
                "", 
                "LabChart Files (*.adicht);;All Files (*)"
            )
            
            if file_path:
                try:
                    self.logger.info(f"Loading file: {file_path}")
                    self.data_manager.load_file(file_path)
                    self.current_file_path = file_path
                    
                    # Get available channels
                    channels = self.data_manager.get_available_channels(file_path)
                    self.logger.info(f"Available channels: {channels}")
                    
                    self.btn_plot.setEnabled(True)
                    self.setWindowTitle(f"Aurora Debug - {file_path.split('/')[-1]}")
                    
                except Exception as e:
                    self.logger.error(f"Error loading file: {e}")
                    
        def plot_signals(self):
            """Plot first N signals (60s each)."""
            if not self.current_file_path:
                self.logger.error("No file loaded")
                return
                
            try:
                # Get available channels
                channels = self.data_manager.get_available_channels(self.current_file_path)
                
                # Take first 3 channels for testing (or all if fewer)
                n_plots = 20  # Reduced for testing scroll behavior
                n_channels = min(n_plots, len(channels))
                selected_channels = channels[:n_channels]
                
                self.logger.info(f"Plotting channels: {selected_channels}")
                
                # Create new plot container
                if self.plot_container:
                    self.plot_container.deleteLater()
                    
                self.plot_container = PlotContainerWidget(self)
                
                # Replace plot area
                layout = self.centralWidget().layout()
                layout.removeWidget(self.plot_area)
                self.plot_area.deleteLater()
                self.plot_area = self.plot_container
                layout.addWidget(self.plot_container)
                
                # Set signals in container
                self.plot_container.set_signals(selected_channels)
                
                # Load 60s of data for each signal
                start_time = 0.0
                chunk_size = 60.0
                
                for channel in selected_channels:
                    try:
                        # Get full signal data
                        signal = self.data_manager.get_trace(self.current_file_path, channel)
                        
                        # Calculate samples for 60s chunk
                        samples_per_chunk = int(signal.fs * chunk_size)
                        start_sample = int(signal.fs * start_time)
                        end_sample = min(start_sample + samples_per_chunk, len(signal.data))
                        
                        # Extract 60s chunk
                        chunk_data = signal.data[start_sample:end_sample]
                        
                        # Create time array for the chunk
                        time_data = np.arange(len(chunk_data)) / signal.fs + start_time
                        
                        # Update plot with chunk data
                        self.plot_container.update_plot_data(channel, time_data, chunk_data)
                        
                        self.logger.info(f"Loaded {channel}: {len(chunk_data)}/{len(signal.data)} samples (60s chunk), {signal.fs}Hz")
                        
                    except Exception as e:
                        self.logger.error(f"Error loading signal {channel}: {e}")
                        
                # Update container duration
                self.plot_container.set_duration(chunk_size)
                self.logger.info("Plot container loaded successfully")
                
            except Exception as e:
                self.logger.error(f"Error plotting signals: {e}")
    
    # Create and run debug application
    app = QApplication(sys.argv)
    window = DebugMainWindow()
    window.show()
    
    print("Aurora Plot Widget Debug - Auto Mode")
    print("Loading test file and plotting channels...")
    
    sys.exit(app.exec())