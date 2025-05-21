from dash import Input, Output, State, exceptions
import pandas as pd
from utils.plot import plot_signal
from utils.adicht_loader import get_trace_from_path
from utils.trace_api import get_ecg_full, get_r_peaks, get_ecg_comments
import plotly.graph_objs as go
import numpy as np


def register_plot_callbacks(app):
    # Callback para la página principal
    @app.callback(
        Output("signal_plot", "figure"),
        Input("btn_graficar", "n_clicks"),
        State("store_data", "data"),
        State("dropdown_canal", "value"),
        prevent_initial_call=True,
    )
    def plot_selected_channel(n_clicks, data, selected_channel):
        if not data or not selected_channel:
            raise exceptions.PreventUpdate
        try:
            last_file = data[-1]
            path = last_file["path"]
            trace = get_trace_from_path(path)
            # Buscar canal solicitado en Trace
            canal_idx = None
            for i, sig in enumerate(trace.Signal):
                if sig.Name.strip().lower() == selected_channel.strip().lower():
                    canal_idx = i
                    break
            if canal_idx is None:
                raise Exception(
                    f"Canal '{selected_channel}' no encontrado en el archivo."
                )
            sig = trace.Signal[canal_idx]
            t = (
                np.arange(len(sig.ProData)) / sig.TSR
                if sig.TSR
                else np.arange(len(sig.ProData))
            )
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=t, y=sig.ProData, mode="lines", name=sig.Name))
            # Si es ECG, agregar picos R y comentarios
            if selected_channel.strip().upper() == "ECG":
                ecg_full = get_ecg_full(trace)
                r_peaks = get_r_peaks(trace)
                comentarios = get_ecg_comments(trace)
                t_full = (
                    np.arange(len(ecg_full)) / sig.TSR
                    if sig.TSR
                    else np.arange(len(ecg_full))
                )
                fig.add_trace(
                    go.Scatter(
                        x=t_full[r_peaks],
                        y=ecg_full[r_peaks],
                        mode="markers",
                        name="R Peaks",
                        marker=dict(color="red", size=8),
                    )
                )
                for c in comentarios:
                    if 0 <= c.Seconds < t_full[-1]:
                        fig.add_vline(
                            x=c.Seconds,
                            line_dash="dash",
                            line_color="purple",
                            opacity=0.5,
                        )
                        fig.add_annotation(
                            x=c.Seconds,
                            y=max(ecg_full) * 0.8,
                            text=c.Comment[:20],
                            showarrow=False,
                            yanchor="top",
                            font=dict(color="purple", size=10),
                        )
                fig.update_layout(
                    title="ECG con Picos R y Comentarios",
                    xaxis_title="Tiempo (s)",
                    yaxis_title="Amplitud",
                    template="plotly_white",
                )
            else:
                fig.update_layout(
                    title=f"{sig.Name} - Último Registro",
                    xaxis_title="Tiempo (s)",
                    yaxis_title="Amplitud",
                    template="plotly_white",
                )
            return fig
        except Exception as e:
            return go.Figure()
