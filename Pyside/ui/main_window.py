"""
main_window.py
----------------
Main window for the physiological signals visualization and analysis application.
Orchestrates file loading and the integration of visualization and ECG analysis tabs.
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
from ui.ecg_tab import ECGTab
from ui.tilt_tab import TiltTab


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación. Gestiona la carga de archivos y la integración de pestañas.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Physiological Signals Viewer")
        self.resize(1200, 800)

        # Inicialización de pestañas
        self.tabs = QTabWidget()
        # Pestaña 1: visor general
        self.viewer_tab = ViewerTab(self)
        self.tabs.addTab(self.viewer_tab, "Signals Viewer")
        # Pestaña 2: análisis ECG
        self.ecg_tab = ECGTab()
        self.tabs.addTab(self.ecg_tab, "ECG Analysis")
        # Pestaña 3: Test de Tilt
        self.tilt_tab = TiltTab()
        self.tabs.addTab(self.tilt_tab, "Tilt Test")

        # Layout principal
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Botón de carga de archivo
        self.load_button = QPushButton("Load file")
        self.load_button.clicked.connect(self.load_data)
        main_layout.insertWidget(0, self.load_button)

        # Propiedades de datos
        self.data_record = None
        self.sampling_rates = {}
        self.time_axes = {}
        self.max_len = 0
        self.chunk_size = 120  # Duración del chunk en segundos
        self.target_signals = ["ECG", "FBP",'MCA-L', 'MCA-R', 'Tilt Angle']

    def load_data(self):
        """
        Abre un diálogo para seleccionar un archivo .adicht y carga los datos.
        Configura las pestañas con los datos cargados.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select .adicht file", "", "ADI files (*.adicht)"
        )
        if not file_path:
            return
        from data.adicht_loader import get_data_record_from_path

        self.data_record = get_data_record_from_path(file_path)
        # Extraer metadatos y señales de interés
        self.sampling_rates.clear()
        self.time_axes.clear()
        self.max_len = 0
        for signal in self.data_record.Signals:
            for channel_name in self.target_signals:
                if channel_name.upper() in signal.Name.upper():
                    fs = getattr(signal, "TSR", 1000)
                    full_signal = np.concatenate([signal.BB, signal.ProData, signal.AB])
                    self.sampling_rates[channel_name] = fs
                    self.time_axes[channel_name] = np.arange(len(full_signal)) / fs
                    if len(full_signal) > self.max_len:
                        self.max_len = len(full_signal)
        # Configurar visor general
        self.viewer_tab.load_data(
            file_path,
            self.data_record,
            self.sampling_rates,
            self.time_axes,
            self.chunk_size,
            self.target_signals,
        )
        # Configurar ECGTab
        ecg_data = None
        ecg_fs = None
        for signal in self.data_record.Signals:
            if "ECG" in signal.Name.upper():
                fs = getattr(signal, "TSR", 1000)
                full_signal = np.concatenate([signal.BB, signal.ProData, signal.AB])
                ecg_data = full_signal.astype(np.float32)
                ecg_fs = fs
        self.ecg_tab.update_ecg_tab(ecg_data, ecg_fs)
        self.tilt_tab.update_tilt_tab(self.data_record, self.target_signals, file_path)

    def closeEvent(self, event):
        event.accept()
