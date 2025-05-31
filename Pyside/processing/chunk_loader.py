"""
chunk_loader.py
--------------
Carga eficiente de fragmentos (chunks) de señales fisiológicas desde archivos .adicht.
Permite cargar solo la porción necesaria para visualización eficiente.
"""

from PySide6.QtCore import QObject, Signal
import numpy as np
from data.adicht_loader import get_trace_from_path

class ChunkLoader(QObject):
    """
    Cargador de fragmentos (chunks) de señales fisiológicas.
    Permite cargar solo la porción de datos necesaria para visualización eficiente.
    """
    chunk_loaded = Signal(int, int, dict)  # start_idx, end_idx, {canal: datos}

    def __init__(self, file_path, canales, chunk_size, parent=None):
        """
        Args:
            file_path (str): Ruta absoluta del archivo .adicht.
            canales (list): Lista de nombres de señales a cargar.
            chunk_size (int): Duración del chunk en segundos.
            parent: QObject padre (opcional).
        """
        super().__init__(parent)
        self.file_path = file_path
        self.canales = canales
        self.chunk_size = chunk_size
        self.trace = None
        self._cache = {}  # (canal, start, end): datos

    def load_trace(self):
        """
        Carga el archivo .adicht si no está cargado.
        """
        self.trace = get_trace_from_path(self.file_path)

    def request_chunk(self, start_sec, end_sec):
        """
        Solicita un fragmento de datos para los canales seleccionados.
        Args:
            start_sec (int): Segundo inicial del chunk.
            end_sec (int): Segundo final del chunk.
        """
        if self.trace is None:
            self.load_trace()
        result = {}
        for canal in self.canales:
            for sig in self.trace.Signal:
                if canal.upper() in sig.Name.upper():
                    fs = getattr(sig, 'TSR', 1000)
                    full_signal = np.concatenate([sig.BB, sig.ProData, sig.AB])
                    start_idx = int(start_sec * fs)
                    end_idx = int(end_sec * fs)
                    chunk = full_signal[start_idx:end_idx]
                    result[canal] = chunk.astype(np.float32)
        self.chunk_loaded.emit(start_sec, end_sec, result)
