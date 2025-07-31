import numpy as np
import pywt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
)
import pyqtgraph as pg
from processing.chunk_loader import ChunkLoader
from PySide6.QtCore import Qt


class AnalysisTab(QWidget):
    """
    AnalysisTab: chunk-based ECG/HR visualization and interactive R-peak editing.
    Allows adding, deleting, and moving R-peaks with local HR update.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = None
        self.file_path = None
        self.fs = 1.0
        self.duration = 0.0
        self._max_lvl = 5

        # Defaults
        self.wavelet = "haar"
        self.level = 4
        self.min_dist = 0.5
        self.chunk_size = 60
        self.start_time = 0

        # Dragging state
        self._dragged_peak_idx = None
        self._is_dragging = False

        # Layout
        main = QVBoxLayout(self)
        ctrl = QHBoxLayout()

        # Wavelet selector
        ctrl.addWidget(QLabel("Wavelet:"))
        self.wavelet_cb = QComboBox()
        self.wavelet_cb.addItems(["haar", "db4", "db5", "sym4"])
        self.wavelet_cb.setCurrentText(self.wavelet)
        self.wavelet_cb.currentTextChanged.connect(self._update)
        ctrl.addWidget(self.wavelet_cb)

        # SWT level
        ctrl.addWidget(QLabel("Level:"))
        self.level_sb = QSpinBox()
        self.level_sb.setRange(1, 6)
        self.level_sb.setValue(self.level)
        self.level_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.level_sb)

        # MinDist
        ctrl.addWidget(QLabel("MinDist (s):"))
        self.dist_sb = QDoubleSpinBox()
        self.dist_sb.setRange(0.1, 2.0)
        self.dist_sb.setSingleStep(0.1)
        self.dist_sb.setValue(self.min_dist)
        self.dist_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.dist_sb)

        # Chunk
        ctrl.addWidget(QLabel("Chunk (s):"))
        self.chunk_sb = QSpinBox()
        self.chunk_sb.setRange(1, 600)
        self.chunk_sb.setValue(self.chunk_size)
        self.chunk_sb.valueChanged.connect(self._on_chunk_changed)
        ctrl.addWidget(self.chunk_sb)

        # Start
        ctrl.addWidget(QLabel("Start (s):"))
        self.start_sb = QSpinBox()
        self.start_sb.setRange(0, 0)
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
        self.hr_plot = self.plots.addPlot(row=1, col=0, title="HR_gen Chunk")
        self.wave_plot = self.plots.addPlot(row=2, col=0, title="Mother Wavelet")

        for p in (self.ecg_plot, self.hr_plot, self.wave_plot):
            p.showGrid(x=True, y=True)
            p.getViewBox().setMouseEnabled(x=False, y=False)

        # Disable context menu on ECG plot
        self.ecg_plot.getViewBox().setMenuEnabled(False)

        self.ecg_plot.setLabel("bottom", "Time (s)")
        self.ecg_plot.setLabel("left", "Amplitude")
        self.hr_plot.setLabel("bottom", "Time (s)")
        self.hr_plot.setLabel("left", "BPM")
        self.hr_plot.setXLink(self.ecg_plot)
        self.wave_plot.setLabel("bottom", "Units")
        self.wave_plot.setLabel("left", "Amplitude")

        main.addWidget(self.plots)

        # Connect mouse events
        self.ecg_plot.scene().sigMouseClicked.connect(self._on_ecg_click)

        # Track last chunk for index conversion
        self._last_chunk_start = 0
        self._last_chunk_len = 0
        self._last_peaks = None
        self._last_ecg_chunk = None

    def update_analysis_tab(self, data_manager, file_path):
        self.data_manager = data_manager
        self.file_path = file_path
        ecg = self.data_manager.get_trace(file_path, "ECG")
        self.fs = ecg.fs
        length = len(ecg.data)
        self.duration = length / self.fs

        # max_lvl = pywt.swt_max_level(length)
        # self._max_lvl = max(1, max_lvl)
        if self.level > self._max_lvl:
            self.level = self._max_lvl
        self.level_sb.setRange(1, self._max_lvl)
        self.level_sb.setValue(self.level)

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
        md = self.dist_sb.value()
        chunk = self.chunk_sb.value()
        start = self.start_sb.value()

        # ECG chunk
        ecg_chunk = ChunkLoader.get_chunk(
            self.data_manager, self.file_path, ["ECG"], start, chunk
        )
        t_ecg = np.arange(len(ecg_chunk)) / self.fs + start

        # HR_gen global (full signal)
        hr_sig = self.data_manager.get_trace(
            self.file_path, "HR_GEN", wavelet=wav, swt_level=lvl, min_rr_sec=md
        )
        hr_t = hr_sig.time
        hr_v = hr_sig.data

        # HR_gen chunk
        mask = (hr_t >= start) & (hr_t < start + chunk)
        hr_t_chunk = hr_t[mask]
        hr_v_chunk = hr_v[mask]

        # Detected R-peaks (global indices)
        r_peaks = hr_sig.r_peaks
        peaks_in_chunk = r_peaks[
            (r_peaks >= int(start * self.fs))
            & (r_peaks < int((start + chunk) * self.fs))
        ]
        t_peaks = peaks_in_chunk / self.fs
        y_peaks = ecg_chunk[(peaks_in_chunk - int(start * self.fs)).astype(int)]

        # Plot ECG with peaks
        self.ecg_plot.clear()
        self.ecg_plot.plot(t_ecg, ecg_chunk, pen="b")
        self.ecg_plot.plot(
            t_peaks, y_peaks, pen=None, symbol="o", symbolBrush="r", symbolSize=10
        )

        # Store for mouse interaction
        self._last_chunk_start = start
        self._last_chunk_len = chunk
        self._last_peaks = peaks_in_chunk
        self._last_ecg_chunk = ecg_chunk

        # Plot HR_gen
        self.hr_plot.clear()
        if hr_v_chunk.size:
            hr_min = hr_v_chunk.min() - 10
            hr_max = hr_v_chunk.max() + 10
            self.hr_plot.plot(hr_t_chunk, hr_v_chunk, pen="g")
            self.hr_plot.setYRange(hr_min, hr_max)

        # Wavelet
        try:
            _, psi, x = pywt.Wavelet(wav).wavefun(level=lvl)
        except:
            psi, x = pywt.Wavelet(wav).wavefun()[:2]
        self.wave_plot.clear()
        self.wave_plot.plot(x, psi, pen="m")

    # Mouse interaction: click-inicio y click-destino
    def _on_ecg_click(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)
        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        tolerance = int(0.05 * fs)
        idx_near = np.where(np.abs(hr_sig.r_peaks - global_idx) <= tolerance)[0]

        if event.button() == Qt.LeftButton:
            if self._is_dragging and self._dragged_peak_idx is not None:
                # Click-destino: mueve el peak seleccionado
                window = int(0.1 * fs)
                raw_ecg = self.data_manager.get_trace(self.file_path, "ECG").data
                search_start = max(global_idx - window, 0)
                search_end = min(global_idx + window, len(raw_ecg))
                local_max_idx = (
                    np.argmax(np.abs(raw_ecg[search_start:search_end])) + search_start
                )
                hr_sig.update_peak(self._dragged_peak_idx, local_max_idx)
                hr_sig._data = hr_sig._data.copy()
                self._dragged_peak_idx = None
                self._is_dragging = False
                self._update()
            elif idx_near.size:
                # Click-inicio: seleccionar peak para mover
                self._dragged_peak_idx = idx_near[0]
                self._is_dragging = True
            else:
                # Agregar peak
                self._handle_add_peak(event)
        elif event.button() == Qt.RightButton:
            self._handle_delete_peak(event)

    def _handle_add_peak(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)
        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        # Only add if not too close to another peak
        tolerance = int(0.05 * fs)
        if np.all(np.abs(hr_sig.r_peaks - global_idx) > tolerance):
            window = int(0.1 * fs)
            raw_ecg = self.data_manager.get_trace(self.file_path, "ECG").data
            search_start = max(global_idx - window, 0)
            search_end = min(global_idx + window, len(raw_ecg))
            local_max_idx = (
                np.argmax(np.abs(raw_ecg[search_start:search_end])) + search_start
            )
            hr_sig.r_peaks = np.sort(np.append(hr_sig.r_peaks, local_max_idx))
            # Update only the segments around the new peak
            i = np.searchsorted(hr_sig.r_peaks, local_max_idx)
            if i > 0:
                hr_sig._update_hr_segment(i - 1)
            if i < len(hr_sig.r_peaks) - 1:
                hr_sig._update_hr_segment(i)
            hr_sig._data = hr_sig._data.copy()
            self._update()

    def _handle_delete_peak(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)
        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        tolerance = int(0.05 * fs)
        idx_near = np.where(np.abs(hr_sig.r_peaks - global_idx) <= tolerance)[0]
        if idx_near.size:
            peak_idx = idx_near[0]
            hr_sig.r_peaks = np.delete(hr_sig.r_peaks, peak_idx)
            # Update HR around removed peak
            if peak_idx > 0:
                hr_sig._update_hr_segment(peak_idx - 1)
            if peak_idx < len(hr_sig.r_peaks) - 1:
                hr_sig._update_hr_segment(peak_idx)
            hr_sig._data = hr_sig._data.copy()
            self._update()
