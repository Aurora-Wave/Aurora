"""
Peak detection strategies for ECG analysis using the Strategy design pattern.

This module provides a flexible framework for implementing various R-peak detection
algorithms, including wavelet-based methods and NeuroKit2 detectors.
"""

import numpy as np
import pywt
import warnings
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
from scipy.signal import find_peaks


class PeakDetectionStrategy(ABC):
    """
    Abstract base class for R-peak detection strategies.
    
    This interface defines the contract that all peak detection algorithms must follow,
    enabling easy switching between different detection methods.
    """
    
    @abstractmethod
    def detect_peaks(self, ecg_signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect R-peaks in ECG signal.
        
        Args:
            ecg_signal (np.ndarray): Raw ECG signal, 1D numpy array
            fs (float): Sampling frequency in Hz
            **kwargs: Strategy-specific parameters
            
        Returns:
            np.ndarray: Array of sample indices where R-peaks are detected
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


class WaveletSWTStrategy(PeakDetectionStrategy):
    """
    Stationary Wavelet Transform (SWT) based R-peak detection strategy.
    
    Uses undecimated wavelet transform for translation-invariant feature detection.
    Best for noisy signals where precise peak timing is critical.
    """
    
    @property
    def name(self) -> str:
        return "swt"
    
    @property 
    def description(self) -> str:
        return "Stationary Wavelet Transform - translation-invariant, robust for noisy signals"
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "wavelet": "db3",
            "level": 4,
            "min_rr_sec": 0.4
        }
    
    def detect_peaks(self, ecg_signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect R-peaks using Stationary Wavelet Transform.
        
        Args:
            ecg_signal: Raw ECG signal
            fs: Sampling frequency 
            wavelet: Wavelet type (default: 'db3')
            level: Decomposition level (default: 4)
            min_rr_sec: Minimum R-R interval in seconds (default: 0.4)
            
        Returns:
            Array of peak indices
        """
        params = self.get_default_params()
        params.update(kwargs)
        
        wavelet = params["wavelet"]
        level = params["level"]
        min_rr_sec = params["min_rr_sec"]
        
        # Adjust level to maximum allowed by signal length
        max_level = pywt.swt_max_level(len(ecg_signal))
        if max_level == 0:
            raise ValueError("Signal too short for SWT decomposition")
        level = min(level, max_level)
        
        # Perform undecimated SWT
        coeffs = pywt.swt(ecg_signal, wavelet, level=level)
        
        # Reconstruct signal using ISWT
        reconstructed = pywt.iswt(coeffs, wavelet)
        
        # Convert minimum R-R interval to samples
        min_distance = int(min_rr_sec * fs)
        
        # Detect peaks in reconstructed signal
        peaks, _ = find_peaks(reconstructed, distance=min_distance)
        
        return peaks


class WaveletDWTStrategy(PeakDetectionStrategy):
    """
    Discrete Wavelet Transform (DWT) based R-peak detection strategy.
    
    Uses standard wavelet decomposition for efficient signal processing.
    Fastest method with good baseline performance.
    """
    
    @property
    def name(self) -> str:
        return "dwt"
    
    @property
    def description(self) -> str:
        return "Discrete Wavelet Transform - efficient, good baseline performance"
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "wavelet": "haar", 
            "level": 5,
            "min_rr_sec": 0.4
        }
    
    def detect_peaks(self, ecg_signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect R-peaks using Discrete Wavelet Transform.
        
        Args:
            ecg_signal: Raw ECG signal
            fs: Sampling frequency
            wavelet: Wavelet type (default: 'haar')
            level: Decomposition level (default: 5)
            min_rr_sec: Minimum R-R interval in seconds (default: 0.4)
            
        Returns:
            Array of peak indices
        """
        params = self.get_default_params()
        params.update(kwargs)
        
        wavelet = params["wavelet"]
        level = params["level"] 
        min_rr_sec = params["min_rr_sec"]
        
        # Perform DWT decomposition
        coeffs = pywt.wavedec(ecg_signal, wavelet, level=level)
        
        # Reconstruct signal 
        reconstructed = pywt.waverec(coeffs, wavelet)
        
        # Convert minimum R-R interval to samples
        min_distance = int(min_rr_sec * fs)
        
        # Detect peaks in reconstructed signal
        peaks, _ = find_peaks(reconstructed, distance=min_distance)
        
        return peaks


class WaveletCWTStrategy(PeakDetectionStrategy):
    """
    Continuous Wavelet Transform (CWT) based R-peak detection strategy.
    
    Uses continuous wavelet transform for optimal time-frequency resolution.
    Best accuracy for R-peak detection, especially in challenging signals.
    """
    
    @property
    def name(self) -> str:
        return "cwt"
    
    @property
    def description(self) -> str:
        return "Continuous Wavelet Transform - best time-frequency resolution and accuracy"
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "wavelet": "haar",  # Haar wavelet for CWT
            "scales": None,  # Auto-calculated based on expected QRS duration
            "min_rr_sec": 0.4
        }
    
    def _calculate_scales(self, fs: float) -> np.ndarray:
        """
        Calculate optimal scales for CWT based on expected QRS complex duration.
        
        QRS complexes typically last 80-120ms, so we focus on those frequencies.
        """
        # QRS duration range: 0.08-0.12 seconds
        qrs_duration_range = [0.08, 0.12]
        
        # Convert to scales based on sampling frequency
        # Scale relates to the period of the wavelet in samples
        min_scale = max(1, int(qrs_duration_range[0] * fs / 4))  # Divide by 4 for better resolution
        max_scale = int(qrs_duration_range[1] * fs / 2)  # Divide by 2 for better resolution
        
        # Create scale range - use integers for PyWavelets CWT
        scales = np.arange(min_scale, max_scale + 1, max(1, (max_scale - min_scale) // 20))
        
        return scales
    
    def detect_peaks(self, ecg_signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect R-peaks using Continuous Wavelet Transform with PyWavelets.
        
        Args:
            ecg_signal: Raw ECG signal
            fs: Sampling frequency
            wavelet: Wavelet type (default: 'haar' - Haar wavelet)
            scales: CWT scales (auto-calculated if None)
            min_rr_sec: Minimum R-R interval in seconds (default: 0.4)
            
        Returns:
            Array of peak indices
        """
        params = self.get_default_params()
        params.update(kwargs)
        
        wavelet_name = params["wavelet"]
        scales = params["scales"] 
        min_rr_sec = params["min_rr_sec"]
        
        # Map ricker to mexh for PyWavelets compatibility (backward compatibility)
        if wavelet_name == "ricker":
            wavelet_name = "mexh"  # Mexican hat wavelet in PyWavelets
        
        # Auto-calculate scales if not provided
        if scales is None:
            scales = self._calculate_scales(fs)
        
        try:
            # Perform CWT using PyWavelets
            cwt_coeffs, freqs = pywt.cwt(ecg_signal, scales, wavelet_name)
            
            # Find the scale with maximum energy (typically corresponds to QRS)
            energy_per_scale = np.sum(np.abs(cwt_coeffs), axis=1)
            optimal_scale_idx = np.argmax(energy_per_scale)
            
            # Use coefficients at optimal scale for peak detection
            optimal_coeffs = cwt_coeffs[optimal_scale_idx, :]
            
            # Convert minimum R-R interval to samples
            min_distance = int(min_rr_sec * fs)
            
            # Detect peaks in CWT coefficients (use absolute values for peak detection)
            peaks, _ = find_peaks(np.abs(optimal_coeffs), distance=min_distance)
            
            return peaks
            
        except Exception as e:
            # Fallback to DWT if CWT fails
            warnings.warn(
                f"CWT failed with wavelet '{wavelet_name}': {str(e)}. "
                f"Falling back to DWT method.",
                RuntimeWarning
            )
            
            # Use DWT as fallback
            dwt_strategy = WaveletDWTStrategy()
            return dwt_strategy.detect_peaks(ecg_signal, fs, **kwargs)


class NeuroKit2Strategy(PeakDetectionStrategy):
    """
    NeuroKit2-based R-peak detection strategy.
    
    This is a wrapper strategy that will use NeuroKit2's built-in peak detection
    algorithms when the library is available. Supports multiple NeuroKit2 methods
    like pan_tompkins, xqrs, hamilton_segmenter, etc.
    """
    
    def __init__(self, method: str = "pan_tompkins"):
        """
        Initialize NeuroKit2 strategy with specific detection method.
        
        Args:
            method: NeuroKit2 detection method ("pan_tompkins", "xqrs", "hamilton_segmenter", etc.)
        """
        self.method = method
        self._nk2_available = self._check_neurokit2()
        
    def _check_neurokit2(self) -> bool:
        """Check if NeuroKit2 is available."""
        try:
            import neurokit2 as nk
            return True
        except ImportError:
            return False
    
    @property
    def name(self) -> str:
        return f"neurokit2_{self.method}"
    
    @property
    def description(self) -> str:
        return f"NeuroKit2 {self.method} detector - professional-grade ECG analysis"
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "sampling_rate": None,  # Will use fs from detect_peaks
            "show": False,
            "correct_artifacts": False
        }
    
    def detect_peaks(self, ecg_signal: np.ndarray, fs: float, **kwargs) -> np.ndarray:
        """
        Detect R-peaks using NeuroKit2 algorithms.
        
        Args:
            ecg_signal: Raw ECG signal
            fs: Sampling frequency
            method: NeuroKit2 detection method
            **kwargs: Additional NeuroKit2 parameters
            
        Returns:
            Array of peak indices
            
        Raises:
            ImportError: If NeuroKit2 is not installed
            ValueError: If the specified method is not available
        """
        if not self._nk2_available:
            raise ImportError(
                "NeuroKit2 is required for this strategy. "
                "Install it with: pip install neurokit2"
            )
        
        try:
            import neurokit2 as nk
        except ImportError as e:
            raise ImportError("Failed to import NeuroKit2") from e
        
        params = self.get_default_params()
        params.update(kwargs)
        params["sampling_rate"] = fs
        
        try:
            # Use NeuroKit2's ecg_peaks function
            _, peaks_dict = nk.ecg_peaks(ecg_signal, sampling_rate=fs, method=self.method, **params)
            
            # Extract peak indices
            peaks = peaks_dict["ECG_R_Peaks"]
            
            return np.array(peaks)
            
        except Exception as e:
            raise ValueError(f"NeuroKit2 peak detection failed with method '{self.method}': {str(e)}") from e


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
        # Wavelet-based strategies
        self.register_strategy(WaveletSWTStrategy())
        self.register_strategy(WaveletDWTStrategy())
        self.register_strategy(WaveletCWTStrategy())
        
        # NeuroKit2 strategies (will be available if NeuroKit2 is installed)
        neurokit2_methods = ["pan_tompkins", "xqrs", "hamilton_segmenter", "christov_segmenter"]
        for method in neurokit2_methods:
            try:
                strategy = NeuroKit2Strategy(method)
                self.register_strategy(strategy)
            except ImportError:
                # NeuroKit2 not available, skip these strategies
                pass
    
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


# Global registry instance
strategy_registry = PeakDetectionStrategyRegistry()