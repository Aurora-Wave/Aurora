"""
PlotStyleManager - Gestión centralizada de estilos para plots.
Adaptado para el sistema de sesiones de Aurora.
"""

import pyqtgraph as pg
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtGui import QColor
from PySide6.QtCore import QObject, Signal
from typing import Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, replace
import logging


@dataclass
class PlotStyle:
    """Data class for plot styling configuration."""
    pen_color: str = 'white'
    pen_width: int = 1
    background_color: str = 'black'
    grid_alpha: float = 0.5
    grid_enabled: bool = True
    mouse_x_enabled: bool = False
    mouse_y_enabled: bool = False
    min_plot_height: int = 150
    
    def to_pen(self) -> pg.mkPen:
        """Convert to PyQtGraph pen object."""
        return pg.mkPen(color=self.pen_color, width=self.pen_width)


class PlotStyleManager(QObject):
    """
    Centralized manager for plot styling across the application.
    Provides consistent visual appearance while allowing customization.
    """
    
    # Qt Signals - MUST be declared at class level
    minHeightChanged = Signal(int)  # new_min_height
    colorChanged = Signal(str, str)  # signal_name, new_color
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("aurora.ui.PlotStyleManager")
        
        # Default base style for all signals
        self.DEFAULT_STYLE = PlotStyle()
        
        # Color palette for automatic assignment
        self.COLOR_PALETTE = [
            "#EB0808",  # Red  
            "#4DB900",  # Green
            "#2102BB",  # Blue  
            '#4ECDC4',  # Teal
            '#45B7D1',  # Light Blue
            '#96CEB4',  # Green
            '#FFEAA7',  # Yellow
            '#DDA0DD',  # Plum
            '#F39C12',  # Orange
            '#E74C3C',  # Dark Red
            '#9B59B6',  # Purple
        ]
        
        # Creates mapping for signal and styles
        self.custom_styles: Dict[str, PlotStyle] = {}
        self.color_index = 0
        
        self.logger.debug("PlotStyleManager initialized")
    
    def get_style_for_signal(self, signal_name: str, custom_style: Optional[PlotStyle] = None) -> PlotStyle:
        """
        Get styling for a specific signal with persistent state management.
        
        Priority:
        1. If signal exists in manager → return latest state (includes user modifications)
        2. If custom_style provided and signal doesn't exist → create from custom_style  
        3. Otherwise → create auto-style
        
        Args:
            signal_name: Name of the signal
            custom_style: Optional custom style for initialization (only used if signal doesn't exist)
            
        Returns:
            PlotStyle object (always returns latest state for the signal)
        """
        # Priority 1: If signal exists in manager, return latest state (includes user modifications)
        if signal_name in self.custom_styles:
            return self.custom_styles[signal_name]
        
        # Priority 2: If custom_style provided for new signal, use it for initialization
        if custom_style:
            self.custom_styles[signal_name] = custom_style
            self.logger.debug(f"Assigned custom style to {signal_name}")
            return custom_style
        
        # Priority 3: Create auto-style for new signal
        return self._assign_auto_style(signal_name)
    
    def _assign_auto_style(self, signal_name: str) -> PlotStyle:
        """Assign automatic style with color from palette."""
        # Color cycling through color palette
        color = self.COLOR_PALETTE[self.color_index % len(self.COLOR_PALETTE)]
        self.color_index += 1
        
        # Create style based on default with auto assigned color
        auto_style = replace(self.DEFAULT_STYLE, pen_color=color)
        self.custom_styles[signal_name] = auto_style
        
        self.logger.debug(f"Auto-assigned style to {signal_name}: color={color}")
        return auto_style
    
    def set_custom_style(self, signal_name: str, style: PlotStyle):
        """Set custom style for a specific signal."""
        self.custom_styles[signal_name] = style
        self.logger.debug(f"Set custom style for {signal_name}")
    
    def get_available_colors(self) -> list:
        """Get list of available colors in palette."""
        return self.COLOR_PALETTE.copy()
    
    def configure_plot_widget(self, plot_widget: pg.PlotWidget, signal_name: str, 
                            custom_style: Optional[PlotStyle] = None):
        """
        Configure a PyQtGraph PlotWidget with appropriate styling.
        
        Args:
            plot_widget: The plot widget to configure
            signal_name: Name of the signal
            custom_style: Optional custom style override
        """
        style = self.get_style_for_signal(signal_name, custom_style)
        
        # Configure Plot Background
        plot_widget.setBackground(style.background_color)
        
        # Configure grid
        if style.grid_enabled:
            plot_widget.showGrid(x=True, y=True, alpha=style.grid_alpha)
        else:
            plot_widget.showGrid(x=False, y=False)
        
        # Configure mouse interaction
        plot_widget.setMouseEnabled(x=style.mouse_x_enabled, y=style.mouse_y_enabled)
        
        # Set labels
        plot_widget.setLabel("bottom", "Time (s)")
        # Left label is set by CustomPlot to signal name
        
        self.logger.debug(f"Configured plot widget for {signal_name}")

    def create_plot_pen(self, signal_name: str, custom_style: Optional[PlotStyle] = None) -> pg.mkPen:
        """Create a pen object for plotting."""
        style = self.get_style_for_signal(signal_name, custom_style)
        return style.to_pen()
    
    def get_signal_color(self, signal_name: str) -> str:
        """Get the color for a specific signal."""
        style = self.get_style_for_signal(signal_name)
        return style.pen_color
    
    def update_signal_color(self, signal_name: str, color: str):
        """Update color for a specific signal."""
        # Create new custom style based on current
        base_style = self.get_style_for_signal(signal_name)
        new_style = replace(base_style, pen_color=color)
        self.custom_styles[signal_name] = new_style
        
        self.logger.debug(f"Updated color for {signal_name} to {color}")
        
        # Emit signal for live updates
        self.colorChanged.emit(signal_name, color)
    
    def reset_signal_style(self, signal_name: str):
        """Reset signal to default styling."""
        if signal_name in self.custom_styles:
            del self.custom_styles[signal_name]
            self.logger.debug(f"Reset style for {signal_name}")
    
    def export_styles(self) -> Dict[str, Any]:
        """Export current style configuration."""
        return {
            'custom_styles': {name: {
                'pen_color': style.pen_color,
                'pen_width': style.pen_width,
                'background_color': style.background_color,
                'grid_alpha': style.grid_alpha,
                'grid_enabled': style.grid_enabled,
                'mouse_x_enabled': style.mouse_x_enabled,
                'mouse_y_enabled': style.mouse_y_enabled,
                'min_plot_height': style.min_plot_height
            } for name, style in self.custom_styles.items()},
            'color_index': self.color_index
        }
    
    def import_styles(self, styles_data: Dict[str, Any]):
        """Import style configuration."""
        if 'custom_styles' in styles_data:
            for name, style_dict in styles_data['custom_styles'].items():
                self.custom_styles[name] = PlotStyle(**style_dict)
        
        if 'color_index' in styles_data:
            self.color_index = styles_data['color_index']
            
        self.logger.debug("Imported style configuration")
    
    def update_min_height(self, signal_name, new_min: int):
        """Update minimum height for specific signal or all signals (*)."""  
        if signal_name == "*":
            # Update default style for all new signals
            self.DEFAULT_STYLE = replace(self.DEFAULT_STYLE, min_plot_height=new_min)
            
            # Update all existing custom styles
            for name in self.custom_styles:
                current_style = self.custom_styles[name]
                self.custom_styles[name] = replace(current_style, min_plot_height=new_min)
                
            self.logger.info(f"Updated minimum height for all signals to {new_min}px")
        else:
            # Update specific signal
            base_style = self.get_style_for_signal(signal_name)
            new_style = replace(base_style, min_plot_height=new_min)
            self.custom_styles[signal_name] = new_style
            
            self.logger.debug(f"Updated minimum height for {signal_name} to {new_min}px")
        
        # Emit signal for live updates
        self.minHeightChanged.emit(new_min)
    
    def force_refresh_all_heights(self):
        """Force refresh all plots to use current DEFAULT_STYLE min_plot_height."""
        current_min = self.DEFAULT_STYLE.min_plot_height
        
        # Clear all custom styles to force using DEFAULT_STYLE
        self.custom_styles.clear()
        self.logger.info(f"Force refreshed all heights to {current_min}px")
        
        # Emit signal to refresh all plots
        self.minHeightChanged.emit(current_min)


# Global instance management
_plot_style_manager_instance = None

def get_plot_style_manager():
    """Get or create the global PlotStyleManager instance."""
    global _plot_style_manager_instance
    if _plot_style_manager_instance is None:
        _plot_style_manager_instance = PlotStyleManager()
    return _plot_style_manager_instance

def reset_plot_style_manager():
    """Reset the global instance (useful for testing)."""
    global _plot_style_manager_instance
    _plot_style_manager_instance = None