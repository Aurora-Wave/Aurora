"""
MainWindow para Aurora2.0 - Contenedor minimalista de tabs
Cada tab maneja su propia lógica de señales de forma completamente autónoma.
"""

from PySide6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QMessageBox, QDialog
from PySide6.QtGui import QAction
from Pyside.core import get_user_logger
from Pyside.data.data_manager import DataManager

# Imports de tabs - cada uno maneja solo visualización
from Pyside.ui.viewer_tab_new import ViewerTabNew
from Pyside.ui.event_tab_new import EventTabNew
from Pyside.ui.analysis_tab_new import AnalysisTabNew
from Pyside.ui.utils.error_handler import error_handler
from Pyside.ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from Pyside.processing.csv_exporter_horizontal import CSVExporterHorizontal

import csv  # CSV writing
from Pyside.processing.interval_extractor import extract_event_intervals  # event intervals
from Pyside.ui.widgets.export_selection_dialog import ExportSelectionDialog  # selection dialog


class MainWindow(QMainWindow):
    """
    MainWindow para Aurora2.0 con separación de responsabilidades.
    
    Responsabilidades:
    - UI Management: Menu bar, botones, dialogs
    - Data Management: DataManager centralizado 
    - Tab Management: Contenedor de tabs de visualización
    
    Arquitectura corregida:
    - MainWindow: UI + DataManager centralizado
    - ViewerTab: Solo PlotContainerWidget para visualización
    - AnalysisTab: Solo plots de análisis (futuro)
    - EventTab: Solo plots de eventos (futuro)
    """
    
    def __init__(self):
        """Inicializar MainWindow con DataManager centralizado."""
        super().__init__()
        self.setWindowTitle("Aurora2.0 - Signal Analysis")
        self.setMinimumSize(1400, 900)
        
        # Logger
        self.logger = get_user_logger(self.__class__.__name__)
        self.logger.info("Aurora2.0 MainWindow initialized")
        
        # Centralized DataManager
        self.data_manager = DataManager()
        self.current_file_path: str = ""
        
        # Tab widget como contenedor principal
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        
        # Crear tabs autónomos
        self._create_tabs()
        
        # Crear menu bar minimalista
        self._create_menu_bar()
        
        self.logger.info("Aurora2.0 ready - all logic delegated to individual tabs")
        
    def _create_tabs(self) -> None:
        """Crear todas las tabs del sistema."""
        # Viewer Tab - Visualización básica de señales
        self.viewer_tab = ViewerTabNew(self)
        self.tab_widget.addTab(self.viewer_tab, "📊 Viewer")
        
        # Event Tab - Visualización de eventos y comentarios
        self.event_tab = EventTabNew(self)
        self.tab_widget.addTab(self.event_tab, "📈 Events")
        
        # Analysis Tab - Análisis HR y parámetros
        self.analysis_tab = AnalysisTabNew(self)
        self.tab_widget.addTab(self.analysis_tab, "🔬 Analysis")
        
        self.logger.info(f"Created {self.tab_widget.count()} autonomous tabs")
        
    def _create_menu_bar(self) -> None:
        """Crear menu bar minimalista para carga de archivos."""
        menu_bar = self.menuBar()
        
        # Menu File
        file_menu = menu_bar.addMenu("File")
        
        # Open file action
        open_action = QAction("Open File...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        

        # Export action (placeholder)
        export_menu = menu_bar.addMenu("Export")
        export_act = QAction("Export CSV", self)
        export_act.triggered.connect(self._export_csv)
        export_menu.addAction(export_act)

    def _open_file_dialog(self) -> None:
        """Cargar archivo usando DataManager centralizado."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Signal File",
            "",
            "LabChart Files (*.adicht);;All Files (*)"
        )
        
        if file_path:
            try:
                self.logger.info(f"Loading file: {file_path}")
                
                # 1. Cargar archivo con DataManager centralizado
                self.data_manager.load_file(file_path)
                self.current_file_path = file_path
                
                # 2. Obtener canales disponibles
                available_channels = self.data_manager.get_available_channels(file_path)
                self.logger.info(f"Available channels: {len(available_channels)}")
                
                # 3. Mostrar dialog de selección de canales
                dialog = ChannelSelectionDialog(available_channels, self)
                if dialog.exec() == QDialog.Accepted:
                    selected_channels = dialog.get_selected_channels()
                    if selected_channels:
                        # 4. Enviar datos a todos los tabs (solo visualización)
                        
                        # ViewerTab - Visualización básica
                        self.viewer_tab.display_signals(
                            data_manager=self.data_manager,
                            file_path=file_path,
                            target_signals=selected_channels,
                            hr_params={}
                        )
                        self.logger.info(f"Data sent to ViewerTab: {len(selected_channels)} channels")
                        
                        # EventTab - Visualización de eventos
                        self.event_tab.display_signals(
                            data_manager=self.data_manager,
                            file_path=file_path,
                            target_signals=selected_channels,
                            hr_params={}
                        )
                        self.logger.info(f"Data sent to EventTab: {len(selected_channels)} channels")
                        
                        # AnalysisTab - Análisis HR
                        self.analysis_tab.display_signals(
                            data_manager=self.data_manager,
                            file_path=file_path,
                            target_signals=selected_channels,
                            hr_params={}
                        )
                        self.logger.info(f"Data sent to AnalysisTab: {len(selected_channels)} channels")
                    else:
                        self.logger.warning("No channels selected")
                else:
                    self.logger.info("Channel selection cancelled")
                    
            except Exception as e:
                self.logger.error(f"Failed to load file: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to load file:\\n{e}")
        
    # Métodos de conveniencia para acceso a tabs (opcional)
    def get_viewer_tab(self) -> ViewerTabNew:
        """Get viewer tab instance."""
        return self.viewer_tab
        
    def get_event_tab(self) -> EventTabNew:
        """Get event tab instance."""
        return self.event_tab
        
    def get_analysis_tab(self) -> AnalysisTabNew:
        """Get analysis tab instance."""
        return self.analysis_tab
    
    def _export_csv(self):
        """Export selected signal statistics to CSV."""
        return error_handler.safe_execute(self._export_csv_impl, "Exportar CSV")

    def _export_csv_impl(self):
        """Implementación protegida de exportación CSV en formato horizontal."""
        if not self.current_file_path:
            QMessageBox.warning(self, "Export", "No file loaded.")
            return

        path = self.current_file_path
        all_signals = self.data_manager.get_available_channels_for_export(path)

        # Create horizontal exporter - it will parse HR parameters from channel names
        exporter = CSVExporterHorizontal(self.data_manager)
        test_entries = exporter.extract_test_entries(path)
        unique_tests = [entry[0] for entry in test_entries]

        if not unique_tests:
            QMessageBox.warning(self, "Export", "No test events found in file.")
            return

        # Mostrar diálogo de selección
        dialog = ExportSelectionDialog(all_signals, unique_tests, self)
        if not dialog.exec():
            return

        sel_signals, sel_tests, segment_duration = dialog.get_selections()
        if not sel_signals:
            QMessageBox.warning(self, "Export", "No signals selected.")
            return

        # Seleccionar archivo de destino
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)"
        )
        if not save_path:
            return

        # Exportar usando el módulo horizontal
        try:
            exporter.export_to_csv_horizontal(
                path, sel_signals, sel_tests, test_entries, save_path, segment_duration
            )

            #self.session.log_action(
            #    f"CSV export successful (horizontal): {len(sel_signals)} signals, {len(sel_tests) if sel_tests else 1} tests",
            #    self.logger,
            #)

            QMessageBox.information(
                self,
                "Export Success",
                f"CSV exported successfully in horizontal format to:\n{save_path}\n\n"
                f"📊 {len(sel_tests) if sel_tests else 1} test instance(s) exported\n"
                f"📈 {len(sel_signals)} signal(s) included\n"
                f"🔄 Format: signal_mean_tiempoX, signal_max_tiempoX",
            )

        except Exception as ex:
            self.logger.error(f"Export error: {ex}", exc_info=True)
            QMessageBox.critical(
                self, "Export Error", f"Failed to export CSV:\n{str(ex)}"
            )