from dash import Input, Output, State, exceptions
import pandas as pd
from utils.plot import plot_signal
from utils.adicht_loader import load_channel_from_path

def register_plot_callbacks(app):
    # Callback para la página principal
    @app.callback(
        Output("signal_plot", "figure"),
        Input("btn_graficar", "n_clicks"),
        State("store_data", "data"),
        State("dropdown_canal", "value"),
        prevent_initial_call=True
    )
    def plot_selected_channel(n_clicks, data, selected_channel):
        if not data or not selected_channel:
            raise exceptions.PreventUpdate
        try:
            last_file = data[-1]
            path = last_file["path"]
            df = load_channel_from_path(path, label=selected_channel)
            return plot_signal(df, title=f"{selected_channel} - Último Registro")
        except Exception as e:
            return plot_signal(None, title=f"Error: {e}")
