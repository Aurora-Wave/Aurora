"""
Processing package for AuroraWave.

Contains modules for ECG analysis, data processing, and signal extraction.
Supports multiple peak detection strategies including wavelet-based methods
and NeuroKit2 professional algorithms.
"""

from Pyside.processing.ecg_analyzer import ECGAnalyzer
from Pyside.processing.peak_detection_strategies import (
    PeakDetectionStrategy,
    WaveletSWTStrategy,
    WaveletDWTStrategy,
    WaveletCWTStrategy,
    NeuroKit2Strategy,
    strategy_registry
)
from Pyside.processing.chunk_loader import ChunkLoader
from Pyside.processing.marker_extractor import extract_markers, save_markers_to_csv, MARKER_FUNCS
from Pyside.processing.interval_extractor import extract_event_intervals
from Pyside.processing.csv_exporter import CSVExporter

__all__ = [
    'ECGAnalyzer',
    'PeakDetectionStrategy',
    'WaveletSWTStrategy',
    'WaveletDWTStrategy', 
    'WaveletCWTStrategy',
    'NeuroKit2Strategy',
    'strategy_registry',
    'ChunkLoader', 
    'extract_markers',
    'save_markers_to_csv',
    'MARKER_FUNCS',
    'extract_event_intervals',
    'CSVExporter'
]