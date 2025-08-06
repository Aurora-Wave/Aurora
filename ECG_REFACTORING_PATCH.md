# ECGAnalyzer Refactoring Patch: Strategy Pattern Implementation

## Overview

This patch implements a comprehensive refactoring of the ECGAnalyzer to support multiple peak detection strategies using the Strategy design pattern. The implementation provides:

1. **Three wavelet-based strategies**: SWT, DWT, and CWT
2. **NeuroKit2 integration**: Support for professional ECG detectors
3. **Full backward compatibility**: Existing code continues to work
4. **Extensible architecture**: Easy to add new detection algorithms

## Files Modified

### 1. **NEW FILE**: `Pyside/processing/peak_detection_strategies.py`

**Purpose**: Implements the Strategy pattern for peak detection algorithms.

**Key Components**:
- `PeakDetectionStrategy` (Abstract base class)
- `WaveletSWTStrategy` (Stationary Wavelet Transform)
- `WaveletDWTStrategy` (Discrete Wavelet Transform) 
- `WaveletCWTStrategy` (Continuous Wavelet Transform)
- `NeuroKit2Strategy` (NeuroKit2 wrapper)
- `PeakDetectionStrategyRegistry` (Strategy management)

**Features**:
- Pluggable architecture for detection algorithms
- Auto-detection of NeuroKit2 availability
- Configurable parameters per strategy
- Comprehensive error handling

### 2. **MODIFIED**: `Pyside/processing/ecg_analyzer.py`

**Changes**:
- Complete rewrite using Strategy pattern
- Enhanced API with backward compatibility
- Support for custom strategies
- Comprehensive documentation and examples

**Before**:
```python
# Old implementation - limited to basic wavelet transform
def detect_rr_peaks(ecg_signal, fs, **kwargs):
    method = kwargs.get("method","wavelet")
    # Fixed DWT implementation only
    coeffs = pywt.wavedec(ecg_signal, wv, level=5)
    reconstructed = pywt.waverec(coeffs,wv)
    peaks, _ = find_peaks(reconstructed, distance=min_dist)
    return peaks
```

**After**:
```python
# New implementation - flexible strategy-based approach
def detect_rr_peaks(ecg_signal, fs, method="dwt", strategy=None, **kwargs):
    # Handles multiple detection methods via strategy pattern
    detection_strategy = strategy_registry.get_strategy(method)
    return detection_strategy.detect_peaks(ecg_signal, fs, **kwargs)
```

### 3. **MODIFIED**: `Pyside/processing/__init__.py`

**Changes**:
- Added exports for new strategy classes
- Updated package documentation
- Exposed strategy registry for external use

### 4. **ADDED**: Missing `__init__.py` files

**Files Added**:
- `Pyside/data/__init__.py`
- `Pyside/ui/utils/__init__.py` 
- `Pyside/ui/widgets/__init__.py`

### 5. **MODIFIED**: Import statements converted to absolute form

**Files Modified**:
- `Pyside/data/data_manager.py`
- `Pyside/ui/widgets/selectable_viewbox.py`
- `Pyside/ui/managers/__init__.py`
- `Pyside/core/visualization/__init__.py`

### 6. **FIXED**: Critical bug in `Pyside/core/comments.py`

**Issue**: `self.label` referenced but never initialized
**Fix**: Added `label` parameter to `__init__` method

## API Changes and Backward Compatibility

### New Features

1. **Multiple Detection Methods**:
```python
# Wavelet-based methods
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="swt")  # Stationary WT
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="dwt")  # Discrete WT (default)
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="cwt")  # Continuous WT

# NeuroKit2 methods (when available)
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="pan_tompkins")
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="xqrs")
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="hamilton_segmenter")
```

2. **Custom Strategies**:
```python
# Register and use custom detection algorithm
class MyCustomDetector(PeakDetectionStrategy):
    # Implementation here
    pass

ECGAnalyzer.register_custom_strategy(MyCustomDetector())
peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method="my_custom")
```

3. **Strategy Information**:
```python
# Get available methods
methods = ECGAnalyzer.get_available_methods()

# Get default parameters for a method
defaults = ECGAnalyzer.get_strategy_defaults("swt")
```

### Backward Compatibility

All existing code continues to work without modification:

