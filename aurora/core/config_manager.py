"""
Unified Configuration Manager for Aurora Application.
Consolidates all configuration functionality with embedded defaults and JSON persistence.
"""

import json
import os
import sys
import logging
from typing import Dict, Any, List, Optional


class ConfigManager:
    """Configuration structure with all embedded defaults."""

    def __init__(self):
        """Initialize configuration with embedded defaults."""
        # UI Settings
        self.default_chunk_size: float = 60.0
        self.default_visible_channels: List[str] = ["HR_gen", "ECG", "FBP", "Valsalva"]
        self.export_format: str = "csv"
        self.last_file_path: str = ""

        # HR Generation Settings
        self.hr_generation: Dict[str, Any] = {
            "default_method": "dwt",
            "wavelet": "haar",
            "level": 4,
            "min_rr_sec": 0.6,
            "min_hr_bpm": 20,
            "max_hr_bpm": 250,
            "max_cache_size": 5,
        }

        # Analysis Settings -
        self.analysis_settings: Dict[str, Any] = {
            "wavelet": "haar",
            "level": 4,
            "min_rr_sec": 0.6,
            "chunk_size": 60,
        }

        # Chunk Loading Settings - Configuration for ChunkLoader
        self.chunk_loading: Dict[str, Any] = {
            "cache_size": 50,
            "max_points_per_plot": 5000,
            "throttle_delay_ms": 50,
            "enable_downsampling": True,
        }

        # UI Limits -
        self.ui_limits: Dict[str, Any] = {
            "max_wavelet_level": 6,
            "min_chunk_size": 1,
            "max_chunk_size": 6000,
            "min_rr_range": [0.1, 2.0],
        }

        # Export Settings
        self.export_settings: Dict[str, Any] = {
            "last_directory": "",
            "default_format": "csv",
        }

        # Window Settings
        self.window_settings: Dict[str, Any] = {"geometry": None, "maximized": False}

        # Session-specific settings that get copied to each session
        self.session_defaults: Dict[str, Any] = {
            "chunk_cache_size": self.chunk_loading["cache_size"],
            "max_points_per_plot": self.chunk_loading["max_points_per_plot"],
        }

        # Peak Detection Parameters
        self.peak_detection_params: Dict[str, Any] = {
            "method": "wavelet",
            "wavelet_config": {"wavelet_type": "haar", "wavelet_level": 5},
            "min_peak_distance": 0.6,
        }


