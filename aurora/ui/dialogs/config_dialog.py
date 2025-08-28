"""
Configuration Dialog for Aurora Application.
Provides UI for managing all application settings.
"""

import os
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QListWidget, QGroupBox, QFormLayout,
    QFileDialog, QMessageBox, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal

from aurora.core.config_manager import get_config_manager


class ChannelSelectionWidget(QWidget):
    """Widget for managing default visible channels."""
    
    def __init__(self, channels: List[str], parent=None):
        super().__init__(parent)
        # Lista completa de canales que Aurora puede manejar (hardcodeado para versión compilada)
        # Basado en archivos reales del usuario final
        self.available_channels = [
            "HR_gen", "ECG", "FBP", "Valsalva", "CO", "SV", "SVR", 
            "ETCO2", "SPO2", "MCA-L", "MCA-R", "Tilt Angle", "MAP",
            "BioAmp raw", "HR"
        ]
        self.selected_channels = channels.copy()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Select default channels to load when opening files:")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Channel list
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QAbstractItemView.MultiSelection)
        
        # Populate with available channels
        for channel in self.available_channels:
            item = QListWidgetItem(channel)
            self.channel_list.addItem(item)
            if channel in self.selected_channels:
                item.setSelected(True)
        
        layout.addWidget(self.channel_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        reset_btn = QPushButton("Reset to Default")
        
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn.clicked.connect(self._select_none)
        reset_btn.clicked.connect(self._reset_default)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def _select_all(self):
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setSelected(True)
    
    def _select_none(self):
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setSelected(False)
    
    def _reset_default(self):
        default_channels = ["HR_gen", "ECG", "FBP", "Valsalva"]
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            item.setSelected(item.text() in default_channels)
    
    def get_selected_channels(self) -> List[str]:
        """Get list of selected channels."""
        selected = []
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item.isSelected():
                selected.append(item.text())
        return selected




class SimpleConfigTab(QWidget):
    """Simplified configuration tab with only essential settings."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Channel settings
        channels_group = QGroupBox("Default Channels to Load")
        channels_layout = QVBoxLayout(channels_group)
        
        info_label = QLabel("These channels will be automatically selected when loading files:")
        info_label.setWordWrap(True)
        channels_layout.addWidget(info_label)
        
        self.channel_widget = ChannelSelectionWidget(self.config.default_visible_channels)
        channels_layout.addWidget(self.channel_widget)
        
        layout.addWidget(channels_group)
        
        layout.addStretch()
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings from UI."""
        return {
            "default_visible_channels": self.channel_widget.get_selected_channels()
        }




class ConfigDialog(QDialog):
    """Main configuration dialog."""
    
    config_changed = Signal()  # Emitted when configuration is saved
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.setWindowTitle("Aurora Configuration")
        self.setModal(True)
        self.resize(600, 500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Config file path
        path_group = QGroupBox("Configuration File")
        path_layout = QHBoxLayout(path_group)
        
        self.path_label = QLabel(self.config_manager.get_config_file_path())
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_config_file)
        path_layout.addWidget(browse_btn)
        
        layout.addWidget(path_group)
        
        # Simple configuration interface
        self.config_tab = SimpleConfigTab(self.config_manager.config)
        layout.addWidget(self.config_tab)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_config)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _browse_config_file(self):
        """Browse for config file location."""
        current_path = self.config_manager.get_config_file_path()
        new_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Configuration File Location",
            current_path,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if new_path:
            self.config_manager.set_config_file_path(new_path)
            self.path_label.setText(new_path)
            QMessageBox.information(
                self,
                "Configuration File Changed",
                f"Configuration file location changed to:\n{new_path}\n\nFile will be created when configuration is saved."
            )
    
    def _reset_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all settings to their default values?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.config_manager.reset_to_defaults()
            # Recreate tabs with default values
            self._refresh_interface()
            QMessageBox.information(self, "Reset Complete", "All settings have been reset to defaults.")
    
    def _refresh_interface(self):
        """Refresh interface with current configuration."""
        # Recreate the simple config tab
        self.config_tab = SimpleConfigTab(self.config_manager.config)
        
        # Replace in layout
        layout = self.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if isinstance(item.widget(), SimpleConfigTab):
                item.widget().setParent(None)
                layout.insertWidget(i, self.config_tab)
                break
    
    def _save_config(self):
        """Save configuration from UI to manager and file."""
        try:
            # Update config manager with UI values
            settings = self.config_tab.get_settings()
            
            # Update config object  
            self.config_manager.config.default_visible_channels = settings["default_visible_channels"]
            
            # Save to file
            if self.config_manager.save_config():
                QMessageBox.information(self, "Success", "Configuration saved successfully.")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration to file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")