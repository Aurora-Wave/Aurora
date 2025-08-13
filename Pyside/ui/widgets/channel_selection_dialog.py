"""
channel_selection_dialog.py
---------------------------
Dialog window that allows the user to select which channels to visualize.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QCheckBox, QLabel, QScrollArea, QWidget, QPushButton, QHBoxLayout
)

class ChannelSelectionDialog(QDialog):
    """
    Dialog to let the user select one or more signal channels from a given list.
    """

    def __init__(self, channel_names, parent=None, existing_channels=None):
        super().__init__(parent)
        self.setWindowTitle("Select Channels")
        self.selected_channels = []
        self.existing_channels = existing_channels or channel_names

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
            # Add visual indication for channels that need to be generated
            if name == "HR_GEN" and name not in self.existing_channels:
                display_name = f"{name} (will be generated)"
                checkbox = QCheckBox(display_name)
                checkbox.setToolTip("This channel will be generated using default parameters when selected")
            else:
                checkbox = QCheckBox(name)
            
            self.checkboxes.append(checkbox)
            container_layout.addWidget(checkbox)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Add Select All / Deselect All buttons
        select_buttons_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        
        select_all_btn.clicked.connect(self.select_all_channels)
        deselect_all_btn.clicked.connect(self.deselect_all_channels)
        
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(deselect_all_btn)
        select_buttons_layout.addStretch()
        
        layout.addLayout(select_buttons_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def select_all_channels(self):
        """Select all available channels."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all_channels(self):
        """Deselect all channels."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def get_selected_channels(self):
        """Return a list of the names of the selected channels."""
        selected = []
        for cb in self.checkboxes:
            if cb.isChecked():
                # Handle display names that contain additional text
                text = cb.text()
                if " (will be generated)" in text:
                    # Extract the actual channel name
                    channel_name = text.split(" (will be generated)")[0]
                    selected.append(channel_name)
                else:
                    selected.append(text)
        return selected
