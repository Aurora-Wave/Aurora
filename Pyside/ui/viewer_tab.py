"""
viewer_tab.py
-------------
General visualization tab for physiological signals.
Encapsulates plotting logic, scrollbar, and chunk loading.
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollBar,
    QHBoxLayout,
    QLabel,
    QSpinBox,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from ui.widgets.selectable_viewbox import SelectableViewBox
from processing.chunk_loader import ChunkLoader


class ViewerTab(QWidget):
    """
    Pestaña de visualización general de señales fisiológicas.
    Permite navegar por las señales cargadas usando chunk loading y barra de desplazamiento.
    Sincroniza la selección de regiones entre gráficos.
    """

    def __init__(self, main_window):
        """
        Args:
            main_window (QMainWindow): Referencia a la ventana principal para acceso a datos globales.
        """
        super().__init__()
        self.main_window = main_window
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plots = []
        self._regions = []
        self.scrollbar = None
        self.chunk_size_spinbox = None
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(5)
        self.plot_area_layout = QVBoxLayout()
        self.plot_area_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_area_layout.setSpacing(0)
        self.plot_area_layout.addLayout(self.controls_layout)
        self.plot_area_layout.addWidget(self.plot_widget)
        self.setLayout(self.plot_area_layout)

    def setup_plots(self, target_signals):
        """
        Inicializa los gráficos para cada señal objetivo.
        Args:
            target_signals (list): List of signal names to display.
        """
        self.plot_widget.clear()
        self.plots = []
        self._regions = []
        for i, signal_name in enumerate(target_signals):
            vb = SelectableViewBox(self.main_window, i)
            p = self.plot_widget.addPlot(row=i, col=0, title=signal_name, viewBox=vb)
            p.setLabel("bottom", "Time (s)")
            p.setLabel("left", signal_name)
            p.setMouseEnabled(x=False, y=False)
            self.plots.append(p)
            self._regions.append(None)

    def load_data(
        self,
        file_path,
        data_record,
        sampling_rates,
        time_axes,
        chunk_size,
        target_signals,
    ):
        """
        Configura los gráficos, barra de desplazamiento y chunk loader para la pestaña de visualización general.
        Args:
            file_path (str): Absolute path to the data file.
            data_record (Trace): Loaded data object.
            sampling_rates (dict): Sampling rates per channel.
            time_axes (dict): Time axes per channel.
            chunk_size (int): Chunk duration in seconds.
            target_signals (list): List of signals to display.
        """
        self.file_path = file_path
        self.data_record = data_record
        self.sampling_rates = sampling_rates
        self.time_axes = time_axes
        self.chunk_size = chunk_size
        self.target_signals = target_signals
        self.max_len = max(
            [len(self.time_axes[c]) for c in self.target_signals if c in self.time_axes]
        )
        self.setup_plots(self.target_signals)
        # Controls for chunk size and scrollbar
        if self.chunk_size_spinbox:
            self.controls_layout.removeWidget(self.chunk_size_spinbox)
            self.chunk_size_spinbox.deleteLater()
            self.chunk_size_spinbox = None
        if self.scrollbar:
            self.controls_layout.removeWidget(self.scrollbar)
            self.scrollbar.setParent(None)
            self.scrollbar = None
        # SpinBox for chunk size
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(1)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(self.chunk_size)
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.setToolTip("Chunk size (seconds)")
        self.chunk_size_spinbox.valueChanged.connect(self.on_chunk_size_changed)
        self.controls_layout.addWidget(QLabel("Window:"))
        self.controls_layout.addWidget(self.chunk_size_spinbox)
        # Scrollbar
        self.scrollbar = QScrollBar()
        self.scrollbar.setOrientation(Qt.Horizontal)
        min_fs = min(self.sampling_rates.values())
        durations = [
            self.time_axes[signal_name][-1]
            for signal_name in self.target_signals
            if signal_name in self.sampling_rates and signal_name in self.time_axes
        ]
        min_duration = int(min(durations)) if durations else 0
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(
            min_duration - self.chunk_size if min_duration > self.chunk_size else 0
        )
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self.request_chunk)
        self.controls_layout.addWidget(self.scrollbar)
        # Chunk loader reusing the already loaded data_record
        self.chunk_loader = ChunkLoader(
            self.file_path,
            self.target_signals,
            self.chunk_size,
            signal_group=self.data_record,
        )
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        # Load first chunk
        self.request_chunk(0)

    def request_chunk(self, value):
        """
        Solicita un nuevo chunk de datos al cambiar la posición del scrollbar.
        Args:
            value (int): Initial second of the chunk to display.
        """
        start = int(value)
        end = start + self.chunk_size
        self.chunk_loader.request_chunk(start, end)

    def update_chunk(self, start, end, data_dict):
        """
        Actualiza los gráficos con los datos del chunk solicitado.
        Args:
            start (int): Initial second of the chunk.
            end (int): Final second of the chunk.
            data_dict (dict): Dictionary {signal_name: chunk_data}
        """
        max_points = 5000  # Manual downsampling limit
        for i, signal_name in enumerate(self.target_signals):
            p = self.plots[i]
            if not hasattr(p, "curve") or p.curve is None:
                p.curve = p.plot([], [], pen="y", autoDownsample=True, antialias=False)
            fs = self.sampling_rates[signal_name]
            expected_len = int(self.chunk_size * fs)
            if signal_name in data_dict:
                y = data_dict[signal_name]
                if len(y) < expected_len:
                    y = np.concatenate(
                        [y, np.full(expected_len - len(y), np.nan, dtype=np.float32)]
                    )
                t = np.arange(expected_len) / fs + start
                if len(y) > max_points:
                    step = int(np.ceil(len(y) / max_points))
                    y = y[::step]
                    t = t[::step]
                else:
                    step = 1
                p.curve.setData(t, y, downsample=step, autoDownsample=True)
                p.setXRange(start, start + self.chunk_size, padding=0)
                if np.any(~np.isnan(y)):
                    y_valid = y[~np.isnan(y)]
                    y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                    p.setYRange(y_min, y_max)
                else:
                    p.setYRange(0, 1)
            else:
                t = np.arange(expected_len) / fs + start
                y = np.full(expected_len, np.nan, dtype=np.float32)
                if len(y) > max_points:
                    step = int(np.ceil(len(y) / max_points))
                    y = y[::step]
                    t = t[::step]
                else:
                    step = 1
                p.curve.setData(t, y, downsample=step, autoDownsample=True)
                p.setXRange(start, start + self.chunk_size, padding=0)
                p.setYRange(0, 1)

    def on_chunk_size_changed(self, value):
        """
        Actualiza el tamaño del chunk y recarga el chunk actual.
        """
        self.chunk_size = value
        # Update scrollbar maximum
        durations = [
            self.time_axes[signal_name][-1]
            for signal_name in self.target_signals
            if signal_name in self.sampling_rates and signal_name in self.time_axes
        ]
        min_duration = int(min(durations)) if durations else 0
        self.scrollbar.setMaximum(
            min_duration - self.chunk_size if min_duration > self.chunk_size else 0
        )
        # Update chunk loader
        self.chunk_loader = ChunkLoader(
            self.file_path,
            self.target_signals,
            self.chunk_size,
            signal_group=self.data_record,
        )
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        # Reload current chunk
        self.request_chunk(self.scrollbar.value())
