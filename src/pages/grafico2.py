import dash
from dash import html, dcc
import numpy as np
from utils.plot import plot_signal
from utils.adicht_loader import get_trace_from_path
from utils.trace_api import get_ecg_full, get_r_peaks, get_ecg_comments
import plotly.graph_objs as go

dash.register_page(__name__, path="/grafico2")


def layout():
    return html.Div(
        [
            html.H2("ECG Procesado (Página 2)"),
            dcc.Graph(id="signal_plot_g2"),
            html.Hr(),
            html.Div(id="file_summary_g2"),
        ]
    )


def register_callbacks(app):
    @app.callback(
        [
            dash.dependencies.Output("signal_plot_g2", "figure"),
            dash.dependencies.Output("file_summary_g2", "children"),
        ],
        dash.dependencies.Input("store_data", "data"),
        prevent_initial_call=False,
    )
    def show_ecg_processed(data):
        try:
            if data and len(data) > 0:
                last_file = data[-1]
                path = last_file["path"]
                trace = get_trace_from_path(path)
                ecg_full = get_ecg_full(trace)
                r_peaks = get_r_peaks(trace)
                comentarios = get_ecg_comments(trace)
                t = np.arange(len(ecg_full)) / trace.Signal[trace.ECGSI].TSR
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=t, y=ecg_full, mode="lines", name="ECG"))
                fig.add_trace(
                    go.Scatter(
                        x=t[r_peaks],
                        y=ecg_full[r_peaks],
                        mode="markers",
                        name="R Peaks",
                        marker=dict(color="red", size=8),
                    )
                )
                # Anotar comentarios
                for c in comentarios:
                    if 0 <= c.Seconds < t[-1]:
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
                summary = [
                    html.Div(
                        f"Archivo: {last_file['name']}", style={"fontWeight": "bold"}
                    ),
                    html.Div(f"Canal: {trace.Signal[trace.ECGSI].Name}"),
                    html.Div(f"Picos R detectados: {len(r_peaks)}"),
                    html.Div(f"Comentarios: {len(comentarios)}"),
                ]
                return fig, summary
        except Exception as e:
            return go.Figure(), html.Div(f"Error: {e}", style={"color": "red"})
        # Placeholder si no hay datos
        t = np.linspace(0, 10, 500)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=t, y=np.sin(2 * np.pi * 1 * t), mode="lines", name="ECG")
        )
        fig.update_layout(title="ECG de ejemplo (Filtrado)")
        summary = html.Div("No se ha cargado ningún archivo.")
        return fig, summary
