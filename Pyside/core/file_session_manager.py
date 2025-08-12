"""
Multi-File Session Manager for AuroraWave

This module provides capabilities for managing multiple open files simultaneously,
including session persistence, file switching, and resource management.

Classes:
    FileSession: Represents a single file session with its associated data and UI state
    MultiFileSessionManager: Manages multiple file sessions with switching capabilities

Example:
    >>> manager = MultiFileSessionManager()
    >>> session1 = manager.open_file("/path/to/file1.adicht", ["ECG", "HR"])
    >>> session2 = manager.open_file("/path/to/file2.adicht", ["ECG", "FBP"])
    >>> manager.switch_to_session(session1.session_id)
"""

import os
import uuid
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from Pyside.core import get_user_logger, get_current_session
from Pyside.core.config_manager import get_config_manager


@dataclass
class FileSession:
    """
    Represents a single file session with associated metadata and UI state.

    Attributes:
        session_id: Unique identifier for this session
        file_path: Absolute path to the signal file
        display_name: Human-readable name for UI display
        selected_channels: List of currently selected signal channels
        creation_time: When this session was created
        last_accessed: When this session was last accessed
        is_active: Whether this session is currently active
        ui_state: Dictionary storing UI-specific state (scroll positions, zoom levels, etc.)
        analysis_params: Current analysis parameters for this file
        export_settings: File-specific export preferences
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    display_name: str = ""
    selected_channels: List[str] = field(default_factory=list)
    creation_time: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    is_active: bool = False
    ui_state: Dict[str, Any] = field(default_factory=dict)
    analysis_params: Dict[str, Any] = field(default_factory=dict)
    export_settings: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize computed fields after dataclass creation."""
        if not self.display_name and self.file_path:
            self.display_name = Path(self.file_path).stem

    def update_access_time(self) -> None:
        """Update the last accessed timestamp to current time."""
        self.last_accessed = datetime.now()

    def get_age_minutes(self) -> float:
        """
        Calculate session age in minutes.

        Returns:
            float: Number of minutes since session creation
        """
        return (datetime.now() - self.creation_time).total_seconds() / 60

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary for serialization.

        Returns:
            Dict containing all session data for persistence
        """
        return {
            "session_id": self.session_id,
            "file_path": self.file_path,
            "display_name": self.display_name,
            "selected_channels": self.selected_channels,
            "creation_time": self.creation_time.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "is_active": self.is_active,
            "ui_state": self.ui_state,
            "analysis_params": self.analysis_params,
            "export_settings": self.export_settings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileSession":
        """
        Create FileSession from dictionary data.

        Args:
            data: Dictionary containing session data

        Returns:
            FileSession: Reconstructed session object
        """
        session = cls(
            session_id=data["session_id"],
            file_path=data["file_path"],
            display_name=data["display_name"],
            selected_channels=data["selected_channels"],
            creation_time=datetime.fromisoformat(data["creation_time"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            is_active=data["is_active"],
            ui_state=data.get("ui_state", {}),
            analysis_params=data.get("analysis_params", {}),
            export_settings=data.get("export_settings", {}),
        )
        return session


class MultiFileSessionManager:
    """
    Manages multiple file sessions with switching, persistence, and resource management.

    Provides capabilities for:
    - Opening multiple files simultaneously
    - Switching between active files
    - Persisting session state
    - Managing memory usage
    - Handling file conflicts and duplicates

    Attributes:
        _sessions: Dictionary mapping session IDs to FileSession objects
        _active_session_id: ID of currently active session
        _max_sessions: Maximum number of concurrent sessions
        logger: Logger instance for this class
        config_manager: Configuration manager instance
    """

    def __init__(self, max_sessions: int = 10):
        """
        Initialize the multi-file session manager.

        Args:
            max_sessions: Maximum number of concurrent file sessions (default: 10)
        """
        self._sessions: Dict[str, FileSession] = {}
        self._active_session_id: Optional[str] = None
        self._max_sessions: int = max_sessions
        self.logger = get_user_logger(self.__class__.__name__)
        self.session = get_current_session()
        self.config_manager = get_config_manager()

        # Load persisted sessions on startup
        self._load_persisted_sessions()

    def open_file(
        self,
        file_path: str,
        selected_channels: List[str] = None,
        make_active: bool = True,
    ) -> FileSession:
        """
        Open a new file session or return existing one.

        Args:
            file_path: Absolute path to the signal file
            selected_channels: List of channels to select (optional)
            make_active: Whether to make this session active immediately

        Returns:
            FileSession: The created or existing session

        Raises:
            ValueError: If maximum sessions exceeded or invalid input
            FileNotFoundError: If file does not exist

        Example:
            >>> session = manager.open_file("/data/patient.adicht", ["ECG", "HR"])
        """
        if not file_path or not isinstance(file_path, str):
            raise ValueError("file_path must be a non-empty string")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_path = os.path.abspath(file_path)

        # Validate selected_channels if provided
        if selected_channels is not None:
            if not isinstance(selected_channels, list):
                raise ValueError("selected_channels must be a list")
            if not all(isinstance(ch, str) for ch in selected_channels):
                raise ValueError("All channels must be strings")

        # Check if file is already open
        existing_session = self._find_session_by_path(file_path)
        if existing_session:
            existing_session.update_access_time()
            if selected_channels:
                existing_session.selected_channels = selected_channels
            if make_active:
                self.switch_to_session(existing_session.session_id)
            self.logger.info(f"Returning existing session for {Path(file_path).name}")
            return existing_session

        # Check session limit
        if len(self._sessions) >= self._max_sessions:
            self._cleanup_oldest_session()

        # Create new session
        session = FileSession(
            file_path=file_path,
            selected_channels=selected_channels or [],
            is_active=make_active,
        )

        self._sessions[session.session_id] = session

        if make_active:
            self._set_active_session(session.session_id)

        self.logger.info(
            f"Created new session for {session.display_name} (ID: {session.session_id[:8]})"
        )
        self.session.log_action(
            f"File session opened: {session.display_name}", self.logger
        )

        return session

    def close_session(self, session_id: str) -> bool:
        """
        Close a file session and clean up resources.

        Args:
            session_id: ID of the session to close

        Returns:
            bool: True if session was closed successfully

        Example:
            >>> manager.close_session("abc123-def456-...")
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        # If this was the active session, switch to another one
        if session_id == self._active_session_id:
            remaining_sessions = [
                sid for sid in self._sessions.keys() if sid != session_id
            ]
            if remaining_sessions:
                # Switch to most recently accessed session
                most_recent = max(
                    remaining_sessions,
                    key=lambda sid: self._sessions[sid].last_accessed,
                )
                self.switch_to_session(most_recent)
            else:
                self._active_session_id = None

        del self._sessions[session_id]

        self.logger.info(f"Closed session for {session.display_name}")
        self.session.log_action(
            f"File session closed: {session.display_name}", self.logger
        )

        return True

    def switch_to_session(self, session_id: str) -> bool:
        """
        Switch to a different active session.

        Args:
            session_id: ID of the session to make active

        Returns:
            bool: True if switch was successful

        Example:
            >>> manager.switch_to_session("abc123-def456-...")
        """
        if session_id not in self._sessions:
            self.logger.warning(
                f"Attempted to switch to non-existent session: {session_id}"
            )
            return False

        # Deactivate current session
        if self._active_session_id:
            self._sessions[self._active_session_id].is_active = False

        # Activate new session
        self._set_active_session(session_id)

        session = self._sessions[session_id]
        self.logger.info(f"Switched to session: {session.display_name}")
        self.session.log_action(
            f"Switched to file: {session.display_name}", self.logger
        )

        return True

    def get_active_session(self) -> Optional[FileSession]:
        """
        Get the currently active file session.

        Returns:
            FileSession or None: Active session if one exists
        """
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def get_all_sessions(self) -> List[FileSession]:
        """
        Get all open file sessions.

        Returns:
            List[FileSession]: All current sessions sorted by last access time
        """
        sessions = list(self._sessions.values())
        sessions.sort(key=lambda s: s.last_accessed, reverse=True)
        return sessions

    def get_session_by_id(self, session_id: str) -> Optional[FileSession]:
        """
        Get a specific session by ID.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            FileSession or None: Session if found
        """
        return self._sessions.get(session_id)

    def update_session_channels(self, session_id: str, channels: List[str]) -> bool:
        """
        Update the selected channels for a session.

        Args:
            session_id: ID of the session to update
            channels: New list of selected channels

        Returns:
            bool: True if update was successful
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session.selected_channels = channels
        session.update_access_time()

        self.logger.debug(f"Updated channels for {session.display_name}: {channels}")
        return True

    def update_session_ui_state(
        self, session_id: str, ui_state: Dict[str, Any]
    ) -> bool:
        """
        Update UI state for a session (scroll positions, zoom levels, etc.).

        Args:
            session_id: ID of the session to update
            ui_state: Dictionary containing UI state data

        Returns:
            bool: True if update was successful
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session.ui_state.update(ui_state)
        session.update_access_time()

        return True

    def get_session_count(self) -> int:
        """
        Get the number of open sessions.

        Returns:
            int: Number of currently open sessions
        """
        return len(self._sessions)

    def has_unsaved_changes(self) -> bool:
        """
        Check if any session has unsaved changes.

        Returns:
            bool: True if any session has unsaved changes
        """
        # This would be implemented based on your specific needs
        # For now, return False as a placeholder
        return False

    def save_session_state(self) -> None:
        """
        Persist all session state to configuration.

        Saves current sessions to allow restoration on next application startup.
        """
        try:
            session_data = {
                "active_session_id": self._active_session_id,
                "sessions": [session.to_dict() for session in self._sessions.values()],
                "max_sessions": self._max_sessions,
            }

            # Save to configuration manager
            self.config_manager.current_config["file_sessions"] = session_data
            self.config_manager.save_config()

            self.logger.info(f"Saved state for {len(self._sessions)} file sessions")

        except Exception as e:
            self.logger.error(f"Failed to save session state: {e}", exc_info=True)

    def _load_persisted_sessions(self) -> None:
        """Load previously saved sessions from configuration."""
        try:
            session_data = self.config_manager.current_config.get("file_sessions", {})

            if not session_data:
                self.logger.debug("No persisted sessions found")
                return

            # Restore sessions - validate each one
            restored_count = 0
            for session_dict in session_data.get("sessions", []):
                try:
                    # Validate session data structure
                    required_fields = ["session_id", "file_path", "display_name"]
                    if not all(field in session_dict for field in required_fields):
                        self.logger.warning(
                            f"Skipping invalid session data: missing required fields"
                        )
                        continue

                    # Only restore if file still exists
                    if os.path.exists(session_dict["file_path"]):
                        session = FileSession.from_dict(session_dict)
                        self._sessions[session.session_id] = session
                        restored_count += 1
                    else:
                        self.logger.warning(
                            f"Skipping session for missing file: {session_dict.get('file_path', 'unknown')}"
                        )

                except Exception as session_error:
                    self.logger.warning(
                        f"Failed to restore individual session: {session_error}"
                    )
                    continue

            # Restore active session
            active_id = session_data.get("active_session_id")
            if active_id and active_id in self._sessions:
                self._active_session_id = active_id
                self._sessions[active_id].is_active = True
            elif self._sessions:
                # If specified active session doesn't exist, make the first one active
                first_session_id = next(iter(self._sessions.keys()))
                self._active_session_id = first_session_id
                self._sessions[first_session_id].is_active = True

            # Restore max sessions limit
            self._max_sessions = session_data.get("max_sessions", 10)

            self.logger.info(
                f"Restored {restored_count} file sessions from previous run"
            )

        except Exception as e:
            self.logger.error(f"Failed to load persisted sessions: {e}", exc_info=True)
            # Initialize empty state on failure
            self._sessions = {}
            self._active_session_id = None

    def _find_session_by_path(self, file_path: str) -> Optional[FileSession]:
        """Find a session by file path."""
        file_path = os.path.abspath(file_path)
        for session in self._sessions.values():
            if os.path.abspath(session.file_path) == file_path:
                return session
        return None

    def _set_active_session(self, session_id: str) -> None:
        """Set a session as active and update timestamps."""
        self._active_session_id = session_id
        session = self._sessions[session_id]
        session.is_active = True
        session.update_access_time()

    def _cleanup_oldest_session(self) -> None:
        """Remove the oldest inactive session to make room for a new one."""
        inactive_sessions = [s for s in self._sessions.values() if not s.is_active]

        if not inactive_sessions:
            # If all sessions are active, remove the least recently accessed
            oldest_session = min(self._sessions.values(), key=lambda s: s.last_accessed)
        else:
            oldest_session = min(inactive_sessions, key=lambda s: s.last_accessed)

        self.logger.info(f"Cleaning up oldest session: {oldest_session.display_name}")
        self.close_session(oldest_session.session_id)


# Global instance for application-wide use
_multi_file_manager: Optional[MultiFileSessionManager] = None


def get_multi_file_manager() -> MultiFileSessionManager:
    """
    Get the global multi-file session manager instance.

    Returns:
        MultiFileSessionManager: Global manager instance
    """
    global _multi_file_manager
    if _multi_file_manager is None:
        _multi_file_manager = MultiFileSessionManager()
    return _multi_file_manager
