"""
Aurora - Main entry point for the refactored application.
Multi-session signal analysis with clean architecture.
"""

import sys
import os

# Add parent directory to Python path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PySide6.QtWidgets import QApplication
from aurora.ui.main_window import MainWindow

def main():
    """Main entry point for Aurora application"""
    # Suppress Qt warnings
    os.environ["QT_LOGGING_RULES"] = "qt.core.qobject.connect.warning=false"

    # TODO: Initialize logging when implemented
    # from aurora.core.logging_config import initialize_logging, get_logger
    # session = initialize_logging()
    # logger = get_logger("Aurora.Main")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    exit_code = app.exec()

    # TODO: Shutdown logging when implemented
    # shutdown_logging()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()