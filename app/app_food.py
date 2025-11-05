from dash import Dash, dcc, html, Input, Output
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import math


base_path = os.path.dirname(__file__)
# Prefer cleaned file if present
clean_path = os.path.join(base_path, '..', 'data', 'clean', 'fao_clean.csv')
raw_path = os.path.join(base_path, '..', 'data', 'FAO.csv')


def load_and_prepare(clean_path=clean_path, raw_path=raw_path):
    """Load FAO data (prefer cleaned if exists), rename Y#### columns, melt to long format and return df, df_long."""
    if os.path.exists(clean_path):
        df = pd.read_csv(clean_path, encoding='utf-8')
    elif os.path.exists(raw_path):
        try:
            df = pd.read_csv(raw_path, encoding='utf-8')
        except Exception:
            df = pd.read_csv(raw_path, encoding='latin-1')
    else:
        raise FileNotFoundError(f"Neither {clean_path} nor {raw_path} exists")

    # Basic Unit cleanup (mirrors notebook logic)
    if 'Unit' in df.columns:
        try:
            df['Unit'] = df['Unit'].astype(str).str.replace('tonnes', '', case=False).str.strip()
            df['Unit'] = pd.to_numeric(df['Unit'], errors='coerce').astype('Int64')
        except Exception:
            # keep it as-is if something unexpected happens
            pass

    # Rename columns starting with 'Y' into year strings without leading 'Y'
    year_columns = [c for c in df.columns if isinstance(c, str) and c.startswith('Y') and c[1:].isdigit()]
    if year_columns:
        mapping = {c: c[1:] for c in year_columns}
        df = df.rename(columns=mapping)

    # Ensure year columns are numeric
    year_cols = [c for c in df.columns if isinstance(c, str) and c.isdigit()]
    if year_cols:
        df[year_cols] = df[year_cols].apply(pd.to_numeric, errors='coerce')

    # Melt to long format
    if year_cols:
        id_vars = [c for c in df.columns if c not in year_cols]
        df_long = df.melt(id_vars=id_vars, value_vars=year_cols, var_name='Year', value_name='Value')
        # Convert Year to datetime (year-only)
        df_long['Year'] = pd.to_datetime(df_long['Year'], format='%Y', errors='coerce')
    else:
        # if there are no year columns, produce an empty long frame with expected columns
        df_long = pd.DataFrame(columns=list(df.columns) + ['Year', 'Value'])

    return df, df_long


# Load data once at import time
try:
    df, df_long = load_and_prepare()
except Exception as e:
    print('Error loading data:', e)
    df = pd.DataFrame()
    df_long = pd.DataFrame()


# Initialize the Dash app
app = Dash(__name__)


