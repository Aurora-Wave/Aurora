from dash import html, dcc
import dash_bootstrap_components as dbc

def create_layout():
    return dbc.Container([
        
        # NavBar
        dbc.Nav([
            dbc.DropdownMenu([
                dbc.DropdownMenuItem("Load", id='dropdown_load'),
                dbc.DropdownMenuItem("Save", id='dropdown_save'),
                dbc.DropdownMenuItem("Export", id='dropdown_export'),
            ],
                label="Files",
                nav=True
            ),
            dbc.NavItem(dbc.NavLink("Plots", href="#")),
            dbc.NavItem(dbc.NavLink("Configuration", href="#")),
            dbc.NavItem(dbc.NavLink("Help", href="#")),
            dbc.NavItem(dbc.NavLink("Bugs Report", href="#")),
            dbc.NavItem(dbc.NavLink("Exit", href="#"))
        ],
            justified=True,
            className="justify-content-center"
        ),

        # Hidden modal for file upload
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
                dbc.Button(
                    "Close", 
                    id="close_modal", 
                    className="ms-auto", 
                    n_clicks=0
                )
            )
        ],
            id="upload_modal",
            is_open=False
        ),

        # Data store
        dcc.Store(id='store_data', storage_type='session'),

        # File summary table
        dbc.Container([
            dbc.Row(
                dbc.Col(
                    html.Div("golaa",id='file_summary'),
                    width=12
                )
            )
        ])
    ])
