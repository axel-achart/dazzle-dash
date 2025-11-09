from dash import html, dcc

def build_layout(unique_airlines, min_date=None, max_date=None):
    return html.Div([
        html.Div([
            html.H2("2015 Flight Delay Dashboard"),
            html.P("Analyse 2015 : retards, tendances, causes et performances des compagnies et aéroports.", style={"marginTop":"0"})
        ], style={"marginBottom":"12px"}),

        html.Div([
            html.Div([
                html.Label("Compagnie (filtre)"),
                dcc.Dropdown(
                    options=[{"label": a, "value": a} for a in unique_airlines],
                    value=None,
                    id="airline_filter",
                    placeholder="Toutes les compagnies",
                    clearable=True
                ),
                html.Br(),
                html.Label("Période"),
                dcc.DatePickerRange(
                    id="date_range",
                    start_date=min_date,
                    end_date=max_date,
                    display_format="YYYY-MM-DD"
                ),
            ], style={"width":"36%","display":"inline-block","verticalAlign":"top","paddingRight":"20px"}),

            html.Div(id="kpis", style={"display":"flex","gap":"10px","alignItems":"center","flexWrap":"wrap"})
        ], style={"display":"flex","justifyContent":"space-between","alignItems":"flex-start"}),

        html.Div([
            html.Div([dcc.Graph(id="day_delay", style={"height":"360px"}), html.P(id="day_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="airline_delay", style={"height":"360px"}), html.P(id="airline_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="time_series", style={"height":"360px"}), html.P(id="ts_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="causes", style={"height":"360px"}), html.P(id="causes_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="dist_delay", style={"height":"360px"}), html.P(id="dist_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="top_airports", style={"height":"360px"}), html.P(id="airports_caption", style={"marginTop":"6px"})]),
        ], style={"display":"grid", "gridTemplateColumns":"1fr 1fr", "gap":"12px", "marginTop":"16px"}),

        html.Div(id="debug_info", style={"marginTop":"10px","fontSize":"12px"})
    ], style={"margin":"20px","padding":"12px"})
