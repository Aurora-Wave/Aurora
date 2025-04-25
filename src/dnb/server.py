from multiprocessing import Condition

import os
import pandas as pd
import plotly.express as px
import setproctitle
from dash import Dash, dcc, html, dash_table, Input, Output, State, callback
import argparse

import adi
import base64
import datetime
import io

from dnb.domino import terminate_when_parent_process_dies




def start_dash(host: str, port: int, server_is_started: Condition, debug: bool = False):
    # Set the process title.
    setproctitle.setproctitle('dnb-dash')


    # The following is the minimal sample code from dash itself:
    # https://dash.plotly.com/minimal-app

    def save_file(contents, filename):
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        upload_folder = 'uploaded_files'  # Carpeta donde se guardarán los archivos
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        file_path = os.path.join(upload_folder, filename)
        with open(file_path, 'wb') as f:
            f.write(decoded)
        return file_path


    external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

    app = Dash(__name__, external_stylesheets=external_stylesheets)

    app.layout = html.Div([
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            style={
                'width': '100%',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px'
            },
            # Allow multiple files to be uploaded
            multiple=True
        ),
        html.Div(id='output-data-upload'),
    ])

    def parse_contents(contents, filename, date):
        content_type, content_string = contents.split(',')

        decoded = base64.b64decode(content_string)
        try:
            if 'csv' in filename:
                # Assume that the user uploaded a CSV file
                df = pd.read_csv(
                    io.StringIO(decoded.decode('utf-8')))
            elif 'xls' in filename:
                # Assume that the user uploaded an excel file
                df = pd.read_excel(io.BytesIO(decoded))
            elif 'adicht' in filename:
                # Assume that the user uploaded an adicht file
                f = adi.read_file(save_file(contents, filename))
                channel_id = 3
                record_id = 2
                data = f.channels[channel_id-1].get_data(record_id)
                df = pd.DataFrame(data)
                
                
                
                
        except Exception as e:
            print(e)
            return html.Div([
                'There was an error processing this file.'
            ])

        return html.Div([
            html.H5(filename),
            html.H6(datetime.datetime.fromtimestamp(date)),

            dash_table.DataTable(
                df.to_dict('records'),
                [{'name': i, 'id': i} for i in df.columns]
            ),

            html.Hr(),  # horizontal line

            # For debugging, display the raw contents provided by the web browser
            html.Div('Raw Content'),
            html.Pre(contents[0:200] + '...', style={
                'whiteSpace': 'pre-wrap',
                'wordBreak': 'break-all'
            })
        ])



    @callback(Output('output-data-upload', 'children'),
                Input('upload-data', 'contents'),
                State('upload-data', 'filename'),
                State('upload-data', 'last_modified'))


    def update_output_with_graph(list_of_contents, list_of_names, list_of_dates):
        if list_of_contents is not None:
            children = []
            for c, n, d in zip(list_of_contents, list_of_names, list_of_dates):
                content_type, content_string = c.split(',')
                decoded = base64.b64decode(content_string)
                try:
                    if 'csv' in n:
                        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
                    elif 'xls' in n:
                        df = pd.read_excel(io.BytesIO(decoded))
                    elif 'adicht' in n:
                        f = adi.read_file(save_file(c, n))
                        channel_id = 3
                        record_id = 2
                        data = f.channels[channel_id-1].get_data(record_id)
                        
                        df = pd.DataFrame({'Time': range(len(data)), 'Data': data})
                    else:
                        continue
                    
                except Exception as e:
                    print(e)
                    children.append(html.Div(['There was an error processing this file.']))
                    continue

                graph = dcc.Graph(
                    figure={
                        'data': [
                            {'x': df[df.columns[0]], 'y': df[df.columns[1]], 'type': 'line', 'name': 'Data'}
                        ],
                        'layout': {
                            'title': 'Uploaded File Graph'
                        }
                    }
                )

                children.append(html.Div([
                    
                    graph,
                    html.Div('Raw Content'),
                    html.Pre(c[0:200] + '...', style={
                        'whiteSpace': 'pre-wrap',
                        'wordBreak': 'break-all'
                    })
                ]))
            return children

    # When the parent dies, follow along.    
    if not debug:
        terminate_when_parent_process_dies()
        with server_is_started:
            server_is_started.notify()
        app.run(debug=False, host=host, port=port)
    else:
        app.run(debug=True, host=host, port=port)

    # debug cannot be True right now with nuitka: https://github.com/Nuitka/Nuitka/issues/2953


if __name__ == '__main__':
    port = int(os.getenv("PORT", "8050"))
    host = os.getenv("HOST", "127.0.0.1")

    server_is_started = None
    
    start_dash(host, port, server_is_started, True)