import base64,io,os,adi
import pandas as pd

def parse_file(contents, filename):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        if filename.endswith(".csv"):
            
            #pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            #return {"filename": filename, "contents": contents, "n_channels": 1, "n_records": 1}
            pass
        
        elif filename.endswith(".xls") or filename.endswith(".xlsx"):
            
            #pd.read_excel(io.BytesIO(decoded))
            #return {"filename": filename, "contents": contents, "n_channels": 1, "n_records": 1, "last_modified": last_modified}
            pass
        elif filename.endswith(".adicht"):
            
            path = save_file(contents, filename)
            f = adi.read_file(path)
            return {"filename": filename, "contents": contents, "n_channels": len(f.channels), "n_records": f.channels[0].n_records}

    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        return None


def save_file(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    #Store ID
    upload_folder = 'uploaded_files'
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, 'wb') as f:
        f.write(decoded)
    return file_path

