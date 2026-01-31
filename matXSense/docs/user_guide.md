# MatXSense — User Guide ✅

> Quick reference and step-by-step instructions for installing, running, and using MatXSense — the AI digital twin for material degradation (bridge-focused). 

---

## Table of contents 📚

1. **Introduction**
2. **Quick Start**
3. **Installation**
4. **Run & Dashboard**
5. **Using the API**
6. **Live Sensor Simulation**
7. **Predictions & Models**
8. **Alerts & Recommendations**
9. **Data, Logs & Troubleshooting**
10. **Testing**
11. **Contributing**
12. **References**

---

## 1. Introduction 💡

MatXSense simulates virtual sensors and uses ML models to predict material health, Remaining Useful Life (RUL), and degradation risk for materials such as steel, concrete, polymers, and aluminum. It ships with a small web dashboard and a documented REST API for programmatic access.

---

## 2. Quick Start ⚡

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the server:

```bash
python run_server.py
```

3. Open the app in your browser:

- Dashboard: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`

4. Demo credentials (for local use):

- Username: `admin` or `demo`
- Password: `demo123`

> Note: All `/api/*` endpoints require a JWT in the `Authorization` header (`Bearer <access_token>`).

---

## 3. Installation 🔧

- Requirements: Python 3.10+ (see `requirements.txt`).
- Install packages:

```bash
pip install -r requirements.txt
```

- Optional env vars:
  - `OPENAI_API_KEY` — enables LLM-based, context-aware recommendations for alerts (optional).
  - Other configuration lives in `src/backend/config.py` and `src/utils/config.py`.

---

## 4. Run & Dashboard 🖥️

- Start server from project root:

```bash
python run_server.py
```

- The backend uses FastAPI and serves a simple static dashboard (mounts `frontend/` at `/static`). The root (`/`) returns the dashboard HTML when present.

- Login via the dashboard to enable authenticated features. Use the demo credentials above.

---

## 5. Using the API 🔐

Authentication
- POST `/auth/login` with `application/x-www-form-urlencoded` body: `username` and `password`.
- Response: `{ "access_token": "<JWT>", "token_type": "bearer", "username": "..." }`.
- Include header `Authorization: Bearer <access_token>` on subsequent requests.

Key endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sensors` | Live sensor simulation (temperature, humidity, pH, salinity). |
| GET | `/api/health-rul` | Health score, RUL (days), risk%. Provide all four sensor values to run sensor-driven prediction. |
| POST | `/api/predict` | Custom prediction with `material`, `environment`, and sensor values (JSON). |
| GET | `/api/predictions/bridge` | Bridge RUL predictions (LightGBM / RF / XGBoost). |
| GET | `/api/model-metrics` | Model metrics for the bridge models. |
| GET | `/api/degradation-timeline` | Historical + model-predicted degradation for timelines. |
| GET | `/api/alerts` | Active alerts; accepts context query params for richer recommendations. |

See `/docs` (Swagger UI) for full request/response examples.

---

## 6. Live Sensor Simulation 🌡️

- The `/api/sensors` endpoint returns simulated sensor readings (temperature_celsius, humidity_percent, ph, salinity_psu) and status per-sensor (normal/warning/critical).
- You may filter by `material` and `environment` to see context-aware simulations.

---

## 7. Predictions & Models 🤖

- Models live under `src/ml_models/`:
  - `best_rul_model.pkl` (LightGBM — best RUL regressor)
  - `best_risk_model.pkl` (Random Forest — best classifier for risk/health)
  - `preprocessor.pkl` and `modeling_features.pkl` (feature pipeline)
- `src/ml_models/inference.py` exposes helpers to run predictions programmatically.

Usage example (Python):

```python
from src.ml_models.inference import predict_from_sensors

payload = {
  "material": "steel",
  "environment": "coastal",
  "temperature_celsius": 22.0,
  "humidity_percent": 70.0,
  "ph": 6.8,
  "salinity_psu": 35.0
}

result = predict_from_sensors(**payload)
print(result)
# -> { 'health_score': 82.4, 'rul_days': 5200, 'risk_percent': 12.3, ... }
```

---

## 8. Alerts & Recommendations 🚨

- `/api/alerts` returns active alerts with severity and context.
- When `OPENAI_API_KEY` is set, alert recommendations use an LLM for context-aware remediation suggestions. Otherwise, templated recommendations are returned.

> Tip: Use `GET /api/alerts?material=steel&environment=coastal&temperature_celsius=...` to get recommendations tailored to the exact context.

---

## 9. Data, Logs & Troubleshooting 🧰

Common checks:

- Server not starting:
  - Confirm Python version and dependencies.
  - Check `uvicorn` logs in the terminal where `run_server.py` was run.
- 401 / Authorization errors:
  - Ensure you obtained a token from `/auth/login` and included it as `Authorization: Bearer <token>`.
- Model errors:
  - Confirm expected model files exist under `src/ml_models/` (`*.pkl`, `model_metrics.json`).

Helpful commands:

```bash
# Run tests
python -m pytest tests/ -v

# Run server (dev)
python run_server.py
```

---

## 10. Testing ✅

- Tests live in `tests/`. Run the suite with `pytest`.

---

## 11. Contributing 🤝

- SEBANY Romualdo 
- CHAUKE Martin 

---

## 12. References & Additional Docs 📎

- API reference: `docs/api_docs.md`
- Bridge ML models: `docs/bridge_models.md`
- Model input details: `docs/xgb_model_inputs.md`

---
