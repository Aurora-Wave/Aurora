# Aurora PySide6 App

## Requisitos

Python version = 3.11

## Estructura del proyecto

- `main.py`: Punto de entrada de la aplicación.

- `core/`: Signal, SignalGroup, and related logic
  - `signal.py`: File loading, conversion, and orchestration
  - `signal_group.py`: Aditch file loader
  
- `data/`: File loading, conversion, and orchestration
  - `data_manager.py`: File loading, conversion, and orchestration
  - `aditch_loader.py`: Aditch file loader
  - `csv_loader.py`: csv file loader
  - `EDF_loader.py`: EDF file loader
  
- `processing/`: Módulos de procesamiento y análisis de datos.
   - `chunk_loader.py`: c
   - `ecg_analyzer.py`: ecg functionality
  
- `ui/`: Componentes de la interfaz gráfica (ventanas, pestañas, widgets personalizados).
  - `widgets/`: Widget folder
  - `ecg_tab.py`
  - `main_window.py`
  

  

  

  
- `requirements.txt`: Dependencias del proyecto.

## Instalación

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
