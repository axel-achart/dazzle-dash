"""
Register callbacks. Pure functions using pandas -> plotly.
"""
from dash import Input, Output
import pandas as pd
import plotly.express as px

def register_callbacks(app, df: pd.DataFrame):
    @app.callback(
        Output("day_delay", "figure"),
        Output("airline_delay", "figure"),
        Output("time_series", "figure"),
        Output("kpis", "children"),
        Input("airline_filter", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update(selected_airline, start_date, end_date):
        dff = df.copy()

        # date filter
        if start_date:
            dff = dff[dff["DATE"] >= pd.to_datetime(start_date)]
        if end_date:
            dff = dff[dff["DATE"] <= pd.to_datetime(end_date)]

        # airline filter
        if selected_airline:
            if "AIRLINE_NAME" in dff.columns:
                dff = dff[dff["AIRLINE_NAME"] == selected_airline]
            elif "AIRLINE" in dff.columns:
                dff = dff[dff["AIRLINE"] == selected_airline]

        # --- day plot robust ---
        def make_day_fig(dframe):
            order = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            if dframe is None or dframe.empty:
                return px.bar(title="Retard moyen par jour (aucune donnée)")
            # ensure DAY_NAME exists
            if "DAY_NAME" not in dframe.columns or dframe["DAY_NAME"].isna().all():
                if "DATE" in dframe.columns:
                    dframe["DAY_NAME"] = dframe["DATE"].dt.day_name().map({
                        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
                        "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"
                    })
                else:
                    return px.bar(title="Retard moyen par jour (pas de DATE ni DAY_NAME)")
            if "ARRIVAL_DELAY" not in dframe.columns:
                return px.bar(title="Retard moyen par jour (colonne ARRIVAL_DELAY manquante)")
            dframe["ARRIVAL_DELAY"] = pd.to_numeric(dframe["ARRIVAL_DELAY"], errors="coerce")
            dframe = dframe.dropna(subset=["DAY_NAME", "ARRIVAL_DELAY"])
            if dframe.empty:
                return px.bar(title="Retard moyen par jour (aucun retard valide)")
            grouped = dframe.groupby("DAY_NAME")["ARRIVAL_DELAY"].mean().reindex(order)
            if grouped.dropna().empty:
                return px.bar(title="Retard moyen par jour (aucune moyenne calculable)")
            fig = px.bar(x=grouped.index, y=grouped.values,
                         labels={"x":"Jour", "y":"Retard moyen (min)"},
                         title="Retard moyen par jour de la semaine")
            fig.update_layout(xaxis=dict(categoryorder="array", categoryarray=order))
            return fig

        # --- airline plot ---
        def make_airline_fig(dframe, top_n=20):
            if dframe is None or dframe.empty or "ARRIVAL_DELAY" not in dframe.columns:
                return px.bar(title="Retard moyen par compagnie (données manquantes)")
            name_col = "AIRLINE_NAME" if "AIRLINE_NAME" in dframe.columns else ("AIRLINE" if "AIRLINE" in dframe.columns else None)
            if name_col is None:
                return px.bar(title="Retard moyen par compagnie (pas de colonne nom compagnie)")
            grouped = dframe.groupby(name_col)["ARRIVAL_DELAY"].mean().sort_values(ascending=False).head(top_n)
            if grouped.empty:
                return px.bar(title="Retard moyen par compagnie (aucune donnée)")
            fig = px.bar(x=grouped.index, y=grouped.values,
                         labels={"x":"Compagnie","y":"Retard moyen (min)"},
                         title=f"Top {top_n} compagnies - retard moyen arrivée")
            fig.update_layout(xaxis_tickangle=-45)
            return fig

        # --- time series ---
        def make_ts_fig(dframe, rule="ME"):
            if dframe is None or dframe.empty or "ARRIVAL_DELAY" not in dframe.columns:
                return px.line(title="Série temporelle (données manquantes)")
            ts = dframe.set_index("DATE").resample(rule)["ARRIVAL_DELAY"].mean().dropna()
            if ts.empty:
                return px.line(title="Série temporelle (aucune donnée)")
            fig = px.line(x=ts.index, y=ts.values, labels={"x":"Date","y":"Retard moyen (min)"}, title="Évolution du retard moyen")
            return fig

        fig_day = make_day_fig(dff)
        fig_air = make_airline_fig(dff, top_n=15)
        fig_ts = make_ts_fig(dff, rule="ME")

        # KPIs
        total = len(dff)
        mean_arr = None
        if "ARRIVAL_DELAY" in dff.columns and not dff["ARRIVAL_DELAY"].dropna().empty:
            mean_arr = round(dff["ARRIVAL_DELAY"].mean(), 2)
        pct_late = None
        if "IS_LATE_ARR" in dff.columns and not dff["IS_LATE_ARR"].dropna().empty:
            pct_late = round(100 * dff["IS_LATE_ARR"].mean(), 2)

        kpis = [
            {
                "title": "Total vols", "value": f"{total:,}"
            },
            {
                "title": "Retard moyen arrivée", "value": f"{mean_arr if mean_arr is not None else 'N/A'} min"
            },
            {
                "title": "% vols > 15 min", "value": f"{pct_late if pct_late is not None else 'N/A'} %"
            }
        ]
        # convert to simple HTML blocks
        kpi_blocks = []
        for k in kpis:
            kpi_blocks.append(
                {"type":"html", "content": f"<div style='padding:10px;border:1px solid #ddd;border-radius:6px'><h4>{k['title']}</h4><p>{k['value']}</p></div>"}
            )
        # Dash expects proper components; create them here to avoid extra imports earlier
        from dash import html as _html
        kpi_comps = [_html.Div(_html.H4(k["title"])) for k in []]  # dummy to satisfy style below
        # better: create actual components
        kpi_comps = [
            _html.Div([_html.H4(k["title"]), _html.P(k["value"])], style={"padding":"10px","border":"1px solid #ddd","borderRadius":"6px"})
            for k in kpis
        ]

        return fig_day, fig_air, fig_ts, kpi_comps
