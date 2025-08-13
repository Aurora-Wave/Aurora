import pyqtgraph as pg
from PySide6.QtGui import QColor
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class PlotStyle:
    """Data class for plot styling configuration."""
    pen_color: str = 'white'
    pen_width: int = 1
    background_color: str = 'black'
    grid_alpha: float = 0.3
    grid_enabled: bool = True
    mouse_x_enabled: bool = False
    mouse_y_enabled: bool = False
    plot_height: int = 200
    
    def to_pen(self) -> pg.mkPen:
        """Convert to PyQtGraph pen object."""
        return pg.mkPen(color=self.pen_color, width=self.pen_width)


@dataclass
class ToolbarStyle:
    """Data class for controls styling configuration (Aurora original style)."""
    # Aurora uses default system appearance - no custom background colors
    background_color: str = "transparent"  # No background in Aurora
    border_color: str = 'transparent'      # No borders in Aurora
    separator_color: str = 'transparent'   # No visible separators
    label_color: str = 'red'               # Default system text color
    label_font_weight: str = 'normal'     # Default font weight
    start_time_bg: str = 'transparent'    # No background for time display
    start_time_fg: str = 'black'          # Default text color
    start_time_font: str = 'default'      # Default system font
    spinbox_border: str = 'default'       # System default styling
    spinbox_bg: str = 'default'           # System default background
    slider_bg: str = 'default'            # System default slider
    slider_border: str = 'default'        # System default border
    slider_handle: str = 'default'        # System default handle
    slider_handle_hover: str = 'default'  # System default hover
    placeholder_color: str = '#666'       # Subtle placeholder text
    placeholder_border: str = '#ccc'      # Light placeholder border
    height: int = 30                      # Aurora controls height
    spacing: int = 10                     # Aurora spacing between controls
    start_spacing: int = 10               # Initial spacing at start of controls
    # Standard controls (always present)
    start_label: str = "Start:"           # Start time label text
    chunk_label: str = "Chunk size:"      # Chunk size label text
    signals_placeholder: str = "[Dropdown Widget Here]"  # Placeholder text
    
    def get_controls_layout_style(self) -> tuple:
        """Get Aurora-style layout configuration."""
        return (0, 0, 0, 0), self.spacing  # margins, spacing
    
    def get_controls_config(self) -> dict:
        """Get standard controls configuration."""
        return {
            'start_spacing': self.start_spacing,
            'spacing': self.spacing,
            'start_label': self.start_label,
            'chunk_label': self.chunk_label,
            'signals_placeholder': self.signals_placeholder
        }
    
    def get_start_time_stylesheet(self) -> str:
        """Generate minimal stylesheet for start time label (Aurora style)."""
        return ""  # Aurora uses default styling
    
    def get_slider_stylesheet(self) -> str:
        """Generate minimal stylesheet for position slider (Aurora style)."""
        return "QScrollBar {height: 20px;}"  # Only height like Aurora original
    
    def get_placeholder_stylesheet(self) -> str:
        """Generate stylesheet for signals placeholder."""
        return f"""
            color: {self.placeholder_color};
            font-style: italic;
            padding: 3px 8px;
            border: 1px dashed {self.placeholder_border};
            border-radius: 3px;
        """


