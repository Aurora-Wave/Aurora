"""
CustomPlot - Plot individual con funcionalidades avanzadas.
Incluye drag & drop, cambio de colores, comentarios, y cambio de señales.
Adaptado para el sistema de sesiones de Aurora.
"""

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QColorDialog, QMenu, QComboBox, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag, QPixmap, QPainter, QAction
from typing import List, Dict, Optional, Tuple
import logging
import numpy as np

from aurora.ui.managers.plot_style_manager import get_plot_style_manager, PlotStyle
from aurora.ui.utils.selectable_viewbox import SelectableViewBox


class NoScrollComboBox(QComboBox):
    """QComboBox que no responde al scroll del mouse/touchpad."""
    
    def wheelEvent(self, event):
        """Ignore wheel events to prevent accidental signal changes."""
        # No llamar a super().wheelEvent(event) para ignorar el scroll
        event.ignore()


class CustomPlot(QWidget):
    """
    Plot individual personalizable con integración completa.
    
    Funcionalidades:
    - Cambio de colores interactivo
    - Drag & drop para reordering
    - Visualización de comentarios
    - Cambio dinámico de señal
    - Context menus
    - Integración con managers de estilo y comentarios
    """
    
    # Signals for operations
    remove_requested = Signal(object)  # self
    color_changed = Signal(object, str)  # self, new_color
    style_changed = Signal(object)  # self
    signal_changed = Signal(object, str)  # self, new_signal_name
    
    def __init__(self, signal_name: str, available_signals: List[str] = None, custom_style: Optional[PlotStyle] = None, 
                 plot_container=None, plot_index: int = 0):
        super().__init__()
        self.signal_name = signal_name
        self.available_signals = available_signals or [signal_name]
        self.custom_style = custom_style
        self.plot_container = plot_container
        self.plot_index = plot_index
        self.drag_start_position = None
        
        # Managers
        self.style_manager = get_plot_style_manager()
        
        # Logger
        self.logger = logging.getLogger(f"aurora.ui.CustomPlot.{signal_name}")
        
        # Get current style
        self.current_style = self.style_manager.get_style_for_signal(signal_name, custom_style)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        self.setup_ui()
        self.logger.debug(f"CustomPlot created for {signal_name}")
        
    @property
    def min_height(self):
        """Get height from style manager"""
        return getattr(self.current_style, 'min_plot_height', 150)
    
    def minimumSizeHint(self):
        """Size hint for QSplitter - enforces minimum height."""
        from PySide6.QtCore import QSize
        return QSize(200, self.min_height)
        
    def setup_ui(self):
        """Setup the UI for the individual plot widget."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # ========= Control area (left side) - fixed width =========
        controls_frame = QFrame()
        controls_frame.setFixedWidth(120)  # Slightly wider for signal selector
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(2, 2, 2, 2)
        
        # Drag handle
        self.drag_label = QLabel("≡≡≡")
        self.drag_label.setAlignment(Qt.AlignCenter)
        self.drag_label.setToolTip("Drag to reorder")
        self.drag_label.setMaximumHeight(15)
        
        # Signal selector dropdown (without scroll wheel behavior)
        self.signal_selector = NoScrollComboBox()
        self.signal_selector.addItems(self.available_signals)
        self.signal_selector.setCurrentText(self.signal_name)
        self.signal_selector.currentTextChanged.connect(self.on_signal_changed)
        self.signal_selector.setToolTip("Change signal (click to select)")
        
        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(30, 20)
        self.btn_remove.setStyleSheet("QPushButton { color: red; }")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        self.btn_remove.setToolTip("Remove plot")
        
        controls_layout.addWidget(self.drag_label)
        controls_layout.addWidget(self.signal_selector)
        controls_layout.addWidget(self.btn_remove)
        controls_layout.addStretch()
        # ========= Control area (left side) END =========

        # ========= Plot widget (right side) =========
        # Create SelectableViewBox if plot_container is provided
        if self.plot_container:
            viewbox = SelectableViewBox(self.plot_container, self.plot_index)
            self.plot_widget = pg.PlotWidget(viewBox=viewbox)
            # Store reference to access SelectableViewBox signals if needed
            self.viewbox = viewbox
        else:
            self.plot_widget = pg.PlotWidget()
            self.viewbox = None

        # Configure plot using centralized style management
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
        self.style_manager.configure_plot_widget(
            self.plot_widget, 
            self.signal_name, 
            self.current_style
        )
        
        # Remove left label - using combobox selector instead
        self.plot_widget.setLabel("left", "")

        # Apply to CustomPlot container
        self.setMinimumHeight(self.min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.logger.debug(f"CustomPlot {self.signal_name} minimum height set to: {self.min_height}px")
        
        # Create curve with style from manager
        pen = self.style_manager.create_plot_pen(self.signal_name, self.custom_style)
        self.curve = self.plot_widget.plot(pen=pen, name=self.signal_name)
        
        self.logger.debug(f"Plot configured for {self.signal_name} using PlotStyleManager")
        
    def setup_context_menu(self):
        """Setup custom context menu for plot."""
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, position):
        """Show custom context menu."""
        from aurora.ui.utils.context_menu import PlotContextMenu
        
        menu = PlotContextMenu.create_plot_menu(
            parent_widget=self,
            available_signals=self.available_signals,
            current_signal=self.signal_name,
            on_color_change=self.change_color,
            on_signal_change=self.change_signal,
            on_remove=lambda: self.remove_requested.emit(self)
        )
        
        PlotContextMenu.show_menu(menu, self.plot_widget, position)

    def on_signal_changed(self, new_signal: str):
        """Handle signal change from dropdown."""
        if new_signal and new_signal != self.signal_name:
            self.change_signal(new_signal)
            
    def change_color(self):
        """Open color dialog and change plot color."""
        color_dialog = QColorDialog(self)
        color_dialog.setCurrentColor(self.current_style.pen_color)
        
        if color_dialog.exec():
            new_color = color_dialog.currentColor().name()
            self.update_color(new_color)
            self.color_changed.emit(self, new_color)
            
    def change_signal(self, new_signal_name: str):
        """Change the signal displayed in this plot."""
        if new_signal_name in self.available_signals:
            old_signal = self.signal_name
            self.signal_name = new_signal_name
            
            # Update UI elements
            self.signal_selector.setCurrentText(new_signal_name)
            # No left label - using combobox selector instead
            
            # Get style for new signal
            self.current_style = self.style_manager.get_style_for_signal(new_signal_name)
            
            # Update plot appearance
            pen = self.style_manager.create_plot_pen(new_signal_name)
            self.curve.setPen(pen)
            
            self.logger.info(f"Changed signal from {old_signal} to {new_signal_name}")
            
            # Emit signal change
            self.signal_changed.emit(self, new_signal_name)
            
    def update_color(self, color: str):
        """Update plot color."""
        # Update style manager
        self.style_manager.update_signal_color(self.signal_name, color)
        
        # Update current style
        self.current_style = self.style_manager.get_style_for_signal(self.signal_name)
        
        # Label removed - using combobox selector instead
        
        # Update plot curve using style manager
        pen = self.style_manager.create_plot_pen(self.signal_name, self.custom_style)
        self.curve.setPen(pen)
        
        self.logger.debug(f"Updated color for {self.signal_name} to {color}")
    
    def update_available_signals(self, new_signals: List[str]):
        """Update the list of available signals for changing."""
        self.available_signals = new_signals
        
        # Update dropdown
        current_signal = self.signal_selector.currentText()
        self.signal_selector.clear()
        self.signal_selector.addItems(new_signals)
        
        # Restore current selection if still available
        if current_signal in new_signals:
            self.signal_selector.setCurrentText(current_signal)
        
        self.logger.debug(f"Updated available signals: {new_signals}")
    
    def update_data(self, time_data: np.ndarray, y_data: np.ndarray):
        """Update plot data efficiently - only updates data without recreating curve."""
        try:
            # Fast update: only change data, keep existing curve and styling
            if hasattr(self, 'curve') and self.curve is not None:
                self.curve.setData(time_data, y_data)
            else:
                # First time: create curve with proper styling
                pen = self.style_manager.create_plot_pen(self.signal_name, self.custom_style)
                self.curve = self.plot_widget.plot(time_data, y_data, pen=pen, name=self.signal_name)
                
        except Exception as e:
            self.logger.error(f"Error updating data for {self.signal_name}: {e}")
    
    def set_time_range(self, start_time: float, end_time: float):
        """Set the time range for the plot ViewBox (called once from container)."""
        try:
            viewbox = self.plot_widget.getViewBox()
            viewbox.setXRange(start_time, end_time, padding=0)
            # Auto-range Y axis to fit data
            viewbox.enableAutoRange(axis=viewbox.YAxis)
        except Exception as e:
            self.logger.error(f"Error setting time range for {self.signal_name}: {e}")
    
    # ========= Drag and Drop Implementation =========
    
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
    
    # ========= Height Management =========

    def refresh_min_height(self, new_min: int):
        """Refresh minimum height when style manager updates."""
        # Update current_style to get latest state from manager (includes user modifications)
        self.current_style = self.style_manager.get_style_for_signal(self.signal_name, self.custom_style)
        
        # Update container minimum height
        self.setMinimumHeight(self.min_height)
        
        # Force Qt to recalculate size hints
        self.updateGeometry()
        
        self.logger.debug(f"Refreshed {self.signal_name} minimum height to: {self.min_height}px")
    
    def _on_color_changed(self, signal_name: str, new_color: str):
        """Handle color change signal from style manager."""
        if signal_name == self.signal_name:
            # Update plot curve
            pen = self.style_manager.create_plot_pen(self.signal_name, self.custom_style)
            self.curve.setPen(pen)
    
    # Comments are now handled globally by PlotContainer, not per-plot
    
    # ========= Cleanup =========
    
    def cleanup(self):
        """Cleanup when plot is being destroyed."""
        try:
            # Comments are now handled globally, no per-plot cleanup needed
            
            # Disconnect style manager signals
            try:
                self.style_manager.colorChanged.disconnect(self._on_color_changed)
                self.style_manager.minHeightChanged.disconnect(self.refresh_min_height)
            except (RuntimeError, TypeError):
                pass
            
            # Clear viewbox reference
            self.viewbox = None
                
            self.logger.debug(f"CustomPlot cleanup completed for {self.signal_name}")
            
        except Exception as e:
            self.logger.error(f"Error during CustomPlot cleanup: {e}")
    
    