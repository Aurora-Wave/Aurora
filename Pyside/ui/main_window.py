"""
main_window.py
----------------
Ventana principal de la aplicación de visualización y análisis de señales fisiológicas.
Orquesta la carga de archivos y la integración de las pestañas de visualización y análisis ECG.
"""

from PySide6.QtWidgets import QMainWindow, QFileDialog, QPushButton, QVBoxLayout, QWidget, QTabWidget
import numpy as np
from ui.viewer_tab import ViewerTab
from ui.ecg_tab import ECGTab

class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación. Gestiona la carga de archivos y la integración de pestañas.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visor de Señales Fisiológicas")
        self.resize(1200, 800)

        # Inicialización de pestañas
        self.tabs = QTabWidget()
        # Pestaña 1: visor general
        self.viewer_tab = ViewerTab(self)
        self.tabs.addTab(self.viewer_tab, "Visor señales")
        # Pestaña 2: análisis ECG
        self.ecg_tab = ECGTab()
        self.tabs.addTab(self.ecg_tab, "Análisis ECG")

        # Layout principal
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

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

    def load_data(self):
        """
        Abre un diálogo para seleccionar un archivo .adicht y carga los datos.
        Configura las pestañas con los datos cargados.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo .adicht", "", "Archivos ADI (*.adicht)")
        if not file_path:
            return
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

    def closeEvent(self, event):
        event.accept()
