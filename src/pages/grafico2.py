import dash
from dash import html, dcc
import pandas as pd
import numpy as np
from utils.plot import plot_signal, preprocess_ecg_signal
from utils.adicht_loader import load_channel_from_path

dash.register_page(__name__, path="/grafico2")

def layout():
    return html.Div([
        html.H2("ECG Procesado (Página 2)"),
        dcc.Graph(id="signal_plot_g2"),
        html.Hr(),
        html.Div(id="file_summary_g2")
    ])

def register_callbacks(app):
    @app.callback(
        [dash.dependencies.Output("signal_plot_g2", "figure"),
         dash.dependencies.Output("file_summary_g2", "children")],
        dash.dependencies.Input("store_data", "data"),
        prevent_initial_call=False
    )
    def show_ecg_processed(data):
        try:
            if data and len(data) > 0:
                last_file = data[-1]
                path = last_file["path"]
                # Mostrar canales disponibles
                from utils.adicht_loader import get_channel_labels_from_path
                try:
                    available_channels = get_channel_labels_from_path(path)
                except Exception as e:
                    available_channels = [f"Error al leer canales: {e}"]
                # Intentar cargar ECG
                df = load_channel_from_path(path, label="ECG")
                if df is None or df.empty or ("ECG" not in df.columns):
                    fig = plot_signal(pd.DataFrame(), title="Canal 'ECG' no encontrado o vacío")
                    summary = [
                        html.Div(f"Archivo: {last_file['name']}", style={"fontWeight": "bold"}),
                        html.Div(f"Canales disponibles: {available_channels}"),
                        html.Div("No se encontró el canal 'ECG' o está vacío.", style={"color": "red"})
                    ]
                    return fig, summary
                df_proc = preprocess_ecg_signal(df, signal_col="ECG", fs=500)
                fig = plot_signal(df_proc, title="ECG - Último Registro (Filtrado)")
                summary = [
                    html.Div(f"Archivo: {last_file['name']}", style={"fontWeight": "bold"}),
                    html.Div(f"Canales disponibles: {available_channels}"),
                    html.Div("Canal 'ECG' procesado correctamente.", style={"color": "green"})
                ]
                return fig, summary
        except Exception as e:
            return plot_signal(pd.DataFrame(), title=f"Error: {e}"), html.Div(f"Error: {e}", style={"color": "red"})
        # Placeholder si no hay datos
        t = np.linspace(0, 10, 500)
        df_placeholder = pd.DataFrame({"Time": t, "ECG": np.sin(2 * np.pi * 1 * t)})
        df_proc = preprocess_ecg_signal(df_placeholder, signal_col="ECG", fs=500)
        fig = plot_signal(df_proc, title="ECG de ejemplo (Filtrado)")
        summary = html.Div("No se ha cargado ningún archivo.")
        return fig, summary
