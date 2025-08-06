"""
UI utilities package for AuroraWave.

Contains utility modules for error handling, configuration, and UI helpers.
"""

from Pyside.ui.utils.error_handler import ErrorHandler, error_handler
from Pyside.ui.utils.scroll_config import ScrollConfig

__all__ = [
    'ErrorHandler',
    'error_handler', 
    'ScrollConfig'
]