"""
EventTabNew - Layout horizontal con EventPlotContainer y CommentListWidget
Implementación simple y limpia siguiendo el patrón estándar.
"""

from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Signal, Qt

from .widgets.event_plot_container import EventPlotContainer
from .widgets.comment_list_widget import CommentListWidget
from Pyside.core import get_user_logger
import os


class EventTabNew(QWidget):
    """
    EventTab con layout horizontal: EventPlotContainer | CommentListWidget
    
    Layout simple y limpio:
    - Izquierda: EventPlotContainer para visualización de eventos
    - Derecha: CommentListWidget para gestión de comentarios
    - Splitter horizontal para redimensionar
    
    Responsabilidades:
    - Layout horizontal con splitter
    - Integración entre plots y comentarios  
    - Recibir datos del MainWindow
    - Navegación entre comentarios y plots
    
    Sigue patrón estándar:
    - display_signals() para recibir datos del MainWindow
    - Solo visualización, sin lógica de carga
    """
    
    def __init__(self, main_window=None):
        super().__init__()
        self.logger = get_user_logger("EventTabNew")
        self.main_window = main_window
        
        # Configuration (recibida de MainWindow)
        self.target_signals: List[str] = []
        self.hr_params: Dict = {}
        self.file_path: str = ""
        
        # UI Components
        self.plot_container: EventPlotContainer = None
        self.comment_widget: CommentListWidget = None
        self.info_label: QLabel = None
        
        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(3)  # Reducir espaciado
        
        self.setup_ui()
        self.logger.info("EventTabNew initialized with horizontal layout")
        
    def setup_ui(self):
        """Setup horizontal layout with EventPlotContainer and CommentListWidget"""
        
        # Info area - compacta
        self.info_label = QLabel("No file loaded")
        self.info_label.setStyleSheet("QLabel { font-weight: bold; color: #888; font-size: 11px; }")
        self.info_label.setMaximumHeight(20)  # Limitar altura máxima
        self.info_label.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.info_label)
        
        # Create horizontal splitter
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Event plot container
        self.plot_container = EventPlotContainer(self)
        self.splitter.addWidget(self.plot_container)
        
        # Right side: Comment widget
        self.comment_widget = CommentListWidget(self)
        self.splitter.addWidget(self.comment_widget)
        
        # Set splitter proportions: 70% plots, 30% comments
        self.splitter.setStretchFactor(0, 7)  # Plots get more space
        self.splitter.setStretchFactor(1, 3)  # Comments get less space
        self.splitter.setSizes([700, 300])     # Initial sizes
        
        # Agregar splitter con stretch para tomar todo el espacio
        self.main_layout.addWidget(self.splitter, 1)  # stretch factor = 1
        
        # Connect signals between components
        self.connect_signals()
        
    def connect_signals(self):
        """Connect signals between plot container and comment widget"""
        # Plot container signals
        if self.plot_container:
            self.plot_container.time_changed.connect(self.on_time_changed)
            self.plot_container.chunk_size_changed.connect(self.on_chunk_size_changed)
        
        # Comment widget signals
        if self.comment_widget:
            self.comment_widget.comment_time_navigate.connect(self.on_navigate_to_comment_time)
            self.comment_widget.comment_selected.connect(self.on_comment_selected)
        
    def display_signals(self, data_manager, file_path: str, target_signals: List[str], hr_params: Dict = None) -> None:
        """
        Display signals in horizontal layout - recibe datos del MainWindow.
        
        Interface estándar para recibir datos del MainWindow:
        1. Recibir DataManager del MainWindow
        2. Actualizar UI info
        3. Configurar EventPlotContainer y CommentListWidget
        
        Args:
            data_manager: DataManager centralizado del MainWindow
            file_path: Ruta del archivo cargado
            target_signals: Señales seleccionadas para mostrar
            hr_params: Parámetros de HR (opcional)
        """
        try:
            self.logger.info(f"Displaying signals in horizontal layout: {len(target_signals)} channels")
            
            # 1. Guardar configuración recibida del MainWindow
            self.file_path = file_path
            self.target_signals = target_signals
            self.hr_params = hr_params or {}
            
            # 2. Actualizar UI info específica del tab
            filename = os.path.basename(file_path)
            self.info_label.setText(f"Events - File: {filename} | Channels: {', '.join(target_signals)}")
            
            # 3. Configurar EventPlotContainer (lado izquierdo)
            if self.plot_container:
                self.plot_container.set_data_context(data_manager, file_path, self.hr_params)
                self.plot_container.set_signals(target_signals)
            
            # 4. Configurar CommentListWidget (lado derecho)
            if self.comment_widget:
                self.comment_widget.set_data_context(data_manager, file_path)
            
            self.logger.info(f"Horizontal layout configured successfully: plots + comments")
            
        except Exception as e:
            self.logger.error(f"Failed to setup horizontal layout: {e}", exc_info=True)
            self.info_label.setText(f"Error setting up display: {e}")
            raise
            
    def update_hr_params(self, hr_params: Dict, force_cache_refresh: bool = False):
        """
        Update HR generation parameters - Compatible with MainWindow interface.
        Updates both plot container and comment widget if needed.
        
        Args:
            hr_params: New HR parameters
            force_cache_refresh: Whether to force cache refresh (compatibility parameter)
        """
        self.logger.debug(f"Updating HR params: {hr_params}, force_refresh={force_cache_refresh}")
        
        self.hr_params = hr_params
        
        # Update plot container
        if self.plot_container:
            self.plot_container.update_hr_params(hr_params)
            
        # Comment widget doesn't need HR params directly, but may need refresh
        if force_cache_refresh and self.comment_widget:
            self.comment_widget.refresh_comments()
            
    def refresh_display(self):
        """Refresh the entire display - Used by MainWindow for updates"""
        self.logger.debug("Refreshing horizontal layout display")
        
        # Refresh plot container
        if self.plot_container:
            self.plot_container.refresh_display()
            
        # Refresh comment widget
        if self.comment_widget:
            self.comment_widget.refresh_comments()
            
    def on_time_changed(self, new_time: float):
        """Handle time navigation change"""
        self.logger.debug(f"Time changed to: {new_time:.2f}s")
        
    def on_chunk_size_changed(self, new_chunk_size: float):
        """Handle chunk size change"""
        self.logger.debug(f"Chunk size changed to: {new_chunk_size:.2f}s")
        
    def on_navigate_to_comment_time(self, time_sec: float):
        """Handle navigation to comment time from CommentListWidget"""
        if self.plot_container:
            # Navigate plot container to comment time (center comment with 30s before)
            new_start_time = max(0, time_sec - 30)
            self.plot_container.set_position(new_start_time)
            self.plot_container.load_chunk()
            
        self.logger.debug(f"Navigated to comment time: {time_sec:.2f}s")
        
    def on_comment_selected(self, comment):
        """Handle comment selection for visual feedback"""
        # Could add highlighting or other visual feedback in the future
        self.logger.debug(f"Comment selected: {comment.time:.2f}s - {comment.text[:30]}...")
        
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
            
    def navigate_to_event(self, event_dict: Dict):
        """Navigate to specific event - EventTab specific functionality"""
        if self.plot_container:
            self.plot_container.navigate_to_event(event_dict)
            
    def search_events(self, search_term: str):
        """Search events - EventTab specific functionality"""
        if self.plot_container:
            self.plot_container.filter_events(search_term)
            
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
        return {
            'file_path': self.file_path,
            'target_signals': self.target_signals,
            'hr_params': self.hr_params,
            'duration': self.plot_container.duration if self.plot_container else 0.0,
            'events_count': len(self.plot_container.current_events) if self.plot_container else 0,
            'filtered_events_count': len(self.plot_container.filtered_events) if self.plot_container else 0
        }
        
    def export_current_view(self) -> Dict:
        """Export current view settings for session management"""
        if not self.plot_container:
            return {}
            
        return {
            'start_time': self.plot_container.start_time,
            'chunk_size': self.plot_container.chunk_size,
            'target_signals': self.target_signals,
            'hr_params': self.hr_params,
            'search_filter': self.plot_container.search_edit.text() if self.plot_container.search_edit else "",
            'show_all_comments': self.plot_container.show_all_comments.isChecked() if self.plot_container.show_all_comments else True
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
            
        if 'search_filter' in settings and self.plot_container.search_edit:
            self.plot_container.search_edit.setText(settings['search_filter'])
            
        if 'show_all_comments' in settings and self.plot_container.show_all_comments:
            self.plot_container.show_all_comments.setChecked(settings['show_all_comments'])
            
    def get_events_in_range(self, start_time: float, end_time: float) -> List[Dict]:
        """Get events within specified time range - EventTab specific"""
        if not self.plot_container or not self.plot_container.filtered_events:
            return []
            
        return [
            event for event in self.plot_container.filtered_events
            if start_time <= event.get('t_evento', 0) <= end_time
        ]
        
    def get_all_events(self) -> List[Dict]:
        """Get all loaded events - EventTab specific"""
        if not self.plot_container:
            return []
        return self.plot_container.current_events
        
    def get_filtered_events(self) -> List[Dict]:
        """Get currently filtered events - EventTab specific"""
        if not self.plot_container:
            return []
        return self.plot_container.filtered_events


# Compatibility class alias for gradual migration
EventTab = EventTabNew