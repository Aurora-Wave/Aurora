# 🌊 AuroraWave - Advanced Physiological Signal Analysis Platform

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-orange.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

AuroraWave is a sophisticated desktop application for analyzing physiological signals with advanced multi-file session management, real-time visualization, and comprehensive export capabilities.

## ✨ Key Features

### 🎯 **Multi-File Session Management**
- **Simultaneous file handling**: Open and work with multiple signal files at once
- **Session persistence**: Automatically saves and restores your work sessions
- **Smart switching**: Seamlessly switch between different files and maintain state
- **Resource optimization**: Intelligent memory management with configurable limits

### 📊 **Advanced Signal Analysis**
- **Multiple file formats**: Support for `.adicht` files with extensible architecture
- **HR Generation**: Automated heart rate signal generation using multiple algorithms:
  - Stationary Wavelet Transform (SWT)
  - Discrete Wavelet Transform (DWT) 
  - Continuous Wavelet Transform (CWT)
  - NeuroKit2 integration
- **Event Detection**: Automatic extraction of tilt and cardiovascular events
- **Real-time Visualization**: High-performance plotting with chunk-based loading

### 🎨 **Professional User Interface**
- **Tabbed Interface**: Organized workspace with specialized analysis tabs
- **Interactive Navigation**: Scroll-based navigation with zoom and pan capabilities
- **Session Management**: Visual file selector with session status indicators
- **Context Menus**: Right-click actions for enhanced productivity

### 📈 **Data Export & Analysis**
- **Flexible CSV Export**: Configurable export formats with statistical calculations
- **Interval Analysis**: Export specific time segments with customizable duration
- **Statistical Measures**: Mean and maximum value calculations per time interval
- **Format Options**: Multiple export layouts (vertical, horizontal, interval-based)

### 🔧 **Configuration & Logging**
- **Persistent Configuration**: Automatic saving of user preferences and settings
- **Comprehensive Logging**: Detailed logging system with session tracking
- **Health Monitoring**: Application health checks and performance monitoring
- **User Session Tracking**: Detailed activity logging for debugging and analysisWave – Physiological Signal Analysis App (PySide6)

AuroraWave is a desktop application for loading, visualizing, and analyzing physiological signals (e.g., ECG, HR, blood pressure) from biomedical recordings. Built with PySide6, it enables clinicians and researchers to interact with physiological data through an intuitive graphical interface, without needing to write code.

---

## 🧰 Requirements

- **Python 3.11**
- Dependencies listed in `requirements.txt`

---

## 🗂️ Project Structure

```plaintext
Pyside/
│
├── main.py                                                         # Entry point for the application
│
├── config/
│   └── signals_config.json                                         # Stores last session file path and default channel selection
│
├── core/
│   ├── comments.py                                                 # EMSComment class (annotations in signals)
│   └── signal.py                                                   # Signal, HR_Gen_Signal, SignalGroup classes
│
├── data/
│   ├── aditch_loader.py                                            # Loader for .adicht LabChart files using adi.read_file
│   └── data_manager.py                                             # File and signal management, caching, metadata, HR generation
│
├── processing/
│   ├── chunk_loader.py                                             # Provides synchronous and asynchronous chunked signal access
│   ├── ecg_analyzer.py                                             # Wavelet-based R-peak detection and HR generation
│   ├── interval_extractor.py                                       # Extracts test events from annotations (e.g., Tilt, Baseline)
│   └── marker_extractor.py                                         # Computes statistics per window, event, or full signal
│
├── ui/
│   ├── analysis_tab.py                                             # Tab for general signal marker extraction
│   ├── main_window.py                                              # Main GUI window with file loading, export, tabs
│   ├── tilt_tab.py                                                 # Tab for Tilt Test protocol exploration
│   ├── viewer_tab.py                                               # Tab for scrolling visualization of multiple signals
│   └── widgets/
│   │   ├── channel_selection_dialog.py                             # Dialog to select signal channels
│   │   ├── export_markers.py                                       # Widget for exporting marker data
│   │   ├── export_selection_dialog.py                              # Dialog to select export targets
│   │   └── selectable_viewbox.py                                   # Interactive ViewBox with synchronized selection
│   │
│   │── utils/
│   │   ├── error_handler.py   
│   │   └── scroll_config.py   

```



Instalación

Para crear un ambiente virtual, se puede usar el siguiente comando:

```python
py -3.11 -m venv env
```

Luego de crear el ambiente virtual, se debe activar. En Windows, se puede usar el siguiente comando:

```cmd
.\env\Scripts\activate
```

Luego, se deben instalar las dependencias necesarias. Para ello, se puede usar el siguiente comando:

```cmd
pip install -r requirements.txt
```

Finalmente, para la compilación a .exe, se puede usar el siguiente comando:

```cmd
pyside6-deploy
```

## Licencia

MIT
