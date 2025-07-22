import numpy as np
import pywt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QMessageBox
)
import pyqtgraph as pg
from processing.ecg_analyzer import ECGAnalyzer

class AnalysisTab(QWidget):
    """
    AnalysisTab: per-chunk visualization of ECG, HR_gen, and detected peaks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = None
        self.file_path = None
        self.fs = 1.0
        self.duration = 0.0
        self._max_lvl = 1

        # Defaults
        self.wavelet    = 'haar'
        self.level      = 4
        self.min_dist   = 0.5  # seconds for RR refractory
        self.chunk_size = 60
        self.start_time = 0

        # Track last HR parameters to avoid unnecessary recompute
        self._last_hr_params = (None, None, None)

        # Layout setup
        main = QVBoxLayout(self)
        ctrl = QHBoxLayout()

        # Wavelet selector
        ctrl.addWidget(QLabel("Wavelet:"))
        self.wavelet_cb = QComboBox()
        self.wavelet_cb.addItems(['haar','db4','db5','sym4'])
        self.wavelet_cb.setCurrentText(self.wavelet)
        self.wavelet_cb.currentTextChanged.connect(self._update)
        ctrl.addWidget(self.wavelet_cb)

        # SWT level
        ctrl.addWidget(QLabel("Level:"))
        self.level_sb = QSpinBox()
        self.level_sb.setRange(1,6)
        self.level_sb.setValue(self.level)
        self.level_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.level_sb)

        # MinDist
        ctrl.addWidget(QLabel("MinDist (s):"))
        self.dist_sb = QDoubleSpinBox()
        self.dist_sb.setRange(0.1,2.0)
        self.dist_sb.setSingleStep(0.1)
        self.dist_sb.setValue(self.min_dist)
        self.dist_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.dist_sb)

        # Chunk
        ctrl.addWidget(QLabel("Chunk (s):"))
        self.chunk_sb = QSpinBox()
        self.chunk_sb.setRange(1,600)
        self.chunk_sb.setValue(self.chunk_size)
        self.chunk_sb.valueChanged.connect(self._on_chunk_changed)
        ctrl.addWidget(self.chunk_sb)

        # Start
        ctrl.addWidget(QLabel("Start (s):"))
        self.start_sb = QSpinBox()
        self.start_sb.setRange(0,0)
        self.start_sb.setValue(self.start_time)
        self.start_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.start_sb)

        # Navigation buttons
        self.prev_btn = QPushButton("←")
        self.prev_btn.clicked.connect(self._go_previous_chunk)
        ctrl.addWidget(self.prev_btn)
        self.next_btn = QPushButton("→")
        self.next_btn.clicked.connect(self._go_next_chunk)
        ctrl.addWidget(self.next_btn)

        main.addLayout(ctrl)

        # Plot area
        self.plots = pg.GraphicsLayoutWidget()
        self.ecg_plot = self.plots.addPlot(row=0, col=0, title="ECG Chunk")
        self.hr_plot  = self.plots.addPlot(row=1, col=0, title="HR_gen Chunk")
        self.wave_plot= self.plots.addPlot(row=2, col=0, title="Mother Wavelet")

        for p in (self.ecg_plot, self.hr_plot, self.wave_plot):
            p.showGrid(x=True,y=True)
            p.getViewBox().setMouseEnabled(x=False, y=False)

        self.ecg_plot.setLabel('bottom','Time (s)')
        self.ecg_plot.setLabel('left','Amplitude')
        self.hr_plot.setLabel('bottom','Time (s)')
        self.hr_plot.setLabel('left','BPM')
        self.hr_plot.setXLink(self.ecg_plot)
        self.wave_plot.setLabel('bottom','Units')
        self.wave_plot.setLabel('left','Amplitude')

        main.addWidget(self.plots)

    def update_analysis_tab(self, data_manager, file_path):
        # init on file load
        self.data_manager = data_manager
        self.file_path = file_path
        ecg = self.data_manager.get_trace(file_path, "ECG")
        self.fs = ecg.fs
        length = len(ecg.data)
        self.duration = length / self.fs

        # adjust SWT level range
        max_lvl = pywt.swt_max_level(length)
        self._max_lvl = max(1, max_lvl)
        if self.level > self._max_lvl:
            self.level = self._max_lvl
        self.level_sb.setRange(1, self._max_lvl)
        self.level_sb.setValue(self.level)

        # adjust chunk and start ranges
        self.chunk_sb.setRange(1, int(self.duration))
        self.chunk_sb.setValue(min(self.chunk_size, int(self.duration)))
        self.start_sb.setRange(0, int(self.duration - self.chunk_sb.value()))

        self._update()

    def _on_chunk_changed(self, val):
        self.chunk_size = val
        self.start_sb.setRange(0, int(self.duration - self.chunk_size))
        self._update()

    def _go_previous_chunk(self):
        self.start_sb.setValue(max(0, self.start_sb.value() - self.chunk_size))

    def _go_next_chunk(self):
        max_start = int(self.duration - self.chunk_size)
        self.start_sb.setValue(min(max_start, self.start_sb.value() + self.chunk_size))

    def _update(self):
        wav = self.wavelet_cb.currentText()
        lvl = self.level_sb.value()
        md  = self.dist_sb.value()
        chunk = self.chunk_sb.value()
        start = self.start_sb.value()

        if lvl > self._max_lvl:
            QMessageBox.warning(self, "Level Too High", f"Max level is {self._max_lvl}")
            lvl = self._max_lvl
            self.level_sb.setValue(lvl)

        # ECG chunk retrieval
        ecg_chunk = self.data_manager.get_chunk(self.file_path, "ECG", start, chunk)
        t_ecg = np.arange(len(ecg_chunk)) / self.fs + start

        # HR_gen chunk retrieval: recompute only on param change
        curr_params = (wav, lvl, md)
        if curr_params != self._last_hr_params:
            self.data_manager._files[self.file_path]['signal_cache'].pop('HR_gen', None)
            self._last_hr_params = curr_params

        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_gen",
            wavelet=wav,
            swt_level=lvl,
            min_rr_sec=md
        )
        mask = (hr_sig.time >= start) & (hr_sig.time < start + chunk)
        hr_t = hr_sig.time[mask]
        hr_v = hr_sig.data[mask]

        # compute global min/max of HR for consistent y-limits with 10-unit padding
        if hr_v.size:
            hr_min = hr_v.min() - 10
            hr_max = hr_v.max() + 10
        else:
            hr_min, hr_max = 0, 100  # defaults if empty

        # compute wavelet shape for display
        try:
            _, psi, x = pywt.Wavelet(wav).wavefun(level=lvl)
        except:
            psi, x = pywt.Wavelet(wav).wavefun()[:2]

        # draw ECG and overlay detected R-peaks
        self._draw_ecg(t_ecg, ecg_chunk)
        try:
            peak_indices = ECGAnalyzer.detect_rr_peaks(
                ecg_chunk,
                self.fs,
                wav,
                lvl,
                md
            )
            peak_times = peak_indices / self.fs + start
            peak_amps = ecg_chunk[peak_indices]
            self.ecg_plot.plot(peak_times, peak_amps, pen=None, symbol='o')
        except Exception:
            pass

        # draw HR with new y-limits
        self.hr_plot.clear()
        if hr_v.size:
            self.hr_plot.plot(hr_t, hr_v, pen='g')
            self.hr_plot.setYRange(hr_min, hr_max)

        # draw wavelet plot
        self._draw_wavelet(x, psi)

    def _draw_ecg(self, t, data):
        self.ecg_plot.clear()
        self.ecg_plot.plot(t, data, pen='b')

    def _draw_wavelet(self, x, psi):
        self.wave_plot.clear()
        self.wave_plot.plot(x, psi, pen='m')
