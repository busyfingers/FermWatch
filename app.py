# -*- coding: utf-8 -*-
import config
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import requests
import pandas as pd
import datetime as dt
import json

# Squelch warning about unverified SSL cert for HTTPS - we know the API is OK!
requests.packages.urllib3.disable_warnings()
apiUrl = config.api["url"]
token = config.api["token"]
headers = {"Authorization": "Bearer " + token}

# Show today's values by default
# To-date is tomorrow because the timestamp is 00:00:00
graph_date_from = dt.date.today() - dt.timedelta(days=1)
graph_date_to = dt.date.today() + dt.timedelta(days=1)
graph_update_interval = 1 * 60 * 1000  # 1 minutes
date_update_interval = 60 * 60 * 1000  # 60 minutes
selected_batch = ""
fetched_batches = {}


def fetchBatches():
    req = requests.get(f"{apiUrl}/batchdata", headers=headers, verify=False)
    return json.loads(req.text)


def fetchData(date_from, date_to, batch_id):
    params = {}

    if batch_id:
        params["batchId"] = batch_id
    else:
        params["from"] = date_from
        params["to"] = date_to

    req = requests.get(f"{apiUrl}/temperature",
                       headers=headers, params=params, verify=False)

    return pd.read_json(req.text)


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets, meta_tags=[
    {"name": "viewport", "content": "width=device-width, initial-scale=1"}
])

colors = {
    'background': '#EEEEEE',
    'text': '#0D0D0D'
}

app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='Fermentation watcher',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    dcc.DatePickerSingle(
        id='date-from',
        date=graph_date_from,
        display_format='YYYY-MM-DD',
        style={
            'horizontal-align': 'center'
        }
    ),
    dcc.DatePickerSingle(
        id='date-to',
        date=graph_date_to,
        display_format='YYYY-MM-DD',
        style={
            'horizontal-align': 'center'
        }
    ),
    dcc.Dropdown(
        id='batch-selection',
        value=''
    ),
    html.P(id='selected-batch-info',
           style={'padding': '0.5rem 1rem 1rem 1rem'}),
    dcc.Graph(id='main-graph'),
    dcc.Interval(
        id='interval-component',
        interval=graph_update_interval,
        n_intervals=0
    ),
    dcc.Interval(
        id='date-update',
        interval=date_update_interval,
        n_intervals=0
    )
])

plot_layout = {
    'plot_bgcolor': colors['background'],
    'paper_bgcolor': colors['background'],
    'font': {
        'color': colors['text']
    },
    'title': 'Temperature over time',
    'xaxis': {'title': 'Measured at'},
    'yaxis': {'title': 'Temperature (C)'}
}


@app.callback(Output(component_id='date-from', component_property='date'), [Input(component_id='date-update', component_property='n_intervals')])
def refreshFromDate(n_intervals):
    if selected_batch:
        return None
    else:
        return dt.date.today() - dt.timedelta(days=1)


@app.callback(Output(component_id='date-to', component_property='date'), [Input(component_id='date-update', component_property='n_intervals')])
def refreshToDate(n_intervals):
    if selected_batch:
        return None
    else:
        return dt.date.today() + dt.timedelta(days=1)


@app.callback([Output(component_id='date-from', component_property='disabled'),
               Output(component_id='date-to', component_property='disabled')],
              [Input(component_id='batch-selection', component_property='value')])
def toggleDatePickers(batch_id):
    if batch_id:
        return True, True
    else:
        return False, False


@app.callback(Output(component_id='selected-batch-info', component_property='children'),
              [Input(component_id='batch-selection', component_property='value')])
def setSelectedBatch(batch_id):
    selected_batch = batch_id

    if not batch_id:
        return ""
    else:
        fermentation_end = fetched_batches[batch_id][
            'FermentationEnd'].split('T')[0] if 'FermentationEnd' in fetched_batches[batch_id] else ""
        return f"Fermentation start: {fetched_batches[batch_id]['FermentationStart'].split('T')[0]}, fermentation end: {fermentation_end}"

@app.callback(Output(component_id='batch-selection', component_property='options'),
              [Input(component_id='date-update', component_property='n_intervals')])
def setBatches(n_intervals):
    # headers = {"Authorization": "Bearer " + token}
    # req = requests.get(f"{apiUrl}/batchdata", headers=headers, verify=False)
    # batches = json.loads(req.text)
    batches = fetchBatches()
    options = []

    for batch in batches:
        fetched_batches[batch['Id']] = batch
        options.append(
            {'label': f"Batch#{batch['BatchNo']} - {batch['RecipeName']}", 'value': batch['Id']})

    return options


@app.callback(
    Output(component_id='main-graph', component_property='figure'),
    [Input(component_id='date-from', component_property='date'),
     Input(component_id='date-to', component_property='date'),
     Input(component_id='batch-selection', component_property='value'),
     Input(component_id='interval-component', component_property='n_intervals')])
def reFetchData(date_from, date_to, batch_id, n_intervals):
    df = fetchData(date_from, date_to, batch_id)

    if df.empty:
        return {
            'data': [
                go.Scatter(
                    x=[],
                    y=[],
                    mode='lines+markers',
                    name='temp_vs_time'
                )
            ],
            'layout': plot_layout
        }

    graph_data = []

    bucket = df[df.Location.str.contains('Bucket')]
    ambient = df[df.Location.str.contains('Ambient')]

    if not bucket.empty:
        graph_data.append(getScatterPlot(bucket, "Bucket"))

    if not ambient.empty:
        graph_data.append(getScatterPlot(ambient, "Ambient"))

    return {
        'data': graph_data,
        'layout': plot_layout
    }


def getScatterPlot(dataframe, name):
    return go.Scatter(
        x=dataframe["MeasuredAt"],
        y=dataframe["Value"],
        mode="lines+markers",
        name=name)


if __name__ == '__main__':
    app.run_server(debug=False, host=config.server["listen_on"])
