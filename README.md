# 🌊 AuroraWave - Advanced Physiological Signal Analysis Platform

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-orange.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

AuroraWave is a sophisticated desktop application for analyzing physiological signals (ECG, HR, blood pressure, etc.) with advanced session management, real-time visualization, and interactive comment system.

## ✨ Key Features

### 📊 **Advanced Signal Analysis**
- **File Format Support**: Native `.adicht` LabChart files with extensible loader architecture
- **HR Generation**: Automated heart rate signal generation using advanced algorithms:
  - Stationary Wavelet Transform (SWT) for R-peak detection
  - Multiple wavelet-based approaches (DWT, CWT)
  - NeuroKit2 integration for more detection strategy (WIP)
- **Event Detection**: Automatic extraction of physiological events from annotations
- **Real-time Visualization**: High-performance plotting with intelligent chunk loading

### 💬 **Interactive Comment System**
- **Dual-structure Architecture**: Event-driven comment system with O(1) CRUD operations
- **Visual Markers**: Comment annotations displayed across all signal plots
- **Time Navigation**: Click comments to navigate to specific time points
- **User Comments**: Add, edit, and delete custom annotations with intelligent ID management
- **Cross-tab Synchronization**: Comments update simultaneously across all interface tabs

### 🎨 **Professional User Interface**
- **Tabbed Workspace**: Specialized tabs for viewing, events analysis, and future expansions
- **Interactive Navigation**: Scroll-based navigation with zoom, pan, and time selection
- **Session Management**: Single-session architecture with comprehensive file management
- **Context Menus**: Right-click actions for enhanced productivity and comment management

### 📈 **Data Export & Analysis**
- **Flexible Export**: CSV export with configurable formats and statistical calculations
- **Interval Analysis**: Export specific time segments with customizable duration
- **Statistical Measures**: Mean and maximum value calculations per time interval
- **Multiple Formats**: Support for various export layouts and data structures

### 🔧 **Robust Architecture**
- **Event-driven Design**: Qt signals/slots for reactive UI updates and component decoupling
- **Modular Structure**: Clean separation between data management, UI, and processing layers
- **Comprehensive Logging**: Detailed logging system with session tracking and debug capabilities
- **Performance Optimization**: Intelligent caching, binary search algorithms, and memory management

---

## 🧰 Requirements

- **Python 3.11**
- Dependencies listed in `requirements.txt`

---

## 🗂️ Project Structure

```plaintext
aurora/
│
├── main.py                                                         # Entry point for the application
│
├── core/
│   ├── comments.py                                                 # EMSComment class and CommentManager (CRUD business logic)
│   ├── config_manager.py                                           # Configuration management and persistence
│   ├── logging_config.py                                           # Logging system configuration
│   ├── session.py                                                  # Session management and file loading
│   ├── session_manager.py                                          # Global session management
│   └── signal.py                                                   # Signal classes and data structures
│
├── data/
│   ├── aditch_loader.py                                            # Loader for .adicht LabChart files using adi-reader
│   ├── base_loader.py                                              # Abstract base loader interface
│   ├── data_manager.py                                             # File and signal management, cache updates only
│   └── edf_loader.py                                               # Loader for EDF files (extensible architecture)
│
├── processing/
│   ├── chunk_loader.py                                             # Optimized chunk loading with intelligent downsampling
│   ├── ecg_analyzer.py                                             # Wavelet-based R-peak detection and HR generation
│   ├── hemodynamic_analyzer.py                                     # Hemodynamic signal analysis
│   ├── interval_extractor.py                                       # Event extraction from annotations
│   └── peak_detection_strategies.py                                # Multiple peak detection algorithms
│
├── ui/
│   ├── main_window.py                                              # Main GUI window with session management
│   │
│   ├── dialogs/
│   │   ├── channel_selection_dialog.py                             # Dialog to select signal channels
│   │   ├── config_dialog.py                                        # Configuration settings dialog
│   │   ├── export_config_dialog.py                                 # Export configuration dialog
│   │   └── file_loader_dialog.py                                   # File loading dialog
│   │
│   ├── managers/
│   │   └── plot_style_manager.py                                   # Plot styling and theme management
│   │
│   ├── tabs/
│   │   ├── events_tab.py                                           # Tab for event analysis and comment management
│   │   ├── session_tab_host.py                                     # Tab container for session management
│   │   ├── viewer_tab.py                                           # Tab for signal visualization
│   │   └── visualization_base_tab.py                               # Base class for visualization tabs
│   │
│   ├── utils/
│   │   ├── context_menu.py                                         # Context menu utilities
│   │   └── selectable_viewbox.py                                   # Interactive ViewBox with selection
│   │
│   └── widgets/
│       ├── comment_list_widget.py                                  # Comment table and CRUD interface
│       ├── custom_plot.py                                          # Custom plot widget with PyQtGraph
│       └── plot_container_widget.py                                # Container for multiple signal plots with markers
│
├── config/
│   └── aurora_config.json                                          # Application configuration file
│
├── logs/                                                           # Application logs directory
│
└── uploaded_files/                                                 # Directory for uploaded data files
```



## 🚀 Installation

### Prerequisites
- **Python 3.11+** installed on your system
- **Windows** operating system
- **Linux and Mac** (WIP)

### Setup Steps

1. **Create Virtual Environment**
   ```cmd
   # Option 1: Using .venv directory
   py -3.11 -m venv .venv
   
   # Option 2: Using env directory
   py -3.11 -m venv env
   ```

2. **Activate Virtual Environment**
   ```cmd
   # CMD - if using .venv
   .venv\Scripts\activate
   
   # CMD - if using env
   env\Scripts\activate
   ```
   
   ```powershell
   # PowerShell - if using .venv
   .venv\Scripts\Activate.ps1
   
   # PowerShell - if using env
   env\Scripts\Activate.ps1
   ```

3. **Install Dependencies**
   ```cmd
   pip install -r requirements.txt
   ```

4. **Run Application**
   ```cmd
   python aurora/main.py
   ```

## 📄 License

MIT License - See LICENSE file for details
