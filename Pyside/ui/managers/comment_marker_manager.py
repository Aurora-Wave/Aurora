"""
Unified Comment Marker Manager for all visualization tabs.
Handles creation, tracking, and cleanup of comment markers across different plot types.
"""

import pyqtgraph as pg
from typing import Dict, List, Tuple, Any, Optional
from Pyside.core import get_user_logger


class CommentMarkerManager:
    """
    Centralized manager for comment markers across visualization tabs.
    Handles marker lifecycle, positioning, and cleanup for different plot architectures.
    """

    def __init__(self, tab_name: str = ""):
        self.tab_name = tab_name
        self.logger = get_user_logger(f"CommentMarkerManager.{tab_name}")

        # Marker tracking - supports both single plot and multi-subplot architectures
        self.comment_markers: Dict[str, List[pg.InfiniteLine]] = {}

        # Default marker styling for system comments
        self.default_style = {
            "pen": pg.mkPen("#ff9500", width=1, style=pg.QtCore.Qt.DashLine),
            "z_value": 1,
        }
        
        # User comment styling (different color for distinction)
        self.user_comment_style = {
            "pen": pg.mkPen("#00ff88", width=1, style=pg.QtCore.Qt.DashLine),
            "z_value": 2,  # Higher z-value to appear on top
        }

    def clear_all_markers(self):
        """Clear all markers from all tracked plots."""
        markers_cleared = 0

        for plot_key, markers in self.comment_markers.items():
            for marker in markers:
                try:
                    if marker.parentItem():
                        marker.parentItem().removeItem(marker)
                        markers_cleared += 1
                except (RuntimeError, AttributeError) as e:
                    # Marker may already be deleted or invalid
                    self.logger.debug(f"Marker cleanup warning for {plot_key}: {e}")

        self.comment_markers.clear()
        self.logger.debug(f"Cleared {markers_cleared} markers from {self.tab_name}")

    def add_markers_to_single_plot(
        self,
        plot_widget: pg.PlotWidget,
        intervals: List[Dict],
        context_start: float,
        context_end: float,
        plot_key: str = "main",
    ):
        """
        Add markers to a single plot widget (ViewerTab style).

        Args:
            plot_widget: The pyqtgraph PlotWidget
            intervals: List of interval dictionaries
            context_start: Start of visible time range
            context_end: End of visible time range
            plot_key: Identifier for this plot (for tracking)
        """
        # Clear existing markers for this plot
        if plot_key in self.comment_markers:
            for marker in self.comment_markers[plot_key]:
                try:
                    if marker.parentItem():
                        marker.parentItem().removeItem(marker)
                except (RuntimeError, AttributeError):
                    pass
            self.comment_markers[plot_key] = []
        else:
            self.comment_markers[plot_key] = []

        # Extract comment data with type information
        comment_data, comment_types = self._extract_comment_data_with_types(intervals)
        if not comment_data:
            return

        # Add markers to the plot - handle both PlotWidget and PlotItem
        if hasattr(plot_widget, 'getPlotItem'):
            # This is a PlotWidget
            plot_item = plot_widget.getPlotItem()
        else:
            # This is already a PlotItem
            plot_item = plot_widget
        markers_added = 0

        for timestamp, labels in comment_data.items():
            if context_start <= timestamp <= context_end:
                # Determine if this is a user comment
                is_user_comment = comment_types.get(timestamp, False)
                marker = self._create_marker(timestamp, labels, is_user_comment)
                plot_item.addItem(marker)
                self.comment_markers[plot_key].append(marker)
                markers_added += 1

        self.logger.debug(f"Added {markers_added} markers to single plot '{plot_key}'")

    def add_markers_to_subplots(
        self,
        subplot_items: Dict[str, Any],
        intervals: List[Dict],
        context_start: float,
        context_end: float,
    ):
        """
        Add markers to multiple subplots (TiltTab/AnalysisTab style).

        Args:
            subplot_items: Dictionary of channel_name -> PlotItem
            intervals: List of interval dictionaries
            context_start: Start of visible time range
            context_end: End of visible time range
        """
        # Clear existing markers from all subplots
        for channel_name in subplot_items.keys():
            if channel_name in self.comment_markers:
                for marker in self.comment_markers[channel_name]:
                    try:
                        if marker.parentItem():
                            marker.parentItem().removeItem(marker)
                    except (RuntimeError, AttributeError):
                        pass
                self.comment_markers[channel_name] = []
            else:
                self.comment_markers[channel_name] = []

        # Extract comment data with type information
        comment_data, comment_types = self._extract_comment_data_with_types(intervals)
        if not comment_data:
            return

        # Add markers to each subplot
        total_markers = 0
        for channel_name, subplot in subplot_items.items():
            markers_added = 0
            for timestamp, labels in comment_data.items():
                if context_start <= timestamp <= context_end:
                    # Determine if this is a user comment
                    is_user_comment = comment_types.get(timestamp, False)
                    marker = self._create_marker(timestamp, labels, is_user_comment)
                    subplot.addItem(marker)
                    self.comment_markers[channel_name].append(marker)
                    markers_added += 1
                    total_markers += 1

        self.logger.debug(
            f"Added {total_markers} markers across {len(subplot_items)} subplots"
        )

    def _extract_comment_data(self, intervals: List[Dict]) -> Dict[float, List[str]]:
        """Extract and deduplicate comment timestamps and labels from intervals."""
        if not intervals:
            return {}

        # Collect all timestamp-label pairs
        comment_pairs = []
        for iv in intervals:
            event_name = iv.get("evento", "Event")

            # Handle user comments specially - show only the comment type and text
            if iv.get("is_user_comment", False):
                # For user comments, just show the comment type and text
                comment_type = iv.get("comment_type", "User")
                if iv.get("t_evento"):
                    # Extract just the comment text after "User: " prefix
                    comment_text = event_name
                    if comment_text.startswith("User: "):
                        comment_text = comment_text[6:]  # Remove "User: " prefix
                    label = f"{comment_type}: {comment_text}"
                    comment_pairs.append((iv.get("t_evento"), label))
            else:
                # Handle system intervals with multiple timestamp types
                if iv.get("t_evento"):
                    comment_pairs.append((iv.get("t_evento"), f"{event_name} Start"))
                if iv.get("t_recovery"):
                    comment_pairs.append((iv.get("t_recovery"), f"{event_name} Recovery"))
                if iv.get("t_tilt_down"):
                    comment_pairs.append((iv.get("t_tilt_down"), f"{event_name} End"))
                if iv.get("t_baseline"):
                    comment_pairs.append((iv.get("t_baseline"), f"{event_name} Baseline"))

        # Group by timestamp and combine labels
        comment_dict = {}
        for timestamp, label in comment_pairs:
            if timestamp is not None:
                if timestamp not in comment_dict:
                    comment_dict[timestamp] = []
                comment_dict[timestamp].append(label)

        return comment_dict

    def _extract_comment_data_with_types(self, intervals: List[Dict]) -> Tuple[Dict[float, List[str]], Dict[float, bool]]:
        """Extract comment data and track which timestamps are user comments."""
        if not intervals:
            return {}, {}

        # Collect all timestamp-label pairs and track user comment status
        comment_pairs = []
        user_comment_timestamps = set()
        
        for iv in intervals:
            event_name = iv.get("evento", "Event")

            # Handle user comments specially - show only the comment type and text
            if iv.get("is_user_comment", False):
                # For user comments, just show the comment type and text
                comment_type = iv.get("comment_type", "User")
                if iv.get("t_evento"):
                    # Extract just the comment text after "User: " prefix
                    comment_text = event_name
                    if comment_text.startswith("User: "):
                        comment_text = comment_text[6:]  # Remove "User: " prefix
                    label = f"{comment_type}: {comment_text}"
                    timestamp = iv.get("t_evento")
                    comment_pairs.append((timestamp, label))
                    user_comment_timestamps.add(timestamp)
            else:
                # Handle system intervals with multiple timestamp types
                if iv.get("t_evento"):
                    comment_pairs.append((iv.get("t_evento"), f"{event_name} Start"))
                if iv.get("t_recovery"):
                    comment_pairs.append((iv.get("t_recovery"), f"{event_name} Recovery"))
                if iv.get("t_tilt_down"):
                    comment_pairs.append((iv.get("t_tilt_down"), f"{event_name} End"))
                if iv.get("t_baseline"):
                    comment_pairs.append((iv.get("t_baseline"), f"{event_name} Baseline"))

        # Group by timestamp and combine labels
        comment_dict = {}
        comment_types = {}
        for timestamp, label in comment_pairs:
            if timestamp is not None:
                if timestamp not in comment_dict:
                    comment_dict[timestamp] = []
                comment_dict[timestamp].append(label)
                # Mark if this timestamp has user comments
                comment_types[timestamp] = timestamp in user_comment_timestamps

        return comment_dict, comment_types

    def _create_marker(self, timestamp: float, labels: List[str], is_user_comment: bool = False) -> pg.InfiniteLine:
        """Create a vertical marker line with labels."""
        combined_label = " | ".join(labels)
        
        # Truncate very long labels to prevent rendering issues
        if len(combined_label) > 50:
            combined_label = combined_label[:47] + "..."
        
        # Choose style based on comment type
        style = self.user_comment_style if is_user_comment else self.default_style
        
        # Enhanced label options for better visibility
        if is_user_comment:
            # Green theme for user comments
            label_opts = {
                "position": 0.85,  # Position user comments slightly lower
                "color": (255, 255, 255),  # White text
                "fill": (0, 100, 0, 180),  # Dark green background
                "border": (0, 255, 136, 255),  # Bright green border
                "anchor": (0, 1),  # Anchor to bottom-left of text
            }
        else:
            # Orange theme for system comments
            label_opts = {
                "position": 0.9,  # System comments higher up
                "color": (255, 255, 255),  # White text
                "fill": (80, 40, 0, 180),  # Dark orange background
                "border": (255, 149, 0, 255),  # Orange border
                "anchor": (0, 1),  # Anchor to bottom-left of text
            }

        marker = pg.InfiniteLine(
            pos=timestamp,
            angle=90,
            pen=style["pen"],
            label=combined_label,
            labelOpts=label_opts,
        )
        marker.setZValue(style["z_value"])

        return marker

    def get_marker_count(self) -> int:
        """Get total number of active markers."""
        return sum(len(markers) for markers in self.comment_markers.values())

    def set_style(self, **style_kwargs):
        """Update default marker styling."""
        self.default_style.update(style_kwargs)
