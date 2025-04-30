from .layout_callbacks import register_layout_callbacks
from .upload_callbacks import register_upload_callbacks

def register_callbacks(app):

    #Layout callback
    register_layout_callbacks(app)

    #Upload files callback
    register_upload_callbacks(app)