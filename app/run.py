"""
run.py
Lance l'application Dash.

Usage:
    python -m app.run [DATA_FOLDER]

Priorité pour trouver le dossier data:
 1) argument CLI
 2) variable d'environnement DATA_FOLDER
 3) prompt console (si interactif)
 4) fallback to app/config.DEFAULT_DATA_FOLDER
"""
import os
import sys
import argparse
from pathlib import Path

from config import DEFAULT_DATA_FOLDER, FLIGHTS_FILE, AIRLINES_FILE, AIRPORTS_FILE
from data.data_loader import DataLoader
from dashboard.app import create_dash_app

def get_data_folder() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("data_folder", nargs="?", default=None)
    args, _ = parser.parse_known_args()
    if args.data_folder:
        if os.path.isdir(args.data_folder):
            return os.path.abspath(args.data_folder)
        else:
            print(f"[Warning] Dossier fourni introuvable: {args.data_folder}")

    env = os.environ.get("DATA_FOLDER")
    if env:
        if os.path.isdir(env):
            return os.path.abspath(env)
        else:
            print(f"[Warning] DATA_FOLDER défini mais dossier introuvable: {env}")

    # interactive prompt if possible
    if sys.stdin.isatty():
        try:
            candidate = input(f"Chemin vers le dossier data (enter pour utiliser '{DEFAULT_DATA_FOLDER}'): ").strip()
            if candidate:
                if os.path.isdir(candidate):
                    return os.path.abspath(candidate)
                else:
                    print(f"[Warning] Dossier introuvable: {candidate}")
        except Exception:
            pass

    # fallback
    fallback = os.path.abspath(DEFAULT_DATA_FOLDER)
    print(f"[Info] Utilisation du dossier par défaut: {fallback}")
    return fallback

def main():
    base = get_data_folder()
    flights_path = os.path.join(base, FLIGHTS_FILE)
    airlines_path = os.path.join(base, AIRLINES_FILE)
    airports_path = os.path.join(base, AIRPORTS_FILE)

    loader = DataLoader(base, flights_fname=FLIGHTS_FILE, airlines_fname=AIRLINES_FILE, airports_fname=AIRPORTS_FILE)

    try:
        flights_df = loader.load_flights()
    except FileNotFoundError as e:
        print("Erreur:", e)
        sys.exit(1)

    airlines_df = loader.load_airlines()
    airports_df = loader.load_airports()

    # create dash app and run
    dash_app = create_dash_app(flights_df, airlines_df, airports_df)
    dash_app.run(debug=True, port=8050)

if __name__ == "__main__":
    main()
