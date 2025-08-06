# processing/ecg_analyzer.py

import numpy as np
import warnings
from typing import Optional, Dict, Any
from Pyside.processing.peak_detection_strategies import strategy_registry, PeakDetectionStrategy


class ECGAnalyzer:
    """
    Enhanced ECG analyzer supporting multiple peak detection strategies.
    
    Uses the Strategy pattern to provide flexible R-peak detection with support for:
    - Wavelet-based methods (SWT, DWT, CWT)
    - NeuroKit2 professional detectors (pan_tompkins, xqrs, etc.)
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
                - "cwt": Continuous Wavelet Transform (most accurate)
                - "pan_tompkins": NeuroKit2 Pan-Tompkins algorithm
                - "xqrs": NeuroKit2 XQRS algorithm  
                - "hamilton_segmenter": NeuroKit2 Hamilton segmenter
                - "christov_segmenter": NeuroKit2 Christov segmenter
            strategy (Optional[PeakDetectionStrategy]): Custom strategy instance.
                If provided, overrides the method parameter.
            **kwargs: Strategy-specific parameters. Common parameters:
                - wavelet (str): Wavelet type for wavelet-based methods
                - level (int): Decomposition level for SWT/DWT
                - min_rr_sec (float): Minimum R-R interval in seconds
                - scales (array): CWT scales (auto-calculated if None)
        
        Returns:
            np.ndarray: Array of sample indices where R-peaks are detected
            
        Raises:
            ValueError: If the specified method/strategy is not available
            ImportError: If NeuroKit2 is required but not installed
            
        Examples:
            >>> # Default DWT method (backward compatible)
            >>> peaks = ECGAnalyzer.detect_rr_peaks(ecg_data, fs=1000)
            
            >>> # Use SWT with custom parameters
            >>> peaks = ECGAnalyzer.detect_rr_peaks(
            ...     ecg_data, fs=1000, method="swt", 
            ...     wavelet="db3", level=4, min_rr_sec=0.35
            ... )
            
            >>> # Use NeuroKit2 Pan-Tompkins algorithm
            >>> peaks = ECGAnalyzer.detect_rr_peaks(
            ...     ecg_data, fs=1000, method="pan_tompkins"
            ... )
            
            >>> # Use custom strategy
            >>> custom_strategy = MyCustomStrategy()
            >>> peaks = ECGAnalyzer.detect_rr_peaks(
            ...     ecg_data, fs=1000, strategy=custom_strategy
            ... )
        """
        
        # Handle backward compatibility for legacy parameter names
        method = ECGAnalyzer._handle_legacy_params(method, kwargs)
        
        # Use custom strategy if provided
        if strategy is not None:
            return strategy.detect_peaks(ecg_signal, fs, **kwargs)
        
        # Get strategy from registry
        try:
            detection_strategy = strategy_registry.get_strategy(method)
        except ValueError as e:
            available_methods = strategy_registry.list_strategies()
            raise ValueError(
                f"Unknown detection method '{method}'. "
                f"Available methods: {available_methods}"
            ) from e
        
        # Execute strategy
        try:
            return detection_strategy.detect_peaks(ecg_signal, fs, **kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Peak detection failed with method '{method}': {str(e)}"
            ) from e
    
    @staticmethod
    def _handle_legacy_params(method: str, kwargs: Dict[str, Any]) -> str:
        """
        Handle backward compatibility for legacy parameter names and values.
        
        Args:
            method: Original method parameter
            kwargs: Keyword arguments (may be modified)
            
        Returns:
            Updated method name
        """
        # Handle legacy "wavelet" method name
        if method == "wavelet":
            warnings.warn(
                "Method 'wavelet' is deprecated. Use 'dwt' for Discrete Wavelet Transform. "
                "Will default to 'dwt' for backward compatibility.",
                DeprecationWarning,
                stacklevel=3
            )
            method = "dwt"
        
        # Handle legacy parameter names
        legacy_param_map = {
            "min_dist": "min_rr_sec",  # Old parameter name
            "swt_level": "level",     # SWT-specific legacy name
            "dwt_level": "level"      # DWT-specific legacy name
        }
        
        for old_param, new_param in legacy_param_map.items():
            if old_param in kwargs and new_param not in kwargs:
                kwargs[new_param] = kwargs.pop(old_param)
                warnings.warn(
                    f"Parameter '{old_param}' is deprecated. Use '{new_param}' instead.",
                    DeprecationWarning,
                    stacklevel=3
                )
        
        # Handle legacy "pan_tonkins" method name (with typo)
        if method == "pan_tonkins":
            warnings.warn(
                "Method 'pan_tonkins' is deprecated. Use 'pan_tompkins' instead.",
                DeprecationWarning,
                stacklevel=3
            )
            method = "pan_tompkins"
        
        return method
    
    @staticmethod
    def get_available_methods() -> Dict[str, str]:
        """
        Get information about all available detection methods.
        
        Returns:
            Dict[str, str]: Dictionary mapping method names to descriptions
        """
        return strategy_registry.get_strategy_info()
    
    @staticmethod
    def register_custom_strategy(strategy: PeakDetectionStrategy):
        """
        Register a custom peak detection strategy.
        
        Args:
            strategy: Custom strategy instance implementing PeakDetectionStrategy
            
        Example:
            >>> class MyDetector(PeakDetectionStrategy):
            ...     # Implementation here
            ...     pass
            >>> 
            >>> my_strategy = MyDetector()
            >>> ECGAnalyzer.register_custom_strategy(my_strategy)
            >>> peaks = ECGAnalyzer.detect_rr_peaks(ecg_data, fs, method=my_strategy.name)
        """
        strategy_registry.register_strategy(strategy)
    
    @staticmethod
    def get_strategy_defaults(method: str) -> Dict[str, Any]:
        """
        Get default parameters for a specific detection method.
        
        Args:
            method: Detection method name
            
        Returns:
            Dict[str, Any]: Default parameters for the method
            
        Raises:
            ValueError: If method is not found
        """
        strategy = strategy_registry.get_strategy(method)
        return strategy.get_default_params()


# Backward compatibility aliases
# These maintain compatibility with existing code that might import specific functions
def detect_rr_peaks(*args, **kwargs):
    """
    Legacy function wrapper for backward compatibility.
    
    This function maintains compatibility with old code that imports
    detect_rr_peaks directly from ecg_analyzer.
    """
    warnings.warn(
        "Direct function import is deprecated. Use ECGAnalyzer.detect_rr_peaks() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return ECGAnalyzer.detect_rr_peaks(*args, **kwargs)