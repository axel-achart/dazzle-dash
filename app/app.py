from dash import Dash, dcc, html, Output, Input

# Importe la fonction de layout de chaque dashboard !
from app.food.app_food import get_layout as layout_food
from app.flights.app_flights import get_layout as layout_flights
from app.who.app_who import get_layout as layout_who, register_callbacks as register_callbacks_who

def main():
    app = Dash(__name__, suppress_callback_exceptions=True)

    app.layout = html.Div([
        dcc.Tabs(id="tabs", value="who", children=[
            dcc.Tab(label='Dashboard Who', value='who'),
            dcc.Tab(label='Dashboard Food', value='food'),
            dcc.Tab(label='Dashboard Flights', value='flights')
        ]),
        html.Div(id='tab-content')
    ])

    @app.callback(Output('tab-content', 'children'), [Input('tabs', 'value')])
    def render_content(tab):
        if tab == 'who':
            return layout_who()
        elif tab == 'food':
            return layout_food()
        elif tab == 'flights':
            return layout_flights()

    app.run(debug=True)