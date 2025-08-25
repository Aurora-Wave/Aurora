"""
VisualizationBaseTab - Base class for session-based visualization tabs.
Adapted for the new session system - each tab receives and works with a Session object.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QSlider
from PySide6.QtCore import Signal as QtSignal, QObject, Qt, QTimer
from PySide6.QtCore import QAbstractItemModel
import logging

from aurora.core.session import Session
from aurora.ui.widgets.plot_container_widget import PlotContainerWidget
from aurora.core.comments import get_comment_manager


class VisualizationBaseTab(QWidget):
    """
    Abstract base class for tabs with plot visualization in session-based system.
    
    Key differences from original:
    - Receives Session object instead of DataManager directly
    - Session contains isolated DataManager and configuration
    - No MainWindow dependency - self-contained tab
    
    Provides common functionality:
    - PlotContainer integration (when PlotContainer is available)
    - Session-based data access
    - Common navigation controls
    - Standard parameter management
    
    Requires subclasses to implement:
    - setup_tab_specific_ui(): Tab-specific UI components
    - update_tab_data(): Process session data for display
    - _customize_for_tab(): Post-display customizations
    """
    
    # Common signals for all visualization tabs
    parameters_changed = QtSignal(dict)  # Emitted when parameters change
    data_updated = QtSignal()  # Emitted when tab data is updated
    error_occurred = QtSignal(str)  # Emitted when errors occur
    time_changed = QtSignal(float)  # Emitted when navigation time changes
    chunk_size_changed = QtSignal(float)  # Emitted when chunk size changes
    
    def __init__(self, session: Session, parent=None):
        """Initialize tab with Session reference."""
        super().__init__(parent)
        
        # Core components
        self.session = session
        self.logger = logging.getLogger(f"aurora.ui.{self.__class__.__name__}")
        
        # Comment management - only consume, don't manage
        self.comment_manager = get_comment_manager()
        
        # Connect CommentManager signals to refresh plot markers
        self.comment_manager.comment_added.connect(self._on_comment_changed)
        self.comment_manager.comment_updated.connect(self._on_comment_changed)
        self.comment_manager.comment_removed.connect(self._on_comment_changed)
        
        # State tracking
        self.is_data_loaded = False
        self.current_signals: List[str] = []
        self.current_parameters: Dict = {}
        
        # Layout components
        self.main_layout = QVBoxLayout(self)
        self.controls_layout = QHBoxLayout()
        
        # PlotContainer - will be created in setup_ui()
        self.plot_container = None
        
        # Navigation controls - shared across all visualization tabs
        self.start_spinbox = None
        self.chunk_spinbox = None 
        self.position_slider = None
        self.time_label = None
        self.btn_prev = None
        self.btn_next = None
        
        # Navigation state
        self.start_time = 0.0
        self.chunk_size = 60.0
        self.duration = 100.0
        
        # Timer for slider throttling (improves performance)
        self.slider_timer = QTimer()
        self.slider_timer.setSingleShot(True)
        self.slider_timer.timeout.connect(self._apply_slider_change)
        self.pending_slider_value = None
        
        # Setup base UI
        self._setup_base_ui()
        
        # Connect session signals
        self.logger.debug("Connecting session signals...")
        try:
            self.session.session_ready.connect(self._on_session_ready)
            self.logger.debug("session_ready signal connected")
        except Exception as e:
            self.logger.error(f"Failed to connect session_ready: {e}")
            
        if hasattr(self.session, 'data_loaded'):
            try:
                self.session.data_loaded.connect(self._on_session_data_loaded)
                self.logger.debug("data_loaded signal connected")
            except Exception as e:
                self.logger.error(f"Failed to connect data_loaded: {e}")
        
        # If session is already loaded, refresh immediately
        if self.session.is_loaded:
            self.logger.info("Session is already loaded - triggering immediate refresh")
            self.refresh_from_session()
        
        self.logger.debug(f"{self.__class__.__name__} initialized with session {session.session_id}")
    
    def _setup_base_ui(self) -> None:
        """Setup common UI elements."""
        # Configure main layout
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)
        
        # Configure controls layout
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)
        
        # Add controls layout to main layout
        self.main_layout.addLayout(self.controls_layout)
        
        # Create navigation controls
        self._create_navigation_controls()
        
        # Create plot container (simplified without duplicate controls)
        # Use class name to create predictable tab_id (e.g., "EventsTab" -> "events_tab")
        tab_type = self.__class__.__name__.lower().replace('tab', '')
        self.plot_container = PlotContainerWidget(self, tab_type=tab_type)
        
        # Let subclasses customize the layout in setup_tab_specific_ui()
        # They can add the plot_container directly or create custom layouts
        
        # Setup UI using Template Method pattern
        self.setup_tab_specific_ui()
    
    def _create_navigation_controls(self):
        """Create common navigation controls for all visualization tabs."""
        # Start time controls
        start_label = QLabel("Start:")
        self.start_spinbox = QSpinBox()
        self.start_spinbox.setRange(0, int(self.duration - self.chunk_size))
        self.start_spinbox.setValue(int(self.start_time))
        self.start_spinbox.setSuffix("s")
        self.start_spinbox.valueChanged.connect(self._on_start_time_changed)
        
        # Chunk size controls  
        chunk_label = QLabel("Chunk:")
        self.chunk_spinbox = QSpinBox()
        self.chunk_spinbox.setRange(10, 6000)
        self.chunk_spinbox.setValue(int(self.chunk_size))
        self.chunk_spinbox.setSuffix("s")
        self.chunk_spinbox.valueChanged.connect(self._on_chunk_size_changed)
        
        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, int(self.duration - self.chunk_size))
        self.position_slider.setValue(int(self.start_time))
        self.position_slider.setMinimumWidth(200)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal { 
                height: 6px; background: #333; border-radius: 3px; 
            }
            QSlider::handle:horizontal { 
                background: #5a9fd4; width: 14px; height: 14px; 
                border-radius: 7px; margin: -4px 0;
            }
            QSlider::handle:horizontal:hover { background: #7bb3e0; }
        """)
        self.position_slider.valueChanged.connect(self._on_slider_changed)
        
        # Time label
        self.time_label = QLabel("0.0s")
        self.time_label.setFixedWidth(50)
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # Previous/Next buttons
        self.btn_prev = QPushButton("←")
        self.btn_prev.clicked.connect(self._go_previous_chunk)
        
        self.btn_next = QPushButton("→")
        self.btn_next.clicked.connect(self._go_next_chunk)
        
        # Add controls to layout
        self.controls_layout.addWidget(start_label)
        self.controls_layout.addWidget(self.start_spinbox)
        self.controls_layout.addWidget(chunk_label)
        self.controls_layout.addWidget(self.chunk_spinbox)
        self.controls_layout.addWidget(self.position_slider)
        self.controls_layout.addWidget(self.time_label)
        self.controls_layout.addWidget(self.btn_prev)
        self.controls_layout.addWidget(self.btn_next)
        self.controls_layout.addStretch()

    @abstractmethod
    def setup_tab_specific_ui(self) -> None:
        """Setup UI components specific to each tab type. Must be implemented by subclasses."""
        pass
    
    def _on_session_ready(self) -> None:
        """Called when session is fully loaded and ready."""
        self.logger.info(f"=== SESSION READY SIGNAL RECEIVED ===")
        self.logger.info(f"Session: {self.session.session_id}")
        self.refresh_from_session()
    
    def _on_session_data_loaded(self, file_path: str) -> None:
        """Called when session data is loaded."""
        self.logger.info(f"Session data loaded: {file_path}")
        self.refresh_from_session()
    
    def refresh_from_session(self) -> None:
        """Refresh tab data from session."""
        self.logger.info(f"=== REFRESH FROM SESSION STARTED ===")
        self.logger.info(f"Tab: {self.__class__.__name__}")
        self.logger.debug(f"Session: {self.session.session_id if self.session else 'None'}")
        
        if not self.session:
            self.logger.error("No session available - cannot refresh")
            return
            
        self.logger.debug(f"Session is_loaded: {self.session.is_loaded}")
        if not self.session.is_loaded:
            self.logger.warning("Session not ready for refresh - is_loaded=False")
            return
            
        try:
            # Get session data and configuration
            self.logger.debug("Getting session data and configuration...")
            data_manager = self.session.data_manager
            file_path = self.session.file_path
            selected_channels = self.session.selected_channels
            config = self.session.config
            
            self.logger.info(f"Data manager: {data_manager}")
            self.logger.info(f"File path: {file_path}")
            self.logger.info(f"Selected channels: {selected_channels}")
            self.logger.debug(f"Config keys: {list(config.keys()) if config else 'None'}")
            
            # Display signals using the standard interface
            self.logger.debug(f"Calling display_signals()...")
            hr_params = config.get('hr_params', {})
            success = self.display_signals(
                data_manager=data_manager,
                file_path=file_path,
                target_signals=selected_channels,
                hr_params=hr_params
            )
            self.logger.info(f"display_signals() result: {success}")
            
            if success:
                self.logger.info(f"=== REFRESH FROM SESSION SUCCESS ===")
            else:
                self.logger.warning(f"=== REFRESH FROM SESSION FAILED - display_signals returned False ===")
                
        except Exception as e:
            self.logger.error(f"=== REFRESH FROM SESSION ERROR ===")
            self.logger.error(f"Exception during refresh: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
    
    @abstractmethod
    def update_tab_data(self, data_manager, file_path: str, **kwargs) -> bool:
        """
        Update tab with data from session. Must be implemented by subclasses.
        
        Args:
            data_manager: DataManager instance from session
            file_path: Path to the data file
            **kwargs: Additional parameters from session config
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    def display_signals(self, data_manager, file_path: str, target_signals: List[str], 
                       hr_params: Dict = None) -> bool:
        """
        Standard interface for displaying signals.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to data file
            target_signals: List of signals to display
            hr_params: HR generation parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            hr_params = hr_params or {}
            
            # Update internal state
            self.current_signals = target_signals.copy()
            self.current_parameters = hr_params.copy()
            
            # Update tab data (delegates to subclass implementation)
            success = self.update_tab_data(
                data_manager=data_manager,
                file_path=file_path,
                target_signals=target_signals,
                hr_params=hr_params
            )
            
            if success:
                self.logger.info(f"Tab data update successful, proceeding with plot display")
                
                # Display signals in plot container
                if self.plot_container:
                    self.logger.info(f"Calling plot_container.display_signals with {len(target_signals)} signals")
                    
                    try:
                        plot_result = self.plot_container.display_signals(data_manager, file_path, target_signals, hr_params)
                        self.logger.info(f"plot_container.display_signals returned: {plot_result}")
                    except Exception as e:
                        self.logger.error(f"Error in plot_container.display_signals: {e}", exc_info=True)
                    
                    # Update navigation controls with duration from data
                    if file_path and target_signals:
                        try:
                            # Get duration from first available signal
                            first_signal_name = target_signals[0]
                            signal = data_manager.get_trace(file_path, first_signal_name)
                            if signal and len(signal.time) > 1:
                                duration = float(signal.time[-1] - signal.time[0])
                                self.logger.info(f"Calculated duration from signal '{first_signal_name}': {duration:.1f}s")
                                self._set_duration(duration)
                                # Also set duration in plot container
                                if self.plot_container:
                                    self.plot_container.set_duration(duration)
                            else:
                                self.logger.warning(f"Could not calculate duration - signal '{first_signal_name}' has insufficient data")
                        except Exception as e:
                            self.logger.warning(f"Could not calculate duration from signals: {e}")
                else:
                    self.logger.error("plot_container is None!")
                
                # Apply tab-specific customizations
                self._customize_for_tab()
                
                self.is_data_loaded = True
                self.data_updated.emit()
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error displaying signals: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            return False
    
    def _on_start_time_changed(self, value: int):
        """Handle start time change from spinbox."""
        self.start_time = float(value)
        self.position_slider.setValue(value)
        
        # Update time label
        if self.time_label:
            self.time_label.setText(f"{value}.0s")
        
        # Notify plot container to reload data
        if self.plot_container:
            self.plot_container.set_time_window(self.start_time, self.chunk_size)
            
        # Refresh comment markers for new time window
        self.refresh_comment_markers()
        
        # Emit signal for other components
        self.time_changed.emit(self.start_time)
    
    def _on_chunk_size_changed(self, value: int):
        """Handle chunk size change from spinbox."""
        self.chunk_size = float(value)
        self._set_duration(self.duration)  # Update ranges
        
        # Notify plot container
        if self.plot_container:
            self.plot_container.set_time_window(self.start_time, self.chunk_size)
            
        # Refresh comment markers for new time window
        self.refresh_comment_markers()
        
        # Emit signal for other components
        self.chunk_size_changed.emit(self.chunk_size)
    
    def _on_slider_changed(self, value: int):
        """Handle position slider change with throttling for better performance."""
        # Update UI immediately for responsiveness
        self.start_time = float(value)
        self.start_spinbox.setValue(value)
        
        if self.time_label:
            self.time_label.setText(f"{value}.0s")
        
        # Store the value and start/restart timer for throttling
        self.pending_slider_value = value
        self.slider_timer.start(150)  # 150ms delay for smooth sliding
        
    def _apply_slider_change(self):
        """Apply the pending slider change to plots (throttled)."""
        if self.pending_slider_value is not None:
            value = self.pending_slider_value
            self.pending_slider_value = None
            
            # Update plot container with throttled value
            if self.plot_container:
                self.plot_container.set_time_window(float(value), self.chunk_size)
            
            # Emit signal for other components
            self.time_changed.emit(float(value))
    
    def _go_previous_chunk(self):
        """Navigate to previous chunk."""
        new_start = max(0, self.start_time - self.chunk_size)
        self.start_spinbox.setValue(int(new_start))
    
    def _go_next_chunk(self):
        """Navigate to next chunk."""
        max_start = self.duration - self.chunk_size
        new_start = min(max_start, self.start_time + self.chunk_size)
        self.start_spinbox.setValue(int(new_start))
    
    def _set_duration(self, duration: float):
        """Set the total duration and update control ranges."""
        self.logger.debug(f"Setting duration to {duration}s (previous: {self.duration}s)")
        self.duration = duration
        max_start = max(0, int(duration - self.chunk_size))
        self.logger.debug(f"Calculated max_start: {max_start} (chunk_size: {self.chunk_size}s)")
        
        if self.start_spinbox:
            self.start_spinbox.setRange(0, max_start)
            self.logger.debug(f"Updated start_spinbox range to 0-{max_start}")
        if self.position_slider:
            self.position_slider.setRange(0, max_start)
            self.logger.debug(f"Updated position_slider range to 0-{max_start}")

    @abstractmethod
    def _customize_for_tab(self) -> None:
        """
        Tab-specific customization after signals are displayed.
        Called by display_signals() method. Must be implemented by subclasses.
        """
        pass
    
    # ================================
    # PARAMETER MANAGEMENT
    # ================================
    
    def update_parameters(self, new_params: Dict, emit_signal: bool = True) -> None:
        """Update tab parameters and optionally emit signal."""
        self.current_parameters.update(new_params)
        
        if emit_signal:
            self.parameters_changed.emit(self.current_parameters.copy())
            
        self.logger.debug(f"Parameters updated: {new_params}")
    
    def get_current_parameters(self) -> Dict:
        """Get current tab parameters."""
        return self.current_parameters.copy()
    
    # ================================
    # COMMENT INTEGRATION (read-only)
    # ================================
    
    def get_current_comments(self) -> List:
        """Get current comments for the active file (read-only access)."""
        if not self.session or not self.session.file_path:
            return []
        return self.comment_manager.get_all_comments_for_file(self.session.file_path)
    
    def get_comments_in_time_range(self, start_time: float, end_time: float) -> List:
        """Get comments within a specific time range using optimized binary search."""
        if not self.session or not self.session.file_path:
            return []
        return self.comment_manager.get_comments_in_time_window(
            self.session.file_path, start_time, end_time
        )
    
    def refresh_comment_markers(self):
        """Request PlotContainer to refresh comment markers display."""
        if self.plot_container and hasattr(self.plot_container, 'refresh_comment_display'):
            # Get current time window
            start_time = getattr(self, 'start_time', 0.0)
            chunk_size = getattr(self, 'chunk_size', 60.0)
            
            # Get comments for current window using optimized query
            visible_comments = self.get_comments_in_time_range(start_time, start_time + chunk_size)
            
            # Tell PlotContainer to render these comments
            self.plot_container.refresh_comment_display(visible_comments)
            self.logger.debug(f"Refreshed {len(visible_comments)} comment markers for time window")
    
    def _on_comment_changed(self, file_path: str, *args):
        """Handle comment changes (add/update/remove) by refreshing markers."""
        # Only refresh if the change affects our current file
        if self.session and self.session.file_path == file_path:
            self.refresh_comment_markers()
            self.logger.debug(f"Comment markers refreshed due to comment change in {file_path}")
    
    def navigate_to_comment_time(self, time_sec: float):
        """Navigate to specific comment time. Available in all visualization tabs."""
        self.logger.info(f"Navigating to comment time: {time_sec:.2f}s")
        
        # Calculate new start time to center the comment
        # Use half chunk size to center the comment in the view
        half_chunk = self.chunk_size / 2
        new_start_time = max(0, time_sec - half_chunk)
        
        # Ensure we don't exceed duration
        if hasattr(self, 'duration') and new_start_time + self.chunk_size > self.duration:
            new_start_time = max(0, self.duration - self.chunk_size)
        
        self.logger.debug(f"Calculated new start time: {new_start_time:.2f}s (chunk_size: {self.chunk_size}s)")
        
        # Update the spinbox which will trigger the proper navigation chain
        if self.start_spinbox:
            self.start_spinbox.setValue(int(new_start_time))
            self.logger.debug(f"Navigation completed to comment time: {time_sec:.2f}s")
    
    # ================================
    # EXPORT SUPPORT
    # ================================
    
    def get_export_data(self) -> Optional[Dict]:
        """
        Get data for export. Can be overridden by subclasses.
        
        Returns:
            Dictionary with exportable data or None if not available
        """
        if not self.is_data_loaded:
            return None
            
        return {
            'tab_type': self.__class__.__name__,
            'session_id': self.session.session_id,
            'file_path': self.session.file_path,
            'signals': self.current_signals.copy(),
            'parameters': self.current_parameters.copy()
        }
    
    # ================================
    # CLEANUP METHODS
    # ================================
    
    def clear_displays(self) -> None:
        """Clear all plot displays."""
        if self.plot_container and hasattr(self.plot_container, 'clear_plots'):
            self.plot_container.clear_plots()
        self.logger.debug("Plot displays cleared")
    
    def reset_tab(self) -> None:
        """Reset tab to initial state."""
        self.is_data_loaded = False
        self.current_signals.clear()
        self.current_parameters.clear()
        self.clear_displays()
        self.logger.debug(f"{self.__class__.__name__} reset")
    
    def cleanup(self) -> None:
        """Cleanup when tab is being destroyed."""
        try:
            # Disconnect session signals
            if self.session:
                self.session.session_ready.disconnect(self._on_session_ready)
                if hasattr(self.session, 'data_loaded'):
                    self.session.data_loaded.disconnect(self._on_session_data_loaded)
            
            # Reset tab
            self.reset_tab()
            
            self.logger.debug(f"{self.__class__.__name__} cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")