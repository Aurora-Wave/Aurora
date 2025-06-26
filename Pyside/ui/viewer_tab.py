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
    Visualization tab for physiological signals.
    Supports scrolling, chunk loading, and synchronized multi-signal display.
    """

    def __init__(self, main_window):
        """
        Args:
            main_window (QMainWindow): Reference to the main window for global access.
        """
        super().__init__()
        self.main_window = main_window
        self.signal_group = None
        self.file_path = None
        self.chunk_size = 0
        self.sampling_rates = {}
        self.time_axes = {}
        self.target_signals = []

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
        Initialize one plot per signal to visualize.
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

    def load_data(self, file_path, signal_group, sampling_rates, time_axes, chunk_size, channel_names):
        """
        Configures the viewer tab with given signal group and GUI controls.

        Args:
            file_path (str): Path to the loaded file.
            signal_group (SignalGroup): Signal group containing all channels.
            sampling_rates (dict): Sampling frequency per channel.
            time_axes (dict): Time vector per channel.
            chunk_size (int): Visualization chunk window in seconds.
            channel_names (list[str]): Channels to visualize.
        """
        self.signal_group = signal_group
        self.file_path = file_path
        self.sampling_rates = sampling_rates
        self.time_axes = time_axes
        self.chunk_size = chunk_size
        self.target_signals = channel_names
        self.max_len = max([len(self.time_axes[c]) for c in self.target_signals if c in self.time_axes])

        self.setup_plots(self.target_signals)

        # Remove previous controls
        if self.chunk_size_spinbox:
            self.controls_layout.removeWidget(self.chunk_size_spinbox)
            self.chunk_size_spinbox.deleteLater()
            self.chunk_size_spinbox = None
        if self.scrollbar:
            self.controls_layout.removeWidget(self.scrollbar)
            self.scrollbar.setParent(None)
            self.scrollbar = None

        # Add chunk size selector
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(1)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(self.chunk_size)
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.setToolTip("Chunk size (seconds)")
        self.chunk_size_spinbox.valueChanged.connect(self.on_chunk_size_changed)
        self.controls_layout.addWidget(QLabel("Window:"))
        self.controls_layout.addWidget(self.chunk_size_spinbox)

        # Add scrollbar for navigation
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
        self.scrollbar.setMaximum(min_duration - self.chunk_size if min_duration > self.chunk_size else 0)
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self.request_chunk)
        self.controls_layout.addWidget(self.scrollbar)

        # Initialize chunk loader
        self.chunk_loader = ChunkLoader(
            file_path=self.file_path,
            channel_names=self.target_signals,
            chunk_size=self.chunk_size,
            signal_group=self.signal_group,
        )
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)

        # Load first window
        self.request_chunk(0)

    def request_chunk(self, value):
        """
        Request a chunk of signal to visualize based on scrollbar position.
        """
        start = int(value)
        end = start + self.chunk_size
        self.chunk_loader.request_chunk(start, end)

    def update_chunk(self, start, end, data_dict):
        """
        Update each signal plot with the requested chunk data.
        """
        max_points = 5000  # Downsampling threshold
        for i, signal_name in enumerate(self.target_signals):
            p = self.plots[i]
            if not hasattr(p, "curve") or p.curve is None:
                p.curve = p.plot([], [], pen="y", autoDownsample=True, antialias=False)

            fs = self.sampling_rates[signal_name]
            expected_len = int(self.chunk_size * fs)

            if signal_name in data_dict:
                y = data_dict[signal_name]
                if len(y) < expected_len:
                    y = np.concatenate([y, np.full(expected_len - len(y), np.nan, dtype=np.float32)])
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
        Update chunk loader and scrollbar when chunk duration changes.
        """
        self.chunk_size = value
        durations = [
            self.time_axes[signal_name][-1]
            for signal_name in self.target_signals
            if signal_name in self.sampling_rates and signal_name in self.time_axes
        ]
        min_duration = int(min(durations)) if durations else 0
        self.scrollbar.setMaximum(min_duration - self.chunk_size if min_duration > self.chunk_size else 0)

        # Update chunk loader with new size
        self.chunk_loader = ChunkLoader(
            file_path=self.file_path,
            channel_names=self.target_signals,
            chunk_size=self.chunk_size,
            signal_group=self.signal_group,
        )
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        self.request_chunk(self.scrollbar.value())
