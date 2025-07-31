"""
Unified Comment Marker Manager for all visualization tabs.
Handles creation, tracking, and cleanup of comment markers across different plot types.
"""

import pyqtgraph as pg
from typing import Dict, List, Tuple, Any, Optional
import logging


class CommentMarkerManager:
    """
    Centralized manager for comment markers across visualization tabs.
    Handles marker lifecycle, positioning, and cleanup for different plot architectures.
    """

    def __init__(self, tab_name: str = ""):
        self.tab_name = tab_name
        self.logger = logging.getLogger(f"{__name__}.CommentMarkerManager.{tab_name}")

        # Marker tracking - supports both single plot and multi-subplot architectures
        self.comment_markers: Dict[str, List[pg.InfiniteLine]] = {}

        # Default marker styling
        self.default_style = {
            "pen": pg.mkPen("#ff9500", width=1, style=pg.QtCore.Qt.DashLine),
            "label_color": "#ff9500",
            "label_fill": (255, 149, 0, 50),
            "label_position": 0.95,
            "z_value": 1,
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

        # Extract comment data
        comment_data = self._extract_comment_data(intervals)
        if not comment_data:
            return

        # Add markers to the plot
        plot_item = plot_widget.getPlotItem()
        markers_added = 0

        for timestamp, labels in comment_data.items():
            if context_start <= timestamp <= context_end:
                marker = self._create_marker(timestamp, labels)
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

        # Extract comment data
        comment_data = self._extract_comment_data(intervals)
        if not comment_data:
            return

        # Add markers to each subplot
        total_markers = 0
        for channel_name, subplot in subplot_items.items():
            markers_added = 0
            for timestamp, labels in comment_data.items():
                if context_start <= timestamp <= context_end:
                    marker = self._create_marker(timestamp, labels)
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

            # Extract different timestamp types
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

    def _create_marker(self, timestamp: float, labels: List[str]) -> pg.InfiniteLine:
        """Create a vertical marker line with labels."""
        combined_label = " | ".join(labels)

        marker = pg.InfiniteLine(
            pos=timestamp,
            angle=90,
            pen=self.default_style["pen"],
            label=combined_label,
            labelOpts={
                "position": self.default_style["label_position"],
                "color": self.default_style["label_color"],
                "fill": self.default_style["label_fill"],
            },
        )
        marker.setZValue(self.default_style["z_value"])

        return marker

    def get_marker_count(self) -> int:
        """Get total number of active markers."""
        return sum(len(markers) for markers in self.comment_markers.values())

    def set_style(self, **style_kwargs):
        """Update default marker styling."""
        self.default_style.update(style_kwargs)
