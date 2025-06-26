import numpy as np

class Signal:
    """
    Represents a single physiological signal, including time series data, units,
    sampling frequency, and optional buffers, annotations, and analysis fields.
    """

    def __init__(self, name, data, time, units="a.u.", fs=1.0):
        self.name = name
        self.units = units
        self.fs = fs

        self._data = np.asarray(data)
        self._time = np.asarray(time)

        # Optional: boundary buffers (for pre/post padding)
        self.BB = np.array([])
        self.AB = np.array([])

        # Optional: annotations (e.g. from LabChart)
        self.MarkerData = []

        # Optional: ECG-specific analysis (if applicable)
        self.FMxI = []  # R-peak indices
        self.CL = []    # RR intervals in samples
        self.CLI = []   # Second peak index per RR
        self.CLT = []   # Time of second peak (s)

    @property
    def data(self):
        return self._data

    @property
    def time(self):
        return self._time

    #def get_segment(self, start_time, end_time):
    #    """
    #    Return a Signal segment between start_time and end_time.
    #    """
    #    mask = (self._time >= start_time) & (self._time <= end_time)
    #    return Signal(self.name, self._data[mask], self._time[mask], self.units, self.fs)

    def get_full_signal(self, include_time=False):
        """
        Reconstruct the full signal including BB and AB buffers.

        Returns:
            np.ndarray or (np.ndarray, np.ndarray)
        """
        full_data = np.concatenate([self.BB, self._data, self.AB])
        if include_time:
            total_len = len(full_data)
            full_time = np.linspace(1 / self.fs, total_len / self.fs, total_len)
            return full_data, full_time
        return full_data

    def to_csv(self, filepath):
        """
        Export the signal to a CSV file.
        """
        np.savetxt(filepath, np.column_stack((self._time, self._data)),
                   delimiter=",", header="time,data", comments='')

    def __getitem__(self, key):
        return self._data[key], self._time[key]

    def __len__(self):
        return len(self._data)
    def __str__(self):
        """
        Return a human-readable summary of the signal object.
        """
        n_samples = len(self._data)
        duration = self._time[-1] - self._time[0] if n_samples > 1 else 0
        t = 200
        return (
            f"Signal: {self.name}\n"
            f"  Units: {self.units}\n"
            f"  Sampling Rate: {self.fs} Hz\n"
            f"  Duration: {duration:.2f} seconds\n"
            f"  Samples: {n_samples}\n"
            f"  First 30 data points: {self._data[t:t+30]}\n"
            f"  First 30 time values: {self._time[t:t+30]}"
        )



class SignalGroup:
    """
    Represents a collection of Signal objects.
    Provides access, listing, and export functionalities.
    """

    def __init__(self, signals):
        self.signals = {s.name: s for s in signals}

    def get(self, name):
        return self.signals.get(name)

    def list_names(self):
        return list(self.signals.keys())

    def export_all(self, folder_path):
        for signal in self.signals.values():
            signal.to_csv(f"{folder_path}/{signal.name}.csv")
