import os
from dotenv import load_dotenv
from fusion_solar_py.client import FusionSolarClient

# Carica le variabili dal file .env
load_dotenv()

USER = os.getenv('FUSIONSOLAR_USER')
PASSWORD = os.getenv('FUSIONSOLAR_PASS')

def main():
    print("Inizio test di connessione a Fusion Solar...")
    
    if not USER or not PASSWORD or USER == 'la_tua_email_qui':
        print("ERRORE: Inserisci la tua email e password nel file .env prima di eseguire lo script.")
        return

    try:
        # Inizializza il client con il sottodominio corretto
        client = FusionSolarClient(USER, PASSWORD, huawei_subdomain='uni002eu5')
        
        print("\n[OK] Login effettuato con successo!")
        
        # Prova a ottenere le stazioni (impianti)
        stations = client.get_station_list()
        print(f"\nImpianti trovati: {len(stations)}")
        
        for plant in stations:
            print(f"- Nome impianto: {plant.get('name')} (DN: {plant.get('dn')})")
            print(f"  Produzione Odierna: {plant.get('dailyEnergy')} kWh")
            print(f"  Produzione Mensile: {plant.get('monthEnergy')} kWh")
            print(f"  Potenza Attuale: {plant.get('currentPower')} kW")
            print(f"  Capacità Batteria: {plant.get('batteryCapacity')} kWh")
            print("-" * 30)
            
    except Exception as e:
        print(f"\n[ERRORE] Errore durante la connessione: {e}")
        print("Nota: Se l'errore riguarda un 'captcha', potrebbe essere necessario un approccio diverso.")

if __name__ == '__main__':
    main()
