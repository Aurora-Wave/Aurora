from dash import html, dcc

#Create main layout
def create_layout():

    return html.Div([
        # Horizontal tab navigation
        dcc.Tabs(
            id='menu-tabs',
            value='tab-file',  # Default selected tab
            children=[
                dcc.Tab(label = 'Files',             value = 'tab-file'),
                dcc.Tab(label = 'Plots',             value = 'tab-plot'),
                dcc.Tab(label = 'Configuration',     value = 'tab-config'),
                dcc.Tab(label = 'Help',              value = 'tab-help'),
            ],
            style={'margin': '5px', 'text-align': 'left'}
        ),

        # Content area that will be updated by callback
        dcc.Store(id = 'stored-filenames'),
        dcc.Store(id = 'stored-contents'),
        html.Div(id  = 'tab-content')
    ])
