import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Welcome to Life Expectancy Dashboard", className="text-center my-4"),
            html.P("Explore global life expectancy data through interactive visualizations.", className="text-center"),
            dbc.Button("Go to Analytics", href="/analytics", color="primary", className="d-block mx-auto my-3"),
        ], width=12)
    ])
], fluid=True)