```python
# This still works exactly as before
peaks = ECGAnalyzer.detect_rr_peaks(ecg_signal, fs)

# Legacy parameters are automatically converted with deprecation warnings
peaks = ECGAnalyzer.detect_rr_peaks(ecg_signal, fs, method="wavelet", min_dist=0.5)
# DeprecationWarning: Method 'wavelet' is deprecated. Use 'dwt'...
# DeprecationWarning: Parameter 'min_dist' is deprecated. Use 'min_rr_sec'...
```

## Strategy-Specific Parameters

### SWT (Stationary Wavelet Transform)
- `wavelet`: Wavelet type (default: 'db3')
- `level`: Decomposition level (default: 4)
- `min_rr_sec`: Minimum R-R interval (default: 0.4)

### DWT (Discrete Wavelet Transform) - Default
- `wavelet`: Wavelet type (default: 'haar')
- `level`: Decomposition level (default: 5)
- `min_rr_sec`: Minimum R-R interval (default: 0.4)

### CWT (Continuous Wavelet Transform)
- `wavelet`: Wavelet type (default: 'ricker')
- `scales`: CWT scales (auto-calculated if None)
- `min_rr_sec`: Minimum R-R interval (default: 0.4)

### NeuroKit2 Methods
- `sampling_rate`: Automatically set from `fs` parameter
- `show`: Display plots (default: False)
- `correct_artifacts`: Enable artifact correction (default: False)
- Plus method-specific parameters from NeuroKit2 documentation

## Performance Characteristics

| Method | Speed | Accuracy | Best Use Case |
|--------|-------|----------|---------------|
| DWT | Fastest | Good | Default choice, clean signals |
| SWT | Slowest | Robust | Noisy signals, precise timing needed |
| CWT | Medium | Best | Complex signals, research applications |
| NeuroKit2 | Varies | Professional | Clinical applications, validated algorithms |

## Migration Guide

### For Existing Code
No changes required! The default behavior remains identical to the previous implementation.

### For New Development
Use the enhanced API for better control:

```python
# Choose optimal method for your use case
if signal_quality == "high":
    method = "dwt"  # Fast processing
elif signal_quality == "poor":
    method = "swt"  # Robust detection
else:
    method = "pan_tompkins"  # Professional-grade

peaks = ECGAnalyzer.detect_rr_peaks(ecg, fs, method=method)
```

### Adding NeuroKit2 Support
Install NeuroKit2 to enable professional algorithms:
```bash
pip install neurokit2
```

Once installed, NeuroKit2 methods become automatically available.

## Testing and Validation

### Unit Tests Required
- Test each strategy with synthetic ECG signals
- Validate backward compatibility with existing test cases
- Performance benchmarks for different signal lengths
- Error handling for edge cases

### Integration Testing
- Test NeuroKit2 integration (when available)
- Validate parameter conversion and deprecation warnings
- Test custom strategy registration and usage

## Future Extensions

The Strategy pattern architecture makes it easy to add:

1. **More NeuroKit2 algorithms**: Any new detectors from NeuroKit2
2. **Custom academic algorithms**: Research-specific detection methods
3. **Hybrid strategies**: Combining multiple detection approaches
4. **Real-time strategies**: Optimized for streaming ECG data
5. **Machine learning detectors**: AI-based R-peak detection

## Error Handling Improvements

- Comprehensive error messages with suggested solutions
- Graceful degradation when optional dependencies are missing
- Input validation for all strategy parameters
- Clear documentation of method requirements and limitations

## Dependencies

### Required (no changes)
- numpy
- scipy
- pywt (PyWavelets)

### Optional (new)
- neurokit2: For professional ECG analysis algorithms

## Summary

This refactoring transforms the ECGAnalyzer from a fixed-implementation class to a flexible, strategy-based framework. It maintains 100% backward compatibility while enabling:

- Support for multiple detection algorithms
- Easy integration of NeuroKit2 professional tools
- Extensible architecture for future algorithms
- Better separation of concerns
- Enhanced testing and validation capabilities

The implementation follows software engineering best practices:
- Strategy design pattern for algorithm selection
- Comprehensive error handling and validation
- Extensive documentation and examples
- Backward compatibility with deprecation warnings
- Modular, testable code structure

Users can continue using existing code without changes, while new development can leverage the enhanced capabilities for improved ECG analysis performance.