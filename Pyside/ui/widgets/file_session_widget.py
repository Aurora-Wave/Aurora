"""
File Session Widget for AuroraWave

This module provides a widget for managing multiple file sessions with a tabbed interface
that shows currently open files and allows easy switching between them.

Classes:
    FileSessionWidget: Widget for displaying and managing file sessions
    SessionTab: Custom tab widget for individual file sessions

Example:
    >>> session_widget = FileSessionWidget(main_window)
    >>> main_window.setCentralWidget(session_widget)
"""

from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QMenu,
    QToolButton,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtGui import QIcon, QAction

from Pyside.core import get_user_logger, get_current_session
from Pyside.core.file_session_manager import get_multi_file_manager, FileSession


class SessionTab(QFrame):
    """
    Custom tab widget for displaying file session information.

    Shows file name, channel count, and session status with context menu options.

    Signals:
        close_requested: Emitted when user requests to close this session
        switch_requested: Emitted when user requests to switch to this session
    """

    close_requested = QtSignal(str)  # session_id
    switch_requested = QtSignal(str)  # session_id

    def __init__(self, session: FileSession, parent=None):
        """
        Initialize the session tab.

        Args:
            session: FileSession object to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.session = session
        self.logger = get_user_logger(self.__class__.__name__)

        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            SessionTab {
                border: 1px solid #ccc;
                border-radius: 4px;
                margin: 2px;
                padding: 4px;
            }
            SessionTab:hover {
                border-color: #999;
                background-color: #f0f0f0;
            }
            .active {
                border-color: #007acc;
                background-color: #e6f3ff;
            }
        """
        )

        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Top row: file name and close button
        top_layout = QHBoxLayout()

        self.file_label = QLabel()
        self.file_label.setStyleSheet("font-weight: bold; color: #333;")
        top_layout.addWidget(self.file_label)

        top_layout.addStretch()

        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(16, 16)
        self.close_button.setStyleSheet(
            """
            QPushButton {
                border: none;
                background: transparent;
                color: #666;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ff4444;
                color: white;
                border-radius: 8px;
            }
        """
        )
        self.close_button.clicked.connect(self._on_close_clicked)
        top_layout.addWidget(self.close_button)

        layout.addLayout(top_layout)

        # Bottom row: channel info and status
        self.info_label = QLabel()
        self.info_label.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(self.info_label)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_display(self) -> None:
        """Update the display based on current session state."""
        self.file_label.setText(self.session.display_name)

        channel_count = len(self.session.selected_channels)
        channel_text = f"{channel_count} channel{'s' if channel_count != 1 else ''}"

        age_minutes = self.session.get_age_minutes()
        if age_minutes < 1:
            age_text = "just opened"
        elif age_minutes < 60:
            age_text = f"{int(age_minutes)}m ago"
        else:
            hours = int(age_minutes / 60)
            age_text = f"{hours}h ago"

        self.info_label.setText(f"{channel_text} • {age_text}")

        # Update styling based on active state
        if self.session.is_active:
            self.setProperty("class", "active")
        else:
            self.setProperty("class", "")
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_close_clicked(self) -> None:
        """Handle close button click."""
        self.close_requested.emit(self.session.session_id)

    def _show_context_menu(self, position) -> None:
        """Show context menu for this session."""
        menu = QMenu(self)

        # Switch to action
        if not self.session.is_active:
            switch_action = QAction("Switch to this file", self)
            switch_action.triggered.connect(
                lambda: self.switch_requested.emit(self.session.session_id)
            )
            menu.addAction(switch_action)

        # Close action
        close_action = QAction("Close file", self)
        close_action.triggered.connect(self._on_close_clicked)
        menu.addAction(close_action)

        menu.addSeparator()

        # Properties action
        props_action = QAction("Properties...", self)
        props_action.triggered.connect(self._show_properties)
        menu.addAction(props_action)

        menu.exec(self.mapToGlobal(position))

    def _show_properties(self) -> None:
        """Show properties dialog for this session."""
        # This would show a dialog with detailed session information
        self.logger.info(
            f"Properties requested for session: {self.session.display_name}"
        )

    def mousePressEvent(self, event) -> None:
        """Handle mouse press to switch sessions."""
        if event.button() == Qt.LeftButton and not self.session.is_active:
            self.switch_requested.emit(self.session.session_id)
        super().mousePressEvent(event)

    def update_session(self, session: FileSession) -> None:
        """Update the session and refresh display."""
        self.session = session
        self._update_display()


