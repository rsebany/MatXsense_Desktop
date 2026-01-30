# MatXSense – AI Digital Twin for Material Degradation

Material degradation monitoring using **virtual IoT sensors** and **machine learning**. Predict health, remaining useful life (RUL), and degradation risk for steel, concrete, polymers, and aluminum in different environments—with a **bridge digital twin** and optional sensor-driven inference.

---

## Problem

Materials like steel, concrete, and polymers degrade over time due to temperature, humidity, pH, and salinity. Traditional monitoring is costly and often reactive. MatXSense provides a **digital twin** that simulates sensors and uses ML to predict degradation and RUL.

## Solution

- **Virtual sensors**: Simulated temperature, humidity, pH, and salinity (optionally driven by real location weather).
- **ML-powered predictions**: LightGBM (best RUL), Random Forest (best risk), and XGBoost models trained on bridge digital twin data; 38-feature pipeline with preprocessor.
- **Material & environment aware**: Steel, concrete, polymer, aluminum in coastal, industrial, urban, or arctic conditions with material-specific thresholds and alerts.
- **Web dashboard**: Login, live sensor grid, health/RUL cards, degradation timeline chart, and alerts.

---

## Features

| Feature | Description |
|--------|-------------|
| **Live sensor simulation** | Temperature, humidity, pH, salinity with status (normal/warning) and optional real-weather input |
| **Health & RUL** | Health score (0–100), RUL (days), risk %. **Sensor-driven** when all four sensor params passed (→ LightGBM RUL, RF risk); else **bridge sample** from precomputed predictions. |
| **Bridge predictions** | RUL (years) from RF, XGBoost, LightGBM; optional `material_type` filter; single-sample or list |
| **Model metrics** | 6 bridge models: 3 RUL regressors (MAE, RMSE, R²) + 3 Health/Risk classifiers (Accuracy, AUC, F1). Best RUL: LightGBM; best classifier: Random Forest. |
| **Degradation timeline** | Historical + model-predicted degradation (bridge digital twin) |
| **Alerts** | Threshold-based (temp, humidity, pH, salinity, risk) with severity (info/warning/critical), acknowledge, and context-aware recommendations |
| **Custom predict** | `POST /api/predict` with material, environment, and sensor values for on-demand health/RUL/risk |
| **JWT auth** | Demo login for dashboard and API |

---

## Tech Stack

- **Backend**: FastAPI, Uvicorn, JWT (python-jose), bcrypt (passlib)
- **Data**: Pandas; environmental simulator (time-series temp/humidity/pH/salinity); bridge digital twin dataset
- **ML**: LightGBM (best RUL), Random Forest (best risk), XGBoost; preprocessor + 38 modeling features; inference in `src/ml_models/inference.py`
- **Frontend**: HTML/CSS/JS, Chart.js, Axios, Font Awesome; served as static files by FastAPI

---

## Project Structure

```
MatXSense/
├── run_server.py              # Start backend (FastAPI on :8000)
├── requirements.txt
├── setup.py
├── README.md
├── data/
│   └── bridge_digital_twin_dataset.csv   # Bridge digital twin source data
├── docs/
│   ├── api_docs.md            # API reference and auth
│   ├── user_guide.md
│   ├── bridge_models.md      # Bridge ML models description
│   └── xgb_model_inputs.md   # XGB/model inputs documentation
├── frontend/
│   ├── index.html            # Login + dashboard
│   ├── style.css
│   └── scripts.js
├── notebooks/
│   └── matXSense.ipynb   # EDA, training, bridge models
├── src/
│   ├── backend/
│   │   ├── main.py           # FastAPI app, auth, static mount
│   │   ├── api.py            # Sensors, health-rul, predictions, timeline, alerts, materials
│   │   ├── auth.py           # JWT + demo user
│   │   ├── config.py         # Paths (predictions, metrics, env JSON)
│   │   └── database.py
│   ├── data_generation/
│   │   ├── environmental_data_simulator.py
│   │   ├── environmental_data.csv
│   │   └── environmental_data.json
│   ├── ml_models/
│   │   ├── inference.py      # LightGBM RUL, RF risk, get_modeling_features()
│   │   ├── best_rul_model.pkl
│   │   ├── best_risk_model.pkl
│   │   ├── preprocessor.pkl
│   │   ├── modeling_features.pkl
│   │   ├── model_metrics.json
│   │   ├── sample_predictions.csv
│   │   ├── prediction_comparison.csv
│   │   └── ...  summary_visualization            # feature_importance, analysis_summary, etc.
│   └── utils/
│       ├── config.py
│       └── helpers.py
├── tests/
│   ├── test_data_generation.py
│   └── test_predictions.py
|   └──test_integration.py

└── presentations/
    └── pitch_deck.pptx
```

---

## Quick Start

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**

   ```bash
   python run_server.py
   ```

3. **Open the app**

   - Browser: **http://localhost:8000**
   - API docs: **http://localhost:8000/docs**

4. **Login (demo)**

   - Username: `admin` or `demo`
   - Password: `demo123`

All `/api/*` endpoints require: `Authorization: Bearer <access_token>` (obtain token via `POST /auth/login`).

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Get JWT (form: username, password) |
| GET | `/api/sensors` | Live sensor simulation (?material=, ?environment=) |
| GET | `/api/health-rul` | Health, RUL (days), risk %; sensor-driven if 4 params provided, else bridge sample |
| GET | `/api/predictions/bridge` | Bridge RUL predictions (RF, XGBoost, LightGBM), RUL in years (?material_type=) |
| GET | `/api/predictions/xgb` | Legacy list from bridge comparison (?limit=) |
| GET | `/api/predictions/xgb/{engine_id}` | Single sample by row index |
| POST | `/api/predict` | Custom prediction: body (material, environment, sensor values) → health, RUL, risk |
| GET | `/api/model-metrics` | All 6 bridge models (3 RUL + 3 classifier metrics) |
| GET | `/api/degradation-timeline` | Historical + predicted degradation |
| GET | `/api/alerts` | Active alerts (optional sensor params for recommendations) |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge alert |
| GET | `/api/materials` | Material and environment options for dropdowns |
| GET | `/api/export/report` | Export report |

See **docs/api_docs.md** for full API details.

---

## Data & Models

- **Bridge digital twin**: `data/bridge_digital_twin_dataset.csv` is the source dataset. Processed features and trained models live in `src/ml_models/` (e.g. `processed_bridge_dataset.csv`, `best_rul_model.pkl`, `best_risk_model.pkl`).
- **Environmental data**: Generated by `EnvironmentalDataSimulator` (temperature, humidity, pH, salinity over time); stored as CSV/JSON and used for timelines and sensor simulation.
- **Models**: LightGBM (best RUL), Random Forest (best risk), XGBoost; preprocessor and 38 modeling features. Metrics in `model_metrics.json`; sample outputs in `sample_predictions.csv` and `prediction_comparison.csv`.

---

## Tests

```bash
# From project root
python -m pytest tests/ -v
```

---

## Documentation

- **docs/api_docs.md** – API reference and auth
- **docs/user_guide.md** – User guide
- **docs/bridge_models.md** – Bridge ML models
- **docs/xgb_model_inputs.md** – Model inputs and features

---

## License

See repository or project terms.
