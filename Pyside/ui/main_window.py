import json
import unicodedata
import os
import csv
import logging
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox,
    QTabWidget, QToolBar)

from PySide6.QtGui import QAction
from data.data_manager import DataManager
from ui.viewer_tab import ViewerTab
from ui.analysis_tab import AnalysisTab
from ui.tilt_tab import TiltTab
from ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from ui.widgets.export_selection_dialog import ExportSelectionDialog
from core.interval_extractor import extract_event_intervals

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)
CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config", "signals_config.json")
)

class MainWindow(QMainWindow):
    """
    Main window for AuroraWave with enhanced debug logging
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuroraWave")
        self.setMinimumSize(1200, 800)

        # Setup logger
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"CONFIG_PATH: {CONFIG_PATH}")

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
        #self._init_menubar():

        # Toolbar
        self._init_toolbar()

        # Attempt to load last session config
        self._load_config_if_exists()




    # Menubar definition
    def _init_menubar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Files")
        export_menu = menu_bar.addMenu("Export")
        export_menu.addAction("Exportar marcadores", self.export_marke)


    # Toolbar definition
    def _init_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        self.addToolBar(toolbar)
        load_act = QAction("Load File", self)
        load_act.triggered.connect(self._load_file_dialog)
        toolbar.addAction(load_act)
        export_act = QAction("Export CSV", self)
        export_act.triggered.connect(self._export_csv)
        toolbar.addAction(export_act)

    def _load_config_if_exists(self):
        """Attempt to load configuration and apply default file and signals."""
        self.logger.debug("Attempting to load configuration file...")
        if not os.path.exists(CONFIG_PATH):
            self.logger.warning(f"Configuration file not found at {CONFIG_PATH}")
            return
        try:
            with open(CONFIG_PATH, "r", encoding='utf-8-sig') as f:
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
            fp = unicodedata.normalize('NFC', fp)

        self.logger.debug(f"Resolved file_path: {fp}")
        self.logger.debug(f"Configured default_signals: {defaults}")

        if fp and os.path.exists(fp):
            try:
                self.logger.debug(f"Loading file from config: {fp}")
                self.data_manager.load_file(fp)  # Load the file
                self.current_file = fp
                if defaults:
                    self.logger.debug("Updating tabs with default signals...")
                    self.update_tabs(defaults)
            except Exception as e:
                self.logger.error(f"Failed to load or update from config: {e}", exc_info=True)
        else:
            self.logger.warning(f"Configured file path does not exist: {fp}")

    def _load_file_dialog(self):
        """Open a file dialog to select a signal file and load it."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select signal file",
            "",
            "Signal files (*.adicht *.edf);;All files (*)"
        )
        if not path:
            return
        try:
            self.data_manager.load_file(path)
            self.current_file = path
            meta = self.data_manager.get_metadata(path)
            channels = meta.get("channels", [])
            if not channels:
                QMessageBox.warning(self, "No Channels", "No channels found in file.")
                return
            dlg = ChannelSelectionDialog(channels, self)
            if not dlg.exec():
                return
            selected = dlg.get_selected_channels()
            if not selected:
                QMessageBox.information(self, "No Selection", "No channels selected.")
                return
            self.update_tabs(selected)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file: {e}")

    def update_tabs(self, selected_channels):
        """Create and insert ViewerTab, and update Tilt and Analysis tabs."""
        if not self.current_file:
            return
        path = self.current_file
        meta = self.data_manager.get_metadata(path)

        # ViewerTab
        viewer = ViewerTab(self)
        viewer.load_data(
            file_path=path,
            chunk_size=60,
            target_signals=selected_channels 
            )
        idx = self.tab_widget.count() - 2
        self.tab_widget.insertTab(idx, viewer, os.path.basename(path))
        self.tab_widget.setCurrentIndex(idx)

        # Update Tilt and Analysis
        self.tilt_tab.update_tilt_tab(self.data_manager, path)
        self.analysis_tab.update_analysis_tab(self.data_manager, path)

    def _export_csv(self):
        """Export selected signal statistics to CSV."""
        if not self.current_file:
            QMessageBox.warning(self, "Export", "No file loaded.")
            return
        path = self.current_file
        all_signals = self.data_manager.get_available_channels(path)
        traces = [self.data_manager.get_trace(path, ch) for ch in all_signals]
        intervals = extract_event_intervals(traces)
        tests = [iv.get("evento") for iv in intervals if iv.get("evento")]
        seen = set()
        unique_tests = [t for t in tests if t not in seen and not seen.add(t)]
        dialog = ExportSelectionDialog(all_signals, unique_tests, self)
        if not dialog.exec():
            return
        sel_signals, sel_tests = dialog.get_selections()
        if not sel_signals:
            QMessageBox.warning(self, "Export", "No signals selected.")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not save_path:
            return
        export_ints = []
        if sel_tests:
            for iv in intervals:
                if iv.get("evento") in sel_tests:
                    s = iv.get("t_evento"); e = iv.get("t_recovery")
                    if s is not None and e is not None:
                        export_ints.append((iv["evento"], s, e))
        else:
            export_ints.append(("Full", 0, None))
        headers = []
        rows = []
        for test_name, s, e in export_ints:
            row = []
            hdr = []
            for ch in sel_signals:
                hdr += [f"{ch}_mean_{test_name}", f"{ch}_max_{test_name}"]
                sig = self.data_manager.get_trace(path, ch)
                data = sig.get_full_signal()
                fs = sig.fs
                i0 = int(s * fs) if s else 0
                i1 = int(e * fs) if e else len(data)
                seg = data[i0:i1]
                if seg.size:
                    row += [f"{float(seg.mean()):.6f}", f"{float(seg.max()):.6f}"]
                else:
                    row += ["", ""]
            headers = hdr
            rows.append(row)
        try:
            with open(save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(headers)
                writer.writerows(rows)
            QMessageBox.information(self, "Export", f"CSV exported to {save_path}")
        except Exception as ex:
            QMessageBox.critical(self, "Export Error", str(ex))

    def _close_tab(self, index):
        """Close the specified tab, unless it's Tilt or Analysis."""
        widget = self.tab_widget.widget(index)
        if widget in (self.tilt_tab, self.analysis_tab):
            return
        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def closeEvent(self, event):
        """Override close event to skip saving config (per user request)."""
        event.accept()
