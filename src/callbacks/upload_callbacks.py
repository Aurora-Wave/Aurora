# callbacks/upload_callbacks.py

from dash import Input, Output, State, html, ctx
import dash

def register_upload_callbacks(app):
    
    @app.callback(
        Output('stored-filenames', 'data'),
        Output('stored-contents','data'),
        Input('upload-data', 'filename'),
        State('upload-data','filename'),

        prevent_initial_call=True
    )

    def store_uploaded_files(contents, filenames):
        if contents is None or filenames is None:
            return dash.no_update, dash.no_update
        return filenames, contents  # Save both

    #Show list of files
    @app.callback(
        Output('file-list', 'children'),
        Input('stored-filenames', 'data')
    )

    def display_uploaded_files(filenames):
        if not filenames:
            return html.Div("No files uploaded yet.")
        return html.Ul([html.Li(f) for f in filenames])
