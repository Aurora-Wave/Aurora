def load_from_npz(file_path, channel_key):
    npz_data = np.load(file_path, allow_pickle=True)
    arr = npz_data[channel_key]
    name, fs, unit = arr[0], float(arr[1]), arr[2]
    data = arr[3:].astype(float)
    time = np.arange(len(data)) / fs
    return name, fs, unit, time, data
