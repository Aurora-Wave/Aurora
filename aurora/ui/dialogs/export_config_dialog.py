"""
export_config_dialog.py
-----------------------
Main configuration dialog for hemodynamic data export
compatible with a RedCap-like format based on extract_stand_tilt.m
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QWidget,
    QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal as QtSignal
import logging
from typing import Dict, List, Optional, Any
import os


class ExportConfigDialog(QDialog):
    """
    Advanced configuration dialog for hemodynamic data export.
    Allows selecting protocols, signals, temporal points and analysis windows.
    """

    # Predefined protocol configurations
    PROTOCOL_CONFIGS = {
        "stand": {
            "name": "Stand Test Protocol",
            "description": "Orthostatic stand test protocol",
            "prefix": "stand_",
            "required_signals": ["hr_aurora", "FBP"],
            "recommended_signals": ["CO", "SV", "SVR", "ETCO2", "SPO2"],
            "temporal_points": [20, 30, 40, 50],
            "analysis_windows": {
                "nadir_search": 60,
                "peak_search": 60,
                "stabilization": (300, 600),  # 5-10 min
            },
        },
        "tilt": {
            "name": "Tilt Table Test",
            "description": "Tilt table protocol for orthostatic evaluation",
            "prefix": "tilt_",
            "required_signals": ["hr_aurora", "FBP"],
            "recommended_signals": ["CO", "SV", "SVR", "ETCO2", "SPO2"],
            "temporal_points": [20, 30, 40, 50],
            "analysis_windows": {
                "nadir_search": 60,
                "peak_search": 60,
                "stabilization": (300, 600),
            },
        },
        "lbnp": {
            "name": "Lower Body Negative Pressure",
            "description": "Lower body negative pressure protocol",
            "prefix": "lbnp_",
            "required_signals": ["hr_aurora", "FBP"],
            "recommended_signals": ["CO", "SV", "SVR", "ETCO2", "SPO2"],
            "temporal_points": [20, 30, 40, 50],
            "analysis_windows": {
                "nadir_search": 60,
                "peak_search": 60,
                "stabilization": (300, 600),
            },
        },
        "custom": {
            "name": "Custom Protocol",
            "description": "User-defined custom configuration",
            "prefix": "custom_",
            "required_signals": [],
            "recommended_signals": [],
            "temporal_points": [],
            "analysis_windows": {},
        },
    }

    def __init__(self, session, detected_protocol: str = None, parent=None):
        super().__init__(parent)
        self.session = session
        self.detected_protocol = detected_protocol or "stand"
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("Aurora - Hemodynamic Export Configuration")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        # State variables
        self.export_config: Dict[str, Any] = {}
        self.available_signals: List[str] = []
        self.selected_signals: List[str] = []

        self._setup_ui()
        self._load_available_signals()
        self._connect_signals()
        self._set_default_protocol(self.detected_protocol)

        self.logger.info(
            f"ExportConfigDialog initialized with protocol: {self.detected_protocol}"
        )

    def _setup_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Main tabs
        tab_widget = QTabWidget()
        # Create and add tabs
        protocol_tab = self._create_protocol_tab()
        signals_tab = self._create_signals_tab()
        advanced_tab = self._create_advanced_tab()
        preview_tab = self._create_preview_tab()

        tab_widget.addTab(protocol_tab, "Protocol")
        tab_widget.addTab(signals_tab, "Signals")
        tab_widget.addTab(advanced_tab, "Advanced")
        tab_widget.addTab(preview_tab, "Preview")

        layout.addWidget(tab_widget)

        # Action buttons (single, cleaned instance)
        button_layout = QHBoxLayout()
        self.validate_btn = QPushButton("🔍 Validate Configuration")
        self.export_btn = QPushButton("💾 Export Data")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.export_btn.setDefault(True)
        self.export_btn.setEnabled(False)  # Enabled only after successful validation
        button_layout.addStretch()
        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def _create_protocol_tab(self) -> QWidget:
        """Create protocol configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Protocol selection
        protocol_group = QGroupBox("Protocol Type")
        protocol_layout = QVBoxLayout(protocol_group)

        self.protocol_combo = QComboBox()
        for key, config in self.PROTOCOL_CONFIGS.items():
            self.protocol_combo.addItem(config["name"], key)
        protocol_layout.addWidget(QLabel("Select protocol:"))
        protocol_layout.addWidget(self.protocol_combo)

        # Protocol description
        self.protocol_description = QTextEdit()
        self.protocol_description.setMaximumHeight(80)
        self.protocol_description.setReadOnly(True)
        protocol_layout.addWidget(QLabel("Description:"))
        protocol_layout.addWidget(self.protocol_description)

        layout.addWidget(protocol_group)
        # Output file settings
        output_group = QGroupBox("Output File")
        output_layout = QGridLayout(output_group)

        self.participant_id = QSpinBox()
        self.participant_id.setMinimum(1)
        self.participant_id.setMaximum(9999)
        self.participant_id.setValue(1)
        self.output_path_label = QLabel("Not selected")
        self.browse_btn = QPushButton("📁 Browse...")

        output_layout.addWidget(QLabel("Participant ID:"), 0, 0)
        output_layout.addWidget(self.participant_id, 0, 1)
        output_layout.addWidget(QLabel("Target file:"), 1, 0)
        output_layout.addWidget(self.output_path_label, 1, 1)
        output_layout.addWidget(self.browse_btn, 1, 2)

        layout.addWidget(output_group)
        layout.addStretch()

        return tab

    def _create_signals_tab(self) -> QWidget:
        """Create signal selection tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Left panel - available signals
        available_group = QGroupBox("Available Signals")
        available_layout = QVBoxLayout(available_group)

        self.available_list = QListWidget()
        available_layout.addWidget(self.available_list)

        # Right panel - selected signals
        selected_group = QGroupBox("Selected Signals")
        selected_layout = QVBoxLayout(selected_group)

        self.selected_list = QListWidget()
        selected_layout.addWidget(self.selected_list)

        # Control buttons
        control_layout = QVBoxLayout()
        control_layout.addStretch()

        self.add_signal_btn = QPushButton("➡️ Add")
        self.remove_signal_btn = QPushButton("⬅️ Remove")
        self.add_all_btn = QPushButton("⏩ Add All")
        self.remove_all_btn = QPushButton("⏪ Remove All")

        control_layout.addWidget(self.add_signal_btn)
        control_layout.addWidget(self.remove_signal_btn)
        control_layout.addWidget(self.add_all_btn)
        control_layout.addWidget(self.remove_all_btn)
        control_layout.addStretch()

        # Ensamblar layout
        layout.addWidget(available_group)
        layout.addLayout(control_layout)
        layout.addWidget(selected_group)

        return tab

    def _create_advanced_tab(self) -> QWidget:
        """Create advanced configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Temporal configuration
        temporal_group = QGroupBox("Temporal Analysis Points")
        temporal_layout = QGridLayout(temporal_group)

        self.temporal_checkboxes = {}
        default_points = [20, 30, 40, 50]

        for i, point in enumerate(default_points):
            checkbox = QCheckBox(f"{point} seconds")
            checkbox.setChecked(True)
            self.temporal_checkboxes[point] = checkbox
            temporal_layout.addWidget(checkbox, i // 2, i % 2)

        layout.addWidget(temporal_group)

        # Analysis windows configuration
        windows_group = QGroupBox("Analysis Windows")
        windows_layout = QGridLayout(windows_group)

        self.nadir_window = QSpinBox()
        self.nadir_window.setMinimum(10)
        self.nadir_window.setMaximum(300)
        self.nadir_window.setValue(60)
        self.nadir_window.setSuffix(" s")

        self.stabilization_start = QSpinBox()
        self.stabilization_start.setMinimum(60)
        self.stabilization_start.setMaximum(600)
        self.stabilization_start.setValue(300)
        self.stabilization_start.setSuffix(" s")

        self.stabilization_end = QSpinBox()
        self.stabilization_end.setMinimum(300)
        self.stabilization_end.setMaximum(1200)
        self.stabilization_end.setValue(600)
        self.stabilization_end.setSuffix(" s")

        windows_layout.addWidget(QLabel("Nadir search window:"), 0, 0)
        windows_layout.addWidget(self.nadir_window, 0, 1)
        windows_layout.addWidget(QLabel("Stabilization start:"), 1, 0)
        windows_layout.addWidget(self.stabilization_start, 1, 1)
        windows_layout.addWidget(QLabel("Stabilization end:"), 2, 0)
        windows_layout.addWidget(self.stabilization_end, 2, 1)

        layout.addWidget(windows_group)
        layout.addStretch()

        return tab

    def _create_preview_tab(self) -> QWidget:
        """Create preview tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        preview_label = QLabel("Configuration Preview:")
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(self.font())
        layout.addWidget(self.preview_text)

        return tab

    def _load_available_signals(self):
        """Load available signals for the current session."""
        if not self.session or not hasattr(self.session, "data_manager"):
            return

        try:
            # Get signals from the loaded file
            file_path = getattr(self.session, "file_path", None)
            if file_path:
                self.available_signals = (
                    self.session.data_manager.get_available_channels(file_path)
                )

                # Add available hr_aurora configurations (parameterized variants)
                if "ECG" in self.available_signals:
                    hr_configs = (
                        self.session.data_manager.get_available_channels_for_export(
                            file_path
                        )
                    )
                    hr_aurora_configs = [
                        ch for ch in hr_configs if ch.lower().startswith("hr_aurora")
                    ]

                    # Replace base hr_aurora with configuration-specific versions
                    if "hr_aurora" in self.available_signals:
                        self.available_signals.remove("hr_aurora")

                    self.available_signals.extend(hr_aurora_configs)

                self.logger.info(
                    f"Available signals loaded: {len(self.available_signals)}"
                )
                self._update_signal_lists()

        except Exception as e:
            self.logger.error(f"Error loading available signals: {e}")
            QMessageBox.warning(self, "Error", f"Error loading signals: {e}")

    def _update_signal_lists(self):
        """Refresh the available and selected signal lists."""
        self.available_list.clear()
        self.selected_list.clear()

        # Available (non-selected) signals
        available_not_selected = [
            sig for sig in self.available_signals if sig not in self.selected_signals
        ]
        for signal in available_not_selected:
            item = QListWidgetItem(signal)

            # Mark required signals
            current_protocol = self.protocol_combo.currentData()
            required = self.PROTOCOL_CONFIGS.get(current_protocol, {}).get(
                "required_signals", []
            )

            if any(req in signal for req in required):
                item.setText(f"⭐ {signal}")
                item.setToolTip("Required signal for this protocol")

            self.available_list.addItem(item)

        # Selected signals
        for signal in self.selected_signals:
            item = QListWidgetItem(signal)
            self.selected_list.addItem(item)

    def _connect_signals(self):
        """Connect UI event signals."""
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        self.browse_btn.clicked.connect(self._browse_output_file)
        self.validate_btn.clicked.connect(self._validate_configuration)
        self.export_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        # Signal list control buttons
        self.add_signal_btn.clicked.connect(self._add_signal)
        self.remove_signal_btn.clicked.connect(self._remove_signal)
        self.add_all_btn.clicked.connect(self._add_all_signals)
        self.remove_all_btn.clicked.connect(self._remove_all_signals)

        # Update preview when key fields change
        self.protocol_combo.currentTextChanged.connect(self._update_preview)
        self.participant_id.valueChanged.connect(self._update_preview)

    def _set_default_protocol(self, protocol_key: str):
        """Set default protocol."""
        index = self.protocol_combo.findData(protocol_key)
        if index >= 0:
            self.protocol_combo.setCurrentIndex(index)
            self._on_protocol_changed()

    def _on_protocol_changed(self):
        """Handle protocol change."""
        current_protocol = self.protocol_combo.currentData()
        config = self.PROTOCOL_CONFIGS.get(current_protocol, {})
        # Update description
        description = config.get("description", "")
        self.protocol_description.setPlainText(description)

        # Auto-select required and recommended signals
        required = config.get("required_signals", [])
        recommended = config.get("recommended_signals", [])

        # Clear current selection
        self.selected_signals.clear()

        # Add required signals
        for req_signal in required:
            matching_signals = [
                sig for sig in self.available_signals if req_signal in sig
            ]
            if matching_signals:
                # Take first match (default configuration if multiple)
                self.selected_signals.append(matching_signals[0])

        # Add recommended signals if available
        for rec_signal in recommended:
            if (
                rec_signal in self.available_signals
                and rec_signal not in self.selected_signals
            ):
                self.selected_signals.append(rec_signal)

        self._update_signal_lists()
        self._update_preview()

        self.logger.debug(f"Protocol changed to: {current_protocol}")

    def _browse_output_file(self):
        """Open dialog to select output file."""
        default_name = f"participant_{self.participant_id.value():03d}_export.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save export as",
            default_name,
            "CSV files (*.csv);;All files (*.*)",
        )

        if file_path:
            self.output_path_label.setText(os.path.basename(file_path))
            self.output_path_label.setToolTip(file_path)
            self._update_preview()

    def _add_signal(self):
        """Add currently selected signal."""
        current = self.available_list.currentItem()
        if current:
            signal_name = current.text().replace("⭐ ", "")  # Remove required marker
            if signal_name not in self.selected_signals:
                self.selected_signals.append(signal_name)
                self._update_signal_lists()
                self._update_preview()

    def _remove_signal(self):
        """Remove currently selected signal."""
        current = self.selected_list.currentItem()
        if current:
            signal_name = current.text()
            if signal_name in self.selected_signals:
                self.selected_signals.remove(signal_name)
                self._update_signal_lists()
                self._update_preview()

    def _add_all_signals(self):
        """Add all available signals."""
        self.selected_signals = self.available_signals.copy()
        self._update_signal_lists()
        self._update_preview()

    def _remove_all_signals(self):
        """Remove all selected signals."""
        self.selected_signals.clear()
        self._update_signal_lists()
        self._update_preview()

    def _update_preview(self):
        """Update configuration preview pane."""
        config = self.get_export_config()

        preview_text = []
        preview_text.append("=== EXPORT CONFIGURATION ===\n")

        preview_text.append(f"📋 Protocol: {config['protocol']['name']}")
        preview_text.append(f"🆔 Participant: {config['participant_id']:03d}")
        preview_text.append(f"📄 File: {config.get('output_path', 'Not selected')}\n")

        preview_text.append(f"📊 Selected signals ({len(config['signals'])}):")
        for signal in config["signals"]:
            preview_text.append(f"  • {signal}")

        preview_text.append(f"\n⏱️ Temporal points:")
        for point in config["temporal_points"]:
            preview_text.append(f"  • {point}s")

        preview_text.append(f"\n🔍 Analysis windows:")
        windows = config["analysis_windows"]
        preview_text.append(f"  • Nadir search: {windows['nadir_search']}s")
        preview_text.append(
            f"  • Stabilization: {windows['stabilization'][0]}-{windows['stabilization'][1]}s"
        )

        self.preview_text.setPlainText("\n".join(preview_text))

    def _validate_configuration(self):
        """Validate current configuration."""
        try:
            config = self.get_export_config()

            # Basic validations
            errors = []

            if not config["signals"]:
                errors.append("No signals selected")

            if not config.get("output_path"):
                errors.append("No output file specified")

            # Validate required signals
            protocol_config = self.PROTOCOL_CONFIGS.get(config["protocol"]["key"], {})
            required_signals = protocol_config.get("required_signals", [])

            for req_signal in required_signals:
                if not any(req_signal in signal for signal in config["signals"]):
                    errors.append(f"Missing required signal: {req_signal}")

            if errors:
                QMessageBox.warning(
                    self,
                    "Invalid configuration",
                    "Errors found:\n\n" + "\n".join(f"• {error}" for error in errors),
                )
                return False

            # Successful validation
            QMessageBox.information(
                self,
                "Validation successful",
                "✅ Configuration is valid and ready to export.",
            )
            self.export_btn.setEnabled(True)
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Validation error", f"Error during validation: {e}"
            )
            return False

    def get_export_config(self) -> Dict[str, Any]:
        """Return current export configuration."""
        current_protocol_key = self.protocol_combo.currentData()
        protocol_config = self.PROTOCOL_CONFIGS.get(current_protocol_key, {})

        # Collect selected temporal points
        selected_temporal = []
        for point, checkbox in self.temporal_checkboxes.items():
            if checkbox.isChecked():
                selected_temporal.append(point)

        config = {
            "protocol": {
                "key": current_protocol_key,
                "name": protocol_config.get("name", ""),
                "prefix": protocol_config.get("prefix", ""),
            },
            "participant_id": self.participant_id.value(),
            "output_path": self.output_path_label.toolTip() or None,
            "signals": self.selected_signals.copy(),
            "temporal_points": selected_temporal,
            "analysis_windows": {
                "nadir_search": self.nadir_window.value(),
                "stabilization": (
                    self.stabilization_start.value(),
                    self.stabilization_end.value(),
                ),
            },
            "session": self.session,
        }

        return config
