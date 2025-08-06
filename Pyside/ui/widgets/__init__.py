"""
UI widgets package for AuroraWave.

Contains custom widgets and dialogs for the application.
"""

from Pyside.ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from Pyside.ui.widgets.export_markers import ExportMarkersDialog
from Pyside.ui.widgets.export_selection_dialog import ExportSelectionDialog
from Pyside.ui.widgets.selectable_viewbox import SelectableViewBox

__all__ = [
    'ChannelSelectionDialog',
    'ExportMarkersDialog',
    'ExportSelectionDialog',
    'SelectableViewBox'
]