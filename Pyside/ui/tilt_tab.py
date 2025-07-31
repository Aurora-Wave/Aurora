import numpy as np
import logging
from .utils.scroll_config import ScrollConfig
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QAbstractItemView,
    QSpinBox,
    QScrollBar,
    QSizePolicy,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from data.data_manager import DataManager
from processing.interval_extractor import extract_event_intervals
from processing.chunk_loader import ChunkLoader


class TiltTab(QWidget):
    """
    Tab to visualize tilt events (intervals) across all channels.
    Loads a full 10-minute context window but displays a user-defined chunk size.
    Enables panning across the full context, zoom disabled, synchronized across channels.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Setup logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Data attributes
        self.data_manager: DataManager = None
        self.file_path: str = None
        self.channel_names: list[str] = []
        self.intervals: list[dict] = []
        self._selected_idx: int | None = None

        # Visualization parameters
        self._chunk_size: float = 60.0  # seconds
        self._context_start: float = 0.0
        self._context_end: float = 0.0
        self._offset: float = 0.0

        # ChunkLoader for efficient data loading
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self._update_chunk)

        # Store plot curves for efficient updates
        self.plot_curves = {}

        # UI setup
        self._setup_ui()

    def _setup_ui(self):
        # Interval table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Event", "Event(s)", "End(s)", "Duration(s)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellClicked.connect(self._on_row_selected)

        # Controls: filter, chunk size and scrollbar
        self.filter_box = QLineEdit(placeholderText="Filter events...")
        self.filter_box.textChanged.connect(self._apply_filter)

        self.chunk_spin = QSpinBox()
        self.chunk_spin.setSuffix(" s")
        self.chunk_spin.setRange(1, 600)
        self.chunk_spin.setValue(int(self._chunk_size))
        self.chunk_spin.valueChanged.connect(self._on_chunk_changed)

        # ──────────── Improved Horizontal ScrollBar ────────────
        self.scrollbar = QScrollBar(Qt.Horizontal)
        # make it expand horizontally
        self.scrollbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # give it a visible height
        self.scrollbar.setMinimumHeight(20)
        self.scrollbar.setMaximumHeight(20)
        self.scrollbar.valueChanged.connect(self._on_scroll_changed)
        # Configurar tamaño mínimo para la barra de desplazamiento
        self.scrollbar.setMinimumWidth(300)  # Ancho mínimo de 300px
        self.scrollbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Search:"))
        ctrl.addWidget(self.filter_box)
        ctrl.addStretch()
        ctrl.addWidget(QLabel("Chunk:"))
        ctrl.addWidget(self.chunk_spin)

        # Agregar la barra de scroll con mayor proporción del espacio
        ctrl.addWidget(QLabel("Navigate:"))
        ctrl.addWidget(self.scrollbar, 1)  # Factor de stretch 1 para expandir

        # Plot area
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plots: dict[str, pg.PlotItem] = {}

        # Main layout
        layout = QVBoxLayout(self)
        layout.addLayout(ctrl)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.plot_widget, stretch=3)

    def update_tilt_tab(self, dm: DataManager, path: str):
        # Initialize data manager and path
        self.data_manager = dm
        self.file_path = path

        # Determine channels: from metadata + cache (to include HR_gen)
        meta = set(dm.get_available_channels(path))
        cache = {k.split("|")[0] for k in dm._files[path]["signal_cache"]}
        available = meta.union(cache)
        order = ["ECG", "HR_gen", "FBP", "Valsalva"]
        self.channel_names = [ch for ch in order if ch in available]

        # Extract intervals (events)
        signals = [dm.get_trace(path, ch) for ch in self.channel_names]
        self.intervals = extract_event_intervals(signals)
        self._selected_idx = None

        # Populate table of events
        self._populate_table()

        # Set context window to first 10 minutes (or less)
        max_durations = [max(dm.get_trace(path, ch).time) for ch in self.channel_names]
        self._context_start = 0.0
        self._context_end = min(max(max_durations), self._context_start + 600.0)

        # Configure scrollbar range and render initial chunk
        self._setup_scroll()
        # Initial chunk load
        self._request_chunk()

    def _populate_table(self):
        self.table.setRowCount(len(self.intervals))
        for i, iv in enumerate(self.intervals):
            t0 = iv.get("t_baseline", iv.get("t_evento", 0.0))
            te = iv.get("t_evento", 0.0)
            t1 = iv.get("t_recovery", iv.get("t_tilt_down", te))
            dur = t1 - te  # Duración desde evento hasta fin
            items = [iv.get("evento", ""), te, t1, dur]
            for j, val in enumerate(items):
                txt = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
                self.table.setItem(i, j, QTableWidgetItem(txt))
        self._apply_filter()

    def _apply_filter(self):
        term = self.filter_box.text().lower()
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            hide = term not in (it.text().lower() if it else "")
            self.table.setRowHidden(r, hide)

    def _setup_scroll(self):
        total = self._context_end - self._context_start
        max_scroll = int(max(total - self._chunk_size, 0))

        # Desconectar temporalmente para evitar llamadas recursivas
        try:
            self.scrollbar.valueChanged.disconnect(self._on_scroll_changed)
        except TypeError:
            # La señal no estaba conectada, ignorar
            pass

        self.scrollbar.setRange(0, max_scroll)
        self.scrollbar.setPageStep(int(self._chunk_size))
        # Usar el offset actual en lugar de resetear a 0
        target_value = int(min(max(self._offset, 0), max_scroll))
        self.scrollbar.setValue(target_value)

        # Reconectar la señal
        self.scrollbar.valueChanged.connect(self._on_scroll_changed)

    def _on_chunk_changed(self, val):
        self._chunk_size = float(val)
        self._setup_scroll()
        self._request_chunk()

    def _on_scroll_changed(self, val):
        self._offset = float(val)
        self._request_chunk()

    def _request_chunk(self):
        """Request chunk data efficiently using ChunkLoader."""
        if not self.data_manager or not self.file_path or not self.channel_names:
            return

        start_time = self._context_start + self._offset
        self.chunk_loader.request_chunk(
            data_manager=self.data_manager,
            file_path=self.file_path,
            channel_names=self.channel_names,
            start_sec=start_time,
            duration_sec=self._chunk_size,
        )

    def _update_chunk(self, start_sec, end_sec, data_dict):
        """Update plots with chunk data efficiently."""
        # Clear plots only if needed (first time or channel count changed)
        if len(self.plots) != len(self.channel_names):
            self.plot_widget.clear()
            self.plots.clear()
            self.plot_curves.clear()
            self._setup_plots()

        # Update each channel's data
        for idx, ch in enumerate(self.channel_names):
            if idx >= len(self.plots):
                continue

            plot_item = self.plots[ch]
            chunk_data = data_dict.get(ch, np.array([]))

            if chunk_data.size == 0:
                continue

            # Get signal info for time axis
            sig = self.data_manager.get_trace(self.file_path, ch)
            fs = sig.fs

            # Create time array
            t = np.arange(len(chunk_data)) / fs + start_sec

            # Downsample if too many points
            max_pts = 5000
            if len(chunk_data) > max_pts:
                step = int(np.ceil(len(chunk_data) / max_pts))
                t = t[::step]
                chunk_data = chunk_data[::step]

            # Update or create curve
            if ch in self.plot_curves:
                self.plot_curves[ch].setData(t, chunk_data)
            else:
                self.plot_curves[ch] = plot_item.plot(
                    t, chunk_data, pen=pg.mkPen("y", width=1)
                )

            # Set ranges
            plot_item.setXRange(start_sec, end_sec, padding=0)
            if chunk_data.size > 0:
                finite_data = chunk_data[np.isfinite(chunk_data)]
                if finite_data.size > 0:
                    plot_item.setYRange(
                        float(finite_data.min()), float(finite_data.max())
                    )

    def _setup_plots(self):
        """Setup plot structure efficiently."""
        for idx, ch in enumerate(self.channel_names):
            p = self.plot_widget.addPlot(row=idx, col=0, title=ch)
            vb = p.getViewBox()
            vb.setMouseMode(pg.ViewBox.PanMode)
            vb.setMouseEnabled(x=True, y=False)
            vb.setLimits(xMin=self._context_start, xMax=self._context_end)

            # Agregar soporte para scroll wheel sincronizado
            def create_wheel_handler(viewbox, channel_name):
                def wheel_handler(ev):
                    # Verificar que el scrollbar esté disponible
                    if not hasattr(self, "scrollbar") or self.scrollbar is None:
                        ev.ignore()
                        return

                    # Usar configuración centralizada
                    delta = ev.delta()
                    scroll_amount = ScrollConfig.get_scroll_amount(delta, "tilt")

                    # Verificar umbral mínimo
                    if not ScrollConfig.should_scroll(scroll_amount):
                        ev.accept()
                        return

                    # Obtener offset actual
                    current_offset = self._offset
                    new_offset = current_offset + scroll_amount

                    # Aplicar límites del contexto
                    max_offset = max(
                        self._context_end - self._context_start - self._chunk_size, 0
                    )
                    new_offset = max(0, min(max_offset, new_offset))

                    # Solo actualizar si hay cambio significativo
                    if abs(new_offset - current_offset) > 0.1:
                        self._offset = new_offset
                        # Actualizar scrollbar para mantener sincronización
                        try:
                            self.scrollbar.valueChanged.disconnect(
                                self._on_scroll_changed
                            )
                        except TypeError:
                            pass
                        self.scrollbar.setValue(int(new_offset))
                        self.scrollbar.valueChanged.connect(self._on_scroll_changed)
                        # Solicitar nuevo chunk
                        self._request_chunk()

                    ev.accept()

                return wheel_handler

            # Asignar el handler de wheel a cada ViewBox
            vb.wheelEvent = create_wheel_handler(vb, ch)
            self.plots[ch] = p

    def _update_plot_limits(self):
        """Update X limits for all plots based on current context."""
        for plot_item in self.plots.values():
            vb = plot_item.getViewBox()
            vb.setLimits(xMin=self._context_start, xMax=self._context_end)

    def _on_row_selected(self, row, col):
        self._selected_idx = row
        iv = self.intervals[row]
        evt = iv.get("t_evento", 0)
        end = iv.get("t_recovery", iv.get("t_tilt_down", evt))

        self.logger.debug(f"Selected row {row}, event at {evt:.2f}s, end at {end:.2f}s")

        # Calcular duración real del test
        test_duration = end - evt
        self.logger.debug(f"Test duration: {test_duration:.2f}s")

        if test_duration > 0:
            # Definir margen mínimo
            margin = min(10.0, test_duration * 0.05)  # 5% del test o máximo 10s
            self._context_start = max(evt - margin, 0)
            self._context_end = end + margin

            # Desconectar temporalmente para evitar llamadas recursivas
            try:
                self.chunk_spin.valueChanged.disconnect(self._on_chunk_changed)
            except TypeError:
                # La señal no estaba conectada, ignorar
                pass

            # Lógica de chunk_size según duración del test
            if test_duration < 60.0:
                # Tests cortos: mostrar completo con márgenes
                self._chunk_size = test_duration + (2 * margin)
                self.chunk_spin.setValue(int(self._chunk_size))
                self._offset = 0  # Mostrar desde el inicio
                self.logger.debug(
                    f"Short test: showing complete duration {self._chunk_size:.2f}s"
                )
            else:
                # Tests largos: ventana por defecto de 60s, posicionada al inicio del test
                self._chunk_size = 60.0
                self.chunk_spin.setValue(60)
                self._offset = 0  # Posicionar al inicio del test
                self.logger.debug(f"Long test: using 60s window at start")

            # Reconectar la señal
            self.chunk_spin.valueChanged.connect(self._on_chunk_changed)

        else:
            # Fallback: ventana de 2 minutos alrededor del evento
            self._context_start = max(evt - 60, 0)
            self._context_end = evt + 60
            self._offset = 0

        self.logger.debug(
            f"Context: {self._context_start:.2f} - {self._context_end:.2f}, "
            f"Chunk size: {self._chunk_size:.2f}, Offset: {self._offset:.2f}"
        )

        self._update_plot_limits()  # Actualizar límites de plots existentes
        self._setup_scroll()
        self._request_chunk()
