# Aurora PySide6 App

## Requisitos

Python version = 3.11

## Estructura del proyecto

- `main.py`: Punto de entrada de la aplicación.
- `ui/`: Componentes de la interfaz gráfica (ventanas, pestañas, widgets personalizados).
- `processing/`: Módulos de procesamiento y análisis de datos.
- `data/`: Carga y manejo de archivos de datos.
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
