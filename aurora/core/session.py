"""
Session - Minimal core for each loaded file.
Each Session replicates current app functionality but isolated per file.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from aurora.core.config_manager import get_config_manager
from aurora.data.data_manager import DataManager


class Session(QObject):
    """
    Represents a loaded file with isolated components.
    Each Session = Complete app instance for a specific file.
    """

    # Signals to SessionManager/MainWindow
    data_loaded = Signal(str)  # file_path
    channels_available = Signal(list)  # available_channels
    session_ready = Signal()
    load_failed = Signal(str)  # error_message

    def __init__(self, file_path: str, session_id: str):
        super().__init__()

        self.logger = logging.getLogger("aurora.core.Session")
        self.logger.debug(f"=== SESSION INIT STARTED ===")

        self.session_id = session_id
        self.file_path = os.path.abspath(file_path)
        self.display_name = Path(self.file_path).stem
        self.creation_time = datetime.now()
        self.last_accessed = datetime.now()

        self.logger.debug(f"Session ID: {self.session_id}")
        self.logger.debug(f"File path (absolute): {self.file_path}")
        self.logger.debug(f"Display name: {self.display_name}")

        # State
        self.is_loaded = False
        self.selected_channels: List[str] = []

        # Exclusive components
        self.logger.debug(f"Creating DataManager instance...")
        try:
            self.data_manager = DataManager()
            self.logger.debug(f"DataManager created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create DataManager: {e}", exc_info=True)
            raise

        # Initialize ChunkLoader (will be created after successful file load)
        self.chunk_loader = None

        # Get processed config (defaults + JSON override if exists)
        self.logger.debug(f"Loading default configuration...")
        try:
            default_manager = get_config_manager()
            self.config = {
                "default_chunk_size": default_manager.config.default_chunk_size,
                "visible_channels": default_manager.config.default_visible_channels.copy(),
                "peak_detection_params": default_manager.config.peak_detection_params.copy(),
                "export_format": default_manager.config.export_format,
            }

            # Add session-specific defaults including ChunkLoader configuration
            session_defaults = default_manager.get_session_defaults()
            self.config.update(session_defaults)
            self.logger.debug(f"Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}", exc_info=True)
            raise

        self.logger.debug(f"=== SESSION INIT COMPLETED ===")

    def load_file(self,selected_channels: List[str] = None,config_file_path: Optional[str] = None) -> bool:
        
        self.logger.info(f"=== SESSION LOAD_FILE STARTED ===")
        self.logger.info(f"Session: {self.session_id}")
        self.logger.info(f"File: {self.file_path}")
        self.logger.debug(f"Selected channels requested: {selected_channels}")
        self.logger.debug(f"Config file path: {config_file_path}")

        try:
            self.last_accessed = datetime.now()

            # Verify file exists
            self.logger.debug(f"Checking file existence...")
            if not os.path.exists(self.file_path):
                error_msg = f"File not found: {self.file_path}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            self.logger.info(
                f"File exists - proceeding with DataManager.load_file()..."
            )

            # Load file with DataManager
            try:
                self.logger.debug(
                    f"Calling data_manager.load_file({self.file_path})..."
                )
                load_result = self.data_manager.load_file(self.file_path)
                self.logger.info(
                    f"data_manager.load_file() completed with result: {load_result}"
                )
            except Exception as e:
                self.logger.error(
                    f"Exception in data_manager.load_file(): {e}", exc_info=True
                )
                raise

            # Get available channels
            self.logger.debug(f"Getting available channels...")
            try:
                available_channels = self.data_manager.get_available_channels(
                    self.file_path
                )
                self.logger.info(
                    f"Available channels: {available_channels} (count: {len(available_channels) if available_channels else 0})"
                )
            except Exception as e:
                self.logger.error(
                    f"Exception getting available channels: {e}", exc_info=True
                )
                raise

            if not available_channels:
                error_msg = f"No channels found in file {self.file_path}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Emit channels signal
            self.logger.debug(f"Emitting channels_available signal...")
            self.channels_available.emit(available_channels)

            # Channel selection logic: use config file or show dialog
            if not selected_channels:
                if config_file_path:
                    # Load channels from provided config file using static method
                    self.logger.info(
                        f"Loading channels from config file: {config_file_path}"
                    )
                    try:
                        from aurora.core.config_manager import (
                            load_channels_from_config_file,
                        )

                        config_channels = load_channels_from_config_file(
                            config_file_path
                        )

                        if config_channels:
                            # Validate channels exist in available channels
                            valid_channels = [
                                ch for ch in config_channels if ch in available_channels
                            ]
                            if valid_channels:
                                self.logger.info(
                                    f"Using {len(valid_channels)} channels from config file: {valid_channels}"
                                )
                                selected_channels = valid_channels
                            else:
                                self.logger.warning(
                                    f"No valid channels found in config file, showing dialog"
                                )
                        else:
                            self.logger.warning(
                                f"No channels defined in config file, showing dialog"
                            )

                    except Exception as e:
                        self.logger.error(f"Error loading config file: {e}")
                        self.logger.info("Falling back to channel selection dialog")

                # If no config file or config loading failed, show channel selection dialog
                if not selected_channels:
                    self.logger.info("Showing channel selection dialog...")

                    try:
                        from aurora.ui.dialogs.channel_selection_dialog import (
                            ChannelSelectionDialog,
                        )

                        selected_by_user = ChannelSelectionDialog.select_channels(
                            available_channels,
                            parent=None,
                            existing_channels=available_channels,
                        )

                        if selected_by_user is None:
                            self.logger.warning("Channel selection cancelled by user")
                            return False

                        self.logger.info(
                            f"User selected {len(selected_by_user)} channels: {selected_by_user}"
                        )
                        selected_channels = selected_by_user

                    except ImportError as e:
                        self.logger.warning(
                            f"Could not import ChannelSelectionDialog: {e}"
                        )
                        selected_channels = available_channels
                    except Exception as e:
                        self.logger.error(
                            f"Error showing channel selection dialog: {e}",
                            exc_info=True,
                        )
                        selected_channels = available_channels

            # Set final selected channels
            self.selected_channels = selected_channels

            self.config["visible_channels"] = self.selected_channels.copy()
            self.logger.debug(f"Final selected channels: {self.selected_channels}")

            # Initialize ChunkLoader now that file is loaded
            self.logger.info(f"=== ATTEMPTING TO CREATE CHUNKLOADER ===")
            try:
                from aurora.processing.chunk_loader import ChunkLoader
                self.logger.info(f"ChunkLoader import successful")

                self.chunk_loader = ChunkLoader(self)
                self.logger.info(f"ChunkLoader created successfully: {self.chunk_loader}")
            except Exception as e:
                self.logger.error(f"Failed to create ChunkLoader: {e}")
                import traceback
                self.logger.error(f"ChunkLoader creation traceback:\n{traceback.format_exc()}")
                # Don't fail the entire session load if ChunkLoader fails
                self.chunk_loader = None

            # Mark as loaded and emit ready signal
            self.is_loaded = True
            self.logger.debug(f"Emitting session_ready signal...")
            self.session_ready.emit()

            self.logger.info(f"=== SESSION LOAD_FILE SUCCESS ===")
            return True

        except Exception as e:
            error_msg = f"Failed to load session: {e}"
            self.logger.error(f"=== SESSION LOAD_FILE FAILED ===")
            self.logger.error(error_msg, exc_info=True)
            self.load_failed.emit(error_msg)
            return False

    def close(self) -> None:
        try:
            # Cleanup ChunkLoader if it exists
            if self.chunk_loader and hasattr(self.chunk_loader, "cleanup"):
                self.chunk_loader.cleanup()
            self.chunk_loader = None

            # Clear DataManager cache for this file
            if self.data_manager and self.file_path:
                self.data_manager.unload_file(self.file_path)
            self.data_manager = None

            self.is_loaded = False
            self.selected_channels.clear()

        except Exception as e:
            self.logger.error(f"Error during session cleanup: {e}", exc_info=True)

    def get_session_info(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "display_name": self.display_name,
            "file_path": self.file_path,
            "is_loaded": self.is_loaded,
            "channels_count": len(self.selected_channels),
            "creation_time": self.creation_time.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
        }

    def get_config(self, key: str, default=None) -> Any:
        return self.config.get(key, default)

    def update_config(self, key: str, value: Any) -> None:
        self.config[key] = value
