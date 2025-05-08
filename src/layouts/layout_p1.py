from dash import html, dcc
import dash_bootstrap_components as dbc
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

    return dbc.Container([

        # === NavBar ===
        dbc.Nav([
            dbc.DropdownMenu([
                dbc.DropdownMenuItem("Load", id='dropdown_load'),
                dbc.DropdownMenuItem("Save", id='dropdown_save'),
                dbc.DropdownMenuItem("Export", id='dropdown_export'),
            ], label="Files", nav=True),
            dbc.NavItem(dbc.NavLink("Plots", href="#")),
            dbc.NavItem(dbc.NavLink("Configuration", href="#")),
            dbc.NavItem(dbc.NavLink("Help", href="#")),
            dbc.NavItem(dbc.NavLink("Bugs Report", href="#")),
            dbc.NavItem(dbc.NavLink("Exit", href="#"))
        ], justified=True, className="justify-content-center"),

        html.Hr(),

        # === Almacenamiento de archivos en sesión ===
        dcc.Store(id='store_data', storage_type='session'),

        # === Modal para subir archivos ===
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Upload File")),
            dbc.ModalBody(
                dcc.Upload(
                    id='upload_data',
                    children=dbc.Button("Select File", color="primary"),
                    multiple=True
                )
            ),
            dbc.ModalFooter(
                dbc.Button("Close", id="close_modal", className="ms-auto", n_clicks=0)
            )
        ], id="upload_modal", is_open=False),

        html.Hr(),

        # === Controles para graficar ===
        dbc.Row([
            dbc.Col([
                dcc.Dropdown(
                    id="dropdown_canal",
                    placeholder="Select a signal channel",
                    options=[
                        {"label": ch, "value": ch}
                        for ch in ["ECG", "HR", "FBP", "Valsalva", "CO", "SVR", "ETCO2", "SPO2"]
                    ]
                )
            ], width=6),
            dbc.Col([
                dbc.Button("Graficar", id="btn_graficar", color="success")
            ], width=2)
        ]),
        html.Br(),

        # === Gráfico ===
        dbc.Row([
            dbc.Col(
                dcc.Graph(
                    id="signal_plot",
                    figure=plot_signal(df_placeholder, title="Señal de ejemplo")
                ),
                width=12
            )
        ]),

        html.Hr(),

        # === Tabla resumen (opcional) ===
        dbc.Row([
            dbc.Col(
                html.Div(id="file_summary"),
                width=12
            )
        ])
    ])
