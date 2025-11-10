import os
import pandas as pd
from dash import dcc, html, dash_table, Input, Output
import plotly.express as px
import plotly.graph_objects as go

# ----------------------
# DATA LOADING
# ----------------------
def load_data():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
    CSV_WHO = os.path.join(DATA_DIR, "Life Expectancy Data with IDH.csv")
    try:
        df = pd.read_csv(CSV_WHO, low_memory=False)
    except FileNotFoundError:
        print("=" * 50)
        print("ERROR: Could not find 'data/Life Expectancy Data with IDH.csv'")
        print("Please make sure the data file is in a folder named 'data' at the root of your project.")
        print("=" * 50)
        # Dummy data (structure must match the rest of the code)
        df = pd.DataFrame({
            'country': ['USA', 'USA', 'Canada', 'Canada'],
            'year': [2000, 2001, 2000, 2001],
            'life_expectancy': [76.8, 77.0, 79.1, 79.4],
            'IDH': [0.88, 0.89, 0.89, 0.90],
            'GDP': [40000, 41000, 38000, 39000],
            'population': [282, 285, 30, 31]
        })

    df['life_expectancy'] = pd.to_numeric(df['life_expectancy'], errors='coerce')
    df['year'] = pd.to_numeric(df['year'], errors='coerce').astype(int)
    return df

DF_WHO = load_data()


# ----------------------
# LAYOUT FUNCTION
# ----------------------
def get_layout():
    df = DF_WHO

    print("Data loaded for dashboard:", df.head)

    BASE_year = 2000
    years = sorted(df['year'].unique().tolist())
    if 1999 not in years:
        years.insert(0, 1999)

    countries = sorted(df['country'].unique().tolist())
    countries.insert(0, 'World')

    return html.Div([
        html.H1('Health Data Dashboard'),
        html.Hr(),

        html.H2('Global Data Overview'),
        dcc.Dropdown(
            id='indicator-dropdown',
            options=[
                {'label': 'Life Expectancy', 'value': 'life_expectancy'},
                {'label': 'IDH', 'value': 'IDH'},
            ],
            value='life_expectancy'
        ),
        dcc.Dropdown(
            id='year-dropdown',
            options=[{'label': str(year) + (' (All Years Average)' if year == 1999 else ''), 'value': year}
                     for year in years],
            value=max(years),
            style={'margin': '10px 0'}
        ),
        dcc.Graph(id='global-graph'),

        html.H2('Country/Global Profile'),
        dcc.Dropdown(
            id='country-dropdown',
            options=[{'label': i + (' (Global Average)' if i == 'World' else ''), 'value': i} for i in countries],
            value='World'
        ),
        html.Div(id='country-profile'),

        html.H2('Factor Analysis & Visualization (Based on Full Dataset)'),
        dcc.Graph(id='correlation-graph'),
        dcc.Graph(id='factors-list-graph', style={'height': '300px'}),
        html.Div(id='factor-details'),

        html.H2('Data Table'),
        dash_table.DataTable(
            id='data-table',
            columns=[{'name': i, 'id': i} for i in df.columns],
            data=df.to_dict('records'),
            page_size=10,
            sort_action='native',
            filter_action='native',
            style_table={'overflowX': 'auto'}
        )
    ])


