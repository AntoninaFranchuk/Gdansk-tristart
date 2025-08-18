import json
import requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

app = Flask(__name__)

BASE_URL = "https://ckan2.multimediagdansk.pl/departures?stopId={stop_id}"

# --- Load config or defaults ---
BASE_DIR = Path(__file__).resolve().parent
config_path = BASE_DIR / "config" / "stops.json"
if config_path.exists():
    with config_path.open(encoding="utf-8") as f:
        stops = json.load(f)
else:
    stops = {
        "Brama Wyżynna 01": 1562,
        "Brama Wyżynna 02": 1563,
        "Dworzec Główny 01": 1794,
        "Dworzec PKS": 1795
    }

def get_departures(stop_id: int):
    try:
        resp = requests.get(BASE_URL.format(stop_id=stop_id), timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    departures = []
    for dep in data.get("departures", []):
        time_str = dep.get("estimatedTime") or dep.get("theoreticalTime")
        if time_str:
            dt_utc = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(ZoneInfo("Europe/Warsaw"))
            time_fmt = dt_local.strftime("%H:%M:%S")
        else:
            time_fmt = None
        departures.append({
            "linia": dep.get("routeShortName"),
            "kierunek": dep.get("headsign"),
            "czas_lokalny": time_fmt,
            "opoznienie_s": dep.get("delayInSeconds")
        })
    return departures

# ...existing code...

HTML_TEMPLATE = """
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Departures Gdańsk</title>
<meta http-equiv="refresh" content="30">
<style>
body { font-family: Arial; margin: 20px; }
table { border-collapse: collapse; width: 50%; margin-bottom: 20px; }
th, td { border: 1px solid #333; padding: 8px; text-align: left; }
th { background-color: #eee; }
</style>
</head>
<body>
    <h1>Odjazdy z przystanków</h1>
    <p>Aktualny czas: {{ current_time }}</p>
    {% for stop_name, departures in all_departures.items() %}
        <h2>{{ stop_name }}</h2>
        <pre>{{ departures }}</pre>
    {% endfor %}
    <h3>Legenda:</h3>
    <p><b>opoznienie_s</b> - opóźnienie w sekundach (jeśli 0, pojazd jedzie zgodnie z rozkładem)</p>
</body>
</html>
"""

def format_departures(deps):
    lines = []
    for dep in deps:
        opoznienie = dep.get("opoznienie_s")
        if opoznienie is not None:
            minuty = opoznienie // 60
            sekundy = opoznienie % 60
            opoznienie_str = f"{minuty} min {sekundy} s"
        else:
            opoznienie_str = "brak danych"
        lines.append(
            f"Linia: {dep['linia']}, Kierunek: {dep['kierunek']}, Czas lokalny: {dep['czas_lokalny']}, Opóźnienie: {opoznienie_str}"
        )
    return "\n".join(lines)

@app.route('/')
def index():
    all_departures = {}
    for stop_key,stop_id in stops.items():
        nazwa_przystanku = stop_key.replace("_", " ").title()
        deps = get_departures(stop_id)
        all_departures[nazwa_przystanku] = format_departures(deps)
    current_time = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(
        HTML_TEMPLATE,
        all_departures=all_departures,
        current_time=current_time
        )

# ...existing code...

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True) 