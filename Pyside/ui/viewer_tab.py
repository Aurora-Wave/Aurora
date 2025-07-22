import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollBar,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from ui.widgets.selectable_viewbox import SelectableViewBox
from processing.chunk_loader import ChunkLoader


class ViewerTab(QWidget):
    """
    Tab for general physiological signal visualization.
    Allows chunk navigation and interaction.
    """

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.plots = []
        self.scrollbar = None
        self.chunk_size_spinbox = None

        # Scroll area to allow vertical scrolling of many plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(5)
        self.scroll_area.setWidget(self.scroll_content)

        # Control bar (chunk size + scrollbar)
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.controls_layout)
        main_layout.addWidget(self.scroll_area)
        self.setLayout(main_layout)
        self._regions = []  # Needed for synchronized region selection

    def setup_plots(self, target_signals):
        """Initialize plot widgets for the selected signals."""
        self.clear_plots()
        self.plots = []

        for i, signal_name in enumerate(target_signals):
            vb = SelectableViewBox(self, i)
            plot = pg.PlotWidget(viewBox=vb)
            plot.setMinimumHeight(200)
            plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", signal_name)
            plot.setMouseEnabled(x=False, y=False)
            curve = plot.plot([], [], pen="y")
            plot.curve = curve
            self.scroll_layout.addWidget(plot)
            self.plots.append(plot)
            self._regions.append(None)  # Track region per plot

    def clear_plots(self):
        """Remove all existing plots from layout."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def load_data(self, file_path, data_record, sampling_rates, time_axes, chunk_size, target_signals):
        """
        Set up plots, scrollbar and chunk loader for the viewer tab.
        """
        self.file_path = file_path
        self.data_record = data_record
        self.sampling_rates = sampling_rates
        self.time_axes = time_axes
        self.chunk_size = chunk_size
        self.target_signals = target_signals

        # Precompute global Y ranges
        self.y_ranges = {}
        for signal_name in self.target_signals:
            signal = self.data_record[signal_name]
            y_valid = signal.data[~np.isnan(signal.data)]
            if len(y_valid):
                y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
            else:
                y_min, y_max = 0, 1
            self.y_ranges[signal_name] = (y_min, y_max)

        self.setup_plots(self.target_signals)

        # Controls cleanup
        if self.chunk_size_spinbox:
            self.controls_layout.removeWidget(self.chunk_size_spinbox)
            self.chunk_size_spinbox.deleteLater()
            self.chunk_size_spinbox = None
        if self.scrollbar:
            self.controls_layout.removeWidget(self.scrollbar)
            self.scrollbar.deleteLater()
            self.scrollbar = None

        # Chunk size spinbox
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
        min_duration = int(min(self.time_axes[ch][-1] for ch in self.target_signals))
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self.request_chunk)
        self.controls_layout.addWidget(self.scrollbar)

        # Chunk loader
        self.chunk_loader = ChunkLoader(
            manager=self.main_window.data_manager,
            file_path=self.file_path,
            channel_names=self.target_signals,
            chunk_size=self.chunk_size,
        )
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        self.request_chunk(0)

    def request_chunk(self, value):
        start = int(value)
        end = start + self.chunk_size
        self.chunk_loader.request_chunk(start, end)

    def update_chunk(self, start, end, data_dict):
        for i, signal_name in enumerate(self.target_signals):
            p = self.plots[i]
            fs = self.sampling_rates[signal_name]
            expected_len = int(self.chunk_size * fs)
            y = data_dict.get(signal_name, np.full(expected_len, np.nan, dtype=np.float32))

            if len(y) < expected_len:
                y = np.concatenate([y, np.full(expected_len - len(y), np.nan, dtype=np.float32)])

            t = np.arange(expected_len) / fs + start

            max_points = 5000
            if len(y) > max_points:
                step = int(np.ceil(len(y) / max_points))
                y = y[::step]
                t = t[::step]

            p.curve.setData(t, y)
            p.setXRange(start, end, padding=0)
            y_min, y_max = self.y_ranges.get(signal_name, (0, 1))
            p.setYRange(y_min, y_max)

    def on_chunk_size_changed(self, value):
        self.chunk_size = value
        min_duration = int(min(self.time_axes[ch][-1] for ch in self.target_signals))
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.chunk_loader.chunk_size = value
        self.request_chunk(self.scrollbar.value())
