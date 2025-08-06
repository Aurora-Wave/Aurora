"""
Unified logging configuration for AuroraWave.

Provides rotating file handlers with configurable limits, user session tracking,
and consistent formatting across all modules.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

class AuroraLoggerConfig:
    """logging configuration for AuroraWave."""

    # Class variable to store current log file path
    _current_log_file = None
    
    # Log format optimized for filtering and analysis
    LOG_FORMAT = (
        "%(asctime)s.%(msecs)03d [%(levelname)s] "
        "%(user_context)s%(name)s.%(funcName)s:%(lineno)d - %(message)s"
    )
    
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Default configuration
    DEFAULT_CONFIG = {
        'max_files': 4, # Keep up to n + 1 files
        'max_size_mb': 10,
        'log_level': 'DEBUG',
        'console_output': True,
        'log_dir_name': 'logs'
    }
    
    @classmethod
    def _get_application_root(cls) -> Path:
        """
        Determine the application root directory.
        
        Returns:
            Path: Application root directory
        """
        # Check if we're running as a compiled executable (flag "frozen")
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # PyInstaller compiled executable
            # Use the directory containing the executable
            return Path(sys.executable).parent
        
        elif getattr(sys, 'frozen', False):
            # Other frozen environments (Nuitka,cx_Freeze, etc.)
            return Path(sys.executable).parent
        
        else:
            # Development mode: find project root by looking for main.py
            current_file = Path(__file__)
            
            # Start from current file and go up to find main.py
            search_path = current_file.parent
            for _ in range(5):  # Limit search depth
                # Look for main.py in Pyside folder, but return the parent directory (project root)
                main_py = search_path.parent / "Pyside" / "main.py"
                if main_py.exists():
                    return search_path.parent
                
                # Alternative: look for main.py directly in parent directories
                # main_py = search_path / "Pyside" / "main.py"
                # if main_py.exists():
                #    return search_path
                    
                search_path = search_path.parent
            
            # Fallback: use current working directory
            return Path.cwd()
        
    @classmethod
    def get_log_directory(cls) -> Path:
        """
        Get the logs directory path.
        
        Handles both development and standalone/compiled scenarios:
        - Development: Creates logs/ in project root
        - Standalone: Creates logs/ next to executable
        """
        # Environment variable override (highest priority)
        if env_dir := os.getenv('AURORA_LOG_DIR'):
            log_dir = Path(env_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        
        # Determine application root directory
        app_root = cls._get_application_root()
        
        # Create logs directory relative to application root
        log_dir = app_root / cls.DEFAULT_CONFIG['log_dir_name']
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    @classmethod
    def get_log_level_from_env(cls) -> str:
        """Get log level from environment variable or config."""
        return os.getenv('AURORA_LOG_LEVEL', cls.DEFAULT_CONFIG['log_level']).upper()
    
    @classmethod
    def should_output_console(cls) -> bool:
        """Check if console output should be enabled."""
        env_console = os.getenv('AURORA_LOG_CONSOLE', '').lower()
        if env_console in ('true', '1', 'yes'):
            return True
        elif env_console in ('false', '0', 'no'):
            return False
        return cls.DEFAULT_CONFIG['console_output']
    
    @classmethod
    def get_config_directory(cls) -> Path:
        """
        Get the config directory path.
        
        Creates config/ directory for application configuration files.
        Handles both development and standalone scenarios.
        """
        app_root = cls._get_application_root()
        config_dir = app_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    @classmethod
    def generate_log_filename(cls) -> str:
        """
        Generate a descriptive log filename with timestamp and metadata.
        
        Returns:
            str: Formatted log filename with execution timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"aurora_wave_{timestamp}.log"
    
    @classmethod
    def cleanup_old_log_files(cls) -> int:
        """
        Clean up old log files, keeping only the most recent ones.
        
        Returns:
            int: Number of files removed
        """
        try:
            log_dir = cls.get_log_directory()
            max_files = cls.DEFAULT_CONFIG['max_files']
            
            # Find all aurora_wave log files
            log_pattern = "aurora_wave_*.log"
            log_files = list(log_dir.glob(log_pattern))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove excess files (keep only max_files most recent)
            files_to_remove = log_files[max_files:]
            removed_count = 0
            
            for log_file in files_to_remove:
                try:
                    log_file.unlink()
                    removed_count += 1
                except OSError as e:
                    # Log the error but continue with other files
                    print(f"Warning: Could not remove log file {log_file}: {e}")
            
            return removed_count
            
        except Exception as e:
            print(f"Error during log cleanup: {e}")
            return 0
    
    @classmethod
    def ensure_app_directories(cls) -> Dict[str, Path]:
        """
        Ensure all application directories exist.
        
        Returns:
            Dict[str, Path]: Dictionary containing all directories and their creation status
        """
        directories = {}
        created_directories = {}
        
        # Define directories to check/create
        dirs_to_create = {
            'logs': cls.get_log_directory(),
            'config': cls.get_config_directory()
        }
        
        # Add any additional directories needed by the app
        app_root = cls._get_application_root()
        
        # You can add more directories here as needed
        # dirs_to_create['exports'] = app_root / "exports"
        # dirs_to_create['temp'] = app_root / "temp"
        
        # Ensure all directories exist and track which ones were actually created
        for name, path in dirs_to_create.items():
            directories[name] = path
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created_directories[name] = path
        
        return {'all': directories, 'created': created_directories}


