import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import scipy.signal
from scipy.interpolate import interp1d
import numpy as np

def plot_signal(df, title="Signal", x_label="Time (s)", y_label="Amplitude", signals=None):
    """
    Plots one or more signals on a single plot using a shared Time axis.

    Parameters:
        df (pd.DataFrame): Must contain a 'Time' column and one or more signal columns.
        title (str): Plot title.
        x_label (str): X-axis label.
        y_label (str): Y-axis label.
        signals (list or None): List of column names to plot. If None, all columns except 'Time' are plotted.

    Returns:
        plotly.graph_objects.Figure
    """
    fig = go.Figure()

    if df.empty or "Time" not in df.columns:
        return fig

    if signals is None:
        signals = [col for col in df.columns if col != "Time"]

    for signal in signals:
        if signal in df.columns:
            fig.add_trace(go.Scatter(
                x=df["Time"],
                y=df[signal],
                mode='lines',
                name=signal
            ))

    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template='plotly_white',
        margin=dict(l=40, r=20, t=40, b=40)
    )

    return fig

def plot_signal_grid(df, signals=None, title="Señales", x_label="Tiempo (s)"):
    """
    Plots multiple signals in stacked subplots with a shared Time axis.

    Parameters:
        df (pd.DataFrame): Must include 'Time' and one or more signal columns.
        signals (list or None): List of signal columns to plot. If None, all except 'Time' are used.
        title (str): Overall title of the figure.
        x_label (str): Label for the shared X-axis.

    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty or "Time" not in df.columns:
        return go.Figure()

    if signals is None:
        signals = [col for col in df.columns if col != "Time"]

    fig = make_subplots(
        rows=len(signals),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=signals
    )

    for i, signal in enumerate(signals, start=1):
        if signal in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Time"],
                    y=df[signal],
                    mode="lines",
                    name=signal
                ),
                row=i,
                col=1
            )

    fig.update_layout(
        height=300 * len(signals),
        title_text=title,
        showlegend=False,
        template="plotly_white",
        margin=dict(l=60, r=20, t=40, b=40),
        xaxis_title=x_label
    )

    return fig

def downsample_df(df, step=50):
    """Reduce el número de filas de un DataFrame tomando 1 de cada 'step'."""
    return df.iloc[::step, :].reset_index(drop=True)

def preprocess_ecg_signal(df, signal_col="ECG", fs=500, lowcut=0.5, highcut=40.0, interp_factor=2):
    """
    Aplica un filtro pasa banda y una interpolación a la señal ECG para mejorar su visualización.
    Parámetros:
        df (pd.DataFrame): Debe contener 'Time' y la columna de señal.
        signal_col (str): Nombre de la columna de la señal ECG.
        fs (float): Frecuencia de muestreo original (Hz).
        lowcut (float): Frecuencia de corte baja (Hz).
        highcut (float): Frecuencia de corte alta (Hz).
        interp_factor (int): Factor de interpolación.
    Devuelve:
        pd.DataFrame: DataFrame con la señal filtrada e interpolada.
    """
    if signal_col not in df.columns:
        return df
    # Filtro pasa banda Butterworth
    nyq = 0.5 * fs
    b, a = scipy.signal.butter(2, [lowcut / nyq, highcut / nyq], btype='band')
    filtered = scipy.signal.filtfilt(b, a, df[signal_col].values)
    # Interpolación
    t = df["Time"].values
    interp_t = np.linspace(t[0], t[-1], len(t) * interp_factor)
    interpolator = interp1d(t, filtered, kind='cubic')
    interp_signal = interpolator(interp_t)
    return pd.DataFrame({"Time": interp_t, signal_col: interp_signal})
