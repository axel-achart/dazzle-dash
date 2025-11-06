# Import necessary libraries
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table

# Load data
df = pd.read_csv('data/Life Expectancy Data with IDH and Imputed Values.csv')

# Ensure numeric conversions
df['Life expectancy '] = pd.to_numeric(df['Life expectancy '], errors='coerce')
df['Year'] = pd.to_numeric(df['Year'], errors='coerce').astype(int)

# Set base year for color scaling
BASE_YEAR = 2000

# Get sorted unique years including 1999 if not already present
years = sorted(df['Year'].unique().tolist())
if 1999 not in years:
    years.append(1999)
years.sort()

# Create a Dash app
app = dash.Dash(__name__)

# Define layout
app.layout = html.Div([
    html.H1('Health Data Dashboard'),
    html.Hr(),
    
    # Global Data Overview
    html.H2('Global Data Overview'),
    dcc.Dropdown(
        id='indicator-dropdown',
        options=[
            {'label': 'Life Expectancy', 'value': 'Life expectancy '},
            {'label': 'IDH', 'value': 'IDH'},
        ],
        value='Life expectancy '
    ),
    # Replace slider with dropdown for years
    dcc.Dropdown(
        id='year-dropdown',
        options=[{'label': str(year) + (' (Aggregate)' if year == 1999 else ''), 
                 'value': year} for year in years],
        value=max(years),
        style={'margin': '10px 0'}
    ),
    dcc.Graph(id='global-graph'),
    
    # Drilldown: Country Profile
    html.H2('Country Profile'),
    dcc.Dropdown(
        id='country-dropdown',
        options=[{'label': i + (' (Global Average)' if i == 'World' else ''), 
                 'value': i} for i in sorted(df['Country'].unique())],
        value=df['Country'].unique()[0]
    ),
    html.Div(id='country-profile'),
    
    # Factor Analysis & Visualization
    html.H2('Factor Analysis & Visualization'),
    dcc.Graph(id='correlation-graph'),
    # Right-hand side: show factor list as a small horizontal bar chart (captures hover)
    dcc.Graph(id='factors-list-graph', style={'height': '300px'}),
    html.Div(id='factor-details'),
    
    # Data Table
    html.H2('Data Table'),
    dash_table.DataTable(
        id='data-table',
        columns=[{'name': i, 'id': i} for i in df.columns],
        data=df.to_dict('records')
    )
])

# Update global graph - modify the callback inputs
@app.callback(
    Output('global-graph', 'figure'),
    [Input('indicator-dropdown', 'value'),
     Input('year-dropdown', 'value')]
)
def update_global_graph(indicator, year):
    # Use BASE_YEAR for the color range so gradient is stable
    latest_df = df[df['Year'] == BASE_YEAR]
    # try to coerce to numeric (handles columns that may be non-numeric)
    latest_vals = pd.to_numeric(latest_df.get(indicator, pd.Series()), errors='coerce')
    vmin = None
    vmax = None
    if not latest_vals.empty and latest_vals.notna().any():
        vmin = float(latest_vals.min())
        vmax = float(latest_vals.max())
    else:
        # Fallback: compute across whole dataset for that indicator
        all_vals = pd.to_numeric(df.get(indicator, pd.Series()), errors='coerce')
        if not all_vals.empty and all_vals.notna().any():
            vmin = float(all_vals.min())
            vmax = float(all_vals.max())

    filtered_df = df[df['Year'] == year]
    # If we have valid vmin/vmax, pass them to range_color to lock the gradient
    if vmin is not None and vmax is not None and vmin != vmax:
        fig = px.choropleth(
            filtered_df,
            locations='Country',
            locationmode='country names',
            color=indicator,
            hover_name='Country',
            color_continuous_scale='Viridis',
            range_color=(vmin, vmax)
        )
    else:
        # No valid numeric range found: let plotly choose automatically
        fig = px.choropleth(
            filtered_df,
            locations='Country',
            locationmode='country names',
            color=indicator,
            hover_name='Country',
            color_continuous_scale='Viridis'
        )

    fig.update_layout(coloraxis_colorbar=dict(title=indicator))
    return fig

# Update country profile
@app.callback(
    Output('country-profile', 'children'),
    [Input('country-dropdown', 'value'),
     Input('year-dropdown', 'value')]  # Changed from year-slider
)
def update_country_profile(country, year):
    country_df = df[(df['Country'] == country) & (df['Year'] == year)]
    profile = []
    for col in country_df.columns:
        if col != 'Country' and col != 'Year':
            # guard against empty selection
            val = country_df[col].values[0] if not country_df.empty else "N/A"
            profile.append(html.P(f'{col}: {val}'))
    return profile

# Update correlation graph
@app.callback(
    Output('correlation-graph', 'figure'),
    [Input('indicator-dropdown', 'value'),
     Input('factors-list-graph', 'hoverData')]
)
def update_correlation_graph(indicator, hoverData):
    # compute numeric correlations only
    numeric_df = df.select_dtypes(include=['number'])
    if indicator not in numeric_df.columns:
        return go.Figure()

    corrs = numeric_df.corr()[indicator].drop(index=indicator).sort_values(ascending=False)
    labels = corrs.index.tolist()
    values = corrs.values.tolist()

    # Build horizontal bar chart so all labels and values are visible
    colors = ['#2ca02c' if v >= 0 else '#d62728' for v in values]  # green for positive, red for negative
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation='h',
            marker_color=colors,
            text=[f"{v:.3f}" for v in values],
            textposition='auto',
            hovertemplate='%{y}: %{x:.3f}<extra></extra>'
        )
    )

    fig.update_layout(
        title=f'Correlation with {indicator}',
        xaxis_title='Correlation',
        margin=dict(l=150, r=10, t=40, b=20),
        yaxis={'autorange': 'reversed'},
        height=600
    )

    return fig

# New callback: render the right-hand factors list as a horizontal bar chart (hoverable)
@app.callback(
    Output('factors-list-graph', 'figure'),
    [Input('indicator-dropdown', 'value')]
)
def update_factors_list_graph(indicator):
    numeric_df = df.select_dtypes(include=['number'])
    if indicator not in numeric_df.columns:
        return go.Figure()

    corrs = numeric_df.corr()[indicator].drop(index=indicator).sort_values(ascending=False)
    # Build horizontal bar chart so hovering shows the factor label (y)
    fig = px.bar(
        x=corrs.values,
        y=corrs.index,
        orientation='h',
        labels={'x': 'Correlation', 'y': 'Factor'},
        text_auto='.2f'
    )
    fig.update_layout(margin=dict(l=100, r=10, t=20, b=20), yaxis={'autorange':'reversed'})
    fig.update_traces(marker_color='lightslategray', hovertemplate='%{y}: %{x:.3f}<extra></extra>')
    return fig

# Update factor details (kept for textual info)
@app.callback(
    Output('factor-details', 'children'),
    [Input('indicator-dropdown', 'value')]
)
def update_factor_details(indicator):
    details = []
    details.append(html.P(f'Factor Details: {indicator}'))
    return details

# Update data table - modify the callback inputs
@app.callback(
    Output('data-table', 'data'),
    [Input('country-dropdown', 'value'),
     Input('year-dropdown', 'value')]  # Changed from year-slider
)
def update_data_table(country, year):
    filtered_df = df[(df['Country'] == country) & (df['Year'] == year)]
    return filtered_df.to_dict('records')

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
