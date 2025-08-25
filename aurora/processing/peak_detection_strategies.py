"""
Peak detection strategies for signal analysis using the Strategy design pattern.

This module provides a flexible framework for implementing various peak detection
algorithms for any type of physiological signal, including ECG, blood pressure, etc.
"""

import numpy as np
import warnings
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from aurora.core.config_manager import get_config_manager


class PeakDetectionStrategy(ABC):
    """
    Abstract base class for peak detection strategies.
    
    This interface defines the contract that all peak detection algorithms must follow,
    enabling easy switching between different detection methods for any signal type.
    """
    
    @abstractmethod
    def detect_peaks(self, signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect peaks in any physiological signal.
        
        Args:
            signal (np.ndarray): Raw signal, 1D numpy array
            fs (float): Sampling frequency in Hz
            **kwargs: Strategy-specific parameters
            
        Returns:
            np.ndarray: Array of sample indices where peaks are detected
        """
        pass
    
    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """
        Get default parameters for this strategy.
        
        Returns:
            Dict[str, Any]: Dictionary of default parameter values
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for identification."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the strategy."""
        pass
    
    @property
    def signal_types(self) -> List[str]:
        """List of signal types this strategy can handle."""
        return ["generic"]  # Override in subclasses for specific signals


class WaveletSWTStrategy(PeakDetectionStrategy):
    """
    Stationary Wavelet Transform (SWT) based peak detection strategy.
    
    Uses undecimated wavelet transform for translation-invariant feature detection.
    Best for noisy signals where precise peak timing is critical.
    """
    
    def __init__(self):
        self.config_manager = get_config_manager()
    
    @property
    def name(self) -> str:
        return "swt"
    
    @property 
    def description(self) -> str:
        return "Stationary Wavelet Transform - translation-invariant, robust for noisy signals"
    

    def get_default_params(self) -> Dict[str, Any]:
        hr_settings = self.config_manager.get_hr_generation_settings()
        return {
            "wavelet": hr_settings.get("wavelet", "db3"),
            "level": hr_settings.get("level", 4),
            "min_distance_sec": hr_settings.get("min_rr_sec", 0.4),
            "height_threshold_std": 1.0  # Threshold as multiple of signal std
        }
    
    def detect_peaks(self, signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect peaks using Stationary Wavelet Transform.
        
        Args:
            signal: Raw signal
            fs: Sampling frequency 
            wavelet: Wavelet type (default: 'db3')
            level: Decomposition level (default: 4)
            min_distance_sec: Minimum interval between peaks in seconds
            height_threshold_std: Height threshold as multiple of signal std
            
        Returns:
            Array of peak indices
        """
        try:
            import pywt
            from scipy.signal import find_peaks
        except ImportError as e:
            raise ImportError("PyWavelets and SciPy are required for SWT strategy") from e
        
        params = self.get_default_params()
        params.update(kwargs)
        
        wavelet = params["wavelet"]
        level = params["level"]
        min_distance_sec = params["min_distance_sec"]
        height_threshold_std = params["height_threshold_std"]
        
        # Adjust level to maximum allowed by signal length
        max_level = pywt.swt_max_level(len(signal))
        if max_level == 0:
            raise ValueError("Signal too short for SWT decomposition")
        level = min(level, max_level)
        
        # Perform undecimated SWT
        coeffs = pywt.swt(signal, wavelet, level=level)
        
        # Reconstruct signal using ISWT
        reconstructed = pywt.iswt(coeffs, wavelet)
        
        # Calculate detection parameters
        min_distance = int(min_distance_sec * fs)
        height_threshold = np.std(reconstructed) * height_threshold_std
        
        # Detect peaks in reconstructed signal
        peaks, _ = find_peaks(reconstructed, 
                            distance=min_distance,
                            height=height_threshold)
        
        return peaks


class WaveletDWTStrategy(PeakDetectionStrategy):
    """
    Discrete Wavelet Transform (DWT) based peak detection strategy.
    
    Uses standard wavelet decomposition for efficient signal processing.
    Fastest method with good baseline performance.
    """
    
    def __init__(self):
        self.config_manager = get_config_manager()
    
    @property
    def name(self) -> str:
        return "dwt"
    
    @property
    def description(self) -> str:
        return "Discrete Wavelet Transform - efficient, good baseline performance"
    
    @property
    def signal_types(self) -> List[str]:
        return ["ecg", "blood_pressure", "generic"]
    
    def get_default_params(self) -> Dict[str, Any]:
        hr_settings = self.config_manager.get_hr_generation_settings()
        return {
            "wavelet": hr_settings.get("wavelet", "haar"),
            "level": hr_settings.get("level", 4),
            "min_distance_sec": hr_settings.get("min_rr_sec", 0.4),
            "height_threshold_std": 1.0
        }
    
    def detect_peaks(self, signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect peaks using Discrete Wavelet Transform.
        
        Args:
            signal: Raw signal
            fs: Sampling frequency
            wavelet: Wavelet type (default: 'haar')
            level: Decomposition level (default: 4)
            min_distance_sec: Minimum interval between peaks in seconds
            height_threshold_std: Height threshold as multiple of signal std
            
        Returns:
            Array of peak indices
        """
        try:
            import pywt
            from scipy.signal import find_peaks
        except ImportError as e:
            raise ImportError("PyWavelets and SciPy are required for DWT strategy") from e
        
        params = self.get_default_params()
        params.update(kwargs)
        
        wavelet = params["wavelet"]
        level = params["level"] 
        min_distance_sec = params["min_distance_sec"]
        height_threshold_std = params["height_threshold_std"]
        
        # Perform DWT decomposition
        coeffs = pywt.wavedec(signal, wavelet, level=level)
        
        # Reconstruct signal 
        reconstructed = pywt.waverec(coeffs, wavelet)
        
        # Calculate detection parameters
        min_distance = int(min_distance_sec * fs)
        height_threshold = np.std(reconstructed) * height_threshold_std
        
        # Detect peaks in reconstructed signal
        peaks, _ = find_peaks(reconstructed, 
                            distance=min_distance,
                            height=height_threshold)
        
        return peaks


class ScipyBasicStrategy(PeakDetectionStrategy):
    """
    Basic peak detection using SciPy's find_peaks with preprocessing.
    
    Simple and reliable method using bandpass filtering and adaptive thresholding.
    Good fallback when wavelets are not available.
    """
    
    @property
    def name(self) -> str:
        return "scipy_basic"
    
    @property
    def description(self) -> str:
        return "SciPy find_peaks with bandpass filter - simple and reliable"
    
    @property
    def signal_types(self) -> List[str]:
        return ["ecg", "blood_pressure", "generic"]
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "min_distance_sec": 0.4,  # For ECG, adjust for other signals
            "height_threshold_std": 1.0,
            "filter_signal": True,
            "low_cutoff": 0.5,  # Hz
            "high_cutoff": 40.0,  # Hz
        }
    
    def detect_peaks(self, signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect peaks using SciPy find_peaks with optional filtering.
        
        Args:
            signal: Raw signal
            fs: Sampling frequency
            min_distance_sec: Minimum interval between peaks in seconds
            height_threshold_std: Height threshold as multiple of signal std
            filter_signal: Whether to apply bandpass filter
            low_cutoff: Low cutoff frequency for bandpass filter (Hz)
            high_cutoff: High cutoff frequency for bandpass filter (Hz)
            
        Returns:
            Array of peak indices
        """
        try:
            from scipy.signal import find_peaks, butter, filtfilt
        except ImportError as e:
            raise ImportError("SciPy is required for scipy_basic strategy") from e
        
        params = self.get_default_params()
        params.update(kwargs)
        
        processed_signal = signal.copy()
        
        # Optional bandpass filtering
        if params["filter_signal"]:
            try:
                nyquist = fs / 2
                low_cutoff = max(params["low_cutoff"] / nyquist, 0.001)
                high_cutoff = min(params["high_cutoff"] / nyquist, 0.999)
                
                b, a = butter(4, [low_cutoff, high_cutoff], btype='band')
                processed_signal = filtfilt(b, a, processed_signal)
            except Exception as e:
                warnings.warn(f"Filtering failed: {e}, using unfiltered signal")
        
        # Calculate detection parameters
        min_distance = int(params["min_distance_sec"] * fs)
        height_threshold = np.std(processed_signal) * params["height_threshold_std"]
        
        # Find peaks
        peaks, _ = find_peaks(processed_signal, 
                            distance=min_distance,
                            height=height_threshold)
        
        return peaks


class SimpleThresholdStrategy(PeakDetectionStrategy):
    """
    Simple threshold-based peak detection.
    
    No external dependencies, very basic but works as last resort.
    """
    
    @property
    def name(self) -> str:
        return "simple_threshold"
    
    @property
    def description(self) -> str:
        return "Simple threshold detection - no dependencies, basic functionality"
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "min_distance_sec": 0.4,
            "threshold_std_multiplier": 2.0
        }
    
    def detect_peaks(self, signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Very basic peak detection without external dependencies.
        """
        params = self.get_default_params()
        params.update(kwargs)
        
        threshold = np.mean(signal) + params["threshold_std_multiplier"] * np.std(signal)
        min_distance = int(params["min_distance_sec"] * fs)
        
        peaks = []
        last_peak = -min_distance
        
        for i in range(1, len(signal) - 1):
            if (signal[i] > signal[i-1] and 
                signal[i] > signal[i+1] and
                signal[i] > threshold and
                i - last_peak > min_distance):
                peaks.append(i)
                last_peak = i
        
        return np.array(peaks, dtype=int)


class PeakDetectionStrategyRegistry:
    """
    Registry for managing available peak detection strategies.
    
    Provides centralized access to all available strategies and handles
    strategy selection and instantiation.
    """
    
    def __init__(self):
        self._strategies = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register all built-in strategies."""
        # Always available strategies
        self.register_strategy(SimpleThresholdStrategy())
        
        # SciPy-based strategies
        try:
            self.register_strategy(ScipyBasicStrategy())
        except ImportError:
            warnings.warn("SciPy not available, skipping scipy_basic strategy")
        
        # Wavelet-based strategies
        try:
            self.register_strategy(WaveletDWTStrategy())
            self.register_strategy(WaveletSWTStrategy())
        except ImportError:
            warnings.warn("PyWavelets not available, skipping wavelet strategies")
    
    def register_strategy(self, strategy: PeakDetectionStrategy):
        """
        Register a new peak detection strategy.
        
        Args:
            strategy: Strategy instance to register
        """
        self._strategies[strategy.name] = strategy
    
    def get_strategy(self, name: str) -> PeakDetectionStrategy:
        """
        Get strategy by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy instance
            
        Raises:
            ValueError: If strategy is not found
        """
        if name not in self._strategies:
            available = list(self._strategies.keys())
            raise ValueError(f"Strategy '{name}' not found. Available strategies: {available}")
        
        return self._strategies[name]
    
    def list_strategies(self) -> List[str]:
        """Get list of available strategy names."""
        return list(self._strategies.keys())
    
    def get_strategy_info(self) -> Dict[str, str]:
        """Get information about all available strategies."""
        return {name: strategy.description for name, strategy in self._strategies.items()}
    
    def get_strategies_for_signal(self, signal_type: str) -> List[str]:
        """
        Get list of strategies suitable for a specific signal type.
        
        Args:
            signal_type: Type of signal (e.g., "ecg", "blood_pressure", "generic")
            
        Returns:
            List of strategy names suitable for the signal type
        """
        suitable_strategies = []
        for name, strategy in self._strategies.items():
            if signal_type in strategy.signal_types or "generic" in strategy.signal_types:
                suitable_strategies.append(name)
        return suitable_strategies


# Global registry instance
strategy_registry = PeakDetectionStrategyRegistry()