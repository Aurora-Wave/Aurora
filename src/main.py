from dash import Dash
from layout import create_layout
from callbacks import register_callbacks

# Create Dash app
app = Dash(__name__)

# Set layout
app.layout = create_layout()

# Register all callbacks
register_callbacks(app)
