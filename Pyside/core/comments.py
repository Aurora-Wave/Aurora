
class EMSComment:
    """
    Represents a physiological comment (annotation) in a recording.
    Comments are global to the entire file and synchronized across all channels.
    Includes timing, raw text, and metadata to assist with navigation, editing, and labeling.
    """

    def __init__(self, text, tick_position, comment_id, tick_dt, time_sec, user_defined=False, label=None):
        self.text = text                    # Original comment text (raw from LabChart)
        self.tick_position = tick_position  # Index of the sample tick
        self.comment_id = comment_id        # Unique ID (local to file)
        self.tick_dt = tick_dt              # Tick duration (s)
        self.time = time_sec                # Absolute time (s)
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

class CommentManager(QObject):
    """
    Complete CRUD manager for comment operations with persistence.
    Handles all comment business logic without caching.
    Cache management is DataManager's exclusive responsibility.
    """
    
    # Qt Signals for global plot synchronization
    comment_added = Signal(str, object)    # (file_path, comment)
    comment_updated = Signal(str, object)  # (file_path, comment) 
    comment_removed = Signal(str, str)     # (file_path, comment_id)
    comments_loaded = Signal(str, list)    # (file_path, all_comments)
    
    def __init__(self):
        super().__init__()
        from Pyside.core import get_user_logger
        self.logger = get_user_logger("CommentManager")
        self._next_comment_id = 10000  # Start user IDs high to avoid conflicts
        self._data_manager = None  # Reference to DataManager for cache modification
    
    def set_data_manager(self, data_manager):
        """Set reference to DataManager for direct cache modification."""
        self._data_manager = data_manager
    
    def get_all_comments_from_loader(self, loader) -> list:
        """
        Load all comments from any loader type. Used only during initial file loading.
        
        Args:
            loader: Any loader instance (AditchLoader, EDFLoader, etc.)
            
        Returns:
            list: All comments from the loader
        """
        try:
            comments = loader.get_all_comments()
            self.logger.debug(f"Loaded {len(comments)} comments from {type(loader).__name__}")
            
            # Emit signal for initial comments load (file_path will be set by caller)
            if hasattr(loader, 'path') and loader.path:
                self.comments_loaded.emit(loader.path, comments)
            
            return comments
        except Exception as e:
            self.logger.error(f"Error loading comments from loader: {e}")
            return []
    
    def create_user_comment(self, text: str, time_sec: float, label: str = None) -> EMSComment:
        """
        Create a new user comment object (utility function).
        
        Args:
            text: Comment text
            time_sec: Time position in seconds
            label: Display label (optional, defaults to text)
        
        Returns:
            EMSComment: The created comment object
        """
        comment = EMSComment(
            text=text,
            #FIXME: deberia ser time_Sec*fs
            tick_position=int(time_sec * 1000),  # Approximate tick
            comment_id=self._next_comment_id,
            #FIXME: Lo mismo
            tick_dt=0.001,  # 1ms approximation
            time_sec=time_sec,
            user_defined=True,
            label=label
        )
        
        self._next_comment_id += 1
        self.logger.debug(f"Created user comment at {time_sec:.2f}s: '{text[:30]}...'")
        return comment
    
    def add_comment_to_list(self, comments_list: list, new_comment: EMSComment) -> list:
        """
        Add a comment to a list and return sorted list (utility function).
        
        Args:
            comments_list: Current list of comments
            new_comment: Comment to add
        
        Returns:
            list: New sorted list with added comment
        """
        new_list = comments_list.copy()
        new_list.append(new_comment)
        
        try:
            new_list.sort(key=lambda c: c.time)
        except (AttributeError, TypeError):
            self.logger.warning("Could not sort comments after adding")
        
        self.logger.info(f"Added comment at {new_comment.time:.2f}s to list")
        return new_list
    
    def remove_comment_from_list(self, comments_list: list, comment_to_remove: EMSComment) -> list:
        """
        Remove a comment from a list (utility function).
        
        Args:
            comments_list: Current list of comments
            comment_to_remove: Comment to remove
        
        Returns:
            list: New list without the removed comment
        """
        new_list = comments_list.copy()
        
        try:
            new_list.remove(comment_to_remove)
            self.logger.info(f"Removed comment at {comment_to_remove.time:.2f}s from list")
        except ValueError:
            self.logger.warning("Comment not found in list for removal")
        
        return new_list
    
    def update_comment_in_list(self, comments_list: list, comment_to_update: EMSComment, 
                              text: str = None, time: float = None, label: str = None) -> list:
        """
        Update a comment in a list (utility function).
        
        Args:
            comments_list: Current list of comments
            comment_to_update: Comment to update
            text: New text (optional)
            time: New time (optional)
            label: New label (optional)
        
        Returns:
            list: New list with updated comment, re-sorted if time changed
        """
        new_list = comments_list.copy()
        
        # Find the comment in the list
        for i, comment in enumerate(new_list):
            if comment == comment_to_update:
                # Update the comment
                comment.update(text=text, time=time, label=label)
                
                # Re-sort if time changed
                if time is not None:
                    try:
                        new_list.sort(key=lambda c: c.time)
                    except (AttributeError, TypeError):
                        self.logger.warning("Could not sort comments after time update")
                
                self.logger.info(f"Updated comment at {comment.time:.2f}s in list")
                break
        else:
            self.logger.warning("Comment not found in list for update")
        
        return new_list
    
    def get_comments_in_range(self, comments_list: list, start_time: float, end_time: float) -> list:
        """
        Filter comments within a specific time range (utility function).
        
        Args:
            comments_list: List of comments to filter
            start_time: Start time in seconds
            end_time: End time in seconds
        
        Returns:
            list: Filtered comments within the time range
        """
        filtered = [c for c in comments_list if start_time <= c.time <= end_time]
        return filtered
    
    def sort_comments(self, comments_list: list) -> list:
        """
        Sort comments by time (utility function).
        
        Args:
            comments_list: List of comments to sort
        
        Returns:
            list: Sorted list of comments
        """
        sorted_list = comments_list.copy()
        
        try:
            sorted_list.sort(key=lambda c: c.time)
        except (AttributeError, TypeError):
            self.logger.warning("Could not sort comments")
        
        return sorted_list
    
    def get_comment_statistics(self, comments_list: list) -> dict:
        """
        Get statistics about a list of comments (utility function).
        
        Args:
            comments_list: List of comments to analyze
        
        Returns:
            dict: Statistics about the comments
        """
        system_count = sum(1 for c in comments_list if not c.user_defined)
        user_count = sum(1 for c in comments_list if c.user_defined)
        
        return {
            'system_count': system_count,
            'user_count': user_count,
            'total_count': len(comments_list)
        }
    
    def export_comments_for_all_channels(self, comments_list: list, channels: list) -> dict:
        """
        Export comments formatted for all channels (utility function for EDF export, etc.).
        Since comments are global, they are replicated across all channels.
        
        Args:
            comments_list: List of comments to export
            channels: List of channel names
        
        Returns:
            dict: {channel_name: [comments_list]} for each channel
        """
        export_data = {}
        for channel in channels:
            export_data[channel] = comments_list.copy()
        
        self.logger.debug(f"Exported {len(comments_list)} comments for {len(channels)} channels")
        return export_data
    
    # === CRUD OPERATIONS WITH PERSISTENCE (NO CACHE ACCESS) ===
    
    def add_user_comment(self, file_path: str, text: str, time_sec: float, label: str = None) -> EMSComment:
        """
        Add a user comment and update DataManager cache directly.
        
        Args:
            file_path: Path to the file
            text: Comment text
            time_sec: Time position in seconds
            label: Display label (optional)
        
        Returns:
            EMSComment: The created comment object
        """
        if not self._data_manager:
            raise RuntimeError("DataManager reference not set. Call set_data_manager() first.")
        
        # Create the comment
        new_comment = self.create_user_comment(text, time_sec, label)
        
        # Get current comments from DataManager cache
        current_comments = self._data_manager.get_comments(file_path)
        
        # Add to list and sort
        updated_comments = self.add_comment_to_list(current_comments, new_comment)
        
        # Update DataManager cache directly
        self._data_manager._files[file_path]["comments"] = updated_comments
        
        # Persist to file (TODO: implement actual persistence)
        self._save_comments_to_persistence(file_path, updated_comments)
        
        # Emit signal for global plot synchronization
        self.comment_added.emit(file_path, new_comment)
        
        self.logger.info(f"Added user comment at {time_sec:.2f}s to file {file_path}")
        return new_comment
    
    def remove_user_comment(self, file_path: str, comment: EMSComment) -> bool:
        """
        Remove a user comment and update DataManager cache directly.
        
        Args:
            file_path: Path to the file
            comment: Comment to remove
        
        Returns:
            bool: True if successfully removed
        """
        if not self._data_manager:
            raise RuntimeError("DataManager reference not set. Call set_data_manager() first.")
        
        # Get current comments from DataManager cache
        current_comments = self._data_manager.get_comments(file_path)
        
        # Remove from list
        updated_comments = self.remove_comment_from_list(current_comments, comment)
        
        # Check if removal was successful
        if len(updated_comments) < len(current_comments):
            # Update DataManager cache directly
            self._data_manager._files[file_path]["comments"] = updated_comments
            
            # Persist to file (TODO: implement actual persistence)
            self._save_comments_to_persistence(file_path, updated_comments)
            
            # Emit signal for global plot synchronization
            self.comment_removed.emit(file_path, str(comment.comment_id))
            
            self.logger.info(f"Removed user comment at {comment.time:.2f}s from file {file_path}")
            return True
        
        self.logger.warning(f"Failed to remove comment - not found in file {file_path}")
        return False
    
    def update_user_comment(self, file_path: str, comment: EMSComment, 
                           text: str = None, time: float = None, label: str = None) -> bool:
        """
        Update a user comment and update DataManager cache directly.
        
        Args:
            file_path: Path to the file
            comment: Comment to update
            text: New text (optional)
            time: New time (optional)
            label: New label (optional)
        
        Returns:
            bool: True if successfully updated
        """
        if not self._data_manager:
            raise RuntimeError("DataManager reference not set. Call set_data_manager() first.")
        
        # Get current comments from DataManager cache
        current_comments = self._data_manager.get_comments(file_path)
        
        # Update in list
        updated_comments = self.update_comment_in_list(current_comments, comment, text, time, label)
        
        # Update DataManager cache directly
        self._data_manager._files[file_path]["comments"] = updated_comments
        
        # Persist to file (TODO: implement actual persistence)
        self._save_comments_to_persistence(file_path, updated_comments)
        
        # Emit signal for global plot synchronization
        self.comment_updated.emit(file_path, comment)
        
        self.logger.info(f"Updated user comment at {comment.time:.2f}s in file {file_path}")
        return True
    
    
    def _save_comments_to_persistence(self, file_path: str, comments: list):
        """
        Save comments to persistence layer (files, database, etc.).
        This method only writes to persistence, never to DataManager cache.
        
        Args:
            file_path: Path to the file
            comments: Comments to save to persistence
        """
        # TODO: Implement actual persistence (JSON files, database, etc.)
        user_comments = [c for c in comments if c.user_defined]
        self.logger.debug(f"Saving {len(user_comments)} user comments to persistence for {file_path} (placeholder)")
        pass


# Global instance
_comment_manager_instance = None

def get_comment_manager() -> CommentManager:
    """Get the global CommentManager instance."""
    global _comment_manager_instance
    if _comment_manager_instance is None:
        _comment_manager_instance = CommentManager()
    return _comment_manager_instance
