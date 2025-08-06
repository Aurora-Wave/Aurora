"""
Core package for AuroraWave signal processing and analysis.
"""

from .logging_config import (
    get_logger, 
    get_user_logger, 
    initialize_logging, 
    get_current_session,
    UserSession,
    PerformanceLoggerMixin,
    shutdown_logging,
    AuroraLoggerConfig
)

from .config_manager import (
    ConfigManager,
    get_config_manager
)

__all__ = [
    'get_logger',
    'get_user_logger', 
    'initialize_logging',
    'get_current_session',
    'UserSession',
    'PerformanceLoggerMixin',
    'shutdown_logging',
    'AuroraLoggerConfig',
    'ConfigManager',
    'get_config_manager'
]