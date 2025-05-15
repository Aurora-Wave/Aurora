from dash import Input, Output, State, html, ctx
import dash_bootstrap_components as dbc


def register_upload_button(app):
    '''Handle the modal layout for file upload.
    This function is called when the user clicks the "Load" button in the navbar.
    '''

    @app.callback(
        Output("upload_modal", "style"),
        [Input("nav_load", "n_clicks"),
         Input("close_modal", "n_clicks")],
        State("upload_modal", "style"),
        prevent_initial_call=True
    )
    def toggle_modal(load_click, close_click, current_style):
        trigger = ctx.triggered_id
        if trigger == "nav_load":
            return {"display": "flex", "position": "fixed", "top": 0, "left": 0, "width": "100%", "height": "100%",
                    "background": "rgba(0,0,0,0.5)", "justifyContent": "center", "alignItems": "center", "zIndex": 1000}
        elif trigger == "close_modal":
            return {"display": "none"}
        return current_style


def register_file_summary_callbacks(app):
    @app.callback(
        Output("file_summary", "children"),
        Input("store_data", "data"),
        prevent_initial_call=True
    )
    def render_file_table(files):
        if not files:
            return html.P("No files uploaded.")

        table_header = html.Thead(html.Tr([
            html.Th("File Name"),
            html.Th("Delete")
        ]))

        table_rows = [
            html.Tr([
                html.Td(file["filename"]),
                html.Td(
                    html.Button(
                        "❌",
                        id={"type": "delete_button", "index": file["filename"]},
                        n_clicks=0,
                        style={
                            "background": "#dc3545",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "4px",
                            "padding": "2px 8px",
                            "cursor": "pointer"
                        }
                    )
                )
            ]) for file in files
        ]

        return html.Table(
            [table_header, html.Tbody(table_rows)],
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "marginTop": "10px",
                "border": "1px solid #dee2e6"
            }
        )
