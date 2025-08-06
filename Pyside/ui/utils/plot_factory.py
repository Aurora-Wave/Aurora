"""
Plot Factory for AuroraWave Application
Provides standardized plot creation and configuration utilities.
"""

import numpy as np
import pyqtgraph as pg
from typing import Tuple, Optional, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from Pyside.core.channel_units import get_channel_label_with_unit


class PlotFactory:
    """Factory class for creating standardized plots across the application."""
    
    # Default plot configurations
    DEFAULT_PLOT_HEIGHT = 200
    DEFAULT_GRID_ALPHA = 0.3
    DEFAULT_PADDING_PCT = 0.05
    
    # Standard plot styles
    PLOT_STYLES = {
        'ecg': {
            'pen': pg.mkPen(color='blue', width=1),
            'grid': True,
            'mouse_enabled': (True, False),
        },
        'hr': {
            'pen': pg.mkPen(color='green', width=1),
            'grid': True,
            'mouse_enabled': (True, False)
        },
        'pressure': {
            'pen': pg.mkPen(color='red', width=1),
            'grid': True,
            'mouse_enabled': (True, False)
        },
        'default': {
            'pen': pg.mkPen(color='white', width=1),
            'grid': True,
            'mouse_enabled': (True, False)
        }
    }
    
    @classmethod
    def create_time_series_plot(cls, 
                               signal_name: str,
                               title: Optional[str] = None,
                               height: int = None,
                               mouse_enabled: Tuple[bool, bool] = None,
                               style_type: str = 'default',
                               show_grid: bool = True) -> pg.PlotWidget:
        """
        Create a standardized time series plot.
        
        Args:
            signal_name: Name of the signal for labeling
            title: Plot title (optional)
            height: Plot height in pixels
            mouse_enabled: (x_enabled, y_enabled) tuple
            style_type: Style configuration key
            show_grid: Whether to show grid
            
        Returns:
            Configured PlotWidget
        """
        # Use defaults if not specified
        height = height or cls.DEFAULT_PLOT_HEIGHT
        style = cls.PLOT_STYLES.get(style_type, cls.PLOT_STYLES['default'])
        mouse_enabled = mouse_enabled or style['mouse_enabled']
        
        # Create plot widget
        plot = pg.PlotWidget()
        plot.setMinimumHeight(height)
        
        # Configure labels
        plot.setLabel("bottom", "Time (s)")
        plot.setLabel("left", get_channel_label_with_unit(signal_name))
        
        # Set title if provided
        if title:
            plot.setTitle(title)
            
        # Configure mouse interaction
        plot.setMouseEnabled(x=mouse_enabled[0], y=mouse_enabled[1])
        
        # Configure grid
        if show_grid and style.get('grid', True):
            plot.showGrid(x=True, y=True, alpha=cls.DEFAULT_GRID_ALPHA)
            
        # Set background color
        plot.setBackground('black')
        
        return plot
    
    @classmethod
    def create_subplot_grid(cls, 
                           rows: int, 
                           cols: int = 1,
                           shared_x: bool = True) -> pg.GraphicsLayoutWidget:
        """
        Create a grid of subplots.
        
        Args:
            rows: Number of rows
            cols: Number of columns
            shared_x: Whether to share x-axis
            
        Returns:
            Configured GraphicsLayoutWidget
        """
        layout = pg.GraphicsLayoutWidget()
        layout.setBackground('black')
        
        plots = []
        for row in range(rows):
            row_plots = []
            for col in range(cols):
                if shared_x and plots:  # Link x-axis to first plot
                    plot = layout.addPlot(row=row, col=col, 
                                        viewBox=pg.ViewBox(enableMouse=True))
                    plot.setXLink(plots[0][0])
                else:
                    plot = layout.addPlot(row=row, col=col)
                
                plot.showGrid(x=True, y=True, alpha=cls.DEFAULT_GRID_ALPHA)
                row_plots.append(plot)
            plots.append(row_plots)
            
        return layout, plots
    
    @classmethod
    def calculate_optimal_y_range(cls, 
                                 signal_data: np.ndarray,
                                 padding_pct: float = None,
                                 min_range: float = 0.1) -> Tuple[float, float]:
        """
        Calculate optimal Y range with padding for signal visualization.
        
        Args:
            signal_data: Signal data array
            padding_pct: Percentage of padding to add
            min_range: Minimum range for constant signals
            
        Returns:
            (y_min, y_max) tuple
        """
        padding_pct = padding_pct or cls.DEFAULT_PADDING_PCT
        
        # Handle empty or invalid data
        if signal_data is None or len(signal_data) == 0:
            return -1.0, 1.0
            
        # Filter out non-finite values
        y_valid = signal_data[np.isfinite(signal_data)]
        
        if len(y_valid) == 0:
            return -1.0, 1.0
            
        y_min, y_max = float(np.min(y_valid)), float(np.max(y_valid))
        
        # Handle constant signals
        if abs(y_max - y_min) < 1e-10:
            if y_min == 0:
                return -min_range, min_range
            else:
                padding = max(abs(y_min) * 0.1, min_range)
                return y_min - padding, y_min + padding
        
        # Add percentage-based padding
        y_range = y_max - y_min
        padding = y_range * padding_pct
        
        return y_min - padding, y_max + padding
    
    @classmethod
    def apply_plot_style(cls, 
                        plot: pg.PlotWidget,
                        style_type: str = 'default',
                        custom_style: Dict[str, Any] = None) -> None:
        """
        Apply styling to an existing plot.
        
        Args:
            plot: Plot widget to style
            style_type: Style configuration key
            custom_style: Custom style overrides
        """
        style = cls.PLOT_STYLES.get(style_type, cls.PLOT_STYLES['default']).copy()
        
        if custom_style:
            style.update(custom_style)
            
        # Apply mouse settings
        if 'mouse_enabled' in style:
            plot.setMouseEnabled(x=style['mouse_enabled'][0], 
                               y=style['mouse_enabled'][1])
        
        # Apply grid settings
        if style.get('grid', True):
            plot.showGrid(x=True, y=True, alpha=cls.DEFAULT_GRID_ALPHA)
    
    @classmethod
    def create_analysis_plot_grid(cls) -> Tuple[pg.GraphicsLayoutWidget, Dict[str, pg.PlotItem]]:
        """
        Create the standard plot grid used in AnalysisTab.
        
        Returns:
            (layout_widget, plots_dict)
        """
        layout = pg.GraphicsLayoutWidget()
        layout.setBackground('black')
        
        # Create plots with standard configuration - stacked vertically
        ecg_plot = layout.addPlot(row=0, col=0, title="ECG Chunk")
        hr_plot = layout.addPlot(row=1, col=0, title="HR_gen Chunk")
        wave_plot = layout.addPlot(row=2, col=0, title="Wavelet")
        
        # Configure labels
        ecg_plot.setLabel("bottom", "Time (s)")
        ecg_plot.setLabel("left", get_channel_label_with_unit("ECG"))
        
        hr_plot.setLabel("bottom", "Time (s)")
        hr_plot.setLabel("left", get_channel_label_with_unit("HR"))
        
        wave_plot.setLabel("bottom", "Samples")
        wave_plot.setLabel("left", "Amplitude")
        
        # Apply grid and styling
        for plot in [ecg_plot, hr_plot, wave_plot]:
            plot.showGrid(x=True, y=True, alpha=cls.DEFAULT_GRID_ALPHA)
            
        # Disable zoom/pan for all plots in Analysis tab - keep only ECG clickable for peak editing
        ecg_plot.setMouseEnabled(x=False, y=False)  # Disable zoom but keep clickable via custom event handler
        ecg_plot.getViewBox().setMenuEnabled(False) # Disable contextual menu

        hr_plot.setMouseEnabled(x=False, y=False)   # Disable zoom and pan
        hr_plot.getViewBox().setMenuEnabled(False)

        wave_plot.setMouseEnabled(x=False, y=False) # Disable zoom and pan
        wave_plot.getViewBox().setMenuEnabled(False)

        plots = {
            'ecg': ecg_plot,
            'hr': hr_plot,
            'wavelet': wave_plot
        }
        
        return layout, plots


