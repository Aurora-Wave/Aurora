import os

from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer

from Pyside.data.data_manager import DataManager
from Pyside.ui.viewer_tab import ViewerTab
from Pyside.ui.analysis_tab import AnalysisTab
from Pyside.ui.event_tab import EventTab
from Pyside.ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from Pyside.ui.widgets.export_selection_dialog import ExportSelectionDialog
from Pyside.core import get_user_logger, get_current_session, get_config_manager
from Pyside.processing.interval_extractor import extract_event_intervals
from Pyside.processing.csv_exporter import CSVExporter
from Pyside.processing.csv_exporter_horizontal import CSVExporterHorizontal

# Logging now handled by unified system in core.logging_config

# Suprimir warnings específicos de pyqtgraph
import warnings

warnings.filterwarnings("ignore", "overflow encountered in cast", RuntimeWarning)


class MainWindow(QMainWindow):
    """
    Main window for AuroraWave
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuroraWave")
        # self.setMinimumSize(1200, 800)

        # Initialize logging with user context
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.session.log_action("MainWindow initialized", self.logger)

        # Initialize configuration manager
        self.config_manager = get_config_manager()
        self.logger.info("MainWindow initialization started")

        # Data manager and current file
        self.data_manager = DataManager()
        self.current_file = None

        # Tab widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self.tab_widget)

        # Event(Tilt) and Analysis tabs
        self.event_tab = EventTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.tab_widget.addTab(self.event_tab, "Event Analysis")
        self.tab_widget.addTab(self.analysis_tab, "Signal Analysis")

        # Menubar
        # self._init_menubar():

        # Toolbar
        self._init_toolbar()

        # Timer para verificar el estado de la aplicación
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._check_application_health)
        self.health_timer.start(30000)  # Verificar cada 30 segundos

        # Apply startup configuration (load last session)
        self._apply_startup_configuration()

        self.session.log_action("MainWindow setup complete", self.logger)

    # Menubar definition
    # def _init_menubar(self):
    #    menu_bar = self.menuBar()
    #    file_menu = menu_bar.addMenu("Files")
    #    export_menu = menu_bar.addMenu("Export")
    #    # FIXME Conectar widget de exportacion
    #    # export_menu.addAction("Exportar marcadores", self.export_markers)

    # Toolbar definition
    # FIXME Mover los componentes de la toolbar a Menubar
    def _init_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        self.addToolBar(toolbar)
        # Load file action
        load_act = QAction("Load File", self)
        load_act.triggered.connect(self._load_file_dialog)
        toolbar.addAction(load_act)

        export_act = QAction("Export CSV", self)
        export_act.triggered.connect(self._export_csv)
        toolbar.addAction(export_act)

    def _apply_startup_configuration(self):
        """Apply saved configuration at startup."""
        try:
            self.logger.info("Applying startup configuration...")
            success = self.config_manager.apply_startup_configuration(self)
            if not success:
                self.logger.debug("No valid startup configuration found or applied")
        except Exception as e:
            self.logger.error(
                f"Failed to apply startup configuration: {e}", exc_info=True
            )

    def _check_application_health(self):
        """Verificación periódica del estado de la aplicación."""
        try:
            # Verificar que los componentes principales estén activos
            if not self.tab_widget:
                self.logger.warning("TabWidget no disponible")
                return

            # Verificar memoria y estado de data_manager
            if hasattr(self.data_manager, "current_data"):
                data_count = (
                    len(self.data_manager.current_data)
                    if self.data_manager.current_data
                    else 0
                )
                self.logger.debug(f"Health check: {data_count} archivos cargados")

        except Exception as e:
            self.logger.warning(f"Error en verificación de salud: {e}")

    def _safe_execute(self, func, *args, **kwargs):
        """Ejecutar una función de forma segura con manejo de errores."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error en {func.__name__}: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Error de Operación",
                f"Error en {func.__name__}:\n{str(e)}\n\nLa aplicación continúa funcionando.",
            )
            return None

    # FIXME Limpiar codigo y sacar la logica de las tablas, hacer un widget y configurar manipular todo desde ahi

    def _load_file_dialog(self):
        """Open a file dialog to select a signal file and load it."""
        try:
            self.session.log_action("File loading dialog requested", self.logger)
            return self._load_file_dialog_impl()
        except Exception as e:
            self.logger.error(f"File loading failed: {e}", exc_info=True)
            return None

    def _load_file_dialog_impl(self):
        """Implementación protegida de carga de archivos."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select signal file",
            "",
            "Signal files (*.adicht *.edf);;All files (*)",
        )
        if not path:
            return
        try:
            self.session.log_action(
                f"File selected: {os.path.basename(path)}", self.logger
            )
            self.logger.info(f"DataManager trying to open a file at {path}")
            self.data_manager.load_file(path)
            self.current_file = path
            self.session.log_action(
                f"File loaded successfully: {os.path.basename(path)}", self.logger
            )
            meta = self.data_manager.get_metadata(path)
            channels = meta.get("channels", [])
            if not channels:
                self.logger.error(f"No channels found in {path}")
                QMessageBox.warning(self, "No Channels", "No channels found in file.")
                return

            # Always include HR_GEN in the channel selection, even if not yet generated
            channels_for_selection = channels.copy()
            if "HR_GEN" not in channels_for_selection:
                channels_for_selection.append("HR_GEN")
                self.logger.debug(
                    "Added HR_GEN to channel selection (not yet generated)"
                )

            dlg = ChannelSelectionDialog(
                channels_for_selection, self, existing_channels=channels
            )
            if not dlg.exec():
                return
            selected = dlg.get_selected_channels()
            self.session.log_action(f"Channels selected: {selected}", self.logger)
            self.logger.info(
                f"{selected} channels selected for visualization on ViewerTab"
            )
            if not selected:
                QMessageBox.information(self, "No Selection", "No channels selected.")
                return

            # Generate HR_GEN if selected but doesn't exist in the original file
            if "HR_GEN" in selected and "HR_GEN" not in channels:
                self.logger.info(
                    "HR_GEN selected but not found in file. Generating with analysis tab default parameters..."
                )
                try:
                    # Generate HR_GEN with analysis tab default parameters for consistency
                    analysis_settings = self.config_manager.get_analysis_settings()
                    hr_params = {
                        "wavelet": analysis_settings.get("wavelet", "haar"),
                        "swt_level": analysis_settings.get("level", 4),
                        "min_rr_sec": analysis_settings.get("min_rr_sec", 0.6),
                    }
                    self.logger.debug(f"Using HR generation parameters: {hr_params}")
                    hr_signal = self.data_manager.get_trace(path, "HR_GEN", **hr_params)
                    self.logger.info(
                        "HR_GEN generated successfully and added to file metadata"
                    )
                    self.session.log_action(
                        f"HR_GEN generated at startup with params: {hr_params}",
                        self.logger,
                    )
                except Exception as e:
                    self.logger.error(f"Failed to generate HR_GEN: {e}")
                    QMessageBox.warning(
                        self,
                        "HR Generation Failed",
                        f"Could not generate HR_GEN signal: {str(e)}\n\nProceeding without HR_GEN.",
                    )
                    # Remove HR_GEN from selected channels since generation failed
                    selected = [ch for ch in selected if ch != "HR_GEN"]
                    if not selected:
                        QMessageBox.information(
                            self, "No Selection", "No valid channels selected."
                        )
                        return

            self.update_tabs(selected)

            # Save the new file and channel selection to configuration
            self.config_manager.set_last_file_path(path)
            self.config_manager.set_default_signals(selected)
            self.config_manager.save_config()
            self.logger.debug("Configuration updated and saved")

        except Exception as e:
            self.logger.critical(f"Failed to load file: {e}", exc_info=True)
            QMessageBox.critical(self, "Load Error", f"Failed to load file: {e}")

    def update_tabs(self, selected_channels):
        # FIXME Arreglar para que ViewerTab se inicie vacia igual que las otras y luego se actualice
        """Create and insert ViewerTab, and update Tilt and Analysis tabs."""
        try:
            self.logger.info(
                f"Updating tabs with {len(selected_channels)} selected channels"
            )
            return self._update_tabs_impl(selected_channels)
        except Exception as e:
            self.logger.error(f"Tab update failed: {e}", exc_info=True)
            return None

    def _update_tabs_impl(self, selected_channels):
        """Implementación protegida de actualización de tabs."""
        if not self.current_file:
            return
        path = self.current_file
        # meta = self.data_manager.get_metadata(path)

        # ViewerTab
        viewer = ViewerTab(self)
        hr_params = self.analysis_tab.get_hrgen_params()

        viewer.load_data(
            file_path=path,
            chunk_size=60,
            target_signals=selected_channels,
            hr_params=hr_params,
        )
        # FIXME Intento de poder abrir distintos archivos, cada archivo deberia tener su propio grupo de tabs
        idx = self.tab_widget.count() - 2
        self.tab_widget.insertTab(idx, viewer, os.path.basename(path))
        self.tab_widget.setCurrentIndex(idx)

        # First update AnalysisTab so its hr_params are up-to-date
        self.analysis_tab.update_analysis_tab(self.data_manager, path)
        # Then pass those hr_params into EventTab
        self.event_tab.update_event_tab(self.data_manager, path, hr_params)

    def get_current_hr_params(self):
        """Get current HR_GEN parameters from Analysis tab."""
        return self.analysis_tab.get_hrgen_params()

    def update_viewer_tabs_hr_params(self):
        """Update HR parameters in all ViewerTab instances when Analysis tab changes."""
        try:
            current_hr_params = self.get_current_hr_params()
            self.logger.debug(f"Updating ViewerTab HR parameters: {current_hr_params}")

            # Update all ViewerTab instances (excluding Tilt and Analysis tabs)
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if isinstance(widget, ViewerTab):
                    widget.update_hr_params(current_hr_params)
                    self.logger.debug(
                        f"Updated HR parameters for ViewerTab at index {i}"
                    )

            # Also update EventTab if it uses HR_GEN
            self.event_tab.update_hr_params(current_hr_params)
            self.logger.debug("Updated HR parameters for EventTab")

        except Exception as e:
            self.logger.error(f"Error updating HR parameters across tabs: {e}")

    def _export_csv(self):
        """Export selected signal statistics to CSV."""
        try:
            self.session.log_action("CSV export requested", self.logger)
            return self._export_csv_impl()
        except Exception as e:
            self.logger.error(f"CSV export failed: {e}", exc_info=True)
            return None

    def _export_csv_impl(self):
        """Implementación protegida de exportación CSV en formato horizontal."""
        if not self.current_file:
            QMessageBox.warning(self, "Export", "No file loaded.")
            return

        path = self.current_file
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

            self.session.log_action(
                f"CSV export successful (horizontal): {len(sel_signals)} signals, {len(sel_tests) if sel_tests else 1} tests",
                self.logger,
            )

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

    def _close_tab(self, index):
        """Close the specified tab, unless it's Tilt or Analysis."""
        widget = self.tab_widget.widget(index)
        if widget in (self.event_tab, self.analysis_tab):
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def closeEvent(self, event):
        """Override close event para limpiar recursos."""
        try:
            duration = self.session.get_session_duration()
            self.session.log_action(
                f"Application closing after {duration:.1f}s with {self.session.actions_count} total actions",
                self.logger,
            )
            self.logger.info("Cerrando aplicación...")

            # Save current session configuration
            self.config_manager.save_current_session(self)

            # Detener timer de salud
            if hasattr(self, "health_timer"):
                self.health_timer.stop()

            # Limpiar data_manager si es necesario
            if hasattr(self.data_manager, "cleanup"):
                self.data_manager.cleanup()

            self.logger.info("=== AuroraWave Session Ended ===")
            event.accept()

        except Exception as e:
            self.logger.error(f"Error durante cierre: {e}")
            event.accept()  # Cerrar de todas formas