class FileSessionWidget(QWidget):
    """
    Widget for managing multiple file sessions.

    Provides a horizontal layout showing tabs for each open file session,
    allowing users to switch between files and manage sessions.

    Signals:
        session_switched: Emitted when active session changes
        session_closed: Emitted when a session is closed
    """

    session_switched = QtSignal(str)  # session_id
    session_closed = QtSignal(str)  # session_id

    def __init__(self, parent=None):
        """
        Initialize the file session widget.

        Args:
            parent: Parent widget (typically MainWindow)
        """
        super().__init__(parent)
        self.logger = get_user_logger(self.__class__.__name__)
        self.session_manager = get_multi_file_manager()
        self.session_tabs: Dict[str, SessionTab] = {}

        self._setup_ui()
        self._update_sessions()

        # Connect to session manager signals if available
        # Note: This would require implementing signals in MultiFileSessionManager

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Sessions container with scroll capability
        self.sessions_layout = QHBoxLayout()
        self.sessions_layout.setSpacing(4)

        # Add stretch to push tabs to the left
        self.sessions_layout.addStretch()

        layout.addLayout(self.sessions_layout)

        # Add file button
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(24, 24)
        self.add_button.setToolTip("Open new file")
        self.add_button.setStyleSheet(
            """
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 12px;
                background: #f8f8f8;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e8e8e8;
                border-color: #999;
            }
        """
        )
        self.add_button.clicked.connect(self._on_add_file_clicked)
        layout.addWidget(self.add_button)

    def _update_sessions(self) -> None:
        """Update the display with current sessions."""
        current_sessions = self.session_manager.get_all_sessions()
        current_session_ids = {session.session_id for session in current_sessions}

        # Remove tabs for closed sessions
        tabs_to_remove = []
        for session_id in self.session_tabs:
            if session_id not in current_session_ids:
                tabs_to_remove.append(session_id)

        for session_id in tabs_to_remove:
            self._remove_session_tab(session_id)

        # Add or update tabs for current sessions
        for session in current_sessions:
            if session.session_id in self.session_tabs:
                # Update existing tab
                self.session_tabs[session.session_id].update_session(session)
            else:
                # Add new tab
                self._add_session_tab(session)

    def _add_session_tab(self, session: FileSession) -> None:
        """Add a new session tab."""
        tab = SessionTab(session, self)
        tab.close_requested.connect(self._on_session_close_requested)
        tab.switch_requested.connect(self._on_session_switch_requested)

        self.session_tabs[session.session_id] = tab

        # Insert before the stretch
        self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, tab)

        self.logger.debug(f"Added session tab for: {session.display_name}")

    def _remove_session_tab(self, session_id: str) -> None:
        """Remove a session tab."""
        if session_id in self.session_tabs:
            tab = self.session_tabs[session_id]
            self.sessions_layout.removeWidget(tab)
            tab.deleteLater()
            del self.session_tabs[session_id]

            self.logger.debug(f"Removed session tab for ID: {session_id[:8]}")

    def _on_session_close_requested(self, session_id: str) -> None:
        """Handle session close request."""
        self.session_manager.close_session(session_id)
        self._update_sessions()
        self.session_closed.emit(session_id)

    def _on_session_switch_requested(self, session_id: str) -> None:
        """Handle session switch request."""
        self.session_manager.switch_to_session(session_id)
        self._update_sessions()
        self.session_switched.emit(session_id)

    def _on_add_file_clicked(self) -> None:
        """Handle add file button click."""
        # This would trigger the parent's file open dialog
        if self.parent():
            if hasattr(self.parent(), "_load_file_dialog"):
                self.parent()._load_file_dialog()

    def refresh(self) -> None:
        """Refresh the session display."""
        self._update_sessions()

    def get_session_count(self) -> int:
        """
        Get the number of open sessions.

        Returns:
            int: Number of session tabs currently displayed
        """
        return len(self.session_tabs)

    def get_active_session_tab(self) -> Optional[SessionTab]:
        """
        Get the tab for the currently active session.

        Returns:
            SessionTab or None: Active session tab if one exists
        """
        active_session = self.session_manager.get_active_session()
        if active_session:
            return self.session_tabs.get(active_session.session_id)
        return None
