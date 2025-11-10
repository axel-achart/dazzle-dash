import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Load data
df = pd.read_csv('data/Life Expectancy Data.csv')

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Life Expectancy Analytics", className="text-center my-4"),
            html.P("Interactive visualizations of global life expectancy data.", className="text-center"),
        ], width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(
                id='life-expectancy-map',
                figure=px.choropleth(
                    df,
                    locations="Country",
                    locationmode='country names',
                    color="Life expectancy ",
                    hover_name="Country",
                    animation_frame="Year",
                    title="Global Life Expectancy Over Time"
                )
            )
        ], width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(
                id='life-expectancy-trend',
                figure=px.line(
                    df.groupby('Year')['Life expectancy '].mean().reset_index(),
                    x='Year',
                    y='Life expectancy ',
                    title='Average Global Life Expectancy Trend'
                )
            )
        ], width=6),
        dbc.Col([
            dcc.Graph(
                id='life-expectancy-distribution',
                figure=px.histogram(
                    df,
                    x='Life expectancy ',
                    title='Distribution of Life Expectancy'
                )
            )
        ], width=6)
    ])
], fluid=True)