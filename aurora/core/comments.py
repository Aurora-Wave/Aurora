

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
import numpy as np
import bisect
from typing import Dict, List, Tuple, Optional

class CommentTimeIndex:
    """
    Time-based indexing system for comments in a single file.
    Maintains sorted arrays for O(log n) binary search operations by time.
    """
    
    def __init__(self):
        # Core storage
        self.comments: List[EMSComment] = []
        
        # OPTIMIZATION: Parallel sorted arrays for fast binary search
        self.times_sorted: np.ndarray = np.array([], dtype=np.float64)
        self.ids_sorted: List[str] = []
        
        # Fast lookup map
        self.id_to_comment: Dict[str, EMSComment] = {}
        
        # State tracking
        self._dirty = False
        
    def _rebuild_indices(self):
        """Rebuild sorted arrays and lookup map. Call after bulk changes."""
        if not self.comments:
            self.times_sorted = np.array([], dtype=np.float64)
            self.ids_sorted = []
            self.id_to_comment = {}
            self._dirty = False
            return
            
        # Extract times and create stable sort indices
        times = np.array([c.time for c in self.comments], dtype=np.float64)
        sort_indices = np.argsort(times, kind='stable')  # Stable sort preserves order for equal times
        
        # Build sorted arrays
        self.times_sorted = times[sort_indices]
        self.ids_sorted = [str(self.comments[i].comment_id) for i in sort_indices]
        
        # Build lookup map
        self.id_to_comment = {str(c.comment_id): c for c in self.comments}
        
        self._dirty = False
        
    def add_comment(self, comment: EMSComment) -> bool:
        """Add comment and maintain sorted order. Returns True if successful."""
        try:
            comment_id = str(comment.comment_id)
            
            # Avoid duplicates
            if comment_id in self.id_to_comment:
                return False
                
            # Add to main list
            self.comments.append(comment)
            self.id_to_comment[comment_id] = comment
            
            # Insert into sorted arrays at correct position
            if len(self.times_sorted) == 0:
                self.times_sorted = np.array([comment.time], dtype=np.float64)
                self.ids_sorted = [comment_id]
            else:
                # Find insertion position using binary search
                insert_pos = bisect.bisect_left(self.times_sorted, comment.time)
                
                # Insert into numpy array (expensive, but maintains sort)
                self.times_sorted = np.insert(self.times_sorted, insert_pos, comment.time)
                self.ids_sorted.insert(insert_pos, comment_id)
                
            return True
            
        except Exception as e:
            # Fallback: mark dirty for rebuild
            self._dirty = True
            return False
    
    def remove_comment(self, comment_id: str) -> bool:
        """Remove comment and maintain sorted order. Returns True if found."""
        comment_id_str = str(comment_id)
        
        if comment_id_str not in self.id_to_comment:
            return False
            
        try:
            # Remove from main list and map
            comment = self.id_to_comment.pop(comment_id_str)
            self.comments = [c for c in self.comments if str(c.comment_id) != comment_id_str]
            
            # Find and remove from sorted arrays
            if len(self.ids_sorted) > 0:
                try:
                    sorted_index = self.ids_sorted.index(comment_id_str)
                    self.times_sorted = np.delete(self.times_sorted, sorted_index)
                    del self.ids_sorted[sorted_index]
                except ValueError:
                    # Not found in sorted arrays, mark for rebuild
                    self._dirty = True
                    
            return True
            
        except Exception:
            # Fallback: mark dirty for rebuild
            self._dirty = True
            return False
    
    def get_comments_in_range(self, start_time: float, end_time: float) -> List[EMSComment]:
        """Binary search for comments in time range. O(log n + k) where k = results."""
        if self._dirty:
            self._rebuild_indices()
            
        if len(self.times_sorted) == 0:
            return []
            
        # Binary search for range bounds
        i0 = bisect.bisect_left(self.times_sorted, start_time)
        i1 = bisect.bisect_right(self.times_sorted, end_time)
        
        # Get comment IDs in range and lookup comments
        visible_ids = self.ids_sorted[i0:i1]
        return [self.id_to_comment[comment_id] for comment_id in visible_ids if comment_id in self.id_to_comment]


