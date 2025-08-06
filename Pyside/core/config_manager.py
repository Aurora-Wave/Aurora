"""
Configuration Manager for AuroraWave
Handles loading, saving, and managing user preferences and application configuration.
"""

import json
import os
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional
from Pyside.core import get_user_logger, AuroraLoggerConfig


class ConfigManager:
    """
    Centralized configuration management for AuroraWave.
    Handles user preferences, application settings, and session persistence.
    """
    
    def __init__(self):
        self.logger = get_user_logger(self.__class__.__name__)
        
        # Initialize configuration paths
        self.config_dir = AuroraLoggerConfig.get_config_directory()
        self.config_file = self.config_dir / "signals_config.json"
        
        # Default configuration
        self.default_config = {
            "file_path": "",
            "default_signals": ["ECG", "HR_gen", "FBP"],
            "window_settings": {
                "geometry": None,
                "maximized": False
            },
            "hr_generation": {
                # Core HR generation parameters
                "default_method": "dwt",
                "wavelet": "haar",
                "level": 4,
                "min_rr_sec": 0.6,
                # HR validation parameters
                "min_hr_bpm": 20,
                "max_hr_bpm": 250,
                # Cache settings
                "max_cache_size": 5
            },
            "peak_detection": {
                # Strategy-specific defaults
                "swt": {
                    "wavelet": "haar",
                    "level": 4,
                    "min_rr_sec": 0.6
                },
                "dwt": {
                    "wavelet": "haar",
                    "level": 4,
                    "min_rr_sec": 0.6
                },
                "cwt": {
                    "wavelet": "haar",
                    "scales": None,
                    "min_rr_sec": 0.6
                },
                "neurokit2": {
                    "method": "pan_tompkins",
                    "correct_artifacts": False
                }
            },
            "analysis_settings": {
                "wavelet": "haar",
                "level": 4,
                "min_rr_sec": 0.6,
                "chunk_size": 60
            },
            "export_settings": {
                "last_directory": "",
                "default_format": "csv"
            },
            "ui_limits": {
                "max_wavelet_level": 6,
                "min_chunk_size": 1,
                "max_chunk_size": 600,
                "min_rr_range": [0.1, 2.0]
            }
        }
        
        # Current configuration in memory - load from file immediately
        self.current_config = self.load_config()
        
        self.logger.debug(f"ConfigManager initialized with config file: {self.config_file}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Dict[str, Any]: Loaded configuration, defaults if file doesn't exist
        """
        if not self.config_file.exists():
            self.logger.info(f"Configuration file not found at {self.config_file}, using defaults")
            return self.default_config.copy()
        
        try:
            with open(self.config_file, "r", encoding="utf-8-sig") as f:
                loaded_config = json.load(f)
                self.logger.debug(f"Configuration loaded: {loaded_config}")
                
                # Smart merge: only add defaults for missing sections, don't override saved ones
                merged_config = self.default_config.copy()
                
                # For each loaded section, completely replace the default section
                for section_name, section_data in loaded_config.items():
                    merged_config[section_name] = section_data
                
                self.current_config = merged_config
                return merged_config
                
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}", exc_info=True)
            return self.default_config.copy()
    
    def _filter_user_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out default sections that shouldn't be persisted to disk.
        Only save user-modified settings.
        """
        user_config = {}
        
        # Always save these user-specific sections
        user_sections = ["file_path", "default_signals", "analysis_settings", "export_settings", "window_settings"]
        
        for section in user_sections:
            if section in config:
                user_config[section] = config[section]
        
        # Don't save these default-only sections (they should only exist in memory)
        # - peak_detection: these are code defaults for different algorithms
        # - hr_generation: these are fallback defaults, user settings go in analysis_settings
        # - ui_limits: these are UI constraints, not user preferences
        
        return user_config
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """
        Save configuration to file.
        Only saves user-modified settings, not runtime defaults.
        
        Args:
            config: Configuration to save, uses current_config if None
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if config is None:
            config = self.current_config
        
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Filter to only save user settings, not defaults
            user_config = self._filter_user_config(config)
            
            # Save only user configuration
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(user_config, f, indent=2, ensure_ascii=False)
            
            self.current_config = config.copy()  # Keep full config in memory for runtime
            self.logger.info(f"Configuration saved to {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}", exc_info=True)
            return False
    
    def get_last_file_path(self) -> Optional[str]:
        """Get the last opened file path from configuration."""
        file_path = self.current_config.get("file_path", "")
        if not file_path:
            return None
        
        # Handle relative paths
        if not os.path.isabs(file_path):
            # Resolve relative to project root (parent of config directory)
            base_dir = self.config_dir.parent
            file_path = base_dir / file_path
        else:
            file_path = Path(file_path)
        
        # Normalize unicode form to match filesystem
        file_path_str = str(file_path)
        file_path_str = unicodedata.normalize("NFC", file_path_str)
        
        return file_path_str if Path(file_path_str).exists() else None
    
    def set_last_file_path(self, file_path: str):
        """Set the last opened file path in configuration."""
        # Store as relative path if within project directory
        base_dir = self.config_dir.parent
        try:
            rel_path = Path(file_path).relative_to(base_dir)
            self.current_config["file_path"] = str(rel_path).replace("\\", "/")
        except ValueError:
            # File is outside project directory, store as absolute path
            self.current_config["file_path"] = file_path
        
        self.logger.debug(f"Updated last file path: {self.current_config['file_path']}")
    
    def get_default_signals(self) -> List[str]:
        """Get the default signal channels from configuration."""
        return self.current_config.get("default_signals", ["ECG", "HR_gen", "FBP"])
    
    def set_default_signals(self, signals: List[str]):
        """Set the default signal channels in configuration."""
        self.current_config["default_signals"] = signals.copy()
        self.logger.debug(f"Updated default signals: {signals}")
    
    def get_hr_generation_settings(self) -> Dict[str, Any]:
        """Get HR generation settings."""
        return self.current_config.get("hr_generation", {
            "default_method": "dwt",
            "wavelet": "haar",
            "level": 4,
            "min_rr_sec": 0.6,
            "min_hr_bpm": 20,
            "max_hr_bpm": 250,
            "max_cache_size": 5
        })
    
    def get_peak_detection_defaults(self, method: str) -> Dict[str, Any]:
        """Get default parameters for a specific peak detection method."""
        peak_detection = self.current_config.get("peak_detection", {})
        method_defaults = peak_detection.get(method, {})
        
        # Fallback to general hr_generation settings for common parameters
        hr_settings = self.get_hr_generation_settings()
        fallback_defaults = {
            "wavelet": hr_settings.get("wavelet", "haar"),
            "level": hr_settings.get("level", 4),
            "min_rr_sec": hr_settings.get("min_rr_sec", 0.6)
        }
        
        # Merge method-specific with fallbacks
        combined_defaults = fallback_defaults.copy()
        combined_defaults.update(method_defaults)
        return combined_defaults
    
    def get_hr_validation_limits(self) -> tuple[float, float]:
        """Get HR validation limits (min, max) in BPM."""
        hr_settings = self.get_hr_generation_settings()
        return hr_settings.get("min_hr_bpm", 20), hr_settings.get("max_hr_bpm", 250)
    
    def get_hr_cache_size(self) -> int:
        """Get maximum HR cache size."""
        hr_settings = self.get_hr_generation_settings()
        return hr_settings.get("max_cache_size", 5)
    
    def get_ui_limits(self) -> Dict[str, Any]:
        """Get UI component limits and ranges."""
        return self.current_config.get("ui_limits", {
            "max_wavelet_level": 6,
            "min_chunk_size": 1,
            "max_chunk_size": 600,
            "min_rr_range": [0.1, 2.0]
        })
    
    def get_analysis_settings(self) -> Dict[str, Any]:
        """Get analysis tab settings."""
        return self.current_config.get("analysis_settings", {
            "wavelet": "haar",
            "level": 4,
            "min_rr_sec": 0.6,
            "chunk_size": 60
        })
    
    def update_analysis_settings(self, **kwargs):
        """Update analysis settings."""
        if "analysis_settings" not in self.current_config:
            self.current_config["analysis_settings"] = {}
        
        self.current_config["analysis_settings"].update(kwargs)
        self.logger.debug(f"Updated analysis settings: {kwargs}")
    
    def update_hr_generation_settings(self, **kwargs):
        """Update HR generation settings."""
        if "hr_generation" not in self.current_config:
            self.current_config["hr_generation"] = {}
        
        self.current_config["hr_generation"].update(kwargs)
        self.logger.debug(f"Updated HR generation settings: {kwargs}")
    
    def get_default_hr_config(self) -> Dict[str, Any]:
        """Get default HR generation configuration for compatibility."""
        hr_settings = self.get_hr_generation_settings()
        return {
            "wavelet": hr_settings.get("wavelet", "haar"),
            "swt_level": hr_settings.get("level", 4),  # For backward compatibility
            "level": hr_settings.get("level", 4),      # Standard parameter name
            "min_rr_sec": hr_settings.get("min_rr_sec", 0.6)
        }
    
    def get_window_settings(self) -> Dict[str, Any]:
        """Get window geometry and state settings."""
        return self.current_config.get("window_settings", {
            "geometry": None,
            "maximized": False
        })
    
    def update_window_settings(self, **kwargs):
        """Update window settings."""
        if "window_settings" not in self.current_config:
            self.current_config["window_settings"] = {}
        
        self.current_config["window_settings"].update(kwargs)
        self.logger.debug(f"Updated window settings: {kwargs}")
    
    def apply_startup_configuration(self, main_window) -> bool:
        """
        Apply saved configuration to main window at startup.
        
        Args:
            main_window: MainWindow instance to configure
            
        Returns:
            bool: True if configuration was applied successfully
        """
        try:
            config = self.load_config()
            
            # Get last file path and default signals
            file_path = self.get_last_file_path()
            default_signals = self.get_default_signals()
            
            self.logger.info(f"Applying startup configuration: file={file_path}, signals={default_signals}")
            
            if file_path and os.path.exists(file_path):
                # Load the file through main window
                main_window.data_manager.load_file(file_path)
                main_window.current_file = file_path
                
                if default_signals:
                    main_window.update_tabs(default_signals)
                
                self.logger.info("Startup configuration applied successfully")
                return True
            else:
                if file_path:
                    self.logger.warning(f"Configured file not found: {file_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error applying startup configuration: {e}", exc_info=True)
            return False
    
    def save_current_session(self, main_window):
        """
        Save current session state to configuration.
        
        Args:
            main_window: MainWindow instance to save state from
        """
        try:
            # Update file path if a file is loaded
            if main_window.current_file:
                self.set_last_file_path(main_window.current_file)
            
            # Get currently selected channels from viewer tabs
            current_signals = []
            for i in range(main_window.tab_widget.count()):
                widget = main_window.tab_widget.widget(i)
                if hasattr(widget, 'get_selected_channels'):
                    current_signals = widget.get_selected_channels()
                    break
            
            if current_signals:
                self.set_default_signals(current_signals)
            
            # Save analysis settings if available
            if hasattr(main_window, 'analysis_tab'):
                analysis_params = main_window.analysis_tab.get_hrgen_params()
                self.update_analysis_settings(**analysis_params)
            
            # Save configuration to disk
            success = self.save_config()
            if success:
                self.logger.info("Session configuration saved")
            else:
                self.logger.warning("Failed to save session configuration")
                
        except Exception as e:
            self.logger.error(f"Error saving session configuration: {e}", exc_info=True)


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager