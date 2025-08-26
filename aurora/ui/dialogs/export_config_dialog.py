"""
export_config_dialog.py
-----------------------
Diálogo principal de configuración para exportación de datos hemodinámicos
compatible con formato RedCap según extract_stand_tilt.m
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
    Diálogo de configuración avanzada para exportación de datos hemodinámicos.
    Permite seleccionar protocolos, señales, intervalos y formato de exportación.
    """

    # Configuraciones de protocolo predefinidas
    PROTOCOL_CONFIGS = {
        "stand": {
            "name": "Stand Test Protocol",
            "description": "Protocolo de prueba ortostática en posición de pie",
            "prefix": "stand_",
            "required_signals": ["HR_gen", "FBP"],
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
            "description": "Protocolo de mesa basculante para evaluación ortostática",
            "prefix": "tilt_",
            "required_signals": ["HR_gen", "FBP"],
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
            "description": "Protocolo de presión negativa en miembros inferiores",
            "prefix": "lbnp_",
            "required_signals": ["HR_gen", "FBP"],
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
            "description": "Configuración personalizada definida por usuario",
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

        self.setWindowTitle("Aurora - Configuración de Exportación Hemodynamic")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        # Variables de estado
        self.export_config = {}
        self.available_signals = []
        self.selected_signals = []

        self._setup_ui()
        self._load_available_signals()
        self._connect_signals()
        self._set_default_protocol(self.detected_protocol)

        self.logger.info(
            f"ExportConfigDialog inicializado con protocolo: {self.detected_protocol}"
        )

    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        layout = QVBoxLayout(self)

        # Crear tabs principales
        tab_widget = QTabWidget()

        # Tab 1: Configuración de Protocolo
        protocol_tab = self._create_protocol_tab()
        tab_widget.addTab(protocol_tab, "📋 Protocolo")

        # Tab 2: Selección de Señales
        signals_tab = self._create_signals_tab()
        tab_widget.addTab(signals_tab, "📊 Señales")

        # Tab 3: Configuración Avanzada
        advanced_tab = self._create_advanced_tab()
        tab_widget.addTab(advanced_tab, "⚙️ Avanzado")

        # Tab 4: Vista Previa
        preview_tab = self._create_preview_tab()
        tab_widget.addTab(preview_tab, "👁️ Vista Previa")

        layout.addWidget(tab_widget)

        # Botones de acción
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("🔍 Validar Configuración")
        self.export_btn = QPushButton("💾 Exportar Datos")
        self.cancel_btn = QPushButton("❌ Cancelar")

        self.export_btn.setDefault(True)
        self.export_btn.setEnabled(False)  # Habilitado después de validación

        button_layout.addStretch()
        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _create_protocol_tab(self) -> QWidget:
        """Crea tab de configuración de protocolo."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Selección de protocolo
        protocol_group = QGroupBox("Tipo de Protocolo")
        protocol_layout = QVBoxLayout(protocol_group)

        self.protocol_combo = QComboBox()
        for key, config in self.PROTOCOL_CONFIGS.items():
            self.protocol_combo.addItem(config["name"], key)

        protocol_layout.addWidget(QLabel("Seleccionar protocolo:"))
        protocol_layout.addWidget(self.protocol_combo)

        # Descripción del protocolo
        self.protocol_description = QTextEdit()
        self.protocol_description.setMaximumHeight(80)
        self.protocol_description.setReadOnly(True)
        protocol_layout.addWidget(QLabel("Descripción:"))
        protocol_layout.addWidget(self.protocol_description)

        layout.addWidget(protocol_group)

        # Configuración de archivo de salida
        output_group = QGroupBox("Archivo de Salida")
        output_layout = QGridLayout(output_group)

        self.participant_id = QSpinBox()
        self.participant_id.setMinimum(1)
        self.participant_id.setMaximum(9999)
        self.participant_id.setValue(1)

        self.output_path_label = QLabel("No seleccionado")
        self.browse_btn = QPushButton("📁 Examinar...")

        output_layout.addWidget(QLabel("ID Participante:"), 0, 0)
        output_layout.addWidget(self.participant_id, 0, 1)
        output_layout.addWidget(QLabel("Archivo destino:"), 1, 0)
        output_layout.addWidget(self.output_path_label, 1, 1)
        output_layout.addWidget(self.browse_btn, 1, 2)

        layout.addWidget(output_group)
        layout.addStretch()

        return tab

    def _create_signals_tab(self) -> QWidget:
        """Crea tab de selección de señales."""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # Panel izquierdo - Señales disponibles
        available_group = QGroupBox("Señales Disponibles")
        available_layout = QVBoxLayout(available_group)

        self.available_list = QListWidget()
        available_layout.addWidget(self.available_list)

        # Panel derecho - Señales seleccionadas
        selected_group = QGroupBox("Señales Seleccionadas")
        selected_layout = QVBoxLayout(selected_group)

        self.selected_list = QListWidget()
        selected_layout.addWidget(self.selected_list)

        # Botones de control
        control_layout = QVBoxLayout()
        control_layout.addStretch()

        self.add_signal_btn = QPushButton("➡️ Agregar")
        self.remove_signal_btn = QPushButton("⬅️ Quitar")
        self.add_all_btn = QPushButton("⏩ Agregar Todas")
        self.remove_all_btn = QPushButton("⏪ Quitar Todas")

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
        """Crea tab de configuración avanzada."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Configuración temporal
        temporal_group = QGroupBox("Puntos Temporales de Análisis")
        temporal_layout = QGridLayout(temporal_group)

        self.temporal_checkboxes = {}
        default_points = [20, 30, 40, 50]

        for i, point in enumerate(default_points):
            checkbox = QCheckBox(f"{point} segundos")
            checkbox.setChecked(True)
            self.temporal_checkboxes[point] = checkbox
            temporal_layout.addWidget(checkbox, i // 2, i % 2)

        layout.addWidget(temporal_group)

        # Configuración de ventanas de análisis
        windows_group = QGroupBox("Ventanas de Análisis")
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

        windows_layout.addWidget(QLabel("Ventana búsqueda nadir:"), 0, 0)
        windows_layout.addWidget(self.nadir_window, 0, 1)
        windows_layout.addWidget(QLabel("Estabilización inicio:"), 1, 0)
        windows_layout.addWidget(self.stabilization_start, 1, 1)
        windows_layout.addWidget(QLabel("Estabilización fin:"), 2, 0)
        windows_layout.addWidget(self.stabilization_end, 2, 1)

        layout.addWidget(windows_group)
        layout.addStretch()

        return tab

    def _create_preview_tab(self) -> QWidget:
        """Crea tab de vista previa."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        preview_label = QLabel("Vista Previa de Configuración:")
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(self.font())
        layout.addWidget(self.preview_text)

        return tab

    def _load_available_signals(self):
        """Carga las señales disponibles en la sesión actual."""
        if not self.session or not hasattr(self.session, "data_manager"):
            return

        try:
            # Obtener señales del archivo cargado
            file_path = getattr(self.session, "file_path", None)
            if file_path:
                self.available_signals = (
                    self.session.data_manager.get_available_channels(file_path)
                )

                # Agregar configuraciones de HR_gen disponibles
                if "ECG" in self.available_signals:
                    hr_configs = (
                        self.session.data_manager.get_available_channels_for_export(
                            file_path
                        )
                    )
                    hr_gen_configs = [
                        ch for ch in hr_configs if ch.startswith("HR_gen")
                    ]

                    # Reemplazar HR_gen básico con configuraciones específicas
                    if "HR_gen" in self.available_signals:
                        self.available_signals.remove("HR_gen")

                    self.available_signals.extend(hr_gen_configs)

                self.logger.info(
                    f"Señales disponibles cargadas: {len(self.available_signals)}"
                )
                self._update_signal_lists()

        except Exception as e:
            self.logger.error(f"Error cargando señales disponibles: {e}")
            QMessageBox.warning(self, "Error", f"Error cargando señales: {e}")

    def _update_signal_lists(self):
        """Actualiza las listas de señales disponibles y seleccionadas."""
        self.available_list.clear()
        self.selected_list.clear()

        # Señales disponibles (no seleccionadas)
        available_not_selected = [
            sig for sig in self.available_signals if sig not in self.selected_signals
        ]
        for signal in available_not_selected:
            item = QListWidgetItem(signal)

            # Marcar señales requeridas
            current_protocol = self.protocol_combo.currentData()
            required = self.PROTOCOL_CONFIGS.get(current_protocol, {}).get(
                "required_signals", []
            )

            if any(req in signal for req in required):
                item.setText(f"⭐ {signal}")
                item.setToolTip("Señal requerida para este protocolo")

            self.available_list.addItem(item)

        # Señales seleccionadas
        for signal in self.selected_signals:
            item = QListWidgetItem(signal)
            self.selected_list.addItem(item)

    def _connect_signals(self):
        """Conecta señales de la interfaz."""
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        self.browse_btn.clicked.connect(self._browse_output_file)
        self.validate_btn.clicked.connect(self._validate_configuration)
        self.export_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        # Botones de control de señales
        self.add_signal_btn.clicked.connect(self._add_signal)
        self.remove_signal_btn.clicked.connect(self._remove_signal)
        self.add_all_btn.clicked.connect(self._add_all_signals)
        self.remove_all_btn.clicked.connect(self._remove_all_signals)

        # Actualizar vista previa cuando cambie algo
        self.protocol_combo.currentTextChanged.connect(self._update_preview)
        self.participant_id.valueChanged.connect(self._update_preview)

    def _set_default_protocol(self, protocol_key: str):
        """Establece el protocolo por defecto."""
        index = self.protocol_combo.findData(protocol_key)
        if index >= 0:
            self.protocol_combo.setCurrentIndex(index)
            self._on_protocol_changed()

    def _on_protocol_changed(self):
        """Maneja cambio de protocolo."""
        current_protocol = self.protocol_combo.currentData()
        config = self.PROTOCOL_CONFIGS.get(current_protocol, {})

        # Actualizar descripción
        description = config.get("description", "")
        self.protocol_description.setPlainText(description)

        # Auto-seleccionar señales requeridas
        required = config.get("required_signals", [])
        recommended = config.get("recommended_signals", [])

        # Limpiar selección actual
        self.selected_signals.clear()

        # Agregar señales requeridas
        for req_signal in required:
            matching_signals = [
                sig for sig in self.available_signals if req_signal in sig
            ]
            if matching_signals:
                # Tomar la primera coincidencia (o la configuración por defecto)
                self.selected_signals.append(matching_signals[0])

        # Agregar señales recomendadas disponibles
        for rec_signal in recommended:
            if (
                rec_signal in self.available_signals
                and rec_signal not in self.selected_signals
            ):
                self.selected_signals.append(rec_signal)

        self._update_signal_lists()
        self._update_preview()

        self.logger.debug(f"Protocolo cambiado a: {current_protocol}")

    def _browse_output_file(self):
        """Abre diálogo para seleccionar archivo de salida."""
        default_name = f"participant_{self.participant_id.value():03d}_export.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar exportación como",
            default_name,
            "CSV files (*.csv);;All files (*.*)",
        )

        if file_path:
            self.output_path_label.setText(os.path.basename(file_path))
            self.output_path_label.setToolTip(file_path)
            self._update_preview()

    def _add_signal(self):
        """Agrega señal seleccionada."""
        current = self.available_list.currentItem()
        if current:
            signal_name = current.text().replace(
                "⭐ ", ""
            )  # Remover marca de requerida
            if signal_name not in self.selected_signals:
                self.selected_signals.append(signal_name)
                self._update_signal_lists()
                self._update_preview()

    def _remove_signal(self):
        """Quita señal seleccionada."""
        current = self.selected_list.currentItem()
        if current:
            signal_name = current.text()
            if signal_name in self.selected_signals:
                self.selected_signals.remove(signal_name)
                self._update_signal_lists()
                self._update_preview()

    def _add_all_signals(self):
        """Agrega todas las señales disponibles."""
        self.selected_signals = self.available_signals.copy()
        self._update_signal_lists()
        self._update_preview()

    def _remove_all_signals(self):
        """Quita todas las señales seleccionadas."""
        self.selected_signals.clear()
        self._update_signal_lists()
        self._update_preview()

    def _update_preview(self):
        """Actualiza la vista previa de configuración."""
        config = self.get_export_config()

        preview_text = []
        preview_text.append("=== CONFIGURACIÓN DE EXPORTACIÓN ===\n")

        preview_text.append(f"📋 Protocolo: {config['protocol']['name']}")
        preview_text.append(f"🆔 Participante: {config['participant_id']:03d}")
        preview_text.append(
            f"📄 Archivo: {config.get('output_path', 'No seleccionado')}\n"
        )

        preview_text.append(f"📊 Señales seleccionadas ({len(config['signals'])}):")
        for signal in config["signals"]:
            preview_text.append(f"  • {signal}")

        preview_text.append(f"\n⏱️ Puntos temporales:")
        for point in config["temporal_points"]:
            preview_text.append(f"  • {point}s")

        preview_text.append(f"\n🔍 Ventanas de análisis:")
        windows = config["analysis_windows"]
        preview_text.append(f"  • Búsqueda nadir: {windows['nadir_search']}s")
        preview_text.append(
            f"  • Estabilización: {windows['stabilization'][0]}-{windows['stabilization'][1]}s"
        )

        self.preview_text.setPlainText("\n".join(preview_text))

    def _validate_configuration(self):
        """Valida la configuración actual."""
        try:
            config = self.get_export_config()

            # Validaciones básicas
            errors = []

            if not config["signals"]:
                errors.append("No hay señales seleccionadas")

            if not config.get("output_path"):
                errors.append("No se ha especificado archivo de salida")

            # Validar señales requeridas
            protocol_config = self.PROTOCOL_CONFIGS.get(config["protocol"]["key"], {})
            required_signals = protocol_config.get("required_signals", [])

            for req_signal in required_signals:
                if not any(req_signal in signal for signal in config["signals"]):
                    errors.append(f"Señal requerida faltante: {req_signal}")

            if errors:
                QMessageBox.warning(
                    self,
                    "Configuración inválida",
                    "Errores encontrados:\n\n"
                    + "\n".join(f"• {error}" for error in errors),
                )
                return False

            # Validación exitosa
            QMessageBox.information(
                self,
                "Validación exitosa",
                "✅ La configuración es válida y está lista para exportar.",
            )
            self.export_btn.setEnabled(True)
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Error de validación", f"Error durante validación: {e}"
            )
            return False

    def get_export_config(self) -> Dict[str, Any]:
        """Obtiene la configuración de exportación actual."""
        current_protocol_key = self.protocol_combo.currentData()
        protocol_config = self.PROTOCOL_CONFIGS.get(current_protocol_key, {})

        # Obtener puntos temporales seleccionados
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
