import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollBar,
    QHBoxLayout,
    QSpinBox,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from processing.chunk_loader import ChunkLoader


class TiltTab(QWidget):
    """
    Pestaña para graficar todas las señales entre 'Tilt Angle' y 'Tilt down', con barra de desplazamiento y ajuste de ventana.
    """

    def __init__(self):
        super().__init__()
        self.plot_widget = pg.GraphicsLayoutWidget()
        self._plots = []
        self._data_record = None
        self._target_channels = None
        self._tilt_start = 0
        self._tilt_end = 0
        self._window_size = 10  # segundos
        self._scrollbar = QScrollBar(Qt.Horizontal)
        self._scrollbar.valueChanged.connect(self._on_scroll)
        self._spinbox = QSpinBox()
        self._spinbox.setMinimum(1)
        self._spinbox.setMaximum(3600)
        self._spinbox.setValue(self._window_size)
        self._spinbox.setSuffix(" s")
        self._spinbox.valueChanged.connect(self._on_window_size_changed)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Window (s):"))
        controls_layout.addWidget(self._spinbox)
        controls_layout.addWidget(QLabel("Scroll:"))
        controls_layout.addWidget(self._scrollbar)
        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self.plot_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

    def update_tilt_tab(self, data_record, target_channels=None, file_path=None):
        self._data_record = data_record
        self._target_channels = target_channels
        self._file_path = file_path
        self._setup_tilt_window()
        self._setup_chunk_loader()
        self._request_chunk()

    def _setup_chunk_loader(self):
        if not hasattr(self, "_chunk_loader") or self._chunk_loader is None:
            self._chunk_loader = ChunkLoader(
                self._file_path,
                self._target_channels or [s.Name for s in self._data_record.Signals],
                self._window_size,
                data_record=self._data_record,  # Reutiliza el data_record ya cargado
            )
            self._chunk_loader.chunk_loaded.connect(self._on_chunk_loaded)
        else:
            self._chunk_loader.channel_names = self._target_channels or [
                s.Name for s in self._data_record.Signals
            ]
            self._chunk_loader.chunk_size = self._window_size
            self._chunk_loader.set_data_record(self._data_record)

    def _setup_tilt_window(self):
        # Determinar el rango Tilt global (mínimo inicio, máximo fin entre canales)
        tilt_starts = []
        tilt_ends = []
        for channel_name in self._target_channels or [
            s.Name for s in self._data_record.Signals
        ]:
            signal = next(
                (
                    s
                    for s in self._data_record.Signals
                    if channel_name.upper() in s.Name.upper()
                ),
                None,
            )
            if signal is None:
                continue
            tilt_angle = next(
                (c for c in signal.MarkerData if c.text and "Tilt Angle" in c.text),
                None,
            )
            tilt_down = next(
                (c for c in signal.MarkerData if c.text and "Tilt down" in c.text), None
            )
            if tilt_angle and tilt_down and tilt_down.time > tilt_angle.time:
                tilt_starts.append(tilt_angle.time)
                tilt_ends.append(tilt_down.time)
        if tilt_starts and tilt_ends:
            self._tilt_start = max(min(tilt_starts), 0)
            self._tilt_end = max(tilt_ends)
        else:
            self._tilt_start = 0
            self._tilt_end = 0
        # Configurar scrollbar
        max_scroll = max(int(self._tilt_end - self._tilt_start - self._window_size), 0)
        self._scrollbar.setMinimum(0)
        self._scrollbar.setMaximum(max_scroll)
        self._scrollbar.setPageStep(1)
        self._scrollbar.setSingleStep(1)
        self._scrollbar.setValue(0)

    def _on_window_size_changed(self, value):
        self._window_size = value
        self._setup_tilt_window()
        self._setup_chunk_loader()
        self._request_chunk()

    def _on_scroll(self, value):
        self._request_chunk()

    def _request_chunk(self):
        if self._data_record is None or not hasattr(self, "_chunk_loader"):
            return
        window_start = self._tilt_start + self._scrollbar.value()
        window_end = min(window_start + self._window_size, self._tilt_end)
        self._chunk_loader.request_chunk(window_start, window_end)

    def _on_chunk_loaded(self, start, end, data_dict):
        # Mantener los plots y solo actualizar los datos
        target_channels = self._target_channels or [
            s.Name for s in self._data_record.Signals
        ]
        if not self._plots or len(self._plots) != len(target_channels):
            self.plot_widget.clear()
            self._plots = []
            for row, channel_name in enumerate(target_channels):
                p = self.plot_widget.addPlot(row=row, col=0, title=channel_name)
                p.setLabel("bottom", "Time (s)")
                p.setLabel("left", channel_name)
                curve = p.plot([], [], pen="b", autoDownsample=True, antialias=False)
                self._plots.append((p, curve))
        for i, channel_name in enumerate(target_channels):
            signal = next(
                (
                    s
                    for s in self._data_record.Signals
                    if channel_name.upper() in s.Name.upper()
                ),
                None,
            )
            if signal is None:
                continue
            fs = getattr(signal, "TSR", 1000)
            t = np.arange(int((end - start) * fs)) / fs + start
            y = data_dict.get(channel_name)
            if y is None or len(y) == 0:
                self._plots[i][1].setData([], [])
                continue
            self._plots[i][1].setData(t[: len(y)], y)
