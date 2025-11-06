import os
from pathlib import Path
from typing import Tuple, List

import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CLEAN_DIR = DATA_DIR / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

PARQUET_PATH = CLEAN_DIR / "fao_clean.parquet"
CSV_PATH = DATA_DIR / "FAO.csv"  # adjust if your CSV is elsewhere


@lru_cache(maxsize=1)
def load_prepare_data(parquet_path: Path = PARQUET_PATH, csv_path: Path = CSV_PATH) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # 1) Try parquet for fast load
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        # read CSV with fallback encoding and minimal memory
        try:
            df = pd.read_csv(csv_path, low_memory=False, encoding="utf-8")
        except Exception:
            df = pd.read_csv(csv_path, low_memory=False, encoding="latin-1")
        # do light cleaning and save parquet for next runs
        df = light_clean(df)
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            # if parquet fail (platform issue), continue without writing
            pass
    else:
        # no data found — return empty frames with expected structure
        return pd.DataFrame(), pd.DataFrame(columns=["Year", "Value"])

    # Rename Y#### columns to pure year strings and coerce to numeric
    year_cols = [c for c in df.columns if isinstance(c, str) and c.startswith("Y") and c[1:].isdigit()]
    if year_cols:
        rename_map = {c: c[1:] for c in year_cols}
        df = df.rename(columns=rename_map)
        year_cols = list(rename_map.values())

    # ensure year columns numeric
    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]
    if year_cols:
        df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")

    # Melt to long format if year columns exist
    if year_cols:
        id_vars = [c for c in df.columns if c not in year_cols]
        df_long = df.melt(id_vars=id_vars, value_vars=year_cols, var_name="Year", value_name="Value")
        # convert Year to datetime (year only)
        df_long["Year"] = pd.to_datetime(df_long["Year"].astype(str), format="%Y", errors="coerce")
        # coerce Value numeric, drop NaNs in Value if many
        df_long["Value"] = pd.to_numeric(df_long["Value"], errors="coerce")
        # optionally drop rows with missing area/item or Value
        df_long = df_long.dropna(subset=["Value"])
    else:
        df_long = pd.DataFrame(columns=list(df.columns) + ["Year", "Value"])

    return df, df_long


def light_clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Trim whitespace for object columns
    obj_cols = df.select_dtypes(include="object").columns
    for c in obj_cols:
        df[c] = df[c].astype(str).str.strip()

    if "Unit" in df.columns:
        df["Unit"] = df["Unit"].astype(str).str.replace("tonnes", "", case=False).str.strip()
        # don't coerce to int globally — keep safe
    return df


# Load once at module import for faster callbacks
try:
    WIDE_DF, LONG_DF = load_prepare_data()
except Exception as e:
    print("Data load error:", e)
    WIDE_DF, LONG_DF = pd.DataFrame(), pd.DataFrame()


# Precompute small summaries to avoid recomputing heavy aggregations in callbacks
PRECOMP: dict = {}
if not LONG_DF.empty:
    try:
        PRECOMP['value_stats'] = LONG_DF['Value'].describe().round(2).to_dict()
    except Exception:
        PRECOMP['value_stats'] = {}
else:
    PRECOMP['value_stats'] = {}

# correlation between years (if wide df has year columns)
if not WIDE_DF.empty:
    year_cols = [c for c in WIDE_DF.columns if isinstance(c, str) and c.isdigit()]
    if year_cols:
        try:
            year_df = WIDE_DF[year_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            corr = year_df.corr()
            PRECOMP['corr'] = corr.to_json(orient='split')
        except Exception:
            PRECOMP['corr'] = None
    else:
        PRECOMP['corr'] = None
else:
    PRECOMP['corr'] = None


# Initialize Dash app
# We'll load the chosen Bootswatch theme via a <link> element in the layout so we
# can swap the theme dynamically at runtime. Keep font-awesome icons loaded
# from the external_stylesheets param.
app = Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.icons.FONT_AWESOME])
server = app.server  # if you want to deploy

