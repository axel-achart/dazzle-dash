"""
Factory to create the Dash app given a prepared pandas DataFrame.
"""
from dash import Dash
import dash_bootstrap_components as dbc

from .layout import build_layout
from .callbacks import register_callbacks
import pandas as pd

def create_dash_app(flights_df: pd.DataFrame, airlines_df=None, airports_df=None):
    # Defensive copy
    df = flights_df.copy()
    # Try to use bootstrap theme if available, otherwise fallback
    external = []
    try:
        external = [dbc.themes.BOOTSTRAP]
    except Exception:
        external = []

    app = Dash(__name__, external_stylesheets=external)

    # prepare UI inputs
    if "AIRLINE_NAME" in df.columns:
        unique_airlines = sorted(pd.Series(df["AIRLINE_NAME"].dropna().unique()).astype(str).tolist())
    elif "AIRLINE" in df.columns:
        unique_airlines = sorted(pd.Series(df["AIRLINE"].dropna().unique()).astype(str).tolist())
    else:
        unique_airlines = []

    if "DATE" in df.columns and not df["DATE"].isna().all():
        min_date = str(df["DATE"].min().date())
        max_date = str(df["DATE"].max().date())
    else:
        min_date = None
        max_date = None

    app.layout = build_layout(unique_airlines, min_date, max_date)

    # register callbacks uses `df` in closure
    register_callbacks(app, df)

    return app
