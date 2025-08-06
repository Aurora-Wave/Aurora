import numpy as np
from typing import List
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
    QSplitter,
    QPushButton,
)
from PySide6.QtCore import Qt
import pyqtgraph as pg
from Pyside.core import get_user_logger, get_current_session
from Pyside.data.data_manager import DataManager
from Pyside.processing.interval_extractor import extract_event_intervals
from Pyside.processing.chunk_loader import ChunkLoader
from Pyside.core.channel_units import get_channel_label_with_unit
from Pyside.core.visualization import default_downsampler
from Pyside.ui.managers import CommentMarkerManager, ScrollbarManager
from Pyside.ui.widgets.user_comment_widget import UserCommentWidget, UserComment


class EventTab(QWidget):
    """
    Tab to visualize events (intervals) across all channels.
    Loads a full 10-minute context window but displays a user-defined chunk size.
    Enables panning across the full context, zoom disabled, synchronized across channels.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Setup logger
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()

        # Data attributes
        self.data_manager: DataManager = None
        self.file_path: str = None
        self.channel_names: list[str] = []
        self.intervals: list[dict] = []
        self._selected_idx: int | None = None
        self.hr_params: dict = {}

        # Visualization parameters
        self._chunk_size: float = 60.0  # seconds
        self._context_start: float = 0.0
        self._context_end: float = 0.0
        self._offset: float = 0.0

        # ChunkLoader for efficient data loading
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self._update_chunk)

        # Track chunk requests for validation
        self._last_chunk_request = None

        # Unified navigation management
        self.scrollbar_manager = ScrollbarManager(self)
        self.scrollbar_manager.scroll_changed.connect(self._on_scroll_changed)

        # Multiple subplot structure
        self.subplot_items = {}  # PlotItem for each channel
        self.plot_curves = {}

        # Unified comment marker management
        self.marker_manager = CommentMarkerManager("EventTab")
        
        # User comment management
        self.user_comment_widget = UserCommentWidget(self)
        self.user_comments: List[UserComment] = []

        self.channel_colors = {
            "ECG": "#ffff00",  # Amarillo
            "HR_gen": "#00ff00",  # Verde
            "FBP": "#ff0000",  # Rojo
            "Valsalva": "#00ffff",  # Cyan
        }

        # UI setup
        self._setup_ui()
        
        # Connect user comment signals
        self._connect_user_comment_signals()

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
        
        # Show all comments button
        self.show_all_comments_btn = QPushButton("Show All Comments")
        self.show_all_comments_btn.setToolTip("Display all comments from the signal file")
        self.show_all_comments_btn.clicked.connect(self._show_all_comments)
        self._showing_all_comments = False

        self.scrollbar = QScrollBar(Qt.Horizontal)
        self.scrollbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scrollbar.valueChanged.connect(self._on_scroll_changed)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Search:"))
        ctrl.addWidget(self.filter_box)
        ctrl.addStretch()
        ctrl.addWidget(self.show_all_comments_btn)
        ctrl.addWidget(QLabel("Chunk:"))
        ctrl.addWidget(self.chunk_spin)

        # Agregar la barra de scroll con mayor proporción del espacio
        ctrl.addWidget(QLabel("Navigate:"))
        ctrl.addWidget(self.scrollbar, 1)  # Factor de stretch 1 para expandir

        # Plot area
        self.plot_widget = pg.GraphicsLayoutWidget()

        # Main layout with splitters for resizable sections
        layout = QVBoxLayout(self)
        layout.addLayout(ctrl)
        
        # Create horizontal splitter for table and comment widget
        table_splitter = QSplitter(Qt.Horizontal)
        table_splitter.addWidget(self.table)
        table_splitter.addWidget(self.user_comment_widget)
        table_splitter.setStretchFactor(0, 2)  # Table gets more space
        table_splitter.setStretchFactor(1, 1)  # Comment widget gets less space
        
        # Create vertical splitter for table/comments and plot
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(table_splitter)
        main_splitter.addWidget(self.plot_widget)
        main_splitter.setStretchFactor(0, 1)  # Table/comments section
        main_splitter.setStretchFactor(1, 3)  # Plot section gets more space
        
        layout.addWidget(main_splitter)
    
    def _connect_user_comment_signals(self):
        """Connect user comment widget signals for plot updates."""
        self.user_comment_widget.comments_changed.connect(self._on_user_comments_changed)
        self.user_comment_widget.comment_added.connect(self._on_user_comment_added)
    
    def _on_user_comments_changed(self, comments: List[UserComment]):
        """Handle user comments changes and update plot markers."""
        self.user_comments = comments
        self._update_plot_markers()
    
    def _on_user_comment_added(self, comment: UserComment):
        """Handle new user comment and provide feedback."""
        self.logger.info(f"User comment added: {comment}")
        # The comments_changed signal will handle the plot update
    
    def _update_plot_markers(self):
        """Update plot markers to include both system intervals and user comments."""
        if not hasattr(self, 'subplot_items') or not self.subplot_items:
            return
            
        try:
            # Get current time range for filtering comments
            start_time = self._context_start + self._offset
            end_time = start_time + self._chunk_size
            
            # Clear existing markers before updating
            self.marker_manager.clear_all_markers()
            
            # Filter system intervals to current time range for performance
            relevant_intervals = [
                iv for iv in self.intervals
                if any(start_time <= ts <= end_time for ts in [
                    iv.get('t_evento'), iv.get('t_baseline'), 
                    iv.get('t_recovery'), iv.get('t_tilt_down')
                ] if ts is not None)
            ]
            
            # Add system interval markers using unified manager (only relevant ones)
            if relevant_intervals:
                self.marker_manager.add_markers_to_subplots(
                    self.subplot_items, relevant_intervals, start_time, end_time
                )
            
            # Filter user comments to current time range
            relevant_comments = [
                comment for comment in self.user_comments
                if start_time <= comment.timestamp <= end_time
            ]
            
            if relevant_comments:
                # Convert user comments to marker format compatible with CommentMarkerManager
                user_intervals = []
                for comment in relevant_comments:
                    user_interval = {
                        'evento': f"User: {comment.comment[:30]}{'...' if len(comment.comment) > 30 else ''}",
                        't_evento': comment.timestamp,
                        'comment_type': comment.comment_type,
                        'is_user_comment': True
                    }
                    user_intervals.append(user_interval)
                
                # Add user comment markers with different visual style
                for channel, subplot in self.subplot_items.items():
                    self.marker_manager.add_markers_to_single_plot(
                        subplot, user_intervals, start_time, end_time, f"{channel}_user_comments"
                    )
            
            self.logger.debug(f"Updated plot markers in range {start_time:.1f}-{end_time:.1f}s: {len(relevant_intervals)} intervals, {len(relevant_comments)} user comments")
            
        except Exception as e:
            self.logger.warning(f"Error updating plot markers: {e}")

    # def update_tilt_tab(self, dm: DataManager, path: str):
    def update_event_tab(self, dm: DataManager, path: str, hr_params: dict):
        # Initialize data manager and path
        self.data_manager = dm
        self.file_path = path
        # Store HR_gen params for later chunk updates
        self.hr_params = hr_params
        
        # Set file path in user comment widget for persistence
        self.user_comment_widget.set_file_path(path)
        self.session.log_action("Event tab updated with new data", self.logger)

        # Determine channels: from metadata + cache (to include HR_gen)
        meta = set(dm.get_available_channels(path))
        self.logger.info("Trying to update event tab with new info")
        cache = {k.split("|")[0] for k in dm._files[path]["signal_cache"]}
        self.logger.debug(f"cache list of channels {cache}")
        available = meta.union(cache)
        order = ["ECG", "HR_gen", "FBP", "Valsalva"]
        self.channel_names = [ch for ch in order if ch in available]

        # Extract intervals (events) using cached method from DataManager
        self.intervals = dm.get_event_intervals(path, self.channel_names, **self.hr_params)
        self._selected_idx = None
        self._selected_idx = None

        # Populate table of events
        self._populate_table()

        ### Set context window to first 10 minutes (or less)
        ###max_durations = [max(dm.get_trace(path, ch).time) for ch in self.channel_names]

        # Set context window to first 10 minutes (or less), using hr_params for HR_gen
        max_durations = []
        for ch in self.channel_names:
            if ch.upper() == "HR_GEN":
                sig = dm.get_trace(path, ch, **self.hr_params)
            else:
                sig = dm.get_trace(path, ch)
            max_durations.append(max(sig.time))

        self._context_start = 0.0
        self._context_end = min(max(max_durations), self._context_start + 600.0)

        # Configure scrollbar range and render initial chunk
        self._setup_scroll()
        # Initial chunk load
        self._request_chunk()

    def _populate_table(self):
        if self._showing_all_comments:
            self._populate_all_comments_table()
        else:
            self._populate_intervals_table()
        self._apply_filter()
    
    def _populate_intervals_table(self):
        """Populate table with event intervals (default mode)."""
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Event", "Event(s)", "End(s)", "Duration(s)"]
        )
        
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
    
    def _populate_all_comments_table(self):
        """Populate table with all signal comments."""
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["Time(s)", "Comment", "Channel"]
        )
        
        # Get all comments from DataManager
        try:
            all_comments = []
            if self.data_manager and self.file_path:
                # Get raw comments from the file
                file_entry = self.data_manager._files[self.file_path]
                raw_comments = file_entry.get("comments", [])
                
                # Extract all markers from all signals
                for ch in self.channel_names:
                    try:
                        sig = self.data_manager.get_trace(self.file_path, ch)
                        for marker in getattr(sig, "MarkerData", []):
                            text = getattr(marker, "text", "") or ""
                            time = getattr(marker, "time", None)
                            if text and time is not None:
                                all_comments.append({
                                    "time": float(time),
                                    "text": text,
                                    "channel": ch
                                })
                    except Exception as e:
                        self.logger.debug(f"Could not get markers from {ch}: {e}")
                
                # Also add raw comments if available
                for comment in raw_comments:
                    if hasattr(comment, 'time') and hasattr(comment, 'text'):
                        all_comments.append({
                            "time": float(comment.time),
                            "text": comment.text,
                            "channel": "File"
                        })
            
            # Sort by time
            all_comments.sort(key=lambda x: x["time"])
            
            self.table.setRowCount(len(all_comments))
            for i, comment in enumerate(all_comments):
                items = [comment["time"], comment["text"], comment["channel"]]
                for j, val in enumerate(items):
                    if j == 0:  # Time column
                        txt = f"{val:.2f}"
                    else:
                        txt = str(val)
                    self.table.setItem(i, j, QTableWidgetItem(txt))
            
            self.logger.debug(f"Displayed {len(all_comments)} comments in table")
                        
        except Exception as e:
            self.logger.error(f"Error populating all comments table: {e}")
            # Fallback to intervals table
            self._populate_intervals_table()
    
    def _show_all_comments(self):
        """Toggle between showing intervals and all comments."""
        self._showing_all_comments = not self._showing_all_comments
        
        if self._showing_all_comments:
            self.show_all_comments_btn.setText("Show Event Intervals")
            self.show_all_comments_btn.setToolTip("Return to event intervals view")
            self.logger.info("Switching to all comments view")
        else:
            self.show_all_comments_btn.setText("Show All Comments")
            self.show_all_comments_btn.setToolTip("Display all comments from the signal file")
            self.logger.info("Switching to event intervals view")
        
        # Repopulate the table with new mode
        self._populate_table()
    
    def _navigate_to_time(self, target_time: float):
        """Navigate to a specific time position."""
        try:
            # Calculate the total file duration
            max_durations = []
            for ch in self.channel_names:
                if ch.upper() == "HR_GEN":
                    sig = self.data_manager.get_trace(self.file_path, ch, **self.hr_params)
                else:
                    sig = self.data_manager.get_trace(self.file_path, ch)
                max_durations.append(max(sig.time))
            
            file_duration = max(max_durations)
            
            # Set context around the target time
            margin = self._chunk_size / 2  # Center the target time
            self._context_start = max(0, target_time - margin)
            self._context_end = min(file_duration, target_time + margin)
            
            # If the context is smaller than chunk size, expand it
            if (self._context_end - self._context_start) < self._chunk_size:
                needed = self._chunk_size - (self._context_end - self._context_start)
                # Try to expand both sides
                expand_each = needed / 2
                new_start = max(0, self._context_start - expand_each)
                new_end = min(file_duration, self._context_end + expand_each)
                
                # If we can't expand both sides equally, expand the available side
                if new_start == 0:
                    new_end = min(file_duration, self._context_start + self._chunk_size)
                elif new_end == file_duration:
                    new_start = max(0, self._context_end - self._chunk_size)
                
                self._context_start = new_start
                self._context_end = new_end
            
            # Set offset to show the target time
            self._offset = max(0, min(target_time - self._context_start - self._chunk_size/2, 
                                    self._context_end - self._context_start - self._chunk_size))
            
            # Update UI
            self._update_plot_limits()
            self._setup_scroll()
            self._request_chunk()
            
            self.logger.debug(f"Navigated to time {target_time:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Error navigating to time {target_time}: {e}")

    def _apply_filter(self):
        term = self.filter_box.text().lower()
        for r in range(self.table.rowCount()):
            # Check multiple columns for the search term
            hide = True
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and term in item.text().lower():
                    hide = False
                    break
            self.table.setRowHidden(r, hide)

    def _setup_scroll(self):
        """Setup scrollbar using unified manager."""
        total_duration = self._context_end - self._context_start
        self.scrollbar_manager.setup_scrollbar(
            self.scrollbar, total_duration, self._chunk_size
        )
        # Set current offset to maintain position
        self.scrollbar_manager.update_offset(self._offset, emit_signal=False)

    def _on_chunk_changed(self, val):
        self._chunk_size = float(val)
        self.scrollbar_manager.update_chunk_size(self._chunk_size)
        self._request_chunk()

    def _on_scroll_changed(self, offset_value):
        """Handle scroll changes from unified manager."""
        self._offset = offset_value
        self._request_chunk()

    def _request_chunk(self):
        """Request chunk data efficiently using ChunkLoader."""
        if not self.data_manager or not self.file_path or not self.channel_names:
            return

        start_time = self._context_start + self._offset
        # Store request details for validation
        self._last_chunk_request = {
            "start_time": start_time,
            "duration": self._chunk_size,
            "end_time": start_time + self._chunk_size,
        }

        self.chunk_loader.request_chunk(
            data_manager=self.data_manager,
            file_path=self.file_path,
            channel_names=self.channel_names,
            start_sec=start_time,
            duration_sec=self._chunk_size,
        )

    def _update_chunk(self, start_sec, end_sec, data_dict):
        """Update subplots with chunk data efficiently."""
        try:
            # Validate inputs
            if not self.data_manager or not self.file_path or not self.channel_names:
                return

            # If channel count changed, rebuild the subplot structure
            if len(self.subplot_items) != len(self.channel_names):
                self._setup_subplots()

            for ch in self.channel_names:
                try:
                    # For HR_gen, re-fetch with the current HR parameters
                    if ch.upper() == "HR_GEN":
                        sig = self.data_manager.get_trace(
                            self.file_path, ch, **self.hr_params
                        )
                        fs = sig.fs
                        # Slice by time window - use inclusive end to match ChunkLoader behavior
                        mask = (sig.time >= start_sec) & (
                            sig.time <= end_sec
                        )  # <= inclusive!
                        t = sig.time[mask]
                        chunk_data = sig.data[mask]
                        if chunk_data.size == 0:
                            continue
                    else:
                        # Other channels come from the chunk loader
                        chunk_data = data_dict.get(ch, np.array([]))
                        if chunk_data.size == 0:
                            continue
                        sig = self.data_manager.get_trace(self.file_path, ch)
                        fs = sig.fs
                        # Build time axis for the raw chunk - ensure it covers the full range
                        # Use the actual start/end times rather than just chunk indices
                        actual_duration = len(chunk_data) / fs
                        t = np.linspace(
                            start_sec, start_sec + actual_duration, len(chunk_data)
                        )

                        # Ensure time array matches chunk_data length exactly
                        if len(t) != len(chunk_data):
                            t = np.arange(len(chunk_data)) / fs + start_sec

                        # Debug info for incomplete plots
                        if len(chunk_data) > 0:
                            actual_end = t[-1] if len(t) > 0 else start_sec
                            expected_end = (
                                self._last_chunk_request["end_time"]
                                if self._last_chunk_request
                                else end_sec
                            )
                            if (
                                abs(actual_end - expected_end) > 0.1
                            ):  # More than 100ms difference
                                self.logger.debug(
                                    f"Channel {ch} chunk incomplete: expected end {expected_end:.3f}s, actual end {actual_end:.3f}s"
                                )

                    # Validate subplot exists
                    if ch not in self.subplot_items:
                        continue

                    # Get plot width for intelligent downsampling
                    subplot = self.subplot_items[ch]
                    plot_widget_width = self.plot_widget.width()
                    subplot_width = max(
                        plot_widget_width - 100, 600
                    )  # Account for margins

                    # Apply FIXED intelligent adaptive downsampling
                    original_points = len(chunk_data)
                    if len(chunk_data) > 200:  # Only downsample if worth it
                        t, chunk_data = default_downsampler.downsample_adaptive(
                            t, chunk_data, plot_width_pixels=subplot_width
                        )
                        downsampled_points = len(chunk_data)
                        reduction_pct = (1 - downsampled_points / original_points) * 100
                        self.logger.debug(
                            f"Channel {ch}: {original_points} → {downsampled_points} points ({reduction_pct:.1f}% reduction) [FIXED DOWNSAMPLER]"
                        )
                    else:
                        self.logger.debug(
                            f"Channel {ch}: {original_points} points (no downsampling needed)"
                        )

                    # Get the subplot for this channel
                    subplot = self.subplot_items[ch]

                    # Update existing curve or create a new one
                    if ch in self.plot_curves:
                        self.plot_curves[ch].setData(t, chunk_data)
                    else:
                        color = self.channel_colors.get(ch, "#ffffff")
                        self.plot_curves[ch] = subplot.plot(
                            t, chunk_data, pen=pg.mkPen(color, width=1), name=ch
                        )

                    # Set X range (all subplots will be synchronized)
                    # Use actual data range if available, otherwise use requested range
                    if len(t) > 0:
                        actual_start = min(t[0], start_sec)
                        actual_end = max(
                            t[-1], start_sec
                        )  # Ensure we don't go backwards
                        # But don't exceed the requested window too much
                        display_start = max(actual_start, start_sec - 0.1)
                        display_end = min(max(actual_end, end_sec - 0.1), end_sec + 0.1)
                        subplot.setXRange(display_start, display_end, padding=0)
                    else:
                        # Fallback to requested range
                        subplot.setXRange(start_sec, end_sec, padding=0)

                    # Set Y range based on actual data
                    finite = chunk_data[np.isfinite(chunk_data)]
                    if finite.size > 0:
                        y_margin = (finite.max() - finite.min()) * 0.1  # 10% margin
                        subplot.setYRange(
                            float(finite.min() - y_margin),
                            float(finite.max() + y_margin),
                            padding=0,
                        )

                except Exception as e:
                    self.logger.warning(f"Error updating channel {ch}: {e}")
                    continue
            
            # Update markers after chunk data is loaded
            self._update_plot_markers()

        except Exception as e:
            self.logger.error(f"Error in _update_chunk: {e}")

    def _setup_subplots(self):
        """Setup synchronized subplots for each channel."""
        # Clear existing markers before rebuilding
        self.marker_manager.clear_all_markers()

        self.plot_widget.clear()
        self.subplot_items.clear()
        self.plot_curves.clear()

        # Create subplots in vertical layout
        for i, ch in enumerate(self.channel_names):
            subplot = self.plot_widget.addPlot(row=i, col=0, title=ch)

            # Configure each subplot
            vb = subplot.getViewBox()
            vb.setMouseMode(pg.ViewBox.PanMode)
            vb.setMouseEnabled(x=True, y=False)  # Only horizontal panning
            vb.setLimits(xMin=self._context_start, xMax=self._context_end)

            # Disable individual wheel events - we'll handle globally
            vb.wheelEvent = self._create_global_wheel_handler()

            # Configure appearance
            subplot.showGrid(x=True, y=True)
            subplot.setMenuEnabled(False)

            # Only show X label on bottom subplot
            if i == len(self.channel_names) - 1:
                subplot.setLabel("bottom", "Time (s)")
            else:
                subplot.hideAxis("bottom")

            # Set Y label with units
            y_label = get_channel_label_with_unit(ch)
            subplot.setLabel("left", y_label)

            # Store subplot reference
            self.subplot_items[ch] = subplot

        # Link all X-axes for synchronized panning
        if len(self.subplot_items) > 1:
            reference_plot = list(self.subplot_items.values())[0]
            for subplot in list(self.subplot_items.values())[1:]:
                subplot.setXLink(reference_plot)

        # Add comment markers (both system intervals and user comments)
        self._update_plot_markers()

    def _create_global_wheel_handler(self):
        """Create a wheel handler that works across all subplots."""

        def wheel_handler(ev):
            # Use unified scrollbar manager for wheel events
            delta = ev.delta()
            if self.scrollbar_manager.handle_wheel_scroll(delta, scroll_factor=2.0):
                ev.accept()
            else:
                ev.ignore()

        return wheel_handler

    def _update_plot_limits(self):
        """Update X limits for all subplots based on current context."""
        for subplot in self.subplot_items.values():
            vb = subplot.getViewBox()
            vb.setLimits(xMin=self._context_start, xMax=self._context_end)

            # Reset X range to current position
            current_start = self._context_start + self._offset
            current_end = current_start + self._chunk_size
            subplot.setXRange(current_start, current_end, padding=0)

    def _on_row_selected(self, row, col):
        # Handle different table modes
        if self._showing_all_comments:
            # In comments mode, navigate to the comment time
            time_item = self.table.item(row, 0)  # Time is in first column
            if time_item:
                try:
                    comment_time = float(time_item.text())
                    self._navigate_to_time(comment_time)
                    self.logger.debug(f"Navigated to comment at {comment_time:.2f}s")
                except ValueError:
                    self.logger.warning(f"Could not parse time from row {row}")
            return
        
        # Original intervals mode behavior
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

        self._update_plot_limits()  # Actualizar límites de subplots
        self._setup_scroll()
        self._request_chunk()
    
    def update_hr_params(self, new_hr_params):
        """Update HR_GEN parameters and refresh display if needed."""
        try:
            old_params = self.hr_params.copy()
            self.hr_params = new_hr_params.copy()
            
            self.logger.debug(f"EventTab HR parameters updated from {old_params} to {new_hr_params}")
            
            # Check if HR_GEN is in our channels and we have valid data
            if (hasattr(self, 'channel_names') and 'HR_GEN' in self.channel_names 
                and hasattr(self, 'data_manager') and self.data_manager):
                
                # Refresh the current display with new HR parameters
                if hasattr(self, '_selected_idx') and self._selected_idx is not None:
                    self._request_chunk()  # This will use the updated hr_params
                    self.logger.debug("Refreshed EventTab display with new HR parameters")
                    
        except Exception as e:
            self.logger.error(f"Error updating EventTab HR parameters: {e}")
