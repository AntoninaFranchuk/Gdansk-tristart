import json
import requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string, send_from_directory, redirect, url_for

# Utwórz folder 'output' jeśli nie istnieje
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

# Ścieżka do pliku w folderze 'output'
plik_path = output_dir / "wynik.txt"

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

# --- HTML template with table ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Departures Gdańsk</title>
<meta http-equiv="refresh" content="30">
<style>
body { font-family: Arial; margin: 20px; }
table { border-collapse: collapse; margin-bottom: 20px; }
th, td { border: 1px solid #ccc; padding: 6px 10px; }
th { background: #eee; }
button { margin-right: 10px; }
</style>
</head>
<body>
    <h1>Odjazdy z przystanków</h1>
    <p>Aktualny czas: {{ current_time }}</p>
    <form method="post" action="/zapisz">
        <button type="submit">Zapisz odjazdy do pliku</button>
    </form>
    <form method="post" action="/aktualizuj">
        <button type="submit">Aktualizuj odjazdy na stronie</button>
    </form>
    {% for stop_name, departures in all_departures.items() %}
        <h2>{{ stop_name }}</h2>
        {% if departures %}
        <table>
            <tr>
                <th>Linia</th>
                <th>Kierunek</th>
                <th>Czas lokalny</th>
                <th>Opóźnienie</th>
            </tr>
            {% for dep in departures %}
            <tr>
                <td>{{ dep.linia }}</td>
                <td>{{ dep.kierunek }}</td>
                <td>{{ dep.czas_lokalny }}</td>
                <td>
                    {% if dep.opoznienie_s is not none %}
                        {{ dep.opoznienie_s // 60 }} min {{ dep.opoznienie_s % 60 }} s
                    {% else %}
                        brak danych
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
            <p><i>Brak danych dla tego przystanku</i></p>
        {% endif %}
    {% endfor %}
</body>
</html>
"""

def format_departures_for_file(deps):
    """Ładne formatowanie do zapisu w pliku TXT"""
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
            f"Linia: {dep['linia']}, Kierunek: {dep['kierunek']}, "
            f"Czas lokalny: {dep['czas_lokalny']}, Opóźnienie: {opoznienie_str}"
        )
    return "\n".join(lines)

@app.route('/', methods=['GET', 'POST'])
def index():
    all_departures = {}
    for stop_key, stop_id in stops.items():
        nazwa_przystanku = stop_key.replace("_", " ").title()
        deps = get_departures(stop_id)
        all_departures[nazwa_przystanku] = deps
    current_time = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(
        HTML_TEMPLATE,
        all_departures=all_departures,
        current_time=current_time
    )

@app.route('/zapisz', methods=['POST'])
def zapisz():
    zapisz_odjazdy_do_pliku()
    return redirect(url_for('index'))

@app.route('/aktualizuj', methods=['POST'])
def aktualizuj():
    return redirect(url_for('index'))

def zapisz_odjazdy_do_pliku():
    with plik_path.open("w", encoding="utf-8") as f:
        for stop_key, stop_id in stops.items():
            nazwa_przystanku = stop_key.replace("_", " ").title()
            deps = get_departures(stop_id)
            f.write(f"{nazwa_przystanku}:\n")
            f.write(format_departures_for_file(deps))
            f.write("\n\n")

@app.route('/plik')
def download_file():
    zapisz_odjazdy_do_pliku()
    return send_from_directory(
        directory=str(output_dir),
        path="wynik.txt",
        as_attachment=True
    )

if __name__ == "__main__":
    zapisz_odjazdy_do_pliku()
    app.run(host="0.0.0.0", debug=True)
