"""
FileLoaderDialog - Simple form for loading signal file and configuration.
Replaces previous channel selection flow with dual loading system.
"""

import os
import logging
from typing import Tuple, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QDialogButtonBox, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class FileLoaderDialog(QDialog):
    """
    Form dialog for loading:
    1. Signal file (.adicht) - REQUIRED
    2. Configuration file (.json) - OPTIONAL (fallback to channel selection dialog)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger("aurora.ui.FileLoaderDialog")
        self.logger.info("FileLoaderDialog opened")
        
        self.setWindowTitle("Load Signal File and Configuration")
        self.setModal(True)
        self.setMinimumSize(600, 250)
        self.setMaximumSize(800, 350)
        
        # File paths
        self.signal_file_path = ""
        self.config_file_path = ""
        
        self.init_ui()
        self._update_ok_button_state()
    
    def init_ui(self):
        """Initialize form interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header_label = QLabel("Select signal file and optional configuration")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Form group box
        form_group = QGroupBox("File Selection")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        
        # Signal file row
        signal_layout = QHBoxLayout()
        self.signal_path_edit = QLineEdit()
        self.signal_path_edit.setPlaceholderText("Select a signal file (.adicht)")
        self.signal_path_edit.setReadOnly(True)
        
        self.signal_browse_btn = QPushButton("Browse...")
        self.signal_browse_btn.setMinimumWidth(100)
        self.signal_browse_btn.clicked.connect(self._browse_signal_file)
        
        signal_layout.addWidget(self.signal_path_edit)
        signal_layout.addWidget(self.signal_browse_btn)
        
        # Config file row
        config_layout = QHBoxLayout()
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setPlaceholderText("Optional: Load saved configuration (.json)")
        self.config_path_edit.setReadOnly(True)
        
        self.config_browse_btn = QPushButton("Browse...")
        self.config_browse_btn.setMinimumWidth(100)
        self.config_browse_btn.clicked.connect(self._browse_config_file)
        
        self.config_clear_btn = QPushButton("Clear")
        self.config_clear_btn.setMinimumWidth(80)
        self.config_clear_btn.clicked.connect(self._clear_config_file)
        self.config_clear_btn.setEnabled(False)
        
        config_layout.addWidget(self.config_path_edit)
        config_layout.addWidget(self.config_browse_btn)
        config_layout.addWidget(self.config_clear_btn)
        
        # Add rows to form
        form_layout.addRow("Signal File:", signal_layout)
        form_layout.addRow("Config File:", config_layout)
        
        layout.addWidget(form_group)
        
        # Stretch
        layout.addStretch()
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_dialog)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        # Get OK button reference
        self.ok_button = self.button_box.button(QDialogButtonBox.Ok)
    
    def _browse_signal_file(self):
        """Open dialog to select signal file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Signal File",
            "",
            "LabChart Files (*.adicht);;All Files (*)"
        )
        
        if file_path:
            self.signal_file_path = file_path
            self.signal_path_edit.setText(os.path.basename(file_path))
            self.signal_path_edit.setToolTip(file_path)
            self.logger.info(f"Signal file selected: {file_path}")
            self._update_ok_button_state()
    
    def _browse_config_file(self):
        """Open dialog to select configuration file."""
        # Get default config directory
        try:
            from aurora.core.config_manager import get_config_manager
            config_manager = get_config_manager()
            default_dir = os.path.dirname(config_manager.get_config_file_path())
        except:
            default_dir = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Configuration File",
            default_dir,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.config_file_path = file_path
            self.config_path_edit.setText(os.path.basename(file_path))
            self.config_path_edit.setToolTip(file_path)
            self.config_clear_btn.setEnabled(True)
            self.logger.info(f"Config file selected: {file_path}")
    
    def _clear_config_file(self):
        """Clear configuration file selection."""
        self.config_file_path = ""
        self.config_path_edit.setText("")
        self.config_path_edit.setToolTip("")
        self.config_clear_btn.setEnabled(False)
        self.logger.info("Config file selection cleared")
    
    def _update_ok_button_state(self):
        """Update OK button state based on signal file availability."""
        has_signal_file = bool(self.signal_file_path and os.path.exists(self.signal_file_path))
        self.ok_button.setEnabled(has_signal_file)
        
        if has_signal_file:
            self.ok_button.setText("Load Files")
        else:
            self.ok_button.setText("Select Signal File")
    
    def _accept_dialog(self):
        """Handle dialog acceptance."""
        # Validate signal file
        if not self.signal_file_path or not os.path.exists(self.signal_file_path):
            QMessageBox.warning(self, "Error", "Please select a valid signal file")
            return
        
        # Validate config file if selected
        if self.config_file_path and not os.path.exists(self.config_file_path):
            QMessageBox.warning(self, "Error", "Selected config file does not exist")
            return
        
        self.logger.info(f"Files accepted - Signal: {self.signal_file_path}, Config: {self.config_file_path or 'None (will show channel selection)'}")
        
        # Accept dialog
        self.accept()
    
    def get_selected_files(self) -> Tuple[str, Optional[str]]:
        """
        Get selected files.
        Returns:
            Tuple[str, Optional[str]]: (signal_file_path, config_file_path_or_none)
        """
        return (
            self.signal_file_path,
            self.config_file_path if self.config_file_path else None
        )
    
    @staticmethod
    def select_files(parent=None) -> Optional[Tuple[str, Optional[str]]]:
        """
        Static method to show dialog and get files.
        
        Returns:
            Optional[Tuple[str, Optional[str]]]: None if cancelled, else (signal_file, config_file_or_none)
        """
        dialog = FileLoaderDialog(parent)
        
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_selected_files()
        else:
            return None