from dash import Dash, html, dcc
from layouts.layout_p1 import create_layout
from callbacks import register_callbacks
import dash

# Crear la app Dash con soporte multipage y suppress_callback_exceptions
app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

# Layout principal con barra de navegación y contenedor de páginas
dcc_store = dcc.Store(id='store_data', storage_type='session')
dcc_plot_state = dcc.Store(id='store_plot_state', storage_type='session')
app.layout = html.Div([
    dcc_store,  # Store global para archivos
    dcc_plot_state,  # Store global para el estado del gráfico
    html.Nav([
        dcc.Link("Inicio", href="/", style={"margin": "0 10px"}),
        dcc.Link("Nuevo Gráfico", href="/grafico2", style={"margin": "0 10px"}),
    ], style={"display": "flex", "justifyContent": "center", "padding": "10px"}),
    dash.page_container
])

# Registrar callbacks globales
register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True, port=8050)