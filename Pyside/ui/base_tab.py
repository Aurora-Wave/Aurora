"""
Base Tab Abstract Class for AuroraWave Application
Provides common functionality and interface for all visualization tabs.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QObject, Signal as QtSignal
from Pyside.core import get_user_logger, get_current_session
from Pyside.core.config_manager import get_config_manager


class BaseTab(QWidget, ABC):
    """
    Abstract base class for all visualization tabs in AuroraWave.
    
    Provides common functionality including:
    - Standardized initialization patterns
    - Parameter management
    - Logging and session management
    - Common update interface
    """
    
    # Signals for inter-tab communication
    parameters_changed = QtSignal(dict)  # Emitted when tab parameters change
    data_updated = QtSignal(str)  # Emitted when data is updated
    status_message = QtSignal(str)  # Emitted for status bar messages
    
    def __init__(self, parent=None):
        """Initialize base tab with common components."""
        super().__init__(parent)
        
        # Core components
        self.main_window = parent
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.config_manager = get_config_manager()
        
        # Data management
        self.data_manager = None
        self.file_path: Optional[str] = None
        
        # Layout components
        self.main_layout = QVBoxLayout(self)
        self.controls_layout = QHBoxLayout()
        
        # Common properties
        self._parameters: Dict[str, Any] = {}
        self._is_initialized: bool = False
        
        # Setup base UI
        self._setup_base_ui()
        
        # Connect base signals
        self._connect_base_signals()
        
        self.logger.debug(f"{self.__class__.__name__} initialized")
    
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
        
        # Create tab-specific UI
        self.setup_ui()
    
    def _connect_base_signals(self) -> None:
        """Connect common signals."""
        # Connect parameter changes to update mechanism
        self.parameters_changed.connect(self._on_parameters_changed)
    
    @abstractmethod
    def setup_ui(self) -> None:
        """Setup tab-specific UI components. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def update_tab_data(self, data_manager, file_path: str, **kwargs) -> bool:
        """
        Update tab with new data. Must be implemented by subclasses.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the data file
            **kwargs: Additional parameters specific to the tab
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """
        Get current tab parameters. Must be implemented by subclasses.
        
        Returns:
            Dictionary of current parameter values
        """
        pass
    
    @abstractmethod
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Set tab parameters. Must be implemented by subclasses.
        
        Args:
            parameters: Dictionary of parameter values to set
        """
        pass
    
    def update_data(self, data_manager, file_path: str, **kwargs) -> bool:
        """
        Standardized data update method with error handling and logging.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the data file
            **kwargs: Additional parameters
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            self.logger.info(f"Updating {self.__class__.__name__} with file: {file_path}")
            
            # Store references
            self.data_manager = data_manager
            self.file_path = file_path
            
            # Call subclass-specific update
            success = self.update_tab_data(data_manager, file_path, **kwargs)
            
            if success:
                self._is_initialized = True
                self.data_updated.emit(file_path)
                self.logger.debug(f"{self.__class__.__name__} update completed successfully")
            else:
                self.logger.warning(f"{self.__class__.__name__} update failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating {self.__class__.__name__}: {e}", exc_info=True)
            self.status_message.emit(f"Error updating {self.__class__.__name__}: {str(e)}")
            return False
    
    def update_parameters(self, parameters: Dict[str, Any], emit_signal: bool = True) -> None:
        """
        Update tab parameters with validation and notification.
        
        Args:
            parameters: New parameter values
            emit_signal: Whether to emit parameters_changed signal
        """
        try:
            # Validate parameters if method exists
            if hasattr(self, 'validate_parameters'):
                parameters = self.validate_parameters(parameters)
            
            # Store old parameters for comparison
            old_parameters = self._parameters.copy()
            
            # Update parameters
            self.set_parameters(parameters)
            self._parameters.update(parameters)
            
            # Emit signal if requested and parameters changed
            if emit_signal and parameters != old_parameters:
                self.parameters_changed.emit(parameters)
                
            self.logger.debug(f"Parameters updated: {parameters}")
            
        except Exception as e:
            self.logger.error(f"Error updating parameters: {e}", exc_info=True)
    
    def _on_parameters_changed(self, parameters: Dict[str, Any]) -> None:
        """Handle parameter changes. Can be overridden by subclasses."""
        self.logger.debug(f"Parameters changed: {parameters}")
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        Get current status information for the tab.
        
        Returns:
            Dictionary containing status information
        """
        return {
            'tab_name': self.__class__.__name__,
            'initialized': self._is_initialized,
            'file_path': self.file_path,
            'parameters': self.get_current_parameters(),
            'data_loaded': self.data_manager is not None
        }
    
    def reset_tab(self) -> None:
        """Reset tab to initial state. Can be overridden by subclasses."""
        self.data_manager = None
        self.file_path = None
        self._parameters.clear()
        self._is_initialized = False
        
        # Clear any plots or data displays
        if hasattr(self, 'clear_displays'):
            self.clear_displays()
            
        self.logger.debug(f"{self.__class__.__name__} reset")
    
    def save_tab_state(self) -> Dict[str, Any]:
        """
        Save current tab state for session persistence.
        
        Returns:
            Dictionary containing tab state
        """
        return {
            'parameters': self.get_current_parameters(),
            'file_path': self.file_path,
            'tab_type': self.__class__.__name__
        }
    
    def restore_tab_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore tab state from saved data.
        
        Args:
            state: Saved tab state
            
        Returns:
            True if restoration was successful, False otherwise
        """
        try:
            if 'parameters' in state:
                self.update_parameters(state['parameters'], emit_signal=False)
            
            self.logger.debug(f"Tab state restored for {self.__class__.__name__}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring tab state: {e}", exc_info=True)
            return False
    
    def get_export_data(self) -> Optional[Dict[str, Any]]:
        """
        Get data suitable for export. Can be overridden by subclasses.
        
        Returns:
            Dictionary of exportable data or None if not applicable
        """
        return None
    
    def cleanup(self) -> None:
        """Clean up resources. Can be overridden by subclasses."""
        self.reset_tab()
        self.logger.debug(f"{self.__class__.__name__} cleanup completed")


class VisualizationTab(BaseTab):
    """
    Extended base class for tabs that display signal visualizations.
    
    Provides additional functionality for plot management and signal handling.
    """
    
    def __init__(self, parent=None):
        """Initialize visualization tab with plotting support."""
        super().__init__(parent)
        
        # Plot management
        self.plots: List = []
        self.plot_data: Dict[str, Any] = {}
        
        # Signal-specific parameters
        self.chunk_size: float = 60.0  # Default chunk size in seconds
        self.current_signals: List[str] = []
    
    @abstractmethod
    def create_plots(self) -> None:
        """Create visualization plots. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def update_plots(self) -> None:
        """Update plot displays. Must be implemented by subclasses."""
        pass
    
    def clear_displays(self) -> None:
        """Clear all plot displays."""
        for plot in self.plots:
            if hasattr(plot, 'clear'):
                plot.clear()
        
        self.plot_data.clear()
        self.logger.debug("Plot displays cleared")
    
    def set_chunk_size(self, chunk_size: float) -> None:
        """
        Set the chunk size for signal visualization.
        
        Args:
            chunk_size: Chunk size in seconds
        """
        if chunk_size > 0:
            old_chunk_size = self.chunk_size
            self.chunk_size = chunk_size
            
            # Update parameters dictionary
            self._parameters['chunk_size'] = chunk_size
            
            # Emit signal if changed
            if chunk_size != old_chunk_size:
                self.parameters_changed.emit({'chunk_size': chunk_size})
    
    def get_current_signals(self) -> List[str]:
        """Get currently displayed signal names."""
        return self.current_signals.copy()
    
    def set_current_signals(self, signals: List[str]) -> None:
        """Set currently displayed signal names."""
        self.current_signals = signals.copy()
        self._parameters['signals'] = signals