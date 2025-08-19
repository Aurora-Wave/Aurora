"""
UI widgets package for AuroraWave.

Contains custom widgets and dialogs for the application.
"""

from Pyside.ui.widgets.channel_selection_dialog import ChannelSelectionDialog
from Pyside.ui.widgets.export_markers import ExportMarkersDialog
from Pyside.ui.widgets.export_selection_dialog import ExportSelectionDialog
from Pyside.ui.widgets.selectable_viewbox import SelectableViewBox
from Pyside.ui.widgets.plot_widget import PlotContainerWidget, CustomPlot
from Pyside.ui.widgets.viewer_plot_container import ViewerPlotContainer
from Pyside.ui.widgets.event_plot_container import EventPlotContainer
from Pyside.ui.widgets.analysis_plot_container import AnalysisPlotContainer

__all__ = [
    'ChannelSelectionDialog',
    'ExportMarkersDialog',
    'ExportSelectionDialog',
    'SelectableViewBox',
    'PlotContainerWidget',
    'CustomPlot',
    'ViewerPlotContainer',
    'EventPlotContainer',
    'AnalysisPlotContainer'
]