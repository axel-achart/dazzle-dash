import os
from pathlib import Path
from typing import Tuple, List

import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, dash_table, exceptions as dash_exceptions
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CLEAN_DIR = DATA_DIR / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

PARQUET_PATH = CLEAN_DIR / "fao_clean.parquet"
CSV_PATH = DATA_DIR / "FAO.csv"


@lru_cache(maxsize=1)
def load_prepare_data(parquet_path: Path = PARQUET_PATH, csv_path: Path = CSV_PATH) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # 1) Load raw data (parquet preferred for speed)
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        # read CSV with fallback encoding
        try:
            df = pd.read_csv(csv_path, low_memory=False, encoding="utf-8")
        except Exception:
            df = pd.read_csv(csv_path, low_memory=False, encoding="latin-1")
        df = light_clean(df)
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            pass
    else:
        # no data found — return empty frames with expected structure
        return pd.DataFrame(), pd.DataFrame(columns=["Year", "Value"])

    # Normalize column names used in the app
    # Map source 'Area'/'Items' to our canonical 'Country'/'Product'
    rename_map = {}
    if "Area" in df.columns and "Country" not in df.columns:
        rename_map["Area"] = "Country"
    if "Item" in df.columns and "Product" not in df.columns:
        rename_map["Item"] = "Product"
    if rename_map:
        df = df.rename(columns=rename_map)

    # Find year columns: either 'Y####' or plain digits
    year_cols = [c for c in df.columns if isinstance(c, str) and c.startswith("Y") and c[1:].isdigit()]
    if year_cols:
        df = df.rename(columns={c: c[1:] for c in year_cols})
    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]

    if year_cols:
        # coerce year columns to numeric and melt to long form
        df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
        id_vars = [c for c in df.columns if c not in year_cols]
        df_long = df.melt(id_vars=id_vars, value_vars=year_cols, var_name="Year", value_name="Value")
        # convert Year to datetime (year only)
        df_long["Year"] = pd.to_datetime(df_long["Year"].astype(str), format="%Y", errors="coerce")
        df_long["Value"] = pd.to_numeric(df_long["Value"], errors="coerce")
        # drop rows without a numeric Value
        df_long = df_long.dropna(subset=["Value"]) if not df_long.empty else pd.DataFrame(columns=list(df.columns) + ["Year", "Value"])
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
if not LONG_DF.empty and 'Value' in LONG_DF.columns:
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
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.icons.FONT_AWESOME,
        dbc.themes.FLATLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap",
    ],
)
server = app.server

