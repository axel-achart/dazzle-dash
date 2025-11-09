from dash import Input, Output, html
import pandas as pd
import plotly.express as px
from pandas.api.types import CategoricalDtype
from typing import Optional

DAY_ORDER_EN = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
DAY_CAT = CategoricalDtype(DAY_ORDER_EN, ordered=True)
PALETTE = px.colors.qualitative.Vivid
PLOTLY_TEMPLATE = "plotly"  # mode clair

DAY_FR_TO_EN = {
    "Lundi":"Monday","Mardi":"Tuesday","Mercredi":"Wednesday",
    "Jeudi":"Thursday","Vendredi":"Friday","Samedi":"Saturday","Dimanche":"Sunday"
}

def preprocess(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None: return pd.DataFrame()
    d = df.copy()

    if "DATE" in d.columns:
        d["DATE"] = pd.to_datetime(d["DATE"], errors="coerce")

    for col in ("ARRIVAL_DELAY", "DEPARTURE_DELAY"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")

    if "DAY_OF_WEEK" in d.columns:
        d["DAY_NAME"] = d["DAY_OF_WEEK"].map(lambda x: DAY_FR_TO_EN.get(str(x).strip(), x))
        d.loc[~d["DAY_NAME"].isin(DAY_ORDER_EN), "DAY_NAME"] = pd.NA
        d["DAY_NAME"] = d["DAY_NAME"].astype(DAY_CAT)
    elif "DATE" in d.columns:
        d["DAY_NAME"] = d["DATE"].dt.day_name()
        d["DAY_NAME"] = d["DAY_NAME"].astype(DAY_CAT)

    return d

def make_day_fig(df):
    tmp = df.dropna(subset=["DAY_NAME","ARRIVAL_DELAY"])
    if tmp.empty:
        return px.bar(title="Aucune donnée", template=PLOTLY_TEMPLATE)

    grouped = tmp.groupby("DAY_NAME")["ARRIVAL_DELAY"].mean().reindex(DAY_ORDER_EN)
    fig = px.bar(x=grouped.index, y=grouped.values,
                 labels={"x":"Jour","y":"Retard moyen (min)"},
                 title="Retard moyen par jour",
                 template=PLOTLY_TEMPLATE, color=grouped.index)
    fig.update_layout(showlegend=False)
    return fig

def make_airline_fig(df):
    name_col = "AIRLINE_NAME" if "AIRLINE_NAME" in df else "AIRLINE"
    tmp = df.dropna(subset=[name_col,"ARRIVAL_DELAY"])
    grouped = tmp.groupby(name_col)["ARRIVAL_DELAY"].mean().sort_values(ascending=False).head(15)
    fig = px.bar(x=grouped.index, y=grouped.values,
                 title="Top 15 compagnies (retard moyen)",
                 labels={"x":"Compagnie","y":"Retard moyen (min)"},
                 template=PLOTLY_TEMPLATE, color=grouped.values)
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(tickangle=45)
    return fig

def make_ts_fig(df):
    if "DATE" not in df.columns: 
        return px.line(title="Pas de colonne DATE", template=PLOTLY_TEMPLATE)
    tmp = df.set_index("DATE")["ARRIVAL_DELAY"].resample("W").mean()
    fig = px.line(x=tmp.index, y=tmp.values,
                  title="Retard moyen hebdomadaire",
                  labels={"x":"Date","y":"Retard (min)"},
                  template=PLOTLY_TEMPLATE)
    return fig

def make_causes_fig(df):
    causes = ["AIR_SYSTEM_DELAY","SECURITY_DELAY","AIRLINE_DELAY","LATE_AIRCRAFT_DELAY","WEATHER_DELAY"]
    causes = [c for c in causes if c in df.columns]
    if not causes: 
        return px.bar(title="Causes non disponibles", template=PLOTLY_TEMPLATE)

    means = df[causes].mean().sort_values()
    fig = px.bar(x=means.index, y=means.values,
                 title="Retard moyen par cause",
                 labels={"x":"Cause","y":"Retard moyen (min)"},
                 template=PLOTLY_TEMPLATE, color=means.values)
    fig.update_layout(coloraxis_showscale=False)
    return fig

def make_dist_fig(df):
    fig = px.histogram(df, x="ARRIVAL_DELAY", nbins=80,
                       title="Distribution des retards (min)",
                       template=PLOTLY_TEMPLATE)
    return fig

def make_top_airports_fig(dframe: pd.DataFrame, top_n:int=12):
    """
    Show top airports by average arrival delay.
    Prefer full airport name (ORIGIN_NAME). If not available, fall back to ORIGIN_AIRPORT (code).
    Display shortened x-labels for readability and full name in hover tooltip.
    """
    if dframe is None or dframe.empty or "ARRIVAL_DELAY" not in dframe.columns:
        return px.bar(title="Top aéroports - pas de données", template=PLOTLY_TEMPLATE)

    # prefer full name
    if "ORIGIN_NAME" in dframe.columns and dframe["ORIGIN_NAME"].notna().any():
        name_col = "ORIGIN_NAME"
    elif "ORIGIN_AIRPORT" in dframe.columns and dframe["ORIGIN_AIRPORT"].notna().any():
        name_col = "ORIGIN_AIRPORT"
    else:
        return px.bar(title="Top aéroports - colonnes origine manquantes", template=PLOTLY_TEMPLATE)

    # compute average delay per airport
    grouped = dframe.groupby(name_col, observed=True)["ARRIVAL_DELAY"].mean().sort_values(ascending=False).head(top_n)
    if grouped.empty:
        return px.bar(title="Top aéroports - aucune donnée", template=PLOTLY_TEMPLATE)

    # prepare short labels for x-axis but keep full names for hover (customdata)
    full_names = grouped.index.astype(str).to_list()
    short_labels = []
    for s in full_names:
        s_str = str(s)
        # trim common suffixes and limit length
        s_str = s_str.replace(" Airport", "").replace(" International", "")
        short_labels.append(s_str if len(s_str) <= 30 else s_str[:27] + "...")

    import numpy as _np
    customdata = _np.array(full_names).reshape(-1, 1)

    fig = px.bar(
        x=short_labels,
        y=grouped.values,
        labels={"x":"Aéroport","y":"Retard moyen (min)"},
        title=f"Top {top_n} aéroports par retard moyen",
        template=PLOTLY_TEMPLATE,
        color=grouped.values,
        color_continuous_scale="Viridis",
    )
    # show full airport name in hover and formatted delay
    fig.update_traces(
        hovertemplate="%{customdata[0]}<br>Retard moyen: %{y:.1f} min",
        customdata=customdata
    )
    fig.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False)
    return fig


CACHE = {}
def register_callbacks(app, df):
    df = preprocess(df)

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
    def update(airline, start, end):
        mask = pd.Series(True, index=df.index)
        if airline:
            mask &= df["AIRLINE_NAME"].eq(airline) if "AIRLINE_NAME" in df else df["AIRLINE"].eq(airline)
        if start: mask &= df["DATE"] >= start
        if end: mask &= df["DATE"] <= end

        dff = df.loc[mask]

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

        # KPIs
        total = len(dff)
        avg = round(dff["ARRIVAL_DELAY"].mean(),2) if "ARRIVAL_DELAY" in dff else "NA"
        med = round(dff["ARRIVAL_DELAY"].median(),2) if "ARRIVAL_DELAY" in dff else "NA"

        kpis = html.Div([
            html.Div([html.B("Vols analysés"), html.P(f"{total:,}")]),
            html.Div([html.B("Retard moyen"), html.P(f"{avg} min")]),
            html.Div([html.B("Médiane"), html.P(f"{med} min")])
        ], style={"display":"flex","gap":"12px"})

        return *figs, *captions, kpis
