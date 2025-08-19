"""
CommentListWidget - Widget para gestión de comentarios con tabla, búsqueda y botones CRUD.
Muestra todos los comentarios en una tabla con funcionalidades de agregar, editar, eliminar y buscar.
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

from Pyside.core import get_user_logger
from Pyside.core.comments import EMSComment


class CommentEditDialog(QDialog):
    """Dialog para agregar/editar comentarios."""
    
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
    Widget para gestión de comentarios con tabla, búsqueda y botones CRUD.
    """
    
    # Signals
    comment_selected = Signal(object)  # EMSComment selected
    comment_time_navigate = Signal(float)  # Navigate to time
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_user_logger("CommentListWidget")
        
        # Data
        self.comments: List[EMSComment] = []
        self.filtered_comments: List[EMSComment] = []
        self.data_manager = None
        self.file_path = ""
        
        # Comments are now managed via Qt signals in CommentManager
        # No need for separate marker management
        
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
        # Columns: Text, Time, Label (reordered)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Text", "Time (s)", "Label"])
        
        # Table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)           # Text
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Label
        
        # Connect signals
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
    def set_data_context(self, data_manager, file_path: str):
        """
        Set the data context for comment management.
        
        Args:
            data_manager: DataManager instance
            file_path: Path to the current file
        """
        self.data_manager = data_manager
        self.file_path = file_path
        self.refresh_comments()
        
        # Comments are automatically synchronized via Qt signals
        # No manual initialization needed
        
    def refresh_comments(self):
        """Refresh comments from data manager."""
        if not self.data_manager or not self.file_path:
            return
        
        try:
            self.comments = self.data_manager.get_comments(self.file_path)
            self.filter_comments()  # Apply current filter
            self.logger.debug(f"Refreshed {len(self.comments)} comments")
        except Exception as e:
            self.logger.error(f"Error refreshing comments: {e}")
            self.comments = []
            self.populate_table([])
    
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
        
    def on_selection_changed(self):
        """Handle table selection change."""
        has_selection = bool(self.table.selectedItems())
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        
        if has_selection:
            comment = self.get_selected_comment()
            if comment:
                self.comment_selected.emit(comment)
    
    def on_item_double_clicked(self, item):
        """Handle double-click on table item."""
        comment = self.get_selected_comment()
        if comment:
            # Navigate to comment time
            self.comment_time_navigate.emit(comment.time)
    
    def get_selected_comment(self) -> Optional[EMSComment]:
        """Get the currently selected comment."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            text_item = self.table.item(current_row, 0)  # Comment stored in text column now
            if text_item:
                return text_item.data(Qt.UserRole)
        return None
    
    def add_comment(self):
        """Add a new comment using correct separation of concerns."""
        if not self.data_manager or not self.file_path:
            QMessageBox.warning(self, "Error", "No file loaded.")
            return
        
        dialog = CommentEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_comment_data()
            
            try:
                # Step 1: Add comment through CommentManager (CRUD + persistence)
                from Pyside.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                new_comment = comment_manager.add_user_comment(
                    self.file_path,
                    data['text'],
                    data['time_sec'],
                    data['label']
                )
                
                # Step 2: Cache updated automatically by CommentManager
                # Step 3: Plots updated automatically via Qt signals
                # Step 4: Refresh UI display
                self.refresh_comments()
                
                # Navigate to new comment
                self.comment_time_navigate.emit(data['time_sec'])
                
                self.logger.info(f"Added comment at {data['time_sec']:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error adding comment: {e}")
                QMessageBox.critical(self, "Error", f"Failed to add comment: {e}")
    
    def edit_comment(self):
        """Edit the selected comment using correct separation of concerns."""
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
                # Step 1: Update comment through CommentManager (CRUD + persistence)
                from Pyside.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                comment_manager.update_user_comment(
                    self.file_path,
                    comment,
                    text=data['text'],
                    time=data['time_sec'],
                    label=data['label']
                )
                
                # Step 2: Cache updated automatically by CommentManager
                # Step 3: Plots updated automatically via Qt signals
                # Step 4: Refresh UI display
                self.refresh_comments()
                
                self.logger.info(f"Updated comment at {data['time_sec']:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error updating comment: {e}")
                QMessageBox.critical(self, "Error", f"Failed to update comment: {e}")
    
    def delete_comment(self):
        """Delete the selected comment using correct separation of concerns."""
        comment = self.get_selected_comment()
        if not comment:
            return
        
        if not self.data_manager or not self.file_path:
            QMessageBox.warning(self, "Error", "No file loaded.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the comment at {comment.time:.2f}s?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Step 1: Remove comment through CommentManager (CRUD + persistence)
                from Pyside.core.comments import get_comment_manager
                comment_manager = get_comment_manager()
                
                success = comment_manager.remove_user_comment(self.file_path, comment)
                
                if success:
                    # Step 2: Cache updated automatically by CommentManager
                    # Step 3: Plots updated automatically via Qt signals
                    # Step 4: Refresh UI display
                    self.refresh_comments()
                    self.logger.info(f"Deleted comment at {comment.time:.2f}s")
                else:
                    QMessageBox.warning(self, "Error", "Comment not found for deletion.")
                
            except Exception as e:
                self.logger.error(f"Error deleting comment: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete comment: {e}")
    
    def navigate_to_comment(self, comment: EMSComment):
        """Navigate to a specific comment and select it in table."""
        for row in range(self.table.rowCount()):
            time_item = self.table.item(row, 0)
            if time_item and time_item.data(Qt.UserRole) == comment:
                self.table.selectRow(row)
                self.comment_time_navigate.emit(comment.time)
                break
    
    def clear_selection(self):
        """Clear table selection."""
        self.table.clearSelection()


if __name__ == "__main__":
    import sys
    import os
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog, QLabel, QMessageBox
    
    # Add Aurora2.0 paths
    aurora2_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app/Pyside"
    if aurora2_path not in sys.path:
        sys.path.insert(0, aurora2_path)
    
    aurora2_app_path = "C:/Users/Poney/Desktop/Python/Aurora2.0/Aurora_app"
    if aurora2_app_path not in sys.path:
        sys.path.insert(0, aurora2_app_path)
    
    from Pyside.data.data_manager import DataManager
    
    class CommentListDebugWindow(QMainWindow):
        """Simple debug window for CommentListWidget."""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CommentListWidget Debug")
            self.setGeometry(200, 200, 800, 600)
            
            # Data
            self.data_manager = DataManager()
            self.current_file = ""
            
            self.setup_ui()
            
        def setup_ui(self):
            """Setup simple UI."""
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            
            # Load button
            self.load_button = QPushButton("Load ADItch File")
            self.load_button.clicked.connect(self.load_file)
            layout.addWidget(self.load_button)
            
            # File info label
            self.file_label = QLabel("No file loaded")
            layout.addWidget(self.file_label)
            
            # Comment widget
            self.comment_widget = CommentListWidget()
            self.comment_widget.comment_time_navigate.connect(self.on_navigate)
            layout.addWidget(self.comment_widget)
            
        def load_file(self):
            """Load an ADItch file."""
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open ADItch File",
                "",
                "ADItch Files (*.adicht);;All Files (*)"
            )
            
            if file_path:
                print(f"DEBUG: Selected file: {file_path}")
                try:
                    # Load with DataManager
                    print("DEBUG: Calling data_manager.load_file()...")
                    self.data_manager.load_file(file_path)  # load_file returns None
                    print("DEBUG: load_file completed (void function)")
                    
                    # Check if file was actually loaded by checking if it's in _files
                    if file_path in self.data_manager._files:
                        self.current_file = file_path
                        filename = os.path.basename(file_path)
                        print(f"DEBUG: File loaded successfully: {filename}")
                        
                        # Check if file is in data manager
                        print(f"DEBUG: Files in data_manager: {list(self.data_manager._files.keys())}")
                        
                        # Get comments
                        print("DEBUG: Getting comments...")
                        comments = self.data_manager.get_comments(file_path)
                        print(f"DEBUG: Got {len(comments)} comments")
                        print(f"DEBUG: Comment types: {[type(c).__name__ for c in comments[:3]]}")  # First 3
                        
                        # Update UI
                        self.file_label.setText(f"Loaded: {filename} ({len(comments)} comments)")
                        
                        # Debug DataManager methods
                        print(f"DEBUG: DataManager methods: {[m for m in dir(self.data_manager) if 'comment' in m.lower()]}")
                        
                        # Set data in comment widget
                        print("DEBUG: Setting data context in comment widget...")
                        self.comment_widget.set_data_context(self.data_manager, file_path)
                        print("DEBUG: Data context set successfully")
                        
                        print(f"SUCCESS: Loaded {filename} with {len(comments)} comments")
                        
                    else:
                        print("DEBUG: DataManager.load_file() returned False")
                        QMessageBox.warning(self, "Error", "Failed to load file - DataManager returned False")
                        
                except Exception as e:
                    print(f"DEBUG: Exception occurred: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                    QMessageBox.critical(self, "Error", f"Error loading file: {e}")
            else:
                print("DEBUG: No file selected")
        
        def on_navigate(self, time_sec: float):
            """Handle navigation signal."""
            print(f"Navigate to: {time_sec:.2f}s")
    
    # Run application
    app = QApplication(sys.argv)
    window = CommentListDebugWindow()
    window.show()
    
    print("CommentListWidget Debug")
    print("Click 'Load ADItch File' to test")
    
    sys.exit(app.exec())