"""
MainWindow - Multi-session container with QTabWidget.
Each tab represents a complete app instance for one file.
"""

import logging
import numpy as np
from PySide6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QMessageBox, QDialog
from PySide6.QtGui import QAction

from aurora.core.session_manager import get_session_manager
from aurora.ui.tabs.session_tab_host import SessionTabHost
from aurora.ui.dialogs.config_dialog import ConfigDialog


class MainWindow(QMainWindow):
    """
    Main application window with multi-session architecture.

    Architecture:
    - MainWindow contains QTabWidget for sessions
    - Each tab = SessionTabHost (complete app instance for one file)
    - SessionManager handles session creation/cleanup
    - File menu triggers session creation
    """

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger("aurora.ui.MainWindow")
        self.logger.debug("=== MAINWINDOW INIT STARTED ===")

        self.setWindowTitle("Aurora 2.0 - Multi-Session Signal Analysis")
        # self.setMinimumSize(1400, 900)
        self.showMaximized()
        self.logger.debug("Window title and size configured")

        # Get SessionManager instance
        self.logger.debug("Getting SessionManager instance...")
        try:
            self.session_manager = get_session_manager()
            self.logger.debug("SessionManager obtained successfully")
        except Exception as e:
            self.logger.error(f"Failed to get SessionManager: {e}", exc_info=True)
            raise

        # Create central QTabWidget for sessions
        self.logger.debug("Creating QTabWidget for sessions...")
        self.session_tabs = QTabWidget()
        self.session_tabs.setTabsClosable(True)
        self.session_tabs.setMovable(True)
        self.setCentralWidget(self.session_tabs)
        self.logger.debug("QTabWidget configured and set as central widget")

        # Create menu bar
        self.logger.debug("Creating menu bar...")
        self._create_menu_bar()
        self.logger.debug("Menu bar created")

        # Connect signals
        self.logger.debug("Connecting signals...")
        self._connect_signals()
        self.logger.debug("Signals connected")

        self.logger.debug("=== MAINWINDOW INIT COMPLETED ===")

    def _create_menu_bar(self):
        """Create menu bar with File and Export menus."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open File...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Export menu
        export_menu = menu_bar.addMenu("Export")

        export_csv_action = QAction("Export CSV", self)
        export_csv_action.triggered.connect(self._export_csv)
        export_menu.addAction(export_csv_action)

        # Settings menu
        settings_menu = menu_bar.addMenu("Settings")

        config_action = QAction("Configuration...", self)
        config_action.setShortcut("Ctrl+,")
        config_action.triggered.connect(self._open_config_dialog)
        settings_menu.addAction(config_action)

    def _connect_signals(self):
        """Connect signals from SessionManager and tabs."""
        # SessionManager signals
        self.session_manager.session_created.connect(self._on_session_created)
        self.session_manager.session_closed.connect(self._on_session_closed)

        # Tab close button signals
        self.session_tabs.tabCloseRequested.connect(self._close_tab)

    def _open_file_dialog(self):
        """Show file loader dialog and create new session."""
        self.logger.info("=== OPEN FILE DIALOG STARTED ===")

        try:
            from aurora.ui.dialogs.file_loader_dialog import FileLoaderDialog

            self.logger.debug("Showing FileLoaderDialog...")
            result = FileLoaderDialog.select_files(parent=self)

            if result:
                signal_file_path, config_file_path = result
                self.logger.info(
                    f"Files selected - Signal: {signal_file_path}, Config: {config_file_path or 'None'}"
                )

                self.logger.debug(f"Delegating to SessionManager.create_session()...")

                try:
                    session = self.session_manager.create_session(
                        signal_file_path, config_file_path
                    )
                    self.logger.info(
                        f"SessionManager.create_session() returned: {session}"
                    )

                    if not session:
                        error_msg = "Failed to load file - SessionManager returned None"
                        self.logger.error(error_msg)
                        QMessageBox.critical(self, "Error", "Failed to load file")
                    else:
                        self.logger.info(
                            f"Session created successfully: {session.session_id}"
                        )

                except Exception as e:
                    error_msg = f"Exception during session creation: {e}"
                    self.logger.error(error_msg, exc_info=True)
                    QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
            else:
                self.logger.debug("No files selected - dialog cancelled")

        except ImportError as e:
            self.logger.error(f"Could not import FileLoaderDialog: {e}")
            QMessageBox.critical(self, "Error", "FileLoaderDialog not available")
        except Exception as e:
            self.logger.error(f"Exception in file dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error opening file dialog: {e}")

        self.logger.info("=== OPEN FILE DIALOG COMPLETED ===")

    def _export_csv(self):
        """Export current session data to CSV using advanced hemodynamic analysis."""
        # Get current active session
        current_index = self.session_tabs.currentIndex()
        if current_index == -1:
            QMessageBox.warning(self, "Export", "No file loaded.")
            return

        tab_host = self.session_tabs.widget(current_index)
        if not hasattr(tab_host, "session"):
            QMessageBox.warning(self, "Export", "No valid session found.")
            return

        session = tab_host.session
        if not session.is_loaded:
            QMessageBox.warning(self, "Export", "Session not loaded.")
            return

        try:
            # Import ExportConfigDialog locally to avoid circular imports
            from aurora.ui.dialogs import ExportConfigDialog
            from aurora.processing.hemodynamic_analyzer import HemodynamicAnalyzer

            self.logger.info(f"Iniciando exportación para sesión: {session.session_id}")

            # Detectar protocolo automáticamente (placeholder por ahora)
            detected_protocol = self._detect_protocol(session)

            # Abrir diálogo de configuración de exportación
            export_dialog = ExportConfigDialog(session, detected_protocol, self)

            if export_dialog.exec() == QDialog.DialogCode.Accepted:
                # Obtener configuración de exportación
                export_config = export_dialog.get_export_config()

                # Ejecutar proceso de exportación
                success = self._execute_export(export_config)

                if success:
                    QMessageBox.information(
                        self,
                        "Exportación Exitosa",
                        f"✅ Datos exportados correctamente.\n"
                        f"Archivo: {export_config.get('output_path', 'N/A')}",
                    )
                    self.logger.info("Exportación completada exitosamente")
                else:
                    QMessageBox.warning(
                        self,
                        "Error de Exportación",
                        "❌ Error durante el proceso de exportación.\n"
                        "Revisar logs para detalles.",
                    )
            else:
                self.logger.info("Exportación cancelada por usuario")

        except ImportError as e:
            self.logger.error(f"Error importando módulos de exportación: {e}")
            QMessageBox.critical(
                self,
                "Error de Módulos",
                f"Error cargando componentes de exportación:\n{e}",
            )
        except Exception as e:
            self.logger.error(f"Error durante exportación: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error Inesperado", f"Error durante exportación:\n{e}"
            )

    def _detect_protocol(self, session) -> str:
        """
        Detecta automáticamente el tipo de protocolo basado en comentarios.

        Args:
            session: Sesión activa con datos cargados

        Returns:
            str: Tipo de protocolo detectado ("stand", "tilt", "lbnp", "custom")
        """
        try:
            # Obtener comentarios/intervalos de la sesión
            if hasattr(session, "file_path") and session.file_path:
                intervals = session.data_manager.get_event_intervals(session.file_path)

                # Buscar patrones de protocolo en eventos
                events = [interval.get("evento", "").lower() for interval in intervals]
                all_events = " ".join(events)

                if "tilt" in all_events:
                    return "tilt"
                elif "stand" in all_events:
                    return "stand"
                elif "lbnp" in all_events or "negative pressure" in all_events:
                    return "lbnp"

        except Exception as e:
            self.logger.warning(f"Error detectando protocolo: {e}")

        # Protocolo por defecto
        return "stand"

    def _execute_export(self, export_config: dict) -> bool:
        """
        Ejecuta el proceso de exportación con la configuración especificada.

        Args:
            export_config: Configuración de exportación del diálogo

        Returns:
            bool: True si exportación exitosa, False en caso contrario
        """
        try:
            from aurora.processing.hemodynamic_analyzer import HemodynamicAnalyzer
            import pandas as pd
            import csv
            import numpy as np

            session = export_config["session"]
            output_path = export_config["output_path"]

            if not output_path:
                self.logger.error("Ruta de salida no especificada")
                return False

            self.logger.info(f"Iniciando exportación a: {output_path}")

            # Cargar señales seleccionadas
            signals = {}
            for signal_name in export_config["signals"]:
                try:
                    if signal_name.startswith("HR_gen"):
                        # Extraer parámetros HR_gen si están en el nombre
                        # Por ahora usar configuración por defecto
                        signal = session.data_manager.get_trace(
                            session.file_path,
                            "HR_gen",
                            wavelet="haar",
                            level=4,
                            min_rr_sec=0.6,
                        )
                    else:
                        signal = session.data_manager.get_trace(
                            session.file_path, signal_name
                        )

                    signals[signal_name] = signal
                    self.logger.debug(f"Señal cargada: {signal_name}")

                except Exception as e:
                    self.logger.error(f"Error cargando señal {signal_name}: {e}")

            if not signals:
                self.logger.error("No se pudieron cargar señales")
                return False

            # Realizar análisis hemodinámico
            analyzer = HemodynamicAnalyzer(self.logger)
            protocol_key = export_config["protocol"]["key"]

            analysis_results = analyzer.prepare_hemodynamic_analysis(
                signals, protocol_key
            )

            # Generar datos para CSV en formato RedCap
            csv_data = self._format_results_for_redcap(analysis_results, export_config)

            # Escribir archivo CSV
            self._write_csv_file(csv_data, output_path, export_config)

            self.logger.info("Exportación completada exitosamente")
            return True

        except Exception as e:
            self.logger.error(f"Error durante exportación: {e}", exc_info=True)
            return False

    def _format_results_for_redcap(self, analysis_results: dict, config: dict) -> dict:
        """
        Formatea los resultados del análisis para exportación RedCap.

        Args:
            analysis_results: Resultados del HemodynamicAnalyzer
            config: Configuración de exportación

        Returns:
            dict: Datos formateados para CSV
        """
        participant_id = config["participant_id"]
        prefix = config["protocol"]["prefix"]

        # Inicializar fila de datos
        row_data = {"parti_id": f"{participant_id:03d}"}

        # Agregar datos de ventanas temporales
        temporal_windows = analysis_results.get("temporal_windows", {})
        temporal_points = config.get("temporal_points", [])

        for signal_name, values in temporal_windows.items():
            for time_point in temporal_points:
                if time_point in values:
                    column_name = f"{prefix}{time_point}s_{signal_name.lower()}"
                    row_data[column_name] = round(values[time_point], 6)

        # Agregar eventos de nadir
        nadir_events = analysis_results.get("nadir_events", {})
        if nadir_events.get("found"):
            row_data[f"{prefix}nadir_time"] = round(nadir_events["time"], 1)
            row_data[f"{prefix}nadir_sbp"] = round(nadir_events["sbp"], 0)

        # Agregar eventos de pico HR
        peak_events = analysis_results.get("peak_events", {})
        for event_name, event_data in peak_events.items():
            if "hr" in event_data:
                row_data[f"{prefix}{event_name}"] = round(event_data["hr"], 0)
            if "time" in event_data:
                row_data[f"{prefix}{event_name}_time"] = round(event_data["time"], 1)

        # Agregar estadísticas de últimos 5 minutos
        statistics = analysis_results.get("statistics", {})
        for stat_name, stat_values in statistics.items():
            for stat_type, value in stat_values.items():
                column_name = f"{prefix}{stat_name}_{stat_type}"
                row_data[column_name] = round(value, 6) if not np.isnan(value) else ""

        return row_data

    def _write_csv_file(self, data: dict, output_path: str, config: dict):
        """
        Escribe los datos al archivo CSV.

        Args:
            data: Datos a escribir
            output_path: Ruta del archivo de salida
            config: Configuración de exportación
        """
        import csv

        # Escribir CSV con separador de coma (estándar RedCap)
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            if data:
                fieldnames = list(data.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Escribir encabezado
                writer.writeheader()

                # Escribir datos
                writer.writerow(data)

                self.logger.info(f"CSV escrito con {len(fieldnames)} columnas")
            else:
                self.logger.warning("No hay datos para escribir en CSV")

    def _open_config_dialog(self):
        """Abre el diálogo de configuración general."""
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # Configuración guardada - podría activar actualización en sesiones si fuera necesario
            self.logger.info("Configuración actualizada por usuario")

    def _on_session_created(self, session_id: str, session):
        """Handle new session created by SessionManager."""
        self.logger.info(f"=== SESSION CREATED SIGNAL RECEIVED ===")
        self.logger.info(f"Session ID: {session_id}")
        self.logger.info(f"Session object: {session}")
        self.logger.debug(f"Session display name: {session.display_name}")

        try:
            # Create SessionTabHost for this session
            self.logger.debug(f"Creating SessionTabHost for session {session_id}...")
            tab_host = SessionTabHost(session, self)
            self.logger.info(f"SessionTabHost created successfully")

            # Add as new tab
            self.logger.debug(f"Adding tab with name: {session.display_name}")
            tab_index = self.session_tabs.addTab(tab_host, session.display_name)
            self.logger.debug(f"Tab added at index: {tab_index}")

            # Make this tab active
            self.session_tabs.setCurrentIndex(tab_index)
            self.logger.debug(f"Tab set as current")

            # Connect tab host signals
            self.logger.debug(f"Connecting tab host signals...")
            tab_host.session_error.connect(
                lambda error: self._on_session_error(session_id, error)
            )
            self.logger.debug(f"Tab host signals connected")

            self.logger.info(f"=== SESSION TAB CREATION SUCCESS ===")

        except Exception as e:
            error_msg = f"Failed to create session tab: {e}"
            self.logger.error(f"=== SESSION TAB CREATION FAILED ===")
            self.logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Error", error_msg)

    def _on_session_closed(self, session_id: str):
        """Handle session closed by SessionManager."""
        # Find and remove corresponding tab
        for i in range(self.session_tabs.count()):
            tab_host = self.session_tabs.widget(i)
            if (
                hasattr(tab_host, "session")
                and tab_host.session.session_id == session_id
            ):
                self.session_tabs.removeTab(i)
                break

    def _on_session_failed(self, session_id: str, error: str):
        """Handle session creation failure."""
        QMessageBox.critical(
            self, "Session Error", f"Failed to create session: {error}"
        )

    def _on_session_error(self, session_id: str, error: str):
        """Handle error from SessionTabHost."""
        QMessageBox.warning(self, "Session Error", f"Session {session_id}: {error}")

    def _close_tab(self, index: int):
        """Handle tab close button clicked."""
        tab_host = self.session_tabs.widget(index)
        if hasattr(tab_host, "session"):
            session_id = tab_host.session.session_id

            # Cleanup tab host
            tab_host.cleanup()

            # Close session in SessionManager
            self.session_manager.close_session(session_id)

    def closeEvent(self, event):
        """Handle application close - cleanup all sessions."""
        self.session_manager.close_all_sessions()
        event.accept()
