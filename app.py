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

# Squelch warning about unverified SSL cert for HTTPS - we know the API is OK!
requests.packages.urllib3.disable_warnings()
apiUrl = config.api["url"]
token = config.api["token"]

# Show today's values by default
# To-date is tomorrow because the timestamp is 00:00:00
graph_date_from = dt.date.today() - dt.timedelta(days=1)
graph_date_to = dt.date.today() + dt.timedelta(days=1)
graph_update_interval = 1 * 60 * 1000  # 1 minutes
date_update_interval = 60 * 60 * 1000  # 60 minutes


def fetchData(date_from, date_to):
    headers = {"Authorization": "Bearer " + token}
    params = {"from": date_from, "to": date_to}
    req = requests.get(apiUrl, headers=headers, params=params, verify=False)

    return pd.read_json(req.text)


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

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
    return dt.date.today() - dt.timedelta(days=1)


@app.callback(Output(component_id='date-to', component_property='date'), [Input(component_id='date-update', component_property='n_intervals')])
def refreshToDate(n_intervals):
    return dt.date.today() + dt.timedelta(days=1)


@app.callback(
    Output(component_id='main-graph', component_property='figure'),
    [Input(component_id='date-from', component_property='date'),
     Input(component_id='date-to', component_property='date'),
     Input(component_id='interval-component', component_property='n_intervals')])
def reFetchData(date_from, date_to, n_intervals):
    df = fetchData(date_from, date_to)

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
