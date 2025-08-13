import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QLabel, QSpinBox, QScrollBar, QPushButton, QFrame, QApplication,
    QColorDialog, QMenu, QComboBox, QCheckBox, QWidgetAction, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag, QPixmap, QPainter, QAction
from typing import List, Dict, Optional
import sys
import numpy as np

try:
    from ..managers.plot_style_manager import plot_style_manager, PlotStyle, ToolbarStyle
except ImportError:
    # For standalone testing
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from managers.plot_style_manager import plot_style_manager, PlotStyle, ToolbarStyle


class DraggablePlotWidget(QWidget):
    """Individual plot widget that can be reordered via drag and drop."""
    
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
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI for the individual plot widget."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Control area (left side) - now with drag handle and controls
        controls_frame = QFrame()
        controls_frame.setFixedWidth(80)
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(2, 2, 2, 2)
        controls_layout.setSpacing(2)
        
        # Drag handle label
        self.drag_label = QLabel("≡≡≡")
        self.drag_label.setAlignment(Qt.AlignCenter)
        self.drag_label.setStyleSheet(
            "QLabel { background-color: #444; color: white; "
            "border: 1px solid #666; padding: 2px; font-weight: bold; }"
        )
        self.drag_label.setToolTip("Drag to reorder")
        self.drag_label.setMaximumHeight(15)
        
        # Signal name label (clickable for color change)
        self.signal_label = QLabel(self.signal_name)
        self.signal_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; color: {self.current_style.pen_color}; "
            "border: 1px solid transparent; padding: 1px; }"
            "QLabel:hover { border: 1px solid #666; background-color: #333; }"
        )
        self.signal_label.setMaximumHeight(20)
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
        
        # Plot widget (right side)
        self.plot_widget = pg.PlotWidget()
        plot_style_manager.configure_plot_widget(self.plot_widget, self.signal_name, self.custom_style)
        
        # Disable default PyQtGraph context menu
        self.plot_widget.getViewBox().setMenuEnabled(False)
        
        # Setup custom context menu for plot
        self.setup_context_menu()
        
        # Store current plot data for replotting
        self.current_x_data = None
        self.current_y_data = None
        
        layout.addWidget(controls_frame)
        layout.addWidget(self.plot_widget)
        
    def set_data(self, x_data, y_data, custom_pen=None):
        """Set data to plot."""
        # Store data for replotting
        self.current_x_data = x_data
        self.current_y_data = y_data
        
        self.plot_widget.clear()
        if custom_pen:
            pen = custom_pen
        else:
            pen = plot_style_manager.create_plot_pen(self.signal_name, self.custom_style)
        self.plot_widget.plot(x_data, y_data, pen=pen)
        
    def clear_plot(self):
        """Clear the plot."""
        self.plot_widget.clear()
        
    def set_x_range(self, x_min: float, x_max: float):
        """Set X-axis range."""
        self.plot_widget.setXRange(x_min, x_max)
        
    def set_y_range(self, y_min: float, y_max: float):
        """Set Y-axis range."""
        self.plot_widget.setYRange(y_min, y_max)
    
    def setup_context_menu(self):
        """Setup custom context menu for plot options."""
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position):
        """Show custom context menu with plot options."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
            }
            QMenu::item {
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #3d3d3d;
            }
        """)
        
        # Styling section
        style_menu = menu.addMenu("Styling")
        
        # Color change action
        color_action = QAction("Change Color...", self)
        color_action.triggered.connect(self.change_color)
        style_menu.addAction(color_action)
        
        # Line width submenu
        width_menu = style_menu.addMenu("Line Width")
        for width in [1, 2, 3, 4, 5]:
            width_action = QAction(f"{width}px", self)
            width_action.triggered.connect(lambda checked, w=width: self.change_line_width(w))
            if width == self.current_style.pen_width:
                width_action.setChecked(True)
            width_menu.addAction(width_action)
        
        # Reset style action
        reset_action = QAction("Reset Style", self)
        reset_action.triggered.connect(self.reset_style)
        style_menu.addAction(reset_action)
        
        menu.addSeparator()
        
        # Zoom section
        zoom_menu = menu.addMenu("Zoom")
        
        # Auto-range actions
        autorange_action = QAction("Auto Range", self)
        autorange_action.triggered.connect(self.auto_range)
        zoom_menu.addAction(autorange_action)
        
        autorange_x_action = QAction("Auto Range X", self)
        autorange_x_action.triggered.connect(self.auto_range_x)
        zoom_menu.addAction(autorange_x_action)
        
        autorange_y_action = QAction("Auto Range Y", self)
        autorange_y_action.triggered.connect(self.auto_range_y)
        zoom_menu.addAction(autorange_y_action)
        
        zoom_menu.addSeparator()
        
        # Zoom presets
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        zoom_menu.addAction(zoom_out_action)
        
        # Enable/disable mouse interaction
        mouse_menu = menu.addMenu("Mouse")
        
        enable_zoom_action = QAction("Enable Zoom", self)
        enable_zoom_action.setCheckable(True)
        enable_zoom_action.setChecked(self.plot_widget.getViewBox().state['mouseEnabled'][0])
        enable_zoom_action.triggered.connect(self.toggle_mouse_zoom)
        mouse_menu.addAction(enable_zoom_action)
        
        enable_pan_action = QAction("Enable Pan", self)
        enable_pan_action.setCheckable(True)
        enable_pan_action.setChecked(self.plot_widget.getViewBox().state['mouseEnabled'][0])
        enable_pan_action.triggered.connect(self.toggle_mouse_pan)
        mouse_menu.addAction(enable_pan_action)
        
        menu.addSeparator()
        
        # Plot management
        remove_action = QAction("Remove Plot", self)
        remove_action.triggered.connect(lambda: self.remove_requested.emit(self))
        menu.addAction(remove_action)
        
        # Show menu
        menu.exec(self.plot_widget.mapToGlobal(position))
    
    def on_label_clicked(self, event):
        """Handle click on signal label to change color."""
        if event.button() == Qt.LeftButton:
            self.change_color()
    
    def change_color(self):
        """Open color dialog to change plot color."""
        current_color = self.current_style.pen_color
        color = QColorDialog.getColor(Qt.white, self, "Choose Plot Color")
        
        if color.isValid():
            color_name = color.name()
            self.update_color(color_name)
    
    def update_color(self, color: str):
        """Update the plot color."""
        plot_style_manager.update_signal_color(self.signal_name, color)
        self.current_style = plot_style_manager.get_style_for_signal(self.signal_name)
        
        # Update label color
        self.signal_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; color: {color}; "
            "border: 1px solid transparent; padding: 1px; }"
            "QLabel:hover { border: 1px solid #666; background-color: #333; }"
        )
        
        # Update plot color if data exists
        if self.current_x_data is not None and self.current_y_data is not None:
            self.replot_data()
        
        # Emit signal for external handling
        self.color_changed.emit(self, color)
    
    def reset_style(self):
        """Reset plot to default style."""
        plot_style_manager.reset_signal_style(self.signal_name)
        self.current_style = plot_style_manager.get_style_for_signal(self.signal_name)
        self.update_color(self.current_style.pen_color)
        self.style_changed.emit(self)
    
    def get_current_color(self) -> str:
        """Get current plot color."""
        return self.current_style.pen_color
    
    # Drag and Drop Implementation
    def mousePressEvent(self, event):
        """Handle mouse press for drag start."""
        if event.button() == Qt.LeftButton:
            # Check if click is on drag handle
            if self.drag_label.geometry().contains(event.position().toPoint()):
                self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if (event.buttons() == Qt.LeftButton and 
            self.drag_start_position is not None and
            (event.position().toPoint() - self.drag_start_position).manhattanLength() >= QApplication.startDragDistance()):
            
            self.start_drag()
        super().mouseMoveEvent(event)
    
    def start_drag(self):
        """Start drag operation."""
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set drag data
        mime_data.setText(f"plot_widget:{self.signal_name}")
        drag.setMimeData(mime_data)
        
        # Create drag pixmap
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.drag_start_position)
        
        # Execute drag
        drag.exec(Qt.MoveAction)
        
        self.drag_start_position = None
    
    def replot_data(self):
        """Replot current data with updated style."""
        if self.current_x_data is not None and self.current_y_data is not None:
            self.set_data(self.current_x_data, self.current_y_data)
    
    def change_line_width(self, width: int):
        """Change line width of the plot."""
        if self.signal_name in plot_style_manager.custom_styles:
            plot_style_manager.custom_styles[self.signal_name].pen_width = width
        else:
            # Create custom style with new width
            base_style = plot_style_manager.get_style_for_signal(self.signal_name)
            new_style = PlotStyle(
                pen_color=base_style.pen_color,
                pen_width=width,
                background_color=base_style.background_color,
                grid_alpha=base_style.grid_alpha,
                grid_enabled=base_style.grid_enabled,
                mouse_x_enabled=base_style.mouse_x_enabled,
                mouse_y_enabled=base_style.mouse_y_enabled,
                plot_height=base_style.plot_height
            )
            plot_style_manager.custom_styles[self.signal_name] = new_style
        
        self.current_style = plot_style_manager.get_style_for_signal(self.signal_name)
        self.replot_data()
        self.style_changed.emit(self)
    
    # Zoom and view methods
    def auto_range(self):
        """Auto-range both X and Y axes."""
        self.plot_widget.autoRange()
    
    def auto_range_x(self):
        """Auto-range X axis only."""
        if self.current_x_data is not None:
            x_min, x_max = float(np.min(self.current_x_data)), float(np.max(self.current_x_data))
            self.plot_widget.setXRange(x_min, x_max)
    
    def auto_range_y(self):
        """Auto-range Y axis only."""
        if self.current_y_data is not None:
            y_valid = self.current_y_data[np.isfinite(self.current_y_data)]
            if len(y_valid) > 0:
                y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                # Add 5% padding
                y_range = y_max - y_min
                if y_range > 0:
                    padding = y_range * 0.05
                    self.plot_widget.setYRange(y_min - padding, y_max + padding)
                else:
                    self.plot_widget.setYRange(y_min - 0.1, y_max + 0.1)
    
    def zoom_in(self):
        """Zoom in by 50%."""
        viewbox = self.plot_widget.getViewBox()
        current_range = viewbox.viewRange()
        
        x_center = (current_range[0][0] + current_range[0][1]) / 2
        y_center = (current_range[1][0] + current_range[1][1]) / 2
        
        x_width = (current_range[0][1] - current_range[0][0]) * 0.5
        y_width = (current_range[1][1] - current_range[1][0]) * 0.5
        
        self.plot_widget.setXRange(x_center - x_width/2, x_center + x_width/2)
        self.plot_widget.setYRange(y_center - y_width/2, y_center + y_width/2)
    
    def zoom_out(self):
        """Zoom out by 50%."""
        viewbox = self.plot_widget.getViewBox()
        current_range = viewbox.viewRange()
        
        x_center = (current_range[0][0] + current_range[0][1]) / 2
        y_center = (current_range[1][0] + current_range[1][1]) / 2
        
        x_width = (current_range[0][1] - current_range[0][0]) * 1.5
        y_width = (current_range[1][1] - current_range[1][0]) * 1.5
        
        self.plot_widget.setXRange(x_center - x_width/2, x_center + x_width/2)
        self.plot_widget.setYRange(y_center - y_width/2, y_center + y_width/2)
    
    def toggle_mouse_zoom(self, enabled: bool):
        """Toggle mouse zoom functionality."""
        current_y_enabled = self.plot_widget.getViewBox().state['mouseEnabled'][1]
        self.plot_widget.setMouseEnabled(x=enabled, y=current_y_enabled)
    
    def toggle_mouse_pan(self, enabled: bool):
        """Toggle mouse pan functionality."""
        # Pan is the same as zoom in PyQtGraph
        self.toggle_mouse_zoom(enabled)


