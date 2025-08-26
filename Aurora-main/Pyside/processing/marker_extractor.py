"""
marker_extractor.py
-------------------
Functions to extract physiological markers from signals, supporting
multiple modes: whole signal, by event/comment, or by window.
"""

import numpy as np

# Marker function dictionary
def mean_marker(x):
    # Calculate mean, ignoring NaN
    return float(np.nanmean(x))

def max_marker(x):
    return float(np.nanmax(x))

def min_marker(x):
    return float(np.nanmin(x))

def std_marker(x):
    return float(np.nanstd(x))

MARKER_FUNCS = {
    "Mean": mean_marker,
    "Max": max_marker,
    "Min": min_marker,
    "Std": std_marker,
    # Add more as needed (e.g., median, percentiles, HRV, etc.)
}

def extract_markers(
    signals_dict,     # Dict: {signal_name: signal_object}, where signal_object has .data, .time, etc.
    markers,          # List[str]: marker names, e.g. ["Mean", "Std"]
    mode,             # str: "Whole signal", "By event/comment", "By window"
    filter_value,     # See below: varies by mode
    comment_intervals=None,  # Dict[str, Tuple[float, float]], optional: {label: (start, end)}
):
    """
    Extracts selected markers from given signals according to mode.

    Args:
        signals_dict: dict of {signal_name: signal_object}
        markers: list of marker names
        mode: extraction mode
        filter_value: varies:
            - Whole signal: None
            - By event/comment: comment label (str)
            - By window: (start (s), end (s), window_size (s))
        comment_intervals: Dict opcional con los intervalos de los comentarios.

    Returns:
        List of dicts (each dict = one row for the CSV)
    """
    results = []
    for sig_name, sig in signals_dict.items():
        time = sig.time  # 1D np.array
        data = sig.data  # 1D np.array
        if mode == "Whole signal":
            segments = [("Whole signal", time, data)]
        elif mode == "By event/comment":
            if comment_intervals is None or filter_value not in comment_intervals:
                continue
            t0, t1 = comment_intervals[filter_value]
            mask = (time >= t0) & (time <= t1)
            segments = [(filter_value, time[mask], data[mask])]
        elif mode == "By window":
            start, end, window_size = filter_value
            segments = []
            t0, t1 = float(start), float(end)
            num_windows = int(np.ceil((t1 - t0) / window_size))
            for i in range(num_windows):
                ws = t0 + i * window_size
                we = min(ws + window_size, t1)
                mask = (time >= ws) & (time < we)
                label = f"Window {i+1}: {ws:.1f}-{we:.1f}s"
                segments.append((label, time[mask], data[mask]))
        else:
            raise ValueError(f"Unknown mode: {mode}")

        for seg_label, seg_time, seg_data in segments:
            row = {
                "Signal": sig_name,
                "Segment": seg_label,
            }
            for mk in markers:
                func = MARKER_FUNCS.get(mk)
                if func is not None and seg_data.size > 0:
                    row[mk] = func(seg_data)
                else:
                    row[mk] = np.nan
            results.append(row)
    return results

import csv

def save_markers_to_csv(results, path):
    if not results:
        return
    fieldnames = list(results[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

# --- TEST SIMPLE ---
if __name__ == "__main__":
    # Aquí puedes testear con un mock
    class DummySignal:
        def __init__(self, name, data, time):
            self.data = data
            self.time = time

    # Ejemplo de señal de 0 a 100s
    t = np.arange(0, 100, 0.1)
    y = np.sin(t) + np.random.normal(0, 0.1, size=t.shape)
    sig = DummySignal("Test", y, t)
    signals_dict = {"Test": sig}
    markers = ["Mean", "Max", "Min", "Std"]

    # Whole signal
    res = extract_markers(signals_dict, markers, "Whole signal", None)
    print("Whole signal:", res)

    # By window (cada 10s)
    res = extract_markers(signals_dict, markers, "By window", (0, 100, 10))
    print("By window:", res)
    save_markers_to_csv(res, "test_markers.csv")
