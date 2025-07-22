import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QAbstractItemView, QPushButton,
    QSpinBox, QScrollBar, QMessageBox
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from data.data_manager import DataManager
from core.interval_extractor import extract_event_intervals
from core.comments import EMSComment
from processing.ecg_analyzer import ECGAnalyzer

class TiltTab(QWidget):
    """
    Tab to visualize tilt events and manage EMSComment annotations across all channels.
    Loads a full 10-minute context window but displays a user-defined chunk size.
    Enables panning across the full context, zoom disabled, synchronized across channels.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Data attributes
        self.data_manager: DataManager = None
        self.file_path: str = None
        self.channel_names: list[str] = []
        self.intervals: list[dict] = []
        self.comments: list[EMSComment] = []
        self._selected_idx: int | None = None
        # Visualization parameters
        self._chunk_size: float = 60.0  # seconds
        self._context_start: float = 0.0
        self._context_end: float = 0.0
        self._offset: float = 0.0
        # UI setup
        self._setup_ui()

    def _setup_ui(self):
        # Interval table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Event", "Start(s)", "Event(s)", "End(s)", "Duration(s)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellClicked.connect(self._on_row_selected)

        # Controls
        self.filter_box = QLineEdit(placeholderText="Filter events...")
        self.filter_box.textChanged.connect(self._apply_filter)
        self.add_btn = QPushButton("Add comment")
        self.add_btn.clicked.connect(self._add_comment)
        self.del_btn = QPushButton("Delete comment")
        self.del_btn.clicked.connect(self._delete_comment)
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setSuffix(" s")
        self.chunk_spin.setRange(1, 600)
        self.chunk_spin.setValue(int(self._chunk_size))
        self.chunk_spin.valueChanged.connect(self._on_chunk_changed)
        self.scrollbar = QScrollBar(Qt.Horizontal)
        self.scrollbar.valueChanged.connect(self._on_scroll_changed)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Search:"))
        ctrl.addWidget(self.filter_box)
        ctrl.addWidget(self.add_btn)
        ctrl.addWidget(self.del_btn)
        ctrl.addStretch()
        ctrl.addWidget(QLabel("Chunk:"))
        ctrl.addWidget(self.chunk_spin)
        ctrl.addWidget(self.scrollbar)

        # Plot area
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plots: dict[str, pg.PlotItem] = {}

        # Main layout
        layout = QVBoxLayout(self)
        layout.addLayout(ctrl)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.plot_widget, stretch=3)

    def update_tilt_tab(self, dm: DataManager, path: str):
        # Initialize data manager and path
        self.data_manager = dm
        self.file_path = path
        # Compute HR_gen
        ecg = dm.get_trace(path, "ECG")
        ecg.detect_r_peaks(wavelet="haar", swt_level=4, min_rr_sec=0.5)
        dm.get_trace(path, "HR_gen", wavelet="haar", swt_level=4, min_rr_sec=0.5)
        # Determine channels
        meta = set(dm.get_available_channels(path))
        cache = {k.split("|")[0] for k in dm._files[path]["signal_cache"]}
        available = meta.union(cache)
        order = ["ECG", "HR_gen", "FBP", "Valsalva"]
        self.channel_names = [ch for ch in order if ch in available]
        # Extract intervals
        signals = [dm.get_trace(path, ch) for ch in self.channel_names]
        self.intervals = extract_event_intervals(signals)
        # Load user comments
        self.comments = []
        for ch in self.channel_names:
            sig = dm.get_trace(path, ch)
            for c in getattr(sig, "MarkerData", []):
                if isinstance(c, EMSComment) and c.user_defined:
                    self.comments.append(c)
        self._selected_idx = None
        self._populate_table()
        # Set context window (10 minutes)
        self._context_start = 0.0
        self._context_end = min(
            max(dm.get_trace(path, ch).time),
            self._context_start + 600.0
        )
        # Configure scrollbar
        self._setup_scroll()
        # Render initial chunk
        self._render_chunk()

    def _populate_table(self):
        self.table.setRowCount(len(self.intervals))
        for i, iv in enumerate(self.intervals):
            t0 = iv.get("t_baseline", iv.get("t_evento", 0))
            te = iv.get("t_evento", 0)
            t1 = iv.get("t_recovery", iv.get("t_tilt_down", te))
            dur = t1 - t0
            items = [iv.get("evento", ""), t0, te, t1, dur]
            for j, val in enumerate(items):
                txt = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
                self.table.setItem(i, j, QTableWidgetItem(txt))
        self._apply_filter()

    def _apply_filter(self):
        term = self.filter_box.text().lower()
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            hide = term not in (it.text().lower() if it else "")
            self.table.setRowHidden(r, hide)

    def _setup_scroll(self):
        total = self._context_end - self._context_start
        max_scroll = int(max(total - self._chunk_size, 0))
        self.scrollbar.setRange(0, max_scroll)
        self.scrollbar.setPageStep(int(self._chunk_size))
        self.scrollbar.setValue(0)

    def _on_chunk_changed(self, val):
        self._chunk_size = float(val)
        self._setup_scroll()
        self._render_chunk()

    def _on_scroll_changed(self, val):
        self._offset = float(val)
        self._render_chunk()

    def _render_chunk(self):
        """
        Render data for [window_start, window_start+chunk_size],
        enable panning across full 10-min context, sync views.
        """
        self.plot_widget.clear()
        self.plots.clear()
        w_start = self._context_start + self._offset
        w_end = min(w_start + self._chunk_size, self._context_end)
        max_pts = 5000
        # Prepare each plot
        for idx, ch in enumerate(self.channel_names):
            sig = (self.data_manager.get_trace(
                self.file_path, ch,
                wavelet="haar", swt_level=4, min_rr_sec=0.5
            ) if ch == "HR_gen" else self.data_manager.get_trace(self.file_path, ch))
            # Get time/data
            if ch == "HR_gen":
                t = sig.time
                y = sig.data
            else:
                data = sig.get_full_signal(include_time=True)
                if isinstance(data, tuple):
                    y, t = data
                else:
                    y = data
                    t = np.arange(len(data)) / sig.fs
            # Mask for chunk
            mask = (t >= w_start) & (t < w_end)
            t_seg = t[mask]
            y_seg = y[mask]
            # Downsample
            if len(y_seg) > max_pts:
                step = int(np.ceil(len(y_seg) / max_pts))
                t_seg = t_seg[::step]
                y_seg = y_seg[::step]
            # Create plot
            p = self.plot_widget.addPlot(row=idx, col=0, title=ch)
            vb = p.getViewBox()
            vb.setMouseMode(pg.ViewBox.PanMode)
            vb.setMouseEnabled(x=True, y=False)
            vb.setLimits(xMin=self._context_start, xMax=self._context_end)
            vb.sigXRangeChanged.connect(self._sync_pan)
            p.plot(t_seg, y_seg, pen=pg.mkPen("y", width=1))
            p.setXRange(w_start, w_end, padding=0)
            if y_seg.size:
                fv = y_seg[np.isfinite(y_seg)]
                if fv.size:
                    p.setYRange(float(fv.min()), float(fv.max()))
            self.plots[ch] = p

    def _sync_pan(self, vb, x_range):
        left, right = x_range
        for p in self.plots.values():
            if p.getViewBox() is not vb:
                p.setXRange(left, right, padding=0)

    def _on_row_selected(self, row, col):
        self._selected_idx = row
        iv = self.intervals[row]
        evt = iv.get("t_evento", 0)
        self._context_start = max(evt - 300, 0)
        self._context_end = evt + 300
        self._setup_scroll()
        self._render_chunk()

    def _add_comment(self):
        if self._selected_idx is None:
            QMessageBox.warning(self, "Warning", "Select event first")
            return
        evt = self.intervals[self._selected_idx].get("t_evento", 0)
        cid = max((c.comment_id for c in self.comments), default=0) + 1
        cnt = 0
        for ch in self.channel_names:
            sig = self.data_manager.get_trace(self.file_path, ch)
            c = EMSComment(
                text="User annotation",
                tick_position=int(evt * sig.fs),
                channel=sig.name,
                comment_id=cid,
                tick_dt=1.0 / sig.fs,
                time_sec=evt,
                user_defined=True
            )
            sig.MarkerData.append(c)
            self.comments.append(c)
            cnt += 1
        QMessageBox.information(self, "Comment", f"Added to {cnt} channels")

    def _delete_comment(self):
        if self._selected_idx is None:
            QMessageBox.warning(self, "Warning", "Select event first")
            return
        evt = self.intervals[self._selected_idx].get("t_evento", 0)
        to_remove = [c for c in self.comments if c.time_sec == evt and c.user_defined]
        if not to_remove:
            QMessageBox.information(self, "Delete", "No user comments")
            return
        cnt = 0
        for c in to_remove:
            sig = self.data_manager.get_trace(self.file_path, c.channel)
            if c in sig.MarkerData:
                sig.MarkerData.remove(c)
                cnt += 1
        self.comments = [c for c in self.comments if c not in to_remove]
        QMessageBox.information(self, "Delete", f"Deleted {cnt} comments")
