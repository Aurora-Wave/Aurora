import dash
from dash import html, dcc, Input, Output, State, exceptions
import pandas as pd
import numpy as np
from utils.plot import plot_signal
from utils.adicht_loader import load_channel_from_path

dash.register_page(__name__, path="/")

def layout():
    # Placeholder: señal de ejemplo
    t = np.linspace(0, 10, 500)
    df_placeholder = pd.DataFrame({
        "Time": t,
        "ECG": np.sin(2 * np.pi * 1 * t)
    })
    return html.Div([
        # Barra de acciones (no navegación de páginas)
        html.Nav([
            html.Button("Load", id="nav_load", style={"margin": "0 10px"}),
            html.Button("Export", id="nav_export", style={"margin": "0 10px"}),
            dcc.Link("Nuevo Gráfico", href="/grafico2", style={"margin": "0 10px", "textDecoration": "none", "color": "#007bff", "background": "none", "border": "none", "padding": "6px 12px", "cursor": "pointer"}),
        ], style={"display": "flex", "justifyContent": "center", "alignItems": "center", "background": "#f8f9fa", "padding": "10px", "borderBottom": "1px solid #ddd"}),
        html.Hr(),
        # Modal para subir archivos
        html.Div(
            id="upload_modal",
            style={"display": "none", "position": "fixed", "top": 0, "left": 0, "width": "100%", "height": "100%",
                   "background": "rgba(0,0,0,0.5)", "justifyContent": "center", "alignItems": "center", "zIndex": 1000},
            children=[
                html.Div(
                    style={"background": "#fff", "padding": "20px", "borderRadius": "8px", "margin": "auto", "width": "350px"},
                    children=[
                        html.H2("Upload File"),
                        dcc.Upload(
                            id='upload_data',
                            children=html.Button("Select File", style={"marginTop": "10px"}),
                            multiple=True
                        ),
                        html.Div(id="upload_status", style={"marginTop": "10px"}),
                        html.Button("Close", id="close_modal", n_clicks=0, style={"marginTop": "10px"})
                    ]
                )
            ]
        ),
        html.Hr(),
        html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "20px"},
            children=[
                dcc.Dropdown(
                    id="dropdown_canal",
                    placeholder="Select a signal channel",
                    options=[
                        {"label": ch, "value": ch}
                        for ch in ["ECG", "HR", "FBP", "Valsalva", "CO", "SVR", "ETCO2", "SPO2"]
                    ],
                    style={"width": "300px"}
                ),
                html.Button("Graficar", id="btn_graficar", style={"background": "#28a745", "color": "white", "border": "none", "padding": "8px 16px", "borderRadius": "4px"})
            ]
        ),
        html.Br(),
        dcc.Graph(
            id="signal_plot",
            # El valor inicial se setea vía callback para restaurar el estado
        ),
        html.Hr(),
        html.Div(id="file_summary")
    ])

# Callbacks propios de la página home
def register_callbacks(app):
    # Modal de carga
    @app.callback(
        Output("upload_modal", "style"),
        [Input("nav_load", "n_clicks"),
         Input("close_modal", "n_clicks")],
        State("upload_modal", "style"),
        prevent_initial_call=True
    )
    def toggle_modal(load_click, close_click, current_style):
        ctx = dash.callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        if trigger == "nav_load":
            return {"display": "flex", "position": "fixed", "top": 0, "left": 0, "width": "100%", "height": "100%",
                    "background": "rgba(0,0,0,0.5)", "justifyContent": "center", "alignItems": "center", "zIndex": 1000}
        elif trigger == "close_modal":
            return {"display": "none"}
        return current_style

    # Callback para restaurar el gráfico y canal al cargar la página
    @app.callback(
        Output("signal_plot", "figure"),
        Output("dropdown_canal", "value"),
        Input("store_plot_state", "data"),
        prevent_initial_call=False
    )
    def restore_plot_state(plot_state):
        # Si hay estado guardado, restaurar figura y canal
        if plot_state and plot_state.get("page") == "home":
            return plot_state.get("figure"), plot_state.get("canal")
        # Si no, mostrar placeholder seguro
        t = np.linspace(0, 10, 500)
        df_placeholder = pd.DataFrame({"Time": t, "ECG": np.sin(2 * np.pi * 1 * t)})
        return plot_signal(df_placeholder, title="Señal de ejemplo"), None

    # Callback para graficar y guardar el estado
    @app.callback(
        Output("signal_plot", "figure"),
        Output("store_plot_state", "data"),
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
            fig = plot_signal(df, title=f"{selected_channel} - Último Registro")
            # Guardar estado
            return fig, {"page": "home", "canal": selected_channel, "figure": fig}
        except Exception as e:
            return plot_signal(None, title=f"Error: {e}"), dash.no_update
