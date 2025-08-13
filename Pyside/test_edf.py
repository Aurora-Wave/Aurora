#!/usr/bin/env python
"""
Convert .adicht (LabChart) ➜ EDF+  with ECG + HR_GEN channels.

Uso:
    python adicht_to_edf.py <input.adicht> <output.edf>
"""

from pathlib import Path
import sys
from datetime import datetime, timezone
import numpy as np
import mne
from mne.io.constants import FIFF
from mne.filter import resample

from Pyside.data.aditch_loader import AditchLoader


# 1. Parse CLI arguments
if len(sys.argv) < 3:
    sys.exit("Usage: python adicht_to_edf.py <input.adicht> <output.edf>")

in_path  = Path(sys.argv[1]).expanduser().resolve()
out_path = Path(sys.argv[2]).expanduser().resolve()

if not in_path.exists():
    sys.exit(f"Input file not found: {in_path}")

# 2. Load ECG & HR_GEN
loader = AditchLoader()
loader.load(str(in_path))

sig_ecg = loader.get_full_trace("ECG")
sig_hr  = loader.get_full_trace("HR_gen")   

# 3. Resample HR_GEN to match ECG fs
target_fs = sig_ecg.fs
if sig_hr.fs != target_fs:
    sig_hr.data = resample(sig_hr.data, up=int(target_fs), down=int(sig_hr.fs))
    sig_hr.fs   = target_fs

# 4. Ensure finite data (replace NaN / inf with 0.0)

clean_ecg = np.nan_to_num(sig_ecg.data, nan=0.0, posinf=0.0, neginf=0.0)
clean_hr  = np.nan_to_num(sig_hr.data,  nan=0.0, posinf=0.0, neginf=0.0)

data = np.vstack([clean_ecg, clean_hr])      # (2, n_samples)

# 5. Construct RawArray
info = mne.create_info(
    ch_names=["ECG", "HR_GEN"],
    sfreq=target_fs,
    ch_types=["ecg", "misc"],
)
# ECG in mV
info["chs"][0]["unit"]     = FIFF.FIFF_UNIT_V
info["chs"][0]["unit_mul"] = -3

# HR dimensionless
info["chs"][1]["unit"] = 0

raw = mne.io.RawArray(data, info)
raw.set_meas_date(datetime.now(timezone.utc).replace(microsecond=0))

# Annotations
if loader.comments:
    onsets       = [float(c.time) for c in loader.comments]
    durations    = [0.0] * len(loader.comments)
    descriptions = [str(c.text) for c in loader.comments]
    raw.set_annotations(mne.Annotations(onsets, durations, descriptions))


mne.export.export_raw(
    str(out_path),          # fname
    raw,                    # Raw
    fmt="edf",
    physical_range="auto",
    overwrite=True,
    add_ch_type=False,
)
print(f"[edfio] EDF+ written to {out_path}")
sys.exit(0)