color_mode_switch =  html.Span(
    [
        dbc.Label(className="fa fa-sun", html_for="switch"),
        dbc.Switch( id="switch", value=True, className="d-inline-block ms-1", persistence=True),
        dbc.Label(className="fa fa-moon", html_for="switch"),
    ]
)

def build_layout(wide_df: pd.DataFrame, long_df: pd.DataFrame):
    # safe lists
    areas = sorted(long_df["Area"].dropna().unique()) if not long_df.empty else []
    items = sorted(long_df["Item"].dropna().unique()) if not long_df.empty else []

    # year min/max
    if not long_df.empty and "Year" in long_df.columns:
        years = long_df["Year"].dt.year.dropna().astype(int)
        min_year, max_year = int(years.min()), int(years.max())
    else:
        min_year, max_year = 1961, 2013

    # default areas: top 5 by total
    if not long_df.empty:
        default_areas = list(long_df.groupby("Area")["Value"].sum().nlargest(5).index)
    else:
        default_areas = []

    layout = html.Div([
        # Theme link inserted here so it can be swapped at runtime by the switch
        html.Link(id='theme-link', rel='stylesheet', href=dbc.themes.FLATLY),

        # Header (includes theme switch)
        html.Div([
            html.Div(html.H2("FAO — Dashboard", style={"margin": "0"}), style={"display": "inline-block"}),
            html.Div(color_mode_switch, style={"float": "right", "display": "flex", "alignItems": "center"})
        ], style={"padding": "20px", "border-bottom": "1px solid #dee2e6"}),
        
        # Main content container
        html.Div([
            # Left sidebar with controls
            html.Div([
                html.Div([
                    html.Label("Areas (countries)", style={"font-weight": "bold", "margin-bottom": "8px"}),
                    dcc.Dropdown(id="area-dropdown", options=[{"label": a, "value": a} for a in areas],
                               value=default_areas, multi=True, placeholder="Select areas",
                               style={"margin-bottom": "16px"}),
                               
                    html.Label("Items", style={"font-weight": "bold", "margin-bottom": "8px"}),
                    dcc.Dropdown(id="item-dropdown", options=[{"label": i, "value": i} for i in items],
                               value=[], multi=True, placeholder="Select items (optional)",
                               style={"margin-bottom": "16px"}),
                               
                    html.Label("Year range", style={"font-weight": "bold", "margin-bottom": "8px"}),
                    dcc.RangeSlider(id="year-range", min=min_year, max=max_year, value=[min_year, max_year],
                                  marks={y: str(y) for y in range(min_year, max_year + 1, max(1, (max_year - min_year) // 6))})
                ], style={"background-color": "white", "padding": "20px", "border-radius": "8px", "box-shadow": "0 2px 4px rgba(0,0,0,0.1)"})
            ], style={"width": "25%", "margin-right": "2%"}),

            # Right content area with graphs
            html.Div([
                # Top bar charts row
                html.Div([
                    html.Div([
                        dcc.Graph(id="bar-top-areas", config={"displayModeBar": False})
                    ], style={"width": "50%", "padding": "10px"}),
                    
                    html.Div([
                        dcc.Graph(id="bar-top-items", config={"displayModeBar": False})
                    ], style={"width": "50%", "padding": "10px"})
                ], style={"display": "flex", "margin-bottom": "20px"}),
                
                # Time series chart
                html.Div([
                    dcc.Graph(id="ts-top-areas", style={"height": "420px"}, config={"displayModeBar": False})
                ], style={"padding": "10px", "margin-bottom": "20px"}),
                
                # Pie chart
                html.Div([
                    dcc.Graph(id="pie-area", config={"displayModeBar": False})
                ], style={"padding": "10px"}),

                html.Div([
                    dcc.Graph(id='corr-heatmap', config={"displayModeBar": False})
                ], style={"display": "flex","margin-bottom": "20px"})

            ], style={"width": "73%", "background-color": "white", "border-radius": "8px", "box-shadow": "0 2px 4px rgba(0,0,0,0.1)", "padding": "20px"})
        ], style={"display": "flex", "padding": "20px"}),


        html.Div([
            dash_table.DataTable(id='stats-table',
                                 columns=[{"name": k, "id": k} for k in ['stat', 'value']],
                                 data=[],
                                 style_table={"overflowX": "auto"},
                                 style_cell={"textAlign": "left"})
        ], style={"padding": "12px", "width": "100%"}),

        # store the long dataframe in JSON once to avoid re-parsing CSV per callback
        dcc.Store(id="df-long-store", data=long_df.to_json(date_format="iso", orient="split")),
        dcc.Store(id='precomp-store', data=PRECOMP)
    ])
    return layout


app.layout = build_layout(WIDE_DF, LONG_DF)


# Clientside callback: toggle the Bootswatch theme CSS href when the switch is toggled.
# Using a clientside callback makes the swap instantaneous in the browser.
app.clientside_callback(
    f"""
    function(is_dark) {{
        if (is_dark) {{
            return '{dbc.themes.DARKLY}';
        }} else {{
            return '{dbc.themes.FLATLY}';
        }}
    }}
    """,
    Output('theme-link', 'href'),
    Input('switch', 'value')
)


# --- helpers used inside callbacks ---

def df_from_store(df_json) -> pd.DataFrame:
    try:
        dfl = pd.read_json(df_json, orient="split")
    except Exception:
        return pd.DataFrame()
    if "Year" in dfl.columns:
        dfl["Year"] = pd.to_datetime(dfl["Year"], errors="coerce")
    return dfl


# --- Callbacks ---

@app.callback(
    Output("bar-top-areas", "figure"),
    Input("item-dropdown", "value"),
    Input("year-range", "value"),
    Input("df-long-store", "data")
)
def update_top_areas(selected_items, year_range, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    # filter by year range
    if year_range and "Year" in dfl.columns:
        start, end = year_range
        mask = dfl["Year"].dt.year.between(start, end)
        dfl = dfl.loc[mask]

    # filter by items if provided
    if selected_items:
        dfl = dfl.loc[dfl["Item"].isin(selected_items)]

    if dfl.empty or "Area" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig

    agg = dfl.groupby("Area")["Value"].sum().nlargest(10)
    fig = px.bar(x=agg.values, y=agg.index, orientation="h",
                 labels={"x": "Total Value", "y": "Area"},
                 title="Top 10 Areas by total Value")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=120))
    return fig


@app.callback(
    Output("bar-top-items", "figure"),
    Input("area-dropdown", "value"),
    Input("year-range", "value"),
    Input("df-long-store", "data")
)
def update_top_items(selected_areas, year_range, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    if year_range and "Year" in dfl.columns:
        start, end = year_range
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    if selected_areas:
        dfl = dfl.loc[dfl["Area"].isin(selected_areas)]

    if dfl.empty or "Item" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig

    agg = dfl.groupby("Item")["Value"].sum().nlargest(10)
    fig = px.bar(x=agg.values, y=agg.index, orientation="h",
                 labels={"x": "Total Value", "y": "Item"},
                 title="Top 10 Items by total Value")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=120))
    return fig


@app.callback(
    Output("ts-top-areas", "figure"),
    Input("area-dropdown", "value"),
    Input("item-dropdown", "value"),
    Input("year-range", "value"),
    Input("df-long-store", "data")
)
def update_time_series(selected_areas, selected_items, year_range, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty or "Year" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No time-series data")
        return fig

    # filter quickly
    if year_range:
        start, end = year_range
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    if selected_items:
        dfl = dfl.loc[dfl["Item"].isin(selected_items)]

    if not selected_areas:
        # default to top 5 areas by total in filtered data
        totals = dfl.groupby("Area")["Value"].sum().nlargest(5)
        selected_areas = list(totals.index)

    dfl = dfl.loc[dfl["Area"].isin(selected_areas)]
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig

    ts = dfl.groupby([dfl["Year"].dt.year.rename("Year"), "Area"])["Value"].sum().reset_index()
    ts["Year"] = pd.to_datetime(ts["Year"].astype(int), format="%Y")
    fig = px.line(ts, x="Year", y="Value", color="Area", markers=True,
                  title="Time series of Value for selected Areas")
    fig.update_layout(xaxis=dict(dtick="M12"))  # tick every year
    return fig


@app.callback(
    Output("pie-area", "figure"),
    Input("area-dropdown", "value"),
    Input("year-range", "value"),
    Input("df-long-store", "data")
)
def update_pie(selected_areas, year_range, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    # filter by year
    if year_range:
        start, end = year_range
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    # choose area
    if selected_areas:
        area = selected_areas[0]
    else:
        totals = dfl.groupby("Area")["Value"].sum().nlargest(1)
        area = totals.index[0] if not totals.empty else None

    if not area:
        fig = go.Figure()
        fig.update_layout(title="No area available")
        return fig

    subset = dfl.loc[dfl["Area"] == area]
    data = subset.groupby("Item")["Value"].sum().reset_index()
    data = data.loc[data["Value"] > 0].sort_values("Value", ascending=False)
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for {area}")
        return fig

    total = data["Value"].sum()
    thresh = total * 0.03
    big = data.loc[data["Value"] >= thresh]
    small_sum = data.loc[data["Value"] < thresh, "Value"].sum()
    labels = list(big["Item"])
    values = list(big["Value"])
    if small_sum > 0:
        labels.append("Other")
        values.append(small_sum)

    fig = px.pie(values=values, names=labels, title=f"Production distribution by Item — {area}")
    return fig



@app.callback(
    Output('corr-heatmap', 'figure'),
    Input('precomp-store', 'data')
)
def update_corr(precomp):
    if not precomp or not precomp.get('corr'):
        fig = go.Figure()
        fig.update_layout(title='No correlation matrix available')
        return fig
    try:
        corr_df = pd.read_json(precomp.get('corr'), orient='split')
        fig = px.imshow(corr_df.values, x=corr_df.columns, y=corr_df.index,
                        color_continuous_scale='RdBu', zmin=-1, zmax=1,
                        title='Correlation between years')
        fig.update_layout(margin=dict(l=40, r=20, t=40, b=40))
        return fig
    except Exception:
        fig = go.Figure()
        fig.update_layout(title='Error building correlation heatmap')
        return fig


@app.callback(
    Output('stats-table', 'data'),
    Input('precomp-store', 'data')
)
def update_stats_table(precomp):
    stats = precomp.get('value_stats') if precomp else {}
    if not stats:
        return []
    # convert to list of dicts for DataTable
    rows = []
    for k, v in stats.items():
        rows.append({'stat': k, 'value': v})
    return rows


@app.callback(
    Output('stats-table', 'style_cell'),
    Output('stats-table', 'style_header'),
    Output('stats-table', 'style_data'),
    Input('switch', 'value')
)
def stats_table_styles(is_dark: bool):
    if is_dark:
        style_cell = {
            'textAlign': 'left',
            'padding': '8px',
            'color': '#f8f9fa',
            'backgroundColor': '#222',
        }
        style_header = {
            'backgroundColor': '#2b2b2b',
            'fontWeight': 'bold',
            'color': '#f8f9fa',
        }
        style_data = {
            'backgroundColor': '#222',
            'color': '#f8f9fa',
        }
    else:
        style_cell = {
            'textAlign': 'left',
            'padding': '8px',
            'color': '#212529',
            'backgroundColor': 'white',
        }
        style_header = {
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold',
            'color': '#212529',
        }
        style_data = {
            'backgroundColor': 'white',
            'color': '#212529',
        }
    return style_cell, style_header, style_data


if __name__ == "__main__":
    # Set debug=False for faster startup in production; toggle True for development.
    app.run(debug=False, port=8050)
