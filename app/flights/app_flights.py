import os
import pandas as pd
import plotly.express as px
from dash import html, dcc, Input, Output

BASE_DIR = os.path.dirname(os.path.abspath(__file__))         # Te place dans .../app/flights/ OU .../app/food/ OU .../app/who/
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
CSV_FLIGHTS = os.path.join(DATA_DIR, "clean", "dashboard_flights.csv")
df = pd.read_csv(CSV_FLIGHTS, low_memory=False)

def preprocess(df):
    df = df.copy()
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    for col in ("ARRIVAL_DELAY", "DEPARTURE_DELAY"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "DAY_OF_WEEK" in df.columns:
        DAY_FR_TO_EN = {
            "Lundi":"Monday","Mardi":"Tuesday","Mercredi":"Wednesday","Jeudi":"Thursday",
            "Vendredi":"Friday","Samedi":"Saturday","Dimanche":"Sunday"
        }
        DAY_ORDER_EN = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        df["DAY_NAME"] = df["DAY_OF_WEEK"].map(lambda x: DAY_FR_TO_EN.get(str(x).strip(), x))
        df["DAY_NAME"] = pd.Categorical(df["DAY_NAME"], DAY_ORDER_EN, ordered=True)
    elif "DATE" in df.columns:
        df["DAY_NAME"] = df["DATE"].dt.day_name()
    return df

df = preprocess(df)
unique_airlines = sorted(df["AIRLINE_NAME"].dropna().astype(str).unique().tolist()) if "AIRLINE_NAME" in df.columns else []
min_date = str(df["DATE"].min().date()) if "DATE" in df.columns else None
max_date = str(df["DATE"].max().date()) if "DATE" in df.columns else None

print("Data loaded for dashboard:", df.head)

def get_layout():
    return html.Div([
        html.H2("2015 Flight Delay Dashboard"),
        html.P("Analyse 2015 : retards, tendances, causes et performances des compagnies et aéroports."),
        html.Div([
            html.Div([
                html.Label("Compagnie (filtre)"),
                dcc.Dropdown(
                    options=[{"label": a, "value": a} for a in unique_airlines],
                    value=None, id="airline_filter", placeholder="Toutes les compagnies", clearable=True
                ),
                html.Br(),
                html.Label("Période"),
                dcc.DatePickerRange(
                    id="date_range",
                    start_date=min_date,
                    end_date=max_date,
                    display_format="YYYY-MM-DD"
                )
            ], style={"width":"36%","display":"inline-block","verticalAlign":"top","paddingRight":"20px"}),
            html.Div(id="kpis", style={"display":"flex","gap":"10px","alignItems":"center","flexWrap":"wrap"})
        ], style={"display":"flex","justifyContent":"space-between","alignItems":"flex-start"}),
        html.Div([
            html.Div([dcc.Graph(id="day_delay", style={"height":"360px"}), html.P(id="day_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="airline_delay", style={"height":"360px"}), html.P(id="airline_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="time_series", style={"height":"360px"}), html.P(id="ts_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="causes", style={"height":"360px"}), html.P(id="causes_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="dist_delay", style={"height":"360px"}), html.P(id="dist_caption", style={"marginTop":"6px"})]),
            html.Div([dcc.Graph(id="top_airports", style={"height":"360px"}), html.P(id="airports_caption", style={"marginTop":"6px"})])
        ], style={"display":"grid", "gridTemplateColumns":"1fr 1fr", "gap":"12px", "marginTop":"16px"}),
        html.Div(id="debug_info", style={"marginTop":"10px","fontSize":"12px"})
    ], style={"margin":"20px","padding":"12px"})


def register_callbacks(app):
    @app.callback(
        Output("day_delay","figure"),
        Output("airline_delay","figure"),
        Output("time_series","figure"),
        Output("causes","figure"),
        Output("dist_delay","figure"),
        Output("top_airports","figure"),
        Output("day_caption","children"),
        Output("airline_caption","children"),
        Output("ts_caption","children"),
        Output("causes_caption","children"),
        Output("dist_caption","children"),
        Output("airports_caption","children"),
        Output("kpis","children"),
        Input("airline_filter","value"),
        Input("date_range","start_date"),
        Input("date_range","end_date")
    )
    def update_dashboard(airline, start, end):
        mask = pd.Series(True, index=df.index)
        if airline:
            name_col = "AIRLINE_NAME" if "AIRLINE_NAME" in df.columns else "AIRLINE"
            mask &= df[name_col] == airline
        if start: mask &= df["DATE"] >= start
        if end: mask &= df["DATE"] <= end
        dff = df[mask]
        # KPI
        total = len(dff)
        avg = round(dff["ARRIVAL_DELAY"].mean(),2) if "ARRIVAL_DELAY" in dff else "NA"
        med = round(dff["ARRIVAL_DELAY"].median(),2) if "ARRIVAL_DELAY" in dff else "NA"
        kpis = html.Div([
            html.Div([html.B("Vols analysés"), html.P(f"{total:,}")]),
            html.Div([html.B("Retard moyen"), html.P(f"{avg} min")]),
            html.Div([html.B("Médiane"), html.P(f"{med} min")])
        ], style={"display":"flex","gap":"12px"})
        # Figures
        def make_day_fig(df):
            tmp = df.dropna(subset=["DAY_NAME","ARRIVAL_DELAY"])
            if tmp.empty:
                return px.bar(title="Aucune donnée")
            grouped = tmp.groupby("DAY_NAME")["ARRIVAL_DELAY"].mean()
            return px.bar(x=grouped.index, y=grouped.values, labels={"x":"Jour","y":"Retard moyen (min)"}, title="Retard moyen par jour")
        def make_airline_fig(df):
            name_col = "AIRLINE_NAME" if "AIRLINE_NAME" in df else "AIRLINE"
            tmp = df.dropna(subset=[name_col,"ARRIVAL_DELAY"])
            grouped = tmp.groupby(name_col)["ARRIVAL_DELAY"].mean().sort_values(ascending=False).head(15)
            return px.bar(x=grouped.index, y=grouped.values, title="Top 15 compagnies (retard moyen)", labels={"x":"Compagnie","y":"Retard moyen (min)"})
        def make_ts_fig(df):
            if "DATE" not in df.columns:
                return px.line(title="Pas de colonne DATE")
            tmp = df.set_index("DATE")["ARRIVAL_DELAY"].resample("W").mean()
            return px.line(x=tmp.index, y=tmp.values, title="Retard moyen hebdomadaire", labels={"x":"Date","y":"Retard (min)"})
        def make_causes_fig(df):
            causes = [c for c in ["AIR_SYSTEM_DELAY","SECURITY_DELAY","AIRLINE_DELAY","LATE_AIRCRAFT_DELAY","WEATHER_DELAY"] if c in df.columns]
            if not causes:
                return px.bar(title="Causes non disponibles")
            means = df[causes].mean().sort_values()
            return px.bar(x=means.index, y=means.values, title="Retard moyen par cause", labels={"x":"Cause","y":"Retard moyen (min)"})
        def make_dist_fig(df):
            return px.histogram(df, x="ARRIVAL_DELAY", nbins=80, title="Distribution des retards (min)")
        def make_top_airports_fig(df, top_n=12):
            name_col = "ORIGIN_NAME" if "ORIGIN_NAME" in df.columns else "ORIGIN_AIRPORT"
            tmp = df.dropna(subset=[name_col,"ARRIVAL_DELAY"])
            grouped = tmp.groupby(name_col)["ARRIVAL_DELAY"].mean().sort_values(ascending=False).head(top_n)
            return px.bar(x=grouped.index, y=grouped.values, labels={"x":"Aéroport","y":"Retard moyen (min)"}, title=f"Top {top_n} aéroports par retard moyen")
        figs = [
            make_day_fig(dff),
            make_airline_fig(dff),
            make_ts_fig(dff),
            make_causes_fig(dff),
            make_dist_fig(dff),
            make_top_airports_fig(dff)
        ]
        captions = [
            "Retards moyens selon le jour de la semaine.",
            "Compagnies les plus impactées par les retards.",
            "Tendance des retards au fil de l'année.",
            "Causes principales de retard.",
            "Répartition des retards sur l’année 2015.",
            "Aéroports avec les plus grands retards moyens."
        ]
        return *figs, *captions, kpis
