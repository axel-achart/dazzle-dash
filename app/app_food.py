from dash import *
import pandas as pd
import os
import plotly.express as px

base_path = os.path.dirname(__file__)
file_path = os.path.join(base_path, '..', 'data', 'FAO.csv')

# Load the dataset
try:
    df = pd.read_csv(file_path, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(file_path, encoding='latin1')

# Initialize the Dash app
app = Dash()

# Define the layout of the app
app.layout = [html.Div(children='Dashboard Food Transport Page'),
              dcc.Graph(figure=px.histogram(df, x='Area', y='Unit', histfunc='avg'))]




if __name__ == '__main__':
    app.run(debug=True)