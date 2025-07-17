import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QAbstractItemView,
    QSpinBox,
    QScrollBar,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from core.comments import EMSComment
from core.interval_extractor import extract_event_intervals


class TiltTab(QWidget):
    """
    Tab to visualize and manage comments (EMSComment) in a signal.
    Shows a table of intervals and plots the full signals for selected channels.
    """

    def __init__(self):
        super().__init__()
        self.signal_group = None
        self.file_path = None
        self.channel_names = []
        self.comments = []
        self.intervals = []
        self.target_channels = ["HR", "ECG", "FBP", "Valsalva"]
        self._selected_interval_idx = None

        # Table of intervals
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Evento", "Inicio (s)", "Evento (s)", "Fin (s)", "Duración (s)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_interval_selected)

        # Controls
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter comments...")
        self.filter_box.textChanged.connect(self._filter_comments)

        self.delete_button = QPushButton("Delete Comment")
        self.delete_button.clicked.connect(self._delete_selected_comment)

        self.add_button = QPushButton("Add Comment")
        self.add_button.clicked.connect(self._add_comment)


        # --- NEW: Chunk controls ---
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(1)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(60)
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.setToolTip("Chunk size (seconds)")
        self.chunk_size_spinbox.valueChanged.connect(self._on_chunk_size_changed)

        self.scrollbar = QScrollBar()
        self.scrollbar.setOrientation(Qt.Horizontal)
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(0)
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self._on_scrollbar_changed)

        controls_layout = QHBoxLayout()
        self.filter_box.setMaximumWidth(180)
        controls_layout.addWidget(self.filter_box)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addWidget(self.add_button)
        controls_layout.addWidget(QLabel("Window:"))
        controls_layout.addWidget(self.chunk_size_spinbox)
        controls_layout.addWidget(self.scrollbar, stretch=2)

        # Plots for selected channels
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_items = {}  # {channel_name: (plot, curve)}

        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.plot_widget, 3)
        self.setLayout(layout)

        # Estado del gráfico
        self._current_chunk_start = 0
        self._chunk_size = 60

    def update_tilt_tab(self, signal_group, channel_names, file_path):
        self.signal_group = signal_group
        self.channel_names = channel_names
        self.file_path = file_path
        # Filtrar canales válidos y únicos para target_channels
        self.target_channels = []
        for name in ["HR", "ECG", "FBP", "Valsalva"]:
            sig = self.signal_group.get(name)
            if sig and name not in self.target_channels:
                self.target_channels.append(name)
        self._load_intervals()
        self._update_interval_table()
        self._selected_interval_idx = None
        # --- Sincronización de gráficos con scrollbar ---
        self._setup_scrollbar_and_chunk()
        self._update_plot_chunk()

    def _setup_scrollbar_and_chunk(self):
        # Determinar el rango del evento seleccionado
        t_evt, t_fin = None, None
        if (
            self._selected_interval_idx is not None
            and 0 <= self._selected_interval_idx < len(self.intervals)
        ):
            interval = self.intervals[self._selected_interval_idx]
            t_evt = interval.get("t_evento")
            t_fin = interval.get("t_recovery") or interval.get("t_tilt_down")
        if t_evt is None or t_fin is None or t_fin <= t_evt:
            t_evt, t_fin = 0, 1
        self._event_start = t_evt
        self._event_end = t_fin
        self._chunk_size = self.chunk_size_spinbox.value()
        max_scroll = max(0, int((t_fin - t_evt) - self._chunk_size))
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(max_scroll)
        self.scrollbar.setValue(0)
        self._current_chunk_start = 0

    def _on_chunk_size_changed(self, value):
        self._chunk_size = value
        self._setup_scrollbar_and_chunk()
        self._update_plot_chunk()

    def _on_scrollbar_changed(self, value):
        self._current_chunk_start = value
        self._update_plot_chunk()

    def _update_plot_chunk(self):
        self.plot_widget.clear()
        self.plot_items.clear()
        # Usar el rango del evento seleccionado
        t_evt = getattr(self, '_event_start', 0)
        t_fin = getattr(self, '_event_end', 1)
        chunk_size = self._chunk_size
        start = t_evt + self._current_chunk_start
        end = min(start + chunk_size, t_fin)
        max_points = 5000  # Igual que viewer_tab
        for idx, channel in enumerate(self.target_channels):
            signal = self.signal_group.get(channel)
            if signal is None:
                continue
            y_full = signal.get_full_signal()
            fs = signal.fs
            t_full = np.arange(len(y_full)) / fs
            idx_ini = int(np.round(start * fs))
            idx_fin = int(np.round(end * fs))
            idx_ini = max(0, min(idx_ini, len(y_full) - 1))
            idx_fin = max(idx_ini + 1, min(idx_fin, len(y_full)))
            t = t_full[idx_ini:idx_fin]
            y = y_full[idx_ini:idx_fin]
            # Downsampling manual
            if len(y) > max_points:
                step = int(np.ceil(len(y) / max_points))
                y = y[::step]
                t = t[::step]
            else:
                step = 1
            p = self.plot_widget.addPlot(row=idx, col=0, title=channel)
            p.setLabel("bottom", "Time (s)")
            p.setLabel("left", channel)
            p.showGrid(x=True, y=True)
            curve = p.plot(t, y, pen="y")
            p.setXRange(t[0], t[-1], padding=0)
            if np.any(~np.isnan(y)):
                y_valid = y[~np.isnan(y)]
                y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                p.setYRange(y_min, y_max)
            else:
                p.setYRange(0, 1)
            self.plot_items[channel] = (p, curve)
        self._mark_event_in_chunk()

    def _mark_event_in_chunk(self):
        if (
            self._selected_interval_idx is not None
            and 0 <= self._selected_interval_idx < len(self.intervals)
        ):
            interval = self.intervals[self._selected_interval_idx]
            t_evt = interval.get("t_evento")
            evento = interval.get("evento", "")
            if t_evt is not None:
                for channel, (p, _) in self.plot_items.items():
                    if p is not None:
                        x_range = p.viewRange()[0]
                        if x_range[0] <= t_evt <= x_range[1]:
                            vline = pg.InfiniteLine(
                                pos=t_evt, angle=90, pen=pg.mkPen("r", width=2)
                            )
                            p.addItem(vline)
                            label = pg.TextItem(evento, color="r", anchor=(0, 1))
                            label.setPos(t_evt, p.viewRange()[1][1])
                            p.addItem(label)

    def _load_intervals(self):
        signals = [
            self.signal_group.get(name)
            for name in self.channel_names
            if self.signal_group.get(name)
        ]
        self.intervals = extract_event_intervals(signals)

    def _update_interval_table(self):
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Evento", "Inicio (s)", "Evento (s)", "Fin (s)", "Duración (s)"]
        )
        self.table.setRowCount(len(self.intervals))
        for row, interval in enumerate(self.intervals):
            evento = interval.get("evento", "")
            t_ini = interval.get("t_baseline") or interval.get("t_evento")
            t_evt = interval.get("t_evento")
            t_fin = interval.get("t_recovery") or interval.get("t_tilt_down")
            duracion = (
                (t_fin - t_ini) if (t_ini is not None and t_fin is not None) else None
            )
            self.table.setItem(row, 0, QTableWidgetItem(str(evento)))
            self.table.setItem(
                row, 1, QTableWidgetItem(f"{t_ini:.2f}" if t_ini is not None else "")
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(f"{t_evt:.2f}" if t_evt is not None else "")
            )
            self.table.setItem(
                row, 3, QTableWidgetItem(f"{t_fin:.2f}" if t_fin is not None else "")
            )
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(f"{duracion:.2f}" if duracion is not None else ""),
            )

    def _filter_comments(self):
        self._update_comment_table()

    def _on_interval_selected(self, row, col):
        self._selected_interval_idx = row
        self._setup_scrollbar_and_chunk()
        self._update_plot_chunk()


    def _delete_selected_comment(self):
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        if not selected_rows:
            return
        for row in sorted(selected_rows, reverse=True):
            comment = self._apply_filter()[row]
            signal = self.signal_group.get(comment.channel)
            if signal:
                signal.MarkerData.remove(comment)
            self.comments.remove(comment)
        self._update_comment_table()

    def _add_comment(self):
        if not self.channel_names:
            return
        signal = self.signal_group.get(self.channel_names[0])
        if not signal:
            return

        new_time = 5.0
        new_id = max([c.comment_id for c in self.comments], default=0) + 1
        new_comment = EMSComment(
            text="User comment",
            tick_position=int(new_time * signal.fs),
            channel=signal.name,
            comment_id=new_id,
            tick_dt=1.0 / signal.fs,
            time_sec=new_time,
            user_defined=True,
        )
        signal.MarkerData.append(new_comment)
        self.comments.append(new_comment)
        self._update_comment_table()
