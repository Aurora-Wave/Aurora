import sys
import os
# Add parent directory to Python path for absolute imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PySide6.QtWidgets import QApplication
from Pyside.ui.main_window import MainWindow

# Initialize logging system early
from Pyside.core.logging_config import initialize_logging, get_logger
session = initialize_logging()  # Initialize with automatic user ID
logger = get_logger("AuroraWave.Main")

# Suppress Qt warnings
os.environ["QT_LOGGING_RULES"] = "qt.core.qobject.connect.warning=false"

if __name__ == "__main__":
    try:
        logger.info("AuroraWave application starting...")
        
        app = QApplication(sys.argv)
        logger.info("Qt application initialized")
        
        window = MainWindow()
        logger.info("MainWindow created")
        
        window.show()
        logger.info("MainWindow displayed - application ready")
        
        # Run the application
        exit_code = app.exec()
        logger.info(f"Application exited with code: {exit_code}")
        
        # Shutdown logging system
        from Pyside.core import shutdown_logging
        shutdown_logging()
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Fatal error during application startup: {e}", exc_info=True)
        sys.exit(1)
