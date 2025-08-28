

class EMSComment:
    """
    Represents a physiological comment (annotation) in a recording.
    Comments are global to the entire file and synchronized across all channels.
    Includes timing, raw text, and metadata to assist with navigation, editing, and labeling.
    """

    def __init__(self, text, time_sec, comment_id, user_defined=False, label=None):
        self.text = text                    # Comment text
        self.time = time_sec                # Absolute time in seconds (universal)
        self.comment_id = comment_id        # Unique ID (local to file)
        self.user_defined = user_defined    # Whether this comment was added manually by the user
        self.label = label or text          # Display label, defaults to text if not provided

    def to_dict(self):
        """
        Return the comment as a dictionary, useful for table display or export.
        """
        return {
            "id": self.comment_id,
            "text": self.text,
            "time_sec": self.time,
            "user_defined": self.user_defined
        }

    def update(self, text=None, time=None, label=None):
        """
        Update comment text, time (e.g. after user correction).
        """
        if text is not None:
            self.text = text
        if time is not None:
            self.time = time
        if label is not None:
            self.label = label

    def __repr__(self):
        tag = "(user)" if self.user_defined else ""
        return f"EMSComment(id={self.comment_id}, time={self.time:.2f}s, label='{self.label}' {tag}, text='{self.text}')"


from PySide6.QtCore import QObject, Signal
from typing import Optional, List
import bisect


class CommentManager(QObject):
    """
    Comment manager implementing CRUD operations with business logic.
    
    Architecture:
    - Implements CRUD operations directly
    - Accesses data through DataManager
    - Emits change notifications for cache updates
    """
    
    # Change notification signals for DataManager cache updates
    comment_created = Signal(str, object)  # (file_path, comment)
    comment_updated = Signal(str, str, dict)  # (file_path, comment_id, updates)
    comment_deleted = Signal(str, str)  # (file_path, comment_id)
    
    def __init__(self):
        super().__init__()
        from aurora.core import get_user_logger
        self.logger = get_user_logger("CommentManager")
        self._data_manager = None  # Will be injected
    
    def add_comment(self, file_path: str, text: str, time_sec: float, label: str = None) -> EMSComment:
        """Add a new comment with validation and business logic"""
        # Validate input
        if not text.strip():
            raise ValueError("Comment text cannot be empty")
        if time_sec < 0:
            raise ValueError("Time cannot be negative")
        
        # Generate unique ID
        next_id = self._get_next_comment_id(file_path)
        
        # Create comment
        comment = EMSComment(
            text=text.strip(),
            time_sec=time_sec,
            comment_id=next_id,
            user_defined=True,
            label=label.strip() if label else None
        )
        
        # Emit notification for DataManager to update cache
        self.comment_created.emit(file_path, comment)
        self.logger.info(f"Comment created: ID {next_id} at {time_sec:.2f}s in {file_path}")
        
        return comment
        
    def update_comment(self, file_path: str, comment_id: str, **updates) -> bool:
        """Update an existing comment with validation"""
        # Validate updates
        if 'text' in updates and not updates['text'].strip():
            raise ValueError("Comment text cannot be empty")
        if 'time_sec' in updates and updates['time_sec'] < 0:
            raise ValueError("Time cannot be negative")
        
        # Emit notification for DataManager to update cache
        self.comment_updated.emit(file_path, comment_id, updates)
        self.logger.info(f"Comment updated: ID {comment_id} in {file_path}")
        
        return True
        
    def delete_comment(self, file_path: str, comment_id: str) -> bool:
        """Delete a comment"""
        comment_id_str = str(comment_id)
        
        # Emit notification for DataManager to update cache
        self.comment_deleted.emit(file_path, comment_id_str)
        self.logger.info(f"Comment deleted: ID {comment_id_str} in {file_path}")
        
        return True
    
    def set_data_manager(self, data_manager):
        """Inject DataManager dependency"""
        self._data_manager = data_manager
    
    def _get_next_comment_id(self, file_path: str) -> int:
        """Generate next available comment ID for a file"""
        if not self._data_manager:
            raise RuntimeError("DataManager not injected - call set_data_manager() first")
        
        # Access comments from DataManager to find max ID
        try:
            comments = self._data_manager.get_comments(file_path)
            if not comments:
                return 1
            
            max_id = max(c.comment_id for c in comments)
            return max_id + 1
        except Exception as e:
            self.logger.warning(f"Failed to get existing comments for ID generation: {e}")
            return 1
    

# Global instance
_comment_manager_instance = None

def get_comment_manager() -> CommentManager:
    """Get the global CommentManager instance."""
    global _comment_manager_instance
    if _comment_manager_instance is None:
        _comment_manager_instance = CommentManager()
    return _comment_manager_instance