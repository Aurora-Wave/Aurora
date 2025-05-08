import base64
import os
import tempfile

def save_temp_file(contents, filename):
    """
    Saves a base64-encoded file to a temporary location on disk.

    Parameters:
        contents (str): Base64-encoded content from dcc.Upload.
        filename (str): Original filename uploaded.

    Returns:
        str: Absolute path to the saved temporary file.
    """
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(tmp_path, 'wb') as f:
        f.write(decoded)

    return tmp_path
