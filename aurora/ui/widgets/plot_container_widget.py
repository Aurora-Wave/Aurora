import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSplitter,
    QLabel,
    QSpinBox,
    QPushButton,
    QFrame,
    QSlider,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from typing import List, Dict, Optional, Tuple
import logging
import numpy as np

from aurora.ui.widgets.custom_plot import CustomPlot
from aurora.ui.managers.plot_style_manager import get_plot_style_manager
import pyqtgraph as pg


class PlotContainerWidget(QWidget):
    """
    Widget to contain multiple CustomPlot widgets with shared controls.
    """

    # Signals
    scroll_changed = Signal(float)  # scroll_position
    plots_reordered = Signal(list)  # new_order
    signal_changed_in_plot = Signal(str, str)  # old_signal, new_signal

    def __init__(self, parent=None, tab_type: str = None):
        super().__init__(parent)
        self.logger = logging.getLogger("aurora.ui.PlotContainerWidget")

        # State
        self.start_time = 0.0
        self.chunk_size = 60.0
        self.duration = 100.0
        self.target_signals: List[str] = []
        self.plots: List[CustomPlot] = []

        # Data management
        self.data_manager = None
        self.file_path = None
        self.available_signals: List[str] = []

        # Custom PLot Style Managers
        self.style_manager = get_plot_style_manager()

        # UI Components
        self.controls_widget = None
        self.plots_splitter = None
        self.scroll_area = None

        # Comment rendering - simple visual markers only
        self.comment_markers: List[tuple] = (
            []
        )  # List of tuples (marker, plot_widget) for proper cleanup

        # Region selection management
        self._regions: List[Optional[pg.LinearRegionItem]] = []

        # Enable drop in container
        self.setAcceptDrops(True)

        self.setup_ui()

        # Connect to style manager for global height changes
        self.style_manager.minHeightChanged.connect(self._on_global_height_changed)

        # Install event filter to detect resize events
        self.scroll_area.installEventFilter(self)

        # Manual resize detection
        self._user_resizing = False
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_timeout)

        self.logger.debug("PlotContainerWidget initialized")

    def setup_ui(self):
        """Setup the plots area only - navigation handled by parent tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Only plots area - no navigation controls
        self.setup_plots_area()
        main_layout.addWidget(self.scroll_area)

    # Navigation controls removed - handled by VisualizationBaseTab

    def setup_plots_area(self):
        """Setup plots area with QSplitter for automatic space distribution."""
        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Create QSplitter for plots (vertical distribution)
        self.plots_splitter = QSplitter(Qt.Vertical)
        self.plots_splitter.setChildrenCollapsible(False)  # Prevent plot collapsing
        self.plots_splitter.setHandleWidth(3)  # Thin resize handles

        # Set splitter in scroll area
        self.scroll_area.setWidget(self.plots_splitter)

        # Connect splitter signal for manual resize detection
        self.plots_splitter.splitterMoved.connect(self._on_splitter_moved)

    def display_signals(
        self,
        data_manager,
        file_path: str,
        target_signals: List[str],
        hr_params: Dict = None,
    ):
        """
        Display signals using the provided data manager.

        Args:
            data_manager: DataManager instance from session
            file_path: Path to data file
            target_signals: List of signals to display
            hr_params: HR generation parameters (for future use)
        """
        self.logger.info(f"=== PlotContainer display_signals START ===")
        self.logger.info(f"File: {file_path}")
        self.logger.info(f"Target signals: {target_signals}")
        self.logger.info(f"DataManager type: {type(data_manager)}")

        try:
            self.data_manager = data_manager
            self.file_path = file_path
            self.target_signals = target_signals

            # Get available signals from data manager
            self.available_signals = self.data_manager.get_available_channels(file_path)

            # Create plots for signals
            self.create_plots()

            # Load and display data
            self.logger.info("Calling load_and_display_data()...")
            self.load_and_display_data()
            self.logger.info("load_and_display_data() completed")

            # Comments are handled by VisualizationBaseTab and rendered here when requested

            self.logger.info(
                f"=== PlotContainer display_signals SUCCESS with {len(target_signals)} signals ==="
            )
            return True

        except Exception as e:
            self.logger.error(f"Error displaying signals: {e}", exc_info=True)
            return False

    def create_plots(self):
        """Create plot widgets for target signals."""
        # Clear existing plots
        self.clear_plots()

        self.logger.debug(f"Creating plots for signals: {self.target_signals}")

        # Create new plots
        for plot_index, signal_name in enumerate(self.target_signals):
            plot = CustomPlot(
                signal_name,
                available_signals=self.available_signals,
                plot_container=self,
                plot_index=plot_index,
            )

            # Configure plot for splitter
            self._configure_plot_for_splitter(plot)

            # Connect signals
            plot.remove_requested.connect(self.remove_plot)
            plot.color_changed.connect(self.on_plot_color_changed)
            plot.signal_changed.connect(self.on_plot_signal_changed)

            # Connect to style manager for height changes
            self.style_manager.minHeightChanged.connect(plot.refresh_min_height)

            # Add to splitter
            self.plots.append(plot)
            self.plots_splitter.addWidget(plot)

            # Set stretch factor for equal distribution
            idx = self.plots_splitter.count() - 1
            self.plots_splitter.setStretchFactor(idx, 1)

        self.logger.info(f"Created {len(self.plots)} plots total")

        # CRITICAL: Calculate and set total splitter size for scroll area
        self._update_splitter_size()

    def _configure_plot_for_splitter(self, plot: CustomPlot):
        """Configure plot for optimal behavior in QSplitter."""
        # Unify size policy: allow full expansion
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        min_height = plot.minimumHeight()
        size_policy = plot.sizePolicy()

        self.logger.debug(f"Plot {plot.signal_name} ready for splitter:")
        self.logger.debug(f"  - minimumHeight(): {min_height}px")
        self.logger.debug(
            f"  - sizePolicy: H={size_policy.horizontalPolicy()}, V={size_policy.verticalPolicy()}"
        )

    def clear_plots(self):
        """Clear all existing plots."""
        for plot in self.plots:
            plot.cleanup()  # Cleanup connections
            plot.setParent(None)  # Remove from splitter
            plot.deleteLater()
        self.plots.clear()

    def remove_plot(self, plot: CustomPlot):
        """Remove a plot from the container."""
        if plot in self.plots:
            # Cleanup plot
            plot.cleanup()

            self.plots.remove(plot)
            plot.setParent(None)  # Remove from splitter
            plot.deleteLater()

            # Update target signals
            if plot.signal_name in self.target_signals:
                self.target_signals.remove(plot.signal_name)

            self.logger.debug(f"Removed plot {plot.signal_name} from splitter")

            # Update splitter size after removing plot
            self._update_splitter_size()

    def add_plot(self, signal_name: str):
        """Add a new plot for the given signal."""
        if (
            signal_name not in self.target_signals
            and signal_name in self.available_signals
        ):
            self.target_signals.append(signal_name)
            plot_index = len(self.plots)  # Current number of plots will be the index

            plot = CustomPlot(
                signal_name,
                available_signals=self.available_signals,
                plot_container=self,
                plot_index=plot_index,
            )

            # Configure for splitter
            self._configure_plot_for_splitter(plot)

            # Connect signals
            plot.remove_requested.connect(self.remove_plot)
            plot.color_changed.connect(self.on_plot_color_changed)
            plot.signal_changed.connect(self.on_plot_signal_changed)

            # Connect to style manager for height changes
            self.style_manager.minHeightChanged.connect(plot.refresh_min_height)

            # Comments are handled globally by PlotContainer, not per-plot

            # Add to splitter
            self.plots.append(plot)
            self.plots_splitter.addWidget(plot)

            # Set stretch factor for equal distribution
            idx = self.plots_splitter.count() - 1
            self.plots_splitter.setStretchFactor(idx, 1)

            # Load data for new plot
            if self.data_manager and self.file_path:
                try:
                    signal = self.data_manager.get_trace(self.file_path, signal_name)
                    if signal:
                        # Calculate sample range
                        start_sample = int(signal.fs * self.start_time)
                        end_sample = int(
                            signal.fs * (self.start_time + self.chunk_size)
                        )
                        end_sample = min(end_sample, len(signal.data))

                        if start_sample < len(signal.data):
                            # Extract data chunk
                            chunk_data = signal.data[start_sample:end_sample]
                            time_data = (
                                np.arange(len(chunk_data)) / signal.fs + self.start_time
                            )

                            # Update plot
                            plot.update_data(time_data, chunk_data)

                except Exception as e:
                    self.logger.error(
                        f"Error loading data for new plot {signal_name}: {e}"
                    )

            self.logger.debug(f"Added plot {signal_name} to splitter")

            # Update splitter size after adding plot
            self._update_splitter_size()

    def on_plot_color_changed(self, plot: CustomPlot, new_color: str):
        """Handle plot color change."""
        self.logger.debug(f"Plot {plot.signal_name} color changed to {new_color}")

    def on_plot_signal_changed(self, plot: CustomPlot, new_signal_name: str):
        """Handle signal change in plot."""
        old_signal = plot.signal_name

        # Update target signals list
        if old_signal in self.target_signals:
            idx = self.target_signals.index(old_signal)
            self.target_signals[idx] = new_signal_name

        # Reload data for the new signal
        self.load_and_display_data()

        self.logger.info(f"Plot signal changed from {old_signal} to {new_signal_name}")
        self.signal_changed_in_plot.emit(old_signal, new_signal_name)

    def load_and_display_data(self):
        """Load and display data for current time window."""
        if not self.data_manager or not self.file_path:
            return

        try:
            # Calculate time window
            start_time = self.start_time
            end_time = start_time + self.chunk_size

            self.logger.debug(
                f"Loading data for time window: {start_time:.1f}s - {end_time:.1f}s"
            )

            # Load data for each plot (fast - no ViewBox operations)
            for plot in self.plots:
                signal_name = plot.signal_name

                try:
                    # Get signal from data manager
                    signal = self.data_manager.get_trace(self.file_path, signal_name)
                    if signal is None:
                        self.logger.warning(f"No data for signal {signal_name}")
                        continue

                    # Calculate sample range
                    start_sample = int(signal.fs * start_time)
                    end_sample = int(signal.fs * end_time)
                    end_sample = min(end_sample, len(signal.data))

                    if start_sample >= len(signal.data):
                        self.logger.warning(
                            f"Start time beyond signal length for {signal_name}"
                        )
                        continue

                    # Extract data chunk
                    chunk_data = signal.data[start_sample:end_sample]

                    # Create time array
                    time_data = np.arange(len(chunk_data)) / signal.fs + start_time

                    # Update plot
                    plot.update_data(time_data, chunk_data)


                except Exception as e:
                    self.logger.error(
                        f"Error loading data for signal {signal_name}: {e}"
                    )

            # Set time range for all plots ONCE (batch operation)
            if self.plots:
                for plot in self.plots:
                    plot.set_time_range(start_time, end_time)

            # Comments are rendered when VisualizationBaseTab calls refresh_comment_display()

        except Exception as e:
            self.logger.error(f"Error loading and displaying data: {e}")

    def refresh_comment_display(self, comments_to_render):
        """
        SIMPLE: Render comment markers. Called by VisualizationBaseTab.
        This is now the only comment-related method - just pure rendering.
        """
        try:
            # Clear existing markers
            self._clear_comment_markers()

            if not self.plots or not comments_to_render:
                return

            # Create vertical line marker for each comment in each plot
            for comment in comments_to_render:
                self._create_comment_markers_for_all_plots(comment)

            self.logger.debug(
                f"Rendered {len(self.comment_markers)} comment markers across {len(self.plots)} plots"
            )

        except Exception as e:
            self.logger.error(f"Error rendering comments: {e}")

    def _create_comment_markers_for_all_plots(self, comment):
        """Create vertical line marker for a comment in each plot."""
        try:
            # Marker style and label options
            if comment.user_defined:
                # User comment style (green theme)
                pen = pg.mkPen("#00ff88", width=2)
                label_opts = {
                    "position": 0.85,  # Position user comments slightly lower
                    "color": (255, 255, 255),  # White text
                    "fill": (0, 100, 0, 180),  # Dark green background
                    "border": (0, 255, 136, 255),  # Bright green border
                    "anchor": (0, 1),  # Anchor to bottom-left of text
                }
            else:
                # System comment style (orange theme)
                pen = pg.mkPen("#ff9500", width=1)
                label_opts = {
                    "position": 0.9,  # System comments higher up
                    "color": (255, 255, 255),  # White text
                    "fill": (80, 40, 0, 180),  # Dark orange background
                    "border": (255, 149, 0, 255),  # Orange border
                    "anchor": (0, 1),  # Anchor to bottom-left of text
                }

            # Prepare label text
            label_text = (
                comment.text[:30] + "..." if len(comment.text) > 30 else comment.text
            )

            # Create vertical line marker for EACH plot
            for plot in self.plots:
                if hasattr(plot, "plot_widget"):
                    marker = pg.InfiniteLine(
                        pos=comment.time,
                        angle=90,  # Vertical
                        pen=pen,
                        movable=False,
                        label=label_text,
                        labelOpts=label_opts,
                    )

                    # Add marker to this plot and store reference with plot_widget
                    plot.plot_widget.addItem(marker)
                    self.comment_markers.append((marker, plot.plot_widget))

        except Exception as e:
            self.logger.error(f"Error creating markers for comment: {e}")

    def _clear_comment_markers(self):
        """Clear all comment markers from all plots."""
        for marker, plot_widget in self.comment_markers:
            try:
                # Remove marker directly from the plot_widget that owns it
                plot_widget.removeItem(marker)
            except Exception as e:
                # Marker might already be removed or plot_widget invalid
                pass

        self.comment_markers.clear()

    # Navigation methods removed - now handled by VisualizationBaseTab
    # set_duration, _on_start_time_changed, _on_chunk_size_changed, etc. moved to base class

    def get_plot_by_signal(self, signal_name: str) -> Optional[CustomPlot]:
        """Get plot widget for specific signal."""
        for plot in self.plots:
            if plot.signal_name == signal_name:
                return plot
        return None

    # ========= Drag and Drop Implementation for Plot Reordering =========

    def dragEnterEvent(self, event):
        """Handle drag enter for plot reordering."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("plot:"):
            event.acceptProposedAction()
            self.logger.debug("Drag enter accepted for plot reordering")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move for plot reordering."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("plot:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop for plot reordering in splitter."""
        if not (
            event.mimeData().hasText() and event.mimeData().text().startswith("plot:")
        ):
            event.ignore()
            return

        # Extract signal name from drag data
        drag_text = event.mimeData().text()
        signal_name = drag_text.replace("plot:", "")

        # Find the dragged plot
        dragged_plot = self.get_plot_by_signal(signal_name)
        if not dragged_plot:
            event.ignore()
            return

        # Find drop position in splitter
        drop_position = event.position()
        target_index = self._get_drop_index(drop_position)

        # Reorder plot in splitter
        self._reorder_plot_in_splitter(dragged_plot, target_index)

        event.acceptProposedAction()
        self.logger.debug(f"Plot {signal_name} reordered to index {target_index}")

        # Emit reorder signal
        new_order = [plot.signal_name for plot in self.plots]
        self.plots_reordered.emit(new_order)

    def _get_drop_index(self, drop_position) -> int:
        """Calculate target index based on drop position with precision."""
        # Convert coordinates to splitter coordinate system (works while scrolled)
        splitter_pos = self.plots_splitter.mapFrom(self, drop_position)
        drop_y = splitter_pos.y()

        if not self.plots:
            return 0

        # Compare drop_position.y() with widget.geometry() borders for precision
        cumulative_y = 0
        for i, plot in enumerate(self.plots):
            plot_geometry = plot.geometry()
            plot_top = cumulative_y
            plot_bottom = cumulative_y + plot_geometry.height()

            # If drop is in upper half of this plot, insert before it
            plot_middle = plot_top + plot_geometry.height() // 2
            if drop_y <= plot_middle:
                return i

            cumulative_y = plot_bottom

        # If we get here, drop is after all plots
        return len(self.plots)

    def _reorder_plot_in_splitter(self, plot: CustomPlot, target_index: int):
        """Reorder plot in splitter and update internal list."""
        # Get current index
        current_index = self.plots.index(plot)

        if current_index == target_index:
            return  # No change needed

        # Remove from splitter and list
        plot.setParent(None)  # Remove from splitter
        self.plots.remove(plot)

        # Insert at target position
        target_index = min(target_index, len(self.plots))  # Clamp again
        self.plots.insert(target_index, plot)
        self.plots_splitter.insertWidget(target_index, plot)

        # Restore stretch factors for equal distribution
        for i, current_plot in enumerate(self.plots):
            self.plots_splitter.setStretchFactor(i, 1)

        self.logger.debug(
            f"Reordered plot {plot.signal_name}: {current_index} -> {target_index}"
        )

    # ========= Splitter Size Management =========

    def _update_splitter_size(self):
        """Update splitter size to accommodate all minimum heights."""
        if not self.plots:
            return

        # Skip update if user is manually resizing
        if getattr(self, "_user_resizing", False):
            self.logger.debug("SKIPPING splitter size update - user is resizing")
            return

        # Calculate total minimum height needed
        total_min_height = sum(plot.minimumHeight() for plot in self.plots)

        # Add padding for splitter handles
        handle_padding = (len(self.plots) - 1) * self.plots_splitter.handleWidth()
        total_height = total_min_height + handle_padding

        # Get available height in scroll area viewport
        viewport_height = self.scroll_area.viewport().height()

        self.logger.info(f"🔍 SPLITTER SIZE CALCULATION:")
        self.logger.info(f"  - Plots count: {len(self.plots)}")
        self.logger.info(
            f"  - Individual minimumHeight(): {[plot.minimumHeight() for plot in self.plots]}"
        )
        self.logger.info(f"  - Total minimum required: {total_min_height}px")
        self.logger.info(f"  - Handle padding: {handle_padding}px")
        self.logger.info(f"  - Total required: {total_height}px")
        self.logger.info(f"  - Viewport available: {viewport_height}px")
        self.logger.info(
            f"  - Condition (total > viewport): {total_height > viewport_height}"
        )

        # CRITICAL: Force splitter to respect minimum heights only when necessary
        if total_height > viewport_height:
            # If total required height > viewport, set minimum but don't force sizes
            self.plots_splitter.setMinimumHeight(total_height)

            # Only force sizes if plots are below their minimum
            current_sizes = self.plots_splitter.sizes()
            min_sizes = [plot.minimumHeight() for plot in self.plots]

            needs_force = any(
                current < min_size
                for current, min_size in zip(current_sizes, min_sizes)
            )

            if needs_force:
                QTimer.singleShot(10, lambda: self.plots_splitter.setSizes(min_sizes))
                self.logger.debug(f"FORCED individual sizes: {min_sizes}")

            self.logger.debug(f"Set minimum height to {total_height}px")
        else:
            # If total required height <= viewport, allow normal distribution
            self.plots_splitter.setMinimumHeight(total_min_height)
            self.logger.debug(f"Normal distribution: {total_height}px fits in viewport")

        # Force updates
        self.scroll_area.updateGeometry()
        self.plots_splitter.updateGeometry()

    def _on_global_height_changed(self, new_min: int):
        """Handle global minimum height change from style manager."""
        self.logger.info(
            f"Global minimum height changed to {new_min}px, updating splitter size"
        )
        # The individual plots will have already updated their minimum heights
        # Now we need to update the splitter total size
        self._update_splitter_size()

    def _on_splitter_moved(self, pos: int, index: int):
        """Handle splitter moved by user."""
        self._user_resizing = True
        self._resize_timer.stop()
        self._resize_timer.start(500)  # 500ms timeout after user stops resizing

        # CRITICAL: Remove ALL constraints during user resize
        self.plots_splitter.setMinimumHeight(0)

        # Also remove individual plot minimum heights temporarily
        for plot in self.plots:
            plot.setMinimumHeight(0)

        self.logger.info(f"🖱️ USER RESIZE: pos={pos}, idx={index}")
        self.logger.info(f"  - Plots count: {len(self.plots)}")
        self.logger.info(f"  - Removed all constraints temporarily")

    def _on_resize_timeout(self):
        """Called when user stops resizing for timeout period."""
        self._user_resizing = False

        # Restore individual plot minimum heights
        for plot in self.plots:
            plot.setMinimumHeight(plot.min_height)

        self.logger.info("User finished manual resizing, restoring constraints")

        # Restore minimum height constraints after user finishes
        QTimer.singleShot(100, self._update_splitter_size)

    def eventFilter(self, obj, event):
        """Event filter to detect scroll area resize events."""
        if obj == self.scroll_area and event.type() == QEvent.Type.Resize:
            # Delay the update slightly to ensure the resize is complete
            QTimer.singleShot(10, self._update_splitter_size)
        return super().eventFilter(obj, event)

    # Comment rendering is now handled by refresh_comment_display() method above

    # ========= Region Selection Management =========

    def clear_all_regions(self):
        """Clear all region selections in all plots."""
        for i, plot in enumerate(self.plots):
            if i < len(self._regions) and self._regions[i] is not None:
                plot.plot_widget.removeItem(self._regions[i])
                self._regions[i] = None

        self.logger.debug("Cleared all region selections")

    def create_regions_at(self, region_bounds: List[float]):
        """
        Create region selections at specified bounds in all plots.

        Args:
            region_bounds: [start_x, end_x] coordinates for the region
        """
        # Ensure _regions list matches plots count
        while len(self._regions) < len(self.plots):
            self._regions.append(None)

        # Create regions in all plots
        for i, plot in enumerate(self.plots):
            # Remove existing region if any
            if i < len(self._regions) and self._regions[i] is not None:
                plot.plot_widget.removeItem(self._regions[i])

            # Create new region
            region = pg.LinearRegionItem(
                region_bounds,
                orientation=pg.LinearRegionItem.Vertical,
            )
            region.setZValue(10)  # Draw on top
            plot.plot_widget.addItem(region)

            # Store reference
            if i >= len(self._regions):
                self._regions.append(region)
            else:
                self._regions[i] = region

        self.logger.debug(f"Created regions at bounds: {region_bounds}")

    def update_all_regions(self, region_bounds: List[float]):
        """
        Update all existing region selections with new bounds.

        Args:
            region_bounds: [start_x, end_x] coordinates for the region
        """
        for region in self._regions:
            if region is not None:
                region.setRegion(region_bounds)

    def has_regions(self) -> bool:
        """Check if any regions are currently selected."""
        return any(region is not None for region in self._regions)

    def get_current_region(self) -> Optional[Tuple[float, float]]:
        """
        Get current region bounds if any region exists.

        Returns:
            Tuple[float, float]: (start_time, end_time) or None if no regions
        """
        for region in self._regions:
            if region is not None:
                bounds = region.getRegion()
                return (min(bounds), max(bounds))
        return None

    # ========= Cleanup =========

    # ========= Navigation Interface =========
    # Navigation is handled by VisualizationBaseTab, PlotContainer only responds to changes

    def set_time_window(self, start_time: float, chunk_size: float):
        """Set time window and reload data. Called by parent tab."""
        self.start_time = start_time
        self.chunk_size = chunk_size
        self.load_and_display_data()

    def update_chunk_data(
        self, start_sec: float, end_sec: float, data_dict: Dict[str, np.ndarray]
    ):
        """
        Update plots with chunk data from ChunkLoader.

        This method is called by ChunkLoader to efficiently update plots with
        pre-loaded and downsampled chunk data.

        Args:
            start_sec: Start time of the chunk
            end_sec: End time of the chunk
            data_dict: Dictionary mapping channel names to numpy arrays
        """
        try:
            self.logger.debug(
                f"Updating plots with chunk data: {start_sec:.2f}-{end_sec:.2f}s"
            )

            # Update internal time state
            self.start_time = start_sec
            self.chunk_size = end_sec - start_sec

            # Update each visible channel plot
            for i, channel_name in enumerate(self.target_signals):
                if i >= len(self.plots):
                    continue

                plot_widget = self.plots[i]
                chunk_data = data_dict.get(channel_name, np.array([]))

                if chunk_data.size == 0:
                    # No data for this channel - clear the plot
                    plot_widget.plot_widget.clear()
                    continue

                try:
                    # Get signal for sampling frequency
                    if (
                        hasattr(self, "data_manager")
                        and hasattr(self, "file_path")
                        and self.data_manager
                        and self.file_path
                    ):

                        sig = self.data_manager.get_trace(self.file_path, channel_name)
                        fs = sig.fs if sig else 1000.0  # Default fallback
                    else:
                        fs = 1000.0  # Default sampling frequency

                    # Create time axis
                    t = np.arange(len(chunk_data)) / fs + start_sec

                    # Update plot data efficiently - use correct API for CustomPlot
                    plot_widget.plot_widget.clear()
                    
                    # Get pen from style manager (CustomPlot architecture)
                    pen = plot_widget.style_manager.create_plot_pen(plot_widget.signal_name, plot_widget.custom_style)
                    plot_widget.plot_widget.plot(t, chunk_data, pen=pen)

                    # Set plot ranges
                    plot_widget.plot_widget.setXRange(start_sec, end_sec, padding=0)

                    # Apply Y range if available
                    if (
                        hasattr(plot_widget, "auto_range_y")
                        and not plot_widget.auto_range_y
                    ):
                        if hasattr(plot_widget, "y_min") and hasattr(
                            plot_widget, "y_max"
                        ):
                            plot_widget.plot_widget.setYRange(
                                plot_widget.y_min, plot_widget.y_max
                            )
                        else:
                            # Auto-range Y based on visible data
                            if len(chunk_data) > 0:
                                y_min, y_max = np.nanmin(chunk_data), np.nanmax(
                                    chunk_data
                                )
                                margin = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
                                plot_widget.plot_widget.setYRange(
                                    y_min - margin, y_max + margin
                                )

                    self.logger.debug(
                        f"Updated plot {i} ({channel_name}): {len(chunk_data)} points"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to update plot {i} ({channel_name}): {e}"
                    )
                    continue

            # Comments are handled by VisualizationBaseTab calling refresh_comment_display()
            # No need to update here - will be refreshed automatically

        except Exception as e:
            self.logger.error(f"Failed to update chunk data: {e}", exc_info=True)

    def set_duration(self, duration: float):
        """Set total duration. Called by parent tab."""
        self.duration = duration

    def cleanup(self):
        """Cleanup when container is being destroyed."""
        try:
            # Clear all regions
            self.clear_all_regions()

            # Clear comment markers
            self._clear_comment_markers()

            # Clear all plots
            self.clear_plots()

            # Disconnect from style manager
            try:
                self.style_manager.minHeightChanged.disconnect(
                    self._on_global_height_changed
                )
            except (RuntimeError, TypeError):
                pass

            self.logger.debug("PlotContainerWidget cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during PlotContainerWidget cleanup: {e}")