class CustomFormatter(logging.Formatter):
    """Custom formatter that handles user context and colors for console."""
    
    # Color codes for console output
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def __init__(self, use_colors: bool = False):
        super().__init__(
            fmt=AuroraLoggerConfig.LOG_FORMAT,
            datefmt=AuroraLoggerConfig.DATE_FORMAT
        )
        self.use_colors = use_colors
    
    def format(self, record):
        # Add empty user_context if not present
        if not hasattr(record, 'user_context'):
            record.user_context = ""
        
        # Format the record
        formatted = super().format(record)
        
        # Add colors for console output
        if self.use_colors and hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            if color:
                formatted = f"{color}{formatted}{reset}"
        
        return formatted


class UserContextFilter(logging.Filter):
    """Inject user context into log records."""
    
    def __init__(self, user_context: str):
        super().__init__()
        self.user_context = f"{user_context} " if user_context else ""
    
    def filter(self, record):
        record.user_context = self.user_context
        return True


class PerformanceLoggerMixin:
    """Mixin for adding performance logging to operations."""
    
    def log_operation(self, operation_name: str, duration: float = None, **metrics):
        """Log operation with performance metrics."""
        if not hasattr(self, 'logger'):
            return
        
        message_parts = [operation_name]
        
        if duration is not None:
            message_parts.append(f"in {duration:.3f}s")
        
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if key.endswith('_mb') or key.endswith('_gb'):
                    message_parts.append(f"{key}={value:.1f}")
                elif key.endswith('_count'):
                    message_parts.append(f"{key}={value}")
                else:
                    message_parts.append(f"{key}={value}")
            else:
                message_parts.append(f"{key}={value}")
        
        message = " ".join(str(part) for part in message_parts)
        
        # Log at appropriate level based on duration
        if duration is not None:
            if duration > 5.0:
                self.logger.warning(f"SLOW: {message}")
            elif duration > 2.0:
                self.logger.info(f"PERF: {message}")
            else:
                self.logger.debug(f"PERF: {message}")
        else:
            self.logger.info(message)


class UserSession:
    """Track user session for logging context."""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id or self._generate_session_id()
        self.start_time = datetime.now()
        self.actions_count = 0
    
    def _generate_session_id(self) -> str:
        """Generate a simple session ID."""
        timestamp = datetime.now().strftime("%m%d_%H%M")
        return f"user{timestamp}"
    
    def get_context(self) -> str:
        """Get the user context string for logging."""
        return f"USER[{self.user_id}]"
    
    def log_action(self, action: str, logger: logging.Logger):
        """Log user action with session context."""
        self.actions_count += 1
        logger.info(f"{action} (action #{self.actions_count})")
    
    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return (datetime.now() - self.start_time).total_seconds()


# Global logger instance and session
_logger_instance = None
_current_session = None


