"""
Define the Dash layout and static components.
"""
from dash import html, dcc

def build_layout(unique_airlines, min_date=None, max_date=None):
    return html.Div([
        html.H2("Dashboard - Retards de vols (Data Junior, SOLID)"),
        html.Div([
            html.Label("Compagnie (filtre)"),
            dcc.Dropdown(options=[{"label": a, "value": a} for a in unique_airlines],
                         value=None, id="airline_filter", multi=False, placeholder="Toutes"),
            html.Br(),
            html.Label("Plage de dates"),
            dcc.DatePickerRange(id="date_range", start_date=min_date, end_date=max_date),
        ], style={"width": "40%", "display": "inline-block", "verticalAlign": "top", "paddingRight": "20px"}),

        html.Div(id="kpis", style={"display": "flex", "gap": "10px", "marginTop": "10px"}),

        html.Div([
            dcc.Graph(id="day_delay"),
            dcc.Graph(id="airline_delay"),
            dcc.Graph(id="time_series")
        ])
    ], style={"margin": "20px"})
