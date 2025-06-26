"""
analysis_tab.py
---------------
General signal analysis tab. Allows signal selection, chunk scrolling, and editing.
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QSpinBox, QPushButton
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from processing.chunk_loader import ChunkLoader


class AnalysisTab(QWidget):
    """
    Analysis workspace for physiological signals.
    Allows signal selection, scrollable chunk loading, and peak visualization.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.signal_group = None
        self.file_path = None
        self.chunk_loader = None
        self.selected_signal_name = None
        self.fs = 1000

        self._params_by_signal = {}  # Save chunk state per signal

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # --- Controls ---
        self.controls_layout = QHBoxLayout()

        self.label = QLabel("Select Signal:")
        self.signal_selector = QComboBox()
        self.signal_selector.currentIndexChanged.connect(self._on_signal_selected)

        self.chunk_label = QLabel("Chunk (s):")
        self.chunk_size_box = QSpinBox()
        self.chunk_size_box.setRange(1, 600)
        self.chunk_size_box.setValue(60)
        self.chunk_size_box.setSuffix(" s")
        self.chunk_size_box.valueChanged.connect(self._on_chunk_size_changed)

        self.start_label = QLabel("Start (s):")
        self.start_time_box = QSpinBox()
        self.start_time_box.setRange(0, 99999)
        self.start_time_box.setValue(0)
        self.start_time_box.valueChanged.connect(self._on_scroll)

        self.prev_button = QPushButton("⏮ Previous")
        self.prev_button.clicked.connect(self._go_to_previous_chunk)

        self.next_button = QPushButton("Next ⏭")
        self.next_button.clicked.connect(self._go_to_next_chunk)

        for widget in [self.label, self.signal_selector,
                       self.chunk_label, self.chunk_size_box,
                       self.start_label, self.start_time_box,
                       self.prev_button, self.next_button]:
            self.controls_layout.addWidget(widget)

        # --- Plot area ---
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_items = [self.plot_widget.addPlot(row=i, col=0) for i in range(3)]
        for plot in self.plot_items:
            plot.showGrid(x=True, y=True)
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", "Amplitude")

        self.curves = [None, None, None]
        self.peak_scatter = None

        # Assemble
        self.layout.addLayout(self.controls_layout)
        self.layout.addWidget(self.plot_widget)

    def update_analysis_tab(self, signal_group, target_signals, file_path):
        """
        Called from MainWindow when new file is loaded.
        """
        self.signal_group = signal_group
        self.file_path = file_path

        self.signal_selector.blockSignals(True)
        self.signal_selector.clear()
        for name in signal_group.list_names():
            self.signal_selector.addItem(name)
        self.signal_selector.blockSignals(False)

        if self.signal_selector.count() > 0:
            self.signal_selector.setCurrentIndex(0)

    def _on_signal_selected(self, index):
        if index < 0:
            return

        name = self.signal_selector.currentText()
        self.selected_signal_name = name
        signal = self.signal_group.get(name)

        if not signal:
            return

        self.fs = signal.fs

        # Restore saved state for this signal
        params = self._params_by_signal.get(name, {"chunk_size": 60, "start_time": 0})
        self.chunk_size_box.setValue(params["chunk_size"])
        self.start_time_box.setValue(params["start_time"])

        self._create_loader_and_request_chunk()

    def _on_chunk_size_changed(self, value):
        if not self.selected_signal_name:
            return

        self._save_current_state()
        self._create_loader_and_request_chunk()

    def _on_scroll(self, value):
        if not self.selected_signal_name:
            return

        self._save_current_state()
        if self.chunk_loader:
            self.chunk_loader.request_chunk(value, value + self.chunk_size_box.value())

    def _go_to_next_chunk(self):
        current = self.start_time_box.value()
        chunk = self.chunk_size_box.value()
        self.start_time_box.setValue(current + chunk)

    def _go_to_previous_chunk(self):
        current = self.start_time_box.value()
        chunk = self.chunk_size_box.value()
        self.start_time_box.setValue(max(0, current - chunk))

    def _save_current_state(self):
        name = self.selected_signal_name
        if name:
            self._params_by_signal[name] = {
                "chunk_size": self.chunk_size_box.value(),
                "start_time": self.start_time_box.value(),
            }

    def _create_loader_and_request_chunk(self):
        if not self.selected_signal_name:
            return

        channels = [self.selected_signal_name]
        if self.selected_signal_name == "HR_GEN" and self.signal_group.get("ECG"):
            channels.append("ECG")

        self.chunk_loader = ChunkLoader(
            file_path=self.file_path,
            channel_names=channels,
            chunk_size=self.chunk_size_box.value(),
            signal_group=self.signal_group,
        )
        self.chunk_loader.chunk_loaded.connect(self._update_plots)
        self._on_scroll(self.start_time_box.value())

    def _update_plots(self, start, end, data_dict):
        name = self.selected_signal_name
        if name not in data_dict:
            return

        # Clear all plots
        for plot in self.plot_items:
            plot.clear()
        self.curves = [None, None, None]

        signal = self.signal_group.get(name)
        if signal is None:
            return

        y = data_dict[name]
        t = np.arange(len(y)) / self.fs + start

        if name == "ECG":
            # Plot 1: ECG raw
            self.curves[0] = self.plot_items[0].plot(t, y, pen="c")

            # Plot 2: ECG + peaks
            self.curves[1] = self.plot_items[1].plot(t, y, pen="y")
            peaks = signal.FMxI if hasattr(signal, "FMxI") else None
            if peaks is not None and len(peaks) > 0:
                rel_peaks = (peaks - int(start * self.fs)).astype(int)
                valid_peaks = rel_peaks[(rel_peaks >= 0) & (rel_peaks < len(y))]
                x_peaks = t[valid_peaks]
                y_peaks = y[valid_peaks]
                self.plot_items[1].plot(
                    x_peaks, y_peaks, pen=None, symbol='o', symbolBrush='r', symbolSize=10
                )

            # Plot 3: HR_GEN if available
            hr = self.signal_group.get("HR_GEN")
            if hr:
                hr_t = hr.time
                hr_y = hr.data
                mask = (hr_t >= start) & (hr_t <= end)
                self.curves[2] = self.plot_items[2].plot(hr_t[mask], hr_y[mask], pen="m")

        elif name == "HR_GEN":
            # Plot 1: ECG + peaks
            ecg = self.signal_group.get("ECG")
            if ecg:
                ecg_data, ecg_time = ecg.get_full_signal(include_time=True)
                mask = (ecg_time >= start) & (ecg_time <= end)
                ecg_seg = ecg_data[mask]
                time_seg = ecg_time[mask]
                self.curves[0] = self.plot_items[0].plot(time_seg, ecg_seg, pen="y")

                peaks = ecg.FMxI if hasattr(ecg, "FMxI") else None
                if peaks is not None and len(peaks) > 0:
                    rel_peaks = (peaks - int(start * ecg.fs)).astype(int)
                    valid_peaks = rel_peaks[(rel_peaks >= 0) & (rel_peaks < len(ecg_seg))]
                    x_peaks = time_seg[valid_peaks]
                    y_peaks = ecg_seg[valid_peaks]
                    self.plot_items[0].plot(
                        x_peaks, y_peaks, pen=None, symbol='o', symbolBrush='r', symbolSize=10
                    )

            # Plot 2: HR_GEN itself
            hr = signal
            hr_t = hr.time
            hr_y = hr.data
            mask = (hr_t >= start) & (hr_t <= end)
            self.curves[1] = self.plot_items[1].plot(hr_t[mask], hr_y[mask], pen="m")

        else:
            # Default: Plot single-channel
            self.curves[0] = self.plot_items[0].plot(t, y, pen="g")
