from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFileDialog, QApplication,
    QListWidget, QListWidgetItem, QAbstractItemView, QLineEdit
)

import sys
class ExportMarkersDialog(QDialog):
    def __init__(self, signals, comments, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export physiological markers")
        layout = QVBoxLayout()

        # Multi-signal selection
        layout.addWidget(QLabel("Select signal(s):"))
        self.signal_list = QListWidget()
        self.signal_list.addItems(signals)
        self.signal_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.signal_list)

        # Multi-marker selection
        layout.addWidget(QLabel("Select marker(s):"))
        self.marker_list = QListWidget()
        self.marker_list.addItems(["Mean", "Max", "Min", "Std"])
        self.marker_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.marker_list)

        # Filtering mode
        layout.addWidget(QLabel("Filter by:"))
        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItems(["Whole signal", "By event/comment", "By window"])
        layout.addWidget(self.filter_mode_combo)

        # Event/Comment selection
        self.event_label = QLabel("Select event/comment:")
        self.event_combo = QComboBox()
        self.event_combo.addItems(comments)
        layout.addWidget(self.event_label)
        layout.addWidget(self.event_combo)

        # Window selection (Start, End, Window Size)
        self.window_layout = QHBoxLayout()
        self.window_label1 = QLabel("Start (s):")
        self.window_start_spin = QSpinBox()
        self.window_start_spin.setMinimum(0)
        self.window_start_spin.setMaximum(86400)
        self.window_start_spin.setValue(0)

        self.window_label2 = QLabel("End (s):")
        self.window_end_spin = QSpinBox()
        self.window_end_spin.setMinimum(0)
        self.window_end_spin.setMaximum(86400)
        self.window_end_spin.setValue(0)  # Será seteado por defecto después

        self.window_label3 = QLabel("Window size (s):")
        self.window_size_spin = QSpinBox()
        self.window_size_spin.setMinimum(1)
        self.window_size_spin.setMaximum(3600)
        self.window_size_spin.setValue(60)

        self.window_layout.addWidget(self.window_label1)
        self.window_layout.addWidget(self.window_start_spin)
        self.window_layout.addWidget(self.window_label2)
        self.window_layout.addWidget(self.window_end_spin)
        self.window_layout.addWidget(self.window_label3)
        self.window_layout.addWidget(self.window_size_spin)
        layout.addLayout(self.window_layout)

        # Button box
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export")
        self.cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Inicialmente, oculta widgets
        self._update_visibility()

        # Connect
        self.export_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.filter_mode_combo.currentIndexChanged.connect(self._update_visibility)

    def _update_visibility(self):
        mode = self.filter_mode_combo.currentText()
        self.event_label.setVisible(mode == "By event/comment")
        self.event_combo.setVisible(mode == "By event/comment")
        is_window = (mode == "By window")
        self.window_label1.setVisible(is_window)
        self.window_start_spin.setVisible(is_window)
        self.window_label2.setVisible(is_window)
        self.window_end_spin.setVisible(is_window)
        self.window_label3.setVisible(is_window)
        self.window_size_spin.setVisible(is_window)

    def set_default_window_end(self, signal_duration):
        # This function can be called after dialog creation, to set default end.
        self.window_end_spin.setMaximum(int(signal_duration))
        self.window_end_spin.setValue(int(signal_duration))

    def get_selection(self):
        """
        Returns:
            signals: [str]
            markers: [str]
            filter_mode: str
            filter_value: 
                - comment:str
                - (start:int, end:int, win_size:int)
                - None
        """
        signals = [item.text() for item in self.signal_list.selectedItems()]
        markers = [item.text() for item in self.marker_list.selectedItems()]
        mode = self.filter_mode_combo.currentText()
        if mode == "By event/comment":
            return signals, markers, mode, self.event_combo.currentText()
        elif mode == "By window":
            return signals, markers, mode, (
                self.window_start_spin.value(),
                self.window_end_spin.value(),
                self.window_size_spin.value()
            )
        else:
            return signals, markers, mode, None


