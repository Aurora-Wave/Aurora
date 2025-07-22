import numpy as np
import adi
from core.signal import Signal, ECGSignal
from core.comments import EMSComment
from data.base_loader import BaseLoader

class AditchLoader(BaseLoader):
    """
    Loader for .adicht files using adi.read_file.
    Parses LabChart signals and comments into Signal and ECGSignal objects.
    Supports full loading, chunk-based loading, and comment extraction.
    """

    def __init__(self):
        self.path = None
        self.file_data = None
        self.metadata = {}
        self.comments = []

    def load(self, path):
        """
        Load the .adicht file and initialize metadata and comments.
        This does not load full signal data.

        Args:
            path (str): Path to the .adicht file.
        """
        self.path = path
        self.file_data = adi.read_file(path)

        # Parse basic metadata
        self.metadata = {
            "channels": [ch.name for ch in self.file_data.channels],
            "fs": {ch.name: int(round(ch.fs[0])) for ch in self.file_data.channels},
            "n_records": self.file_data.n_records,
        }

        # Extract all EMS-style comments across channels and records
        self.comments = []
        for ch in self.file_data.channels:
            name = ch.name
            for rec_idx, rec in enumerate(ch.records):
                if hasattr(rec, "comments") and rec.comments:
                    for idx, c in enumerate(rec.comments):
                        tick_dt = getattr(c, "tick_dt", 1.0 / ch.fs[rec_idx])
                        tick_pos = getattr(c, "tick_position", 0)
                        text = getattr(c, "text", "")
                        time_sec = tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                        self.comments.append(EMSComment(
                            text=text,
                            tick_position=tick_pos,
                            channel=name,
                            comment_id=idx + 1,
                            tick_dt=tick_dt,
                            time_sec=time_sec,
                            user_defined=False,
                        ))

    def get_metadata(self):
        """Return metadata extracted from the file."""
        return self.metadata

    def get_all_comments(self):
        """Return list of EMSComment objects parsed from the file."""
        return self.comments

    def get_chunk(self, channel: str, start: float, duration: float):
        """
        Return a chunk of signal data for a given channel and time window.

        Args:
            channel (str): Channel name.
            start (float): Start time in seconds.
            duration (float): Duration in seconds.

        Returns:
            np.ndarray: Chunk of signal data corresponding to the requested window.
        """
        ch = next((c for c in self.file_data.channels if c.name == channel), None)
        if ch is None:
            raise ValueError(f"Channel '{channel}' not found.")

        fs = self.metadata["fs"][channel]
        start_idx = int(start * fs)
        end_idx = int((start + duration) * fs)

        data = []
        total_samples = 0
        for rec_id in range(1, self.file_data.n_records + 1):
            segment = ch.get_data(rec_id)
            if segment is None:
                continue

            seg_len = len(segment)
            if total_samples + seg_len < start_idx:
                total_samples += seg_len
                continue

            # Get overlap range
            s = max(0, start_idx - total_samples)
            e = min(seg_len, end_idx - total_samples)
            if s < e:
                data.append(segment[s:e])
            total_samples += seg_len
            if total_samples >= end_idx:
                break

        if not data:
            return np.array([])

        return np.concatenate(data)

    def get_full_trace(self, channel: str, gap_length=3):
        """
        Load the full signal for a given channel, including buffers and annotations.

        Args:
            channel (str): Channel name.
            gap_length (int): Length in seconds for padding between records.

        Returns:
            Signal or ECGSignal: Full signal object.
        """
        ch = next((c for c in self.file_data.channels if c.name == channel), None)
        if ch is None:
            raise ValueError(f"Channel '{channel}' not found.")

        fs = self.metadata["fs"][channel]
        units = ch.units
        total_records = self.file_data.n_records

        # Concatenate records with optional gaps
        full_data = []
        for rec_id in range(1, total_records + 1):
            data = ch.get_data(rec_id)
            if data is not None:
                full_data.append(data)
                if rec_id < total_records:
                    full_data.append(np.zeros(gap_length * fs))
        full_data = np.concatenate(full_data)

        # Segment buffers
        bb = full_data[:fs]
        ab = full_data[-fs:]
        pro_data = full_data[fs:-fs]
        time = np.linspace(1 / fs, len(pro_data) / fs, len(pro_data))

        # Instantiate signal
        if "ECG" in channel.upper():
            sig = ECGSignal(name=channel, data=pro_data, time=time, units=units, fs=fs)
            sig.BB = bb
            sig.AB = ab
            sig.detect_r_peaks()
        else:
            sig = Signal(name=channel, data=pro_data, time=time, units=units, fs=fs)
            sig.BB = bb
            sig.AB = ab

        # Attach relevant comments
        sig.MarkerData = [c for c in self.comments if c.channel == channel]
        return sig
