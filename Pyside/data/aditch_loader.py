import numpy as np
import adi
from Pyside.core.signal import Signal, HR_Gen_Signal
from Pyside.core.comments import EMSComment
from Pyside.data.base_loader import BaseLoader
import logging
class AditchLoader(BaseLoader):
    """
    Loader for .adicht files using adi.read_file.
    Parses LabChart signals and comments into Signal and HR_Gen_Signal objects.
    Supports full loading, chunk-based loading, and comment extraction.
    """
    def __init__(self):
        self.path = None
        self.file_data = None
        self.metadata = {}
        self.comments = []
        self.logger = logging.getLogger(__name__)

    def load(self, path: str):
        self.path = path
        self.file_data = adi.read_file(path)
        self.metadata = {
            "channels": [ch.name for ch in self.file_data.channels],
            "fs": {ch.name: int(round(ch.fs[0])) for ch in self.file_data.channels},
            "n_records": self.file_data.n_records
        }
        # Extract comments
        self.comments = []
        for ch in self.file_data.channels:
            name = ch.name
            for rec_idx, rec in enumerate(ch.records):
                if hasattr(rec, "comments") and rec.comments:
                    for idx, c in enumerate(rec.comments):
                        tick_dt = getattr(c, "tick_dt", 1.0 / ch.fs[rec_idx])
                        tick_pos = getattr(c, "tick_position", 0)
                        time_sec = tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                        self.comments.append(EMSComment(
                            text=c.text,
                            tick_position=tick_pos,
                            channel=name,
                            comment_id=idx + 1,
                            tick_dt=tick_dt,
                            time_sec=time_sec,
                            user_defined=False))

    def get_metadata(self) -> dict:
        return self.metadata

    def get_all_comments(self) -> list[EMSComment]:
        return self.comments

    def get_full_trace(self, channel: str, gap_length: int = 3, **kwargs) -> Signal:
        """
        Return a full Signal or HR_Gen_Signal for the given channel.
        If channel is HR_GEN (case-insensitive) and ECG exists, derive using parameters in kwargs.
        """
        upper = channel.upper()

        # HR
        if upper == "HR_GEN" and "ECG" in self.metadata['channels']:
            self.logger.info(f"Triying to generated HR with {kwargs} ")
            # Derive HR from ECG, using kwargs if provided
            raw_sig = self.get_full_trace('ECG', gap_length)
            # Defaults for HR_gen parameters
            wavelet = kwargs.get('wavelet', 'haar')
            swt_level = kwargs.get('swt_level', 4)
            min_rr_sec = kwargs.get('min_rr_sec', 0.4)
  
            hr_sig = HR_Gen_Signal(
                name="HR_gen",
                ecg_data=raw_sig.data,
                ecg_time=raw_sig.time,
                units="bpm",
                fs=raw_sig.fs)
            
            hr_sig.set_r_peaks(
                raw_sig,
                wavelet=wavelet,
                swt_level=swt_level,
                min_rr_sec=min_rr_sec
            )
            hr_sig.MarkerData = raw_sig.MarkerData
            
            if channel not in self.metadata.get('channels'):
                self.metadata.get('channels').append("HR_gen")

            self.logger.debug((f" canales actuales {self.metadata.get('channels')}"))

            return hr_sig

        # Otherwise, load raw channel
        ch = next((c for c in self.file_data.channels if c.name == channel), None)
        if ch is None:
            raise ValueError(f"Channel '{channel}' not found in file.")

        # Records suma
        fs = self.metadata['fs'][channel]
        total = self.metadata['n_records']
        segments = []
        for rec_id in range(1, total + 1):
            data = ch.get_data(rec_id)
            if data is not None:
                segments.append(data)
                if rec_id < total:
                    segments.append(np.zeros(gap_length * fs))
        full = np.concatenate(segments)
        bb = full[:fs]
        ab = full[-fs:]
        core = full[fs:-fs]
        time = np.linspace(1 / fs, len(core) / fs, len(core))

        sig = Signal(
            name=channel,
            data=core,
            time=time,
            units=ch.units,
            fs=fs
        )
        sig.BB = bb
        sig.AB = ab
        sig.MarkerData = [c for c in self.comments if c.channel == channel]
        return sig
