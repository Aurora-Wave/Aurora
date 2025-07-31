import json
import unicodedata
import os
import csv
import logging
import numpy as np
import sys
import traceback
from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer
from data.data_manager import DataManager
from ui.viewer_tab import ViewerTab
from ui.analysis_tab import AnalysisTab
from ui.tilt_tab import TiltTab
from ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from ui.widgets.export_selection_dialog import ExportSelectionDialog
from ui.utils.error_handler import error_handler
from processing.interval_extractor import extract_event_intervals

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Suprimir warnings específicos de pyqtgraph
import warnings

warnings.filterwarnings("ignore", "overflow encountered in cast", RuntimeWarning)


# Signals configuration path
CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config", "signals_config.json")
)


class MainWindow(QMainWindow):
    """
    Main window for AuroraWave
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuroraWave")
        self.setMinimumSize(1200, 800)

        # Configurar error handler global PRIMERO
        error_handler.install_global_handler(self)
        self.logger = error_handler.logger

        # Setup logger con configuración mejorada
        self.logger.debug(f"USER SIGNALS PREFERENCE CONFIG_PATH: {CONFIG_PATH}")

        # Data manager and current file
        self.data_manager = DataManager()
        self.current_file = None

        # Tab widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self.tab_widget)

        # Tilt and Analysis tabs
        self.tilt_tab = TiltTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.tab_widget.addTab(self.tilt_tab, "Tilt Protocol")
        self.tab_widget.addTab(self.analysis_tab, "Signal Analysis")

        # Menubar
        # self._init_menubar():

        # Toolbar
        self._init_toolbar()

        # Timer para verificar el estado de la aplicación
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._check_application_health)
        self.health_timer.start(30000)  # Verificar cada 30 segundos

        # Attempt to load last session config
        self._load_config_if_exists()

    # Menubar definition
    def _init_menubar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Files")
        export_menu = menu_bar.addMenu("Export")
        # FIXME Conectar widget de exportacion
        # export_menu.addAction("Exportar marcadores", self.export_markers)

    # Toolbar definition
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

    # Preference config
    def _load_config_if_exists(self):
        """Attempt to load configuration and apply default file and signals."""
        self.logger.info("Attempting to load configuration file...")
        if not os.path.exists(CONFIG_PATH):
            self.logger.warning(f"Configuration file not found at {CONFIG_PATH}")
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
                self.logger.debug(f"Configuration loaded: {cfg}")
        except Exception as e:
            self.logger.error(f"Error reading config file: {e}", exc_info=True)
            return

        fp = cfg.get("file_path")
        defaults = cfg.get("default_signals", [])

        if isinstance(fp, str):
            # Normalize path separators
            fp = os.path.normpath(fp)
            # If the path is relative, resolve it against the config directory
            if not os.path.isabs(fp):
                base_dir = os.path.dirname(CONFIG_PATH)
                fp = os.path.normpath(os.path.join(base_dir, fp))
            # Normalize unicode form to match filesystem
            fp = unicodedata.normalize("NFC", fp)

        self.logger.debug(f"Resolved file_path: {fp}")
        self.logger.debug(f"Configured default_signals: {defaults}")

        if fp and os.path.exists(fp):
            try:
                self.logger.info(f"Loading file from config: {fp}")
                self.data_manager.load_file(fp)  # Load the file
                self.current_file = fp
                if defaults:
                    self.logger.info("Updating tabs with default signals...")
                    self.update_tabs(defaults)
            except Exception as e:
                self.logger.error(
                    f"Failed to load or update from config: {e}", exc_info=True
                )
                # Mostrar error al usuario pero no cerrar la aplicación
                QMessageBox.warning(
                    self,
                    "Error de Configuración",
                    f"No se pudo cargar el archivo configurado:\n{fp}\n\nError: {str(e)}",
                )
        else:
            self.logger.debug(f"Configured file path does not exist: {fp}")

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
        return error_handler.safe_execute(self._load_file_dialog_impl, "Cargar Archivo")

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
            self.logger.info(f"DataManager trying to open a file at {path}")
            self.data_manager.load_file(path)
            self.current_file = path
            meta = self.data_manager.get_metadata(path)
            channels = meta.get("channels", [])
            if not channels:
                self.logger.error(f"No channels found in {path}")
                QMessageBox.warning(self, "No Channels", "No channels found in file.")
                return

            dlg = ChannelSelectionDialog(channels, self)
            if not dlg.exec():
                return
            selected = dlg.get_selected_channels()
            self.logger.info(
                f"{selected} channels selected for visualization on ViewerTab"
            )
            if not selected:
                QMessageBox.information(self, "No Selection", "No channels selected.")
                return
            self.update_tabs(selected)
        except Exception as e:
            self.logger.critical(f"Failed to load file: {e}", exc_info=True)
            QMessageBox.critical(self, "Load Error", f"Failed to load file: {e}")

    def update_tabs(self, selected_channels):
        # FIXME Arreglar para que ViewerTab se inicie vacia igual que las otras y luego se actualice
        """Create and insert ViewerTab, and update Tilt and Analysis tabs."""
        return error_handler.safe_execute(
            self._update_tabs_impl, "Actualizar Tabs", selected_channels
        )

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
            hr_params=hr_params
            )
        # FIXME Intento de poder abrir distintos archivos, cada archivo deberia tener su propio grupo de tabs
        idx = self.tab_widget.count() - 2
        self.tab_widget.insertTab(idx, viewer, os.path.basename(path))
        self.tab_widget.setCurrentIndex(idx)

        # Update Tilt and Analysis
        self.tilt_tab.update_tilt_tab(self.data_manager, path)
        self.analysis_tab.update_analysis_tab(self.data_manager, path)

    def _export_csv(self):
        """Export selected signal statistics to CSV."""
        return error_handler.safe_execute(self._export_csv_impl, "Exportar CSV")

    def _export_csv_impl(self):
        """Implementación protegida de exportación CSV."""
        if not self.current_file:
            QMessageBox.warning(self, "Export", "No file loaded.")
            return

        path = self.current_file
        all_signals = self.data_manager.get_available_channels(path)

        # Extraer intervalos de eventos sin cargar todas las señales
        try:
            # Solo cargamos ECG para extraer comentarios (es más liviano que cargar todo)
            ecg_trace = self.data_manager.get_trace(path, "ECG")
            intervals = extract_event_intervals([ecg_trace])

            # Extraer tests con información de tiempo para distinguir duplicados
            test_entries = []
            for iv in intervals:
                evento = iv.get("evento")
                if evento:
                    # Crear identificador único con tiempo de inicio
                    t_start = iv.get("t_evento") or iv.get("t_tilt_angle", 0)
                    # Formatear tiempo en minutos:segundos para mejor legibilidad
                    tiempo_str = f"{int(t_start//60):02d}:{int(t_start%60):02d}"
                    display_name = f"{evento} (at {tiempo_str})"
                    test_entries.append((display_name, iv))

            # Ordenar por tiempo de inicio
            test_entries.sort(
                key=lambda x: x[1].get("t_evento", 0) or x[1].get("t_tilt_angle", 0)
            )
            unique_tests = [entry[0] for entry in test_entries]

        except Exception as e:
            self.logger.warning(f"Could not extract events: {str(e)}")
            QMessageBox.warning(self, "Export", f"Could not extract events: {str(e)}")
            unique_tests = []
            test_entries = []

        # Mostrar diálogo de selección
        dialog = ExportSelectionDialog(all_signals, unique_tests, self)
        if not dialog.exec():
            return

        sel_signals, sel_tests = dialog.get_selections()
        if not sel_signals:
            QMessageBox.warning(self, "Export", "No signals selected.")
            return

        # Seleccionar archivo de destino
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)"
        )
        if not save_path:
            return

        # Preparar intervalos de exportación
        export_ints = []
        if sel_tests and test_entries:
            # Crear mapeo de nombres de display a intervalos
            test_map = {entry[0]: entry[1] for entry in test_entries}

            for test_name in sel_tests:
                if test_name in test_map:
                    iv = test_map[test_name]
                    # Obtener tiempos de inicio y fin según el tipo de test
                    if iv.get("tipo") == "tilt_angle":
                        s = iv.get("t_evento") or iv.get("t_tilt_angle")
                        e = iv.get("t_tilt_down")
                    else:  # tipo "coms"
                        s = iv.get("t_evento")
                        e = iv.get("t_recovery")

                    if s is not None and e is not None:
                        # Usar el nombre original del evento, no el display name
                        original_name = iv.get("evento", test_name.split(" (at ")[0])
                        export_ints.append((original_name, s, e))
        else:
            # Si no hay tests seleccionados, exportar señal completa
            export_ints.append(("Full_Signal", 0, None))

        if not export_ints:
            # Agregar información de debugging
            self.logger.warning(
                f"No export intervals found. Selected tests: {sel_tests}"
            )
            self.logger.warning(
                f"Available test entries: {[entry[0] for entry in test_entries]}"
            )
            QMessageBox.warning(
                self,
                "Export",
                f"No valid intervals found.\n\n"
                f"Selected tests: {len(sel_tests)}\n"
                f"Available tests: {len(test_entries)}",
            )
            return

        # Exportar datos
        try:
            headers = []
            rows = []

            for test_name, s, e in export_ints:
                row = []  # No incluir nombre del test como primera columna
                if not headers:  # Solo definir headers una vez
                    headers = []  # No incluir "Test_Instance"

                # Calcular estadísticas por minuto
                if e is not None and s is not None:
                    duration = e - s
                    minutes = (
                        int(duration / 60) + 1
                    )  # Número de minutos completos o parciales

                    # Agregar headers para cada minuto si es la primera iteración
                    if len(headers) == 0:  # Si headers está vacío
                        for min_idx in range(minutes):
                            for ch in sel_signals:
                                headers.extend(
                                    [
                                        f"{ch}_mean_min{min_idx+1}",
                                        f"{ch}_max_min{min_idx+1}",
                                    ]
                                )

                    # Calcular estadísticas por minuto
                    for min_idx in range(minutes):
                        min_start = s + (min_idx * 60)
                        min_end = min(s + ((min_idx + 1) * 60), e)

                        for ch in sel_signals:
                            try:
                                # Manejar HR_gen con parámetros por defecto
                                if ch.upper() == "HR_GEN":
                                    sig = self.data_manager.get_trace(
                                        path, ch, wavelet="haar", level=4, min_dist=0.5
                                    )
                                else:
                                    sig = self.data_manager.get_trace(path, ch)

                                data = sig.data  # Usar .data directamente
                                fs = sig.fs
                                i0 = int(min_start * fs)
                                i1 = int(min_end * fs)
                                seg = data[i0:i1] if i1 <= len(data) else data[i0:]

                                if seg.size > 0:
                                    row.extend(
                                        [
                                            f"{float(seg.mean()):.6f}",
                                            f"{float(seg.max()):.6f}",
                                        ]
                                    )
                                else:
                                    row.extend(["", ""])
                            except Exception as ex:
                                self.logger.warning(f"Error processing {ch}: {ex}")
                                row.extend(["ERROR", "ERROR"])
                else:
                    # Si no hay duración definida, usar señal completa
                    if len(headers) == 0:  # Si headers está vacío
                        for ch in sel_signals:
                            headers.extend([f"{ch}_mean_full", f"{ch}_max_full"])

                    for ch in sel_signals:
                        try:
                            # Manejar HR_gen con parámetros por defecto
                            if ch.upper() == "HR_GEN":
                                sig = self.data_manager.get_trace(
                                    path, ch, wavelet="haar", level=4, min_dist=0.5
                                )
                            else:
                                sig = self.data_manager.get_trace(path, ch)

                            data = sig.data
                            if data.size > 0:
                                row.extend(
                                    [
                                        f"{float(data.mean()):.6f}",
                                        f"{float(data.max()):.6f}",
                                    ]
                                )
                            else:
                                row.extend(["", ""])
                        except Exception as ex:
                            self.logger.warning(f"Error processing {ch}: {ex}")
                            row.extend(["ERROR", "ERROR"])

                rows.append(row)

            # Escribir archivo CSV
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                writer.writerows(rows)

            QMessageBox.information(
                self,
                "Export Success",
                f"CSV exported successfully to:\n{save_path}\n\n"
                f"📊 {len(rows)} test instance(s) exported\n"
                f"📈 {len(sel_signals)} signal(s) included",
            )

        except Exception as ex:
            self.logger.error(f"Export error: {ex}", exc_info=True)
            QMessageBox.critical(
                self, "Export Error", f"Failed to export CSV:\n{str(ex)}"
            )

    def _close_tab(self, index):
        """Close the specified tab, unless it's Tilt or Analysis."""
        widget = self.tab_widget.widget(index)
        if widget in (self.tilt_tab, self.analysis_tab):
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def closeEvent(self, event):
        """Override close event para limpiar recursos."""
        try:
            self.logger.info("Cerrando aplicación...")

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
