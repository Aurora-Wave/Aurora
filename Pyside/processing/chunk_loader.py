"""
chunk_loader.py
<<<<<<< Updated upstream
--------------
Carga eficiente de fragmentos (chunks) de señales fisiológicas desde archivos .adicht.
Permite cargar solo la porción necesaria para visualización eficiente.
=======
---------------
Efficient loading of chunks of physiological signals using the new SignalGroup structure.
>>>>>>> Stashed changes
"""

from PySide6.QtCore import QObject, Signal as QtSignal
import numpy as np
<<<<<<< Updated upstream
from data.adicht_loader import get_trace_from_path

class ChunkLoader(QObject):
    """
    Cargador de fragmentos (chunks) de señales fisiológicas.
    Permite cargar solo la porción de datos necesaria para visualización eficiente.
=======
from data.adicht_loader import load_adicht


class ChunkLoader(QObject):
    """
    Chunk loader for physiological signals.
    Loads only the necessary data portion for efficient visualization.
    Compatible with the new SignalGroup structure.
>>>>>>> Stashed changes
    """
    chunk_loaded = Signal(int, int, dict)  # start_idx, end_idx, {canal: datos}

<<<<<<< Updated upstream
    def __init__(self, file_path, canales, chunk_size, parent=None):
        """
        Args:
            file_path (str): Ruta absoluta del archivo .adicht.
            canales (list): Lista de nombres de señales a cargar.
            chunk_size (int): Duración del chunk en segundos.
            parent: QObject padre (opcional).
=======
    chunk_loaded = QtSignal(int, int, dict)  # start_sec, end_sec, {channel_name: chunk}

    def __init__(self, file_path, channel_names, chunk_size, parent=None, signal_group=None):
        """
        Args:
            file_path (str): Path to .adicht file.
            channel_names (list[str]): Names of channels to extract.
            chunk_size (int): Chunk duration in seconds.
            parent: Optional parent object.
            signal_group (SignalGroup): Preloaded signals (optional).
>>>>>>> Stashed changes
        """
        super().__init__(parent)
        self.file_path = file_path
        self.canales = canales
        self.chunk_size = chunk_size
<<<<<<< Updated upstream
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
=======
        self.signal_group = signal_group
        self._cache = {}  # (channel_name, start, end): data

    def set_signal_group(self, signal_group):
        """Update the SignalGroup object used for chunking."""
        self.signal_group = signal_group

    def load_signal_group(self):
        """Load the signal group from disk if not yet available."""
        if self.signal_group is None:
            self.signal_group = load_adicht(self.file_path)

    def request_chunk(self, start_sec, end_sec):
        """Emit a chunk of data between start_sec and end_sec for all requested channels."""
        self.load_signal_group()
        result = {}

        for name in self.channel_names:
            signal = self.signal_group.get(name)
            if signal is not None:
                fs = signal.fs
                full_data = signal.get_full_signal()
                start_idx = int(start_sec * fs)
                end_idx = int(end_sec * fs)
                chunk = full_data[start_idx:end_idx]
                result[name] = chunk.astype(np.float32)

>>>>>>> Stashed changes
        self.chunk_loaded.emit(start_sec, end_sec, result)