def build_layout(wide_df: pd.DataFrame, long_df: pd.DataFrame):
    # safe lists (use renamed columns Country/Product)
    countries = sorted(long_df["Country"].dropna().unique()) if not long_df.empty and "Country" in long_df.columns else []
    products = sorted(long_df["Product"].dropna().unique()) if not long_df.empty and "Product" in long_df.columns else []

    # year min/max
    if not long_df.empty and "Year" in long_df.columns:
        years = long_df["Year"].dt.year.dropna().astype(int)
        min_year, max_year = int(years.min()), int(years.max())
    else:
        min_year, max_year = 1961, 2013

    # default countries: top 5 by total
    if not long_df.empty and "Country" in long_df.columns:
        # default top 5 countries by total value
        default_countries = list(long_df.groupby("Country")["Value"].sum().nlargest(5).index)
    else:
        default_countries = []

    # Initial filter values
    initial_filters = {
        "countries": default_countries,
        "products": [],
        "year_range": [min_year, max_year]
    }

    layout = html.Div([
        # Header
        html.Div([
            html.H2(
                "FAO — DASHBOARD",
                style={
                    "margin": 0,
                    "textAlign": "center",
                    "fontSize": "32px",
                    "fontWeight": 700,
                },
            )
        ], style={"padding": "20px", "border-bottom": "1px solid #dee2e6", "display": "flex", "justifyContent": "center"}),

        # Main content container
        html.Div([
            # Left sidebar with controls
            html.Div([
                html.Div([
                    html.Label("Countries", style={"font-weight": "bold", "margin-bottom": "8px"}),
                    dcc.Dropdown(
                        id="area-dropdown",
                        options=[{"label": c, "value": c} for c in countries],
                        value=default_countries,
                        multi=True,
                        placeholder="Select countries",
                        style={"margin-bottom": "16px"},
                    ),

                    html.Label("Products", style={"font-weight": "bold", "margin-bottom": "8px", "color": "#212529"}),
                    dcc.Dropdown(
                        id="item-dropdown",
                        options=[{"label": p, "value": p} for p in products],
                        value=[],
                        multi=True,
                        placeholder="Select products (optional)",
                        style={"margin-bottom": "16px"}
                    ),

                    html.Label("Year range", style={"font-weight": "bold", "margin-bottom": "8px", "color": "#212529"}),
                    dcc.RangeSlider(
                        id="year-range",
                        min=min_year,
                        max=max_year,
                        value=[min_year, max_year],
                        marks={y: str(y) for y in range(min_year, max_year + 1, max(1, (max_year - min_year) // 6))},
                        className="mt-2"
                    ),

                    html.Div([
                        dbc.Button(
                            "Apply filters",
                            id="apply-filters-btn",
                            color="primary",
                            className="w-100 mt-4",
                            style={
                                "fontWeight": 600,
                                "fontSize": "16px",
                                "padding": "10px 14px",
                                "borderRadius": "8px",
                                "boxShadow": "0 2px 6px rgba(0,0,0,0.08)",
                            },
                        )
                    ], style={"margin-top": "20px"})
                ], style={
                    "background-color": "white",
                    "padding": "20px",
                    "border-radius": "8px",
                    "box-shadow": "0 2px 4px rgba(0,0,0,0.1)",
                    "color": "#212529"
                })
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
                                 style_cell={"textAlign": "left", "color": "#212529", "backgroundColor": "white"},
                                 style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold", "color": "#212529"},
                                 style_data={"backgroundColor": "white", "color": "#212529"}
                                 )
        ], style={"padding": "12px", "width": "100%"}),

        # store the long dataframe in JSON once to avoid re-parsing CSV per callback
        dcc.Store(id="df-long-store", data=long_df.to_json(date_format="iso", orient="split")),
        dcc.Store(id='precomp-store', data=PRECOMP),
        # Store for validated filters
        dcc.Store(id="validated-filters", data=initial_filters)
    ], style={"fontFamily": "'Inter', sans-serif", "backgroundColor": "#f8f9fa"})
    return layout


app.layout = build_layout(WIDE_DF, LONG_DF)

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
    Output("validated-filters", "data"),
    Input("apply-filters-btn", "n_clicks"),
    State("area-dropdown", "value"),
    State("item-dropdown", "value"),
    State("year-range", "value")
)
def update_validated_filters(n_clicks, countries, products, year_range):
    if n_clicks is None:
        raise dash_exceptions.PreventUpdate
    return {
        "countries": countries if countries is not None else [],
        "products": products if products is not None else [],
        "year_range": year_range if year_range is not None else []
    }

@app.callback(
    Output("bar-top-areas", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_top_areas(validated_filters, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    # filter by year range
    if validated_filters and "year_range" in validated_filters and validated_filters["year_range"] and "Year" in dfl.columns:
        start, end = validated_filters["year_range"]
        mask = dfl["Year"].dt.year.between(start, end)
        dfl = dfl.loc[mask]

    # filter by products if provided
    if validated_filters and "products" in validated_filters and validated_filters["products"]:
        dfl = dfl.loc[dfl["Product"].isin(validated_filters["products"])]

    if dfl.empty or "Country" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig
    agg = dfl.groupby("Country")["Value"].sum().nlargest(10)
    fig = px.bar(x=agg.values, y=agg.index, orientation="h",
                 labels={"x": "Total Quantity Produced", "y": "Countries"},
                 title="Top 10 Countries by Quantity Produced")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=120))
    return fig


@app.callback(
    Output("bar-top-items", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_top_items(validated_filters, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    if validated_filters and "year_range" in validated_filters and validated_filters["year_range"] and "Year" in dfl.columns:
        start, end = validated_filters["year_range"]
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    if validated_filters and "countries" in validated_filters and validated_filters["countries"]:
        dfl = dfl.loc[dfl["Country"].isin(validated_filters["countries"])]

    if dfl.empty or "Product" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig
    agg = dfl.groupby("Product")["Value"].sum().nlargest(10)
    fig = px.bar(x=agg.index, y=agg.values,
                 labels={"x": "Products", "y": "Total Quantity Produced"},
                 title="Top 10 Products by Quantity Produced")
    fig.update_layout(xaxis={'tickangle': 45}, margin=dict(b=100))  # Rotation des étiquettes pour la lisibilité
    return fig


@app.callback(
    Output("ts-top-areas", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_time_series(validated_filters, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty or "Year" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No time-series data")
        return fig

    # filter quickly
    if validated_filters and "year_range" in validated_filters and validated_filters["year_range"]:
        start, end = validated_filters["year_range"]
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    if validated_filters and "products" in validated_filters and validated_filters["products"]:
        dfl = dfl.loc[dfl["Product"].isin(validated_filters["products"])]

    selected_countries = validated_filters.get("countries", []) if validated_filters else []
    if not selected_countries:
        # default to top 5 countries by total in filtered data
        totals = dfl.groupby("Country")["Value"].sum().nlargest(5)
        selected_countries = list(totals.index)

    dfl = dfl.loc[dfl["Country"].isin(selected_countries)]
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig
    ts = dfl.groupby([dfl["Year"].dt.year.rename("Year"), "Country"])["Value"].sum().reset_index()
    ts["Year"] = pd.to_datetime(ts["Year"].astype(int), format="%Y")
    # Use the canonical 'Value' column for the y-axis
    fig = px.line(ts, x="Year", y="Value", color="Country", markers=True,
                  title="Time series of Value for selected Countries")
    # improve tick formatting and layout for yearly data
    # place legend vertically on the right side and expand right margin to avoid overlap
    fig.update_layout(
        xaxis=dict(tickformat="%Y"),
        yaxis=dict(title_text="Value"),
        hovermode='x unified',
        margin=dict(t=40, l=60, r=160, b=40),
        legend=dict(
            title_text="Country",
            orientation='v',
            x=1.02,
            xanchor='left',
            y=0.5,
            yanchor='middle'
        )
    )
    return fig


@app.callback(
    Output("pie-area", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_pie(validated_filters, df_json):
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    # filter by year
    if validated_filters and "year_range" in validated_filters and validated_filters["year_range"]:
        start, end = validated_filters["year_range"]
        dfl = dfl.loc[dfl["Year"].dt.year.between(start, end)]

    # Get countries to display
    selected_countries = validated_filters.get("countries", []) if validated_filters else []
    if not selected_countries:
        # If no countries selected, show top 6 by total value
        totals = dfl.groupby("Country")["Value"].sum().nlargest(6)
        selected_countries = list(totals.index)

    if not selected_countries:
        fig = go.Figure()
        fig.update_layout(title="Select countries to display their production distribution")
        return fig

    # Create subplots grid
    n_countries = len(selected_countries)
    cols = min(3, n_countries)  # max 3 columns
    rows = (n_countries + cols - 1) // cols  # ceiling division

    fig = go.Figure()

    # Calculate position and size for each subplot
    width_per_pie = 0.85 / cols
    height_per_pie = 0.85 / rows

    for i, country in enumerate(selected_countries):
        # Calculate grid position
        row = i // cols
        col = i % cols

        # Calculate center position for this pie
        x_center = (col + 0.5) * (1 / cols)
        y_center = 1 - ((row + 0.5) * (1 / rows))

        # Get data for this country
        subset = dfl.loc[dfl["Country"] == country]
        data = subset.groupby("Product")["Value"].sum().reset_index()
        data = data.loc[data["Value"] > 0].sort_values("Value", ascending=False)

        if not data.empty:
            total = data["Value"].sum()
            thresh = total * 0.03
            big = data.loc[data["Value"] >= thresh]
            small_sum = data.loc[data["Value"] < thresh, "Value"].sum()
            labels = list(big["Product"])
            values = list(big["Value"])
            if small_sum > 0:
                labels.append("Other")
                values.append(small_sum)

            # Add pie trace
            fig.add_trace(go.Pie(
                values=values,
                labels=labels,
                name=country,
                title=country,
                domain=dict(
                    x=[x_center - width_per_pie/2, x_center + width_per_pie/2],
                    y=[y_center - height_per_pie/2, y_center + height_per_pie/2]
                ),
                showlegend=False,
                textposition='inside',
                textinfo='label+percent',
                hole=0.3
            ))

    fig.update_layout(
        title="Production distribution by Product for selected Countries",
        margin=dict(t=50, l=20, r=20, b=20),
        height=300 * rows,  # Adjust height based on number of rows
        grid=dict(rows=rows, columns=cols),
        showlegend=False
    )
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


# Theme support removed: DataTable has static light styling above


if __name__ == "__main__":
    # Set debug=False for faster startup in production; toggle True for development.
    app.run(debug=False, port=8050)
