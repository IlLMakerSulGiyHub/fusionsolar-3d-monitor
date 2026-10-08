import os, json
from dotenv import load_dotenv
from fusion_solar_py.client import FusionSolarClient

load_dotenv()
client = FusionSolarClient(os.getenv('FUSIONSOLAR_USER'), os.getenv('FUSIONSOLAR_PASS'), huawei_subdomain='uni002eu5')
stations = client.get_station_list()
plant_id = stations[0].get('dn')
print("Plant ID:", plant_id)

flow = client.get_plant_flow(plant_id)
print("=== FULL FLOW JSON ===")
print(json.dumps(flow, indent=2))
