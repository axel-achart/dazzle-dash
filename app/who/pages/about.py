from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("About This Dashboard", className="text-center my-4"),
            html.P("This dashboard provides insights into global life expectancy data from the World Health Organization.", className="text-center"),
            html.Hr(),
            html.H3("Data Source"),
            html.P("The data used in this dashboard comes from the Life Expectancy Data.csv file, which contains information on life expectancy across various countries and years."),
            html.H3("Features"),
            html.Ul([
                html.Li("Interactive world map showing life expectancy by country"),
                html.Li("Time series analysis of global life expectancy trends"),
                html.Li("Distribution analysis of life expectancy values"),
                html.Li("Responsive design for various screen sizes")
            ]),
            dbc.Button("Back to Home", href="/", color="secondary", className="d-block mx-auto my-3"),
        ], width=12)
    ])
], fluid=True)