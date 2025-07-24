import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollBar, QHBoxLayout, QLabel, QSpinBox, QScrollArea, QSizePolicy,
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
        self._regions = []

        # Scroll area for vertical navigation
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

    def setup_plots(self, target_signals):
        """Initialize plot widgets for the selected signals."""
        self.clear_plots()
        self.plots = []
        self._regions = []
        for i, signal_name in enumerate(target_signals):
            vb = SelectableViewBox(self, i)
            plot = pg.PlotWidget(viewBox=vb)
            plot.setMinimumHeight(200)
            #plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", signal_name)
            plot.setMouseEnabled(x=False, y=False)
            curve = plot.plot([], [], pen="y")
            plot.curve = curve
            self.scroll_layout.addWidget(plot)
            self.plots.append(plot)
            self._regions.append(None)

    def clear_plots(self):
        """Remove all existing plots from layout."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def load_data(self, file_path, chunk_size, target_signals):
        """
        Set up plots, scrollbar and chunk loader for the viewer tab.
        Args:
            file_path (str): Path to the loaded file.
            chunk_size (int): Duration of each chunk in seconds.
            target_signals (list[str]): List of channel names to visualize.
        """
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.target_signals = target_signals

        # Precompute Y ranges for each channel using DataManager
        self.y_ranges = {}
        dm = self.main_window.data_manager
        for signal_name in self.target_signals:
            sig = dm.get_trace(self.file_path, signal_name)
            y_valid = sig.data[~np.isnan(sig.data)]
            if len(y_valid):
                y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
            else:
                y_min, y_max = 0, 1
            self.y_ranges[signal_name] = (y_min, y_max)

        self.setup_plots(self.target_signals)

        # Remove old controls
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

        # Scrollbar for navigation
        self.scrollbar = QScrollBar()
        self.scrollbar.setOrientation(Qt.Horizontal)
        # Get total duration for all selected signals
        durations = []
        for ch in self.target_signals:
            sig = dm.get_trace(self.file_path, ch)
            durations.append(len(sig.data) / sig.fs)
        min_duration = int(min(durations)) if durations else 1
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self.request_chunk)
        self.controls_layout.addWidget(self.scrollbar)

        # Instantiate the QObject-based ChunkLoader
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        self.request_chunk(0)

    def request_chunk(self, value):
        start = int(value)
        dm = self.main_window.data_manager
        self.chunk_loader.request_chunk(
            data_manager=dm,
            file_path=self.file_path,
            channel_names=self.target_signals,
            start_sec=start,
            duration_sec=self.chunk_size
        )

    def update_chunk(self, start, end, data_dict):
        for i, signal_name in enumerate(self.target_signals):
            p = self.plots[i]
            sig = self.main_window.data_manager.get_trace(self.file_path, signal_name)
            fs = sig.fs
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
        dm = self.main_window.data_manager
        durations = []
        for ch in self.target_signals:
            sig = dm.get_trace(self.file_path, ch)
            durations.append(len(sig.data) / sig.fs)
        min_duration = int(min(durations)) if durations else 1
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.request_chunk(self.scrollbar.value())
