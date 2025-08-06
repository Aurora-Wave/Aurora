import sys
import os

# Add parent directory to Python path for absolute imports
# This allow to 
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PySide6.QtWidgets import QApplication
from Pyside.ui.main_window import MainWindow

# Suprimir advertencias menores de Qt
os.environ["QT_LOGGING_RULES"] = "qt.core.qobject.connect.warning=false"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
