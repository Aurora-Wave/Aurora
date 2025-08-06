# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AuroraWave is a PySide6 desktop application for loading, visualizing, and analyzing physiological signals (ECG, HR, blood pressure) from biomedical recordings. It enables clinicians and researchers to interact with physiological data through an intuitive GUI without coding.

## Development Setup

Create virtual environment:
```bash
py -3.11 -m venv env
```

Activate environment (Windows):
```cmd
.\env\Scripts\activate
```

Install dependencies:
```cmd
pip install -r requirements.txt
```

Run application:
```cmd
python Pyside/main.py
```

Build executable:
```cmd
pyside6-deploy
```

## Architecture

### Core Data Flow
- **Data Loading**: File loaders in `data/` handle format-specific parsing (.adicht files via adi-reader)
- **Signal Management**: `DataManager` provides caching, metadata management, and HR generation
- **Processing**: Modular processing pipeline in `processing/` for ECG analysis, chunked loading, and marker extraction
- **Visualization**: Three main tabs (Viewer, Analysis, Tilt) with synchronized signal viewing

### Key Components

**Core Classes**:
- `Signal`: Base signal representation with time series data, units, and annotations
- `HR_Gen_Signal`: Specialized signal for heart rate with R-peak detection via wavelets
- `SignalGroup`: Container for multiple related signals
- `DataManager`: Central hub for file loading, caching, and signal retrieval

**UI Architecture**:
- `MainWindow`: Central window with tab management and file operations
- Three specialized tabs: `viewer_tab.py` (signal scrolling), `analysis_tab.py` (marker extraction), `tilt_tab.py` (tilt test protocols)
- Custom widgets in `ui/widgets/` for channel selection, export dialogs, and interactive viewboxes
- Manager classes in `ui/managers/` handle scrollbar synchronization and comment/marker management

**Processing Pipeline**:
- `ECGAnalyzer`: Wavelet-based R-peak detection and HR generation
- `ChunkLoader`: Async/sync chunked signal access for large files
- `IntervalExtractor`: Extracts test events from annotations (Tilt, Baseline)
- `MarkerExtractor`: Computes statistics per window, event, or full signal

### Signal Processing Flow
1. File loaded via appropriate loader (`AditchLoader` for .adicht files)
2. Signals cached in `DataManager` with metadata and annotations
3. HR generation on-demand using ECG analysis with configurable parameters
4. Chunked loading for efficient visualization of large datasets
5. Interactive selection and marker extraction through GUI components

### Configuration
- `signals_config.json`: Stores last session file path and default channel selections
- Environment variable `QT_LOGGING_RULES` suppresses Qt warnings
- HR generation uses LRU cache with MAX_HR_CACHE=5 limit

## File Structure Notes
- Entry point: `Pyside/main.py`
- All UI code in `Pyside/ui/` with logical separation by functionality
- Processing algorithms isolated in `Pyside/processing/`
- File format support extensible via loader registry pattern in `DataManager`