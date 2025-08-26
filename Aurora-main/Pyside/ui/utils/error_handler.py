"""
error_handler.py
---------------
Sistema de manejo de errores y logging mejorado para AuroraWave
"""

import logging
import sys
import os
import traceback
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, Signal


class ErrorHandler(QObject):
    """Manejador centralizado de errores y logging."""

    # Señal para notificar errores a la UI
    error_occurred = Signal(str, str)  # (title, message)

    def __init__(self, app_name="AuroraWave"):
        super().__init__()
        self.app_name = app_name
        self.setup_logging()

    def setup_logging(self):
        """Configurar sistema de logging con archivos rotativos."""
        # Crear directorio de logs si no existe
        log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        os.makedirs(log_dir, exist_ok=True)

        # Configurar archivo de log con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"aurora_wave_{timestamp}.log")

        # Configurar logger principal
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(logging.DEBUG)

        # Limpiar handlers existentes
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Handler para archivo
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Handler para consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formato de log
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info(f"=== {self.app_name} Session Started ===")
        self.logger.info(f"Log file: {log_file}")

    def install_global_handler(self, main_window=None):
        """Instalar manejador global de excepciones."""
        self.main_window = main_window

        def exception_hook(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Permitir Ctrl+C
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            # Registrar error completo
            error_msg = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            self.logger.critical(f"EXCEPCIÓN NO CAPTURADA:\n{error_msg}")

            # Mostrar al usuario
            self._show_error_dialog(
                "Error Crítico", f"{exc_type.__name__}: {str(exc_value)}", error_msg
            )

        sys.excepthook = exception_hook

    def _show_error_dialog(self, title, message, details=None):
        """Mostrar diálogo de error al usuario."""
        try:
            if self.main_window:
                msg_box = QMessageBox(self.main_window)
            else:
                msg_box = QMessageBox()

            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)

            if details:
                msg_box.setDetailedText(details)

            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()

        except Exception as e:
            # Fallback si falla el QMessageBox
            print(f"ERROR CRÍTICO: {title} - {message}")
            if details:
                print(f"Detalles: {details}")

    def log_operation(self, operation_name, *args, **kwargs):
        """Decorator para registrar operaciones importantes."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                self.logger.info(f"INICIANDO: {operation_name}")
                try:
                    result = func(*args, **kwargs)
                    self.logger.info(f"COMPLETADO: {operation_name}")
                    return result
                except Exception as e:
                    self.logger.error(
                        f"ERROR EN {operation_name}: {str(e)}", exc_info=True
                    )
                    self._show_error_dialog(
                        f"Error en {operation_name}", str(e), traceback.format_exc()
                    )
                    raise

            return wrapper

        return decorator

    def safe_execute(self, func, operation_name=None, *args, **kwargs):
        """Ejecutar función de forma segura con logging."""
        op_name = operation_name or func.__name__
        self.logger.debug(f"Ejecutando: {op_name}")

        try:
            result = func(*args, **kwargs)
            self.logger.debug(f"Completado: {op_name}")
            return result
        except Exception as e:
            self.logger.error(f"Error en {op_name}: {str(e)}", exc_info=True)
            self._show_error_dialog(
                f"Error en {op_name}", str(e), traceback.format_exc()
            )
            return None


# Instancia global del manejador de errores
error_handler = ErrorHandler()
