import os
import time
import re
import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from fusion_solar_py.client import FusionSolarClient

load_dotenv()

app = Flask(__name__)
# Chiave fissa per firmare i cookie di sessione (necessaria su Vercel Serverless e per multi-dispositivo)
app.secret_key = os.getenv('SECRET_KEY', 'ecosmart-fusionsolar-3d-secret-key-2026-v1')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

IS_VERCEL = bool(os.getenv('VERCEL'))
SAVED_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'saved_account.json')

# Cache in memoria indicizzata per username (così più parenti collegati insieme non si sovrascrivono mai)
clients_cache = {}
data_cache = {}
CACHE_SECONDS = 15

HUAWEI_SUBDOMAINS = [
    'uni002eu5',
    'uni001eu5',
    'uni003eu5',
    'uni004eu5',
    'uni005eu5',
    'region01eu5',
    'region02eu5',
    'region03eu5',
    'region04eu5',
    'region05eu5'
]


def get_current_credentials():
    """
    Restituisce le credenziali per il dispositivo/browser corrente:
    1. Prima controlla il cookie cifrato di sessione del singolo telefono/PC (funziona su Vercel e in multi-utente).
    2. Se siamo in locale sul PC (non su Vercel) e non è stato fatto logout, usa saved_account.json o .env.
    """
    if session.get('logged_out'):
        return None

    if session.get('fs_user') and session.get('fs_pass'):
        return {
            "username": session['fs_user'],
            "password": session['fs_pass'],
            "subdomain": session.get('fs_sub', 'uni002eu5')
        }

    # Fallback locale (solo su PC locale, non su Vercel pubblico)
    if not IS_VERCEL:
        if os.path.exists(SAVED_ACCOUNT_FILE):
            try:
                with open(SAVED_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('logged_out'):
                        return None
                    if data.get('username') and data.get('password'):
                        return {
                            "username": data['username'],
                            "password": data['password'],
                            "subdomain": data.get('subdomain', 'uni002eu5')
                        }
            except Exception as e:
                print(f"Errore lettura saved_account.json: {e}")

        env_user = os.getenv('FUSIONSOLAR_USER')
        env_pass = os.getenv('FUSIONSOLAR_PASS')
        env_sub = os.getenv('FUSIONSOLAR_SUBDOMAIN', 'uni002eu5')
        if env_user and env_pass and env_user != 'la_tua_email_qui':
            return {
                "username": env_user,
                "password": env_pass,
                "subdomain": env_sub
            }

    return None


def is_authenticated():
    return get_current_credentials() is not None


def get_client_for_creds(creds):
    """Ottiene o crea il client FusionSolar per uno specifico account."""
    key = f"{creds['username']}@{creds['subdomain']}"
    if key not in clients_cache:
        clients_cache[key] = FusionSolarClient(
            creds["username"],
            creds["password"],
            huawei_subdomain=creds["subdomain"]
        )
    return clients_cache[key]


def parse_kw(value_str):
    """Estrae il numero float da stringhe tipo '0.245 kW'."""
    if not value_str:
        return 0.0
    try:
        return float(re.sub(r'[^\d.]', '', str(value_str)))
    except Exception:
        return 0.0


def _try_single_subdomain(username, password, sub):
    """Funzione worker per testare un sottodominio Huawei."""
    test_client = FusionSolarClient(username, password, huawei_subdomain=sub)
    stations = test_client.get_station_list()
    if stations is not None and len(stations) > 0:
        return sub, test_client, stations
    raise ValueError(f"Nessun impianto su {sub}")


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    req_subdomain = body.get('subdomain') or 'auto'
    remember = bool(body.get('remember', True))

    if not username or not password:
        return jsonify({"error": "Inserisci sia username/email che password."}), 400

    subdomains_to_try = [req_subdomain] if req_subdomain != 'auto' else HUAWEI_SUBDOMAINS

    found_sub = None
    found_client = None
    found_stations = None
    last_error = None

    # Test parallelo veloce (perfetto per Vercel Serverless per non superare mai il timeout)
    with ThreadPoolExecutor(max_workers=min(5, len(subdomains_to_try))) as executor:
        future_to_sub = {
            executor.submit(_try_single_subdomain, username, password, sub): sub
            for sub in subdomains_to_try
        }
        for future in as_completed(future_to_sub):
            try:
                sub, test_client, stations = future.result()
                found_sub = sub
                found_client = test_client
                found_stations = stations
                break
            except Exception as e:
                last_error = str(e)

    if found_sub and found_client and found_stations:
        plant_name = found_stations[0].get('name', 'Impianto Fotovoltaico')
        key = f"{username}@{found_sub}"
        clients_cache[key] = found_client
        data_cache.pop(key, None)

        # Salva nel Cookie di Sessione del dispositivo corrente (telefono/PC)
        session.permanent = remember
        session['fs_user'] = username
        session['fs_pass'] = password
        session['fs_sub'] = found_sub
        session.pop('logged_out', None)

        # Salva anche in locale se siamo su PC
        if not IS_VERCEL:
            try:
                with open(SAVED_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
                    if remember:
                        json.dump({
                            "username": username,
                            "password": password,
                            "subdomain": found_sub
                        }, f, indent=2)
                    else:
                        json.dump({"logged_out": True}, f, indent=2)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "plant_name": plant_name,
            "subdomain": found_sub,
            "username": username
        })

    return jsonify({
        "error": f"Impossibile accedere a FusionSolar. Verifica email e password. ({last_error or 'Account non trovato'})"
    }), 401


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    creds = get_current_credentials()
    if creds:
        key = f"{creds['username']}@{creds['subdomain']}"
        old_client = clients_cache.pop(key, None)
        data_cache.pop(key, None)
        try:
            if old_client:
                old_client.log_out()
        except Exception:
            pass

    session.clear()
    session['logged_out'] = True

    if not IS_VERCEL:
        try:
            with open(SAVED_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
                json.dump({"logged_out": True}, f, indent=2)
        except Exception:
            pass

    return redirect(url_for('login_page'))


@app.route('/')
def index():
    if not is_authenticated():
        return redirect(url_for('login_page'))
    return render_template('dashboard_solare_3d.html')


@app.route('/3d')
def view_3d():
    if not is_authenticated():
        return redirect(url_for('login_page'))
    return render_template('index.html')


@app.route('/hub')
@app.route('/dashboard')
def view_hub():
    if not is_authenticated():
        return redirect(url_for('login_page'))
    return render_template('dashboard_solare_3d.html')


@app.route('/api/flow')
def get_flow():
    creds = get_current_credentials()
    if not creds:
        return jsonify({"error": "Non autenticato", "need_login": True}), 401

    key = f"{creds['username']}@{creds['subdomain']}"
    current_time = time.time()

    cached_entry = data_cache.get(key)
    if cached_entry and (current_time - cached_entry['time'] < CACHE_SECONDS):
        return jsonify(cached_entry['data'])

    try:
        c = get_client_for_creds(creds)
        stations = c.get_station_list()
        if not stations:
            return jsonify({"error": "Nessun impianto trovato su questo account"}), 404

        plant_id = stations[0].get('dn')
        flow_raw = c.get_plant_flow(plant_id)

        plant_name = stations[0].get('name', 'Impianto Solare')
        daily_energy = stations[0].get('dailyEnergy', '0.0')
        month_energy = stations[0].get('monthEnergy', '0.0')
        cumul_energy = stations[0].get('cumulativeEnergy', '0.0')

        dashboard_data = {
            "account": {
                "username": creds.get("username"),
                "subdomain": creds.get("subdomain")
            },
            "station": {
                "name": plant_name,
                "daily_energy": float(daily_energy) if daily_energy else 0.0,
                "month_energy": float(month_energy) if month_energy else 0.0,
                "total_energy": float(cumul_energy) if cumul_energy else 0.0
            },
            "pv":      {"power": 0.0, "active": False},
            "grid":    {"power": 0.0, "importing": False, "exporting": False, "active": False},
            "battery": {"power": 0.0, "soc": 0.0, "charging": False, "discharging": False, "active": False},
            "house":   {"power": 0.0, "active": False},
            "wallbox": {"power": 0.0, "active": False},
        }

        if not (flow_raw and 'data' in flow_raw):
            return jsonify(dashboard_data)

        outer_data = flow_raw['data']
        inner_data = {}
        for k, val in outer_data.items():
            if isinstance(val, dict) and 'nodes' in val:
                inner_data = val
                break

        nodes = inner_data.get('nodes', [])
        links = inner_data.get('links', [])

        for node in nodes:
            nid = node.get('id')
            tips = node.get('deviceTips', {})
            desc_val = node.get('description', {}).get('value', '')

            if nid == '1':
                pv_power = parse_kw(tips.get('ACTIVE_POWER', 0))
                dashboard_data["pv"]["power"] = pv_power
                dashboard_data["pv"]["active"] = pv_power > 0

            if nid == '4':
                bat_power = parse_kw(tips.get('BATTERY_POWER', 0))
                soc = float(tips.get('SOC', 0))
                running = tips.get('RUNNING_STATUS', '')
                charging    = running == '0'
                discharging = running == '1'
                dashboard_data["battery"]["power"]       = bat_power
                dashboard_data["battery"]["soc"]         = soc
                dashboard_data["battery"]["charging"]    = charging
                dashboard_data["battery"]["discharging"] = discharging
                dashboard_data["battery"]["active"]      = bat_power > 0.01

            if nid == '5':
                house_power = parse_kw(desc_val)
                dashboard_data["house"]["power"]  = house_power
                dashboard_data["house"]["active"] = house_power > 0

        for link in links:
            from_node  = link.get('fromNode')
            to_node    = link.get('toNode')
            flowing    = link.get('flowing', 'NONE')
            desc_val   = link.get('description', {}).get('value', '')
            label      = link.get('description', {}).get('label', '')
            val        = parse_kw(desc_val)

            if from_node == '2' and to_node == '3' and flowing == 'FORWARD' and val > 0:
                dashboard_data["grid"]["power"]     = val
                dashboard_data["grid"]["exporting"] = True
                dashboard_data["grid"]["active"]    = True

            if from_node == '3' and to_node == '2' and flowing == 'FORWARD' and val > 0:
                dashboard_data["grid"]["power"]     = val
                dashboard_data["grid"]["importing"] = True
                dashboard_data["grid"]["active"]    = True

            if 'buy.power' in label and val > 0:
                dashboard_data["grid"]["power"]     = val
                dashboard_data["grid"]["importing"] = True
                dashboard_data["grid"]["exporting"] = False
                dashboard_data["grid"]["active"]    = True

            if 'sell.power' in label and val > 0:
                dashboard_data["grid"]["power"]     = val
                dashboard_data["grid"]["exporting"] = True
                dashboard_data["grid"]["importing"] = False
                dashboard_data["grid"]["active"]    = True

        data_cache[key] = {'time': current_time, 'data': dashboard_data}
        return jsonify(dashboard_data)

    except Exception as e:
        print(f"Errore API per {key}: {e}")
        clients_cache.pop(key, None)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
