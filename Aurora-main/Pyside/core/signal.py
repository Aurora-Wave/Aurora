# data/signal.py

import numpy as np
from processing.ecg_analyzer import ECGAnalyzer

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
        # initialize base signal with raw ECG data
        super().__init__(name=name,data=ecg_data,time=ecg_time,units=units,fs=fs)
        # container for detected peak indices
        self.r_peaks = np.array([])

    def set_r_peaks(self, ECG: Signal, **kargs):
        """
        Detect R-peaks and generate the full HR series.
        """
        # detect peaks on raw ECG
        peaks = ECGAnalyzer.detect_rr_peaks(ECG.data, ECG.fs, **kargs)
        self.r_peaks = np.sort(np.asarray(peaks))
        # fill in HR values across entire signal
        self._generate_full_hr()

    def _generate_full_hr(self):
        """
        Internal: fill HR values between each pair of R-peaks.
        """
        if len(self.r_peaks) < 2:
            return
        hr_data = np.zeros_like(self._data)
        # compute HR for each interval
        for i in range(len(self.r_peaks) - 1):
            start = int(self.r_peaks[i])
            end = int(self.r_peaks[i + 1])
            rr = (end - start) / self.fs
            if rr <= 0:
                continue
            hr = 60.0 / rr
            hr_data[start:end] = hr
        self._data = hr_data
        self.units = "bpm"

    def add_peak(self, new_peak: int):
        """
        Append a new R-peak and update only the new segment's HR.
        """
        if self.r_peaks.size == 0:
            # first peak: store and wait for next
            self.r_peaks = np.array([new_peak])
            return
        last = int(self.r_peaks[-1])
        if new_peak <= last:
            raise ValueError("New peak must be greater than last detected peak.")
        # compute HR for the new interval
        rr = (new_peak - last) / self.fs
        if rr <= 0:
            return
        hr = 60.0 / rr
        # append and fill segment
        self.r_peaks = np.append(self.r_peaks, new_peak)
        self._data[last:new_peak] = hr

    def update_peak(self, i: int, new_index: int):
        """
        Modify an existing R-peak and update affected HR segments.
        """
        if not (0 <= i < len(self.r_peaks)):
            return
        self.r_peaks[i] = new_index
        self.r_peaks = np.sort(self.r_peaks)
        # update segments around the modified peak
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
            return
        hr = 60.0 / rr
        self._data[start:end] = hr

    def get_hr_signal(self):
        """
        Return a standalone Signal object of the HR series.
        """
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
