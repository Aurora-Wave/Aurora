"""
ExportSelectionDialog
Diálogo para seleccionar señales y tests a exportar.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QAbstractItemView,
    QGroupBox,
    QSpinBox,
    QFormLayout,
)
from PySide6.QtCore import Qt


class ExportSelectionDialog(QDialog):
    def __init__(self, signals, tests, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Signals and Tests to Export")
        self.setMinimumSize(400, 500)
        self.selected_signals = []
        self.selected_tests = []

        layout = QVBoxLayout()

        # Grupo de señales
        sig_group = QGroupBox("Signals to Export")
        sig_layout = QVBoxLayout()
        sig_layout.addWidget(QLabel("Select physiological signals:"))

        self.signal_list = QListWidget()
        self.signal_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for sig in signals:
            item = QListWidgetItem(sig)
            self.signal_list.addItem(item)
        sig_layout.addWidget(self.signal_list)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)

        # Grupo de tests
        test_group = QGroupBox("Test Instances to Export")
        test_layout = QVBoxLayout()
        test_layout.addWidget(
            QLabel("Select test instances (with timestamp for identification):")
        )

        self.test_list = QListWidget()
        self.test_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for test in tests:
            item = QListWidgetItem(test)
            # Agregar tooltip con información adicional si es necesario
            if " (at " in test:
                base_name = test.split(" (at ")[0]
                time_info = test.split(" (at ")[1].rstrip(")")
                item.setToolTip(f"Test: {base_name}\nStart time: {time_info}")
            self.test_list.addItem(item)
        test_layout.addWidget(self.test_list)
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)

        # Configuración de segmentación temporal
        config_group = QGroupBox("Time Segmentation Configuration")
        config_layout = QFormLayout()

        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(10, 300)  # Entre 10 segundos y 5 minutos
        self.segment_spin.setValue(60)  # Default: 60 segundos (1 minuto)
        self.segment_spin.setSuffix(" seconds")
        self.segment_spin.setToolTip(
            "Duration of each time segment for statistics calculation"
        )

        config_layout.addRow("Segment duration:", self.segment_spin)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Info adicional
        info_label = QLabel(
            "📊 Export format: Statistics per time segment (mean & max values)\n"
            "📁 Output: CSV file with semicolon separator\n"
            "💡 HR_gen: Computed heart rate signal available\n"
            "⏱️ Multiple tests: Distinguished by start time"
        )
        info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        layout.addWidget(info_label)

        # Botones
        button_row = QHBoxLayout()
        ok_btn = QPushButton("Export")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(ok_btn)
        layout.addLayout(button_row)

        self.setLayout(layout)

    def get_selections(self):
        signals = [item.text() for item in self.signal_list.selectedItems()]
        tests = [item.text() for item in self.test_list.selectedItems()]
        segment_duration = float(self.segment_spin.value())
        return signals, tests, segment_duration
