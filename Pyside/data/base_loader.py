from abc import ABC, abstractmethod

class BaseLoader(ABC):
    @abstractmethod
    def load(self, path: str):
        """Initialize loader and parse necessary file metadata."""
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return basic metadata about the file (channels, duration, fs, etc)."""
        pass
    @abstractmethod
    def get_full_trace(self, channel: str):
        """Return the complete signal (Signal or ECGSignal object)."""
        pass

    @abstractmethod
    def get_all_comments(self) -> list:
        """Return all EMS-style comments from the file."""
        pass
