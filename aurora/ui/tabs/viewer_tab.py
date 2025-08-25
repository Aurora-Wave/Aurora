"""
ViewerTab - Session-based signal visualization tab.
Simplified implementation for the new aurora session system.
"""

from typing import List, Dict, Optional
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Signal
import logging
import os

from aurora.core.session import Session
from aurora.ui.tabs.visualization_base_tab import VisualizationBaseTab
from aurora.ui.widgets.plot_container_widget import PlotContainerWidget


class ViewerTab(VisualizationBaseTab):
    """
    ViewerTab for Aurora - Simple signal visualization using sessions.
    
    Responsibilities:
    - Display signals from session data
    - Show basic file information
    - Handle time navigation and chunk size changes
    - Provide clean interface for signal viewing
    
    Uses session-based architecture:
    - Receives Session object instead of DataManager directly
    - Session contains isolated DataManager and configuration
    - No MainWindow dependency
    """
    
    # Additional signals specific to ViewerTab
    time_navigation_requested = Signal(float)  # Emitted when user requests time navigation
    
    def __init__(self, session: Session, parent=None):
        """Initialize ViewerTab with Session."""
        super().__init__(session, parent)
        
        # ViewerTab specific components
        self.info_label: QLabel = None
        # plot_container is now inherited from VisualizationBaseTab
        
        self.logger.info(f"ViewerTab initialized for session {session.session_id}")
        
    def setup_tab_specific_ui(self):
        """Setup ViewerTab-specific UI components."""
        # Info area showing current file and signals
        self.info_label = QLabel("No file loaded")
        self.info_label.setStyleSheet("QLabel { font-weight: bold; color: #888; padding: 5px; }")
        
        # Add info label to controls layout (inherited from base)
        self.controls_layout.addWidget(self.info_label)
        
        # Add the plot container from base class to main layout
        # (plot_container is already created in VisualizationBaseTab)
        self.main_layout.addWidget(self.plot_container)
        
        # Connect plot container signals to tab-specific handlers
        if self.plot_container:
            # Navigation is now handled by VisualizationBaseTab, no need to connect here
            pass
    
    def update_tab_data(self, data_manager, file_path: str, **kwargs) -> bool:
        """
        Implementation of abstract method from VisualizationBaseTab.
        
        Args:
            data_manager: DataManager instance from session
            file_path: Path to the data file
            **kwargs: Contains target_signals and configuration
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            target_signals = kwargs.get('target_signals', [])
            hr_params = kwargs.get('hr_params', {})
            
            if not target_signals:
                self.logger.warning("No target signals provided for ViewerTab")
                return False
            
            # Update info display (ViewerTab-specific)
            self._update_info_display(file_path, target_signals)
            
            # Data loading and plot display is handled by VisualizationBaseTab.display_signals()
            # We just return success here since this method is called FROM display_signals()
            
            self.logger.debug(f"ViewerTab data updated: {len(target_signals)} signals")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating ViewerTab data: {e}", exc_info=True)
            return False
    
    def _customize_for_tab(self) -> None:
        """
        ViewerTab-specific customization after signals are displayed.
        Called by the inherited display_signals() method.
        """
        # ViewerTab doesn't need special customization beyond basic display
        # This is where we could add ViewerTab-specific plot configurations if needed
        self.logger.debug("ViewerTab customization applied")
    
    def _update_info_display(self, file_path: str, target_signals: List[str]):
        """Update the info label with current file and signals information."""
        try:
            # Extract filename from path
            filename = os.path.basename(file_path) if file_path else "Unknown"
            
            # Create info text
            signals_text = ", ".join(target_signals) if target_signals else "None"
            if len(signals_text) > 50:  # Truncate if too long
                signals_text = signals_text[:47] + "..."
            
            info_text = f"File: {filename} | Signals: {signals_text}"
            
            # Update label
            if self.info_label:
                self.info_label.setText(info_text)
                
        except Exception as e:
            self.logger.error(f"Error updating info display: {e}")
            if self.info_label:
                self.info_label.setText("Error displaying file info")
    
    # ================================
    # SIGNAL HANDLERS
    # ================================
    
    # Navigation is now handled by VisualizationBaseTab
    # These methods are no longer needed
    
    # ================================
    # PUBLIC INTERFACE METHODS  
    # ================================
    
    def load_data(self, data_manager, file_path: str, target_signals: List[str], hr_params: Dict = None):
        """
        Legacy interface method for compatibility.
        Delegates to the standard display_signals() method.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the loaded file  
            target_signals: List of signal names to display
            hr_params: HR generation parameters
        """
        self.logger.info(f"ViewerTab load_data called (legacy interface)")
        
        # Use the standard interface
        hr_params = hr_params or {}
        return self.display_signals(data_manager, file_path, target_signals, hr_params)
    
    def update_hr_params(self, hr_params: Dict, force_cache_refresh: bool = False):
        """
        Legacy interface method for HR parameter updates.
        
        Args:
            hr_params: New HR parameters
            force_cache_refresh: Whether to force cache refresh
        """
        self.logger.info("ViewerTab HR parameters update requested (legacy interface)")
        
        # Update parameters using inherited method
        self.update_parameters(hr_params, emit_signal=True)
        
        # If we need to refresh the display
        if force_cache_refresh and self.session and self.session.data_manager:
            target_signals = self.session.selected_channels
            if target_signals:
                self.display_signals(
                    self.session.data_manager, 
                    self.session.file_path, 
                    target_signals, 
                    hr_params
                )
    
    # ================================
    # OVERRIDE METHODS FOR CUSTOMIZATION
    # ================================
    
    def get_export_data(self) -> Optional[Dict]:
        """
        Override to provide ViewerTab-specific export data.
        """
        base_export = super().get_export_data()
        
        # Add ViewerTab-specific export data
        if base_export:
            base_export.update({
                'tab_type': 'ViewerTab',
                'display_info': self.info_label.text() if self.info_label else None,
                'current_time': self.plot_container.start_time if self.plot_container else 0.0,
                'chunk_size': self.plot_container.chunk_size if self.plot_container else 60.0,
            })
        
        return base_export
    
    def reset_tab(self) -> None:
        """Override to include ViewerTab-specific reset logic."""
        super().reset_tab()
        
        # Reset ViewerTab-specific components
        if self.info_label:
            self.info_label.setText("No file loaded")
            
        if self.plot_container:
            self.plot_container.clear_plots()
            
        self.logger.debug("ViewerTab reset completed")
        
    def cleanup(self) -> None:
        """Override to include ViewerTab-specific cleanup."""
        try:
            # Navigation signals are handled by VisualizationBaseTab now
            # No plot container signals to disconnect
            
            # Call parent cleanup
            super().cleanup()
            
            self.logger.debug("ViewerTab cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during ViewerTab cleanup: {e}")