class ConfigManagerSystem:
    """Configuration manager system with embedded defaults and JSON persistence."""

    def __init__(self, config_file_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_file_path: Optional custom path to config file
        """
        self.logger = logging.getLogger("aurora.core.ConfigManager")

        # Determine config file path
        if config_file_path:
            self.config_file = config_file_path
        else:
            self.config_dir = self._get_config_directory()
            self.config_file = os.path.join(self.config_dir, "aurora_config.json")

        # Initialize with embedded defaults only
        self.config = ConfigManager()

    def _get_config_directory(self) -> str:
        """Get config directory based on development/production environment."""
        if getattr(sys, "frozen", False):
            # Production: compiled executable - config next to .exe
            return os.path.dirname(sys.executable)
        else:
            # Development: config in Aurora_app/config/ directory
            current_dir = os.path.dirname(os.path.abspath(__file__))  # aurora/core/
            aurora_core_dir = os.path.dirname(current_dir)  # aurora/
            aurora_app_dir = os.path.dirname(aurora_core_dir)  # Aurora_app/
            return os.path.join(aurora_app_dir, "config")

    def _load_config(self) -> bool:
        """Load configuration from JSON, keeping embedded defaults for missing values."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Update config with JSON values, keeping defaults for missing keys
                self._update_config_from_dict(data)

                self.logger.info(f"Configuration loaded from: {self.config_file}")
                return True
            else:
                self.logger.info("No config file found, using embedded defaults")
                return False

        except Exception as e:
            self.logger.error(f"Error loading config, using embedded defaults: {e}")
            return False

    def _update_config_from_dict(self, data: Dict[str, Any]):
        """Update config object from dictionary, preserving nested structure."""
        # Simple fields
        self.config.default_chunk_size = data.get(
            "default_chunk_size", self.config.default_chunk_size
        )
        self.config.default_visible_channels = data.get(
            "default_visible_channels", self.config.default_visible_channels
        )
        self.config.export_format = data.get("export_format", self.config.export_format)
        self.config.last_file_path = data.get(
            "last_file_path", self.config.last_file_path
        )

        # Nested dictionaries - merge with defaults
        if "hr_generation" in data:
            self.config.hr_generation.update(data["hr_generation"])

        if "analysis_settings" in data:
            self.config.analysis_settings.update(data["analysis_settings"])

        if "export_settings" in data:
            self.config.export_settings.update(data["export_settings"])

        if "window_settings" in data:
            self.config.window_settings.update(data["window_settings"])

        if "ui_limits" in data:
            self.config.ui_limits.update(data["ui_limits"])

        if "peak_detection_params" in data:
            self.config.peak_detection_params.update(data["peak_detection_params"])

    def save_config(self) -> bool:
        """Save current configuration to JSON."""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Convert config to dictionary
            config_dict = self.config.__dict__

            # Save to JSON with pretty formatting
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Configuration saved to: {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False

    def reset_to_defaults(self):
        """Reset configuration to embedded defaults."""
        self.config = ConfigManager()
        self.logger.info("Configuration reset to embedded defaults")

    def get_config_file_path(self) -> str:
        """Get current config file path."""
        return self.config_file

    def set_config_file_path(self, new_path: str) -> None:
        """Set new config file path."""
        self.config_file = new_path

    # Legacy compatibility methods for existing code
    def get_config(self, key: str, default=None):
        """Get configuration value by key."""
        return getattr(self.config, key, default)

    def set_config(self, key: str, value: Any):
        """Set configuration value by key."""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.logger.debug(f"Set config {key} = {value}")
        else:
            self.logger.warning(f"Unknown config key: {key}")

    def get_hr_generation_settings(self) -> Dict[str, Any]:
        """Get HR generation settings."""
        return self.config.hr_generation.copy()

    def get_hr_validation_limits(self) -> tuple[float, float]:
        """Get HR validation limits (min, max) in BPM."""
        return (
            self.config.hr_generation["min_hr_bpm"],
            self.config.hr_generation["max_hr_bpm"],
        )

    def get_hr_cache_size(self) -> int:
        """Get maximum HR cache size."""
        return self.config.hr_generation["max_cache_size"]

    def get_default_hr_config(self) -> Dict[str, Any]:
        """Get default HR generation configuration for compatibility."""
        hr_settings = self.config.hr_generation
        return {
            "wavelet": hr_settings["wavelet"],
            "swt_level": hr_settings["level"],  # For backward compatibility
            "level": hr_settings["level"],  # Standard parameter name
            "min_rr_sec": hr_settings["min_rr_sec"],
        }

    def get_analysis_settings(self) -> Dict[str, Any]:
        """Get analysis tab settings."""
        return self.config.analysis_settings.copy()

    def update_hr_generation_settings(self, **kwargs):
        """Update HR generation settings."""
        self.config.hr_generation.update(kwargs)
        self.logger.debug(f"Updated HR generation settings: {kwargs}")

    def update_analysis_settings(self, **kwargs):
        """Update analysis settings."""
        self.config.analysis_settings.update(kwargs)
        self.logger.debug(f"Updated analysis settings: {kwargs}")

    def get_peak_detection_defaults(self, method: str) -> Dict[str, Any]:
        """Get default parameters for peak detection methods."""
        # Base defaults for all methods
        base_defaults = {
            "min_distance_sec": 0.4,  # Minimum 400ms between peaks (150 BPM max)
            "height_threshold_std": 1.0,  # Threshold as multiple of signal std
        }

        # Method-specific defaults
        method_defaults = {
            "dwt": {**base_defaults, "wavelet": "haar", "level": 4},
            "swt": {**base_defaults, "wavelet": "db3", "level": 4},
            "cwt": {
                **base_defaults,
                "wavelet": "mexh",
                "scales": None,  # Auto-calculated
            },
            "scipy_basic": {
                **base_defaults,
                "filter_signal": True,
                "low_cutoff": 0.5,
                "high_cutoff": 40.0,
            },
            "simple_threshold": {**base_defaults, "threshold_std_multiplier": 2.0},
            "neurokit2": {**base_defaults, "correct_artifacts": False},
        }

        # Return method-specific defaults or base defaults
        return method_defaults.get(method, base_defaults)

    # Additional accessors for new fields
    def get_last_file_path(self) -> str:
        """Get last opened file path."""
        return self.config.last_file_path

    def set_last_file_path(self, file_path: str):
        """Set last opened file path."""
        self.config.last_file_path = file_path
        self.logger.debug(f"Set last file path: {file_path}")

    def get_export_settings(self) -> Dict[str, Any]:
        """Get export settings."""
        return self.config.export_settings.copy()

    def update_export_settings(self, **kwargs):
        """Update export settings."""
        self.config.export_settings.update(kwargs)
        self.logger.debug(f"Updated export settings: {kwargs}")

    def get_window_settings(self) -> Dict[str, Any]:
        """Get window settings."""
        return self.config.window_settings.copy()

    def update_window_settings(self, **kwargs):
        """Update window settings."""
        self.config.window_settings.update(kwargs)
        self.logger.debug(f"Updated window settings: {kwargs}")

    def get_chunk_loading_settings(self) -> Dict[str, Any]:
        """Get chunk loading settings."""
        return self.config.chunk_loading.copy()

    def update_chunk_loading_settings(self, **kwargs):
        """Update chunk loading settings."""
        self.config.chunk_loading.update(kwargs)
        self.logger.debug(f"Updated chunk loading settings: {kwargs}")

    def get_session_defaults(self) -> Dict[str, Any]:
        """Get default settings for new sessions."""
        return self.config.session_defaults.copy()


# Global instance
_config_manager = None


def get_config_manager() -> ConfigManagerSystem:
    """Get global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManagerSystem()
    return _config_manager


def set_custom_config_manager(config_manager: ConfigManagerSystem):
    """Set custom config manager instance (for testing or custom paths)."""
    global _config_manager
    _config_manager = config_manager


def load_channels_from_config_file(config_file_path: str) -> List[str]:
    """
    Static method to load channels from a specific config file without affecting global instance.

    Args:
        config_file_path: Path to JSON config file

    Returns:
        List[str]: List of channel names from config file, empty list if error/not found
    """
    try:
        import json

        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            channels = data.get("default_visible_channels", [])
            return channels if isinstance(channels, list) else []
        else:
            return []

    except Exception as e:
        # Log error but don't crash - return empty list
        logging.getLogger("aurora.core.ConfigManager").error(
            f"Error loading channels from {config_file_path}: {e}"
        )
        return []
