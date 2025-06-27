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
    QHBoxLayout,
    QMessageBox,
)
import numpy as np
from ui.viewer_tab import ViewerTab
from ui.analysis_tab import AnalysisTab
from ui.tilt_tab import TiltTab
import csv

## TuningTab import eliminado


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

        # Data-related properties
        self.signal_group = None  # Inicializa antes de crear las pestañas
        self.sampling_rates = {}
        self.time_axes = {}
        self.max_len = 0
        self.chunk_size = 120
        self.target_signals = ["HR", "ECG", "FBP", "Valsalva", "CO"]

        # (Tuning tab eliminado)

        # Layout setup
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # File load button
        self.load_button = QPushButton("Load file")
        self.load_button.clicked.connect(self.load_data)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self.export_csv)
        button_row = QHBoxLayout()
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.export_button)
        main_layout.insertLayout(0, button_row)

    def export_csv(self):
        """
        Exporta un CSV con una sola fila: cada columna es la media por minuto y el máximo por minuto de cada señal.
        """
        if self.signal_group is None:
            return

        # Selección de archivo destino
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        # Procesar señales
        row = []
        headers = []
        for name in self.target_signals:
            signal = self.signal_group.get(name)
            if signal is None:
                headers.extend([f"{name}_mean", f"{name}_max"])
                row.extend(["", ""])
                continue
            data = signal.get_full_signal()
            fs = signal.fs
            if len(data) == 0 or fs <= 0:
                headers.extend([f"{name}_mean", f"{name}_max"])
                row.extend(["", ""])
                continue
            n_minutes = int(np.ceil(len(data) / (fs * 60)))
            for minute in range(n_minutes):
                start = int(minute * fs * 60)
                end = int(min((minute + 1) * fs * 60, len(data)))
                segment = data[start:end]
                if len(segment) == 0:
                    mean = ""
                    maxv = ""
                else:
                    mean_val = (
                        float(np.mean(segment))
                        if np.isscalar(np.mean(segment))
                        else float(np.mean(segment).item())
                    )
                    maxv_val = (
                        float(np.max(segment))
                        if np.isscalar(np.max(segment))
                        else float(np.max(segment).item())
                    )
                    # Formatear con punto decimal
                    mean = f"{mean_val:.6f}"
                    maxv = f"{maxv_val:.6f}"
                headers.append(f"{name}_mean_min{minute+1}")
                headers.append(f"{name}_max_min{minute+1}")
                row.append(mean)
                row.append(maxv)
        # Escribir CSV
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                writer.writerow(row)
            QMessageBox.information(self, "Export", f"Exported CSV to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

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
        self.tilt_tab.update_tilt_tab(self.signal_group, self.target_signals, file_path)

        # (Tuning tab eliminado)

    def _apply_hr_global(self, hr_signal):
        # (Callback de HR global desde tuning eliminado)
        self.signal_group.replace("HR", hr_signal)
        # Refresca las vistas que dependan de HR
        self.viewer_tab.load_data(
            file_path=None,
            signal_group=self.signal_group,
            sampling_rates=self.sampling_rates,
            time_axes=self.time_axes,
            chunk_size=self.chunk_size,
            channel_names=self.target_signals,
        )
        self.analysis_tab.update_analysis_tab(
            self.signal_group, self.target_signals, None
        )
        self.tilt_tab.update_tilt_tab(self.signal_group, self.target_signals, None)

    def closeEvent(self, event):
        """
        Handle app close event.
        """
        event.accept()
