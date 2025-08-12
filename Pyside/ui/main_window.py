"""
Main Window Module for AuroraWave

This module provides the main application window with multi-file session management,
signal visualization, and analysis capabilities.

Classes:
    MainWindow: Main application window with tab management and file handling

Features:
    - Multi-file session management
    - Signal visualization and analysis
    - Export capabilities
    - Configuration management
    - Session persistence

Example:
    >>> window = MainWindow()
    >>> window.show()
"""

import os
from typing import List, Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QMenu,
    QMenuBar,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QWidget,
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
from Pyside.core.file_session_manager import get_multi_file_manager, FileSession
from Pyside.processing.interval_extractor import extract_event_intervals
from Pyside.processing.csv_exporter import CSVExporter
from Pyside.processing.csv_exporter_horizontal import CSVExporterHorizontal

# Logging now handled by unified system in core.logging_config

# Suprimir warnings específicos de pyqtgraph
import warnings

warnings.filterwarnings("ignore", "overflow encountered in cast", RuntimeWarning)


class MainWindow(QMainWindow):
    """
    Main application window for AuroraWave.

    Provides the primary user interface with multi-file session management,
    signal visualization, analysis tools, and export capabilities.

    Attributes:
        data_manager: Centralized data management instance
        file_session_manager: Multi-file session manager
        config_manager: Configuration manager instance
        current_file: Currently active file path (deprecated, use file_session_manager)
        tab_widget: Main tab container for different views
        event_tab: Event analysis tab instance
        analysis_tab: Signal analysis tab instance
        file_selector: Dropdown for switching between open files

    Example:
        >>> window = MainWindow()
        >>> window.show()
    """

    def __init__(self) -> None:
        """
        Initialize the main window with all components and managers.

        Sets up the UI, initializes managers, applies startup configuration,
        and establishes health monitoring.
        """
        super().__init__()
        self.setWindowTitle("AuroraWave - Multi-File Signal Analysis")
        self.setMinimumSize(1400, 900)

        # Initialize logging with user context
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.session.log_action("MainWindow initialized", self.logger)

        # Initialize managers
        self.config_manager = get_config_manager()
        self.file_session_manager = get_multi_file_manager()
        self.data_manager = DataManager()

        self.logger.info("MainWindow initialization started")

        # Legacy compatibility - will be phased out
        self.current_file: Optional[str] = None

        # Tab widget setup
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self.tab_widget)

        # Core analysis tabs (persistent)
        self.event_tab = EventTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.tab_widget.addTab(self.event_tab, "Event Analysis")
        self.tab_widget.addTab(self.analysis_tab, "Signal Analysis")

        # Setup UI components
        self._init_menubar()
        self._init_toolbar()
        self._init_file_selector()

        # Health monitoring timer
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._check_application_health)
        self.health_timer.start(30000)  # Check every 30 seconds

        # Apply startup configuration
        self._apply_startup_configuration()

        self.session.log_action("MainWindow setup complete", self.logger)

    def _init_menubar(self) -> None:
        """Initialize the application menu bar with multi-file support."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        # File operations
        open_file_action = QAction("Open File...", self)
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.triggered.connect(self._load_file_dialog)
        file_menu.addAction(open_file_action)

        close_file_action = QAction("Close Current File", self)
        close_file_action.setShortcut("Ctrl+W")
        close_file_action.triggered.connect(self._close_current_file)
        file_menu.addAction(close_file_action)

        close_all_action = QAction("Close All Files", self)
        close_all_action.setShortcut("Ctrl+Shift+W")
        close_all_action.triggered.connect(self._close_all_files)
        file_menu.addAction(close_all_action)

        file_menu.addSeparator()

        # Recent files submenu
        recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu(recent_menu)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Export menu
        export_menu = menu_bar.addMenu("Export")
        export_csv_action = QAction("Export to CSV...", self)
        export_csv_action.setShortcut("Ctrl+E")
        export_csv_action.triggered.connect(self._export_csv)
        export_menu.addAction(export_csv_action)

        # Window menu
        window_menu = menu_bar.addMenu("Window")

        # Session management
        session_submenu = window_menu.addMenu("File Sessions")
        self._update_session_menu(session_submenu)

    def _init_file_selector(self) -> None:
        """Initialize the file selector dropdown in the toolbar."""
        # Create container widget for file selector
        self.file_selector_widget = QWidget()
        layout = QHBoxLayout(self.file_selector_widget)
        layout.setContentsMargins(5, 0, 5, 0)

        # File selector label and dropdown
        selector_label = QLabel("Active File:")
        self.file_selector = QComboBox()
        self.file_selector.setMinimumWidth(200)
        self.file_selector.currentTextChanged.connect(self._on_file_selection_changed)

        layout.addWidget(selector_label)
        layout.addWidget(self.file_selector)

        # Add to toolbar
        if hasattr(self, "toolbar"):
            self.toolbar.addSeparator()
            self.toolbar.addWidget(self.file_selector_widget)

    def _update_file_selector(self) -> None:
        """Update the file selector dropdown with current sessions."""
        try:
            self.logger.debug("Updating file selector...")
            self.file_selector.blockSignals(True)
            self.file_selector.clear()

            sessions = self.file_session_manager.get_all_sessions()
            active_session = self.file_session_manager.get_active_session()

            self.logger.debug(
                f"Found {len(sessions)} sessions, active: {active_session.display_name if active_session else 'None'}"
            )

            for session in sessions:
                self.file_selector.addItem(session.display_name, session.session_id)
                self.logger.debug(f"Added session to selector: {session.display_name}")

            # Set current selection
            if active_session:
                for i in range(self.file_selector.count()):
                    if self.file_selector.itemData(i) == active_session.session_id:
                        self.file_selector.setCurrentIndex(i)
                        self.logger.debug(
                            f"Set active session in selector: {active_session.display_name}"
                        )
                        break

            self.file_selector.blockSignals(False)
            self.logger.info(f"File selector updated with {len(sessions)} sessions")

        except Exception as e:
            self.logger.error(f"Failed to update file selector: {e}", exc_info=True)

    def _on_file_selection_changed(self, display_name: str) -> None:
        """Handle file selection change from dropdown."""
        if not display_name:
            return

        # Prevent recursive calls during programmatic updates
        if self.file_selector.signalsBlocked():
            return

        current_index = self.file_selector.currentIndex()
        if current_index >= 0:
            session_id = self.file_selector.itemData(current_index)
            if session_id:
                # Check if this is actually a different session
                current_active = self.file_session_manager.get_active_session()
                if current_active and current_active.session_id == session_id:
                    return  # No change needed

                self.file_session_manager.switch_to_session(session_id)
                self._update_tabs_for_active_session()

    def _update_recent_files_menu(self, menu: QMenu) -> None:
        """Update the recent files submenu."""
        # This would be implemented to show recently opened files
        # For now, just add a placeholder
        no_recent_action = QAction("No recent files", self)
        no_recent_action.setEnabled(False)
        menu.addAction(no_recent_action)

    def _update_session_menu(self, menu: QMenu) -> None:
        """Update the session management submenu."""
        menu.clear()

        sessions = self.file_session_manager.get_all_sessions()
        if not sessions:
            no_sessions_action = QAction("No open files", self)
            no_sessions_action.setEnabled(False)
            menu.addAction(no_sessions_action)
            return

        for session in sessions:
            session_action = QAction(session.display_name, self)
            if session.is_active:
                session_action.setText(f"• {session.display_name}")
            session_action.triggered.connect(
                lambda checked, sid=session.session_id: self.file_session_manager.switch_to_session(
                    sid
                )
            )
            menu.addAction(session_action)

    def _close_current_file(self) -> None:
        """Close the currently active file session."""
        active_session = self.file_session_manager.get_active_session()
        if active_session:
            self.file_session_manager.close_session(active_session.session_id)
            self._update_file_selector()
            self._update_tabs_for_active_session()

    def _close_all_files(self) -> None:
        """Close all open file sessions."""
        sessions = self.file_session_manager.get_all_sessions()
        for session in sessions:
            self.file_session_manager.close_session(session.session_id)
        self._update_file_selector()
        self._clear_all_viewer_tabs()

    def _update_tabs_for_active_session(self) -> None:
        """Update tabs to reflect the currently active session."""
        active_session = self.file_session_manager.get_active_session()

        if not active_session:
            # No active session, clear viewer tabs but keep analysis tabs
            self._clear_viewer_tabs()
            self._clear_analysis_tabs()
            return

        # Update legacy current_file for compatibility
        self.current_file = active_session.file_path

        # Update existing tabs with new session data instead of creating new ones
        if active_session.selected_channels:
            self._update_existing_tabs_for_session(active_session)

    def _update_existing_tabs_for_session(self, session: "FileSession") -> None:
        """Update existing tabs with data from the specified session."""
        try:
            self.logger.info(
                f"Updating existing tabs for session: {session.display_name}"
            )

            # Prevent recursive updates
            if hasattr(self, "_updating_session") and self._updating_session:
                self.logger.debug("Session update already in progress, skipping")
                return

            self._updating_session = True

            # Load file data through data_manager
            self.data_manager.load_file(session.file_path)

            # Clear user comments from EventTab for session isolation
            if hasattr(self.event_tab, "user_comment_widget"):
                self.event_tab.user_comment_widget.set_file_path(session.file_path)

            # Clear existing user comments from all tabs before loading new session
            if hasattr(self.event_tab, "user_comments"):
                self.event_tab.user_comments.clear()

            # Clear comment markers from all tabs to ensure clean state
            if hasattr(self.event_tab, "marker_manager"):
                self.event_tab.marker_manager.clear_all_markers()

            # Clear comment markers from all ViewerTabs
            for viewer_tab in self._get_viewer_tabs():
                if hasattr(viewer_tab, "marker_manager"):
                    viewer_tab.marker_manager.clear_all_markers()

            # Find ViewerTabs that belong to this session
            session_viewer_tabs = []
            for viewer_tab in self._get_viewer_tabs():
                if viewer_tab.file_path == session.file_path:
                    session_viewer_tabs.append(viewer_tab)

            if session_viewer_tabs:
                # Update only ViewerTabs that belong to this session
                for viewer_tab in session_viewer_tabs:
                    hr_params = self.analysis_tab.get_hrgen_params()
                    viewer_tab.load_data(
                        file_path=session.file_path,
                        chunk_size=60,
                        target_signals=session.selected_channels,
                        hr_params=hr_params,
                    )
                    self.logger.debug(
                        f"Updated ViewerTab for session {session.display_name} with {len(session.selected_channels)} channels"
                    )
            else:
                # No ViewerTabs exist for this session, create one
                self.update_tabs(session.selected_channels)
                return

            # Update Analysis Tab - always update to show data from active session
            self.analysis_tab.update_analysis_tab(self.data_manager, session.file_path)

            # Update Event Tab - always update to show data from active session
            hr_params = self.analysis_tab.get_hrgen_params()
            self.event_tab.update_event_tab(
                self.data_manager, session.file_path, hr_params
            )

            # Update HR parameters only for ViewerTabs of this session
            hr_params = self.analysis_tab.get_hrgen_params()
            for viewer_tab in session_viewer_tabs:
                if hasattr(viewer_tab, "update_hr_params"):
                    viewer_tab.update_hr_params(hr_params)

            self.logger.info(
                f"Successfully updated tabs for session: {session.display_name}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to update tabs for session {session.display_name}: {e}",
                exc_info=True,
            )
        finally:
            self._updating_session = False

    def _clear_viewer_tabs(self) -> None:
        """Clear all viewer tabs while keeping analysis tabs."""
        tabs_to_remove = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, ViewerTab):
                tabs_to_remove.append(i)

        # Remove from highest index to lowest to avoid index shifts
        for i in reversed(tabs_to_remove):
            self.tab_widget.removeTab(i)

    def _clear_all_viewer_tabs(self) -> None:
        """Clear all viewer tabs and reset analysis tabs."""
        self._clear_viewer_tabs()

        # Reset analysis tabs
        self.event_tab.reset_tab() if hasattr(self.event_tab, "reset_tab") else None
        (
            self.analysis_tab.reset_tab()
            if hasattr(self.analysis_tab, "reset_tab")
            else None
        )

    def _clear_analysis_tabs(self) -> None:
        """Clear analysis and event tabs data without removing them."""
        try:
            # Reset analysis tab
            if hasattr(self.analysis_tab, "reset_tab"):
                self.analysis_tab.reset_tab()

            # Reset event tab
            if hasattr(self.event_tab, "reset_tab"):
                self.event_tab.reset_tab()

            self.logger.debug("Cleared analysis tabs data")
        except Exception as e:
            self.logger.error(f"Failed to clear analysis tabs: {e}", exc_info=True)

    def _get_viewer_tabs(self) -> List:
        """Get all currently open ViewerTab instances."""
        viewer_tabs = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, ViewerTab):
                viewer_tabs.append(widget)
        return viewer_tabs  # Menubar definition

    # def _init_menubar(self):
    #    menu_bar = self.menuBar()
    #    file_menu = menu_bar.addMenu("Files")
    #    export_menu = menu_bar.addMenu("Export")
    #    # FIXME Conectar widget de exportacion
    #    # export_menu.addAction("Exportar marcadores", self.export_markers)

    def _init_toolbar(self) -> None:
        """Initialize the main toolbar with file operations and session management."""
        self.toolbar = QToolBar("Main Toolbar", self)
        self.addToolBar(self.toolbar)

        # File operations
        load_action = QAction("Open File", self)
        load_action.triggered.connect(self._load_file_dialog)
        self.toolbar.addAction(load_action)

        export_action = QAction("Export CSV", self)
        export_action.triggered.connect(self._export_csv)
        self.toolbar.addAction(export_action)

    def _apply_startup_configuration(self):
        """Apply saved configuration at startup."""
        try:
            self.logger.info("Applying startup configuration...")
            success = self.config_manager.apply_startup_configuration(self)
            if not success:
                self.logger.debug("No valid startup configuration found or applied")
            else:
                # Create a session for the loaded file
                if hasattr(self, "current_file") and self.current_file:
                    self._create_session_from_current_file()
                    self._update_file_selector()
        except Exception as e:
            self.logger.error(
                f"Failed to apply startup configuration: {e}", exc_info=True
            )

    def _create_session_from_current_file(self):
        """Create a session for the currently loaded file."""
        if not self.current_file:
            return

        try:
            # Check if session already exists for this file
            existing_session = None
            for session in self.file_session_manager.get_all_sessions():
                if session.file_path == self.current_file:
                    existing_session = session
                    break

            if not existing_session:
                # Create new session
                session = self.file_session_manager.open_file(
                    file_path=self.current_file,
                    selected_channels=self.config_manager.get_default_signals(),
                )
                self.logger.info(
                    f"Created session for startup file: {session.display_name}"
                )
            else:
                # Switch to existing session
                self.file_session_manager.switch_to_session(existing_session.session_id)
                self.logger.info(
                    f"Switched to existing session: {existing_session.display_name}"
                )

        except Exception as e:
            self.logger.error(
                f"Failed to create session from current file: {e}", exc_info=True
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

            # Create or update session for the loaded file
            try:
                session = self.file_session_manager.open_file(
                    file_path=path, selected_channels=selected
                )
                self._update_file_selector()
                self.logger.info(
                    f"Created session for new file: {session.display_name}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create session for loaded file: {e}", exc_info=True
                )

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

    def closeEvent(self, event) -> None:
        """
        Override close event to clean up resources and save session state.

        Args:
            event: QCloseEvent from the window system
        """
        try:
            duration = self.session.get_session_duration()
            self.session.log_action(
                f"Application closing after {duration:.1f}s with {self.session.actions_count} total actions",
                self.logger,
            )
            self.logger.info("Closing application...")

            # Save multi-file session state
            self.file_session_manager.save_session_state()

            # Save current session configuration (legacy)
            self.config_manager.save_current_session(self)

            # Stop health monitoring timer
            if hasattr(self, "health_timer"):
                self.health_timer.stop()

            # Clean up data manager if necessary
            if hasattr(self.data_manager, "cleanup"):
                self.data_manager.cleanup()

            self.logger.info("=== AuroraWave Session Ended ===")
            event.accept()

        except Exception as e:
            self.logger.error(f"Error during application closure: {e}")
            event.accept()  # Close anyway
