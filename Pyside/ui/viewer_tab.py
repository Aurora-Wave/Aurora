import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollBar,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QScrollArea,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from Pyside.ui.widgets.selectable_viewbox import SelectableViewBox
from Pyside.processing.chunk_loader import ChunkLoader
from Pyside.core.channel_units import get_channel_label_with_unit
from Pyside.core import get_user_logger
from Pyside.ui.managers.comment_marker_manager import CommentMarkerManager


class ViewerTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.logger = get_user_logger(self.__class__.__name__)
        self.plots = []
        self.scrollbar = None
        self.chunk_size_spinbox = None
        self._regions = []
        self.file_path = None
        self.chunk_size = 60
        self.hr_params = {}
        self.comment_markers = {}  # Track comment markers per plot for cleanup
        
        # Unified comment marker management
        self.marker_manager = CommentMarkerManager("ViewerTab")

        # Layouts
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)

        # Plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(5)
        self.scroll_area.setWidget(self.scroll_content)

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.controls_layout)
        main_layout.addWidget(self.scroll_area)
        self.setLayout(main_layout)

    def load_data(self, file_path, chunk_size, target_signals, hr_params=None):
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.hr_params = hr_params or {}
        self.target_signals = target_signals

        # Calculate global Y-axis ranges for each signal across the entire signal length
        dm = self.main_window.data_manager
        self.y_ranges = {}
        for signal_name in self.target_signals:
            try:
                # Get the full signal trace for global min/max calculation
                # Only apply HR parameters to HR_GEN signals
                if signal_name.upper() == "HR_GEN":
                    sig = dm.get_trace(self.file_path, signal_name, **self.hr_params)
                else:
                    sig = dm.get_trace(self.file_path, signal_name)
                
                # Calculate global min/max across entire signal, excluding NaN values
                y_data = np.asarray(sig.data)
                y_valid = y_data[np.isfinite(y_data)]  # Remove NaN and inf values
                
                if len(y_valid) > 0:
                    y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                    
                    # Add small padding (5%) for better visualization
                    if y_min != y_max:
                        y_range = y_max - y_min
                        padding = y_range * 0.05
                        y_min -= padding
                        y_max += padding
                    else:
                        # Handle constant signals
                        if y_min == 0:
                            y_min, y_max = -0.1, 0.1
                        else:
                            padding = abs(y_min) * 0.1
                            y_min -= padding
                            y_max += padding
                    
                    self.logger.debug(f"Global Y-range for {signal_name}: {y_min:.3f} to {y_max:.3f} (from {len(y_valid)} valid samples)")
                else:
                    # Fallback for signals with no valid data
                    y_min, y_max = -1.0, 1.0
                    self.logger.warning(f"No valid data for {signal_name}, using default range")
                
                self.y_ranges[signal_name] = (y_min, y_max)
                
            except Exception as e:
                # Robust fallback for any errors during range calculation
                self.logger.error(f"Error calculating Y-range for {signal_name}: {e}")
                self.y_ranges[signal_name] = (-1.0, 1.0)
        self.setup_plots(self.target_signals)
        self._init_chunk_controls()
        self._setup_chunk_loader()

    def setup_plots(self, target_signals):
        self.clear_plots()
        self.plots = []
        self._regions = []
        self.comment_markers = {}  # Reset comment markers dictionary
        for i, signal_name in enumerate(target_signals):
            vb = SelectableViewBox(self, i)
            plot = pg.PlotWidget(viewBox=vb)
            plot.setMinimumHeight(200)
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", get_channel_label_with_unit(signal_name))
            plot.setMouseEnabled(x=False, y=False)
            curve = plot.plot([], [], pen="y")
            plot.curve = curve
            self.scroll_layout.addWidget(plot)
            self.plots.append(plot)
            self._regions.append(None)
            # Initialize empty marker list for this plot
            self.comment_markers[plot] = []

    def clear_plots(self):
        # Clear comment markers first
        self._clear_comment_markers()

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def _init_chunk_controls(self):
        # Remove previous controls if they exist
        if self.chunk_size_spinbox:
            self.controls_layout.removeWidget(self.chunk_size_spinbox)
            self.chunk_size_spinbox.deleteLater()
            self.chunk_size_spinbox = None
        if self.scrollbar:
            self.controls_layout.removeWidget(self.scrollbar)
            self.scrollbar.deleteLater()
            self.scrollbar = None

        # Chunk size spinbox
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(1)
        self.chunk_size_spinbox.setMaximum(3600)
        self.chunk_size_spinbox.setValue(self.chunk_size)
        self.chunk_size_spinbox.setSuffix(" s")
        self.chunk_size_spinbox.valueChanged.connect(self.on_chunk_size_changed)
        self.controls_layout.addWidget(QLabel("Chunk size:"))
        self.controls_layout.addWidget(self.chunk_size_spinbox)

        # Horizontal scrollbar for navigation
        self.scrollbar = QScrollBar()
        self.scrollbar.setOrientation(Qt.Horizontal)
        self.scrollbar.setMinimumHeight(20)  # Reducir de 35 a 20px
        self.scrollbar.setMaximumHeight(20)  # Reducir de 35 a 20px
        self.scrollbar.setStyleSheet(
            "QScrollBar {height: 20px;}"
        )  # Reducir de 35 a 20px
        dm = self.main_window.data_manager
        durations = []
        for ch in self.target_signals:
            sig = dm.get_trace(self.file_path, ch)
            durations.append(len(sig.data) / sig.fs)
        min_duration = int(min(durations)) if durations else 1
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.scrollbar.setPageStep(1)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.setValue(0)
        self.scrollbar.valueChanged.connect(self.request_chunk)
        self.controls_layout.addWidget(self.scrollbar)

        # Add comment markers after setting up scrollbar
        self._add_comment_markers()

    def _setup_chunk_loader(self):
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self.update_chunk)
        self.request_chunk(0)

    def request_chunk(self, value):
        start = int(value)
        dm = self.main_window.data_manager
        self.chunk_loader.request_chunk(
            data_manager=dm,
            file_path=self.file_path,
            channel_names=self.target_signals,
            start_sec=start,
            duration_sec=self.chunk_size,
        )

    def update_chunk(self, start, end, data_dict):
        for i, signal_name in enumerate(self.target_signals):
            p = self.plots[i]
            # Only use HR parameters for HR_GEN signals
            if signal_name.upper() == "HR_GEN":
                sig = self.main_window.data_manager.get_trace(
                    self.file_path, signal_name, **self.hr_params
                )
            else:
                # Raw signals should never use HR parameters
                sig = self.main_window.data_manager.get_trace(
                    self.file_path, signal_name
                )
            fs = sig.fs
            expected_len = int(self.chunk_size * fs)
            start_idx = int(start * fs)
            end_idx = int(end * fs)
            y = sig.data[start_idx:end_idx]
            y = np.asarray(y)
            if not np.all(np.isfinite(y)):
                y = np.nan_to_num(y, nan=0.0, posinf=1e6, neginf=-1e6)
            if np.abs(y).max() > 1e6:
                y = np.clip(y, -1e6, 1e6)
            if len(y) < expected_len:
                y = np.concatenate(
                    [y, np.full(expected_len - len(y), np.nan, dtype=np.float32)]
                )
            t = np.arange(expected_len) / fs + start
            max_points = 5000
            if len(y) > max_points:
                step = int(np.ceil(len(y) / max_points))
                y = y[::step]
                t = t[::step]
            p.curve.setData(t, y)
            p.setXRange(start, end, padding=0)
            
            # Apply global Y-range for consistent scaling across all chunks
            y_min, y_max = self.y_ranges.get(signal_name, (-1.0, 1.0))
            
            # Additional safety checks
            if not np.isfinite(y_min) or not np.isfinite(y_max):
                self.logger.warning(f"Invalid Y-range for {signal_name}: {y_min}, {y_max}. Using fallback.")
                y_min, y_max = -1.0, 1.0
            elif abs(y_max - y_min) > 1e6:
                self.logger.warning(f"Y-range too large for {signal_name}: {y_max - y_min}. Clamping.")
                y_center = (y_min + y_max) / 2
                y_min, y_max = y_center - 1e5, y_center + 1e5
            elif y_min == y_max:
                # Handle edge case where min equals max
                padding = max(abs(y_min) * 0.1, 0.1)
                y_min -= padding
                y_max += padding
            
            p.setYRange(y_min, y_max, padding=0)
            
            # Debug: Show current chunk vs global range occasionally
            if hasattr(self, '_debug_counter'):
                self._debug_counter += 1
            else:
                self._debug_counter = 1
            
            if self._debug_counter % 20 == 1:  # Every 20th update
                chunk_y_valid = y[np.isfinite(y)]
                if len(chunk_y_valid) > 0:
                    chunk_min, chunk_max = np.min(chunk_y_valid), np.max(chunk_y_valid)
                    self.logger.debug(f"{signal_name} - Chunk range: [{chunk_min:.3f}, {chunk_max:.3f}], Global range: [{y_min:.3f}, {y_max:.3f}]")

        # Add comment markers after updating all plots
        self._add_comment_markers()

    def _clear_comment_markers(self):
        """Clear all existing comment markers from plots."""
        for plot, markers in self.comment_markers.items():
            for marker in markers:
                try:
                    plot.removeItem(marker)
                except (ValueError, RuntimeError):
                    # Marker may already be deleted
                    pass
        self.comment_markers.clear()

    def _add_comment_markers(self):
        """Add comment markers using unified CommentMarkerManager."""
        try:
            # Clear previous markers first
            self._clear_comment_markers()
            self.marker_manager.clear_all_markers()

            # Get data manager and extract intervals
            dm = self.main_window.data_manager
            if not dm or not self.file_path:
                return

            # Get ECG trace to extract system intervals
            ecg = dm.get_trace(self.file_path, "ECG")
            from Pyside.processing.interval_extractor import extract_event_intervals
            intervals = extract_event_intervals([ecg])

            # Get current time range
            current_start = self.scrollbar.value()
            current_end = current_start + self.chunk_size

            # Create subplot dictionary for CommentMarkerManager
            plot_dict = {}
            for i, plot in enumerate(self.plots):
                signal_name = self.target_signals[i] if i < len(self.target_signals) else f"Plot_{i}"
                plot_dict[signal_name] = plot

            # Add system interval markers using unified manager
            self.marker_manager.add_markers_to_subplots(
                plot_dict, intervals, current_start, current_end
            )

            # Load and add user comments
            user_comments = self._load_user_comments()
            if user_comments:
                # Convert user comments to interval format for marker manager
                user_intervals = []
                for comment in user_comments:
                    if current_start <= comment.timestamp <= current_end:
                        user_interval = {
                            'evento': f"User: {comment.comment[:30]}{'...' if len(comment.comment) > 30 else ''}",
                            't_evento': comment.timestamp,
                            'comment_type': comment.comment_type,
                            'is_user_comment': True
                        }
                        user_intervals.append(user_interval)
                
                # Add user comment markers with different styling
                if user_intervals:
                    for signal_name, plot in plot_dict.items():
                        self.marker_manager.add_markers_to_single_plot(
                            plot, user_intervals, current_start, current_end, f"{signal_name}_user_comments"
                        )

            self.logger.debug(f"Added markers for range {current_start}-{current_end}: {len(intervals)} intervals, {len(user_comments)} user comments")

        except Exception as e:
            self.logger.error(f"Error adding comment markers: {e}")
    
    def _load_user_comments(self):
        """Load user comments from file if available."""
        try:
            if not self.file_path:
                return []
            
            # Import UserComment class
            from Pyside.ui.widgets.user_comment_widget import UserComment
            import json
            from pathlib import Path
            
            # Create comments directory path
            data_file_path = Path(self.file_path)
            comments_dir = data_file_path.parent / "comments"
            comment_file = comments_dir / f"{data_file_path.stem}_comments.json"
            
            # If comment file doesn't exist or is empty, return empty list
            if not comment_file.exists():
                self.logger.debug(f"No comment file found: {comment_file}")
                return []
            
            # Check if file is empty
            if comment_file.stat().st_size == 0:
                self.logger.debug(f"Empty comment file: {comment_file}")
                return []
            
            # Load comments from file
            with open(comment_file, 'r', encoding='utf-8') as f:
                comments_data = json.load(f)
            
            # Convert to UserComment objects
            user_comments = []
            for comment_data in comments_data.get('comments', []):
                comment = UserComment.from_dict(comment_data)
                user_comments.append(comment)
            
            self.logger.debug(f"Loaded {len(user_comments)} user comments from {comment_file}")
            return user_comments
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.debug(f"No user comments available: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"Error loading user comments: {e}")
            return []

    def on_chunk_size_changed(self, value):
        self.chunk_size = value
        dm = self.main_window.data_manager
        durations = []
        for ch in self.target_signals:
            sig = dm.get_trace(self.file_path, ch)
            durations.append(len(sig.data) / sig.fs)
        min_duration = int(min(durations)) if durations else 1
        self.scrollbar.setMaximum(max(0, min_duration - self.chunk_size))
        self.request_chunk(self.scrollbar.value())
        # Refresh markers after chunk size change
        self._add_comment_markers()
    
    def get_selected_channels(self):
        """Get the list of currently loaded channel names."""
        return getattr(self, 'target_signals', [])
    
    def update_hr_params(self, new_hr_params):
        """Update HR_GEN parameters and refresh Y-ranges for HR_GEN signals."""
        try:
            old_params = self.hr_params.copy()
            self.hr_params = new_hr_params.copy()
            
            self.logger.debug(f"HR parameters updated from {old_params} to {new_hr_params}")
            
            # Check if HR_GEN is in our target signals
            if hasattr(self, 'target_signals') and 'HR_GEN' in self.target_signals:
                # Recalculate Y-range for HR_GEN signal with new parameters
                dm = self.main_window.data_manager
                try:
                    sig = dm.get_trace(self.file_path, 'HR_GEN', **self.hr_params)
                    
                    # Recalculate global Y-range for HR_GEN
                    y_data = np.asarray(sig.data)
                    y_valid = y_data[np.isfinite(y_data)]
                    
                    if len(y_valid) > 0:
                        y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
                        
                        # Add padding
                        if y_min != y_max:
                            y_range = y_max - y_min
                            padding = y_range * 0.05
                            y_min -= padding
                            y_max += padding
                        else:
                            padding = max(abs(y_min) * 0.1, 0.1)
                            y_min -= padding
                            y_max += padding
                        
                        # Update the stored Y-range
                        self.y_ranges['HR_GEN'] = (y_min, y_max)
                        self.logger.debug(f"Updated HR_GEN Y-range: [{y_min:.3f}, {y_max:.3f}] with new parameters")
                    
                except Exception as e:
                    self.logger.error(f"Error updating HR_GEN Y-range: {e}")
                
                # Trigger a chunk refresh to apply the new parameters
                if hasattr(self, 'scrollbar') and self.scrollbar:
                    self.request_chunk(self.scrollbar.value())
                    self.logger.debug("Refreshed current chunk with new HR parameters")
            
        except Exception as e:
            self.logger.error(f"Error updating HR parameters: {e}")
