"""
SessionTabHost - Container for 3 internal tabs bound to a Session.
Each SessionTabHost represents a complete app instance for one file.
"""

import logging
from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

from aurora.core.session import Session


class SessionTabHost(QWidget):
    """
    Container widget that hosts 3 internal tabs for a specific session.
    
    Each SessionTabHost = Complete app instance bound to one Session.
    Contains: ViewerTab, AnalysisTab, EventTab - all sharing the same Session.
    
    This widget gets placed as a tab inside MainWindow's QTabWidget.
    """
    
    # Signals to parent (MainWindow)
    session_error = Signal(str)  # error_message
    
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger("aurora.ui.SessionTabHost")
        self.logger.info(f"=== SESSIONTABHOST INIT STARTED ===")
        self.logger.info(f"Session: {session.session_id}")
        self.logger.debug(f"Session object: {session}")
        self.logger.debug(f"Parent: {parent}")
        
        self.session = session
        
        # Main layout
        self.logger.debug("Creating main layout...")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.logger.debug("Main layout created")
        
        # Internal tab widget for 3 tabs
        self.logger.debug("Creating internal QTabWidget...")
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        self.logger.debug("Internal QTabWidget created and added to layout")
        
        # Create 3 internal tabs
        self.logger.debug("Creating internal tabs...")
        try:
            self._create_internal_tabs()
            self.logger.info("Internal tabs created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create internal tabs: {e}", exc_info=True)
            raise
        
        # Connect session signals
        self.logger.debug("Connecting session signals...")
        try:
            self.session.load_failed.connect(self._on_session_error)
            self.logger.debug("Session signals connected")
        except Exception as e:
            self.logger.error(f"Failed to connect session signals: {e}", exc_info=True)
            raise
            
        self.logger.info(f"=== SESSIONTABHOST INIT COMPLETED ===")
    
    def _create_internal_tabs(self):
        """Create the 3 internal tabs bound to the session."""
        self.logger.debug("Importing tabs...")
        # Import real tabs
        try:
            from aurora.ui.tabs.viewer_tab import ViewerTab
            from aurora.ui.tabs.events_tab import EventsTab
            self.logger.debug("ViewerTab and EventsTab imported successfully")
        except Exception as e:
            self.logger.error(f"Failed to import tabs: {e}", exc_info=True)
            raise
        # from aurora.ui.analysis_tab import AnalysisTab  # TODO: Not implemented yet
        
        # Create ViewerTab with session
        self.logger.debug(f"Creating ViewerTab with session {self.session.session_id}...")
        try:
            self.viewer_tab = ViewerTab(self.session)
            self.logger.info("ViewerTab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create ViewerTab: {e}", exc_info=True)
            raise
            
        self.logger.debug("Adding ViewerTab to internal QTabWidget...")
        self.tab_widget.addTab(self.viewer_tab, "📊 Viewer")
        self.logger.debug("ViewerTab added to QTabWidget")
        
        # Connect session signals to viewer tab
        self.logger.debug("Connecting session signals to internal handlers...")
        if hasattr(self.session, 'session_ready'):
            self.session.session_ready.connect(self._on_session_ready)
            self.logger.debug("session_ready signal connected")
        if hasattr(self.session, 'load_failed'):
            self.session.load_failed.connect(self._on_session_error)
            self.logger.debug("load_failed signal connected")
        
        # Create EventsTab with session
        self.logger.debug(f"Creating EventsTab with session {self.session.session_id}...")
        try:
            self.events_tab = EventsTab(self.session)
            self.logger.info("EventsTab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create EventsTab: {e}", exc_info=True)
            # Fallback to placeholder if EventsTab fails
            self.events_tab = self._create_placeholder_tab("Event")
            
        # TEMPORARY: Placeholder for Analysis tab (not implemented yet)
        self.logger.debug("Creating placeholder for Analysis tab...")
        analysis_tab = self._create_placeholder_tab("Analysis")
        
        self.tab_widget.addTab(analysis_tab, "🔬 Analysis")
        self.tab_widget.addTab(self.events_tab, "📈 Events")
        self.logger.debug("Analysis placeholder and EventsTab added to QTabWidget")
    
    def _create_placeholder_tab(self, tab_name: str) -> QWidget:
        """TEMPORARY: Create placeholder tab for testing."""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        
        info_label = QLabel(f"{tab_name} Tab - PLACEHOLDER")
        info_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #666;")
        layout.addWidget(info_label)
        
        session_info = QLabel(f"Session: {self.session.session_id}\nFile: {self.session.display_name}")
        session_info.setStyleSheet("color: #888;")
        layout.addWidget(session_info)
        
        layout.addStretch()
        
        return placeholder
    
    def _on_session_ready(self):
        """Handle session ready signal."""
        # Session is ready, viewer tab should automatically refresh
        pass
    
    def _on_session_error(self, error: str):
        """Handle session errors."""
        self.session_error.emit(error)
    
    def cleanup(self):
        """Cleanup when tab host is being closed."""
        try:
            # Cleanup viewer tab
            if hasattr(self, 'viewer_tab') and self.viewer_tab:
                self.viewer_tab.cleanup()
            
            # Disconnect session signals
            if hasattr(self.session, 'session_ready'):
                self.session.session_ready.disconnect(self._on_session_ready)
            if hasattr(self.session, 'load_failed'):
                self.session.load_failed.disconnect(self._on_session_error)
        except Exception as e:
            print(f"Error during cleanup: {e}")