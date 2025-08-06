"""
ECG Debug Tracker for Analysis Tab
Monitors ECG signal consistency when peak detection parameters change.
"""

import numpy as np
import hashlib
from typing import Optional, Dict, Any, Tuple
from Pyside.core import get_user_logger


class ECGDebugTracker:
    """
    Debug tracker to monitor ECG signal changes during parameter modifications.
    
    This helps identify if ECG data is being unintentionally modified when
    HR generation parameters change in the Analysis tab.
    """
    
    def __init__(self, logger_name: str = "ECGDebugTracker"):
        self.logger = get_user_logger(logger_name)
        self.previous_ecg_data: Optional[np.ndarray] = None
        self.previous_ecg_hash: Optional[str] = None
        self.previous_parameters: Optional[Dict[str, Any]] = None
        self.previous_chunk_info: Optional[Tuple[float, float]] = None  # (start, duration)
        self.comparison_count = 0
        
        self.logger.info("ECG Debug Tracker initialized")
    
    def _calculate_hash(self, data: np.ndarray) -> str:
        """Calculate a hash of the ECG data for quick comparison."""
        if data is None or len(data) == 0:
            return "empty"
        
        # Use first/last/middle samples and statistics for hash
        samples_to_hash = np.concatenate([
            data[:10] if len(data) >= 10 else data,
            data[-10:] if len(data) >= 10 else [],
            data[len(data)//2:len(data)//2+10] if len(data) >= 20 else [],
            [np.mean(data), np.std(data), np.min(data), np.max(data)]
        ])
        
        return hashlib.md5(samples_to_hash.tobytes()).hexdigest()[:16]
    
    def _detailed_comparison(self, data1: np.ndarray, data2: np.ndarray) -> Dict[str, Any]:
        """Perform detailed comparison between two ECG signals."""
        if data1 is None or data2 is None:
            return {"error": "One of the signals is None"}
        
        if len(data1) != len(data2):
            return {
                "length_mismatch": True,
                "len1": len(data1),
                "len2": len(data2),
                "identical": False
            }
        
        # Check if arrays are identical
        identical = np.array_equal(data1, data2)
        
        if identical:
            return {"identical": True}
        
        # If not identical, provide detailed analysis
        diff = data2 - data1
        abs_diff = np.abs(diff)
        
        return {
            "identical": False,
            "max_absolute_difference": float(np.max(abs_diff)),
            "mean_absolute_difference": float(np.mean(abs_diff)),
            "std_absolute_difference": float(np.std(abs_diff)),
            "num_different_samples": int(np.sum(abs_diff > 1e-10)),
            "percent_different": float(100 * np.sum(abs_diff > 1e-10) / len(data1)),
            "first_difference_index": int(np.argmax(abs_diff > 1e-10)) if np.any(abs_diff > 1e-10) else None,
            "signal1_stats": {
                "mean": float(np.mean(data1)),
                "std": float(np.std(data1)),
                "min": float(np.min(data1)),
                "max": float(np.max(data1))
            },
            "signal2_stats": {
                "mean": float(np.mean(data2)),
                "std": float(np.std(data2)),
                "min": float(np.min(data2)),
                "max": float(np.max(data2))
            }
        }
    
    def capture_ecg_state(self, ecg_data: np.ndarray, parameters: Dict[str, Any], 
                         start_time: float, chunk_duration: float) -> None:
        """
        Capture the current ECG state before parameter changes.
        
        Args:
            ecg_data: Current ECG chunk data
            parameters: Current peak detection parameters
            start_time: Chunk start time in seconds
            chunk_duration: Chunk duration in seconds
        """
        if ecg_data is None:
            self.logger.warning("ECG data is None - cannot capture state")
            return
        
        # Make a copy to avoid reference issues
        self.previous_ecg_data = ecg_data.copy()
        self.previous_ecg_hash = self._calculate_hash(ecg_data)
        self.previous_parameters = parameters.copy()
        self.previous_chunk_info = (start_time, chunk_duration)
        
        self.logger.debug(f"ECG state captured: {len(ecg_data)} samples, "
                         f"hash={self.previous_ecg_hash}, params={parameters}, "
                         f"chunk={start_time}s-{start_time + chunk_duration}s")
    
    def compare_ecg_state(self, current_ecg_data: np.ndarray, current_parameters: Dict[str, Any],
                         current_start_time: float, current_chunk_duration: float) -> bool:
        """
        Compare current ECG state with previously captured state.
        
        Args:
            current_ecg_data: Current ECG chunk data
            current_parameters: Current peak detection parameters  
            current_start_time: Current chunk start time
            current_chunk_duration: Current chunk duration
            
        Returns:
            bool: True if ECG data is identical, False if different
        """
        self.comparison_count += 1
        
        if self.previous_ecg_data is None:
            self.logger.info("No previous ECG state to compare against")
            return True
        
        if current_ecg_data is None:
            self.logger.error("Current ECG data is None - cannot compare")
            return False
        
        # Check if we're comparing the same chunk
        current_chunk_info = (current_start_time, current_chunk_duration)
        same_chunk = self.previous_chunk_info == current_chunk_info
        
        # Calculate current hash for quick comparison
        current_hash = self._calculate_hash(current_ecg_data)
        hash_identical = current_hash == self.previous_ecg_hash
        
        # Perform detailed comparison
        comparison_result = self._detailed_comparison(self.previous_ecg_data, current_ecg_data)
        
        # Log results
        param_changes = []
        if self.previous_parameters:
            for key, prev_val in self.previous_parameters.items():
                curr_val = current_parameters.get(key, "MISSING")
                if prev_val != curr_val:
                    param_changes.append(f"{key}: {prev_val} → {curr_val}")
        
        log_level = "info" if comparison_result.get("identical", False) else "warning"
        
        message = (
            f"ECG Comparison #{self.comparison_count}:\n"
            f"  Same chunk: {same_chunk} (prev: {self.previous_chunk_info}, curr: {current_chunk_info})\n"
            f"  Hash identical: {hash_identical} (prev: {self.previous_ecg_hash}, curr: {current_hash})\n"
            f"  Data identical: {comparison_result.get('identical', False)}\n"
            f"  Parameter changes: {param_changes if param_changes else 'None'}\n"
        )
        
        if not comparison_result.get("identical", False):
            message += (
                f"  SIGNAL CHANGES DETECTED:\n"
                f"    Max absolute difference: {comparison_result.get('max_absolute_difference', 'N/A')}\n"
                f"    Mean absolute difference: {comparison_result.get('mean_absolute_difference', 'N/A')}\n"
                f"    Samples different: {comparison_result.get('num_different_samples', 'N/A')} "
                f"({comparison_result.get('percent_different', 0):.2f}%)\n"
            )
            
            if comparison_result.get("length_mismatch"):
                message += f"    Length mismatch: {comparison_result.get('len1')} vs {comparison_result.get('len2')}\n"
        
        # Log with appropriate level
        getattr(self.logger, log_level)(message)
        
        # Update state for next comparison
        self.previous_ecg_data = current_ecg_data.copy()
        self.previous_ecg_hash = current_hash
        self.previous_parameters = current_parameters.copy()
        self.previous_chunk_info = current_chunk_info
        
        return comparison_result.get("identical", False)
    
    def reset(self):
        """Reset the debug tracker state."""
        self.previous_ecg_data = None
        self.previous_ecg_hash = None
        self.previous_parameters = None
        self.previous_chunk_info = None
        self.comparison_count = 0
        self.logger.info("ECG Debug Tracker reset")