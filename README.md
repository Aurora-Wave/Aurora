# Aurora

## Requisitos

Python version = 3.9.13 (Obligatorio)

## Instalación

Luego de clonar el repositorio, se puede optar por crear un ambiente virtual o no. Si se opta por crear un ambiente virtual, se recomienda usar `venv` o `virtualenv`. Para crear un ambiente virtual, se puede usar el siguiente comando:

```python
py -3.9 -m venv env
```

Luego de crear el ambiente virtual, se debe activar. En Windows, se puede usar el siguiente comando:

```cmd
.\env\Scripts\activate
```

Luego, se deben instalar las dependencias necesarias. Para ello, se puede usar el siguiente comando:

```cmd
pip install -r requirements.txt
```

Finalmente, se instala el paquete para poder convertir el archivo .py a .exe. Para ello, se puede usar el siguiente comando:

```cmd
pip install .
```

en la carpeta 'Aurora'.

## Ejecución

### Ejecución completa (Versión .exe)

Para ejecutar el programa, se puede usar el siguiente comando:

```pip
python src/dnb/main.py
```

Esto abrirá una aplicación.

### Ejecución debug (Versión web)

Cuando se quiera ejecutar el programa en modo web, se puede usar el siguiente comando:

```pip
python src/dnb/server.py
```

Esto abrirá una ventana del navegador con la aplicación web. En la consola se mostrará el puerto en el que se está ejecutando la aplicación.

## Puntos importantes

- El programa está diseñado para funcionar en Windows. No se garantiza que funcione en otros sistemas operativos.
- El programa está diseñado para funcionar en Python 3.9.13. No se garantiza que funcione en otras versiones de Python.
- El programa está diseñado para funcionar con las librerías especificadas en el archivo `requirements.txt`. No se garantiza que funcione con otras versiones de las librerías.
