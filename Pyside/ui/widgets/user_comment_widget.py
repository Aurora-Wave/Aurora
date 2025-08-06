"""
User Comment Widget for TiltTab
Allows users to add, edit, and manage custom comments with timestamps.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QDialog, QTextEdit,
    QDialogButtonBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QGroupBox, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal as QtSignal, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap

from Pyside.core import get_user_logger
from Pyside.core.config_manager import get_config_manager


class UserComment:
    """Data class representing a user comment with timestamp and metadata."""
    
    def __init__(self, 
                 timestamp: float,
                 comment: str,
                 comment_type: str = "User",
                 created_at: Optional[datetime] = None,
                 file_path: Optional[str] = None):
        """
        Initialize user comment.
        
        Args:
            timestamp: Time position in seconds
            comment: Comment text
            comment_type: Type/category of comment
            created_at: When comment was created
            file_path: Associated file path
        """
        self.timestamp = float(timestamp)
        self.comment = str(comment).strip()
        self.comment_type = str(comment_type)
        self.created_at = created_at or datetime.now()
        self.file_path = file_path
        self.id = f"{self.timestamp:.3f}_{self.created_at.timestamp()}"
    
    def to_dict(self) -> Dict:
        """Convert comment to dictionary for serialization."""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'comment': self.comment,
            'comment_type': self.comment_type,
            'created_at': self.created_at.isoformat(),
            'file_path': self.file_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserComment':
        """Create comment from dictionary."""
        comment = cls(
            timestamp=data['timestamp'],
            comment=data['comment'],
            comment_type=data.get('comment_type', 'User'),
            created_at=datetime.fromisoformat(data['created_at']),
            file_path=data.get('file_path')
        )
        comment.id = data['id']
        return comment
    
    def __str__(self) -> str:
        return f"{self.timestamp:.1f}s: {self.comment}"
    
    def __repr__(self) -> str:
        return f"UserComment(timestamp={self.timestamp}, comment='{self.comment}')"


class CommentEditDialog(QDialog):
    """Dialog for creating or editing user comments."""
    
    def __init__(self, 
                 parent=None,
                 comment: Optional[UserComment] = None,
                 current_timestamp: Optional[float] = None):
        """
        Initialize comment edit dialog.
        
        Args:
            parent: Parent widget
            comment: Existing comment to edit (None for new comment)
            current_timestamp: Current time position for new comments
        """
        super().__init__(parent)
        self.comment = comment
        self.current_timestamp = current_timestamp or 0.0
        
        self.setWindowTitle("Add Comment" if comment is None else "Edit Comment")
        self.setModal(True)
        self.resize(400, 300)
        
        self.setup_ui()
        
        if self.comment:
            self.populate_fields()
    
    def setup_ui(self) -> None:
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout for comment fields
        form_layout = QFormLayout()
        
        # Timestamp input
        self.timestamp_spinbox = QDoubleSpinBox()
        self.timestamp_spinbox.setRange(0.0, 999999.0)
        self.timestamp_spinbox.setDecimals(3)
        self.timestamp_spinbox.setSuffix(" s")
        self.timestamp_spinbox.setValue(self.current_timestamp)
        form_layout.addRow("Timestamp:", self.timestamp_spinbox)
        
        # Comment type selection
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "User", "Marker", "Event", "Analysis", "Note", "Warning", "Custom"
        ])
        form_layout.addRow("Type:", self.type_combo)
        
        # Comment text
        self.comment_text = QTextEdit()
        self.comment_text.setMaximumHeight(100)
        self.comment_text.setPlaceholderText("Enter your comment here...")
        form_layout.addRow("Comment:", self.comment_text)
        
        layout.addLayout(form_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        # Enable/disable OK button based on comment text
        self.comment_text.textChanged.connect(self.validate_input)
        self.validate_input()
    
    def populate_fields(self) -> None:
        """Populate fields with existing comment data."""
        if self.comment:
            self.timestamp_spinbox.setValue(self.comment.timestamp)
            self.type_combo.setCurrentText(self.comment.comment_type)
            self.comment_text.setPlainText(self.comment.comment)
    
    def validate_input(self) -> None:
        """Validate input and enable/disable OK button."""
        comment_text = self.comment_text.toPlainText().strip()
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(len(comment_text) > 0)
    
    def get_comment_data(self) -> Tuple[float, str, str]:
        """
        Get comment data from dialog.
        
        Returns:
            (timestamp, comment_text, comment_type) tuple
        """
        return (
            self.timestamp_spinbox.value(),
            self.comment_text.toPlainText().strip(),
            self.type_combo.currentText()
        )


class UserCommentWidget(QWidget):
    """
    Widget for managing user comments in the EventTab.
    
    Provides functionality to:
    - Add new comments at specific timestamps
    - Edit existing comments
    - Delete comments
    - Save/load comments to/from file
    - Display comments in plots as markers
    """
    
    # Signals
    comment_added = QtSignal(UserComment)
    comment_edited = QtSignal(UserComment)
    comment_deleted = QtSignal(str)  # comment ID
    comments_changed = QtSignal(list)  # list of comments
    
    def __init__(self, parent=None):
        """Initialize user comment widget."""
        super().__init__(parent)
        
        self.logger = get_user_logger(self.__class__.__name__)
        self.config_manager = get_config_manager()
        
        # Comment storage
        self.comments: Dict[str, UserComment] = {}  # id -> comment
        self.current_file_path: Optional[str] = None
        
        # UI setup
        self.setup_ui()
        self.connect_signals()
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.save_comments)
        self.auto_save_timer.setSingleShot(True)
    
    def setup_ui(self) -> None:
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("User Comments")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Add comment button
        self.add_button = QPushButton("Add Comment")
        self.add_button.setToolTip("Add a new comment at current time position")
        header_layout.addWidget(self.add_button)
        
        layout.addLayout(header_layout)
        
        # Comments list
        self.comment_list = QListWidget()
        self.comment_list.setMaximumHeight(150)
        self.comment_list.setAlternatingRowColors(True)
        layout.addWidget(self.comment_list)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.edit_button = QPushButton("Edit")
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        button_layout.addStretch()
        
        self.clear_button = QPushButton("Clear All")
        button_layout.addWidget(self.clear_button)
        
        self.export_button = QPushButton("Export")
        self.export_button.setToolTip("Export comments to file")
        button_layout.addWidget(self.export_button)
        
        layout.addLayout(button_layout)
        
        # Status info
        self.status_label = QLabel("No comments")
        self.status_label.setStyleSheet("color: gray; font-size: 9px;")
        layout.addWidget(self.status_label)
    
    def connect_signals(self) -> None:
        """Connect widget signals."""
        self.add_button.clicked.connect(self.add_comment_dialog)
        self.edit_button.clicked.connect(self.edit_selected_comment)
        self.delete_button.clicked.connect(self.delete_selected_comment)
        self.clear_button.clicked.connect(self.clear_all_comments)
        self.export_button.clicked.connect(self.export_comments)
        
        self.comment_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.comment_list.itemDoubleClicked.connect(self.edit_selected_comment)
    
    def set_file_path(self, file_path: str) -> None:
        """
        Set current file path and load associated comments.
        
        Args:
            file_path: Path to the current data file
        """
        if file_path != self.current_file_path:
            # Save current comments if any
            if self.current_file_path and self.comments:
                self.save_comments()
            
            self.current_file_path = file_path
            self.load_comments()
            
            self.logger.debug(f"File path set to: {file_path}")
    
    def add_comment_dialog(self, timestamp: Optional[float] = None) -> None:
        """
        Show dialog to add a new comment.
        
        Args:
            timestamp: Timestamp for the comment (if None, will use 0.0)
        """
        dialog = CommentEditDialog(self, current_timestamp=timestamp or 0.0)
        
        if dialog.exec() == QDialog.Accepted:
            timestamp, comment_text, comment_type = dialog.get_comment_data()
            self.add_comment(timestamp, comment_text, comment_type)
    
    def add_comment(self, 
                   timestamp: float,
                   comment_text: str,
                   comment_type: str = "User") -> UserComment:
        """
        Add a new user comment.
        
        Args:
            timestamp: Time position in seconds
            comment_text: Comment text
            comment_type: Type of comment
            
        Returns:
            Created UserComment object
        """
        # Create new comment
        comment = UserComment(
            timestamp=timestamp,
            comment=comment_text,
            comment_type=comment_type,
            file_path=self.current_file_path
        )
        
        # Store comment
        self.comments[comment.id] = comment
        
        # Update UI
        self.refresh_comment_list()
        
        # Emit signals
        self.comment_added.emit(comment)
        self.comments_changed.emit(list(self.comments.values()))
        
        # Schedule auto-save
        self.schedule_auto_save()
        
        self.logger.info(f"Added comment: {comment}")
        return comment
    
    def edit_selected_comment(self) -> None:
        """Edit the currently selected comment."""
        current_item = self.comment_list.currentItem()
        if not current_item:
            return
            
        comment_id = current_item.data(Qt.UserRole)
        comment = self.comments.get(comment_id)
        
        if comment:
            dialog = CommentEditDialog(self, comment=comment)
            
            if dialog.exec() == QDialog.Accepted:
                timestamp, comment_text, comment_type = dialog.get_comment_data()
                
                # Update comment
                comment.timestamp = timestamp
                comment.comment = comment_text
                comment.comment_type = comment_type
                
                # Refresh UI
                self.refresh_comment_list()
                
                # Emit signals
                self.comment_edited.emit(comment)
                self.comments_changed.emit(list(self.comments.values()))
                
                # Schedule auto-save
                self.schedule_auto_save()
                
                self.logger.info(f"Edited comment: {comment}")
    
    def delete_selected_comment(self) -> None:
        """Delete the currently selected comment."""
        current_item = self.comment_list.currentItem()
        if not current_item:
            return
        
        comment_id = current_item.data(Qt.UserRole)
        comment = self.comments.get(comment_id)
        
        if comment:
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Delete Comment",
                f"Are you sure you want to delete this comment?\n\n{comment}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Remove comment
                del self.comments[comment_id]
                
                # Refresh UI
                self.refresh_comment_list()
                
                # Emit signals
                self.comment_deleted.emit(comment_id)
                self.comments_changed.emit(list(self.comments.values()))
                
                # Schedule auto-save
                self.schedule_auto_save()
                
                self.logger.info(f"Deleted comment: {comment}")
    
    def clear_all_comments(self) -> None:
        """Clear all comments after confirmation."""
        if not self.comments:
            return
            
        reply = QMessageBox.question(
            self,
            "Clear All Comments",
            f"Are you sure you want to delete all {len(self.comments)} comments?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear all comments
            self.comments.clear()
            
            # Refresh UI
            self.refresh_comment_list()
            
            # Emit signal
            self.comments_changed.emit([])
            
            # Schedule auto-save
            self.schedule_auto_save()
            
            self.logger.info("All comments cleared")
    
    def refresh_comment_list(self) -> None:
        """Refresh the comment list display."""
        self.comment_list.clear()
        
        # Sort comments by timestamp
        sorted_comments = sorted(self.comments.values(), key=lambda c: c.timestamp)
        
        for comment in sorted_comments:
            # Create display text
            display_text = f"{comment.timestamp:.1f}s [{comment.comment_type}]: {comment.comment}"
            
            # Create list item
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, comment.id)
            item.setToolTip(f"Created: {comment.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            self.comment_list.addItem(item)
        
        # Update status
        count = len(self.comments)
        if count == 0:
            self.status_label.setText("No comments")
        elif count == 1:
            self.status_label.setText("1 comment")
        else:
            self.status_label.setText(f"{count} comments")
    
    def on_selection_changed(self) -> None:
        """Handle comment selection changes."""
        has_selection = self.comment_list.currentItem() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
    
    def get_comments_for_timerange(self, start_time: float, end_time: float) -> List[UserComment]:
        """
        Get comments within a specific time range.
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            List of comments within the time range
        """
        return [
            comment for comment in self.comments.values()
            if start_time <= comment.timestamp <= end_time
        ]
    
    def get_all_comments(self) -> List[UserComment]:
        """Get all comments sorted by timestamp."""
        return sorted(self.comments.values(), key=lambda c: c.timestamp)
    
    def get_comment_file_path(self) -> Optional[Path]:
        """Get the path for saving comments."""
        if not self.current_file_path:
            return None
        
        # Create comments directory if it doesn't exist
        data_file_path = Path(self.current_file_path)
        comments_dir = data_file_path.parent / "comments"
        comments_dir.mkdir(exist_ok=True)
        
        # Comment file named after data file
        comment_file = comments_dir / f"{data_file_path.stem}_comments.json"
        return comment_file
    
    def save_comments(self) -> bool:
        """
        Save comments to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            comment_file = self.get_comment_file_path()
            if not comment_file:
                return True
            
            # If no comments exist, delete the comment file instead of saving empty file
            if not self.comments:
                if comment_file.exists():
                    comment_file.unlink()
                    self.logger.debug(f"Deleted empty comment file: {comment_file}")
                return True
            
            # Convert comments to serializable format
            comments_data = {
                'file_path': self.current_file_path,
                'saved_at': datetime.now().isoformat(),
                'comments': [comment.to_dict() for comment in self.comments.values()]
            }
            
            # Save to file
            with open(comment_file, 'w', encoding='utf-8') as f:
                json.dump(comments_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved {len(self.comments)} comments to {comment_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving comments: {e}", exc_info=True)
            return False
    
    def load_comments(self) -> bool:
        """
        Load comments from file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            comment_file = self.get_comment_file_path()
            if not comment_file or not comment_file.exists():
                self.comments.clear()
                self.refresh_comment_list()
                return True
            
            # Load from file
            with open(comment_file, 'r', encoding='utf-8') as f:
                comments_data = json.load(f)
            
            # Convert back to UserComment objects
            self.comments.clear()
            for comment_data in comments_data.get('comments', []):
                comment = UserComment.from_dict(comment_data)
                self.comments[comment.id] = comment
            
            # Refresh UI
            self.refresh_comment_list()
            
            # Emit signal
            self.comments_changed.emit(list(self.comments.values()))
            
            self.logger.debug(f"Loaded {len(self.comments)} comments from {comment_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading comments: {e}", exc_info=True)
            self.comments.clear()
            self.refresh_comment_list()
            return False
    
    def export_comments(self) -> None:
        """Export comments to a CSV or text file."""
        if not self.comments:
            QMessageBox.information(self, "Export Comments", "No comments to export.")
            return
        
        try:
            from PySide6.QtWidgets import QFileDialog
            
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Comments",
                f"comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                # Export comments
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_path.endswith('.csv'):
                        # CSV format
                        f.write("Timestamp,Type,Comment,Created\n")
                        for comment in sorted(self.comments.values(), key=lambda c: c.timestamp):
                            f.write(f"{comment.timestamp},{comment.comment_type},\"{comment.comment}\",{comment.created_at.isoformat()}\n")
                    else:
                        # Text format
                        f.write("User Comments Export\n")
                        f.write("=" * 50 + "\n\n")
                        for comment in sorted(self.comments.values(), key=lambda c: c.timestamp):
                            f.write(f"{comment.timestamp:.1f}s [{comment.comment_type}]: {comment.comment}\n")
                            f.write(f"  Created: {comment.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                QMessageBox.information(self, "Export Complete", f"Comments exported to:\n{file_path}")
                self.logger.info(f"Exported {len(self.comments)} comments to {file_path}")
                
        except Exception as e:
            self.logger.error(f"Error exporting comments: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Error exporting comments:\n{str(e)}")
    
    def schedule_auto_save(self) -> None:
        """Schedule auto-save of comments."""
        self.auto_save_timer.stop()
        self.auto_save_timer.start(2000)  # Auto-save after 2 seconds of inactivity