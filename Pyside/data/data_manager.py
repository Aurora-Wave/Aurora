from core.signal import Signal, SignalGroup
from data.adicht_loader import load_adicht
#from data.csv_loader import load_csv
#from data.edf_loader import load_edf

class DataManager:
    """
    Orchestrates the loading of physiological data files.
    Selects the appropriate loader based on file extension and returns a SignalGroup.
    """

    def __init__(self):
        # File extension to loader function map
        self.loaders = {
            ".adicht": load_adicht,
            #".csv": load_csv,
            #".edf": load_edf
        }

    def load(self, path, preload=True):
        """
        Load a data file and return a SignalGroup.

        Args:
            path (str): File path to load.
            preload (bool): Whether to load all data into memory immediately (if supported).

        Returns:
            SignalGroup: A group of Signal objects.
        """
        ext = "." + path.split(".")[-1].lower()
        loader = self.loaders.get(ext)

        if not loader:
            raise ValueError(f"Unsupported file extension: {ext}")

        # Load raw signals from specific loader
        raw_signals = loader(path, preload)

        # Wrap as SignalGroup and return
        return SignalGroup(raw_signals)
