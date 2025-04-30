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