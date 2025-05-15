from .layout_callbacks import register_upload_button, register_file_summary_callbacks
from .stored_data_callbacks import register_stored_data_callbacks
from .plot_callbacks import register_plot_callbacks

def register_callbacks(app):
    register_upload_button(app)
    register_stored_data_callbacks(app)
    register_file_summary_callbacks(app)
    register_plot_callbacks(app)

