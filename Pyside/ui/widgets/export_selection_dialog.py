"""
ExportSelectionDialog
Diálogo para seleccionar señales y tests a exportar.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QAbstractItemView
from PySide6.QtCore import Qt

class ExportSelectionDialog(QDialog):
    def __init__(self, signals, tests, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Signals and Tests to Export")
        self.selected_signals = []
        self.selected_tests = []
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Select signals to export:"))
        self.signal_list = QListWidget()
        self.signal_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for sig in signals:
            item = QListWidgetItem(sig)
            self.signal_list.addItem(item)
        layout.addWidget(self.signal_list)

        layout.addWidget(QLabel("Select tests to export:"))
        self.test_list = QListWidget()
        self.test_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for test in tests:
            item = QListWidgetItem(test)
            self.test_list.addItem(item)
        layout.addWidget(self.test_list)

        button_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        self.setLayout(layout)

    def get_selections(self):
        signals = [item.text() for item in self.signal_list.selectedItems()]
        tests = [item.text() for item in self.test_list.selectedItems()]
        return signals, tests
