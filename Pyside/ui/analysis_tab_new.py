"""
AnalysisTabNew implementation using the modular AnalysisPlotContainer system.
Follows the standard pattern: receives DataManager from MainWindow, handles only visualization.
"""

from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Signal
import numpy as np
import os

from .widgets.analysis_plot_container import AnalysisPlotContainer
from Pyside.core import get_user_logger


class AnalysisTabNew(QWidget):
    """
    AnalysisTab para Aurora2.0 - Solo maneja visualización de análisis HR.
    
    Responsabilidades:
    - Contener AnalysisPlotContainer para análisis de HR
    - Recibir datos del MainWindow para mostrar
    - Manejar interacciones de UI específicas de análisis
    - Gestionar parámetros de generación HR
    
    NO maneja:
    - Carga de archivos (MainWindow)
    - Selección de canales (MainWindow) 
    - DataManager (MainWindow)
    
    Sigue patrón estándar:
    - Recibe DataManager del MainWindow
    - Configura AnalysisPlotContainer con datos
    - Solo visualización y análisis, sin lógica de carga
    """
    
    # Signals for HR parameter changes (for potential MainWindow communication)
    hr_params_changed = Signal(dict)
    
    def __init__(self, main_window=None):
        super().__init__()
        self.logger = get_user_logger("AnalysisTabNew")
        self.main_window = main_window
        
        # Configuration (recibida de MainWindow)
        self.target_signals: List[str] = []
        self.hr_params: Dict = {}
        self.file_path: str = ""
        
        # UI Components
        self.plot_container: AnalysisPlotContainer = None
        self.info_label: QLabel = None
        
        # Create our own layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(10)
        
        self.setup_ui()
        self.logger.info("AnalysisTabNew initialized")
        
    def setup_ui(self):
        """Setup the UI using AnalysisPlotContainer as main component"""
        
        # Info area
        self.info_label = QLabel("No file loaded")
        self.info_label.setStyleSheet("QLabel { font-weight: bold; color: #888; }")
        self.main_layout.addWidget(self.info_label)
        
        # Analysis plot container with HR controls
        self.plot_container = AnalysisPlotContainer(self)
        self.main_layout.addWidget(self.plot_container)
        
        # Connect container signals to tab-level handling
        self.plot_container.time_changed.connect(self.on_time_changed)
        self.plot_container.chunk_size_changed.connect(self.on_chunk_size_changed)
        
        # Connect HR parameter changes for potential propagation
        # (In future, this could notify MainWindow to update other tabs)
        
    def display_signals(self, data_manager, file_path: str, target_signals: List[str], hr_params: Dict = None) -> None:
        """
        Mostrar señales en AnalysisPlotContainer - Recibe datos del MainWindow.
        
        Interface estándar para recibir datos del MainWindow:
        1. Recibir DataManager del MainWindow
        2. Actualizar UI info
        3. Configurar AnalysisPlotContainer para mostrar datos
        
        Args:
            data_manager: DataManager centralizado del MainWindow
            file_path: Ruta del archivo cargado
            target_signals: Señales seleccionadas para mostrar
            hr_params: Parámetros de HR (opcional)
        """
        try:
            self.logger.info(f"Displaying signals for analysis: {len(target_signals)} channels")
            
            # 1. Guardar configuración recibida del MainWindow
            self.file_path = file_path
            self.target_signals = target_signals
            self.hr_params = hr_params or {}
            
            # 2. Actualizar UI info específica del tab
            filename = os.path.basename(file_path)
            hr_info = f" | HR Params: {len(self.hr_params)} set" if self.hr_params else ""
            self.info_label.setText(f"Analysis - File: {filename} | Channels: {', '.join(target_signals)}{hr_info}")
            
            # 3. Configurar AnalysisPlotContainer con datos del MainWindow
            self.plot_container.set_data_context(data_manager, file_path, self.hr_params)
            self.plot_container.set_signals(target_signals)
            
            self.logger.info(f"Analysis signals displayed successfully: {len(target_signals)} channels")
            
        except Exception as e:
            self.logger.error(f"Failed to display analysis signals: {e}", exc_info=True)
            self.info_label.setText(f"Error displaying signals: {e}")
            raise
            
    def update_hr_params(self, hr_params: Dict, force_cache_refresh: bool = False):
        """
        Update HR generation parameters - Compatible with MainWindow interface.
        
        Args:
            hr_params: New HR parameters
            force_cache_refresh: Whether to force cache refresh (compatibility parameter)
        """
        self.logger.debug(f"Updating HR params: {hr_params}, force_refresh={force_cache_refresh}")
        
        self.hr_params = hr_params
        if self.plot_container:
            self.plot_container.update_hr_params(hr_params)
            
        # Emit signal for potential MainWindow communication
        self.hr_params_changed.emit(hr_params)
            
    def get_current_hr_params(self) -> Dict:
        """Get current HR parameters from plot container"""
        if self.plot_container:
            return self.plot_container.get_current_hr_params()
        return self.hr_params
        
    def refresh_display(self):
        """Refresh the entire display - Used by MainWindow for updates"""
        self.logger.debug("Refreshing analysis display")
        if self.plot_container:
            self.plot_container.refresh_display()
            
    def on_time_changed(self, new_time: float):
        """Handle time navigation change"""
        self.logger.debug(f"Time changed to: {new_time:.2f}s")
        
    def on_chunk_size_changed(self, new_chunk_size: float):
        """Handle chunk size change"""
        self.logger.debug(f"Chunk size changed to: {new_chunk_size:.2f}s")
        
    def get_current_time_range(self) -> tuple:
        """Get current visible time range - Used by MainWindow"""
        if self.plot_container:
            return (
                self.plot_container.start_time,
                self.plot_container.start_time + self.plot_container.chunk_size
            )
        return (0.0, 60.0)
        
    def get_current_chunk_size(self) -> float:
        """Get current chunk size - Used by MainWindow"""
        return self.plot_container.chunk_size if self.plot_container else 60.0
        
    def get_target_signals(self) -> List[str]:
        """Get currently displayed signals - Used by MainWindow"""
        return self.target_signals
        
    def set_chunk_size(self, chunk_size: float):
        """Set chunk size programmatically"""
        if self.plot_container:
            self.plot_container.chunk_size = chunk_size
            self.plot_container.chunk_spinbox.setValue(int(chunk_size))
            
    def navigate_to_time(self, time_sec: float):
        """Navigate to specific time"""
        if self.plot_container:
            self.plot_container.start_time = time_sec
            self.plot_container.start_spinbox.setValue(int(time_sec))
            self.plot_container.position_slider.setValue(int(time_sec))
            self.plot_container.load_chunk()
            
    def navigate_to_peak(self, direction: str = "next"):
        """Navigate to R-peak - AnalysisTab specific functionality"""
        if self.plot_container:
            if direction == "next":
                self.plot_container.navigate_to_next_peak()
            elif direction == "prev":
                self.plot_container.navigate_to_prev_peak()
                
    def regenerate_hr_signal(self):
        """Regenerate HR signal with current parameters - AnalysisTab specific"""
        if self.plot_container:
            self.plot_container.regenerate_hr_signal()
            
            # Emit updated parameters for potential MainWindow sync
            current_params = self.plot_container.get_current_hr_params()
            self.hr_params_changed.emit(current_params)
            
    def toggle_r_peaks_visibility(self):
        """Toggle R-peaks visibility - AnalysisTab specific"""
        if self.plot_container:
            self.plot_container.toggle_r_peaks_visibility()
            
    def set_hr_parameters(self, wavelet: str = None, level: int = None, min_rr: float = None):
        """Set specific HR parameters - AnalysisTab specific"""
        if not self.plot_container:
            return
            
        current_params = self.plot_container.get_current_hr_params()
        
        if wavelet is not None:
            current_params['wavelet'] = wavelet
        if level is not None:
            current_params['swt_level'] = level
        if min_rr is not None:
            current_params['min_rr_sec'] = min_rr
            
        self.plot_container.update_hr_params(current_params)
        self.hr_params_changed.emit(current_params)
        
    def add_signal(self, signal_name: str):
        """Add a new signal to the display"""
        if signal_name not in self.target_signals:
            self.target_signals.append(signal_name)
            if self.plot_container:
                self.plot_container.add_plot(signal_name)
                
    def remove_signal(self, signal_name: str):
        """Remove a signal from the display"""
        if signal_name in self.target_signals:
            self.target_signals.remove(signal_name)
            if self.plot_container:
                plot = self.plot_container.get_plot_by_signal(signal_name)
                if plot:
                    self.plot_container.remove_plot(plot)
                    
    def get_plot_for_signal(self, signal_name: str):
        """Get plot widget for specific signal - Compatibility method"""
        if self.plot_container:
            return self.plot_container.get_plot_by_signal(signal_name)
        return None
        
    def clear_plots(self):
        """Clear all plots"""
        if self.plot_container:
            self.plot_container.clear_plots()
            
    def has_data(self) -> bool:
        """Check if tab has loaded data"""
        return bool(self.file_path and self.target_signals)
        
    def get_data_info(self) -> Dict:
        """Get information about loaded data"""
        analysis_info = {}
        if self.plot_container:
            analysis_info = {
                'hr_params': self.plot_container.get_current_hr_params(),
                'r_peaks_visible': self.plot_container.r_peaks_visible,
                'hr_signal_generated': self.plot_container.current_hr_signal is not None
            }
            
        return {
            'file_path': self.file_path,
            'target_signals': self.target_signals,
            'hr_params': self.hr_params,
            'duration': self.plot_container.duration if self.plot_container else 0.0,
            'analysis_info': analysis_info
        }
        
    def export_current_view(self) -> Dict:
        """Export current view settings for session management"""
        if not self.plot_container:
            return {}
            
        return {
            'start_time': self.plot_container.start_time,
            'chunk_size': self.plot_container.chunk_size,
            'target_signals': self.target_signals,
            'hr_params': self.plot_container.get_current_hr_params() if self.plot_container else {},
            'r_peaks_visible': self.plot_container.r_peaks_visible if self.plot_container else True
        }
        
    def import_view_settings(self, settings: Dict):
        """Import view settings from session"""
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
            
        if 'r_peaks_visible' in settings and hasattr(self.plot_container, 'r_peaks_visible'):
            # Set visibility state
            target_state = settings['r_peaks_visible']
            current_state = self.plot_container.r_peaks_visible
            if target_state != current_state:
                self.plot_container.toggle_r_peaks_visibility()
                
    def get_current_hr_signal(self):
        """Get current HR signal object - AnalysisTab specific"""
        if self.plot_container:
            return self.plot_container.current_hr_signal
        return None
        
    def get_r_peaks(self) -> Optional[List[int]]:
        """Get current R-peaks - AnalysisTab specific"""
        hr_signal = self.get_current_hr_signal()
        if hr_signal and hasattr(hr_signal, 'r_peaks'):
            return hr_signal.r_peaks.tolist()
        return None
        
    def add_r_peak(self, sample_position: int):
        """Add R-peak at specific sample position - AnalysisTab specific"""
        hr_signal = self.get_current_hr_signal()
        if hr_signal and hasattr(hr_signal, 'add_peak'):
            hr_signal.add_peak(sample_position)
            self.plot_container.load_chunk()  # Refresh display
            
    def remove_r_peak(self, sample_position: int):
        """Remove R-peak at specific sample position - AnalysisTab specific"""
        hr_signal = self.get_current_hr_signal()
        if hr_signal and hasattr(hr_signal, 'r_peaks'):
            # Find closest peak and remove
            peaks = hr_signal.r_peaks
            if len(peaks) > 0:
                closest_idx = np.argmin(np.abs(peaks - sample_position))
                if hasattr(hr_signal, 'delete_peak'):
                    hr_signal.delete_peak(closest_idx)
                    self.plot_container.load_chunk()  # Refresh display


# Compatibility class alias for gradual migration
AnalysisTab = AnalysisTabNew