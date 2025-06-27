import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QScrollBar,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QAbstractItemView,
    QSpinBox,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from core.comments import EMSComment
from core.interval_extractor import extract_event_intervals
from processing.chunk_loader import ChunkLoader


class TiltTab(QWidget):
    """
    Tab to visualize and manage comments (EMSComment) in a signal.
    Shows a table of comments and navigates to corresponding regions on selection.
    """

    def __init__(self):
        super().__init__()
        self.signal_group = None
        self.file_path = None
        self.channel_names = []
        self.comments = []
        self.intervals = []
        self._comment_lines = []
        self.target_channels = ["HR_GEN", "ECG", "FBP", "Valsalva"]
        self._selected_interval_idx = None  # Nuevo: índice de intervalo seleccionado
        self._scrollbar_value = 0  # Nuevo: valor actual de la barra

        # Table of comments
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Text", "Time (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_interval_selected)  # Cambiado

        # Controls
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter comments...")
        self.filter_box.textChanged.connect(self._filter_comments)

        self.delete_button = QPushButton("Delete Comment")
        self.delete_button.clicked.connect(self._delete_selected_comment)

        self.add_button = QPushButton("Add Comment")
        self.add_button.clicked.connect(self._add_comment)

        self.chunk_size = 120  # segundos por defecto
        self.scrollbar = QScrollBar()
        self.scrollbar.setOrientation(Qt.Horizontal)
        self.scrollbar.valueChanged.connect(self._on_scrollbar_changed)
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(10)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(self.chunk_size)
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.valueChanged.connect(self._on_chunk_size_changed)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.filter_box, stretch=1)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addWidget(self.add_button)
        controls_layout.addWidget(QLabel("Ventana:"))
        controls_layout.addWidget(self.chunk_size_spinbox)
        controls_layout.addWidget(self.scrollbar, stretch=3)

        # Plots for selected channels
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_items = {}  # {channel_name: (plot, curve)}

        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.plot_widget, 3)
        self.setLayout(layout)

        self._chunk_loader = None
        self._chunk_loader_connected = False  # Nuevo: para evitar múltiples conexiones

    def update_tilt_tab(self, signal_group, channel_names, file_path):
        self.signal_group = signal_group
        self.channel_names = channel_names
        self.file_path = file_path
        # Filtrar canales válidos y únicos para target_channels
        self.target_channels = []
        for name in ["HR_GEN", "ECG", "FBP", "Valsalva"]:
            sig = self.signal_group.get(name)
            if sig and name not in self.target_channels:
                self.target_channels.append(name)
        self._load_intervals()
        self._update_interval_table()
        self._setup_scrollbar()
        self._selected_interval_idx = None
        self._last_scrollbar_value = 0
        self._disconnect_chunk_loader()
        self._chunk_loader = ChunkLoader(
            file_path=self.file_path,
            channel_names=self.target_channels,
            chunk_size=self.chunk_size,
            signal_group=self.signal_group,
        )
        self._chunk_loader.chunk_loaded.connect(self._on_chunk_loaded)

    def _disconnect_chunk_loader(self):
        if self._chunk_loader is not None:
            try:
                self._chunk_loader.chunk_loaded.disconnect()
            except Exception:
                pass

    def _load_intervals(self):
        # Obtener todas las señales
        signals = [
            self.signal_group.get(name)
            for name in self.channel_names
            if self.signal_group.get(name)
        ]
        self.intervals = extract_event_intervals(signals)

    def _update_interval_table(self):
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Tipo", "Evento", "Inicio (s)", "Evento (s)", "Fin (s)"]
        )
        self.table.setRowCount(len(self.intervals))
        for row, interval in enumerate(self.intervals):
            tipo = interval.get("tipo", "")
            evento = interval.get("evento", "")
            t_ini = interval.get("t_baseline") or interval.get("t_evento")
            t_evt = interval.get("t_evento")
            t_fin = interval.get("t_recovery") or interval.get("t_tilt_down")
            self.table.setItem(row, 0, QTableWidgetItem(str(tipo)))
            self.table.setItem(row, 1, QTableWidgetItem(str(evento)))
            self.table.setItem(
                row, 2, QTableWidgetItem(f"{t_ini:.2f}" if t_ini is not None else "")
            )
            self.table.setItem(
                row, 3, QTableWidgetItem(f"{t_evt:.2f}" if t_evt is not None else "")
            )
            self.table.setItem(
                row, 4, QTableWidgetItem(f"{t_fin:.2f}" if t_fin is not None else "")
            )

    def _filter_comments(self):
        self._update_comment_table()

    def _apply_filter(self):
        query = self.filter_box.text().lower()
        return [c for c in self.comments if query in c.text.lower()]

    def _setup_scrollbar(self):
        # Determinar duración máxima entre todos los canales
        max_dur = 0
        for name in self.target_channels:
            sig = self.signal_group.get(name)
            if sig:
                dur = len(sig.get_full_signal()) / sig.fs
                if dur > max_dur:
                    max_dur = dur
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(
            int(max_dur) - self.chunk_size if max_dur > self.chunk_size else 0
        )
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)

    def _on_chunk_size_changed(self, value):
        self.chunk_size = value
        self._setup_scrollbar()
        self._last_scrollbar_value = self.scrollbar.value()
        self._update_plot()

    def _on_scrollbar_changed(self, value):
        self._last_scrollbar_value = value
        self._update_plot()

    def _on_interval_selected(self, row, col):
        self._selected_interval_idx = row
        self.scrollbar.setValue(0)
        self._last_scrollbar_value = 0
        self._update_plot()

    def _update_plot(self):
        row = self._selected_interval_idx
        if row is None or row >= len(self.intervals):
            return
        interval = self.intervals[row]
        t_ini = interval.get("t_baseline") or interval.get("t_evento")
        t_evt = interval.get("t_evento")
        t_fin = interval.get("t_recovery") or interval.get("t_tilt_down")
        evento = interval.get("evento", "")
        start = self._last_scrollbar_value
        end = start + self.chunk_size
        if t_ini is not None and t_fin is not None and t_fin - t_ini < self.chunk_size:
            start = max(0, t_ini - (self.chunk_size - (t_fin - t_ini)) / 2)
            end = start + self.chunk_size
        self.plot_widget.clear()
        self._comment_lines.clear()
        self.plot_items.clear()
        # Solicitar chunk
        if self._chunk_loader is not None:
            self._chunk_loader.request_chunk(start, end)

    def _on_chunk_loaded(self, start_sec, end_sec, data_dict):
        row = self._selected_interval_idx
        if row is None or row >= len(self.intervals):
            return
        interval = self.intervals[row]
        t_evt = interval.get("t_evento")
        evento = interval.get("evento", "")
        for idx, channel in enumerate(self.target_channels):
            signal = self.signal_group.get(channel)
            if signal is None:
                continue
            fs = signal.fs
            t = np.arange(int((end_sec - start_sec) * fs)) / fs + start_sec
            y = data_dict.get(channel, np.full_like(t, np.nan))
            p = self.plot_widget.addPlot(row=idx, col=0, title=channel)
            p.setLabel("bottom", "Time (s)")
            p.setLabel("left", channel)
            p.showGrid(x=True, y=True)
            curve = p.plot(t, y, pen="y")
            p.setXRange(start_sec, end_sec, padding=0)
            # Línea vertical en el evento con etiqueta
            if t_evt is not None and start_sec <= t_evt <= end_sec:
                vline = pg.InfiniteLine(
                    pos=t_evt, angle=90, pen=pg.mkPen("r", width=2)
                )
                p.addItem(vline)
                label = pg.TextItem(evento, color="r", anchor=(0, 1))
                label.setPos(t_evt, p.viewRange()[1][1])
                p.addItem(label)
                self._comment_lines.append(vline)
                self._comment_lines.append(label)
            self.plot_items[channel] = (p, curve)

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