def initialize_logging(user_id: str = None) -> UserSession:
    """
    Initialize the global logging system and user session.
    
    Args:
        user_id: Optional user identifier
        
    Returns:
        UserSession: The initialized user session
    """
    global _logger_instance, _current_session
    
    if _logger_instance is None:
        # Ensure all application directories exist first
        dir_result = AuroraLoggerConfig.ensure_app_directories()
        
        # Clean up old log files to maintain max_files limit
        removed_files = AuroraLoggerConfig.cleanup_old_log_files()
        
        # Setup the global logger
        _logger_instance = _setup_global_logger()
        
        # Log system startup and directory structure
        startup_logger = logging.getLogger("AuroraWave.System")
        startup_logger.info("=== AuroraWave Logging System Initialized ===")
        
        # Detect execution mode
        if getattr(sys, 'frozen', False):
            startup_logger.info("Running in standalone/compiled mode")
            startup_logger.info(f"Executable path: {sys.executable}")
        else:
            startup_logger.info("Running in development mode")
        
        startup_logger.info(f"Application root: {AuroraLoggerConfig._get_application_root()}")
        startup_logger.info(f"Log level: {AuroraLoggerConfig.get_log_level_from_env()}")
        
        # Only log directories that were actually created (not pre-existing)
        created_dirs = dir_result['created']
        if created_dirs:
            for name, path in created_dirs.items():
                startup_logger.info(f"Directory created: {name} -> {path}")
        else:
            startup_logger.debug("All required directories already exist")
    
    # Initialize user session
    if _current_session is None:
        _current_session = UserSession(user_id)
        session_logger = logging.getLogger("AuroraWave.Session")
        session_logger.info(f"User session started: {_current_session.get_context()}")
    
    return _current_session


def get_logger(name: str, include_user_context: bool = False) -> logging.Logger:
    """
    Get a logger with consistent configuration.
    
    Args:
        name: Module or class name for the logger
        include_user_context: Whether to include user context in logs
        
    Returns:
        logging.Logger: Configured logger instance
    """
    global _logger_instance, _current_session
    
    # Initialize logging if not already done
    if _logger_instance is None:
        initialize_logging()
    
    logger = logging.getLogger(name)
    
    # Add user context filter if requested and session exists
    if include_user_context and _current_session:
        # Check if filter is already added to avoid duplicates
        has_context_filter = any(
            isinstance(f, UserContextFilter) for f in logger.filters
        )
        if not has_context_filter:
            logger.addFilter(UserContextFilter(_current_session.get_context()))
    
    return logger


def get_user_logger(name: str) -> logging.Logger:
    """
    Get a logger with user context included.
    
    Args:
        name: Module or class name for the logger
        
    Returns:
        logging.Logger: Logger with user context
    """
    return get_logger(name, include_user_context=True)


def get_current_session() -> Optional[UserSession]:
    """Get the current user session."""
    return _current_session


def _setup_global_logger():
    """Setup the global logger with rotating file handler."""
    # Get root logger
    root_logger = logging.getLogger()
    
    # Set log level from environment or default
    log_level = getattr(logging, AuroraLoggerConfig.get_log_level_from_env())
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Setup rotating file handler with descriptive filename
    try:
        log_dir = AuroraLoggerConfig.get_log_directory()
        
        # Generate descriptive filename with timestamp and metadata
        log_filename = AuroraLoggerConfig.generate_log_filename()
        log_file = log_dir / log_filename
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=AuroraLoggerConfig.DEFAULT_CONFIG['max_size_mb'] * 1024 * 1024,  # Convert MB to bytes
            backupCount=AuroraLoggerConfig.DEFAULT_CONFIG['max_files'] - 1,  # backupCount excludes current file
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Always capture all levels to file
        
        # Create file formatter
        file_formatter = CustomFormatter(use_colors=False)
        file_handler.setFormatter(file_formatter)
        
        # Add file handler to root logger
        root_logger.addHandler(file_handler)
        
        # Store the log file path for reference
        AuroraLoggerConfig._current_log_file = log_file
        
    except Exception as e:
        # Fallback to console only if file logging fails
        print(f"Warning: Could not setup file logging: {e}")
        print("Falling back to console logging only.")
    
    # Setup console handler (optional)
    if AuroraLoggerConfig.should_output_console():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Create console formatter with colors
        console_formatter = CustomFormatter(use_colors=True)
        console_handler.setFormatter(console_formatter)
        
        # Add console handler to root logger
        root_logger.addHandler(console_handler)
    
    return root_logger


def shutdown_logging():
    """Shutdown logging system and log session summary."""
    global _current_session
    
    if _current_session:
        session_logger = logging.getLogger("AuroraWave.Session")
        duration = _current_session.get_session_duration()
        session_logger.info(
            f"User session ended: {_current_session.get_context()}, "
            f"duration: {duration/60:.1f}min, "
            f"actions: {_current_session.actions_count}"
        )
    
    # Shutdown all handlers
    logging.shutdown()