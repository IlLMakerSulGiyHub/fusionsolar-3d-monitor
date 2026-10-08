# ☀️ EcoSmart FusionSolar 3D Monitor

Web App interattiva in **3D (Blender + Three.js)** per il monitoraggio in tempo reale degli impianti fotovoltaici **Huawei FusionSolar**, progettata per funzionare sia su **PC** che su **Smartphone** (tramite **Vercel**) con supporto **Multi-Account** per tutta la famiglia.

## ✨ Caratteristiche Principali

- **🏡 Modello 3D Fotorealistico creato in Blender (`villa_solare.glb`)**:
  - Villa residenziale su 2 piani con tetto a falde, tegole, vetrate illuminate, balcone, giardino alberato e piscina.
  - **14 Pannelli Fotovoltaici** monocristallini con cornice in alluminio sul tetto.
  - **Inverter Huawei SUN2000** e **Batteria di accumulo Huawei LUNA2000** con indicatori LED SOC dinamici.
  - **Palo della Rete Elettrica Enel** con cavo sospeso e **Carport con Wallbox + Auto Elettrica**.
- **⚡ Flussi Energetici 3D in Tempo Reale**:
  - Particelle luminose che scorrono lungo i cavi tra Pannelli, Inverter, Batteria, Casa, Rete Enel e Wallbox in base ai kW reali letti da Huawei FusionSolar.
- **🔐 Pagina di Login Multi-Account (`/login`)**:
  - Chiunque apra il link dal proprio telefono o PC può accedere con il proprio account Huawei FusionSolar.
  - **Rilevamento Automatico del Server Huawei** (`uni001eu5` .. `uni005eu5`, `region01eu5` .. `region05eu5`) in parallelo.
  - **Sessioni indipendenti su Cookie Cifrato**: più persone (es. madre, zii, familiari) possono usare contemporaneamente lo stesso link da telefoni diversi vedendo ciascuno esclusivamente il proprio impianto.
- **📊 Doppia Modalità di Visualizzazione**:
  - **EcoSmart Hub (`/`)**: Dashboard completa con card interattive, grafici, controllo Wallbox e vista 3D integrata.
  - **Vista 3D Pura (`/3d`)**: Visualizzazione 3D a schermo intero con etichette olografiche, telecamere preimpostate e ciclo Giorno / Tramonto / Notte.

## 🚀 Deploy su Vercel (da GitHub)

1. Importa questo repository su [Vercel](https://vercel.com/new).
2. Clicca direttamente su **Deploy** (il file `vercel.json` configura tutto in automatico).
3. Apri il link generato da qualsiasi smartphone o computer e accedi con le tue credenziali FusionSolar!

## 💻 Avvio in Locale su PC Windows

Fai doppio clic su **`Avvia_Dashboard.bat`** oppure esegui nel terminale:

```bash
pip install -r requirements.txt
python app.py
```

Poi apri il browser su `http://127.0.0.1:5000`.
