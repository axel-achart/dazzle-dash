# Import necessary libraries
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table

# Load data
# Make sure this path is correct for your setup
try:
    df = pd.read_csv('data/Life Expectancy Data with IDH.csv')
except FileNotFoundError:
    print("="*50)
    print("ERROR: Could not find 'data/Life Expectancy Data with IDH.csv'")
    print("Please make sure the data file is in a folder named 'data' in the same directory as this script.")
    print("="*50)
    # Create a dummy dataframe to allow the app to load
    df = pd.DataFrame({
        'country': ['USA', 'USA', 'Canada', 'Canada'],
        'year': [2000, 2001, 2000, 2001],
        'life_expectancy': [76.8, 77.0, 79.1, 79.4],
        'IDH': [0.88, 0.89, 0.89, 0.90],
        'GDP': [40000, 41000, 38000, 39000],
        'population': [282, 285, 30, 31]
    })


# Ensure numeric conversions
df['life_expectancy'] = pd.to_numeric(df['life_expectancy'], errors='coerce')
df['year'] = pd.to_numeric(df['year'], errors='coerce').astype(int)

# Set base year for color scaling
BASE_year = 2000

# Get sorted unique years including 1999 (for aggregate)
years = sorted(df['year'].unique().tolist())
if 1999 not in years:
    years.insert(0, 1999) # Add 1999 to the beginning

# Get sorted unique countries and add 'World' (for aggregate)
countries = sorted(df['country'].unique().tolist())
countries.insert(0, 'World') # Add 'World' to the beginning

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
            {'label': 'Life Expectancy', 'value': 'life_expectancy'},
            {'label': 'IDH', 'value': 'IDH'},
        ],
        value='life_expectancy'
    ),
    # Dropdown for years
    dcc.Dropdown(
        id='year-dropdown',
        options=[{'label': str(year) + (' (All Years Average)' if year == 1999 else ''), 
                  'value': year} for year in years],
        value=max(years), # Default to the latest single year
        style={'margin': '10px 0'}
    ),
    dcc.Graph(id='global-graph'),
    
    # Drilldown: country Profile
    html.H2('Country/Global Profile'),
    dcc.Dropdown(
        id='country-dropdown',
        options=[{'label': i + (' (Global Average)' if i == 'World' else ''), 
                  'value': i} for i in countries],
        value='World' # Default to 'World'
    ),
    html.Div(id='country-profile'),
    
    # Factor Analysis & Visualization
    html.H2('Factor Analysis & Visualization (Based on Full Dataset)'),
    dcc.Graph(id='correlation-graph'),
    # Right-hand side: show factor list as a small horizontal bar chart (captures hover)
    dcc.Graph(id='factors-list-graph', style={'height': '300px'}),
    html.Div(id='factor-details'),
    
    # Data Table
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

# === CALLBACK 1: Update global graph ===
# This callback now handles the '1999' aggregate year
@app.callback(
    Output('global-graph', 'figure'),
    [Input('indicator-dropdown', 'value'),
     Input('year-dropdown', 'value')]
)
def update_global_graph(indicator, year):
    # Use BASE_year for the color range so gradient is stable
    base_df = df[df['year'] == BASE_year]
    
    # Try to get values for the chosen indicator
    base_vals = pd.to_numeric(base_df.get(indicator, pd.Series()), errors='coerce').dropna()
    all_vals = pd.to_numeric(df.get(indicator, pd.Series()), errors='coerce').dropna()

    vmin = None
    vmax = None

    if not base_vals.empty:
        vmin = float(base_vals.min())
        vmax = float(base_vals.max())
    elif not all_vals.empty:
        # Fallback: compute across whole dataset
        vmin = float(all_vals.min())
        vmax = float(all_vals.max())

    if year == 1999:  # Special case for aggregated view
        # Aggregate data across all years for each country
        # Only aggregate numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if indicator not in numeric_cols:
            return go.Figure().update_layout(title=f"'{indicator}' is not a numeric column.")
            
        agg_df = df.groupby('country')[indicator].mean().reset_index()
        filtered_df = agg_df
        title = f'{indicator} by Country (All Years Aggregated)'
    else:
        filtered_df = df[df['year'] == year]
        title = f'{indicator} by Country ({year})'

    # Create the choropleth figure
    if vmin is not None and vmax is not None and vmin != vmax:
        fig = px.choropleth(
            filtered_df,
            locations='country',
            locationmode='country names',
            color=indicator,
            hover_name='country',
            color_continuous_scale='Viridis',
            range_color=(vmin, vmax),
            title=title
        )
    else:
        # No valid numeric range found or indicator is missing
        fig = px.choropleth(
            filtered_df,
            locations='country',
            locationmode='country names',
            color=indicator,
            hover_name='country',
            color_continuous_scale='Viridis',
            title=title
        )

    fig.update_layout(
        coloraxis_colorbar=dict(title=indicator),
        title_x=0.5,  # Center the title
        margin=dict(t=50)  # Add some top margin for the title
    )
    return fig


