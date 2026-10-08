import os
from dotenv import load_dotenv
from fusion_solar_py.client import FusionSolarClient
import json

load_dotenv()

USER = os.getenv('FUSIONSOLAR_USER')
PASSWORD = os.getenv('FUSIONSOLAR_PASS')

def main():
    client = FusionSolarClient(USER, PASSWORD, huawei_subdomain='uni002eu5')
    stations = client.get_station_list()
    
    if not stations:
        print("Nessun impianto trovato.")
        return
        
    plant = stations[0]
    plant_id = plant.get('dn') # L'ID interno usato spesso dalle API Huawei
    
    print(f"Esplorazione dati per impianto: {plant.get('name')} ({plant_id})")
    
    # Tentiamo varie funzioni per vedere quale espone i flussi di energia (pannelli, casa, rete, batteria)
    try:
        print("\n--- GET PLANT FLOW ---")
        flow = client.get_plant_flow(plant_id)
        print(json.dumps(flow, indent=2) if flow else "Nessun dato")
    except Exception as e:
        print(f"Errore get_plant_flow: {e}")

    try:
        print("\n--- GET REAL TIME DATA ---")
        rt = client.get_real_time_data(plant_id)
        print(json.dumps(rt, indent=2) if rt else "Nessun dato")
    except Exception as e:
        print(f"Errore get_real_time_data: {e}")
        
    try:
        print("\n--- GET POWER STATUS ---")
        ps = client.get_power_status(plant_id)
        print(json.dumps(ps, indent=2) if ps else "Nessun dato")
    except Exception as e:
        print(f"Errore get_power_status: {e}")

if __name__ == '__main__':
    main()
