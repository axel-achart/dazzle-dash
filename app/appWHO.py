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

# compute year bounds for slider marks
min_year = int(df['Year'].min())
max_year = int(df['Year'].max())

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
            {'label': 'IDH', 'value': 'IDH'},  # Assuming IDH is computed
        ],
        value='Life expectancy '
    ),
    dcc.Slider(
        id='year-slider',
        min=min_year,
        max=max_year,
        step=1,
        value=max_year,
        marks={y: str(y) for y in range(min_year, max_year + 1)}
    ),
    dcc.Graph(id='global-graph'),
    
    # Drilldown: Country Profile
    html.H2('Country Profile'),
    dcc.Dropdown(
        id='country-dropdown',
        options=[{'label': i, 'value': i} for i in df['Country'].unique()],
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

# Update global graph
@app.callback(
    Output('global-graph', 'figure'),
    [Input('indicator-dropdown', 'value'),
     Input('year-slider', 'value')]
)
def update_global_graph(indicator, year):
    # Always use the color range computed from the latest year so gradient is stable
    latest_df = df[df['Year'] == max_year]
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
     Input('year-slider', 'value')]
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

    # Determine hovered factor label from hoverData (bar chart returns point 'y')
    hovered_label = None
    if hoverData and 'points' in hoverData and len(hoverData['points']) > 0:
        p = hoverData['points'][0]
        # For horizontal bar chart we use 'y' as label; fallback to 'label' for robustness
        hovered_label = p.get('y') or p.get('label') or p.get('customdata')

    # Create 'pull' to emphasize hovered slice
    pull = [0.12 if (lbl == hovered_label) else 0 for lbl in labels]

    fig = go.Figure(data=[go.Pie(labels=labels, values=values, pull=pull, sort=False)])
    fig.update_traces(textinfo='percent+label', hoverinfo='label+value+percent')
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))

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

# Update data table
@app.callback(
    Output('data-table', 'data'),
    [Input('country-dropdown', 'value'),
     Input('year-slider', 'value')]
)
def update_data_table(country, year):
    filtered_df = df[(df['Country'] == country) & (df['Year'] == year)]
    return filtered_df.to_dict('records')

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
