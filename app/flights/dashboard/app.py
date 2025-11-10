# dashboard/app.py
from dash import Dash
import dash_bootstrap_components as dbc
from .layout import build_layout
from .callbacks import register_callbacks, preprocess
import pandas as pd

def create_dash_app(flights_df: pd.DataFrame, airlines_df: pd.DataFrame = None, airports_df: pd.DataFrame = None):
    external = [dbc.themes.BOOTSTRAP] if hasattr(dbc, "themes") else []
    app = Dash(__name__, external_stylesheets=external)
    app.title = "2015 Flight Delay Dashboard"

    # preprocess once
    df_clean = preprocess(flights_df)

    # prepare UI options
    if "AIRLINE_NAME" in df_clean.columns:
        unique_airlines = sorted(df_clean["AIRLINE_NAME"].dropna().astype(str).unique().tolist())
    elif "AIRLINE" in df_clean.columns:
        unique_airlines = sorted(df_clean["AIRLINE"].dropna().astype(str).unique().tolist())
    else:
        unique_airlines = []

    if "DATE" in df_clean.columns and not df_clean["DATE"].isna().all():
        min_date = str(df_clean["DATE"].min().date())
        max_date = str(df_clean["DATE"].max().date())
    else:
        min_date = None
        max_date = None

    app.layout = build_layout(unique_airlines, min_date, max_date)
    register_callbacks(app, df_clean)
    return app
