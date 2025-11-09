import os
from pathlib import Path
from typing import Tuple, List
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, dash_table, exceptions as dashexceptions
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from functools import lru_cache

# Set up data directories and paths
BASEDIR = Path(__file__).resolve().parent
DATADIR = BASEDIR.parent / "data"
CLEANDIR = DATADIR / "clean"
CLEANDIR.mkdir(parents=True, exist_ok=True)
CSVPATH = CLEANDIR / "fao_clean.csv"


@lru_cache(maxsize=1)
def load_prepare_data(csvpath: Path = CSVPATH, fallback_csv: Path = DATADIR / "FAO.csv"):
    if csvpath.exists():
        try:
            df = pd.read_csv(csvpath, low_memory=False, encoding="utf-8")
        except Exception:
            df = pd.read_csv(csvpath, low_memory=False, encoding="latin-1")
    elif fallback_csv.exists():
        try:
            df = pd.read_csv(fallback_csv, low_memory=False, encoding="utf-8")
        except Exception:
            df = pd.read_csv(fallback_csv, low_memory=False, encoding="latin-1")
    else:
        return pd.DataFrame(), pd.DataFrame(columns=["Year", "Value"])
    
    # Canonical column renaming for consistency
    rename_map = {}
    if "Area" in df.columns and "Country" not in df.columns:
        rename_map["Area"] = "Country"
    if "Item" in df.columns and "Product" not in df.columns:
        rename_map["Item"] = "Product"
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Identify year columns
    year_cols = [c for c in df.columns if isinstance(c, str) and (c.startswith("Y") and c[1:].isdigit())]
    if year_cols:
        df = df.rename(columns={c: c[1:] for c in year_cols})
    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]

    # Melt wide format to long format if years exist
    if year_cols:
        df[year_cols] = df[year_cols].apply(pd.to_numeric, errors='coerce')
        id_vars = [c for c in df.columns if c not in year_cols]
        df_long = df.melt(id_vars=id_vars, value_vars=year_cols, var_name="Year", value_name="Value")
        df_long["Year"] = pd.to_datetime(df_long["Year"].astype(str), format="%Y", errors='coerce')
        df_long["Value"] = pd.to_numeric(df_long["Value"], errors="coerce")
        df_long = df_long.dropna(subset=["Value"])
        if df_long.empty:
            df_long = pd.DataFrame(columns=list(df.columns) + ["Year", "Value"])
    else:
        df_long = pd.DataFrame(columns=list(df.columns) + ["Year", "Value"])
    return df, df_long

def light_clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # Strip spaces from string columns and clean units
    df = df.copy()
    obj_cols = df.select_dtypes(include="object").columns
    for c in obj_cols:
        df[c] = df[c].astype(str).str.strip()
    if "Unit" in df.columns:
        df["Unit"] = df["Unit"].astype(str).str.replace("tonnes", "", case=False).str.strip()
    return df

# Load data once at import for fast callbacks
try:
    WIDE_DF, LONG_DF = load_prepare_data()
except Exception as e:
    print("Data load error:", e)
    WIDE_DF, LONG_DF = pd.DataFrame(), pd.DataFrame()

# Precompute stats for optimization
PRECOMP = dict()
if not LONG_DF.empty and "Value" in LONG_DF.columns:
    try:
        PRECOMP["valuestats"] = LONG_DF["Value"].describe().round(2).to_dict()
    except Exception:
        PRECOMP["valuestats"] = {}
if not WIDE_DF.empty:
    year_cols = [c for c in WIDE_DF.columns if isinstance(c, str) and c.isdigit()]
    if year_cols:
        try:
            year_df = WIDE_DF[year_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            corr = year_df.corr()
            PRECOMP["corr"] = corr.to_json(orient="split")
        except Exception:
            PRECOMP["corr"] = None
    else:
        PRECOMP["corr"] = None
else:
    PRECOMP["corr"] = None

# Dash App initialisation and layout
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.icons.FONT_AWESOME, 
        dbc.themes.FLATLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap"
    ],
)
app.server = app.server

