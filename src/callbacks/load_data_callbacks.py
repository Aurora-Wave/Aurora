from dash import Input, Output, State, ctx, ALL, exceptions

def register_stored_data_callbacks(app):
    
    @app.callback(
        Output("store_data", "data"),
        Input("upload_data", "contents"),
        Input({"type": "delete_button", "index": ALL}, "n_clicks"),
        State("upload_data", "filename"),
        State("store_data", "data"),
        prevent_initial_call=True
    )


    #FIXME: This callback is not working as expected. Duplicate files, etc. 
    def manage_files(contents, delete_clicks, filenames, current_files):
        '''
        contents: list of base64-encoded strings (file data)
        filenames: list of file names associated with the uploads
        current_files: list of dicts with keys: "filename", "contents"
        '''

        triggered = ctx.triggered_id

        if current_files is None:
            current_files = []

        # Remove file if a delete button was clicked
        if isinstance(triggered, dict) and triggered.get("type") == "delete_button":
            filename_to_remove = triggered["index"]
            return [f for f in current_files if f["filename"] != filename_to_remove]

        # If no file uploaded, skip update
        if contents is None or filenames is None:
            raise exceptions.PreventUpdate

        # Normalize to list if only one file was uploaded
        if not isinstance(contents, list):
            contents, filenames = [contents], [filenames]

        new_files = []

        for c, f in zip(contents, filenames):
            # Store both filename and raw base64 content
            new_files.append({
                "filename": f,
                "contents": c
            })
        return current_files + new_files
