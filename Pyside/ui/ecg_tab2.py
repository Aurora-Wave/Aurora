"""
ecg_tab.py
----------
Pestaña de análisis ECG: controles, gráficos y lógica de análisis.
Permite seleccionar parámetros y visualizar resultados de detección de RR peaks y transformada wavelet.
"""

import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QComboBox, QGroupBox,QPushButton
import pyqtgraph as pg
from processing.ecg_analyzer import ECGAnalyzer

class ECGTab(QWidget):
    """
    Pestaña de análisis ECG. Permite seleccionar parámetros y visualizar resultados interactivos.
    """
    def __init__(self):
        super().__init__()
        # Widgets de gráficos
        self.ecg_plot_widget = pg.GraphicsLayoutWidget()
        self.rr_plot_widget = pg.GraphicsLayoutWidget()
        self.wavelet_plot_widget = pg.GraphicsLayoutWidget()

        #
        # Controles interactivos

        #RR Distance
        self.rr_distance_spin = QDoubleSpinBox()
        self.rr_distance_spin.setRange(0.1, 2.0)
        self.rr_distance_spin.setSingleStep(0.05)
        self.rr_distance_spin.setValue(0.4)
        self.rr_distance_spin.setSuffix(" s")
        self.rr_distance_spin.setToolTip("Minimum RR peak distance (seconds)")

        # Wavelet config
        #Wavelet window type
        self.wavelet_combo = QComboBox()
        self.wavelet_combo.addItems(["db4", "db6", "haar", "sym4"])
        self.wavelet_combo.setCurrentText("haar")
        self.wavelet_combo.setToolTip("Wavelet type for decomposition")
        #Wavelet level
        self.wavelet_level_spin = QDoubleSpinBox()
        self.wavelet_level_spin.setRange(1, 8)
        self.wavelet_level_spin.setValue(5)
        self.wavelet_level_spin.setToolTip("Wavelet decomposition level")
        # Visualization start time
        self.sample_start_spin = QDoubleSpinBox()
        self.sample_start_spin.setRange(0, 1e6)
        self.sample_start_spin.setValue(600)
        self.sample_start_spin.setSingleStep(10)
        self.sample_start_spin.setToolTip("Start time of analysis windows (s)")
        # Visualization duration time
        self.sample_size_spin = QDoubleSpinBox()
        self.sample_size_spin.setRange(1, 1e5)
        self.sample_size_spin.setValue(20)
        self.sample_size_spin.setSingleStep(10)
        self.sample_size_spin.setToolTip("Duration of analysis window (s)")
        #Apply buttom
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._update_graphs)

        # Layout de controles
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Start (s):"))
        controls_layout.addWidget(self.sample_start_spin)
        controls_layout.addWidget(QLabel("Size (s):"))
        controls_layout.addWidget(self.sample_size_spin)
        controls_layout.addWidget(QLabel("RR Distance (s):"))
        controls_layout.addWidget(self.rr_distance_spin)
        controls_layout.addWidget(QLabel("Wavelet:"))
        controls_layout.addWidget(self.wavelet_combo)
        controls_layout.addWidget(QLabel("Level:"))
        controls_layout.addWidget(self.wavelet_level_spin)
        controls_layout.addWidget(self.apply_button)
        controls_group = QGroupBox("Parámetros de análisis ECG")
        controls_group.setLayout(controls_layout)

        # Layout principal
        ecg_layout = QVBoxLayout()
        ecg_layout.addWidget(controls_group)
        ecg_layout.addWidget(self.ecg_plot_widget)
        ecg_layout.addWidget(self.rr_plot_widget)
        ecg_layout.addWidget(self.wavelet_plot_widget)
        self.setLayout(ecg_layout)

        # Conexión de controles a actualización automática
        self.rr_distance_spin.valueChanged.connect(self._on_params_changed)
        self.wavelet_combo.currentTextChanged.connect(self._on_params_changed)
        self.wavelet_level_spin.valueChanged.connect(self._on_params_changed)
        self.sample_start_spin.valueChanged.connect(self._on_params_changed)
        self.sample_size_spin.valueChanged.connect(self._on_params_changed)
        # Datos actuales
        self._ecg_data = None
        self._ecg_fs = None

    def update_ecg_tab(self, ecg_data, ecg_fs):
        """
        Actualiza los gráficos de la pestaña de análisis ECG según los parámetros seleccionados.
        Args:
            ecg_data (np.ndarray): Señal ECG cruda.
            ecg_fs (float): Frecuencia de muestreo.
        """
        self._ecg_data = ecg_data
        self._ecg_fs = ecg_fs
        self._update_graphs()

    def _on_params_changed(self, *args):
        """
        Llama a la actualización de gráficos cuando cambian los parámetros de análisis.
        """
        self._update_graphs()

    def _update_graphs(self):
        """
        Actualiza los gráficos de ECG, RR peaks y transformada wavelet.
        """
        self.ecg_plot_widget.clear()
        self.rr_plot_widget.clear()
        self.wavelet_plot_widget.clear()
        ecg_data = self._ecg_data
        ecg_fs = self._ecg_fs
        if ecg_data is None or ecg_fs is None:
            #Fixme
            return
        start_sec = self.sample_start_spin.value()
        size_sec = self.sample_size_spin.value()
        start_idx = int(start_sec * ecg_fs)
        end_idx = int((start_sec + size_sec) * ecg_fs)
        ecg_segment = ecg_data[start_idx:end_idx]
        t = np.arange(len(ecg_segment)) / ecg_fs + start_sec

        # ECG crudo
        p1 = self.ecg_plot_widget.addPlot(title="Raw ECG")
        p1.plot(t, ecg_segment, pen='c')

        # RR peaks
        rr_distance = self.rr_distance_spin.value()
        wavelet = self.wavelet_combo.currentText()
        level = int(self.wavelet_level_spin.value())
        rr_peaks = ECGAnalyzer.detect_rr_peaks(ecg_segment, ecg_fs, rr_distance,wavelet, level)
        
        p2 = self.rr_plot_widget.addPlot(title="ECG + RR peaks")
        p2.plot(t, ecg_segment, pen='c')
        if len(rr_peaks) > 0:
            p2.plot(t[rr_peaks], ecg_segment[rr_peaks], pen=None, symbol='o', symbolBrush='r', symbolSize=8)

        # Wavelet
        wavelet_rec, _ = ECGAnalyzer.wavelet_transform(ecg_segment, wavelet, level)
        p3 = self.wavelet_plot_widget.addPlot(title=f"Wavelet Transform ({wavelet}, level {level})")        
        p3.plot(t[:len(wavelet_rec)], wavelet_rec, pen='m')
