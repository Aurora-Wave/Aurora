from dash import Input, Output, State,html
import dash_bootstrap_components as dbc



def register_upload_button(app):
    
    '''Handle the modal layout for file upload.
    This function is called when the user clicks the "Load" button in the navbar.
    '''

    @app.callback(
        Output("upload_modal", "is_open"),
        Input("dropdown_load", "n_clicks"),
        Input("close_modal", "n_clicks"),
        State("upload_modal", "is_open"),
        prevent_initial_call=True,

    )
    def toggle_modal(load_click, close_click, is_open):
        if load_click or close_click:
            return not is_open
        return is_open


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
                    dbc.Button("❌",
                        id={"type": "delete_button", "index": file["filename"]},
                        color="danger", size="sm", n_clicks=0
                    )
                )
            ]) for file in files
        ]

        return dbc.Table(
            [table_header, html.Tbody(table_rows)],
            bordered=True,
            striped=True,
            hover=True,
            size="sm"
        )
