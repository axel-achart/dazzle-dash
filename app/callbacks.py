from dash import Input, Output, html
from layout import get_main_layout
from app.flights.app_flights import get_layout as layout_flights   # module flights, si actif
from app.who.app_who import app as app_who  # attention: tu importes le layout, pas l’objet Dash
from food.app_food import build_layout as layout_food  # module food, si actif

def get_page_layout(pathname):
    if pathname == "/flights":
        return layout_flights()  # layout Dash pour flights
    elif pathname == "/who":
        return app_who.layout  # l’attribut layout du module appWho.py
    elif pathname == "/food":
        return layout_food()  # layout Dash pour food
    else:
        return html.Div([
            html.H2("Bienvenue sur le Dashboard !"),
            html.P("Sélectionnez un onglet ci-dessus.")
        ])

# Enregistre le callback de navigation
def register_callbacks(app):
    app.callback(
        Output("page-content", "children"),
        Input("url", "pathname")
    )(lambda pathname: get_page_layout(pathname))
