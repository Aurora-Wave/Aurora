"""
AnalysisPlotContainer - Especialización del PlotContainerWidget para AnalysisTab
Siguiendo el patrón estándar: recibe DataManager del Tab, gestiona visualización y análisis HR.
"""

import numpy as np
from typing import List, Dict, Optional
from PySide6.QtWidgets import (QWidget, QLabel, QHBoxLayout, QPushButton, 
                               QSpinBox, QComboBox, QDoubleSpinBox, QGroupBox, QVBoxLayout)
from PySide6.QtCore import QTimer

from .plot_widget import PlotContainerWidget
from Pyside.processing.chunk_loader import ChunkLoader
from Pyside.core import get_user_logger


class AnalysisPlotContainer(PlotContainerWidget):
    """
    Container de plots especializado para AnalysisTab.
    
    Responsabilidades:
    - Visualización de señales con controles de análisis HR
    - Controles específicos para parámetros HR (wavelet, level, min_rr)
    - Integración con sistema de generación HR
    - Detección y modificación de R-peaks
    
    Sigue patrón estándar:
    - Recibe DataManager del AnalysisTab
    - Solo maneja visualización y controles de análisis
    - NO gestiona carga de archivos
    """
    
    def __init__(self, parent=None):
        # Analysis-specific parameters - DEBE estar ANTES de super().__init__
        self.current_hr_params = {
            'wavelet': 'haar',
            'swt_level': 4,
            'min_rr_sec': 0.6
        }
        
        super().__init__(parent)
        self.logger = get_user_logger("AnalysisPlotContainer")
        
        # DataManager context (recibido del Tab)
        self.data_manager = None
        self.file_path: str = ""
        self.hr_params: Dict = {}
        
        # Chunk loading
        self.chunk_loader = ChunkLoader()
        self.chunk_loader.chunk_loaded.connect(self.on_chunk_loaded)
        
   
        # Y-range management for consistent scaling
        self.y_ranges: Dict[str, tuple] = {}
        
        # HR analysis state
        self.current_hr_signal = None
        self.r_peaks_visible = True
        
        # Connect signals
        self.time_changed.connect(self.load_chunk)
        self.chunk_size_changed.connect(self.load_chunk)
        
        self.logger.debug("AnalysisPlotContainer initialized")
        
    def create_controls(self) -> QWidget:
        """
        Create controls specific to AnalysisTab.
        Extends base controls with HR analysis functionality.
        """
        # Get base controls (Start, Chunk size, Position slider)
        controls_widget = super().create_controls()
        
        # Add analysis-specific controls
        controls_layout = controls_widget.layout()
        
        # HR Parameters Group
        hr_group = QGroupBox("HR Generation Parameters")
        hr_layout = QHBoxLayout(hr_group)
        
        # Wavelet selection
        hr_layout.addWidget(QLabel("Wavelet:"))
        self.wavelet_combo = QComboBox()
        self.wavelet_combo.addItems(['haar', 'db4', 'db8', 'coif2', 'coif4', 'bior2.2'])
        self.wavelet_combo.setCurrentText(self.current_hr_params['wavelet'])
        self.wavelet_combo.currentTextChanged.connect(self.on_wavelet_changed)
        hr_layout.addWidget(self.wavelet_combo)
        
        # SWT Level
        hr_layout.addWidget(QLabel("Level:"))
        self.level_spinbox = QSpinBox()
        self.level_spinbox.setRange(1, 8)
        self.level_spinbox.setValue(self.current_hr_params['swt_level'])
        self.level_spinbox.valueChanged.connect(self.on_level_changed)
        hr_layout.addWidget(self.level_spinbox)
        
        # Min RR
        hr_layout.addWidget(QLabel("Min RR (s):"))
        self.min_rr_spinbox = QDoubleSpinBox()
        self.min_rr_spinbox.setRange(0.3, 2.0)
        self.min_rr_spinbox.setSingleStep(0.1)
        self.min_rr_spinbox.setDecimals(1)
        self.min_rr_spinbox.setValue(self.current_hr_params['min_rr_sec'])
        self.min_rr_spinbox.valueChanged.connect(self.on_min_rr_changed)
        hr_layout.addWidget(self.min_rr_spinbox)
        
        # Control buttons
        self.regenerate_btn = QPushButton("🔄 Regenerate HR")
        self.regenerate_btn.clicked.connect(self.regenerate_hr_signal)
        hr_layout.addWidget(self.regenerate_btn)
        
        self.toggle_peaks_btn = QPushButton("👁 Toggle R-Peaks")
        self.toggle_peaks_btn.clicked.connect(self.toggle_r_peaks_visibility)
        hr_layout.addWidget(self.toggle_peaks_btn)
        
        controls_layout.addWidget(hr_group)
        
        # Navigation buttons for R-peaks
        peaks_group = QGroupBox("R-Peak Navigation")
        peaks_layout = QHBoxLayout(peaks_group)
        
        self.prev_peak_btn = QPushButton("◀ Prev Peak")
        self.next_peak_btn = QPushButton("Next Peak ▶")
        self.prev_peak_btn.clicked.connect(self.navigate_to_prev_peak)
        self.next_peak_btn.clicked.connect(self.navigate_to_next_peak)
        
        peaks_layout.addWidget(self.prev_peak_btn)
        peaks_layout.addWidget(self.next_peak_btn)
        
        controls_layout.addWidget(peaks_group)
        
        return controls_widget
        
    def set_data_context(self, data_manager, file_path: str, hr_params: Dict = None):
        """Configurar contexto de datos desde AnalysisTab"""
        self.data_manager = data_manager
        self.file_path = file_path
        self.hr_params = hr_params or {}
        
        # Update current HR params with provided params
        if hr_params:
            self.current_hr_params.update(hr_params)
            self.update_controls_from_params()
        
        self.logger.debug(f"Data context set: file={file_path}, hr_params={self.current_hr_params}")
        
        # Calculate duration from ECG signal
        if self.data_manager and self.file_path:
            try:
                ecg = self.data_manager.get_trace(self.file_path, "ECG")
                self.duration = len(ecg.data) / ecg.fs
                self.set_duration(self.duration)
                
                # Generate initial HR signal
                self.generate_hr_signal()
                
                # Calculate Y-ranges for all target signals
                self.calculate_y_ranges()
                
                # Enable comments for plots (focus on HR_gen for AnalysisTab)
                if self.plots:
                    # For AnalysisTab, enable comments only for HR-related signals by default
                    hr_signals = [signal for signal in self.target_signals if 'HR' in signal.upper()]
                    if hr_signals:
                        self.enable_comments_for_signals(file_path, hr_signals)
                    else:
                        # If no HR signals, enable for all plots
                        self.enable_comments_for_all_plots(file_path, True)
                
                self.logger.debug(f"Duration set to {self.duration:.2f}s")
            except Exception as e:
                self.logger.error(f"Error setting data context: {e}")
                
    def update_controls_from_params(self):
        """Update control widgets from current HR params"""
        try:
            if hasattr(self, 'wavelet_combo'):
                self.wavelet_combo.setCurrentText(self.current_hr_params.get('wavelet', 'haar'))
            if hasattr(self, 'level_spinbox'):
                self.level_spinbox.setValue(self.current_hr_params.get('swt_level', 4))
            if hasattr(self, 'min_rr_spinbox'):
                self.min_rr_spinbox.setValue(self.current_hr_params.get('min_rr_sec', 0.6))
        except Exception as e:
            self.logger.error(f"Error updating controls: {e}")
            
    def on_wavelet_changed(self, wavelet: str):
        """Handle wavelet parameter change"""
        self.current_hr_params['wavelet'] = wavelet
        self.logger.debug(f"Wavelet changed to: {wavelet}")
        
    def on_level_changed(self, level: int):
        """Handle level parameter change"""
        self.current_hr_params['swt_level'] = level
        self.logger.debug(f"Level changed to: {level}")
        
    def on_min_rr_changed(self, min_rr: float):
        """Handle min RR parameter change"""
        self.current_hr_params['min_rr_sec'] = min_rr
        self.logger.debug(f"Min RR changed to: {min_rr}")
        
    def regenerate_hr_signal(self):
        """Regenerate HR signal with current parameters"""
        try:
            if not self.data_manager or not self.file_path:
                return
                
            self.logger.info(f"Regenerating HR with params: {self.current_hr_params}")
            
            # Generate new HR signal
            self.generate_hr_signal()
            
            # Update DataManager cache with new parameters
            self.data_manager.update_hr_cache(self.file_path, self.current_hr_signal, **self.current_hr_params)
            
            # Recalculate Y-ranges for HR signals
            self.calculate_y_ranges()
            
            # Reload current chunk with new HR
            self.load_chunk()
            
            self.logger.info("HR signal regenerated successfully")
            
        except Exception as e:
            self.logger.error(f"Error regenerating HR signal: {e}")
            
    def generate_hr_signal(self):
        """Generate HR signal with current parameters"""
        try:
            if not self.data_manager or not self.file_path:
                return
                
            # Get HR signal with current parameters
            self.current_hr_signal = self.data_manager.get_trace(
                self.file_path, 
                "HR_GEN", 
                **self.current_hr_params
            )
            
            self.logger.debug(f"HR signal generated with {len(getattr(self.current_hr_signal, 'r_peaks', []))} R-peaks")
            
        except Exception as e:
            self.logger.error(f"Error generating HR signal: {e}")
            self.current_hr_signal = None
            
    def toggle_r_peaks_visibility(self):
        """Toggle R-peaks visibility on plots"""
        self.r_peaks_visible = not self.r_peaks_visible
        
        # Update button text
        text = "👁 Show R-Peaks" if not self.r_peaks_visible else "👁 Hide R-Peaks"
        self.toggle_peaks_btn.setText(text)
        
        # Refresh plots to show/hide peaks
        self.load_chunk()
        
        self.logger.debug(f"R-peaks visibility toggled: {self.r_peaks_visible}")
        
    def navigate_to_prev_peak(self):
        """Navigate to previous R-peak"""
        if not self.current_hr_signal or not hasattr(self.current_hr_signal, 'r_peaks'):
            return
            
        r_peaks = self.current_hr_signal.r_peaks
        current_sample = int(self.start_time * self.current_hr_signal.fs)
        
        # Find previous peak before current position
        prev_peaks = r_peaks[r_peaks < current_sample]
        
        if len(prev_peaks) > 0:
            target_peak = prev_peaks[-1]  # Most recent previous peak
            target_time = target_peak / self.current_hr_signal.fs
            self.navigate_to_time_centered(target_time)
            
    def navigate_to_next_peak(self):
        """Navigate to next R-peak"""
        if not self.current_hr_signal or not hasattr(self.current_hr_signal, 'r_peaks'):
            return
            
        r_peaks = self.current_hr_signal.r_peaks
        current_sample = int(self.start_time * self.current_hr_signal.fs)
        
        # Find next peak after current position
        next_peaks = r_peaks[r_peaks > current_sample]
        
        if len(next_peaks) > 0:
            target_peak = next_peaks[0]  # Earliest next peak
            target_time = target_peak / self.current_hr_signal.fs
            self.navigate_to_time_centered(target_time)
            
    def navigate_to_time_centered(self, target_time: float):
        """Navigate to specific time, centering it in the view"""
        # Center the target time in the view
        new_start_time = max(0, target_time - self.chunk_size / 2)
        
        # Update controls and load chunk
        self.start_time = new_start_time
        self.start_spinbox.setValue(int(new_start_time))
        self.position_slider.setValue(int(new_start_time))
        
        self.load_chunk()
        
        self.logger.debug(f"Navigated to time {target_time:.2f}s (centered)")
        
    def calculate_y_ranges(self):
        """Calculate global Y-ranges for consistent scaling"""
        self.y_ranges.clear()
        
        if not self.data_manager or not self.file_path:
            return
            
        for signal_name in self.target_signals:
            try:
                # Get appropriate signal data
                if signal_name.upper() == "HR_GEN":
                    sig = self.data_manager.get_trace(self.file_path, signal_name, **self.current_hr_params)
                else:
                    sig = self.data_manager.get_trace(self.file_path, signal_name)
                    
                # Calculate range with safety checks
                data = sig.data
                valid_data = data[np.isfinite(data)]
                
                if len(valid_data) > 0:
                    y_min, y_max = np.min(valid_data), np.max(valid_data)
                    
                    # Safety checks and padding
                    if not np.isfinite(y_min) or not np.isfinite(y_max):
                        y_min, y_max = -1.0, 1.0
                    elif abs(y_max - y_min) > 1e6:
                        y_center = (y_min + y_max) / 2
                        y_min, y_max = y_center - 1e5, y_center + 1e5
                    elif y_min == y_max:
                        padding = max(abs(y_min) * 0.1, 0.1)
                        y_min -= padding
                        y_max += padding
                    else:
                        # Add 5% padding
                        padding = (y_max - y_min) * 0.05
                        y_min -= padding
                        y_max += padding
                        
                    self.y_ranges[signal_name] = (y_min, y_max)
                    self.logger.debug(f"Y-range for {signal_name}: [{y_min:.3f}, {y_max:.3f}]")
                else:
                    self.y_ranges[signal_name] = (-1.0, 1.0)
                    self.logger.warning(f"No valid data for {signal_name}, using default range")
                    
            except Exception as e:
                self.logger.error(f"Error calculating Y-range for {signal_name}: {e}")
                self.y_ranges[signal_name] = (-1.0, 1.0)
                
    def load_chunk(self):
        """Load current chunk using ChunkLoader"""
        if not self.data_manager or not self.file_path or not self.target_signals:
            return
            
        # Request chunk from ChunkLoader with current HR params
        self.chunk_loader.request_chunk(
            data_manager=self.data_manager,
            file_path=self.file_path,
            channel_names=self.target_signals,
            start_sec=self.start_time,
            duration_sec=self.chunk_size,
            hr_params=self.current_hr_params
        )
        
        self.logger.debug(f"Requested chunk: start={self.start_time}, duration={self.chunk_size}")
        
    def on_chunk_loaded(self, start: float, end: float, data_dict: Dict):
        """Handle chunk loaded from ChunkLoader"""
        self.logger.debug(f"Chunk loaded: {start:.2f} - {end:.2f}s, signals: {list(data_dict.keys())}")
        
        # Update each plot with its data (same as ViewerPlotContainer)
        for signal_name in self.target_signals:
            if signal_name not in data_dict:
                self.logger.warning(f"Signal {signal_name} not in loaded chunk")
                continue
                
            plot = self.get_plot_by_signal(signal_name)
            if not plot:
                continue
                
            try:
                # Get signal data
                sig_data = data_dict[signal_name]
                
                # For chunk loaded data, we expect it to be processed
                if hasattr(sig_data, 'data') and hasattr(sig_data, 'fs'):
                    # Signal object
                    fs = sig_data.fs
                    y_data = sig_data.data
                else:
                    # Raw data - get fs from data manager
                    sig = self.data_manager.get_trace(
                        self.file_path, 
                        signal_name, 
                        **self.current_hr_params if signal_name.upper() == "HR_GEN" else {}
                    )
                    fs = sig.fs
                    y_data = sig_data
                    
                # Create time array and process data (same as ViewerPlotContainer)
                expected_len = int(self.chunk_size * fs)
                
                # Handle data preparation
                y_data = np.asarray(y_data)
                if not np.all(np.isfinite(y_data)):
                    y_data = np.nan_to_num(y_data, nan=0.0, posinf=1e6, neginf=-1e6)
                    
                if np.abs(y_data).max() > 1e6:
                    y_data = np.clip(y_data, -1e6, 1e6)
                    
                # Ensure correct length
                if len(y_data) < expected_len:
                    y_data = np.concatenate([
                        y_data, 
                        np.full(expected_len - len(y_data), np.nan, dtype=np.float32)
                    ])
                    
                # Create time array
                t = np.arange(len(y_data)) / fs + self.start_time
                
                # Downsampling for performance
                max_points = 5000
                if len(y_data) > max_points:
                    step = int(np.ceil(len(y_data) / max_points))
                    y_data = y_data[::step]
                    t = t[::step]
                    
                # Update plot data
                plot.curve.setData(t, y_data)
                plot.plot_widget.setXRange(start, end, padding=0)
                
                # Apply consistent Y-range
                y_min, y_max = self.y_ranges.get(signal_name, (-1.0, 1.0))
                plot.plot_widget.setYRange(y_min, y_max, padding=0)
                
                # Update plot label with units
                self.update_plot_label(plot, signal_name)
                
                # Add R-peaks if this is ECG and peaks are visible
                if signal_name.upper() == "ECG" and self.r_peaks_visible:
                    self.add_r_peaks_to_plot(plot, start, end)
                
            except Exception as e:
                self.logger.error(f"Error updating plot {signal_name}: {e}")
                
        # Comments are automatically updated via global signal system
        # No need for manual marker management
        
    def add_r_peaks_to_plot(self, plot, start_time: float, end_time: float):
        """Add R-peak markers to ECG plot"""
        try:
            if not self.current_hr_signal or not hasattr(self.current_hr_signal, 'r_peaks'):
                return
                
            r_peaks = self.current_hr_signal.r_peaks
            fs = self.current_hr_signal.fs
            
            # Find peaks in current time window
            start_sample = int(start_time * fs)
            end_sample = int(end_time * fs)
            
            visible_peaks = r_peaks[(r_peaks >= start_sample) & (r_peaks <= end_sample)]
            
            if len(visible_peaks) > 0:
                # Convert to time
                peak_times = visible_peaks / fs
                
                # Add vertical lines for each peak
                for peak_time in peak_times:
                    # This would be implemented with the marker system
                    # For now, just log
                    pass
                    
                self.logger.debug(f"Added {len(visible_peaks)} R-peaks to ECG plot")
                
        except Exception as e:
            self.logger.error(f"Error adding R-peaks: {e}")
            
    def update_plot_label(self, plot, signal_name: str):
        """Update plot label with appropriate units"""
        try:
            # Get units from signal
            if signal_name.upper() == "HR_GEN":
                sig = self.data_manager.get_trace(self.file_path, signal_name, **self.current_hr_params)
            else:
                sig = self.data_manager.get_trace(self.file_path, signal_name)
                
            units = getattr(sig, 'units', '')
            
            # Clean and validate units to prevent duplication
            if units:
                units_str = str(units).strip()
                
                # Handle cases where units might be duplicated
                if ',' in units_str:
                    unique_units = list(set(u.strip() for u in units_str.split(',') if u.strip()))
                    units_str = ', '.join(unique_units)
                
                plot.plot_widget.setLabel("left", f"{signal_name} ({units_str})")
            else:
                plot.plot_widget.setLabel("left", signal_name)
                
        except Exception as e:
            self.logger.error(f"Error updating plot label for {signal_name}: {e}")
            plot.plot_widget.setLabel("left", signal_name)
            
    def toggle_comments_for_signals(self, signal_names: List[str]):
        """Toggle comment visibility for specific signals."""
        if not self.file_path:
            return
            
        try:
            self.enable_comments_for_signals(self.file_path, signal_names)
            self.logger.info(f"Toggled comments for signals: {signal_names}")
        except Exception as e:
            self.logger.error(f"Error toggling comments for signals: {e}")
            
    def update_hr_params(self, hr_params: Dict):
        """Update HR parameters and reload current chunk"""
        self.current_hr_params.update(hr_params)
        self.hr_params = self.current_hr_params.copy()
        
        # Update controls
        self.update_controls_from_params()
        
        self.logger.debug(f"HR params updated: {self.current_hr_params}")
        
        # Regenerate HR signal with new params
        self.generate_hr_signal()
        
        # Recalculate Y-ranges for HR_GEN signals
        if any('HR' in signal.upper() for signal in self.target_signals):
            self.calculate_y_ranges()
            
        # Reload current chunk
        self.load_chunk()
        
    def get_current_hr_params(self) -> Dict:
        """Get current HR parameters"""
        return self.current_hr_params.copy()
        
    def refresh_display(self):
        """Refresh the entire display"""
        self.generate_hr_signal()
        self.calculate_y_ranges()
        self.load_chunk()
        
    def set_signals(self, signal_names: List[str]):
        """Override to integrate with data loading"""
        super().set_signals(signal_names)
        
        # Calculate Y-ranges for new signals
        if self.data_manager and self.file_path:
            self.calculate_y_ranges()
            
            # Enable comments for new plots (focus on HR signals for AnalysisTab)
            hr_signals = [signal for signal in signal_names if 'HR' in signal.upper()]
            if hr_signals:
                self.enable_comments_for_signals(self.file_path, hr_signals)
            else:
                # If no HR signals, enable for all plots
                self.enable_comments_for_all_plots(self.file_path, True)
            
        # Load current chunk for new signals
        self.load_chunk()