if __name__ == "__main__":
    import os

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from data.aditch_loader import AditchLoader

    app = QApplication(sys.argv)
    file_dialog = QFileDialog()
    file_path, _ = file_dialog.getOpenFileName(
        None,
        "Selecciona archivo .adicht para prueba",
        "",
        "Archivos adicht (*.adicht)"
    )
    if not file_path:
        print("No file selected.")
        sys.exit(0)

    loader = AditchLoader()
    loader.load(file_path)
    meta = loader.get_metadata()
    # Channel list (puedes usar [ch["name"] for ch in ...] si es necesario)
    signals = [ch for ch in meta.get("channels", [])]
    comments_raw = [EMS.text for EMS in loader.get_all_comments()]
    IMPORTANT_EVENTS = ["Tilt", "Stand", "Hyperventilation", "Valsalva"]
    filtered_comments = [c for c in comments_raw if any(evt in c for evt in IMPORTANT_EVENTS)]

    dlg = ExportMarkersDialog(signals, filtered_comments)

    if dlg.exec():
        selection = dlg.get_selection()
        print("Selección del usuario:")
        print("Signals:", selection[0])
        print("Markers:", selection[1])
        print("Modo filtro:", selection[2])
        print("Valor filtro:", selection[3])
    else:
        print("Cancelado por el usuario.")

    sys.exit(0)


"""
if __name__ == "__main__":
    import os

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from data.aditch_loader import AditchLoader
    from processing.marker_extractor import extract_markers, save_markers_to_csv

    app = QApplication(sys.argv)
    file_dialog = QFileDialog()
    file_path, _ = file_dialog.getOpenFileName(
        None,
        "Selecciona archivo .adicht para prueba",
        "",
        "Archivos adicht (*.adicht)"
    )
    if not file_path:
        print("No file selected.")
        sys.exit(0)

    loader = AditchLoader()
    loader.load(file_path)
    meta = loader.get_metadata()
    signals_names = [ch['name'] for ch in meta.get("channels", [])]

    signals_dict_full = {name: loader.get_signal(name) for name in signals_names}

    comments_raw = [EMS.text for EMS in loader.get_all_comments()]
    # Eventos importantes:
    IMPORTANT_EVENTS = ["Tilt", "Stand", "Hyperventilation", "Valsalva"]
    filtered_comments = [c for c in comments_raw if any(evt in c for evt in IMPORTANT_EVENTS)]


    comments_all = loader.get_all_comments()
    comment_intervals = {
        c.text: (c.start, c.end) for c in comments_all
        if any(evt in c.text for evt in IMPORTANT_EVENTS)
    }

    dlg = ExportMarkersDialog(signals_names, filtered_comments)


    if signals_names:
        main_sig = signals_dict_full[signals_names[0]]
        duration = float(main_sig.time[-1])
        dlg.set_default_window_end(duration)

    if dlg.exec():
        signals_sel, markers_sel, mode, filter_value = dlg.get_selection()
        print("Selección del usuario:")
        print("Signals:", signals_sel)
        print("Markers:", markers_sel)
        print("Modo filtro:", mode)
        print("Valor filtro:", filter_value)
        # Subset del dict de señales a las elegidas
        signals_dict = {k: signals_dict_full[k] for k in signals_sel}
        # Extrae marcadores
        if mode == "By event/comment":
            results = extract_markers(signals_dict, markers_sel, mode, filter_value, comment_intervals)
        else:
            results = extract_markers(signals_dict, markers_sel, mode, filter_value)
        # Guardar CSV
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Guardar resultados CSV",
            "",
            "CSV files (*.csv)"
        )
        if save_path:
            save_markers_to_csv(results, save_path)
            print(f"Archivo CSV guardado: {save_path}")
        else:
            print("Exportación cancelada por usuario.")
    else:
        print("Cancelado por el usuario.")

    sys.exit(0)
"""