class PlotContainerWidget(QWidget):
    """
    Main container widget for multiple signal visualization.
    Includes top controls and scrollable plot area.
    """
    
    # Main signals
    chunk_changed = Signal(float, float)  # start_time, chunk_size
    signal_added = Signal(str)  # signal_name
    signal_removed = Signal(str)  # signal_name
    
    def __init__(self):
        super().__init__()
        self.plot_widgets: List[DraggablePlotWidget] = []
        self.chunk_size = 60.0  # seconds
        self.start_time = 0.0
        self.total_duration = 0.0
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the main widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create controls layout (like Aurora original)
        self.setup_controls()
        main_layout.addLayout(self.controls_layout)
        
        # Scrollable plot area
        self.setup_plot_area()
        main_layout.addWidget(self.scroll_area)
        
    def setup_controls(self):
        """Setup the controls layout (Aurora original style)."""
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)
        
        self.create_controls()
    
    def create_controls(self):
        """Create standard control widgets (Start, Chunk size, Slider, Dropdown placeholder)."""
        
        # Get controls configuration from PlotStyleManager
        config = plot_style_manager.get_toolbar_style().get_controls_config()
        
        # Add initial spacing
        if config['start_spacing'] > 0:
            self.controls_layout.addSpacing(config['start_spacing'])
        
        # 1. Start time control (always present) - editable
        self.controls_layout.addWidget(QLabel(config['start_label']))
        self.start_time_spinbox = QSpinBox()
        self.start_time_spinbox.setMinimum(0)
        self.start_time_spinbox.setMaximum(0)  # Will be updated when duration is set
        self.start_time_spinbox.setValue(int(self.start_time))
        self.start_time_spinbox.setSuffix(" s")
        self.start_time_spinbox.setMinimumWidth(80)
        self.start_time_spinbox.valueChanged.connect(self.on_start_time_changed)
        self.controls_layout.addWidget(self.start_time_spinbox)
        
        # 2. Chunk size control (always present)
        self.controls_layout.addWidget(QLabel(config['chunk_label']))
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(1)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(int(self.chunk_size))
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.valueChanged.connect(self.on_chunk_size_changed)
        self.controls_layout.addWidget(self.chunk_size_spinbox)
        
        # 3. Position slider (always present)
        self.position_slider = QScrollBar(Qt.Horizontal)
        self.position_slider.setMinimumHeight(20)
        self.position_slider.setMaximumHeight(20)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(1000)
        self.position_slider.setValue(0)
        self.position_slider.valueChanged.connect(self.on_position_changed)
        self.position_slider.setStyleSheet(plot_style_manager.get_toolbar_slider_style())
        self.controls_layout.addWidget(self.position_slider)
        
        # 4. Signals dropdown placeholder (always present, to be replaced)
        self.signals_placeholder = QLabel(config['signals_placeholder'])
        self.signals_placeholder.setStyleSheet(plot_style_manager.get_toolbar_placeholder_style())
        self.controls_layout.addWidget(self.signals_placeholder)
    
    def set_signals_widget(self, signals_widget: QWidget):
        """Replace the signals placeholder with the actual dropdown widget."""
        # Remove placeholder from layout
        self.controls_layout.removeWidget(self.signals_placeholder)
        self.signals_placeholder.setParent(None)
        
        # Add the new signals widget
        self.controls_layout.addWidget(signals_widget)
    
    def add_control_widget(self, widget: QWidget):
        """Add a new control widget to the controls layout."""
        self.controls_layout.addWidget(widget)
        
    def setup_plot_area(self):
        """Setup the scrollable plot area."""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Plot container widget
        self.plots_container = QWidget()
        self.plots_layout = QVBoxLayout(self.plots_container)
        self.plots_layout.setContentsMargins(0, 0, 0, 0)
        self.plots_layout.setSpacing(2)
        self.plots_layout.addStretch()  # Keep plots at top
        
        self.scroll_area.setWidget(self.plots_container)
        
        # Enable drop on the container
        self.plots_container.setAcceptDrops(True)
        self.plots_container.dragEnterEvent = self.dragEnterEvent
        self.plots_container.dragMoveEvent = self.dragMoveEvent
        self.plots_container.dropEvent = self.dropEvent
        
    def add_signal_plot(self, signal_name: str, custom_style: Optional[PlotStyle] = None) -> DraggablePlotWidget:
        """
        Add a new plot for a signal.
        
        Args:
            signal_name: Name of the signal
            plot_height: Plot height in pixels
            
        Returns:
            The created plot widget
        """
        # Check if already exists
        for plot_widget in self.plot_widgets:
            if plot_widget.signal_name == signal_name:
                return plot_widget
        
        # Create new plot widget
        plot_widget = DraggablePlotWidget(signal_name, custom_style)
        
        # Connect signals
        plot_widget.remove_requested.connect(self.remove_plot)
        plot_widget.color_changed.connect(self.on_plot_color_changed)
        plot_widget.style_changed.connect(self.on_plot_style_changed)
        
        # Add to list and layout
        self.plot_widgets.append(plot_widget)
        # Insert before stretch
        self.plots_layout.insertWidget(len(self.plot_widgets) - 1, plot_widget)
        
        # Emit signal
        self.signal_added.emit(signal_name)
        
        return plot_widget
    
    
    def set_signal_data(self, signal_data_dict: Dict[str, Dict]):
        """Set data for multiple signals at once."""
        for signal_name, data in signal_data_dict.items():
            plot_widget = self.get_plot_widget(signal_name)
            if plot_widget:
                plot_widget.set_data(data['time'], data['data'])
                if 'y_range' in data:
                    plot_widget.set_y_range(data['y_range'][0], data['y_range'][1])
    
        
    def remove_signal_plot(self, signal_name: str):
        """Remove a signal plot."""
        for i, plot_widget in enumerate(self.plot_widgets):
            if plot_widget.signal_name == signal_name:
                self.plot_widgets.pop(i)
                self.plots_layout.removeWidget(plot_widget)
                plot_widget.deleteLater()
                self.signal_removed.emit(signal_name)
                break
    
    def on_plot_color_changed(self, plot_widget: DraggablePlotWidget, new_color: str):
        """Handle plot color change."""
        # Refresh plot data with new color if data exists
        pass  # Will be handled by the calling code
    
    def on_plot_style_changed(self, plot_widget: DraggablePlotWidget):
        """Handle plot style change."""
        # Refresh plot configuration
        plot_style_manager.configure_plot_widget(
            plot_widget.plot_widget, 
            plot_widget.signal_name, 
            plot_widget.custom_style
        )
        # Replot data with new style
        plot_widget.replot_data()
            
    def remove_plot(self, plot_widget: DraggablePlotWidget):
        """Remove a plot from the container."""
        self.remove_signal_plot(plot_widget.signal_name)
        
    def get_plot_widget(self, signal_name: str) -> Optional[DraggablePlotWidget]:
        """Get the plot widget for a specific signal."""
        for plot_widget in self.plot_widgets:
            if plot_widget.signal_name == signal_name:
                return plot_widget
        return None
        
    def set_total_duration(self, duration: float):
        """Set total data duration."""
        self.total_duration = duration
        
        # Update slider and start time spinbox
        if duration > 0:
            max_start_time = max(0, duration - self.chunk_size)
            self.position_slider.setMaximum(int(max_start_time))
            self.position_slider.setEnabled(True)
            
            # Update start time spinbox maximum
            self.start_time_spinbox.setMaximum(int(max_start_time))
            self.start_time_spinbox.setEnabled(True)
        else:
            self.position_slider.setMaximum(0)
            self.position_slider.setEnabled(False)
            self.start_time_spinbox.setMaximum(0)
            self.start_time_spinbox.setEnabled(False)
            
    def on_chunk_size_changed(self, new_size: int):
        """Handle chunk size changes."""
        self.chunk_size = float(new_size)
        
        # Update slider and spinbox maximum
        if self.total_duration > 0:
            max_start_time = max(0, self.total_duration - self.chunk_size)
            self.position_slider.setMaximum(int(max_start_time))
            self.start_time_spinbox.setMaximum(int(max_start_time))
            
            # Adjust current position if necessary
            if self.start_time > max_start_time:
                self.start_time = max_start_time
                self.position_slider.setValue(int(self.start_time))
                self.start_time_spinbox.setValue(int(self.start_time))
        
        self.chunk_changed.emit(self.start_time, self.chunk_size)
        
    def on_position_changed(self, value: int):
        """Handle position slider changes."""
        self.start_time = float(value)
        # Update start time spinbox to match slider
        self.start_time_spinbox.setValue(int(self.start_time))
        self.chunk_changed.emit(self.start_time, self.chunk_size)
    
    def on_start_time_changed(self, value: int):
        """Handle start time spinbox changes."""
        self.start_time = float(value)
        # Update slider to match spinbox
        self.position_slider.setValue(int(self.start_time))
        self.chunk_changed.emit(self.start_time, self.chunk_size)
        
    def set_time_range_all_plots(self, start_time: float, end_time: float):
        """Set time range for all plots."""
        for plot_widget in self.plot_widgets:
            plot_widget.set_x_range(start_time, end_time)
            
    def clear_all_plots(self):
        """Clear all plots."""
        for plot_widget in self.plot_widgets:
            plot_widget.clear_plot()
            
    def get_signal_names(self) -> List[str]:
        """Get list of currently displayed signal names."""
        return [plot_widget.signal_name for plot_widget in self.plot_widgets]
        
    def get_current_chunk_info(self) -> Dict[str, float]:
        """Get current chunk information."""
        return {
            'start_time': self.start_time,
            'end_time': self.start_time + self.chunk_size,
            'chunk_size': self.chunk_size,
            'total_duration': self.total_duration
        }
    
    # Drag and Drop for plot reordering
    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("plot_widget:"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("plot_widget:"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle drop event for plot reordering."""
        if not (event.mimeData().hasText() and event.mimeData().text().startswith("plot_widget:")):
            event.ignore()
            return
        
        # Extract signal name from drag data
        signal_name = event.mimeData().text().split(":", 1)[1]
        
        # Find the dragged widget
        dragged_widget = None
        for widget in self.plot_widgets:
            if widget.signal_name == signal_name:
                dragged_widget = widget
                break
        
        if not dragged_widget:
            event.ignore()
            return
        
        # Find drop position
        drop_position = event.position().toPoint()
        target_index = self.get_drop_index(drop_position)
        
        # Perform reordering
        self.reorder_plot(dragged_widget, target_index)
        
        event.acceptProposedAction()
    
    def get_drop_index(self, drop_position: QPoint) -> int:
        """Calculate the target index for dropping based on position."""
        # Convert global position to container local position
        container_pos = self.plots_container.mapFromGlobal(
            self.mapToGlobal(drop_position)
        )
        
        # Find the widget at this position or calculate insertion point
        for i, widget in enumerate(self.plot_widgets):
            widget_rect = widget.geometry()
            widget_center_y = widget_rect.top() + widget_rect.height() / 2
            
            if container_pos.y() < widget_center_y:
                return i
        
        # If not found, insert at the end
        return len(self.plot_widgets)
    
    def reorder_plot(self, plot_widget: DraggablePlotWidget, target_index: int):
        """Reorder a plot widget to a new position."""
        # Get current index
        current_index = self.plot_widgets.index(plot_widget)
        
        # Adjust target index if moving within the same list
        if target_index > current_index:
            target_index -= 1
        
        # Clamp target index
        target_index = max(0, min(target_index, len(self.plot_widgets) - 1))
        
        # No change needed
        if current_index == target_index:
            return
        
        # Remove from current position
        self.plot_widgets.pop(current_index)
        self.plots_layout.removeWidget(plot_widget)
        
        # Insert at new position
        self.plot_widgets.insert(target_index, plot_widget)
        self.plots_layout.insertWidget(target_index, plot_widget)
    
    def move_plot_to_position(self, signal_name: str, new_index: int) -> bool:
        """Programmatically move a plot to a specific position."""
        plot_widget = self.get_plot_widget(signal_name)
        if not plot_widget:
            return False
        
        new_index = max(0, min(new_index, len(self.plot_widgets) - 1))
        self.reorder_plot(plot_widget, new_index)
        return True
    
    def get_plot_order(self) -> List[str]:
        """Get current order of plots as list of signal names."""
        return [widget.signal_name for widget in self.plot_widgets]
    
    def set_plot_order(self, signal_order: List[str]):
        """Set plot order by providing list of signal names."""
        # Validate all signals exist
        existing_signals = set(self.get_signal_names())
        new_signals = set(signal_order)
        
        if not new_signals.issubset(existing_signals):
            return False
        
        # Reorder widgets according to the new order
        new_widgets = []
        for signal_name in signal_order:
            widget = self.get_plot_widget(signal_name)
            if widget:
                new_widgets.append(widget)
        
        # Clear layout
        for widget in self.plot_widgets:
            self.plots_layout.removeWidget(widget)
        
        # Update list and re-add to layout
        self.plot_widgets = new_widgets
        for i, widget in enumerate(self.plot_widgets):
            self.plots_layout.insertWidget(i, widget)
        
        return True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Try to use real data from Aurora original if available
    use_real_data = True
    
    try:
        import sys
        import os
        
        # Manual path to Aurora original - MODIFY THIS PATH AS NEEDED
        # We need the parent directory that contains 'Pyside' module
        AURORA_ORIGINAL_PATH = r"C:\Users\Poney\Desktop\Python\Aurora\Aurora_app"
        
        print(f"Looking for Aurora original at: {AURORA_ORIGINAL_PATH}")
        pyside_path = os.path.join(AURORA_ORIGINAL_PATH, "Pyside")
        if os.path.exists(pyside_path):
            sys.path.insert(0, AURORA_ORIGINAL_PATH)  # Add the parent directory
            print(f"Added Aurora path: {AURORA_ORIGINAL_PATH}")
            from Pyside.data.data_manager import DataManager
            from Pyside.data.aditch_loader import AditchLoader
            print("Successfully imported Aurora data components")
        else:
            use_real_data = False
            print(f"Aurora original path not found at: {AURORA_ORIGINAL_PATH}")
            print("Please modify AURORA_ORIGINAL_PATH in the script to point to your Aurora original installation")
    except Exception as e:
        use_real_data = False
        print(f"Could not import Aurora components: {e}")
        print("Using synthetic data instead")
    
    # Create main widget
    plot_container = PlotContainerWidget()
    plot_container.setWindowTitle("Plot Widget Debug - Real Data" if use_real_data else "Plot Widget Debug - Synthetic Data")
    plot_container.resize(1200, 800)
    
    if use_real_data:
        try:
            # Initialize data manager
            data_manager = DataManager()
            
            # Look for .adicht files in uploaded_files
            adicht_files = []
            # Manual path to uploaded_files - MODIFY THIS PATH AS NEEDED
            upload_dir = r"C:\Users\Poney\Desktop\Python\Aurora\Aurora_app\uploaded_files"
            print(f"Looking for .adicht files in: {upload_dir}")
            
            if os.path.exists(upload_dir):
                for file in os.listdir(upload_dir):
                    if file.endswith('.adicht'):
                        adicht_files.append(os.path.join(upload_dir, file))
            
            if adicht_files:
                # Use first available .adicht file
                file_path = adicht_files[0]
                print(f"Loading real data from: {os.path.basename(file_path)}")
                
                # Load file
                data_manager.load_file(file_path)
                
                # Get available signals and limit to debug set
                available_signals = data_manager.get_available_channels(file_path)
                debug_signals = ['ECG', 'HR_gen', 'Valsalva']
                
                # Filter to only use signals that exist in the file
                test_signals = [sig for sig in debug_signals if sig in available_signals]
                print(f"Available signals: {available_signals}")
                print(f"Debug signals to load: {test_signals}")
                
                # Create fixed plots for debug signals
                signal_data = {}
                for signal_name in test_signals:
                    try:
                        # Add the plot
                        plot_container.add_signal_plot(signal_name)
                        
                        # Data processing logic (external to widget)
                        if signal_name == 'HR_gen':
                            signal_obj = data_manager.get_trace(file_path, signal_name, wavelet="haar", level=4)
                        else:
                            signal_obj = data_manager.get_trace(file_path, signal_name)
                        
                        y_data = np.asarray(signal_obj.data)
                        t_data = np.arange(len(y_data)) / signal_obj.fs
                        
                        # Calculate Y range (external logic)
                        y_valid = y_data[np.isfinite(y_data)]
                        if len(y_valid) > 0:
                            y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                            if y_min != y_max:
                                y_range = y_max - y_min
                                padding = y_range * 0.05
                                y_min -= padding
                                y_max += padding
                            else:
                                if y_min == 0:
                                    y_min, y_max = -0.1, 0.1
                                else:
                                    padding = abs(y_min) * 0.1
                                    y_min -= padding
                                    y_max += padding
                            y_range = (y_min, y_max)
                        else:
                            y_range = (-1.0, 1.0)
                        
                        # Limit data to 120 seconds for debug
                        max_samples = int(120.0 * signal_obj.fs)
                        if len(y_data) > max_samples:
                            y_data = y_data[:max_samples]
                            t_data = t_data[:max_samples]
                        
                        signal_data[signal_name] = {
                            'time': t_data,
                            'data': y_data,
                            'y_range': y_range
                        }
                        
                        print(f"Loaded {signal_name}: {len(y_data)} samples, {len(y_data)/signal_obj.fs:.1f}s, range: {y_range}")
                        
                        # Debug info for problematic signals
                        if signal_name == 'Valsalva':
                            print(f"Valsalva DEBUG: range {y_range}, unique values: {len(np.unique(y_valid))}")
                            
                    except Exception as e:
                        print(f"Error loading {signal_name}: {e}")
                
                # Set total duration (limit to 120 seconds for debug)
                first_signal_obj = data_manager.get_trace(file_path, available_signals[0])
                full_duration = len(first_signal_obj.data) / first_signal_obj.fs
                debug_duration = min(120.0, full_duration)  # Limit to 120 seconds for debug
                plot_container.set_total_duration(debug_duration)
                print(f"Full duration: {full_duration:.1f}s, Debug duration: {debug_duration:.1f}s")
                
                # Set all signal data at once
                if signal_data:
                    plot_container.set_signal_data(signal_data)
                
                print("Successfully loaded real physiological data!")
                
            else:
                print("No .adicht files found in uploaded_files, using synthetic data")
                use_real_data = False
                
        except Exception as e:
            print(f"Error loading real data: {e}")
            use_real_data = False
    
    # Fallback to synthetic data if real data failed
    if not use_real_data:
        print("Using synthetic data for debugging")
        
        # Set total duration for testing (120 seconds for debug)
        plot_container.set_total_duration(120.0)
        
        # Add debug plots
        debug_signals = ['ECG', 'HR_gen', 'Valsalva']
        signal_data = {}
        
        for signal_name in debug_signals:
            plot_container.add_signal_plot(signal_name)
        
        # Generate test data with proper Y ranges (120 seconds for debug)
        t = np.linspace(0, 120, 2000)  # 120 seconds of data at ~16.7 Hz
        
        # ECG-like signal (realistic range: -1.5 to 1.5 mV)
        ecg_data = 1.2 * np.sin(2 * np.pi * 1.2 * t) + 0.3 * np.sin(2 * np.pi * 5 * t)
        signal_data['ECG'] = {'time': t, 'data': ecg_data, 'y_range': (-2.0, 2.0)}
        
        # HR-like signal (realistic range: 60-120 bpm)
        hr_data = 75 + 10 * np.sin(2 * np.pi * 0.1 * t) + 2 * np.random.randn(len(t))
        signal_data['HR_gen'] = {'time': t, 'data': hr_data, 'y_range': (50, 130)}
        
        # Valsalva-like signal (0-1 range for valve state)
        valsalva_data = np.where(np.sin(2 * np.pi * 0.2 * t) > 0.5, 1.0, 0.0) + 0.1 * np.random.randn(len(t))
        signal_data['Valsalva'] = {'time': t, 'data': valsalva_data, 'y_range': (-0.5, 1.5)}
        
        # Set all data
        plot_container.set_signal_data(signal_data)
    
    # Connect signals for debugging
    def on_chunk_changed(start_time, chunk_size):
        print(f"Chunk changed: start={start_time:.1f}s, size={chunk_size:.1f}s")
        
    def on_signal_added(signal_name):
        print(f"Signal added: {signal_name}")
        
    def on_signal_removed(signal_name):
        print(f"Signal removed: {signal_name}")
    
    plot_container.chunk_changed.connect(on_chunk_changed)
    plot_container.signal_added.connect(on_signal_added)
    plot_container.signal_removed.connect(on_signal_removed)
    
    plot_container.show()
    sys.exit(app.exec())