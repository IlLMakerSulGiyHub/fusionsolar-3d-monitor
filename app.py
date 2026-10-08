import os
import time
import re
import json
import base64
from urllib.parse import urlparse
from datetime import timedelta
import requests
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from fusion_solar_py.client import FusionSolarClient
from fusion_solar_py.encryption import encrypt_password, get_secure_random

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'ecosmart-fusionsolar-3d-secret-key-2026-v1')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

IS_VERCEL = bool(os.getenv('VERCEL'))
SAVED_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'saved_account.json')

# Cache in memoria per utente
clients_cache = {}
data_cache = {}
CACHE_SECONDS = 15

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def get_current_credentials():
    """
    Restituisce le credenziali per il dispositivo/browser corrente:
    1. Dal cookie di sessione del singolo telefono/PC (funziona su Vercel e in multi-utente).
    2. In locale su PC (se non su Vercel), usa saved_account.json o .env.
    """
    if session.get('logged_out'):
        return None

    if session.get('fs_user') and session.get('fs_pass'):
        return {
            "username": session['fs_user'],
            "password": session['fs_pass'],
            "subdomain": session.get('fs_sub', 'uni002eu5'),
            "hw_cookies": session.get('hw_cookies')
        }

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
                            "subdomain": data.get('subdomain', 'uni002eu5'),
                            "hw_cookies": data.get('hw_cookies')
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
                "subdomain": env_sub,
                "hw_cookies": None
            }

    return None


def is_authenticated():
    return get_current_credentials() is not None


def fetch_captcha_image(req_session, login_subdomain="eu5"):
    """Scarica l'immagine Captcha da Huawei e la converte in Base64."""
    url = f"https://{login_subdomain}.fusionsolar.huawei.com/unisso/verifycode"
    r = req_session.get(url, params={"timestamp": round(time.time() * 1000)}, timeout=10)
    r.raise_for_status()
    b64 = base64.b64encode(r.content).decode('utf-8')
    return f"data:image/png;base64,{b64}"


def smart_huawei_login(username, password, req_subdomain="auto", verifycode=None, captcha_cookies=None):
    """
    Esegue UN SOLO tentativo di login su Huawei (evitando blocchi per troppi tentativi)
    e rileva automaticamente il sottodominio regionale dall'URL di redirect di Huawei.
    Supporta anche il codice Captcha se richiesto dal firewall Huawei su IP Cloud (es. Vercel).
    """
    login_subdomain = "eu5"
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT

    if captcha_cookies and isinstance(captcha_cookies, dict):
        s.cookies.update(captcha_cookies)

    # 1. Ottieni chiave pubblica RSA da Huawei
    key_req = s.get(f"https://{login_subdomain}.fusionsolar.huawei.com/unisso/pubkey", timeout=10)
    key_req.raise_for_status()
    key_data = key_req.json()

    # 2. Se l'utente ha inserito il Captcha, pre-valida il codice
    if verifycode:
        verifycode = verifycode.strip()
        try:
            s.post(
                f"https://{login_subdomain}.fusionsolar.huawei.com/unisso/preValidVerifycode",
                data={"verifycode": verifycode, "index": 0},
                timeout=10
            )
        except Exception:
            pass

    # 3. Prepara la richiesta di login cifrata V3
    url = f"https://{login_subdomain}.fusionsolar.huawei.com/unisso/v3/validateUser.action"
    url_params = {
        "timeStamp": key_data["timeStamp"],
        "nonce": get_secure_random()
    }
    enc_password = encrypt_password(key_data=key_data, password=password)

    json_data = {
        "organizationName": "",
        "username": username,
        "password": enc_password
    }
    if verifycode:
        json_data["verifycode"] = verifycode

    r = s.post(url=url, params=url_params, json=json_data, timeout=12)
    r.raise_for_status()
    login_resp = r.json()

    error_code = str(login_resp.get("errorCode") or "")
    error_msg = login_resp.get("errorMsg") or ""

    # 4. Login riuscito (codice 470 = redirect multi-region)
    if error_code == "470" and login_resp.get("respMultiRegionName"):
        target_path = login_resp["respMultiRegionName"][1]
        target_url = f"https://{login_subdomain}.fusionsolar.huawei.com{target_path}"
        redir_resp = s.get(target_url, timeout=12)
        redir_resp.raise_for_status()

        # Estrai automaticamente il vero sottodominio (es. uni002eu5, uni003eu5, region01eu5) dall'URL finale!
        parsed_host = urlparse(redir_resp.url).hostname or ""
        detected_sub = parsed_host.split(".")[0] if ".fusionsolar.huawei.com" in parsed_host else None

        final_sub = detected_sub if (req_subdomain == "auto" and detected_sub) else (
            req_subdomain if req_subdomain != "auto" else (detected_sub or "uni002eu5")
        )

        # Crea il FusionSolarClient riusando i cookie già autenticati (senza rifare il login!)
        hw_cookies = s.cookies.get_dict()
        fs_client = FusionSolarClient(
            username,
            password,
            huawei_subdomain=final_sub,
            cookies=hw_cookies
        )
        # Recupera il company_id / lista impianti
        stations = fs_client.get_station_list()
        return {
            "success": True,
            "client": fs_client,
            "subdomain": final_sub,
            "stations": stations,
            "hw_cookies": fs_client.get_cookies()
        }

    # 5. Gestione richiesta Captcha da parte di Huawei (molto comune da IP Cloud come Vercel)
    if "verification code" in error_msg.lower() or login_resp.get("verifyCodeCreate"):
        captcha_b64 = fetch_captcha_image(s, login_subdomain)
        return {
            "need_captcha": True,
            "captcha_image": captcha_b64,
            "captcha_cookies": s.cookies.get_dict(),
            "error": "Per sicurezza Huawei richiede il codice visivo (Captcha). Inserisci i caratteri mostrati nell'immagine qui sotto."
        }

    # 6. Gestione account bloccato temporaneamente da Huawei
    if "locked" in error_msg.lower() or error_code == "403":
        return {
            "error": "L'account Huawei è temporaneamente bloccato per 10 minuti a causa di troppi tentativi ravvicinati. Attendi 10 minuti (oppure entra una volta dall'app ufficiale FusionSolar) e riprova."
        }

    return {
        "error": f"Accesso rifiutato da Huawei: {error_msg or 'Credenziali non valide'}"
    }


