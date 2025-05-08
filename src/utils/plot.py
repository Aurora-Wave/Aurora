import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

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
