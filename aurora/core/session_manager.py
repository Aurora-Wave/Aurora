"""
SessionManager - Global manager for all file sessions.
Handles session creation, cleanup, and lifecycle management.
"""

import os
import logging
from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal

from aurora.core.session import Session


class SessionManager(QObject):
    """
    Global manager for all file sessions in the application.
    """
    
    # Signals to MainWindow
    session_created = Signal(str, object)  # session_id, session
    session_closed = Signal(str)  # session_id
    
    def __init__(self):
        super().__init__()
        
        self.logger = logging.getLogger("aurora.core.SessionManager")
        self.sessions: Dict[str, Session] = {}
        self._session_counter = 0
        self.active_session_id: Optional[str] = None
        
        self.logger.debug("SessionManager initialized")
    
    def create_session(self, file_path: str, config_file_path: Optional[str] = None) -> Optional[Session]:
        """Create new session for file with unique ID."""
        self.logger.info(f"=== CREATE SESSION STARTED ===")
        self.logger.info(f"Requested file: {file_path}")
        self.logger.info(f"Config file: {config_file_path}")
        self.logger.debug(f"File exists: {os.path.exists(file_path)}")

        # Generate unique session ID
        self._session_counter += 1
        session_id = f"session_{self._session_counter:03d}"
        self.logger.debug(f"Generated session_id: {session_id}")
        
        # Create session
        self.logger.debug(f"Creating Session object...")
        try:
            session = Session(file_path, session_id)
            self.logger.debug(f"Session object created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create Session object: {e}", exc_info=True)
            return None
        
        # Load file
        self.logger.info(f"Attempting to load file via session.load_file()...")
        try:
            load_result = session.load_file(config_file_path=config_file_path)
            self.logger.info(f"session.load_file() returned: {load_result}")
        except Exception as e:
            self.logger.error(f"Exception during session.load_file(): {e}", exc_info=True)
            return None
        
        if load_result:
            self.logger.info(f"File load successful - registering session")
            self.sessions[session_id] = session
            self.active_session_id = session_id
            
            self.logger.debug(f"Emitting session_created signal...")
            self.session_created.emit(session_id, session)
            
            self.logger.info(f"=== CREATE SESSION SUCCESS: {session_id} ===")
            return session
        else:
            self.logger.error(f"File load failed - session creation aborted")
            self.logger.info(f"=== CREATE SESSION FAILED ===")
            return None
                
    
    def close_session(self, session_id: str) -> bool:
        """Close session and cleanup resources."""
        if session_id not in self.sessions:
            return False
        
        try:
            self.sessions[session_id].close()
            del self.sessions[session_id]
            
            # Update active session
            if self.active_session_id == session_id:
                self.active_session_id = next(iter(self.sessions.keys())) if self.sessions else None
            
            self.session_closed.emit(session_id)
            return True
            
        except Exception:
            return False
    
    def close_all_sessions(self) -> None:
        """Close all active sessions."""
        for session_id in list(self.sessions.keys()):
            self.close_session(session_id)
    
    def _on_session_failed(self, session_id: str, error: str) -> None:
        """Handle session load failure."""
        self.session_failed.emit(session_id, error)
        if session_id in self.sessions:
            del self.sessions[session_id]


_session_manager = None

def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager