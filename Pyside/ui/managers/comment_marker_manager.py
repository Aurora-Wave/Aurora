"""
Global Comment Marker Manager for all visualization tabs.
Handles creation, tracking, and cleanup of comment markers across different plot types.
Supports synchronization between tabs via Qt signals.
"""

import pyqtgraph as pg
from PySide6.QtCore import QObject, Signal
from typing import Dict, List, Tuple, Any, Optional, Union
from Pyside.core import get_user_logger
from Pyside.core.comments import EMSComment


class CommentMarkerManager(QObject):
    """
    Global manager for comment markers across all visualization tabs.
    Handles marker lifecycle, positioning, and cleanup with synchronization.
    """
    
    # Qt Signals for global synchronization
    comments_updated = Signal(list)  # List[EMSComment] - when comments change
    comment_added = Signal(object)   # EMSComment - when single comment added
    comment_removed = Signal(str)    # comment_id - when comment removed
    markers_refreshed = Signal()     # when all markers need refresh

    def __init__(self):
        super().__init__()
        self.logger = get_user_logger("GlobalCommentMarkerManager")

        # Global comment storage
        self.current_comments: List[EMSComment] = []
        self.current_file_path: Optional[str] = None
        
        # Marker tracking by tab and plot
        # Structure: {tab_id: {plot_key: [markers]}}
        self.comment_markers: Dict[str, Dict[str, List[pg.InfiniteLine]]] = {}
        
        # Registered plot widgets for updates
        # Structure: {tab_id: {plot_key: plot_widget}}
        self.registered_plots: Dict[str, Dict[str, Any]] = {}

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

    # ========= Global Comment Management =========
    
    def set_comments(self, comments: List[EMSComment], file_path: str):
        """Set global comments and refresh all registered plots."""
        self.current_comments = comments
        self.current_file_path = file_path
        self.logger.info(f"Updated global comments: {len(comments)} comments for {file_path}")
        
        # Emit signal to update all plots
        self.comments_updated.emit(comments)
        self._refresh_all_registered_plots()
    
    def add_comment(self, comment: EMSComment):
        """Add a new comment and update all plots."""
        self.current_comments.append(comment)
        self.logger.info(f"Added comment {comment.comment_id}: {comment.text}")
        
        # Emit signals
        self.comment_added.emit(comment)
        self.comments_updated.emit(self.current_comments)
        self._refresh_all_registered_plots()
    
    def remove_comment(self, comment_id: str):
        """Remove a comment and update all plots."""
        initial_count = len(self.current_comments)
        self.current_comments = [c for c in self.current_comments if c.comment_id != comment_id]
        
        if len(self.current_comments) < initial_count:
            self.logger.info(f"Removed comment {comment_id}")
            # Emit signals
            self.comment_removed.emit(comment_id)
            self.comments_updated.emit(self.current_comments)
            self._refresh_all_registered_plots()
    
    def get_comments(self) -> List[EMSComment]:
        """Get current global comments."""
        return self.current_comments.copy()
    
    def register_plot(self, tab_id: str, plot_key: str, plot_widget: Any):
        """Register a plot widget for automatic updates."""
        if tab_id not in self.registered_plots:
            self.registered_plots[tab_id] = {}
        if tab_id not in self.comment_markers:
            self.comment_markers[tab_id] = {}
            
        self.registered_plots[tab_id][plot_key] = plot_widget
        self.comment_markers[tab_id][plot_key] = []
        
        self.logger.debug(f"Registered plot {tab_id}.{plot_key}")
        
        # Refresh this plot with current comments
        self._refresh_single_plot(tab_id, plot_key)
    
    def unregister_plot(self, tab_id: str, plot_key: str):
        """Unregister a plot widget."""
        # Clear markers first
        self._clear_plot_markers(tab_id, plot_key)
        
        # Remove from tracking
        if tab_id in self.registered_plots and plot_key in self.registered_plots[tab_id]:
            del self.registered_plots[tab_id][plot_key]
        if tab_id in self.comment_markers and plot_key in self.comment_markers[tab_id]:
            del self.comment_markers[tab_id][plot_key]
            
        self.logger.debug(f"Unregistered plot {tab_id}.{plot_key}")
    
    def _refresh_all_registered_plots(self):
        """Refresh all registered plots with current comments."""
        for tab_id in self.registered_plots:
            for plot_key in self.registered_plots[tab_id]:
                self._refresh_single_plot(tab_id, plot_key)
        
        # Emit refresh signal
        self.markers_refreshed.emit()
    
    def _refresh_single_plot(self, tab_id: str, plot_key: str):
        """Refresh a single plot with current comments."""
        if (tab_id not in self.registered_plots or 
            plot_key not in self.registered_plots[tab_id]):
            return
            
        plot_widget = self.registered_plots[tab_id][plot_key]
        
        # Clear existing markers
        self._clear_plot_markers(tab_id, plot_key)
        
        # Add new markers if we have comments
        if self.current_comments:
            # Convert EMSComment to interval format expected by existing methods
            intervals = self._convert_comments_to_intervals(self.current_comments)
            
            # Use existing method with full time range
            if hasattr(plot_widget, 'getPlotItem'):
                # Single plot widget
                self.add_markers_to_single_plot(
                    plot_widget, intervals, -float('inf'), float('inf'), 
                    plot_key, tab_id
                )
            else:
                # Multi-subplot (if needed later)
                pass
    
    def _convert_comments_to_intervals(self, comments: List[EMSComment]) -> List[Dict]:
        """Convert EMSComment objects to interval format."""
        intervals = []
        for comment in comments:
            interval = {
                "evento": comment.text,
                "t_evento": comment.time,
                "is_user_comment": comment.user_defined,
                "comment_type": "User" if comment.user_defined else "System"
            }
            intervals.append(interval)
        return intervals
    
    def _clear_plot_markers(self, tab_id: str, plot_key: str):
        """Clear markers from a specific plot."""
        if (tab_id not in self.comment_markers or 
            plot_key not in self.comment_markers[tab_id]):
            return
            
        markers = self.comment_markers[tab_id][plot_key]
        for marker in markers:
            try:
                if marker.parentItem():
                    marker.parentItem().removeItem(marker)
            except (RuntimeError, AttributeError):
                pass
                
        self.comment_markers[tab_id][plot_key].clear()

    def clear_all_markers(self):
        """Clear all markers from all tracked plots across all tabs."""
        markers_cleared = 0

        for tab_id in self.comment_markers:
            for plot_key in self.comment_markers[tab_id]:
                markers = self.comment_markers[tab_id][plot_key]
                for marker in markers:
                    try:
                        if marker.parentItem():
                            marker.parentItem().removeItem(marker)
                            markers_cleared += 1
                    except (RuntimeError, AttributeError) as e:
                        # Marker may already be deleted or invalid
                        self.logger.debug(f"Marker cleanup warning for {tab_id}.{plot_key}: {e}")

        self.comment_markers.clear()
        self.logger.debug(f"Cleared {markers_cleared} markers from all tabs")

    def add_markers_to_single_plot(
        self,
        plot_widget: pg.PlotWidget,
        intervals: List[Dict],
        context_start: float,
        context_end: float,
        plot_key: str = "main",
        tab_id: str = "default",
    ):
        """
        Add markers to a single plot widget.

        Args:
            plot_widget: The pyqtgraph PlotWidget
            intervals: List of interval dictionaries
            context_start: Start of visible time range
            context_end: End of visible time range
            plot_key: Identifier for this plot (for tracking)
            tab_id: Identifier for the tab containing this plot
        """
        # Ensure tab structure exists
        if tab_id not in self.comment_markers:
            self.comment_markers[tab_id] = {}
            
        # Clear existing markers for this plot
        if plot_key in self.comment_markers[tab_id]:
            for marker in self.comment_markers[tab_id][plot_key]:
                try:
                    if marker.parentItem():
                        marker.parentItem().removeItem(marker)
                except (RuntimeError, AttributeError):
                    pass
            self.comment_markers[tab_id][plot_key] = []
        else:
            self.comment_markers[tab_id][plot_key] = []

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
                self.comment_markers[tab_id][plot_key].append(marker)
                markers_added += 1

        self.logger.debug(f"Added {markers_added} markers to plot '{tab_id}.{plot_key}'")

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
        """Get total number of active markers across all tabs."""
        total = 0
        for tab_id in self.comment_markers:
            for plot_key in self.comment_markers[tab_id]:
                total += len(self.comment_markers[tab_id][plot_key])
        return total

    def set_style(self, **style_kwargs):
        """Update default marker styling."""
        self.default_style.update(style_kwargs)


# ========= Global Instance =========

def get_comment_marker_manager():
    """Get or create the global CommentMarkerManager instance."""
    global _comment_marker_manager
    if '_comment_marker_manager' not in globals():
        globals()['_comment_marker_manager'] = CommentMarkerManager()
    return _comment_marker_manager

# Create the global instance immediately
try:
    _comment_marker_manager = CommentMarkerManager()
except Exception:
    _comment_marker_manager = None
