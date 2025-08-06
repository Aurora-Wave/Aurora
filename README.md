# AuroraWave – Physiological Signal Analysis App (PySide6)

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
