"""
New ViewerTab implementation using the modular PlotContainerWidget system.
Maintains compatibility with existing MainWindow interface while simplifying implementation.
"""

from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Signal

from .widgets.viewer_plot_container import ViewerPlotContainer
from Pyside.core import get_user_logger
import os


class ViewerTabNew(QWidget):
    """
    ViewerTab para Aurora2.0 - Solo maneja visualización de señales.
    
    Responsabilidades:
    - Contener PlotContainerWidget para visualización
    - Recibir datos del MainWindow para mostrar
    - Manejar interacciones de UI de plots
    
    NO maneja:
    - Carga de archivos (MainWindow)
    - Selección de canales (MainWindow) 
    - DataManager (MainWindow)
    """
    
    def __init__(self, main_window=None):
        super().__init__()
        self.logger = get_user_logger("ViewerTabNew")
        self.main_window = main_window  # Store reference but don't use BaseTab
        
        # Configuration (recibida de MainWindow)
        self.target_signals: List[str] = []
        self.hr_params: Dict = {}
        self.file_path: str = ""
        
        # UI Components
        self.plot_container: ViewerPlotContainer = None
        self.info_label: QLabel = None
        
        # Create our own layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(10)
        
        self.setup_ui()
        self.logger.info("ViewerTabNew initialized")
        
    def setup_ui(self):
        """Setup the UI using the modular plot container."""
        # Create UI with ViewerPlotContainer as main component
        
        # Info area
        self.info_label = QLabel("No file loaded")
        self.info_label.setStyleSheet("QLabel { font-weight: bold; color: #888; }")
        self.main_layout.addWidget(self.info_label)
        
        # Plot container
        self.plot_container = ViewerPlotContainer(self)
        self.main_layout.addWidget(self.plot_container)
        
        # Connect container signals to tab-level handling
        self.plot_container.time_changed.connect(self.on_time_changed)
        self.plot_container.chunk_size_changed.connect(self.on_chunk_size_changed)
        
    def load_data(self, data_manager, file_path: str, target_signals: List[str], hr_params: Dict = None):
        """
        Load data into the viewer. Main interface for integration with MainWindow.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the loaded file  
            target_signals: List of signal names to display
            hr_params: HR generation parameters
        """
        self.logger.info(f"Loading data: file={file_path}, signals={target_signals}")
        
        # Store configuration
        self.file_path = file_path
        self.target_signals = target_signals
        self.hr_params = hr_params or {}
        
        # Update info display
        filename = file_path.split('/')[-1].split('\\')[-1] if file_path else "Unknown"
        self.info_label.setText(f"File: {filename} | Signals: {', '.join(target_signals)}")
        
        # Configure plot container
        self.plot_container.set_data_context(data_manager, file_path, hr_params)
        self.plot_container.set_signals(target_signals)
        
        # Load initial chunk
        self.plot_container.load_chunk()
        
        self.logger.info("Data loading completed")
        
    def update_hr_params(self, hr_params: Dict, force_cache_refresh: bool = False):
        """
        Update HR generation parameters. Compatible with MainWindow interface.
        
        Args:
            hr_params: New HR parameters
            force_cache_refresh: Whether to force cache refresh (compatibility parameter)
        """
        self.logger.debug(f"Updating HR params: {hr_params}, force_refresh={force_cache_refresh}")
        
        self.hr_params = hr_params
        self.plot_container.update_hr_params(hr_params)
        
    def refresh_display(self):
        """Refresh the entire display. Used by MainWindow for updates."""
        self.logger.debug("Refreshing display")
        self.plot_container.refresh_display()
        
    def on_time_changed(self, new_time: float):
        """Handle time navigation change."""
        self.logger.debug(f"Time changed to: {new_time:.2f}s")
        
    def on_chunk_size_changed(self, new_chunk_size: float):
        """Handle chunk size change."""
        self.logger.debug(f"Chunk size changed to: {new_chunk_size:.2f}s")
        
    def get_current_time_range(self) -> tuple:
        """Get current visible time range. Used by MainWindow."""
        if self.plot_container:
            return (
                self.plot_container.start_time,
                self.plot_container.start_time + self.plot_container.chunk_size
            )
        return (0.0, 60.0)
        
    def get_current_chunk_size(self) -> float:
        """Get current chunk size. Used by MainWindow."""
        return self.plot_container.chunk_size if self.plot_container else 60.0
        
    def get_target_signals(self) -> List[str]:
        """Get currently displayed signals. Used by MainWindow."""
        return self.target_signals
        
    def set_chunk_size(self, chunk_size: float):
        """Set chunk size programmatically."""
        if self.plot_container:
            self.plot_container.chunk_size = chunk_size
            self.plot_container.chunk_spinbox.setValue(int(chunk_size))
            
    def navigate_to_time(self, time_sec: float):
        """Navigate to specific time."""
        if self.plot_container:
            self.plot_container.start_time = time_sec
            self.plot_container.start_spinbox.setValue(int(time_sec))
            self.plot_container.position_slider.setValue(int(time_sec))
            self.plot_container.load_chunk()
            
    def add_signal(self, signal_name: str):
        """Add a new signal to the display."""
        if signal_name not in self.target_signals:
            self.target_signals.append(signal_name)
            if self.plot_container:
                self.plot_container.add_plot(signal_name)
                
    def remove_signal(self, signal_name: str):
        """Remove a signal from the display."""
        if signal_name in self.target_signals:
            self.target_signals.remove(signal_name)
            if self.plot_container:
                plot = self.plot_container.get_plot_by_signal(signal_name)
                if plot:
                    self.plot_container.remove_plot(plot)
                    
    def get_plot_for_signal(self, signal_name: str):
        """Get plot widget for specific signal. Compatibility method."""
        if self.plot_container:
            return self.plot_container.get_plot_by_signal(signal_name)
        return None
        
    # Additional compatibility methods for MainWindow integration
    def clear_plots(self):
        """Clear all plots."""
        if self.plot_container:
            self.plot_container.clear_plots()
            
    def has_data(self) -> bool:
        """Check if tab has loaded data."""
        return bool(self.file_path and self.target_signals)
        
    def get_data_info(self) -> Dict:
        """Get information about loaded data."""
        return {
            'file_path': self.file_path,
            'target_signals': self.target_signals,
            'hr_params': self.hr_params,
            'duration': self.plot_container.duration if self.plot_container else 0.0
        }
        
    def export_current_view(self) -> Dict:
        """Export current view settings for session management."""
        if not self.plot_container:
            return {}
            
        return {
            'start_time': self.plot_container.start_time,
            'chunk_size': self.plot_container.chunk_size,
            'target_signals': self.target_signals,
            'hr_params': self.hr_params
        }
        
    def import_view_settings(self, settings: Dict):
        """Import view settings from session."""
        if not self.plot_container or not settings:
            return
            
        # Apply settings
        if 'start_time' in settings:
            self.navigate_to_time(settings['start_time'])
            
        if 'chunk_size' in settings:
            self.set_chunk_size(settings['chunk_size'])
            
        if 'target_signals' in settings:
            self.target_signals = settings['target_signals']
            self.plot_container.set_signals(self.target_signals)
            
        if 'hr_params' in settings:
            self.update_hr_params(settings['hr_params'])
            
    def display_signals(self, data_manager, file_path: str, target_signals: List[str], hr_params: Dict = None) -> None:
        """
        Mostrar señales en PlotContainer - Recibe datos del MainWindow.
        
        Este método solo maneja visualización:
        1. Recibir DataManager del MainWindow
        2. Actualizar UI info
        3. Configurar PlotContainer para mostrar datos
        
        Args:
            data_manager: DataManager centralizado del MainWindow
            file_path: Ruta del archivo cargado
            target_signals: Señales seleccionadas para mostrar
            hr_params: Parámetros de HR (opcional)
        """
        try:
            self.logger.info(f"Displaying signals: {len(target_signals)} channels")
            
            # 1. Guardar configuración
            self.file_path = file_path
            self.target_signals = target_signals
            self.hr_params = hr_params or {}
            
            # 2. Actualizar UI info
            filename = os.path.basename(file_path)
            self.info_label.setText(f"File: {filename} | Channels: {', '.join(target_signals)}")
            
            # 3. Configurar PlotContainer con datos del MainWindow
            self.plot_container.set_data_context(data_manager, file_path, self.hr_params)
            self.plot_container.set_signals(target_signals)
            
            self.logger.info(f"Signals displayed successfully: {len(target_signals)} channels")
            
        except Exception as e:
            self.logger.error(f"Failed to display signals: {e}", exc_info=True)
            self.info_label.setText(f"Error displaying signals: {e}")
            raise


# Compatibility class alias for gradual migration
ViewerTab = ViewerTabNew