# -----------------------
# CALLBACKS REGISTRATION
# -----------------------
def register_callbacks(app):
    df = DF_WHO

    BASE_year = 2000

    @app.callback(
        Output('global-graph', 'figure'),
        [Input('indicator-dropdown', 'value'),
         Input('year-dropdown', 'value')]
    )
    def update_global_graph(indicator, year):
        base_df = df[df['year'] == BASE_year]
        base_vals = pd.to_numeric(base_df.get(indicator, pd.Series()), errors='coerce').dropna()
        all_vals = pd.to_numeric(df.get(indicator, pd.Series()), errors='coerce').dropna()

        vmin, vmax = (base_vals.min(), base_vals.max()) if not base_vals.empty else (
            all_vals.min(), all_vals.max())

        if year == 1999:
            numeric_cols = df.select_dtypes(include=['number']).columns
            if indicator not in numeric_cols:
                return go.Figure().update_layout(title=f"'{indicator}' is not a numeric column.")
            filtered_df = df.groupby('country')[indicator].mean().reset_index()
            title = f'{indicator} by Country (All Years Aggregated)'
        else:
            filtered_df = df[df['year'] == year]
            title = f'{indicator} by Country ({year})'

        fig = px.choropleth(
            filtered_df,
            locations='country',
            locationmode='country names',
            color=indicator,
            hover_name='country',
            color_continuous_scale='Viridis',
            range_color=(vmin, vmax) if vmin != vmax else None,
            title=title
        )

        fig.update_layout(
            coloraxis_colorbar=dict(title=indicator),
            title_x=0.5,
            margin=dict(t=50)
        )
        return fig

    @app.callback(
        Output('country-profile', 'children'),
        [Input('country-dropdown', 'value'),
         Input('year-dropdown', 'value')]
    )
    def update_country_profile(country, year):
        profile = []
        numeric_cols = df.select_dtypes(include=['number']).columns.drop('year', errors='ignore')

        if country == 'World':
            if year == 1999:
                agg_data = df[numeric_cols].mean()
                title = "Global Average (All Years)"
            else:
                agg_data = df[df['year'] == year][numeric_cols].mean()
                title = f"Global Average ({year})"
        else:
            if year == 1999:
                agg_data = df[df['country'] == country][numeric_cols].mean()
                title = f"{country} Average (All Years)"
            else:
                row_data = df[(df['country'] == country) & (df['year'] == year)]
                title = f"{country} Profile ({year})"
                if row_data.empty:
                    return [html.H4(title), html.P("No data available.")]
                agg_data = row_data.iloc[0]

        profile.append(html.H4(title))
        for col in agg_data.index:
            if col not in ['country', 'year']:
                profile.append(html.P(f'{col}: {agg_data[col]:.2f}' if pd.notna(agg_data[col]) else f'{col}: N/A'))
        return profile

    @app.callback(
        Output('correlation-graph', 'figure'),
        [Input('indicator-dropdown', 'value'),
         Input('factors-list-graph', 'hoverData')]
    )
    def update_correlation_graph(indicator, hoverData):
        numeric_df = df.select_dtypes(include=['number'])
        if indicator not in numeric_df.columns:
            return go.Figure(layout={'title': f"Cannot correlate non-numeric '{indicator}'"})
        corrs = numeric_df.corr()[indicator].drop(index=indicator).sort_values(ascending=False)
        colors = ['#2ca02c' if v >= 0 else '#d62728' for v in corrs.values]
        fig = go.Figure(go.Bar(
            x=corrs.values,
            y=corrs.index,
            orientation='h',
            marker_color=colors,
            text=[f"{v:.3f}" for v in corrs.values],
            textposition='auto'
        ))
        fig.update_layout(title=f'Correlation with {indicator}', margin=dict(l=150))
        return fig

    @app.callback(
        Output('factors-list-graph', 'figure'),
        [Input('indicator-dropdown', 'value')]
    )
    def update_factors_list_graph(indicator):
        numeric_df = df.select_dtypes(include=['number'])
        if indicator not in numeric_df.columns:
            return go.Figure()
        corrs = numeric_df.corr()[indicator].drop(index=indicator).sort_values(ascending=False)
        fig = px.bar(
            x=corrs.values,
            y=corrs.index,
            orientation='h',
            labels={'x': 'Correlation', 'y': 'Factor'},
            text_auto='.2f'
        )
        fig.update_layout(margin=dict(l=100), yaxis={'autorange': 'reversed'})
        return fig

    @app.callback(
        Output('factor-details', 'children'),
        [Input('indicator-dropdown', 'value')]
    )
    def update_factor_details(indicator):
        return [html.P(f'Factor Details: {indicator}')]

    @app.callback(
        Output('data-table', 'data'),
        [Input('country-dropdown', 'value'),
         Input('year-dropdown', 'value')]
    )
    def update_data_table(country, year):
        if country == 'World':
            filtered_df = df if year == 1999 else df[df['year'] == year]
        else:
            filtered_df = df[df['country'] == country] if year == 1999 else df[
                (df['country'] == country) & (df['year'] == year)]
        return filtered_df.to_dict('records')

# ---------------------
# Optionnel : runner
# ---------------------
def run():
    import dash
    app = dash.Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run_server(debug=True)