# === CALLBACK 2: Update country profile ===
# This callback now handles 'World' and '1999' aggregates
@app.callback(
    Output('country-profile', 'children'),
    [Input('country-dropdown', 'value'),
     Input('year-dropdown', 'value')]
)
def update_country_profile(country, year):
    profile = []
    
    # Select only numeric columns for aggregation
    numeric_cols = df.select_dtypes(include=['number']).columns
    # Exclude 'year' from the list of columns to average
    numeric_cols_no_year = numeric_cols.drop('year', errors='ignore')

    if country == 'World':
        if year == 1999:
            # Case 4: Global average, all years
            agg_data = df[numeric_cols_no_year].mean()
            title = "Global Average (All Years)"
        else:
            # Case 3: Global average, specific year
            agg_data = df[df['year'] == year][numeric_cols_no_year].mean()
            title = f"Global Average ({year})"
        
        profile.append(html.H4(title))
        if agg_data.empty or agg_data.isnull().all():
            profile.append(html.P("No data available."))
            return profile
            
        for col in agg_data.index:
             profile.append(html.P(f'{col}: {agg_data[col]:.2f}'))

    else: # Specific country
        if year == 1999:
            # Case 2: Specific country, all years
            agg_data = df[df['country'] == country][numeric_cols_no_year].mean()
            title = f"{country} Average (All Years)"
            
            profile.append(html.H4(title))
            if agg_data.empty or agg_data.isnull().all():
                profile.append(html.P("No data available."))
                return profile

            for col in agg_data.index:
                profile.append(html.P(f'{col}: {agg_data[col]:.2f}'))
        else:
            # Case 1: Specific country, specific year (Original logic)
            country_df = df[(df['country'] == country) & (df['year'] == year)]
            title = f"{country} Profile ({year})"
            
            profile.append(html.H4(title))
            if country_df.empty:
                profile.append(html.P("No data available."))
                return profile
                
            # Use .iloc[0] to get the single row as a Series
            row_data = country_df.iloc[0]
            for col in row_data.index:
                if col not in ['country', 'year']: # Filter out non-data cols
                    val = row_data[col]
                    profile.append(html.P(f'{col}: {val}'))
    return profile


# === CALLBACK 3: Update correlation graph ===
# This callback is independent of year/country and remains unchanged
@app.callback(
    Output('correlation-graph', 'figure'),
    [Input('indicator-dropdown', 'value'),
     Input('factors-list-graph', 'hoverData')]
)
def update_correlation_graph(indicator, hoverData):
    # compute numeric correlations only
    numeric_df = df.select_dtypes(include=['number'])
    if indicator not in numeric_df.columns:
        return go.Figure(layout={'title': f"Cannot correlate non-numeric '{indicator}'"})

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
        title=f'Correlation with {indicator} (Full Dataset)',
        xaxis_title='Correlation',
        margin=dict(l=150, r=10, t=40, b=20),
        yaxis={'autorange': 'reversed'},
        height=600
    )

    return fig

# === CALLBACK 4: Update factors list graph ===
# This callback is independent of year/country and remains unchanged
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

# === CALLBACK 5: Update factor details ===
# This callback is independent of year/country and remains unchanged
@app.callback(
    Output('factor-details', 'children'),
    [Input('indicator-dropdown', 'value')]
)
def update_factor_details(indicator):
    details = []
    details.append(html.P(f'Factor Details: {indicator}'))
    return details

# === CALLBACK 6: Update data table ===
# This callback now uses 'World' and '1999' to expand the filter
@app.callback(
    Output('data-table', 'data'),
    [Input('country-dropdown', 'value'),
     Input('year-dropdown', 'value')]
)
def update_data_table(country, year):
    if country == 'World':
        if year == 1999:
            # Case 4: All countries, all years
            filtered_df = df
        else:
            # Case 3: All countries, specific year
            filtered_df = df[df['year'] == year]
    else: # Specific country
        if year == 1999:
            # Case 2: Specific country, all years
            filtered_df = df[df['country'] == country]
        else:
            # Case 1: Specific country, specific year (Original)
            filtered_df = df[(df['country'] == country) & (df['year'] == year)]
    
    return filtered_df.to_dict('records')


# Run the app
if __name__ == '__main__':
    app.run(debug=True)