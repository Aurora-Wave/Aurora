"""
main_window.py
--------------
Main window for the physiological signals visualization and analysis application.
Handles file loading and integrates the signal viewer and analysis tabs.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)
import numpy as np
from ui.viewer_tab import ViewerTab
from ui.analysis_tab import AnalysisTab
from ui.tilt_tab import TiltTab


class MainWindow(QMainWindow):
    """
    Main window of the application. Manages the interface layout, file loading,
    and the coordination of different analysis tabs.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Physiological Signals Viewer")
        self.resize(1200, 800)

        # Tab container
        self.tabs = QTabWidget()

        # Tab 1: General signal viewer
        self.viewer_tab = ViewerTab(self)
        self.tabs.addTab(self.viewer_tab, "Signals Viewer")

        # Tab 2: Analysis area
        self.analysis_tab = AnalysisTab()
        self.tabs.addTab(self.analysis_tab, "Signal Analysis")

        # Tab 3: Tilt Test comment viewer
        self.tilt_tab = TiltTab()
        self.tabs.addTab(self.tilt_tab, "Comments / Tilt")

        # Layout setup
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # File load button
        self.load_button = QPushButton("Load file")
        self.load_button.clicked.connect(self.load_data)
        main_layout.insertWidget(0, self.load_button)

        # Data-related properties
        self.signal_group = None
        self.sampling_rates = {}
        self.time_axes = {}
        self.max_len = 0
        self.chunk_size = 120
        self.target_signals = ["HR", "ECG", "FBP", "Valsalva", "CO"]

    def load_data(self):
        """
        Opens a file dialog to select a .adicht file and loads the signal data.
        Passes the data to the viewer and analysis tabs.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select .adicht file", "", "ADI files (*.adicht)"
        )
        if not file_path:
            return

        from data.adicht_loader import load_adicht
        self.signal_group = load_adicht(file_path)

        # Extract metadata from target signals
        self.sampling_rates.clear()
        self.time_axes.clear()
        self.max_len = 0

        for name in self.target_signals:
            signal = self.signal_group.get(name)
            if signal:
                fs = signal.fs
                full_signal = signal.get_full_signal()
                self.sampling_rates[name] = fs
                self.time_axes[name] = np.arange(len(full_signal)) / fs
                self.max_len = max(self.max_len, len(full_signal))

        # Load data in viewer
        self.viewer_tab.load_data(
            file_path=file_path,
            signal_group=self.signal_group,
            sampling_rates=self.sampling_rates,
            time_axes=self.time_axes,
            chunk_size=self.chunk_size,
            channel_names=self.target_signals,
        )

        # Load data in analysis tab
        self.analysis_tab.update_analysis_tab(
            self.signal_group, self.target_signals, file_path
        )

        # Load data in tilt/comments tab
        self.tilt_tab.update_tilt_tab(
            self.signal_group, self.target_signals, file_path
        )

    def closeEvent(self, event):
        """
        Handle app close event.
        """
        event.accept()
