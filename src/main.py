from dash import Dash
import dash_bootstrap_components as dbc
from layout_p1 import create_layout
from callbacks import register_callbacks

# Create Dash app
app = Dash(__name__,external_stylesheets=[dbc.themes.BOOTSTRAP])

# Set layout
app.layout = create_layout()

# Register all callbacks
register_callbacks(app)

if __name__ == '__main__':
    # Set debug=False to allow Nuitka compilation
    app.run(debug=True, port=8050)
    #Ctrl +C to stop the server	