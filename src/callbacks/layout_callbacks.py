from dash import html, dcc, Input, Output

def register_layout_callbacks(app):

    # Reacts to tab selection and updates the content container accordingly
    @app.callback(
        Output('tab-content', 'children'),
        Input('menu-tabs', 'value')
    )

    def render_tab_content(tab_value):
        
        if tab_value == 'tab-file':

            return html.Div([
                html.H4("Upload filesssss "),
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select Files')
                    ]),
                    style={
                        'width': '100%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px'
                    },
                    # Allow multiple files to be uploaded
                    multiple=True
                ),
                html.Div(id='file-list'),

            ])

        elif tab_value == 'tab-config':
            return html.Div([
                html.H4("Processing Config"),
                html.P("CONFIGURAR PROCESAMIENTO - CARGAR CONFIG")
            ])

        elif tab_value == 'tab-help':
            return html.Div([
                html.H4("Help"),
                html.P("Uso de la app")
            ])

        return html.Div("Pestaña no reconocida")
