from .layout_callbacks import register_upload_button, register_file_summary_callbacks
from .load_data_callbacks import register_stored_data_callbacks

def register_callbacks(app):


    #Upload button callback 
    register_upload_button(app)

    # File upload and delete callbacks
    register_stored_data_callbacks(app)

    # File summary table callbacks
    register_file_summary_callbacks(app)
