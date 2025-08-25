# processing/ecg_analyzer.py

import numpy as np
import warnings
from typing import Optional, Dict, Any
from aurora.processing.peak_detection_strategies import strategy_registry, PeakDetectionStrategy


class ECGAnalyzer:
    """
    Enhanced ECG analyzer supporting multiple peak detection strategies.
    
    Uses the Strategy pattern to provide flexible R-peak detection with support for:
    - Wavelet-based methods (SWT, DWT)
    - SciPy-based detectors (basic filtering)  
    - Simple threshold detection
    - Custom user-defined strategies
    
    The analyzer maintains backward compatibility while enabling easy integration
    of new detection algorithms.
    """
    
    @staticmethod
    def detect_rr_peaks(ecg_signal: np.ndarray,
                        fs: float,
                        method: str = "dwt",
                        strategy: Optional[PeakDetectionStrategy] = None,
                        **kwargs) -> np.ndarray:
        """
        Detect R-peaks in ECG signal using configurable detection strategies.
        
        This method provides a unified interface for various R-peak detection algorithms,
        supporting both built-in strategies and custom implementations. It maintains
        full backward compatibility with existing code.
        
        Args:
            ecg_signal (np.ndarray): Raw ECG signal, 1D numpy array
            fs (float): Sampling frequency in Hz
            method (str): Detection strategy name. Available options:
                - "dwt": Discrete Wavelet Transform (default, fastest)
                - "swt": Stationary Wavelet Transform (robust)
                - "scipy_basic": SciPy find_peaks with bandpass filter
                - "simple_threshold": Basic threshold detection (no dependencies)
            strategy (Optional[PeakDetectionStrategy]): Custom strategy instance.
                If provided, overrides the method parameter.
            **kwargs: Strategy-specific parameters. Common parameters:
                - wavelet (str): Wavelet type for wavelet-based methods
                - level (int): Decomposition level for SWT/DWT
                - min_distance_sec (float): Minimum time between peaks
                - height_threshold_std (float): Height threshold as std multiplier
                
        Returns:
            np.ndarray: Array of sample indices where R-peaks are detected,
                       sorted in ascending order
                       
        Raises:
            ValueError: If method is not available or strategy fails
            ImportError: If required dependencies are not installed
            
        Example:
            # Using default DWT method
            peaks = ECGAnalyzer.detect_rr_peaks(ecg_data, fs=1000)
            
            # Using SWT with custom parameters
            peaks = ECGAnalyzer.detect_rr_peaks(
                ecg_data, fs=1000, method="swt", 
                wavelet="db4", level=5, min_distance_sec=0.3
            )
            
            # Using custom strategy
            custom_strategy = MyCustomStrategy()
            peaks = ECGAnalyzer.detect_rr_peaks(
                ecg_data, fs=1000, strategy=custom_strategy
            )
        """
        # Use custom strategy if provided
        if strategy is not None:
            try:
                return strategy.detect_peaks(ecg_signal, fs, **kwargs)
            except Exception as e:
                warnings.warn(f"Custom strategy failed: {e}, falling back to default method")
                # Fall through to method-based detection
        
        # Use method-based strategy selection
        try:
            selected_strategy = strategy_registry.get_strategy(method)
            peaks = selected_strategy.detect_peaks(ecg_signal, fs, **kwargs)
            
            # Ensure peaks are sorted (required for downstream processing)
            peaks = np.sort(peaks)
            
            return peaks
            
        except ValueError as e:
            # Method not found, try fallback strategies
            available_strategies = strategy_registry.list_strategies()
            
            # Try fallback hierarchy: scipy_basic -> simple_threshold
            fallback_methods = ["scipy_basic", "simple_threshold"]
            
            for fallback_method in fallback_methods:
                if fallback_method in available_strategies and fallback_method != method:
                    try:
                        warnings.warn(
                            f"Method '{method}' not available: {e}. "
                            f"Falling back to '{fallback_method}'"
                        )
                        fallback_strategy = strategy_registry.get_strategy(fallback_method)
                        peaks = fallback_strategy.detect_peaks(ecg_signal, fs, **kwargs)
                        return np.sort(peaks)
                    except Exception as fallback_error:
                        warnings.warn(f"Fallback method '{fallback_method}' also failed: {fallback_error}")
                        continue
            
            # If all fallbacks fail, raise the original error
            raise ValueError(f"All peak detection methods failed. Original error: {e}")
        
        except Exception as e:
            # Strategy execution failed
            warnings.warn(f"Peak detection failed with method '{method}': {e}")
            
            # Try simple threshold as last resort
            if method != "simple_threshold":
                try:
                    fallback_strategy = strategy_registry.get_strategy("simple_threshold")
                    peaks = fallback_strategy.detect_peaks(ecg_signal, fs, **kwargs)
                    warnings.warn("Using simple_threshold as fallback")
                    return np.sort(peaks)
                except Exception:
                    pass
            
            # Return empty array if all methods fail
            warnings.warn("All peak detection methods failed, returning empty array")
            return np.array([], dtype=int)
    
    @staticmethod
    def get_available_methods() -> Dict[str, str]:
        """
        Get information about all available detection methods.
        
        Returns:
            Dict[str, str]: Dictionary mapping method names to descriptions
        """
        return strategy_registry.get_strategy_info()
    
    @staticmethod
    def get_method_defaults(method: str) -> Dict[str, Any]:
        """
        Get default parameters for a specific detection method.
        
        Args:
            method (str): Method name
            
        Returns:
            Dict[str, Any]: Default parameters for the method
            
        Raises:
            ValueError: If method is not available
        """
        strategy = strategy_registry.get_strategy(method)
        return strategy.get_default_params()