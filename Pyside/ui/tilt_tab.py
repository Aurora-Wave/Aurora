import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QScrollBar, QHeaderView, QLineEdit, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from core.comments import EMSComment


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
        self._comment_lines = []
        self.target_channels = ["HR_GEN", "ECG", "FBP", "Valsalva"]

        # Table of comments
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Text", "Time (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_comment_selected)

        # Controls
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter comments...")
        self.filter_box.textChanged.connect(self._filter_comments)

        self.delete_button = QPushButton("Delete Comment")
        self.delete_button.clicked.connect(self._delete_selected_comment)

        self.add_button = QPushButton("Add Comment")
        self.add_button.clicked.connect(self._add_comment)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.filter_box)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addWidget(self.add_button)

        # Plots for selected channels
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_items = {}  # {channel_name: (plot, curve)}

        layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.plot_widget, 3)
        self.setLayout(layout)

    def update_tilt_tab(self, signal_group, channel_names, file_path):
        self.signal_group = signal_group
        self.channel_names = channel_names
        self.file_path = file_path
        self._load_comments()
        self._update_comment_table()

    def _load_comments(self):
        self.comments = []
        for name in self.channel_names:
            signal = self.signal_group.get(name)
            if signal and signal.MarkerData:
                self.comments.extend(signal.MarkerData)

    def _update_comment_table(self):
        filtered = self._apply_filter()
        self.table.setRowCount(len(filtered))
        for row, comment in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(str(comment.comment_id)))
            self.table.setItem(row, 1, QTableWidgetItem(comment.text))
            self.table.setItem(row, 2, QTableWidgetItem(f"{comment.time:.2f}"))

    def _filter_comments(self):
        self._update_comment_table()

    def _apply_filter(self):
        query = self.filter_box.text().lower()
        return [c for c in self.comments if query in c.text.lower()]

    def _on_comment_selected(self, row, col):
        filtered = self._apply_filter()
        if row >= len(filtered):
            return
        comment = filtered[row]

        # Clear plots and lines
        self.plot_widget.clear()
        self._comment_lines.clear()
        self.plot_items.clear()

        # Window of 10 seconds around comment
        window = 10
        start = max(0, comment.time - window / 2)
        end = start + window

        # Create plots for selected channels
        for idx, channel in enumerate(self.target_channels):
            signal = self.signal_group.get(channel)
            if signal is None:
                continue

            fs = signal.fs
            full = signal.get_full_signal()
            t = np.linspace(0, len(full) / fs, len(full))
            mask = (t >= start) & (t <= end)

            p = self.plot_widget.addPlot(row=idx, col=0, title=channel)
            p.setLabel("bottom", "Time (s)")
            p.setLabel("left", channel)
            p.showGrid(x=True, y=True)
            curve = p.plot(t[mask], full[mask], pen="y")
            p.setXRange(start, end, padding=0)

            vline = pg.InfiniteLine(pos=comment.time, angle=90, pen=pg.mkPen("r", width=2))
            p.addItem(vline)
            self._comment_lines.append(vline)
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