def build_layout(wide_df: pd.DataFrame, long_df: pd.DataFrame):
    # Build lists for dropdowns and sliders
    countries = sorted(long_df["Country"].dropna().unique()) if not long_df.empty and "Country" in long_df.columns else []
    products = sorted(long_df["Product"].dropna().unique()) if not long_df.empty and "Product" in long_df.columns else []
    if not long_df.empty and "Year" in long_df.columns:
        years = long_df["Year"].dt.year.dropna().astype(int)
        minyear, maxyear = int(years.min()), int(years.max())
    else:
        minyear, maxyear = 1961, 2013

    default_countries = list(long_df.groupby("Country")["Value"].sum().nlargest(5).index) if not long_df.empty and "Country" in long_df.columns else []
    initial_filters = {
        "countries": default_countries,
        "products": [],
        "yearrange": [minyear, maxyear]
    }
    # Page layout: sidebar + main panel
    layout = html.Div([
        html.Div([
            html.H2("FAO FOOD DASHBOARD", style={"margin": 0, "textAlign": "center", "fontSize": "32px", "fontWeight": "700"}),
        ], style={"padding": "20px", "border-bottom": "1px solid #dee2e6", "display": "flex", "justifyContent": "center"}),
        html.Div([
            # Sidebar filters
            html.Div([
                html.Label("Countries", style={"font-weight": "bold", "margin-bottom": "8px"}),
                dcc.Dropdown(
                    id="area-dropdown",
                    options=[{"label": c, "value": c} for c in countries],
                    value=default_countries,
                    multi=True,
                    placeholder="Select countries",
                    style={"margin-bottom": "16px"}
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
                    min=minyear, max=maxyear,
                    value=[minyear, maxyear],
                    marks={str(y): str(y) for y in range(minyear, maxyear + 1, max(1, (maxyear - minyear) // 6))},
                    className="mt-2"
                ),
                html.Div(
                    dbc.Button("Apply filters", id="apply-filters-btn", color="primary", className="w-100 mt-4", style={"fontWeight": 600, "fontSize": "16px"}),
                    style={"margin-top": "20px"}
                ),
            ], style={
                "background-color": "white", "padding": "20px", "border-radius": "8px", "box-shadow": "0 2px 4px rgba(0,0,0,0.1)", "color": "#212529", "width": "25%", "margin-right": "2%"
            }),
            # Main graph panel
            html.Div([
                html.Div([
                    html.Div([
                        dcc.Graph(id="bar-top-areas", config={"displayModeBar": False}, style={"height": "400px", "width": "100%"}),
                        html.P(
                            "This chart displays the 10 countries that produce the highest quantities of the selected food products during the chosen period. The aim is to identify the world's largest producers to facilitate comparison between countries.",
                            style={"margin-bottom": "22px", "font-size": "1rem", "color": "#555"}
                        ),
                    ], style={"width": "50%", "padding": "10px"}),
                    html.Div([
                        dcc.Graph(id="bar-top-items", config={"displayModeBar": False}, style={"height": "400px", "width": "100%"}),
                        html.P(
                            "This graph shows the 10 most produced products according to the selected filters. It allows you to see which foods are the most numerous in the analyzed database.",
                            style={"margin-bottom": "22px", "font-size": "1rem", "color": "#555"}
                        ),
                    ], style={"width": "50%", "padding": "10px"}),
                ], style={"display": "flex", "margin-bottom": "20px"}),
                html.Div([
                    dcc.Graph(id="ts-top-areas", config={"displayModeBar": False}, style={"height": "400px", "width": "100%"}),
                    html.P(
                        "This curve shows the evolution over time of production in the selected countries. It highlights trends, progress, or stagnation over several years.",
                        style={"margin-bottom": "22px", "font-size": "1rem", "color": "#555"}
                    )
                ], style={"padding": "10px", "margin-bottom": "20px"}),
                html.Div([
                    dcc.Graph(id="pie-area", config={"displayModeBar": False}, style={"height": "800px", "width": "100%"}),
                    html.P(
                        "This pie chart illustrates the distribution of production by product within each selected country. It is useful for visualizing the diversity or specialization of each country.",
                        style={"margin-bottom": "12px", "font-size": "1rem", "color": "#555"}
                    )
                ], style={"padding": "10px"}),
                html.Div([
                    dcc.Graph(id="corr-heatmap", config={"displayModeBar": False}, style={"height": "400px", "width": "75%"}),
                    html.P(
                        "The correlation matrix indicates the extent to which annual production varies between different products or countries. The closer the color is to dark blue, the stronger the correlation (positive or negative); white indicates no correlation.",
                        style={"margin-bottom": "12px", "font-size": "1rem", "color": "#555"}
                    )
                ], style={"width": "73%", "background-color": "white", "border-radius": "8px",
                          "box-shadow": "0 2px 4px rgba(0,0,0,0.1)", "padding": "20px"}),
                html.Div([
            dash_table.DataTable(id='stats-table',
                                 columns=[{"name": k, "id": k} for k in ['stat', 'value']],
                                 data=[],
                                 style_table={"overflowX": "auto"},
                                 style_cell={"textAlign": "left", "color": "#212529", "backgroundColor": "white"},
                                 style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold", "color": "#212529"},
                                 style_data={"backgroundColor": "white", "color": "#212529"}
                                 )
        ], style={"padding": "12px", "width": "100%"})
            ], style={"width": "73%", "background-color": "white", "border-radius": "8px",
                      "box-shadow": "0 2px 4px rgba(0,0,0,0.1)", "padding": "20px"})
        ], style={"display": "flex", "padding": "20px", "backgroundColor": "#f8f9fa"}),
        dcc.Store(id="df-long-store", data=LONG_DF.to_json(date_format='iso', orient='split')),
        dcc.Store(id="precomp-store", data=PRECOMP),
        dcc.Store(id="validated-filters", data=initial_filters)
    ], style={"fontFamily": "Inter, sans-serif", "backgroundColor": "#f8f9fa"})
    return layout

app.layout = build_layout(WIDE_DF, LONG_DF)

def df_from_store(df_json) -> pd.DataFrame:
    # Reconstruct DataFrame from JSON store
    try:
        dfl = pd.read_json(df_json, orient='split')
    except Exception:
        return pd.DataFrame()
    if "Year" in dfl.columns:
        dfl["Year"] = pd.to_datetime(dfl["Year"], errors="coerce")
    return dfl

# Callback: Update filters when button clicked
@app.callback(
    Output("validated-filters", "data"),
    Input("apply-filters-btn", "n_clicks"),
    State("area-dropdown", "value"),
    State("item-dropdown", "value"),
    State("year-range", "value"),
)
def update_validated_filters(n_clicks, countries, products, yearrange):
    # Update the validated filters on filter button click
    if n_clicks is None:
        raise dashexceptions.PreventUpdate
    return {
        "countries": countries if countries is not None else [],
        "products": products if products is not None else [],
        "yearrange": yearrange if yearrange is not None else []
    }

@app.callback(
    Output("bar-top-areas", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_top_areas(validated_filters, df_json):
    # Generate bar chart for top 10 countries by total quantity produced
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    mask = pd.Series([True] * len(dfl))
    if validated_filters and "yearrange" in validated_filters and "Year" in dfl.columns:
        start, end = validated_filters["yearrange"]
        mask &= dfl["Year"].dt.year.between(start, end)
    if validated_filters and "products" in validated_filters and validated_filters["products"]:
        mask &= dfl["Product"].isin(validated_filters["products"])

    dfl = dfl[mask]
    if dfl.empty or "Country" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig

    agg = dfl.groupby("Country")["Value"].sum().nlargest(10)
    fig = px.bar(
        x=agg.values,
        y=agg.index,
        orientation="h",
        labels={"x": "Total Quantity Produced", "y": "Countries"},
        title="Top 10 Countries by Quantity Produced"
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=120))
    return fig

@app.callback(
    Output("bar-top-items", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_top_items(validated_filters, df_json):
    # Generate bar chart for top 10 products by total quantity produced
    dfl = df_from_store(df_json)
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available")
        return fig

    mask = pd.Series([True] * len(dfl))
    if validated_filters and "yearrange" in validated_filters and "Year" in dfl.columns:
        start, end = validated_filters["yearrange"]
        mask &= dfl["Year"].dt.year.between(start, end)
    if validated_filters and "countries" in validated_filters and validated_filters["countries"]:
        mask &= dfl["Country"].isin(validated_filters["countries"])

    dfl = dfl[mask]
    if dfl.empty or "Product" not in dfl.columns or "Value" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig

    agg = dfl.groupby("Product")["Value"].sum().nlargest(10)
    fig = px.bar(
        x=agg.index,
        y=agg.values,
        labels={"x": "Products", "y": "Total Quantity Produced"},
        title="Top 10 Products by Quantity Produced"
    )
    fig.update_layout(xaxis_tickangle=45, margin=dict(b=100))
    return fig

@app.callback(
    Output("ts-top-areas", "figure"),
    Input("validated-filters", "data"),
    Input("df-long-store", "data")
)
def update_time_series(validated_filters, df_json):
    # Generate time series for selected countries/products
    dfl = df_from_store(df_json)
    if dfl.empty or "Year" not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title="No time-series data")
        return fig

    mask = pd.Series([True] * len(dfl))
    if validated_filters and "yearrange" in validated_filters:
        start, end = validated_filters["yearrange"]
        mask &= dfl["Year"].dt.year.between(start, end)
    if validated_filters and "products" in validated_filters and validated_filters["products"]:
        mask &= dfl["Product"].isin(validated_filters["products"])

    selected_countries = validated_filters.get("countries", []) if validated_filters else []
    if not selected_countries:
        totals = dfl.groupby("Country")["Value"].sum().nlargest(5)
        selected_countries = list(totals.index)
    mask &= dfl["Country"].isin(selected_countries)

    dfl = dfl[mask]
    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="No data for selected filters")
        return fig
    ts = dfl.groupby([dfl["Year"].dt.year.rename("Year"), "Country"])["Value"].sum().reset_index()
    ts["Year"] = pd.to_datetime(ts["Year"].astype(int), format="%Y")

    fig = px.line(
        ts, x="Year", y="Value", color="Country", markers=True,
        title="Time series of Value for selected Countries"
    )
    fig.update_layout(
        xaxis=dict(tickformat="%Y"),
        yaxis=dict(title_text="Value"),
        hovermode="x unified",
        margin=dict(t=40, l=60, r=160, b=40),
        legend=dict(title_text="Country", orientation="v", x=1.02, xanchor="left", y=0.5, yanchor="middle")
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

    mask = pd.Series([True] * len(dfl))
    if validated_filters and "yearrange" in validated_filters:
        start, end = validated_filters["yearrange"]
        mask &= dfl["Year"].dt.year.between(start, end)

    selected_countries = validated_filters.get("countries", []) if validated_filters else []
    if not selected_countries:
        totals = dfl.groupby("Country")["Value"].sum().nlargest(6)
        selected_countries = list(totals.index)
    mask &= dfl["Country"].isin(selected_countries)
    dfl = dfl[mask]

    if dfl.empty:
        fig = go.Figure()
        fig.update_layout(title="Select countries to display their production distribution")
        return fig

    n_countries = len(selected_countries)
    cols = min(3, n_countries)
    rows = (n_countries + cols - 1) // cols

    # Add spacing between graphs!
    fig = make_subplots(
        rows=rows, cols=cols, specs=[[{"type": "pie"}]*cols for _ in range(rows)],
        horizontal_spacing=0.10, vertical_spacing=0.18
    )

    for i, country in enumerate(selected_countries):
        row = (i // cols) + 1
        col = (i % cols) + 1
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
            fig.add_trace(go.Pie(labels=labels, values=values, name=country, textinfo="label+percent", hole=0.3), row=row, col=col)

    fig.update_layout(
        title="Production distribution by Product for selected Countries",
        showlegend=False,
        height=350*rows,  # ou 400*rows si tu veux plus d'espace
        margin=dict(t=40, b=40)
    )

    return fig


@app.callback(
    Output("corr-heatmap", "figure"),
    Input("precomp-store", "data")
)
def update_corr(precomp):
    # Display correlation matrix between years/products (if available)
    if not precomp or not precomp.get("corr"):
        fig = go.Figure()
        fig.update_layout(title="No correlation matrix available")
        return fig
    try:
        corrdf = pd.read_json(precomp.get("corr"), orient="split")
        fig = px.imshow(
            corrdf.values, x=corrdf.columns, y=corrdf.index,
            color_continuous_scale="RdBu", zmin=-1, zmax=1,
            title="Correlation between years"
        )
        fig.update_layout(margin=dict(l=40, r=20, t=40, b=40))
        return fig
    except Exception:
        fig = go.Figure()
        fig.update_layout(title="Error building correlation heatmap")
        return fig

@app.callback(
    Output('stats-table', 'data'),
    Input('precomp-store', 'data')
)
def update_stats_table(precomp):
    stats = precomp.get('valuestats') if precomp else {}
    if not stats:
        return []
    rows = []
    for k, v in stats.items():
        rows.append({'stat': k, 'value': v})
    return rows


if __name__ == "__main__":
    app.run(debug=False, port=8050)
