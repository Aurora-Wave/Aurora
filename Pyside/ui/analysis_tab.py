import numpy as np
import pywt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
)
import pyqtgraph as pg
from Pyside.processing.chunk_loader import ChunkLoader
from PySide6.QtCore import Qt
from Pyside.core import get_user_logger, get_current_session
from Pyside.core.config_manager import get_config_manager
from Pyside.core.channel_units import get_channel_label_with_unit
from Pyside.ui.utils.ecg_debug_tracker import ECGDebugTracker
from Pyside.ui.utils.plot_factory import PlotFactory, SignalProcessor
from Pyside.ui.managers.comment_marker_manager import CommentMarkerManager


# Use SignalProcessor.sanitize_signal_data instead of local function
sanitize_for_plot = SignalProcessor.sanitize_signal_data


class AnalysisTab(QWidget):
    """
    AnalysisTab: chunk-based ECG/HR visualization and interactive R-peak editing.
    Allows adding, deleting, and moving R-peaks with local HR update.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.config_manager = get_config_manager()
        self.main_window = parent  # Reference to MainWindow for parameter synchronization
        self.logger.info(f"=== ANALYSISTAB INIT DEBUG ===")
        self.logger.info(f"AnalysisTab created with parent: {parent}")
        self.logger.info(f"main_window set to: {self.main_window}")
        self.logger.info(f"main_window type: {type(self.main_window)}")
        
        # ECG Debug Tracker for monitoring signal consistency
        self.ecg_debug_tracker = ECGDebugTracker("AnalysisTab.ECGDebug")
        
        # Comment marker manager for unified comment display
        self.comment_marker_manager = CommentMarkerManager("AnalysisTab")
        
        self.data_manager = None
        self.file_path = None
        self.fs = 1.0
        self.duration = 0.0
        
        # Get user's saved analysis settings (highest priority)
        analysis_settings = self.config_manager.get_analysis_settings()
        ui_limits = self.config_manager.get_ui_limits()
        self._max_lvl = ui_limits.get("max_wavelet_level", 6)

        # Initialize from user's analysis settings (these are the ones that persist)
        self.wavelet = analysis_settings.get("wavelet", "haar")
        self.level = analysis_settings.get("level", 4)
        self.min_rr_sec = analysis_settings.get("min_rr_sec", 0.6)
        self.chunk_size = 60  # UI-specific default
        self.start_time = 0

        # Dragging state
        self._dragged_peak_idx = None
        self._is_dragging = False

        # Comment markers tracking

        # Layout
        main = QVBoxLayout(self)
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Wavelet:"))
        self.wavelet_cb = QComboBox()
        self.wavelet_cb.addItems(["haar", "db4", "db5", "sym4"])
        self.wavelet_cb.setCurrentText(self.wavelet)
        self.wavelet_cb.currentTextChanged.connect(self._update)
        ctrl.addWidget(self.wavelet_cb)

        ctrl.addWidget(QLabel("Level:"))
        self.level_sb = QSpinBox()
        self.level_sb.setRange(1, 6)
        self.level_sb.setValue(self.level)
        self.level_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.level_sb)

        ctrl.addWidget(QLabel("Min R-R Interval (s):"))
        self.dist_sb = QDoubleSpinBox()
        rr_range = ui_limits.get("min_rr_range", [0.1, 2.0])
        self.dist_sb.setRange(rr_range[0], rr_range[1])
        self.dist_sb.setSingleStep(0.1)
        self.dist_sb.setValue(self.min_rr_sec)
        self.dist_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.dist_sb)

        ctrl.addWidget(QLabel("Chunk (s):"))
        self.chunk_sb = QSpinBox()
        self.chunk_sb.setRange(
            ui_limits.get("min_chunk_size", 1), 
            ui_limits.get("max_chunk_size", 600)
        )
        self.chunk_sb.setValue(self.chunk_size)
        self.chunk_sb.valueChanged.connect(self._on_chunk_changed)
        ctrl.addWidget(self.chunk_sb)

        ctrl.addWidget(QLabel("Start (s):"))
        self.start_sb = QSpinBox()
        self.start_sb.setRange(0, 0)
        self.start_sb.setValue(self.start_time)
        self.start_sb.valueChanged.connect(self._update)
        ctrl.addWidget(self.start_sb)

        self.prev_btn = QPushButton("←")
        self.prev_btn.clicked.connect(self._go_previous_chunk)
        ctrl.addWidget(self.prev_btn)
        self.next_btn = QPushButton("→")
        self.next_btn.clicked.connect(self._go_next_chunk)
        ctrl.addWidget(self.next_btn)

        main.addLayout(ctrl)

        # Create plots using PlotFactory for consistency
        self.plots, plot_dict = PlotFactory.create_analysis_plot_grid()
        self.ecg_plot = plot_dict['ecg']
        self.hr_plot = plot_dict['hr']
        self.wave_plot = plot_dict['wavelet']

        
        # Link HR plot to ECG plot for synchronized panning
        self.hr_plot.setXLink(self.ecg_plot)
        
        main.addWidget(self.plots)

        self.ecg_plot.scene().sigMouseClicked.connect(self._on_ecg_click)

        self._last_chunk_start = 0
        self._last_chunk_len = 0
        self._last_peaks = None
        self._last_ecg_chunk = None

    def update_analysis_tab(self, data_manager, file_path):
        self.logger.info(f"Updating AnalysisTab for file: {file_path}")

        # Reset ECG debug tracker for new file
        self.ecg_debug_tracker.reset()
        
        self.data_manager = data_manager
        self.file_path = file_path
        ecg = self.data_manager.get_trace(file_path, "ECG")
        self.fs = ecg.fs
        length = len(ecg.data)
        self.duration = length / self.fs

        if self.level > self._max_lvl:
            self.level = self._max_lvl
        self.level_sb.setRange(1, self._max_lvl)
        self.level_sb.setValue(self.level)

        self.chunk_sb.setRange(1, int(self.duration))
        self.chunk_sb.setValue(min(self.chunk_size, int(self.duration)))
        self.start_sb.setRange(0, int(self.duration - self.chunk_sb.value()))

        # Extract and add comment markers
        self._add_comment_markers()

        self._update()

    def _on_chunk_changed(self, val):
        self.chunk_size = val
        self.start_sb.setRange(0, int(self.duration - self.chunk_size))
        self._update()

    def _go_previous_chunk(self):
        self.start_sb.setValue(max(0, self.start_sb.value() - self.chunk_size))

    def _go_next_chunk(self):
        max_start = int(self.duration - self.chunk_size)
        self.start_sb.setValue(min(max_start, self.start_sb.value() + self.chunk_size))

    def _update(self):
        wav = self.wavelet_cb.currentText()
        lvl = self.level_sb.value()
        md = self.dist_sb.value()
        chunk = self.chunk_sb.value()
        start = self.start_sb.value()

        # ECG chunk
        ecg_chunk = ChunkLoader.get_chunk(
            self.data_manager, self.file_path, ["ECG"], start, chunk
        )
        t_ecg = np.arange(len(ecg_chunk)) / self.fs + start
        y_ecg = sanitize_for_plot(ecg_chunk)
        
        # Debug: Track ECG signal consistency
        current_parameters = {
            "wavelet": wav,
            "level": lvl,
            "min_rr_sec": md,
            "chunk_size": chunk,
            "start_time": start
        }
        
        # Compare with previous state (if available)
        self.ecg_debug_tracker.compare_ecg_state(
            ecg_chunk, current_parameters, start, chunk
        )
        
        # Capture current state for next comparison
        self.ecg_debug_tracker.capture_ecg_state(
            ecg_chunk, current_parameters, start, chunk
        )

        # HR_gen global (full signal)
        hr_sig = self.data_manager.get_trace(
            self.file_path, "HR_GEN", wavelet=wav, swt_level=lvl, min_rr_sec=md
        )
        hr_t = hr_sig.time
        hr_v = hr_sig.data

        # HR_gen chunk
        mask = (hr_t >= start) & (hr_t < start + chunk)
        hr_t_chunk = hr_t[mask]
        hr_v_chunk = hr_v[mask]
        y_hr = sanitize_for_plot(hr_v_chunk)

        # Detected R-peaks (global indices)
        r_peaks = hr_sig.r_peaks
        peaks_in_chunk = r_peaks[
            (r_peaks >= int(start * self.fs))
            & (r_peaks < int((start + chunk) * self.fs))
        ]
        t_peaks = peaks_in_chunk / self.fs
        y_peaks = ecg_chunk[(peaks_in_chunk - int(start * self.fs)).astype(int)]

        # Plot ECG with peaks
        self.ecg_plot.clear()
        self.ecg_plot.plot(t_ecg, y_ecg, pen="b")

        # Get HR values at each peak in the current chunk
        hr_peaks = hr_sig.data[peaks_in_chunk.astype(int)]
        nan_mask = ~np.isfinite(hr_peaks)
        valid_mask = ~nan_mask

        # Plot valid peaks (HR finite): RED
        if np.any(valid_mask):
            self.ecg_plot.plot(
                t_peaks[valid_mask],
                y_peaks[valid_mask],
                pen=None,
                symbol="o",
                symbolBrush="r",
                symbolSize=10,
            )
        # Plot NaN peaks (HR NaN or inf): GREEN
        if np.any(nan_mask):
            self.ecg_plot.plot(
                t_peaks[nan_mask],
                y_peaks[nan_mask],
                pen=None,
                symbol="o",
                symbolBrush="g",
                symbolSize=10,
            )

        self._last_chunk_start = start
        self._last_chunk_len = chunk
        self._last_peaks = peaks_in_chunk
        self._last_ecg_chunk = ecg_chunk

        # Plot HR_gen
        self.hr_plot.clear()
        if hr_v_chunk.size and np.any(np.isfinite(hr_v_chunk)):
            hr_min = np.nanmin(hr_v_chunk) - 10
            hr_max = np.nanmax(hr_v_chunk) + 10
            if not np.isfinite(hr_min) or not np.isfinite(hr_max) or hr_min == hr_max:
                hr_min, hr_max = 20, 200  # fallback for physiological HR
            self.hr_plot.plot(hr_t_chunk, y_hr, pen="g")
            self.hr_plot.setYRange(hr_min, hr_max)
        else:
            self.hr_plot.setYRange(20, 200)

        # Wavelet plot
        try:
            _, psi, x = pywt.Wavelet(wav).wavefun(level=lvl)
        except Exception:
            psi, x = pywt.Wavelet(wav).wavefun()[:2]
        psi = sanitize_for_plot(psi)
        self.wave_plot.clear()
        self.wave_plot.plot(x, psi, pen="m")

        # Update comment markers for current chunk
        self._add_comment_markers()
        
        # Notify other tabs about HR parameter changes
        try:
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.update_viewer_tabs_hr_params()
        except Exception as e:
            self.logger.error(f"Error notifying other tabs of HR parameter changes: {e}")

    # Mouse interaction: click-inicio y click-destino
    def _on_ecg_click(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)

        self.logger.debug(
            f"Clicked at {t_click:.2f}s (index={global_idx}), drag mode={self._is_dragging}"
        )

        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        tolerance = int(0.05 * fs)
        idx_near = np.where(np.abs(hr_sig.r_peaks - global_idx) <= tolerance)[0]

        if event.button() == Qt.LeftButton:
            if self._is_dragging and self._dragged_peak_idx is not None:
                # Click-destino: mueve el peak seleccionado
                window = int(0.1 * fs)
                raw_ecg = self.data_manager.get_trace(self.file_path, "ECG").data
                search_start = max(global_idx - window, 0)
                search_end = min(global_idx + window, len(raw_ecg))
                local_max_idx = (
                    np.argmax(np.abs(raw_ecg[search_start:search_end])) + search_start
                )
                hr_sig.update_peak(self._dragged_peak_idx, local_max_idx)
                hr_sig._data = hr_sig._data.copy()
                self._dragged_peak_idx = None
                self._is_dragging = False
                self._update()
                self.data_manager.update_hr_cache(
                    self.file_path,
                    hr_sig,
                    wavelet=self.wavelet_cb.currentText(),
                    swt_level=self.level_sb.value(),
                    min_rr_sec=self.dist_sb.value(),
                )
                
                # Notify other tabs about the peak changes
                self.logger.info(f"=== PEAK MOVEMENT DEBUG ===")
                self.logger.info(f"main_window exists: {hasattr(self, 'main_window')}")
                self.logger.info(f"main_window value: {getattr(self, 'main_window', 'NOT_SET')}")
                
                try:
                    if hasattr(self, 'main_window') and self.main_window:
                        self.logger.info("Calling main_window.update_viewer_tabs_hr_params() for peak movement")
                        self.main_window.update_viewer_tabs_hr_params(force_cache_refresh=True)
                        self.logger.info("Successfully notified other tabs about peak movement")
                    else:
                        self.logger.warning("main_window not available - cannot notify other tabs about peak movement")
                except Exception as e:
                    self.logger.error(f"Error notifying other tabs about peak movement: {e}", exc_info=True)
                    
                self.logger.debug("Updated HR_GEN cache after moving peak.")

            elif idx_near.size:
                # Click-inicio: seleccionar peak para mover
                self._dragged_peak_idx = idx_near[0]
                self._is_dragging = True
            else:
                # Agregar peak
                self._handle_add_peak(event)
        elif event.button() == Qt.RightButton:
            self._handle_delete_peak(event)

    def _handle_add_peak(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)
        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        # Only add if not too close to another peak
        tolerance = int(0.05 * fs)
        if np.all(np.abs(hr_sig.r_peaks - global_idx) > tolerance):
            window = int(0.1 * fs)
            raw_ecg = self.data_manager.get_trace(self.file_path, "ECG").data
            search_start = max(global_idx - window, 0)
            search_end = min(global_idx + window, len(raw_ecg))
            local_max_idx = (
                np.argmax(np.abs(raw_ecg[search_start:search_end])) + search_start
            )

            self.logger.info(f"Adding new R-peak at index: {local_max_idx}")
            self.session.log_action(f"R-peak added at {local_max_idx}", self.logger)

            hr_sig.r_peaks = np.sort(np.append(hr_sig.r_peaks, local_max_idx))
            # Update only the segments around the new peak
            i = np.searchsorted(hr_sig.r_peaks, local_max_idx)
            if i > 0:
                hr_sig._update_hr_segment(i - 1)
            if i < len(hr_sig.r_peaks) - 1:
                hr_sig._update_hr_segment(i)
            hr_sig._data = hr_sig._data.copy()
            self._update()
            self.data_manager.update_hr_cache(
                self.file_path,
                hr_sig,
                wavelet=self.wavelet_cb.currentText(),
                swt_level=self.level_sb.value(),
                min_rr_sec=self.dist_sb.value(),
            )
            
            # Notify other tabs about the peak changes
            self.logger.info(f"=== PEAK ADDITION DEBUG ===")
            self.logger.info(f"main_window exists: {hasattr(self, 'main_window')}")
            self.logger.info(f"main_window value: {getattr(self, 'main_window', 'NOT_SET')}")
            
            try:
                if hasattr(self, 'main_window') and self.main_window:
                    self.logger.info("Calling main_window.update_viewer_tabs_hr_params() for peak addition")
                    self.main_window.update_viewer_tabs_hr_params()
                    self.logger.info("Successfully notified other tabs about peak addition")
                else:
                    self.logger.warning("main_window not available - cannot notify other tabs about peak addition")
            except Exception as e:
                self.logger.error(f"Error notifying other tabs about peak addition: {e}", exc_info=True)
                
        self.logger.debug("Updated HR_GEN cache after adding peak.")

    def _handle_delete_peak(self, event):
        pos = event.scenePos()
        vb = self.ecg_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        t_click = mouse_point.x()
        fs = self.fs
        global_idx = int(t_click * fs)
        hr_sig = self.data_manager.get_trace(
            self.file_path,
            "HR_GEN",
            wavelet=self.wavelet_cb.currentText(),
            swt_level=self.level_sb.value(),
            min_rr_sec=self.dist_sb.value(),
        )
        tolerance = int(0.05 * fs)
        idx_near = np.where(np.abs(hr_sig.r_peaks - global_idx) <= tolerance)[0]
        if idx_near.size:
            peak_idx = idx_near[0]
            deleted_peak = hr_sig.r_peaks[idx_near[0]]
            hr_sig.r_peaks = np.delete(hr_sig.r_peaks, peak_idx)

            self.logger.info(f"Deleting R-peak at index: {deleted_peak}")
            self.session.log_action(f"R-peak deleted at {deleted_peak}", self.logger)

            # Update HR around removed peak
            if peak_idx > 0:
                hr_sig._update_hr_segment(peak_idx - 1)
            if peak_idx < len(hr_sig.r_peaks) - 1:
                hr_sig._update_hr_segment(peak_idx)
            hr_sig._data = hr_sig._data.copy()
            self._update()
            self.data_manager.update_hr_cache(
                self.file_path,
                hr_sig,
                wavelet=self.wavelet_cb.currentText(),
                swt_level=self.level_sb.value(),
                min_rr_sec=self.dist_sb.value(),
            )
            
            # Notify other tabs about the peak changes
            self.logger.info(f"=== PEAK DELETION DEBUG ===")
            self.logger.info(f"main_window exists: {hasattr(self, 'main_window')}")
            self.logger.info(f"main_window value: {getattr(self, 'main_window', 'NOT_SET')}")
            
            try:
                if hasattr(self, 'main_window') and self.main_window:
                    self.logger.info("Calling main_window.update_viewer_tabs_hr_params() for peak deletion")
                    self.main_window.update_viewer_tabs_hr_params()
                    self.logger.info("Successfully notified other tabs about peak deletion")
                else:
                    self.logger.warning("main_window not available - cannot notify other tabs about peak deletion")
            except Exception as e:
                self.logger.error(f"Error notifying other tabs about peak deletion: {e}", exc_info=True)
                
            self.logger.debug("Updated HR_GEN cache after deleting peak.")

    def get_hrgen_params(self):
        return {
            "wavelet": self.wavelet_cb.currentText(),
            "level": self.level_sb.value(),
            "min_rr_sec": self.dist_sb.value(),
        }

    def _add_comment_markers(self):
        """Add comment markers using the unified CommentMarkerManager."""
        try:
            # Get ECG trace to extract intervals
            ecg = self.data_manager.get_trace(self.file_path, "ECG")
            from processing.interval_extractor import extract_event_intervals
            intervals = extract_event_intervals([ecg])

            # Get current chunk range
            start_time = self.start_sb.value()
            end_time = start_time + self.chunk_sb.value()

            # Add markers to ECG and HR plots only (not wavelet plot due to different scale)
            plots_to_mark = [
                (self.ecg_plot, "ecg_plot"),
                (self.hr_plot, "hr_plot")
            ]
            
            for plot, plot_id in plots_to_mark:
                self.comment_marker_manager.add_markers_to_single_plot(
                    plot, intervals, start_time, end_time, plot_id
                )

            self.logger.debug(f"Added comment markers for range {start_time:.1f}-{end_time:.1f}s")

        except Exception as e:
            self.logger.warning(f"Could not add comment markers: {e}")
