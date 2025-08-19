"""
EventPlotContainer - Especialización del PlotContainerWidget para EventTab
Siguiendo el patrón estándar: recibe DataManager del Tab, gestiona visualización y eventos.
"""

import numpy as np
from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QPushButton, QLineEdit, QCheckBox
from PySide6.QtCore import QTimer

from .plot_widget import PlotContainerWidget
from Pyside.processing.chunk_loader import ChunkLoader
from Pyside.ui.managers.comment_marker_manager import get_comment_marker_manager
from Pyside.core import get_user_logger


class EventPlotContainer(PlotContainerWidget):
    """
    Container de plots especializado para EventTab.
    
    Responsabilidades:
    - Visualización de señales con eventos y comentarios
    - Controles específicos para navegación de eventos
    - Integración con sistema de comentarios
    - Búsqueda y filtrado de eventos
    
    Sigue patrón estándar:
    - Recibe DataManager del EventTab
    - Solo maneja visualización y navegación
    - NO gestiona carga de archivos
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_user_logger("EventPlotContainer")
        
        # DataManager context (recibido del Tab)
        self.data_manager = None
        self.file_path: str = ""
        self.hr_params: Dict = {}
        
        # Event-specific data
        self.current_events: List = []
        self.filtered_events: List = []
        
        # Chunk loading
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self.on_chunk_loaded)
        
        # Comment management uses the new PlotContainerWidget system
        # No need for separate comment managers
        
        # Y-range management for consistent scaling
        self.y_ranges: Dict[str, tuple] = {}
        
        # Connect signals
        self.time_changed.connect(self.load_chunk)
        self.chunk_size_changed.connect(self.load_chunk)
        
        self.logger.debug("EventPlotContainer initialized")
        
    def create_controls(self) -> QWidget:
        """
        Create controls specific to EventTab.
        Extends base controls with event-specific functionality.
        """
        # Get base controls (Start, Chunk size, Position slider)
        controls_widget = super().create_controls()
        
        # Add event-specific controls
        controls_layout = controls_widget.layout()
        
        # Event search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search events...")
        self.search_edit.textChanged.connect(self.filter_events)
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.search_edit)
        
        # Show all comments toggle
        self.show_all_comments = QCheckBox("Show All Comments")
        self.show_all_comments.setChecked(True)
        self.show_all_comments.toggled.connect(self.toggle_comment_visibility)
        controls_layout.addWidget(self.show_all_comments)
        
        # Navigation buttons for events
        self.prev_event_btn = QPushButton("◀ Prev Event")
        self.next_event_btn = QPushButton("Next Event ▶")
        self.prev_event_btn.clicked.connect(self.navigate_to_prev_event)
        self.next_event_btn.clicked.connect(self.navigate_to_next_event)
        
        controls_layout.addWidget(self.prev_event_btn)
        controls_layout.addWidget(self.next_event_btn)
        
        return controls_widget
        
    def set_data_context(self, data_manager, file_path: str, hr_params: Dict = None):
        """Configurar contexto de datos desde EventTab"""
        self.data_manager = data_manager
        self.file_path = file_path
        self.hr_params = hr_params or {}
        
        self.logger.debug(f"Data context set: file={file_path}, hr_params={hr_params}")
        
        # Calculate duration from ECG signal
        if self.data_manager and self.file_path:
            try:
                ecg = self.data_manager.get_trace(self.file_path, "ECG")
                self.duration = len(ecg.data) / ecg.fs
                self.set_duration(self.duration)
                
                # Load events/intervals for navigation
                self.load_events()
                
                # Calculate Y-ranges for all target signals
                self.calculate_y_ranges()
                
                # Enable comments for all plots by default in EventTab
                if self.plots:
                    self.enable_comments_for_all_plots(file_path, True)
                
                self.logger.debug(f"Duration set to {self.duration:.2f}s, {len(self.current_events)} events loaded")
            except Exception as e:
                self.logger.error(f"Error setting data context: {e}")
                
    def load_events(self):
        """Load events/intervals for navigation"""
        try:
            # Get events from DataManager
            self.current_events = self.data_manager.get_event_intervals(
                self.file_path, 
                channel_names=None,  # Use default channels
                **self.hr_params
            )
            
            # Initialize filtered events
            self.filtered_events = self.current_events.copy()
            
            # Update navigation buttons
            self.update_navigation_buttons()
            
            self.logger.debug(f"Loaded {len(self.current_events)} events")
            
        except Exception as e:
            self.logger.error(f"Error loading events: {e}")
            self.current_events = []
            self.filtered_events = []
            
    def filter_events(self, search_text: str):
        """Filter events based on search text"""
        if not search_text:
            self.filtered_events = self.current_events.copy()
        else:
            search_lower = search_text.lower()
            self.filtered_events = [
                event for event in self.current_events
                if search_lower in str(event.get('evento', '')).lower()
            ]
        
        self.update_navigation_buttons()
        self.logger.debug(f"Filtered to {len(self.filtered_events)} events")
        
    def navigate_to_prev_event(self):
        """Navigate to previous event"""
        if not self.filtered_events:
            return
            
        current_time = self.start_time
        # Find previous event before current time
        prev_events = [e for e in self.filtered_events 
                      if e.get('t_evento', 0) < current_time]
        
        if prev_events:
            # Go to most recent previous event
            target_event = max(prev_events, key=lambda x: x.get('t_evento', 0))
            self.navigate_to_event(target_event)
            
    def navigate_to_next_event(self):
        """Navigate to next event"""
        if not self.filtered_events:
            return
            
        current_time = self.start_time
        # Find next event after current time
        next_events = [e for e in self.filtered_events 
                      if e.get('t_evento', 0) > current_time]
        
        if next_events:
            # Go to earliest next event
            target_event = min(next_events, key=lambda x: x.get('t_evento', 0))
            self.navigate_to_event(target_event)
            
    def navigate_to_event(self, event: Dict):
        """Navigate to specific event"""
        event_time = event.get('t_evento', 0)
        
        # Center the event in the view
        new_start_time = max(0, event_time - self.chunk_size / 2)
        
        # Update controls and load chunk
        self.start_time = new_start_time
        self.start_spinbox.setValue(int(new_start_time))
        self.position_slider.setValue(int(new_start_time))
        
        self.load_chunk()
        
        self.logger.debug(f"Navigated to event '{event.get('evento', 'Unknown')}' at {event_time:.2f}s")
        
    def update_navigation_buttons(self):
        """Update navigation button states"""
        current_time = self.start_time
        
        # Check if there are previous/next events
        has_prev = any(e.get('t_evento', 0) < current_time for e in self.filtered_events)
        has_next = any(e.get('t_evento', 0) > current_time for e in self.filtered_events)
        
        self.prev_event_btn.setEnabled(has_prev)
        self.next_event_btn.setEnabled(has_next)
        
    def toggle_comment_visibility(self, show_all: bool):
        """Toggle visibility of all comments"""
        if not self.file_path:
            return
            
        if show_all:
            # Enable comments for all plots
            self.enable_comments_for_all_plots(self.file_path, True)
        else:
            # Disable comments for all plots
            self.disable_all_comments()
            
        self.logger.debug(f"Comment visibility toggled: {show_all} for all plots")
        
    def calculate_y_ranges(self):
        """Calculate global Y-ranges for consistent scaling"""
        self.y_ranges.clear()
        
        if not self.data_manager or not self.file_path:
            return
            
        for signal_name in self.target_signals:
            try:
                # Get appropriate signal data
                if signal_name.upper() == "HR_GEN":
                    sig = self.data_manager.get_trace(self.file_path, signal_name, **self.hr_params)
                else:
                    sig = self.data_manager.get_trace(self.file_path, signal_name)
                    
                # Calculate range with robust safety checks
                data = sig.data
                valid_data = data[np.isfinite(data)]
                
                if len(valid_data) > 0:
                    y_min, y_max = np.min(valid_data), np.max(valid_data)
                    
                    # Robust safety checks to prevent PyQtGraph overflow warnings
                    if not np.isfinite(y_min) or not np.isfinite(y_max):
                        y_min, y_max = -1.0, 1.0
                    elif abs(y_min) > 1e30 or abs(y_max) > 1e30:
                        # Extremely large values - clamp to reasonable range
                        y_min, y_max = -1e6, 1e6
                    elif abs(y_max - y_min) > 1e6:
                        y_center = (y_min + y_max) / 2
                        if abs(y_center) > 1e6:
                            y_center = 0.0  # Reset center if too large
                        y_min, y_max = y_center - 1e5, y_center + 1e5
                    elif y_min == y_max:
                        if abs(y_min) > 1e6:
                            y_min, y_max = -1.0, 1.0  # Reset if value too large
                        else:
                            padding = max(abs(y_min) * 0.1, 0.1)
                            y_min -= padding
                            y_max += padding
                    else:
                        # Add 5% padding with overflow protection
                        range_val = y_max - y_min
                        if range_val > 1e6:
                            # Large range, use fixed padding
                            padding = 1e4
                        else:
                            padding = range_val * 0.05
                        y_min -= padding
                        y_max += padding
                    
                    # Final validation to ensure values are within PyQtGraph limits
                    y_min = np.clip(y_min, -1e15, 1e15)
                    y_max = np.clip(y_max, -1e15, 1e15)
                    
                    # Ensure min < max
                    if y_min >= y_max:
                        y_min, y_max = -1.0, 1.0
                        
                    self.y_ranges[signal_name] = (float(y_min), float(y_max))
                    self.logger.debug(f"Y-range for {signal_name}: [{y_min:.3f}, {y_max:.3f}]")
                else:
                    self.y_ranges[signal_name] = (-1.0, 1.0)
                    self.logger.warning(f"No valid data for {signal_name}, using default range")
                    
            except Exception as e:
                self.logger.error(f"Error calculating Y-range for {signal_name}: {e}")
                self.y_ranges[signal_name] = (-1.0, 1.0)
                
    def load_chunk(self):
        """Load current chunk using ChunkLoader"""
        if not self.data_manager or not self.file_path or not self.target_signals:
            return
            
        # Request chunk from ChunkLoader
        self.chunk_loader.request_chunk(
            data_manager=self.data_manager,
            file_path=self.file_path,
            channel_names=self.target_signals,
            start_sec=self.start_time,
            duration_sec=self.chunk_size,
            hr_params=self.hr_params
        )
        
        # Update navigation buttons for current time
        self.update_navigation_buttons()
        
        self.logger.debug(f"Requested chunk: start={self.start_time}, duration={self.chunk_size}")
        
    def on_chunk_loaded(self, start: float, end: float, data_dict: Dict):
        """Handle chunk loaded from ChunkLoader"""
        self.logger.debug(f"Chunk loaded: {start:.2f} - {end:.2f}s, signals: {list(data_dict.keys())}")
        
        # Update each plot with its data (same as ViewerPlotContainer)
        for signal_name in self.target_signals:
            if signal_name not in data_dict:
                self.logger.warning(f"Signal {signal_name} not in loaded chunk")
                continue
                
            plot = self.get_plot_by_signal(signal_name)
            if not plot:
                continue
                
            try:
                # Get signal data
                sig_data = data_dict[signal_name]
                
                # For chunk loaded data, we expect it to be processed
                if hasattr(sig_data, 'data') and hasattr(sig_data, 'fs'):
                    # Signal object
                    fs = sig_data.fs
                    y_data = sig_data.data
                else:
                    # Raw data - get fs from data manager
                    sig = self.data_manager.get_trace(
                        self.file_path, 
                        signal_name, 
                        **self.hr_params if signal_name.upper() == "HR_GEN" else {}
                    )
                    fs = sig.fs
                    y_data = sig_data
                    
                # Create time array and process data (same as ViewerPlotContainer)
                expected_len = int(self.chunk_size * fs)
                
                # Handle data preparation
                y_data = np.asarray(y_data)
                if not np.all(np.isfinite(y_data)):
                    y_data = np.nan_to_num(y_data, nan=0.0, posinf=1e6, neginf=-1e6)
                    
                if np.abs(y_data).max() > 1e6:
                    y_data = np.clip(y_data, -1e6, 1e6)
                    
                # Ensure correct length
                if len(y_data) < expected_len:
                    y_data = np.concatenate([
                        y_data, 
                        np.full(expected_len - len(y_data), np.nan, dtype=np.float32)
                    ])
                    
                # Create time array
                t = np.arange(len(y_data)) / fs + self.start_time
                
                # Downsampling for performance
                max_points = 5000
                if len(y_data) > max_points:
                    step = int(np.ceil(len(y_data) / max_points))
                    y_data = y_data[::step]
                    t = t[::step]
                    
                # Update plot data
                plot.curve.setData(t, y_data)
                plot.plot_widget.setXRange(start, end, padding=0)
                
                # Apply consistent Y-range with overflow protection
                y_min, y_max = self.y_ranges.get(signal_name, (-1.0, 1.0))
                
                # Additional safety check before setting range
                if np.isfinite(y_min) and np.isfinite(y_max) and y_min < y_max:
                    # Clamp to reasonable values for PyQtGraph
                    y_min = max(-1e10, min(1e10, y_min))
                    y_max = max(-1e10, min(1e10, y_max))
                    plot.plot_widget.setYRange(y_min, y_max, padding=0)
                else:
                    # Fallback to safe default range
                    plot.plot_widget.setYRange(-1.0, 1.0, padding=0)
                
                # Update plot label with units
                self.update_plot_label(plot, signal_name)
                
            except Exception as e:
                self.logger.error(f"Error updating plot {signal_name}: {e}")
                
        # Comments are automatically updated via global signal system
        # No need for manual marker management
        
    def update_plot_label(self, plot, signal_name: str):
        """Update plot label with appropriate units"""
        try:
            # Get units from signal
            if signal_name.upper() == "HR_GEN":
                sig = self.data_manager.get_trace(self.file_path, signal_name, **self.hr_params)
            else:
                sig = self.data_manager.get_trace(self.file_path, signal_name)
                
            units = getattr(sig, 'units', '')
            
            # Clean and validate units to prevent duplication
            if units:
                units_str = str(units).strip()
                
                # Handle cases where units might be duplicated
                if ',' in units_str:
                    unique_units = list(set(u.strip() for u in units_str.split(',') if u.strip()))
                    units_str = ', '.join(unique_units)
                
                plot.plot_widget.setLabel("left", f"{signal_name} ({units_str})")
            else:
                plot.plot_widget.setLabel("left", signal_name)
                
        except Exception as e:
            self.logger.error(f"Error updating plot label for {signal_name}: {e}")
            plot.plot_widget.setLabel("left", signal_name)
            
    def toggle_comments_for_signals(self, signal_names: List[str]):
        """Toggle comment visibility for specific signals."""
        if not self.file_path:
            return
            
        try:
            self.enable_comments_for_signals(self.file_path, signal_names)
            self.logger.info(f"Toggled comments for signals: {signal_names}")
        except Exception as e:
            self.logger.error(f"Error toggling comments for signals: {e}")
            
    def update_hr_params(self, hr_params: Dict):
        """Update HR parameters and reload current chunk"""
        self.hr_params = hr_params
        self.logger.debug(f"HR params updated: {hr_params}")
        
        # Recalculate Y-ranges for HR_GEN signals
        if any('HR' in signal.upper() for signal in self.target_signals):
            self.calculate_y_ranges()
            
        # Reload events with new parameters
        self.load_events()
            
        # Reload current chunk
        self.load_chunk()
        
    def refresh_display(self):
        """Refresh the entire display"""
        self.calculate_y_ranges()
        self.load_events()
        self.load_chunk()
        
    def set_signals(self, signal_names: List[str]):
        """Override to integrate with data loading"""
        super().set_signals(signal_names)
        
        # Calculate Y-ranges for new signals
        if self.data_manager and self.file_path:
            self.calculate_y_ranges()
            
            # Enable comments for new plots
            self.enable_comments_for_all_plots(self.file_path, True)
            
        # Reload events for new signals
        self.load_events()
            
        # Load current chunk for new signals
        self.load_chunk()