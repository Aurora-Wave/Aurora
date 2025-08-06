# data/signal.py

import numpy as np
from Pyside.processing.ecg_analyzer import ECGAnalyzer

class Signal:
    """
    Represents a single physiological signal, including time series data,
    units, sampling frequency, and optional buffers and annotations.
    """
    def __init__(self, name: str, data: np.ndarray, time: np.ndarray,
                 units: str = "a.u.", fs: float = 1.0):
        # signal metadata
        self.name = name
        self.units = units
        self.fs = fs

        # core data arrays
        self._data = np.asarray(data)
        self._time = np.asarray(time)

        # optional buffers
        self.BB = np.array([])  # before-buffer
        self.AB = np.array([])  # after-buffer

        # annotations (e.g., markers)
        self.MarkerData = []

    @property
    def data(self) -> np.ndarray:
        return self._data

    @property
    def time(self) -> np.ndarray:
        return self._time

    def to_csv(self, filepath: str):
        """
        Export the signal (time, data) to a CSV file.
        """
        arr = np.column_stack((self._time, self._data))
        np.savetxt(filepath, arr, delimiter=",", header="time,data", comments="")

    def __len__(self):
        return len(self._data)

    def __str__(self):
        n = len(self._data)
        dur = (self._time[-1] - self._time[0]) if n > 1 else 0
        preview = np.round(self._data[:min(10, n)], 3)
        return (f"Signal '{self.name}': {n} samples, {dur:.2f}s, fs={self.fs}Hz\n"
                f"First data pts: {preview}")
class HR_Gen_Signal(Signal):
    """
    Specialized Signal for derived HR: integrates R-peak detection
    and incremental HR updates.
    """
    def __init__(self, name: str, ecg_data: np.ndarray, ecg_time: np.ndarray,
                 units: str, fs: float):
        super().__init__(name=name, data=ecg_data, time=ecg_time, units=units, fs=fs)
        self.r_peaks = np.array([], dtype=int)

    def set_r_peaks(self, ECG: Signal, **kargs):
        peaks = ECGAnalyzer.detect_rr_peaks(ECG.data, ECG.fs, **kargs)
        self.r_peaks = np.sort(np.asarray(peaks, dtype=int))
        self._generate_full_hr()

    def _generate_full_hr(self):
        """
        Fill HR values between each pair of R-peaks using the current list of peaks.
        Only fills intervals between consecutive peaks.
        """
        if len(self.r_peaks) < 2:
            self._data[:] = np.nan
            return

        hr_data = np.full_like(self._data, np.nan, dtype=np.float32)
        for i in range(len(self.r_peaks) - 1):
            start = int(self.r_peaks[i])
            end = int(self.r_peaks[i + 1])
            rr = (end - start) / self.fs
            if rr <= 0:
                continue
            hr = 60.0 / rr
            if hr < 20 or hr > 250:
                hr = np.nan
            if start < end:
                hr_data[start:end] = hr
        self._data = hr_data
        self.units = "bpm"

    def add_peak(self, new_peak: int):
        """
        Insert a new R-peak, update only the affected segments.
        No duplicates allowed. Keeps r_peaks sorted.
        """
        new_peak = int(new_peak)
        if new_peak in self.r_peaks:
            return

        # Insert and keep sorted
        self.r_peaks = np.sort(np.append(self.r_peaks, new_peak))

        # Find the position where it was inserted
        i = np.searchsorted(self.r_peaks, new_peak)

        # Update the two adjacent segments (before and after the new peak)
        if i > 0:
            self._update_hr_segment(i - 1)
        if i < len(self.r_peaks) - 1:
            self._update_hr_segment(i)

    def update_peak(self, i: int, new_index: int):
        """
        Modify an existing R-peak and update affected HR segments only.
        """
        if not (0 <= i < len(self.r_peaks)):
            return
        self.r_peaks[i] = int(new_index)
        self.r_peaks = np.sort(self.r_peaks)
        # Update segments around the modified peak
        if i > 0:
            self._update_hr_segment(i - 1)
        if i < len(self.r_peaks) - 1:
            self._update_hr_segment(i)

    def _update_hr_segment(self, i: int):
        """
        Recompute HR for interval between r_peaks[i] and r_peaks[i+1].
        """
        start = int(self.r_peaks[i])
        end = int(self.r_peaks[i + 1])
        rr = (end - start) / self.fs
        if rr <= 0 or start >= end:
            self._data[start:end] = np.nan
            return
        hr = 60.0 / rr
        if hr < 20 or hr > 250:
            hr = np.nan
        self._data[start:end] = hr

    def delete_peak(self, peak_idx: int):
        """
        Remove the R-peak at the given index and update only affected HR segments.
        """
        if not (0 <= peak_idx < len(self.r_peaks)):
            return
        self.r_peaks = np.delete(self.r_peaks, peak_idx)
        # Update both neighboring segments if possible
        if peak_idx > 0 and peak_idx < len(self.r_peaks):
            self._update_hr_segment(peak_idx - 1)
        if peak_idx < len(self.r_peaks) - 1:
            self._update_hr_segment(peak_idx)

    def get_hr_signal(self):
        if len(self.r_peaks) < 2:
            return None
        return Signal(
            name=f"{self.name}_HRgen",
            data=self._data.copy(),
            time=self._time.copy(),
            units="bpm",
            fs=self.fs
        )



class SignalGroup:
    """
    Container for multiple Signal or Signal subclasses.
    """
    def __init__(self, signals: list[Signal]):
        self.signals = {sig.name: sig for sig in signals}

    def get(self, name: str) -> Signal | None:
        return self.signals.get(name)

    def list_names(self) -> list[str]:
        return list(self.signals.keys())

    def add(self, sig: Signal):
        self.signals[sig.name] = sig

    def remove(self, name: str):
        self.signals.pop(name, None)

    def export_all(self, folder: str):
        """
        Export each signal to CSV in the given folder.
        """
        for sig in self.signals.values():
            path = f"{folder}/{sig.name}.csv"
            sig.to_csv(path)
