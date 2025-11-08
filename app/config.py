import os

# noms de fichiers par défaut (relatifs au dossier data)
FLIGHTS_FILE = os.environ.get("FLIGHTS_FILE", "dashboard_flights.csv")
AIRLINES_FILE = os.environ.get("AIRLINES_FILE", "airlines.csv")
AIRPORTS_FILE = os.environ.get("AIRPORTS_FILE", "airports.csv")

# chemin par défaut du dossier data (peut être remplacé via CLI/env/input)
DEFAULT_DATA_FOLDER = os.path.join(os.path.dirname(__file__), "..", "data")