class SignalProcessor:
    """Utility class for common signal processing operations."""
    
    @staticmethod
    def sanitize_signal_data(data: np.ndarray, 
                           clip_value: float = 1e6,
                           fill_nan: float = 0.0) -> np.ndarray:
        """
        Sanitize signal data for plotting by handling NaN/inf values and clipping.
        
        Args:
            data: Input signal data
            clip_value: Maximum absolute value allowed
            fill_nan: Value to replace NaN with
            
        Returns:
            Sanitized signal data
        """
        if data is None:
            return np.array([])
            
        data = np.asarray(data, dtype=np.float64)
        
        # Handle infinite values
        if not np.all(np.isfinite(data)):
            data = np.nan_to_num(data, 
                               nan=fill_nan, 
                               posinf=clip_value, 
                               neginf=-clip_value)
        
        # Clip extreme values
        if np.abs(data).max() > clip_value:
            data = np.clip(data, -clip_value, clip_value)
            
        return data
    
    @staticmethod
    def get_signal_with_hr_params(data_manager, 
                                 file_path: str,
                                 signal_name: str,
                                 **hr_params):
        """
        Standardized method to get signal data with proper HR parameter handling.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the data file
            signal_name: Name of the signal to retrieve
            **hr_params: HR generation parameters
            
        Returns:
            Signal object
        """
        # Only apply HR parameters to HR_GEN signals
        if signal_name.upper() == "HR_GEN":
            return data_manager.get_trace(file_path, signal_name, **hr_params)
        else:
            return data_manager.get_trace(file_path, signal_name)
    
    @staticmethod
    def downsample_for_display(data: np.ndarray, 
                              max_points: int = 5000) -> Tuple[np.ndarray, int]:
        """
        Downsample data for efficient display while preserving visual characteristics.
        
        Args:
            data: Input data array
            max_points: Maximum number of points to display
            
        Returns:
            (downsampled_data, step_size)
        """
        if len(data) <= max_points:
            return data, 1
            
        step = int(np.ceil(len(data) / max_points))
        downsampled = data[::step]
        
        return downsampled, step