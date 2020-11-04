# -*- coding: utf-8 -*-
from numpy.core.multiarray import empty_like
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

# https://stackoverflow.com/questions/20625582/how-to-deal-with-settingwithcopywarning-in-pandas
pd.options.mode.chained_assignment = None  # default='warn'

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


def fetch_fermentation_profile(batch_id):
    if not batch_id:
        return []

    params = {"batchId": batch_id}
    req = requests.get(f"{apiUrl}/fermentationProfile",
                       headers=headers, params=params, verify=False)

    return pd.read_json(req.text)


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

app.title = 'Fermentation Watcher'

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
           style={'padding': '0.5rem 1rem 0rem 1rem', 'margin': '0'}),
    html.P(id='next-temp-step',
           style={'padding': '0.5rem 1rem 1rem 1rem', 'margin': '0'}),
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
    batches = fetchBatches()
    options = []

    for batch in batches:
        # TODO: use a component to store fetched_batches instead of a module variable?
        fetched_batches[batch['Id']] = batch
        options.append(
            {'label': f"Batch#{batch['BatchNo']} - {batch['RecipeName']}", 'value': batch['Id']})

    return options


@app.callback(
    [Output(component_id='main-graph', component_property='figure'),
     Output(component_id='next-temp-step', component_property='children')],
    [Input(component_id='date-from', component_property='date'),
     Input(component_id='date-to', component_property='date'),
     Input(component_id='batch-selection', component_property='value'),
     Input(component_id='interval-component', component_property='n_intervals')])
def reFetchData(date_from, date_to, batch_id, n_intervals):
    df = fetchData(date_from, date_to, batch_id)
    fp = fetch_fermentation_profile(batch_id)

    if df.empty:
        return {
            'data': [go.Scatter(
                x=[],
                y=[],
                mode='lines+markers',
                name='temp_vs_time')],
            'layout': plot_layout
        }, ""

    graph_data = []

    bucket = df[df.Location.str.contains('Bucket')]
    ambient = df[df.Location.str.contains('Ambient')]

    if not bucket.empty:
        graph_data.append(getScatterPlot(bucket, "Bucket"))

    if not ambient.empty:
        graph_data.append(getScatterPlot(ambient, "Ambient"))

    next_fermentation_step = ""

    if not fp.empty:
        min_max = getCurrentMinMax(bucket, ambient)
        current_min_measuredAt = min_max[0]
        current_max_measuredAt = min_max[1]

        fp_subset = fp[fp['TimePoint'] <= current_max_measuredAt]
        fp_subset.head(1)['TimePoint'] = current_min_measuredAt

        numFp = len(fp.index)
        numFpSubset = len(fp_subset.index)

        last_fp = fp_subset.tail(1)['TimePoint'].values[0]

        if last_fp < current_max_measuredAt:
            fp_subset = fp_subset.append(
                {'TimePoint': current_max_measuredAt, 'Value': fp.iloc[[numFpSubset]]['Value'].values[0]}, ignore_index=True)

        next_fermentation_step = "Next temperature interval: "

        if numFp - 1 != numFpSubset and current_max_measuredAt < max(fp['TimePoint']):
            new_temp = fp.iloc[[numFpSubset + 1]]['Value'].values[0]
            new_date = fp.iloc[[numFpSubset + 1]
                               ]['TimePoint'].values[0].split('T')[0]

            next_fermentation_step = f"Next temperature interval: {new_temp}C at {new_date}"
        else:
            next_fermentation_step += "none"

        graph_data.append(go.Scatter(
            x=fp_subset["TimePoint"],
            y=fp_subset["Value"],
            line=dict(color='firebrick', width=3, dash='dash'),
            name="Fermentation Profile"))

    graph_update = {
        'data': graph_data,
        'layout': plot_layout
    }

    return graph_update, next_fermentation_step


def getScatterPlot(dataframe, name):
    return go.Scatter(
        x=dataframe["MeasuredAt"],
        y=dataframe["Value"],
        mode="lines+markers",
        name=name)


def getCurrentMinMax(bucket, ambient):
    if bucket.empty and ambient.empty:
        current_max_measuredAt = ''
        current_min_measuredAt = ''
    elif bucket.empty and not ambient.empty:
        current_max_measuredAt = max(ambient['MeasuredAt'])
        current_min_measuredAt = min(ambient['MeasuredAt'])
    elif ambient.empty and not bucket.empty:
        current_max_measuredAt = max(bucket['MeasuredAt'])
        current_min_measuredAt = min(bucket['MeasuredAt'])
    else:
        current_max_measuredAt = max(
            max(bucket['MeasuredAt']), max(ambient['MeasuredAt']))
        current_min_measuredAt = min(
            min(bucket['MeasuredAt']), min(ambient['MeasuredAt']))

    return [current_min_measuredAt, current_max_measuredAt]


if __name__ == '__main__':
    app.run_server(debug=False, host=config.server["listen_on"])
