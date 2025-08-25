"""
ChannelSelectionDialog - Popup dialog for channel selection.
Based on original Aurora ChannelSelectionDialog, adapted for session system.
"""

import logging
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QCheckBox, 
    QLabel, QScrollArea, QWidget, QPushButton
)
from PySide6.QtCore import Qt


class ChannelSelectionDialog(QDialog):
    """
    Dialog window that allows the user to select which channels to visualize.
    """

    def __init__(self, channel_names: List[str], parent=None, existing_channels: Optional[List[str]] = None):
        super().__init__(parent)
        
        self.logger = logging.getLogger("aurora.ui.ChannelSelectionDialog")
        
        self.setWindowTitle("Select Channels")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        self.selected_channels = []
        self.existing_channels = existing_channels or channel_names
        self.checkboxes = []
        
        self.logger.info(f"ChannelSelectionDialog opened with {len(channel_names)} channels")
        
        self.init_ui(channel_names)

    def init_ui(self, channel_names: List[str]):
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header label
        header_label = QLabel("Select the channels you want to visualize:")
        header_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header_label)
        
        # Config button
        config_buttons_layout = QHBoxLayout()
        
        self.use_config_btn = QPushButton("Use Default Channels")
        self.use_config_btn.setToolTip("Use channels defined in preconfiguration")
        self.use_config_btn.clicked.connect(self._apply_config_channels)
        config_buttons_layout.addWidget(self.use_config_btn)
        
        config_buttons_layout.addStretch()
        layout.addLayout(config_buttons_layout)

        # Scrollable area for channel checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(3)

        # Create checkboxes for each channel
        for name in channel_names:
            # Add visual indication for channels that need to be generated
            if name == "HR_gen" and name not in self.existing_channels:
                display_name = f"{name} (will be generated)"
                checkbox = QCheckBox(display_name)
                checkbox.setToolTip("This channel will be generated using default parameters when selected")
            else:
                checkbox = QCheckBox(name)
                
            # Start with all channels unchecked
            checkbox.setChecked(False)
            
            self.checkboxes.append(checkbox)
            container_layout.addWidget(checkbox)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Selection control buttons
        select_buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        
        select_all_btn.clicked.connect(self.select_all_channels)
        deselect_all_btn.clicked.connect(self.deselect_all_channels)
        
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(deselect_all_btn)
        select_buttons_layout.addStretch()
        
        # Add selection count
        self.count_label = QLabel()
        self.update_count_display()
        select_buttons_layout.addWidget(self.count_label)
        
        layout.addLayout(select_buttons_layout)

        # Dialog buttons (OK/Cancel)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Connect checkbox signals to update count
        for checkbox in self.checkboxes:
            checkbox.toggled.connect(self.update_count_display)
            
        # Apply default channel selection from configuration
        self._apply_config_channels()

    def select_all_channels(self):
        """Select all available channels."""
        self.logger.debug("Selecting all channels")
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all_channels(self):
        """Deselect all channels."""
        self.logger.debug("Deselecting all channels")
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)
    
    def update_count_display(self):
        """Update the count display showing selected/total channels."""
        selected_count = len(self.get_selected_channels())
        total_count = len(self.checkboxes)
        self.count_label.setText(f"Selected: {selected_count}/{total_count}")
        
    def get_selected_channels(self) -> List[str]:
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
    
    def accept(self):
        """Handle dialog acceptance."""
        selected = self.get_selected_channels()
        self.logger.info(f"Dialog accepted with {len(selected)} channels selected")
        self.logger.debug(f"Selected channels: {selected}")
        
        if not selected:
            self.logger.warning("No channels selected - dialog accepted anyway")
        
        self.selected_channels = selected
        super().accept()
    
    
    def _normalize_channel_name(self, name: str) -> str:
        """Normalize channel name for fuzzy matching."""
        # Remove common prefixes/suffixes and normalize case
        normalized = name.strip().lower()
        
        # Remove common suffixes
        suffixes_to_remove = [' raw', ' filtered', ' processed', '_gen', '_generated']
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        # Remove common prefixes
        prefixes_to_remove = ['bioamp ', 'bio-amp ', 'bio_amp ']
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        
        return normalized
    
    def _find_best_match(self, config_channel: str, available_channels: list) -> str:
        """Find best matching channel name using fuzzy logic."""
        config_normalized = self._normalize_channel_name(config_channel)
        
        # First try exact match (case insensitive)
        for available in available_channels:
            if available.lower() == config_channel.lower():
                return available
        
        # Then try normalized match
        for available in available_channels:
            if self._normalize_channel_name(available) == config_normalized:
                return available
        
        # Finally try partial match (config name contained in available name)
        for available in available_channels:
            if config_normalized in self._normalize_channel_name(available):
                return available
        
        return None
    
    def _apply_config_channels(self):
        """Apply configured channels to the selection with robust fuzzy matching."""
        try:
            from aurora.core.config_manager import get_config_manager
            
            config_manager = get_config_manager()
            config_channels = config_manager.config.default_visible_channels
            
            self.logger.info(f"Config channels from settings: {config_channels}")
            
            # Get all available channels in the file
            available_channels = []
            for checkbox in self.checkboxes:
                channel_name = checkbox.text()
                if " (will be generated)" in channel_name:
                    channel_name = channel_name.split(" (will be generated)")[0]
                available_channels.append(channel_name)
            
            self.logger.info(f"Available channels in file: {available_channels}")
            
            # Uncheck all first
            for checkbox in self.checkboxes:
                checkbox.setChecked(False)
            
            # Find matches using fuzzy logic
            matches_found = []
            not_found = []
            
            for config_channel in config_channels:
                best_match = self._find_best_match(config_channel, available_channels)
                
                if best_match:
                    # Find and check the corresponding checkbox
                    for checkbox in self.checkboxes:
                        checkbox_name = checkbox.text()
                        if " (will be generated)" in checkbox_name:
                            checkbox_name = checkbox_name.split(" (will be generated)")[0]
                        
                        if checkbox_name == best_match:
                            checkbox.setChecked(True)
                            matches_found.append(f"'{config_channel}' → '{best_match}'")
                            break
                else:
                    not_found.append(config_channel)
            
            if matches_found:
                self.logger.info(f"Channels matched and selected: {matches_found}")
            
            if not_found:
                self.logger.warning(f"Config channels not found (no fuzzy match): {not_found}")
                
                # Suggest similar channels for not found ones
                suggestions = []
                for missing in not_found:
                    missing_norm = self._normalize_channel_name(missing)
                    similar = []
                    for available in available_channels:
                        available_norm = self._normalize_channel_name(available)
                        # Simple similarity check
                        if (missing_norm in available_norm or 
                            available_norm in missing_norm or
                            any(part in available_norm for part in missing_norm.split('_') if len(part) > 2)):
                            similar.append(available)
                    
                    if similar:
                        suggestions.append(f"'{missing}' → maybe try: {similar}")
                
                if suggestions:
                    self.logger.info(f"Suggestions for missing channels: {suggestions}")
            
        except Exception as e:
            self.logger.error(f"Error applying config channels: {e}")

    def reject(self):
        """Handle dialog rejection."""
        self.logger.info("Channel selection dialog cancelled")
        super().reject()
        
    @staticmethod
    def select_channels(channel_names: List[str], parent=None, existing_channels: Optional[List[str]] = None) -> Optional[List[str]]:
        """
        Static method to show the dialog and return selected channels.
        Returns None if dialog was cancelled.
        """
        dialog = ChannelSelectionDialog(channel_names, parent, existing_channels)
        
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_selected_channels()
        else:
            return None