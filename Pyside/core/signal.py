# data/signal.py

import numpy as np
from processing.ecg_analyzer import ECGAnalyzer

class Signal:
    """
    Represents a single physiological signal, including time series data,
    units, sampling frequency, and optional buffers, annotations, and analysis fields.
    """

    def __init__(self, name: str, data: np.ndarray, time: np.ndarray,
                 units: str = "a.u.", fs: float = 1.0):
        self.name = name
        self.units = units
        self.fs = fs

        self._data = np.asarray(data)
        self._time = np.asarray(time)

        # Optional pre/post padding buffers
        self.BB = np.array([])   # before buffer
        self.AB = np.array([])   # after buffer

        # Annotations
        self.MarkerData = []

        # ECG‐specific analysis placeholders
        self.FMxI = np.array([])  # R‐peak sample indices
        self.CL   = np.array([])  # RR intervals in samples
        self.CLI  = np.array([])  # second peak index of each RR interval
        self.CLT  = np.array([])  # time of each RR in seconds

    @property
    def data(self) -> np.ndarray:
        return self._data

    @property
    def time(self) -> np.ndarray:
        return self._time

    def get_full_signal(self, include_time: bool = False):
        """
        Return the full signal including BB and AB buffers.
        """
        full = np.concatenate([self.BB, self._data, self.AB])
        if include_time:
            n = len(full)
            t = np.linspace(1/self.fs, n/self.fs, n)
            return full, t
        return full

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
        dur = (self._time[-1] - self._time[0]) if n>1 else 0
        preview = np.round(self._data[:min(10,n)], 3)
        return (f"Signal '{self.name}': {n} samples, {dur:.2f}s, fs={self.fs}Hz\n"
                f"First data pts: {preview}")


class ECGSignal(Signal):
    """
    Specialized Signal for ECG: integrates R-peak detection via ECGAnalyzer
    and builds an HR signal from RR intervals.
    """

    def __init__(self, **kwargs):
        """
        Accepts same kwargs as Signal.__init__: name, data, time, units, fs.
        """
        super().__init__(**kwargs)
        self.r_peaks = np.array([])
        self.rr_intervals = np.array([])
        self.rr_times = np.array([])

    def detect_r_peaks(self,
                       wavelet: str = 'db3',
                       swt_level: int = 3,
                       min_rr_sec: float = 0.4):
        """
        Detect R‐peaks in the full ECG (including BB/AB).
        Populates:
          - self.FMxI: sample indices of R‐peaks
          - self.CL:   RR intervals in samples
          - self.CLI:  index of the 2nd peak in each RR (i.e. self.FMxI[1:])
          - self.CLT:  time of that 2nd peak (seconds)
        """
        # build the full signal
        if self.BB.size and self.AB.size:
            ecg_full = np.concatenate([self.BB, self._data, self.AB])
        else:
            ecg_full = self._data

        # detect peaks via the unified method
        peaks = ECGAnalyzer.detect_rr_peaks(
            ecg_full,
            fs=self.fs,
            wavelet=wavelet,
            swt_level=swt_level,
            min_rr_sec=min_rr_sec
        )

        # store results
        self.FMxI = np.asarray(peaks)
        if len(self.FMxI) > 1:
            # RR intervals in samples
            self.CL = np.diff(self.FMxI)
            # second peak index per interval
            self.CLI = self.FMxI[1:]
            # time of each RR in seconds
            self.CLT = self.CLI / self.fs
        else:
            self.CL = np.array([])
            self.CLI = np.array([])
            self.CLT = np.array([])

    def get_hr_signal(self) -> Signal | None:
        """
        Return a new Signal named 'HR_gen' representing instantaneous HR.
        Requires detect_r_peaks() to have been called first.
        """
        if self.CLT.size == 0:
            return None

        hr_data = 60.0 / (self.CL / self.fs)  # bpm
        hr_time = self.CLT

        return Signal(
            name="HR_gen",
            data=hr_data,
            time=hr_time,
            units="bpm",
            fs=1.0
        )


class SignalGroup:
    """
    Container for multiple Signal or ECGSignal objects.
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
