"""
EventsTab - Events visualization tab with horizontal layout: PlotContainer | CommentList
Inherits from VisualizationBaseTab for consistency with session system.
"""

from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Signal, Qt
import os

from aurora.ui.tabs.visualization_base_tab import VisualizationBaseTab
from aurora.ui.widgets.plot_container_widget import PlotContainerWidget
from aurora.ui.widgets.comment_list_widget import CommentListWidget
from aurora.core.session import Session


class EventsTab(VisualizationBaseTab):
    """
    Events tab with horizontal layout: PlotContainer | CommentList
    
    Layout:
    - Left side (70%): PlotContainerWidget for signal visualization
    - Right side (30%): CommentListWidget for comment management
    - QSplitter for resizing
    
    Inherits from VisualizationBaseTab:
    - Session-based data access
    - Standard tab lifecycle methods
    - Common signals and error handling
    """
    
    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        
        # Tab-specific components  
        self.comment_widget: CommentListWidget = None
        self.splitter: QSplitter = None
        self.info_label: QLabel = None
        # plot_container is now inherited from VisualizationBaseTab
        
        self.logger.info("EventsTab initialized")
        
    def setup_tab_specific_ui(self):
        """
        Setup horizontal layout with PlotContainer and CommentList.
        Required by VisualizationBaseTab.
        """
        # Info area - compact
        self.info_label = QLabel("Events Tab - No file loaded")
        self.info_label.setStyleSheet("QLabel { font-weight: bold; color: #888; font-size: 11px; }")
        self.info_label.setMaximumHeight(20)
        self.info_label.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.info_label)
        
        # Create horizontal splitter
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Plot container (from VisualizationBaseTab)
        self.splitter.addWidget(self.plot_container)
        
        # Right side: Comment widget  
        self.comment_widget = CommentListWidget(self)
        self.splitter.addWidget(self.comment_widget)
        
        # Set splitter proportions: 70% plots, 30% comments
        self.splitter.setStretchFactor(0, 7)  # Plots get more space
        self.splitter.setStretchFactor(1, 3)  # Comments get less space
        self.splitter.setSizes([700, 300])    # Initial sizes
        
        # Add splitter with stretch to take all space
        self.main_layout.addWidget(self.splitter, 1)
        
        # Connect signals between components
        self.connect_tab_signals()
        
    def connect_tab_signals(self):
        """Connect signals between plot container and comment widget"""
        # Navigation signals are handled by VisualizationBaseTab, not by individual plots
        
        # Comment widget signals
        if self.comment_widget:
            self.comment_widget.comment_time_navigate.connect(self.on_navigate_to_comment_time)
            self.comment_widget.comment_selected.connect(self.on_comment_selected)
        
    def update_tab_data(self, data_manager, file_path: str, **kwargs) -> bool:
        """
        Update tab with session data.
        Required by VisualizationBaseTab.
        
        Args:
            data_manager: DataManager instance from session
            file_path: Path to the data file
            **kwargs: Additional parameters from session config
        
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not data_manager:
                self.logger.warning("No data_manager provided")
                return False
                
            # Get target signals from session
            target_signals = self.session.selected_channels if self.session else []
            
            self.logger.info(f"Updating EventsTab with {len(target_signals)} signals")
            
            # Update UI info (EventsTab-specific)
            filename = os.path.basename(file_path) if file_path else "Unknown"
            self.info_label.setText(f"Events - File: {filename} | Channels: {', '.join(target_signals)}")
            
            # Configure CommentListWidget (right side) - EventsTab-specific
            if self.comment_widget:
                self.comment_widget.set_data_context(data_manager, file_path)
            
            # Data loading and plot display is handled by VisualizationBaseTab.display_signals()
            return True
            
        except Exception as e:
            error_msg = f"Failed to update EventsTab data: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            if self.info_label:
                self.info_label.setText(f"Error: {e}")
            return False
            
    def _customize_for_tab(self):
        """
        Post-display customizations specific to EventsTab.
        Required by VisualizationBaseTab.
        
        Called after data is loaded to apply EventsTab-specific configurations:
        - Enable comments for all plots
        - Configure synchronization between plots and comment panel
        - Apply default display settings
        """
        # Comments are now handled globally by VisualizationBaseTab and PlotContainer
        # No tab-specific comment setup needed
                
        self.logger.info("EventsTab customization completed")
        
    # Navigation is handled by VisualizationBaseTab, no per-tab handlers needed
        
    def on_navigate_to_comment_time(self, time_sec: float):
        """Handle navigation to comment time from CommentListWidget"""
        # Use base class navigation method (centers comment properly based on chunk_size)
        self.navigate_to_comment_time(time_sec)
        
    def on_comment_selected(self, comment):
        """Handle comment selection for visual feedback"""
        self.logger.debug(f"Comment selected: {comment.time:.2f}s - {comment.text[:30]}...")
        
    # Additional EventsTab-specific methods
    def get_current_time_range(self) -> tuple:
        """Get current visible time range"""
        if self.plot_container:
            return (
                self.plot_container.start_time,
                self.plot_container.start_time + self.plot_container.chunk_size
            )
        return (0.0, 60.0)
        
    def navigate_to_time(self, time_sec: float):
        """Navigate to specific time"""
        # Use base class navigation controls
        if self.start_spinbox:
            self.start_spinbox.setValue(int(time_sec))
            
    def add_signal(self, signal_name: str):
        """Add a new signal to the display"""
        if self.plot_container:
            self.plot_container.add_plot(signal_name)
                
    def refresh_display(self):
        """Refresh the entire display"""
        self.logger.debug("Refreshing EventsTab display")
        
        # Refresh plot container
        if self.plot_container:
            self.plot_container.load_chunk()
            
        # Refresh comment widget
        if self.comment_widget:
            self.comment_widget.refresh_comments()