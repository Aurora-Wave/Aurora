from dash import Input, Output, State, ctx, ALL, exceptions
import os
from utils.file_utils import save_temp_file

def register_stored_data_callbacks(app):

    @app.callback(
        Output("store_data", "data"),
        Input("upload_data", "contents"),
        Input({"type": "delete_button", "index": ALL}, "n_clicks"),
        State("upload_data", "filename"),
        State("store_data", "data"),
        prevent_initial_call=True
    )
    def manage_files(contents, delete_clicks, filenames, current_files):
        triggered = ctx.triggered_id

        if current_files is None:
            current_files = []

        if isinstance(triggered, dict) and triggered.get("type") == "delete_button":
            filename_to_remove = triggered["index"]
            updated = []
            for f in current_files:
                if f["filename"] != filename_to_remove:
                    updated.append(f)
                else:
                    try:
                        os.remove(f["path"])
                    except Exception as e:
                        print(f"Error deleting file: {e}")
            return updated

        if contents is None or filenames is None:
            raise exceptions.PreventUpdate

        if not isinstance(contents, list):
            contents, filenames = [contents], [filenames]

        new_files = []
        for c, f in zip(contents, filenames):
            path = save_temp_file(c, f)
            new_files.append({
                "filename": f,
                "path": path
            })

        return current_files + new_files
