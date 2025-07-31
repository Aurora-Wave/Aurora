"""
channel_selection_dialog.py
---------------------------
Dialog window that allows the user to select which channels to visualize.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QCheckBox, QLabel, QScrollArea, QWidget
)

class ChannelSelectionDialog(QDialog):
    """
    Dialog to let the user select one or more signal channels from a given list.
    """

    def __init__(self, channel_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Channels")
        self.selected_channels = []

        self.checkboxes = []
        self.init_ui(channel_names)

    def init_ui(self, channel_names):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select the channels you want to visualize:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        for name in channel_names:
            checkbox = QCheckBox(name)
            self.checkboxes.append(checkbox)
            container_layout.addWidget(checkbox)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_channels(self):
        """Return a list of the names of the selected channels."""
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]