def build_layout(df, df_long):
    # Compute controls options
    areas = sorted(df_long['Area'].dropna().unique()) if not df_long.empty else []
    items = sorted(df_long['Item'].dropna().unique()) if not df_long.empty else []

    # default years
    years = df_long['Year'].dt.year.dropna().astype(int) if not df_long.empty else pd.Series([], dtype=int)
    if not years.empty:
        min_year = int(years.min())
        max_year = int(years.max())
    else:
        min_year, max_year = 1961, 2013

    # default top areas
    total_by_area = df_long.groupby('Area')['Value'].sum().sort_values(ascending=False) if not df_long.empty else pd.Series()
    default_areas = list(total_by_area.head(5).index) if not total_by_area.empty else []

    return html.Div([
        html.H2('FAO Data — Interactive Dashboard'),
        html.Div([
            html.Div([
                html.Label('Areas (countries) — select up to 6'),
                dcc.Dropdown(id='area-dropdown', options=[{'label': a, 'value': a} for a in areas], value=default_areas, multi=True, placeholder='Select areas'),
                html.Br(),
                html.Label('Items — food items'),
                dcc.Dropdown(id='item-dropdown', options=[{'label': i, 'value': i} for i in items], value=[], multi=True, placeholder='Select items (optional)'),
                html.Br(),
                html.Label('Year range'),
                dcc.RangeSlider(id='year-range', min=min_year, max=max_year, value=[min_year, max_year], marks={y: str(y) for y in range(min_year, max_year+1, max(1, (max_year-min_year)//6))}),
            ], style={'width': '28%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'}),

            html.Div([
                dcc.Graph(id='bar-top-areas'),
                dcc.Graph(id='bar-top-items'),
            ], style={'width': '70%', 'display': 'inline-block', 'padding': '10px'}),
        ]),

        html.Div([
            dcc.Graph(id='ts-top-areas', style={'height': '420px'}),
        ], style={'width': '100%', 'padding': '10px'}),

        html.Div([
            html.Div(dcc.Graph(id='pie-area'), style={'width': '48%', 'display': 'inline-block'}),
        ], style={'padding': '10px'}),

        # hidden store with the long dataframe (as JSON) to avoid recomputing on every callback
        dcc.Store(id='df-long-store', data=df_long.to_json(date_format='iso', orient='split')),
    ])


app.layout = build_layout(df, df_long)


# Callbacks
def _load_df_from_store(df_json):
    """Safely read df_long from JSON stored in dcc.Store and ensure Year is datetime.
    Returns an empty DataFrame if input is invalid."""
    try:
        dfl = pd.read_json(df_json, orient='split')
    except Exception:
        return pd.DataFrame()
    # Ensure Year column exists and is datetime
    if 'Year' in dfl.columns:
        try:
            dfl['Year'] = pd.to_datetime(dfl['Year'], errors='coerce')
        except Exception:
            dfl['Year'] = pd.to_datetime(dfl['Year'].astype(str), errors='coerce')
    return dfl

@app.callback(
    Output('bar-top-areas', 'figure'),
    Input('item-dropdown', 'value'),
    Input('year-range', 'value'),
    Input('df-long-store', 'data')
)
def update_top_areas(selected_items, year_range, df_json):
    dfl = _load_df_from_store(df_json)
    if year_range:
        start, end = year_range
        if 'Year' in dfl.columns:
            dfl = dfl[(dfl['Year'].dt.year >= start) & (dfl['Year'].dt.year <= end)]
    if selected_items:
        dfl = dfl[dfl['Item'].isin(selected_items)]
    if dfl.empty or 'Area' not in dfl.columns or 'Value' not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    agg = dfl.groupby('Area')['Value'].sum().sort_values(ascending=False).head(10)
    if agg.empty:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    fig = px.bar(x=agg.values, y=agg.index, orientation='h', labels={'x': 'Total Value', 'y': 'Area'}, title='Top 10 Areas by total Value')
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    return fig


@app.callback(
    Output('bar-top-items', 'figure'),
    Input('area-dropdown', 'value'),
    Input('year-range', 'value'),
    Input('df-long-store', 'data')
)
def update_top_items(selected_areas, year_range, df_json):
    dfl = _load_df_from_store(df_json)
    if year_range:
        start, end = year_range
        if 'Year' in dfl.columns:
            dfl = dfl[(dfl['Year'].dt.year >= start) & (dfl['Year'].dt.year <= end)]
    if selected_areas:
        dfl = dfl[dfl['Area'].isin(selected_areas)]
    if dfl.empty or 'Item' not in dfl.columns or 'Value' not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    agg = dfl.groupby('Item')['Value'].sum().sort_values(ascending=False).head(10)
    if agg.empty:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    fig = px.bar(x=agg.values, y=agg.index, orientation='h', labels={'x': 'Total Value', 'y': 'Item'}, title='Top 10 Items by total Value')
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    return fig


@app.callback(
    Output('ts-top-areas', 'figure'),
    Input('area-dropdown', 'value'),
    Input('item-dropdown', 'value'),
    Input('year-range', 'value'),
    Input('df-long-store', 'data')
)
def update_time_series(selected_areas, selected_items, year_range, df_json):
    dfl = _load_df_from_store(df_json)
    if year_range:
        start, end = year_range
        if 'Year' in dfl.columns:
            dfl = dfl[(dfl['Year'].dt.year >= start) & (dfl['Year'].dt.year <= end)]
    if selected_items:
        dfl = dfl[dfl['Item'].isin(selected_items)]
    if selected_areas:
        dfl = dfl[dfl['Area'].isin(selected_areas)]
    else:
        # default to top 5 areas
        if dfl.empty or 'Area' not in dfl.columns or 'Value' not in dfl.columns:
            fig = go.Figure()
            fig.update_layout(title='No data for selected filters')
            return fig
        totals = dfl.groupby('Area')['Value'].sum().sort_values(ascending=False)
        selected_areas = list(totals.head(5).index)
        dfl = dfl[dfl['Area'].isin(selected_areas)]

    if dfl.empty or 'Year' not in dfl.columns or 'Area' not in dfl.columns or 'Value' not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    ts = dfl.groupby(['Year', 'Area'])['Value'].sum().reset_index()
    if ts.empty:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig
    fig = px.line(ts, x='Year', y='Value', color='Area', markers=True, title='Time series of Value for selected Areas')
    return fig


@app.callback(
    Output('pie-area', 'figure'),
    Input('area-dropdown', 'value'),
    Input('year-range', 'value'),
    Input('df-long-store', 'data')
)
def update_pie(selected_areas, year_range, df_json):
    dfl = _load_df_from_store(df_json)
    if year_range:
        start, end = year_range
        if 'Year' in dfl.columns:
            dfl = dfl[(dfl['Year'].dt.year >= start) & (dfl['Year'].dt.year <= end)]
    # choose first selected area for pie, or top area
    if selected_areas:
        area = selected_areas[0]
    else:
        totals = dfl.groupby('Area')['Value'].sum().sort_values(ascending=False)
        area = totals.index[0] if not totals.empty else None

    if not area:
        fig = go.Figure()
        fig.update_layout(title='No area available')
        return fig

    if dfl.empty or 'Area' not in dfl.columns or 'Item' not in dfl.columns or 'Value' not in dfl.columns:
        fig = go.Figure()
        fig.update_layout(title='No data for selected filters')
        return fig

    data = dfl[dfl['Area'] == area].groupby('Item')['Value'].sum().reset_index()
    data = data[data['Value'] > 0].sort_values('Value', ascending=False)
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=f'No data for {area}')
        return fig

    # group small slices into 'Other'
    total = data['Value'].sum()
    thresh = total * 0.03
    big = data[data['Value'] >= thresh]
    small_sum = data[data['Value'] < thresh]['Value'].sum()
    labels = list(big['Item'])
    values = list(big['Value'])
    if small_sum > 0:
        labels.append('Other')
        values.append(small_sum)

    fig = px.pie(values=values, names=labels, title=f'Production distribution by Item — {area}')
    return fig


if __name__ == '__main__':
    # Use the newer app.run API (replaces app.run_server)
    app.run(debug=True)