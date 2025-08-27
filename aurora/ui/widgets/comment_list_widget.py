"""
CommentListWidget - Widget for comment management with table, search and CRUD buttons.
Shows all comments in a table with add, edit, delete and search functionality.
Adapted for Aurora_app structure.
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QFormLayout, QTextEdit, QDoubleSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import logging

from aurora.core.comments import EMSComment


class CommentEditDialog(QDialog):
    """Dialog for adding/editing comments."""
    
    def __init__(self, parent=None, comment: EMSComment = None):
        super().__init__(parent)
        self.comment = comment
        self.is_edit_mode = comment is not None
        
        self.setWindowTitle("Edit Comment" if self.is_edit_mode else "Add Comment")
        self.setModal(True)
        self.resize(400, 300)
        
        self.setup_ui()
        
        if self.is_edit_mode:
            self.load_comment_data()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Time input
        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setRange(0.0, 99999.0)  # Simple large range
        self.time_spinbox.setDecimals(2)
        self.time_spinbox.setSuffix(" s")
        self.time_spinbox.setMinimumWidth(100)
        form_layout.addRow("Time:", self.time_spinbox)
        
        # Label input
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Optional display label")
        form_layout.addRow("Label:", self.label_edit)
        
        # Text input (larger)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter comment text...")
        self.text_edit.setMinimumHeight(150)
        form_layout.addRow("Text:", self.text_edit)
        
        layout.addLayout(form_layout)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def load_comment_data(self):
        """Load existing comment data into form."""
        if self.comment:
            self.time_spinbox.setValue(self.comment.time)
            self.label_edit.setText(self.comment.label or "")
            self.text_edit.setPlainText(self.comment.text)
    
    def get_comment_data(self) -> dict:
        """Get form data as dictionary."""
        return {
            'time_sec': self.time_spinbox.value(),
            'text': self.text_edit.toPlainText().strip(),
            'label': self.label_edit.text().strip() or None
        }
    
    def validate_data(self) -> bool:
        """Validate form data."""
        data = self.get_comment_data()
        
        if not data['text']:
            QMessageBox.warning(self, "Validation Error", "Comment text cannot be empty.")
            return False
        
        if data['time_sec'] < 0:
            QMessageBox.warning(self, "Validation Error", "Time cannot be negative.")
            return False
        
        return True
    
    def accept(self):
        """Override accept to validate first."""
        if self.validate_data():
            super().accept()


class CommentListWidget(QWidget):
    """
    Widget for comment management with table, search and CRUD buttons.
    """
    
    # Signals
    comment_selected = Signal(object)  # EMSComment selected
    comment_time_navigate = Signal(float)  # Navigate to time
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("aurora.ui.CommentListWidget")
        
        # Data
        self.comments: List[EMSComment] = []
        self.filtered_comments: List[EMSComment] = []
        self.data_manager = None
        self.file_path = ""
        
        # UI setup
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Comments")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter comments...")
        self.search_edit.textChanged.connect(self.filter_comments)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_comment)
        buttons_layout.addWidget(self.add_button)
        
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_comment)
        self.edit_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_comment)
        self.delete_button.setEnabled(False)
        buttons_layout.addWidget(self.delete_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Table
        self.table = QTableWidget()
        self.setup_table()
        layout.addWidget(self.table)
        
    def setup_table(self):
        """Setup the comments table."""
        # Columns: Text, Time, Label
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Text", "Time (s)", "Label"])
        
        # Table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Allow multiple selection
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)           # Text
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Label
        
        # Connect signals
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemClicked.connect(self.on_item_clicked)
        self.table.itemChanged.connect(self.on_item_changed)
        
    def set_data_context(self, data_manager, file_path: str):
        """
        Set the data context for comment management.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the current file
        """
        self.logger.info(f"Setting data context - file_path: {file_path}")
        self.logger.info(f"DataManager type: {type(data_manager)}")
        
        # Disconnect previous data manager signals if any
        if self.data_manager:
            try:
                self.data_manager.comments_changed.disconnect(self.on_comments_changed)
            except:
                pass
        
        self.data_manager = data_manager
        self.file_path = file_path
        
        # Connect to data manager signals for automatic updates
        if self.data_manager:
            self.data_manager.comments_changed.connect(self.on_comments_changed)
        
        self.refresh_comments()
        
    def refresh_comments(self):
        """Refresh comments from data manager."""
        if not self.data_manager or not self.file_path:
            self.logger.warning(f"Cannot refresh comments - data_manager: {self.data_manager}, file_path: {self.file_path}")
            return
        
        try:
            # CRITICAL: Safely disconnect itemChanged to prevent infinite loops
            # Use try/except to handle both connection and disconnection errors
            try:
                # First check if the signal is connected at all
                if self.table.itemChanged.disconnect():
                    self.logger.debug("Disconnected itemChanged signal")
            except (TypeError, RuntimeError):
                # Signal wasn't connected or already disconnected, which is fine
                pass
            
            self.logger.debug(f"Getting comments for file: {self.file_path}")
            self.comments = self.data_manager.get_comments(self.file_path)
            self.logger.info(f"Retrieved {len(self.comments)} comments from data manager")
            
            self.filter_comments()  # Apply current filter
            self.logger.info(f"After filtering: {len(self.filtered_comments)} comments displayed")
            
            # Reconnect the signal
            self.table.itemChanged.connect(self.on_item_changed)
            
        except Exception as e:
            self.logger.error(f"Error refreshing comments: {e}", exc_info=True)
            self.comments = []
            self.populate_table([])
            # Ensure signal is reconnected even on error
            try:
                self.table.itemChanged.connect(self.on_item_changed)
            except:
                pass
    
    def filter_comments(self):
        """Filter comments based on search text."""
        search_text = self.search_edit.text().lower().strip()
        
        if not search_text:
            self.filtered_comments = self.comments.copy()
        else:
            self.filtered_comments = []
            for comment in self.comments:
                # Search in text, label, and time
                if (search_text in comment.text.lower() or
                    search_text in (comment.label or "").lower() or
                    search_text in f"{comment.time:.2f}"):
                    self.filtered_comments.append(comment)
        
        self.populate_table(self.filtered_comments)
        
    def populate_table(self, comments: List[EMSComment]):
        """Populate table with comments."""
        # CRITICAL: Safely disconnect itemChanged to prevent infinite loops
        try:
            self.table.itemChanged.disconnect()
            self.logger.debug("Disconnected itemChanged signal")
        except (TypeError, RuntimeError):
            # Signal wasn't connected or already disconnected, which is fine
            self.logger.debug("itemChanged signal was not connected")
        
        self.table.setRowCount(len(comments))
        
        for row, comment in enumerate(comments):
            # Text column (col 0) - truncate if too long
            text = comment.text
            if len(text) > 100:
                text = text[:97] + "..."
            text_item = QTableWidgetItem(text)
            text_item.setToolTip(comment.text)  # Full text in tooltip
            text_item.setData(Qt.UserRole, comment)  # Store comment reference
            self.table.setItem(row, 0, text_item)
            
            # Time column (col 1)
            time_item = QTableWidgetItem(f"{comment.time:.2f}")
            self.table.setItem(row, 1, time_item)
            
            # Label column (col 2)
            label_text = comment.label or ""
            label_item = QTableWidgetItem(label_text)
            self.table.setItem(row, 2, label_item)
            
            # Mark user comments differently
            if comment.user_defined:
                for col in range(3):
                    item = self.table.item(row, col)
                    if item:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
        
        # Update button states
        self.on_selection_changed()
        
        # Reconnect the signal
        self.table.itemChanged.connect(self.on_item_changed)
        
    def on_selection_changed(self):
        """Handle table selection change."""
        selected_comments = self.get_selected_comments()
        has_selection = len(selected_comments) > 0
        
        # Enable/disable buttons based on selection
        self.edit_button.setEnabled(len(selected_comments) == 1)  # Edit only works with single selection
        self.delete_button.setEnabled(has_selection)
        
        # Update delete button text to reflect selection count
        if len(selected_comments) == 0:
            self.delete_button.setText("Delete")
        elif len(selected_comments) == 1:
            self.delete_button.setText("Delete")
        else:
            self.delete_button.setText(f"Delete ({len(selected_comments)})")
        
        # Emit signal for single selection (for navigation)
        if len(selected_comments) == 1:
            self.comment_selected.emit(selected_comments[0])
    
    def on_item_clicked(self, item):
        """Handle click on table item."""
        comment = self.get_selected_comment()
        if comment:
            # Navigate to comment time
            self.logger.debug(f"Clicked comment at {comment.time:.2f}s, emitting navigate signal")
            self.comment_time_navigate.emit(comment.time)
    
    def on_item_changed(self, item):
        """Handle direct table cell editing."""
        if not self.data_manager or not self.file_path:
            return
            
        # Get the comment for this row
        comment = item.data(Qt.UserRole)
        if not comment:
            # For columns other than text (col 0), get comment from text column
            text_item = self.table.item(item.row(), 0)
            if text_item:
                comment = text_item.data(Qt.UserRole)
        
        if not comment:
            self.logger.warning("Could not find comment for edited item")
            return
        
        try:
            from aurora.core.comments import get_comment_manager
            comment_manager = get_comment_manager()
            
            # Get new values based on column
            new_text = None
            new_time = None 
            new_label = None
            
            if item.column() == 0:  # Text column
                new_text = item.text()
            elif item.column() == 1:  # Time column
                try:
                    new_time = float(item.text())
                    if new_time < 0:
                        raise ValueError("Time cannot be negative")
                except ValueError as e:
                    QMessageBox.warning(self, "Invalid Time", f"Invalid time value: {e}")
                    # Revert to original value
                    item.setText(f"{comment.time:.2f}")
                    return
            elif item.column() == 2:  # Label column
                new_label = item.text().strip() or None
            
            # Update comment through CommentManager
            updates = {}
            if new_text is not None:
                updates['text'] = new_text
            if new_time is not None:
                updates['time_sec'] = new_time
            if new_label is not None:
                updates['label'] = new_label
                
            comment_manager.request_update_comment(
                self.file_path, 
                comment.comment_id, 
                **updates
            )
            
            self.logger.info(f"Updated comment via table editing")
            
        except Exception as e:
            self.logger.error(f"Error updating comment via table: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update comment: {e}")
            # Refresh to revert changes if update failed
            self.refresh_comments()
    
    def get_selected_comment(self) -> Optional[EMSComment]:
        """Get the currently selected comment."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            text_item = self.table.item(current_row, 0)  # Comment stored in text column
            if text_item:
                return text_item.data(Qt.UserRole)
        return None
    
    def get_selected_comments(self) -> List[EMSComment]:
        """Get all currently selected comments."""
        selected_comments = []
        selected_rows = set()
        
        # Get all selected items and extract unique row indices
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        # Collect comments from selected rows
        for row in selected_rows:
            text_item = self.table.item(row, 0)  # Comment stored in text column
            if text_item:
                comment = text_item.data(Qt.UserRole)
                if comment:
                    selected_comments.append(comment)
        
        return selected_comments
    
    def add_comment(self):
        """Add a new comment using comment manager."""
        if not self.data_manager or not self.file_path:
            QMessageBox.warning(self, "Error", "No file loaded.")
            return
        
        dialog = CommentEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_comment_data()
            
            try:
                # Add comment through CommentManager
                from aurora.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                # Add user comment through request system
                comment_manager.request_add_comment(
                    file_path=self.file_path,
                    text=data['text'],
                    time_sec=data['time_sec'],
                    label=data['label']
                )
                
                # Navigate to new comment
                self.comment_time_navigate.emit(data['time_sec'])
                
                self.logger.info(f"Added comment at {data['time_sec']:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error adding comment: {e}")
                QMessageBox.critical(self, "Error", f"Failed to add comment: {e}")
    
    def edit_comment(self):
        """Edit the selected comment."""
        comment = self.get_selected_comment()
        if not comment:
            return
        
        if not self.data_manager or not self.file_path:
            QMessageBox.warning(self, "Error", "No file loaded.")
            return
        
        dialog = CommentEditDialog(self, comment)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_comment_data()
            
            try:
                # Update comment through CommentManager
                from aurora.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                comment_manager.request_update_comment(
                    file_path=self.file_path,
                    comment_id=comment.comment_id,
                    text=data['text'],
                    time_sec=data['time_sec'],
                    label=data['label']
                )
                
                self.logger.info(f"Updated comment at {data['time_sec']:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error updating comment: {e}")
                QMessageBox.critical(self, "Error", f"Failed to update comment: {e}")
    
    def delete_comment(self):
        """Delete the selected comment(s)."""
        selected_comments = self.get_selected_comments()
        if not selected_comments:
            return
        
        if not self.data_manager or not self.file_path:
            QMessageBox.warning(self, "Error", "No file loaded.")
            return
        
        # Confirm deletion with appropriate message for single/multiple selection
        if len(selected_comments) == 1:
            comment = selected_comments[0]
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete the comment at {comment.time:.2f}s?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
        else:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete {len(selected_comments)} selected comments?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
        
        if reply == QMessageBox.Yes:
            try:
                from aurora.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                deleted_count = 0
                failed_count = 0
                
                # Delete all selected comments
                for comment in selected_comments:
                    try:
                        # Debug: Log the comment_id we're trying to delete
                        self.logger.debug(f"Attempting to delete comment - ID: '{comment.comment_id}' (type: {type(comment.comment_id)}) at time {comment.time:.2f}s")
                        
                        comment_manager.request_delete_comment(self.file_path, comment.comment_id)
                        deleted_count += 1
                        self.logger.info(f"Delete request sent for comment {comment.comment_id} at {comment.time:.2f}s")
                        
                    except Exception as e:
                        failed_count += 1
                        self.logger.error(f"Error deleting comment {comment.comment_id}: {e}")
                
                # Show summary if there were failures
                if failed_count > 0:
                    QMessageBox.warning(
                        self, 
                        "Deletion Summary", 
                        f"Deleted {deleted_count} comments successfully.\n{failed_count} comments failed to delete."
                    )
                elif len(selected_comments) > 1:
                    self.logger.info(f"Successfully deleted {deleted_count} comments")
                    
            except Exception as e:
                self.logger.error(f"Error during mass deletion: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete comments: {e}")
    
    def navigate_to_comment(self, comment: EMSComment):
        """Navigate to a specific comment and select it in table."""
        for row in range(self.table.rowCount()):
            text_item = self.table.item(row, 0)
            stored_comment = text_item.data(Qt.UserRole) if text_item else None
            if stored_comment and stored_comment.comment_id == comment.comment_id:
                self.table.selectRow(row)
                self.comment_time_navigate.emit(comment.time)
                break
    
    def clear_selection(self):
        """Clear table selection."""
        self.table.clearSelection()
    
    def on_comments_changed(self, file_path: str):
        """Handle comments changed signal from DataManager."""
        if file_path == self.file_path:
            self.logger.debug(f"Comments changed for {file_path}, refreshing display")
            self.refresh_comments()