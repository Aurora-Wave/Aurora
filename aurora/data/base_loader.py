"""
BaseLoader - Abstract base class for data loaders.
Copied from Pyside for aurora structure.
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseLoader(ABC):
    """Abstract base class for data file loaders."""
    
    @abstractmethod
    def load(self, path: str):
        """Initialize loader and parse necessary file metadata."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict:
        """Return basic metadata about the file (channels, duration, fs, etc)."""
        pass
        
    @abstractmethod
    def get_full_trace(self):
        """Return the complete signal (Signal or ECGSignal object)."""
        pass

    @abstractmethod
    def get_all_comments(self) -> List:
        """Return all EMS-style comments from the file."""
        pass