class PlotStyleManager:
    """
    Centralized manager for plot styling across the application.
    Provides consistent visual appearance while allowing customization.
    """
    
    # Default base style for all signals
    DEFAULT_STYLE = PlotStyle(
        pen_color='#FFFFFF',  # White
        pen_width=1,
        plot_height=200
    )
    
    # Color palette for automatic assignment
    COLOR_PALETTE = [
        '#FF0000',  # Red
        '#FFFF00',  # Yellow
        '#00FFFF',  # Cyan
        '#00FF00',  # Green
        "#EE0C9F",  # Pink
        '#FFFFFF',  # White
    ]
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.custom_styles: Dict[str, PlotStyle] = {}
            self.color_index = 0
            self.toolbar_style = ToolbarStyle()  # Default toolbar style
            self._initialized = True
    
    def get_style_for_signal(self, signal_name: str, custom_style: Optional[PlotStyle] = None) -> PlotStyle:
        """
        Get styling for a specific signal.
        
        Args:
            signal_name: Name of the signal
            custom_style: Optional custom style override
            
        Returns:
            PlotStyle object
        """
        if custom_style:
            return custom_style
        
        # Check if signal has custom style
        if signal_name in self.custom_styles:
            return self.custom_styles[signal_name]
        
        # Assign color from palette automatically
        return self._assign_auto_style(signal_name)
    
    def _assign_auto_style(self, signal_name: str) -> PlotStyle:
        """Assign automatic style with color from palette."""
        color = self.COLOR_PALETTE[self.color_index % len(self.COLOR_PALETTE)]
        self.color_index += 1
        
        # Create style based on default with assigned color
        auto_style = PlotStyle(
            pen_color=color,
            pen_width=self.DEFAULT_STYLE.pen_width,
            background_color=self.DEFAULT_STYLE.background_color,
            grid_alpha=self.DEFAULT_STYLE.grid_alpha,
            grid_enabled=self.DEFAULT_STYLE.grid_enabled,
            mouse_x_enabled=self.DEFAULT_STYLE.mouse_x_enabled,
            mouse_y_enabled=self.DEFAULT_STYLE.mouse_y_enabled,
            plot_height=self.DEFAULT_STYLE.plot_height
        )
        self.custom_styles[signal_name] = auto_style
        return auto_style
    
    def set_custom_style(self, signal_name: str, style: PlotStyle):
        """Set custom style for a specific signal."""
        self.custom_styles[signal_name] = style
    
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
        
        # Configure basic properties
        plot_widget.setBackground(style.background_color)
        plot_widget.setMinimumHeight(style.plot_height)
        
        # Configure grid
        if style.grid_enabled:
            plot_widget.showGrid(x=True, y=True, alpha=style.grid_alpha)
        else:
            plot_widget.showGrid(x=False, y=False)
        
        # Configure mouse interaction
        plot_widget.setMouseEnabled(x=style.mouse_x_enabled, y=style.mouse_y_enabled)
        
        # Set labels
        plot_widget.setLabel("bottom", "Time (s)")
        plot_widget.setLabel("left", self._get_signal_label(signal_name))
    
    def _get_signal_label(self, signal_name: str) -> str:
        """Get appropriate label with units for signal."""
        # Basic unit mapping
        unit_mapping = {
            'ecg': 'mV',
            'hr': 'bpm', 
            'hr_gen': 'bpm',
            'pressure': 'mmHg',
            'systolic': 'mmHg',
            'diastolic': 'mmHg',
            'temperature': '°C',
            'temp': '°C',
            'flow': 'L/min',
            'volume': 'mL'
        }
        
        signal_lower = signal_name.lower()
        for key, unit in unit_mapping.items():
            if key in signal_lower:
                return f"{signal_name} ({unit})"
        
        return f"{signal_name} (AU)"  # Arbitrary Units
    
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
        if signal_name in self.custom_styles:
            self.custom_styles[signal_name].pen_color = color
        else:
            # Create new custom style based on default
            base_style = self.get_style_for_signal(signal_name)
            new_style = PlotStyle(
                pen_color=color,
                pen_width=base_style.pen_width,
                background_color=base_style.background_color,
                grid_alpha=base_style.grid_alpha,
                grid_enabled=base_style.grid_enabled,
                mouse_x_enabled=base_style.mouse_x_enabled,
                mouse_y_enabled=base_style.mouse_y_enabled,
                plot_height=base_style.plot_height
            )
            self.custom_styles[signal_name] = new_style
    
    def reset_signal_style(self, signal_name: str):
        """Reset signal to default styling."""
        if signal_name in self.custom_styles:
            del self.custom_styles[signal_name]
    
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
                'plot_height': style.plot_height
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
    
    def get_toolbar_style(self) -> ToolbarStyle:
        """Get current toolbar style configuration."""
        return self.toolbar_style
    
    def set_toolbar_style(self, toolbar_style: ToolbarStyle):
        """Set toolbar style configuration."""
        self.toolbar_style = toolbar_style
    
    def configure_toolbar(self, toolbar):
        """Configure a QToolBar with the current style."""
        # Apply main toolbar stylesheet
        toolbar.setStyleSheet(self.toolbar_style.get_toolbar_stylesheet())
        
        # Set toolbar properties
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setFixedHeight(self.toolbar_style.height)
    
    def get_toolbar_start_time_style(self) -> str:
        """Get stylesheet for start time label."""
        return self.toolbar_style.get_start_time_stylesheet()
    
    def get_toolbar_slider_style(self) -> str:
        """Get stylesheet for position slider."""
        return self.toolbar_style.get_slider_stylesheet()
    
    def get_toolbar_placeholder_style(self) -> str:
        """Get stylesheet for signals placeholder."""
        return self.toolbar_style.get_placeholder_stylesheet()


# Global instance
plot_style_manager = PlotStyleManager()