def get_client_for_creds(creds):
    """Ottiene o ricrea il client FusionSolar riusando i cookie di sessione Huawei."""
    key = f"{creds['username']}@{creds['subdomain']}"
    if key in clients_cache:
        return clients_cache[key]

    hw_cookies = creds.get("hw_cookies")
    if hw_cookies:
        c = FusionSolarClient(
            creds["username"],
            creds["password"],
            huawei_subdomain=creds["subdomain"],
            cookies=hw_cookies
        )
        if c.is_session_active():
            clients_cache[key] = c
            return c

    # Se i cookie sono scaduti o non presenti, esegui un singolo login pulito
    res = smart_huawei_login(creds["username"], creds["password"], creds["subdomain"])
    if res.get("success"):
        clients_cache[key] = res["client"]
        session['hw_cookies'] = res.get("hw_cookies")
        return res["client"]

    raise RuntimeError(res.get("error", "Sessione Huawei scaduta, effettua nuovamente il login."))


def parse_kw(value_str):
    if not value_str:
        return 0.0
    try:
        return float(re.sub(r'[^\d.]', '', str(value_str)))
    except Exception:
        return 0.0


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/captcha', methods=['GET'])
def api_refresh_captcha():
    """Endpoint per ricaricare una nuova immagine Captcha se non si legge bene."""
    try:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        if session.get('captcha_cookies'):
            s.cookies.update(session['captcha_cookies'])
        img = fetch_captcha_image(s, "eu5")
        session['captcha_cookies'] = s.cookies.get_dict()
        return jsonify({"captcha_image": img})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    req_subdomain = body.get('subdomain') or 'auto'
    verifycode = (body.get('verifycode') or '').strip()
    remember = bool(body.get('remember', True))

    if not username or not password:
        return jsonify({"error": "Inserisci sia username/email che password."}), 400

    captcha_cookies = session.get('captcha_cookies')

    try:
        result = smart_huawei_login(
            username=username,
            password=password,
            req_subdomain=req_subdomain,
            verifycode=verifycode if verifycode else None,
            captcha_cookies=captcha_cookies
        )
    except Exception as e:
        return jsonify({"error": f"Errore di comunicazione con Huawei: {e}"}), 500

    if result.get("need_captcha"):
        session['captcha_cookies'] = result.get("captcha_cookies", {})
        return jsonify({
            "need_captcha": True,
            "captcha_image": result["captcha_image"],
            "error": result["error"]
        }), 401

    if result.get("success"):
        found_sub = result["subdomain"]
        found_client = result["client"]
        found_stations = result["stations"] or []
        hw_cookies = result.get("hw_cookies", {})

        plant_name = found_stations[0].get('name', 'Impianto Fotovoltaico') if found_stations else 'Impianto Fotovoltaico'
        key = f"{username}@{found_sub}"
        clients_cache[key] = found_client
        data_cache.pop(key, None)

        session.permanent = remember
        session['fs_user'] = username
        session['fs_pass'] = password
        session['fs_sub'] = found_sub
        session['hw_cookies'] = hw_cookies
        session.pop('captcha_cookies', None)
        session.pop('logged_out', None)

        if not IS_VERCEL:
            try:
                with open(SAVED_ACCOUNT_FILE, 'w', encoding='utf-8') as f:
                    if remember:
                        json.dump({
                            "username": username,
                            "password": password,
                            "subdomain": found_sub,
                            "hw_cookies": hw_cookies
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
        "error": result.get("error", "Impossibile accedere a FusionSolar.")
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
