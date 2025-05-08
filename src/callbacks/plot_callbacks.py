from dash import Input, Output, State, exceptions
import pandas as pd
from utils.plot import plot_signal
from utils.adicht_loader import load_channel_from_path

def register_plot_callbacks(app):

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

            ##FIXME Solo plotea el ultimo archivo

            last_file = data[-1]
            path = last_file["path"]

            df = load_channel_from_path(path, label=selected_channel)
            return plot_signal(df, title=f"{selected_channel} - Último Registro")
        
        except Exception as e:
            print(f"Error plotting channel {selected_channel}: {e}")
            return plot_signal(pd.DataFrame({'Time': [], selected_channel: []}), title="Error al cargar canal")
