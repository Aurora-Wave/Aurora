from dash import html, dcc
import pandas as pd
import numpy as np
from utils.plot import plot_signal

def create_layout():
    # Placeholder: señal de ejemplo
    t = np.linspace(0, 10, 500)
    df_placeholder = pd.DataFrame({
        "Time": t,
        "ECG": np.sin(2 * np.pi * 1 * t)
    })

    return html.Div([
        # === NavBar simple ===
        html.Nav(
            children=[
                html.Button("Load", id="nav_load", style={"margin": "0 10px"}),
                html.Button("Save", id="nav_save", style={"margin": "0 10px"}),
                html.Button("Export", id="nav_export", style={"margin": "0 10px"}),
                html.Button("Plots", id="nav_plots", style={"margin": "0 10px"}),
                html.Button("Configuration", id="nav_config", style={"margin": "0 10px"}),
                html.Button("Help", id="nav_help", style={"margin": "0 10px"}),
                html.Button("Bugs Report", id="nav_bugs", style={"margin": "0 10px"}),
                html.Button("Exit", id="nav_exit", style={"margin": "0 10px"}),
            ],
            style={
                "display": "flex",
                "justifyContent": "center",
                "alignItems": "center",
                "background": "#f8f9fa",
                "padding": "10px",
                "borderBottom": "1px solid #ddd"
            }
        ),

        html.Hr(),

        # === Almacenamiento de archivos en sesión ===
        dcc.Store(id='store_data', storage_type='session'),

        # === Modal para subir archivos (nativo) ===
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

        # === Controles para graficar ===
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

        # === Gráfico ===
        dcc.Graph(
            id="signal_plot",
            figure=plot_signal(df_placeholder, title="Señal de ejemplo")
        ),

        html.Hr(),

        # === Tabla resumen (opcional) ===
        html.Div(id="file_summary")
    ])
