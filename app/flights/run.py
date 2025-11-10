# run.py
"""
2015 Flight Delay Analytics — Real dataset dashboard entrypoint
Loads data and launches the Dash application.
"""

from data.data_loader import DataLoader
from dashboard.app import create_dash_app
import os
import sys
import time

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")

def main():
    print("\nInitializing dashboard...\n")

    t0 = time.time()
    dl = DataLoader(DATA_FOLDER, normalize_columns=True)
    df = dl.load_flights()

    print(f"Dataset loaded in {time.time() - t0:.2f}s")
    print(f"Total rows: {len(df):,}")
    print(f"Columns  : {df.columns.tolist()}")

    print("\nBuilding dashboard (first load may take a moment)...")

    t1 = time.time()
    app = create_dash_app(df)

    print(f"App ready in {time.time() - t1:.2f}s")
    print("Dashboard live at -> http://127.0.0.1:8050/\n")

    app.run(debug=True, port=8050, host="127.0.0.1")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
