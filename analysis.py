import os
import numpy as np
import pandas as pd
from datetime import date, datetime

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, callback

from dotenv import load_dotenv
load_dotenv()

from statics import DATE_RANGES

import logging
from sys import stdout
from log_config import CustomLogFormat, FORMAT

# Configure my custom format as STDOUT
# https://docs.python.org/3/library/logging.html#logrecord-attributes
handler = logging.StreamHandler(stdout)
handler.setFormatter(CustomLogFormat())
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    handlers=[
        handler
    ]
)

#pd.set_option('display.max_columns', None)
#pd.set_option('display.max_rows', None)

# Initialize the app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Try to load the setups
df:pd.DataFrame = pd.DataFrame()
try:
    df = pd.read_json('setups.json')
    df['time'] = pd.to_datetime(df['time']*1000000)
except:
    logging.warning('No setups.json file found!')

STRATEGIES = df['strategy'].unique().tolist()
TICKERS = df['ticker'].unique().tolist()
TICKERS = ['ALL TICKERS'] + TICKERS
TIMEFRAMES = df['timeframe'].unique().tolist()

print(df)

# App layout
app.layout = html.Div([
    #dcc.Store(id='signal-trades', storage_type='local'),
    html.Div(id='app-div', children=[
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.Stack([
                        html.H5('Filter Setups'),
                        html.H6('Direction'),
                        dbc.RadioItems(id='radios-direction', className='btn-group', inputClassName='btn-check', labelClassName='btn btn-outline-primary', labelCheckedClassName='active',
                            options=[
                                {'label': 'Long', 'value': 'long'},
                                {'label': 'Short', 'value': 'short'}
                            ],
                            value='long',
                        ),
                        html.H6('Type'),
                        dbc.RadioItems(id='radios-type', className='btn-group', inputClassName='btn-check', labelClassName='btn btn-outline-primary', labelCheckedClassName='active',
                            options=[
                                {'label': 'Signal', 'value': 'signal'},
                                {'label': 'Trade', 'value': 'trade'}
                            ],
                            value='signal',
                        ),
                        html.H6('Strategy'),
                        dcc.Dropdown(options=STRATEGIES, value=STRATEGIES[0] if len(STRATEGIES) > 0 else None, id='dropdown-strategy', placeholder='Select a strategy...'),
                        html.H6('Ticker'),
                        dcc.Dropdown(options=TICKERS, value=TICKERS[0] if len(TICKERS) > 0 else None, id='dropdown-ticker', placeholder='Select a ticker...'),
                        html.H6('Date Window'),
                        dcc.Dropdown(
                            id='dropdown-range',
                            value=list(DATE_RANGES.keys())[0],
                            options=list(DATE_RANGES.keys())
                        ),
                        dcc.DatePickerRange(
                            id='date-picker-range',
                            start_date=date(1900, 1, 1),
                            end_date=date(2030, 12, 31),
                            display_format='YYYY-MM-DD',
                            start_date_placeholder_text='YYYY-MM-DD',
                            end_date_placeholder_text='YYYY-MM-DD'
                        ),
                        html.H6('Timeframe'),
                        dcc.Dropdown(options=TIMEFRAMES, value=TIMEFRAMES[0] if len(TIMEFRAMES) > 0 else None, id='dropdown-timeframe', placeholder='Select a timeframe...'),
                        dbc.Button(id='button-show', children=['Show Data']),
                    ], gap=2)
                ], style={'padding':10, 'margin':10})
            ], width='2'),
            dbc.Col([
                dbc.Alert(children='', id='alert-error', is_open=False, color='danger', dismissable=True),
                dbc.Tabs([
                    dbc.Tab([
                        #html.H3('Query'),
                        #html.P(id='p-info', children=''),
                        dcc.Graph(id='graph-content'),
                    ], label='Histograms'),
                ])
            ], width='10'),
        ], style={'padding':5})
    ])
])


@callback(
    Output('date-picker-range', 'start_date'),
    Output('date-picker-range', 'end_date'),
    Input('dropdown-range', 'value'),
    prevent_initial_call=True)
def onRangeDropdown(value:str):
    if value == 'All':
        return '1900-01-01', '2030-12-31'
    return DATE_RANGES[value][0], DATE_RANGES[value][1]


def genHistogramFig(dfIn:pd.DataFrame, col:str, mean:bool=True):
    try:
        
        fig = px.histogram(dfIn, x=col, title=col)
        if mean:
            mv = dfIn[col].mean()
            fig.add_vline(x=mv, line_dash='dash', line_color='red', annotation_text=f'avg = {mv:.2f}', annotation_position='top')
        return fig
    except:
        logging.exception('genHistogramFig EXCEPTION')
    return None


@callback(
    Output('graph-content', 'figure'),
    Output('alert-error', 'children'),
    Output('alert-error', 'is_open'),
    State('radios-direction', 'value'),
    State('radios-type', 'value'),
    State('dropdown-strategy', 'value'),
    State('dropdown-ticker', 'value'),
    State('date-picker-range', 'start_date'),
    State('date-picker-range', 'end_date'),
    State('dropdown-timeframe', 'value'),
    Input('button-show', 'n_clicks'),
    prevent_initial_call=True)
def onButtonShowClick(direction:str, type:str, strategy:str, ticker:str, startDateStr:str, endDateStr:str, timeframe:str, _):
    logging.info(f'Show data: {direction}, {strategy}, {ticker}, {startDateStr}, {endDateStr}')
    error = ''
    fig = None
    try:
        if direction == None or type == None or strategy == None or ticker == None or timeframe == None:
            error = 'Invalid filter settings!'
            return fig, error, len(error)>0

        startDate = datetime.fromisoformat(startDateStr)
        endDate = datetime.fromisoformat(endDateStr)

        filteredDf = df[
            (df['ticker'] != '' if ticker == 'ALL TICKERS' else df['ticker'] == ticker) &
            (df['strategy'] == strategy) &
            (df['direction'] == direction) &
            (df['time'].between(startDate, endDate)) &
            (df['timeframe'] == timeframe)
        ]

        fig = genHistogramFig(filteredDf, 'INSIDE_CANDLE')

    except Exception as e:
        logging.exception('onButtonShowClick EXCEPTION')
        error = str(e)
    return fig, error, len(error)>0


# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8001)