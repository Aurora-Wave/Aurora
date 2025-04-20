# Aurora


## Requisitos
Python version = 3.9.13 (Obligatorio)

## Instalación


Luego de clonar el repositorio, se puede optar por crear un ambiente virtual o no. Si se opta por crear un ambiente virtual, se recomienda usar `venv` o `virtualenv`. Para crear un ambiente virtual, se puede usar el siguiente comando:

```python
python -m venv env
```

Luego de crear el ambiente virtual, se debe activar. En Windows, se puede usar el siguiente comando:

```
.\env\Scripts\activate
```

Luego, se deben instalar las dependencias necesarias. Para ello, se puede usar el siguiente comando:

```python
pip install -r requirements.txt
```

Finalmente, se instala el paquete para poder convertir el archivo .py a .exe. Para ello, se puede usar el siguiente comando:

```python
pip install pyinstaller
```

en la carpeta 'Aurora'.

## Ejecución

Para ejecutar el programa, se puede usar el siguiente comando:

```python
python src/dnb/main.py
```

Esto abrirá una ventana de la aplicación.

## Puntos importantes

- El programa está diseñado para funcionar en Windows. No se garantiza que funcione en otros sistemas operativos.
- El programa está diseñado para funcionar en Python 3.9.13. No se garantiza que funcione en otras versiones de Python.
- El programa está diseñado para funcionar con las librerías especificadas en el archivo `requirements.txt`. No se garantiza que funcione con otras versiones de las librerías.
- Hay que ir actualizando lo trabajado en la carpeta 'src/dnb' para que el programa funcione correctamente. Por lo que después de haber realizado algún cambio, se debe volver a ejecutar el comando `pip install .` en la carpeta 'Aurora' para que los cambios se vean reflejados en el programa.