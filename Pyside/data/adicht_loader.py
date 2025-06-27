"""
adicht_loader.py
----------------
Loader for .adicht files using adi.read_file.
Parses LabChart signals and comments into Signal and SignalGroup objects.
"""

import numpy as np
import adi

from core.signal import Signal, SignalGroup
from core.comments import EMSComment
from processing.ecg_analyzer import ECGAnalyzer

# Global cache to avoid redundant loading
_adicht_cache = {}


def load_adicht(path, preload=True, gap_length=3):
    """
    Load a .adicht LabChart file and return a SignalGroup object.

    Args:
        path (str): Path to the .adicht file.
        preload (bool): Unused.
        gap_length (int): Seconds of zero-padding between records.

    Returns:
        SignalGroup: Group of Signal objects with metadata and comments.
    """
    global _adicht_cache
    if path in _adicht_cache:
        return _adicht_cache[path]

    file_data = adi.read_file(path)
    signals = []
    total_records = file_data.n_records
    ecg_signal = None

    for channel in file_data.channels:
        name = channel.name
        units = channel.units
        fs = channel.fs[0]
        fs_int = int(round(fs))

        # Concatenate records with gap
        full_data = []
        for record_id in range(1, total_records + 1):
            data = channel.get_data(record_id)
            if data is not None:
                full_data.append(data)
                if record_id < total_records:
                    full_data.append(np.zeros(gap_length * fs_int))
        full_data = np.concatenate(full_data)

        # Split into BB, ProData, AB
        bb = full_data[:fs_int]
        ab = full_data[-fs_int:]
        pro_data = full_data[fs_int:-fs_int]
        time = np.linspace(1 / fs, len(pro_data) / fs, len(pro_data))

        # Create Signal object
        sig = Signal(name=name, data=pro_data, time=time, units=units, fs=fs)
        sig.BB = bb
        sig.AB = ab

        # Load EMS comments
        comments = []
        for rec_idx, rec in enumerate(channel.records):
            if hasattr(rec, "comments") and rec.comments:
                for idx, c in enumerate(rec.comments):
                    tick_dt = getattr(c, "tick_dt", 1.0 / channel.fs[rec_idx])
                    tick_pos = getattr(c, "tick_position", 0)
                    text = getattr(c, "text", "")
                    time_sec = (
                        tick_pos * tick_dt
                        + rec_idx * channel.n_samples[rec_idx] * tick_dt
                    )
                    comments.append(
                        EMSComment(
                            text=text,
                            tick_position=tick_pos,
                            channel=name,
                            comment_id=idx + 1,
                            tick_dt=tick_dt,
                            time_sec=time_sec,
                            user_defined=False,
                        )
                    )
        sig.MarkerData = comments

        # If it's an ECG, process R-peaks
        if "ECG" in name.upper():
            ecg_full = np.concatenate([bb, pro_data, ab])
            peaks = ECGAnalyzer.detect_rr_peaks(ecg_full, fs_int)
            sig.FMxI = peaks
            sig.CL = np.diff(peaks)
            sig.CLI = peaks[1 : len(sig.CL) + 1]
            sig.CLT = sig.CLI / fs
            ecg_signal = sig  # Save for HR_GEN

        signals.append(sig)

    # Create HR_GEN if ECG present
    if ecg_signal and ecg_signal.FMxI is not None and len(ecg_signal.FMxI) >= 3:
        peaks = ecg_signal.FMxI
        hr_data = []
        hr_time = []
        for i in range(1, len(peaks) - 1):
            idx_start = peaks[i]
            idx_end = peaks[i + 1]
            t_start = idx_start / ecg_signal.fs
            t_end = idx_end / ecg_signal.fs
            rr = t_end - t_start
            hr = 60 / rr if rr > 0 else 0
            hr_data.extend([hr, hr])
            hr_time.extend([t_start, t_end])
        hr_signal = Signal(name="HR", data=hr_data, time=hr_time, units="bpm", fs=1.0)
        # Reemplaza HR existente si hay, si no, agrega
        replaced = False
        for i, s in enumerate(signals):
            if s.name.upper() == "HR":
                signals[i] = hr_signal
                replaced = True
                break
        if not replaced:
            signals.append(hr_signal)

    signal_group = SignalGroup(signals)
    _adicht_cache[path] = signal_group
    return signal_group
