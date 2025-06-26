"""
main_window.py
<<<<<<< Updated upstream
----------------
Ventana principal de la aplicación de visualización y análisis de señales fisiológicas.
Orquesta la carga de archivos y la integración de las pestañas de visualización y análisis ECG.
=======
--------------
Main window for the physiological signals visualization and analysis application.
Handles file loading and integrates the signal viewer and analysis tabs.
>>>>>>> Stashed changes
"""

from PySide6.QtWidgets import QMainWindow, QFileDialog, QPushButton, QVBoxLayout, QWidget, QTabWidget
import numpy as np
from ui.viewer_tab import ViewerTab
<<<<<<< Updated upstream
from ui.ecg_tab import ECGTab
=======
from ui.analysis_tab import AnalysisTab
from ui.tilt_tab import TiltTab

>>>>>>> Stashed changes

class MainWindow(QMainWindow):
    """
    Main window of the application. Manages the interface layout, file loading,
    and the coordination of different analysis tabs.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visor de Señales Fisiológicas")
        self.resize(1200, 800)

        # Tab container
        self.tabs = QTabWidget()

        # Tab 1: General signal viewer
        self.viewer_tab = ViewerTab(self)
<<<<<<< Updated upstream
        self.tabs.addTab(self.viewer_tab, "Visor señales")
        # Pestaña 2: análisis ECG
        self.ecg_tab = ECGTab()
        self.tabs.addTab(self.ecg_tab, "Análisis ECG")
=======
        self.tabs.addTab(self.viewer_tab, "Signals Viewer")
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
        # Botón de carga de archivo
        self.load_button = QPushButton("Cargar archivo")
        self.load_button.clicked.connect(self.load_data)
        main_layout.insertWidget(0, self.load_button)

        # Propiedades de datos
        self.trace = None
        self.sampling_rates = {}
        self.time_axes = {}
        self.max_len = 0
        self.chunk_size = 120  # Duración del chunk en segundos
        self.target_signals = ['HR', 'ECG', 'FBP', 'Valsalva', 'CO']
=======
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
>>>>>>> Stashed changes

    def load_data(self):
        """
        Opens a file dialog to select a .adicht file and loads the signal data.
        Passes the data to the viewer and analysis tabs.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo .adicht", "", "Archivos ADI (*.adicht)")
        if not file_path:
            return
<<<<<<< Updated upstream
        from data.adicht_loader import get_trace_from_path
        self.trace = get_trace_from_path(file_path)
        # Extraer metadatos y señales de interés
        self.sampling_rates.clear()
        self.time_axes.clear()
        self.max_len = 0
        for sig in self.trace.Signal:
            for canal in self.target_signals:
                if canal.upper() in sig.Name.upper():
                    fs = getattr(sig, 'TSR', 1000)
                    full_signal = np.concatenate([sig.BB, sig.ProData, sig.AB])
                    self.sampling_rates[canal] = fs
                    self.time_axes[canal] = np.arange(len(full_signal)) / fs
                    if len(full_signal) > self.max_len:
                        self.max_len = len(full_signal)
        # Configurar visor general
        self.viewer_tab.load_data(
            file_path,
            self.trace,
            self.sampling_rates,
            self.time_axes,
            self.chunk_size,
            self.target_signals
        )
        # Configurar ECGTab
        ecg_data = None
        ecg_fs = None
        for sig in self.trace.Signal:
            if 'ECG' in sig.Name.upper():
                fs = getattr(sig, 'TSR', 1000)
                full_signal = np.concatenate([sig.BB, sig.ProData, sig.AB])
                ecg_data = full_signal.astype(np.float32)
                ecg_fs = fs
        self.ecg_tab.update_ecg_tab(ecg_data, ecg_fs)
=======

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
>>>>>>> Stashed changes

    def closeEvent(self, event):
        """
        Handle app close event.
        """
        event.accept()