class CommentManager(QObject):
    """
    Optimized CRUD manager for comment operations with fast binary search.
    
    Architecture:
    - Maintains sorted arrays for O(log n) search: times_sorted[], ids_sorted[] 
    - Fast lookup map: id_to_comment{}
    - Handles persistence and cache synchronization with DataManager
    - Provides query interface for Tabs (no rendering - that's UI responsibility)
    """
    
    # Event-driven signals - CommentManager requests, DataManager handles
    comment_create_requested = Signal(str, dict)  # (file_path, comment_data)
    comment_update_requested = Signal(str, str, dict)  # (file_path, comment_id, update_data)
    comment_delete_requested = Signal(str, str)  # (file_path, comment_id)
    
    def __init__(self):
        super().__init__()
        from aurora.core import get_user_logger
        self.logger = get_user_logger("CommentManager")
        self._next_comment_id = 10000  # Start user IDs high to avoid conflicts
    
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
    
    # ========= OPTIMIZED QUERY INTERFACE FOR TABS =========
    
    def load_file_comments(self, file_path: str, comments: List[EMSComment]):
        """Load comments for a file and build optimized index. Called by DataManager."""
        if not file_path:
            return
            
        # Create new index for this file
        index = CommentTimeIndex()
        
        # Add all comments to index (builds sorted arrays)
        for comment in comments:
            index.add_comment(comment)
            
        # Store index
        self._file_indices[file_path] = index
        self._current_file = file_path
        
        self.logger.info(f"Loaded {len(comments)} comments for {file_path} with optimized indexing")
        self.comments_loaded.emit(file_path, comments)
        self.file_comments_changed.emit(file_path)
    
    def get_comments_in_time_window(self, file_path: str, start_time: float, end_time: float) -> List[EMSComment]:
        """
        OPTIMIZED: Get comments in time window using binary search. O(log n + k).
        This is the main method Tabs should use for querying visible comments.
        
        Args:
            file_path: File to query
            start_time: Window start in seconds  
            end_time: Window end in seconds
            
        Returns:
            List of EMSComment objects in time range, sorted by time
        """
        if file_path not in self._file_indices:
            return []
            
        index = self._file_indices[file_path]
        comments = index.get_comments_in_range(start_time, end_time)
        
        self.logger.debug(f"Query [{start_time:.1f}-{end_time:.1f}s]: {len(comments)} comments")
        return comments
        
    def get_all_comments_for_file(self, file_path: str) -> List[EMSComment]:
        """Get all comments for a file (for export, statistics, etc.)."""
        if file_path not in self._file_indices:
            return []
            
        return self._file_indices[file_path].comments.copy()
    
    def set_current_file(self, file_path: str):
        """Set the currently active file for operations."""
        self._current_file = file_path
        
    def get_current_file(self) -> Optional[str]:
        """Get the currently active file."""
        return self._current_file
    
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
            time_sec=time_sec,
            comment_id=self._next_comment_id,
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
            # Find and remove by ID (not object identity)
            for i, comment in enumerate(new_list):
                if comment.comment_id == comment_to_remove.comment_id:
                    new_list.pop(i)
                    self.logger.info(f"Removed comment at {comment_to_remove.time:.2f}s from list")
                    break
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
        
        # Find the comment in the list by ID (not object identity)
        for i, comment in enumerate(new_list):
            if comment.comment_id == comment_to_update.comment_id:
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
        
        # Update optimized index (CRITICAL for queries to work)
        if file_path in self._file_indices:
            index = CommentTimeIndex()
            index.comments = updated_comments
            index._rebuild_indices()
            self._file_indices[file_path] = index
        
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
            
            # Update optimized index (CRITICAL for queries to work)
            if file_path in self._file_indices:
                index = CommentTimeIndex()
                index.comments = updated_comments
                index._rebuild_indices()
                self._file_indices[file_path] = index
            
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
        
        # Update optimized index (CRITICAL for queries to work)
        if file_path in self._file_indices:
            index = CommentTimeIndex()
            index.comments = updated_comments
            index._rebuild_indices()
            self._file_indices[file_path] = index
        
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