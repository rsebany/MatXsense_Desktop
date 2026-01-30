# MatXSense API

## Auth

- **POST /auth/login**  
  Body: `application/x-www-form-urlencoded` with `username`, `password`.  
  Returns: `{ "access_token": "<JWT>", "token_type": "bearer", "username": "..." }`.  
  Demo: `admin` or `demo`, password `demo123`.

- **POST /auth/register**  
  Disabled (501). Use demo login.

All `/api/*` endpoints require header: `Authorization: Bearer <access_token>`.

## API (authenticated)

- **GET /api/sensors** – Live sensor simulation (temperature, humidity, pH, salinity) and status.
- **GET /api/health-rul** – Health score, RUL (days), risk %. Optional: `temperature_celsius`, `humidity_percent`, `ph`, `salinity_psu`. When all four provided → **sensor-driven**; else **bridge sample** (LightGBM RUL, RF risk). Response: `source` `"sensor_driven"` or `"bridge_sample"`, optional `health_status` (Excellent/Good/Fair/Poor/Critical).
- **GET /api/predictions/bridge** – Bridge RUL predictions (RF, XGBoost, LightGBM). Optional `material_type` filter. RUL in years.
- **GET /api/predictions/xgb** – Legacy RUL view from bridge comparison (same data). `pred_lstm` = LightGBM (best RUL).
- **GET /api/predictions/xgb/{engine_id}** – Single sample; `engine_id` = row index.
- **GET /api/model-metrics** – All 6 bridge models (3 RUL regressors + 3 Health/Risk classifiers). Best RUL: LightGBM; Best classifier: RF.
- **GET /api/degradation-timeline** – Historical + model-predicted degradation (bridge digital twin).
- **POST /api/predict** – Run prediction from custom material info. Body (JSON): `material`, `environment`, `temperature_celsius`, `humidity_percent`, `ph`, `salinity_psu`, optional `notes`. Returns `health_score`, `rul_days`, `risk_percent`, `message`.
- **GET /api/alerts** – Active alerts with **context-aware variable recommendations**.  
  Query params (optional): `material`, `environment`, `temperature_celsius`, `humidity_percent`, `ph`, `salinity_psu`, `risk_percent`, `rul_days`, `health_score`.  
  When sensor + material + risk (and optionally `rul_days`, `health_score`) are provided, each alert includes a `recommendation` field: AI-style, variable text based on material, environment, severity, and current context.  
  Set `OPENAI_API_KEY` to use an LLM for recommendations; otherwise template-based variants are used.

## Run

From project root:

```bash
pip install -r requirements.txt
python run_server.py
```

Then open http://localhost:8000 and sign in with `admin` / `demo123`.
