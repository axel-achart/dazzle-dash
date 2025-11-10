from dash import html, dcc

def get_main_layout():
    return html.Div([
        dcc.Location(id="url"),
        html.Nav([
            dcc.Link("Flights", href="/flights"),
            dcc.Link("Life Expectancy WHO", href="/who"),
            dcc.Link("Food", href="/food"),
        ], style={"display": "flex", "gap": "20px"}),
        html.Hr(),
        html.Div(id="page-content")
    ])
