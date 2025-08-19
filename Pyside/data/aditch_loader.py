import numpy as np
import adi
from Pyside.core.signal import Signal, HR_Gen_Signal
from Pyside.core.comments import EMSComment
from Pyside.data.base_loader import BaseLoader
from Pyside.core import get_user_logger
import datetime as dt
import mne
from mne.io.constants import FIFF
from mne.filter import resample

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
        self.logger = get_user_logger(self.__class__.__name__)

    def load(self, path: str):
        self.path = path
        self.file_data = adi.read_file(path)
        self.metadata = {
            "channels": [ch.name for ch in self.file_data.channels],
            "fs": {ch.name: int(round(ch.fs[0])) for ch in self.file_data.channels},
            "n_records": self.file_data.n_records
        }
        # Extract comments (avoid redundancy by processing only first channel with comments)
        self.comments = []
        comment_id = 1
        for ch in self.file_data.channels:
            name = ch.name
            has_comments = False
            
            for rec_idx, rec in enumerate(ch.records):
                if hasattr(rec, "comments") and rec.comments:
                    has_comments = True
                    for c in rec.comments:
                        tick_dt = getattr(c, "tick_dt", 1.0 / ch.fs[rec_idx])
                        tick_pos = getattr(c, "tick_position", 0)
                        time_sec = tick_pos * tick_dt + rec_idx * ch.n_samples[rec_idx] * tick_dt
                        self.comments.append(EMSComment(
                            text=c.text,
                            tick_position=tick_pos,
                            comment_id=comment_id,
                            tick_dt=tick_dt,
                            time_sec=time_sec,
                            user_defined=False))
                        comment_id += 1
            
            # If this channel had comments, no need to check others (avoid duplicates)
            if has_comments:
                break
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
            min_rr_sec = kwargs.get('min_rr_sec', 0.6)
  
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
        sig.MarkerData = self.comments  # Comments are now global, not channel-specific
        return sig
    
    def convert_to_edf(
        self,
        out_path: str,
        channels: list[str] | None = None,
        *,
        resample_enable: bool = True,
        target_fs: float | None = None,
        overwrite: bool = True,
        patient: str = "AuroraWave",
        recording: str | None = None,
        start_datetime: dt.datetime | None = None,
    ) -> str:
        """
        Export the loaded .adicht file to EDF+ using MNE-Python.
        """
        if self.file_data is None:
            raise RuntimeError("No file loaded. Call `load()` first.")

        # 1. Channel selection
        ch_list = channels or self.metadata["channels"]
        ch_type_map = {
            "ECG": "ecg",
            "EEG": "eeg",
            "EMG": "emg",
            "HR_GEN": "misc",
            "HR": "misc",
        }

        # unit_map -> (base_unit, unit_mul)
        unit_map = {
            "V":   (FIFF.FIFF_UNIT_V, 0),
            "mV":  (FIFF.FIFF_UNIT_V, -3),
            "µV":  (FIFF.FIFF_UNIT_V, -6),
            "uV":  (FIFF.FIFF_UNIT_V, -6),
            "bpm": (0, 0),        # UA
            "mmHg": (0, 0),
        }

        ch_data, ch_names, ch_types, base_units, unit_muls, fs_list = [], [], [], [], [], []

        for ch_name in ch_list:
            sig = self.get_full_trace(ch_name)
            ch_names.append(sig.name)
            ch_types.append(ch_type_map.get(sig.name.upper(), "misc"))
            ch_data.append(sig.data.astype(float, copy=False))
            fs_list.append(float(sig.fs))

            # Unit handling
            base, mul = unit_map.get(str(sig.units), (0, 0))
            base_units.append(base)
            unit_muls.append(mul)

        # 2. Resampling (if needed)
        if resample_enable:
            tgt_fs = target_fs or max(fs_list)
            resampled = []
            for data, fs in zip(ch_data, fs_list):
                if fs != tgt_fs:
                    data = resample(data, up=int(tgt_fs), down=int(fs))
                resampled.append(data)
            ch_data = resampled
            sfreq = tgt_fs
        else:
            if len(set(fs_list)) > 1:
                raise ValueError(
                    "Channels have different fs; enable resampling or pick subset with same fs."
                )
            sfreq = fs_list[0]

        data_mat = np.vstack(ch_data)  # (n_channels, n_samples)

        # 3. Build Info and Raw
        info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)
        info["meas_date"] = start_datetime  # None → now
        info["subject_info"] = {"his_id": patient}
        if recording:
            info["description"] = recording

        # Apply units
        for idx in range(len(ch_names)):
            info["chs"][idx]["unit"] = base_units[idx]
            info["chs"][idx]["unit_mul"] = unit_muls[idx]

        raw = mne.io.RawArray(data_mat, info)

        # 4. Annotations from EMSComment
        if self.comments:
            onsets = [c.time for c in self.comments]
            durations = [0.0] * len(self.comments)
            descriptions = [c.text for c in self.comments]
            raw.set_annotations(mne.Annotations(onsets, durations, descriptions))

        # 5. Export to EDF+
        mne.export.export_raw(
            raw,
            out_path,
            fmt="edf",
            physical_range="auto",
            overwrite=overwrite,
            add_ch_type=False,
        )

        self.logger.info(f"EDF+ file written to {out_path}")
        return out_path