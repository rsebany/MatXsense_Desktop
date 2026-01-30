"""MatXSense API: sensors, bridge ML predictions (LightGBM RUL, RF Health), health, alerts."""
import csv
import io
import json
import math
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from .auth import get_current_user
from .config import (
    BRIDGE_SAMPLE_PREDICTIONS_CSV,
    BRIDGE_PREDICTION_COMPARISON_CSV,
    MODEL_METRICS_JSON,
    ENV_JSON,
)

router = APIRouter(prefix="/api", tags=["api"])

# Environment labels for recommendations
ENV_LABELS = {"coastal": "Coastal Marine", "industrial": "Industrial", "urban": "Urban", "arctic": "Arctic"}

# Material-specific data + thresholds (max temp °C, max humidity %, pH range, max salinity ppt)
MATERIALS = {
    "steel": {"base_health": 78, "base_rul": 142, "degradation_rate": 0.35, "label": "Steel (Carbon)",
              "max_temp": 35, "min_temp": 15, "max_humidity": 75, "min_humidity": 40, "ph_min": 6.5, "ph_max": 8.0, "max_salinity": 38},
    "concrete": {"base_health": 82, "base_rul": 210, "degradation_rate": 0.22, "label": "Concrete",
                 "max_temp": 40, "min_temp": 10, "max_humidity": 85, "min_humidity": 35, "ph_min": 6.0, "ph_max": 9.0, "max_salinity": 40},
    "polymer": {"base_health": 90, "base_rul": 310, "degradation_rate": 0.15, "label": "Polymer Composite",
                "max_temp": 45, "min_temp": 5, "max_humidity": 80, "min_humidity": 30, "ph_min": 5.5, "ph_max": 8.5, "max_salinity": 42},
    "aluminum": {"base_health": 85, "base_rul": 190, "degradation_rate": 0.28, "label": "Aluminum Alloy",
                 "max_temp": 38, "min_temp": 12, "max_humidity": 78, "min_humidity": 38, "ph_min": 6.2, "ph_max": 8.2, "max_salinity": 39},
}
# Environment: stress + regional pH/salinity ranges (mean, spread)
ENVIRONMENTS = {
    "coastal": {"stress": 1.35, "humidity_bias": 8, "salinity_bias": 2, "ph_mean": 7.8, "ph_spread": 0.3, "salinity_mean": 35, "salinity_spread": 2},
    "industrial": {"stress": 1.25, "humidity_bias": 0, "salinity_bias": -1, "ph_mean": 7.2, "ph_spread": 0.5, "salinity_mean": 32, "salinity_spread": 3},
    "urban": {"stress": 1.1, "humidity_bias": 2, "salinity_bias": -2, "ph_mean": 7.0, "ph_spread": 0.6, "salinity_mean": 30, "salinity_spread": 4},
    "arctic": {"stress": 0.9, "humidity_bias": -5, "salinity_bias": -2, "ph_mean": 7.5, "ph_spread": 0.4, "salinity_mean": 28, "salinity_spread": 5},
}
DEFAULT_MATERIAL = "steel"
DEFAULT_ENVIRONMENT = "coastal"

# In-memory alert store: list of {id, title, message, severity, acknowledged, created_at}
_alerts_store: List[Dict[str, Any]] = []

# Bridge digital twin: sample predictions (RUL + risk) and model comparison
_sample_df: Optional[pd.DataFrame] = None
_comparison_df: Optional[pd.DataFrame] = None
_metrics_json: Optional[Dict[str, Any]] = None
_env_data: Optional[list] = None


def _get_bridge_sample_predictions() -> pd.DataFrame:
    """Bridge sample predictions: Predicted_RUL_Years_LightGBM, Predicted_Risk_RandomForest, etc."""
    global _sample_df
    if _sample_df is None:
        if not BRIDGE_SAMPLE_PREDICTIONS_CSV.exists():
            raise HTTPException(500, "Bridge sample predictions not found")
        _sample_df = pd.read_csv(BRIDGE_SAMPLE_PREDICTIONS_CSV)
    return _sample_df


def _get_bridge_comparison() -> pd.DataFrame:
    """Bridge prediction comparison: Actual_RUL, Pred_* for RF/XGB/LightGBM."""
    global _comparison_df
    if _comparison_df is None:
        if not BRIDGE_PREDICTION_COMPARISON_CSV.exists():
            raise HTTPException(500, "Bridge prediction comparison not found")
        _comparison_df = pd.read_csv(BRIDGE_PREDICTION_COMPARISON_CSV)
    return _comparison_df


def _get_model_metrics_json() -> Dict[str, Any]:
    """Model metrics for all 6 models (3 RUL + 3 Health/Risk)."""
    global _metrics_json
    if _metrics_json is None:
        if not MODEL_METRICS_JSON.exists():
            return {}
        with open(MODEL_METRICS_JSON) as f:
            _metrics_json = json.load(f)
    return _metrics_json


def _get_env_data() -> list:
    global _env_data
    if _env_data is None:
        if not ENV_JSON.exists():
            return []
        with open(ENV_JSON) as f:
            data = json.load(f)
            _env_data = data.get("data", [])
    return _env_data


# --- Response models ---
class SensorReading(BaseModel):
    temperature_celsius: float
    humidity_percent: float
    ph: float
    salinity_psu: float
    status_temp: str
    status_humidity: str
    status_ph: str
    status_salinity: str
    updated_at: str  # ISO timestamp


class HealthRUL(BaseModel):
    health_score: float
    rul_days: int
    risk_percent: float
    updated_at: str
    model_confidence: Optional[float] = None  # e.g. LightGBM R²
    source: Optional[str] = None  # "sensor_driven" | "bridge_sample"
    health_status: Optional[str] = None  # Excellent | Good | Fair | Poor | Critical (bridge ML)


class BridgePrediction(BaseModel):
    """Bridge RUL predictions: RF, XGBoost, LightGBM (best). RUL in years."""
    sample_id: int
    material_type: Optional[str] = None
    actual_rul_years: float
    pred_rf: float
    pred_xgb: float
    pred_lgb: float  # LightGBM, best RUL model


class XGBPrediction(BaseModel):
    """Legacy-friendly RUL view: actual_rul and pred_* in years. pred_lstm = LightGBM (best)."""
    engine_id: int
    actual_rul: float
    pred_xgb: float
    pred_lstm: Optional[float] = None
    pred_rf: Optional[float] = None


class ModelMetrics(BaseModel):
    model: str
    task: str  # "regression" | "classification"
    test_MAE: Optional[float] = None
    test_RMSE: Optional[float] = None
    test_R2: Optional[float] = None
    Accuracy: Optional[float] = None
    AUC: Optional[float] = None
    F1: Optional[float] = None
    is_best: bool = False


class MaterialInputRequest(BaseModel):
    """Custom material info for prediction."""
    material: str = "steel"
    environment: str = "coastal"
    temperature_celsius: float = 22.0
    humidity_percent: float = 60.0
    ph: float = 7.2
    salinity_psu: float = 35.0
    notes: Optional[str] = None


class MaterialInputResponse(BaseModel):
    """Prediction result from custom material input."""
    health_score: float
    rul_days: int
    risk_percent: float
    message: str = ""


class DegradationPoint(BaseModel):
    x: str  # date
    y: float  # integrity %


class DegradationTimeline(BaseModel):
    historical: List[DegradationPoint]
    prediction: List[DegradationPoint]


def _material_env(material: Optional[str], environment: Optional[str]):
    mat = MATERIALS.get((material or "").strip().lower(), MATERIALS[DEFAULT_MATERIAL])
    env = ENVIRONMENTS.get((environment or "").strip().lower(), ENVIRONMENTS[DEFAULT_ENVIRONMENT])
    return mat, env


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Endpoints ---
@router.get("/sensors", response_model=SensorReading)
def get_sensors(
    material: Optional[str] = Query(None, description="Material type: steel, concrete, polymer, aluminum"),
    environment: Optional[str] = Query(None, description="Environment: coastal, industrial, urban, arctic"),
    current_user: dict = Depends(get_current_user),
):
    """Live sensor simulation. Regional pH/salinity from environment; updated_at for transparency."""
    _, env = _material_env(material, environment)
    hour = (random.random() * 24) if random.random() > 0.7 else (pd.Timestamp.now().hour + pd.Timestamp.now().minute / 60)
    temp_base = 20 + math.sin(hour / 12 * math.pi) * 5
    temp = round(temp_base + (random.random() - 0.5), 1)
    humidity_base = 65 + math.sin(hour / 24 * math.pi) * 5 + env.get("humidity_bias", 0)
    humidity = round(humidity_base + (random.random() * 3 - 1.5), 1)
    # Regional pH/salinity from environment
    ph_mean = env.get("ph_mean", 7.2)
    ph_spread = env.get("ph_spread", 0.3)
    ph = round(ph_mean + (random.random() * 2 - 1) * ph_spread, 1)
    salinity_mean = env.get("salinity_mean", 35)
    salinity_spread = env.get("salinity_spread", 2)
    salinity = round(salinity_mean + (random.random() * 2 - 1) * salinity_spread, 1)
    salinity = max(20, min(45, salinity))

    def status_temp(t):
        return "warning" if t > 28 or t < 22 else "normal"
    def status_humidity(h):
        return "warning" if h > 70 or h < 50 else "normal"
    def status_ph(p):
        return "warning" if p > 7.5 or p < 6.8 else "normal"
    def status_salinity(s):
        return "warning" if s > 37 or s < 33 else "normal"

    return SensorReading(
        temperature_celsius=temp,
        humidity_percent=humidity,
        ph=ph,
        salinity_psu=salinity,
        status_temp=status_temp(temp),
        status_humidity=status_humidity(humidity),
        status_ph=status_ph(ph),
        status_salinity=status_salinity(salinity),
        updated_at=_now_iso(),
    )


@router.get("/health-rul", response_model=HealthRUL)
def get_health_rul(
    material: Optional[str] = Query(None, description="Material type: steel, concrete, polymer, aluminum"),
    environment: Optional[str] = Query(None, description="Environment: coastal, industrial, urban, arctic"),
    temperature_celsius: Optional[float] = Query(None, description="Current sensor temp (°C) – when all 4 sensor params provided, use sensor-driven prediction"),
    humidity_percent: Optional[float] = Query(None, description="Current sensor humidity (%)"),
    ph: Optional[float] = Query(None, description="Current sensor pH"),
    salinity_psu: Optional[float] = Query(None, description="Current sensor salinity (ppt)"),
    current_user: dict = Depends(get_current_user),
):
    """Health score, RUL (days), risk %. Sensor-driven when all 4 sensors given; else bridge sample (LightGBM RUL, RF Risk)."""
    mat, env = _material_env(material, environment)
    material_key = (material or "").strip().lower() or DEFAULT_MATERIAL
    env_key = (environment or "").strip().lower() or DEFAULT_ENVIRONMENT

    if all(x is not None for x in (temperature_celsius, humidity_percent, ph, salinity_psu)):
        health_score, rul_days, risk_percent = _predict_from_material_input(
            material_key, env_key,
            float(temperature_celsius), float(humidity_percent), float(ph), float(salinity_psu),
        )
        return HealthRUL(
            health_score=health_score,
            rul_days=rul_days,
            risk_percent=risk_percent,
            updated_at=_now_iso(),
            model_confidence=0.67,
            source="sensor_driven",
        )

    df = _get_bridge_sample_predictions()
    row = df.sample(1).iloc[0]
    rul_years = float(row["Predicted_RUL_Years_LightGBM"])
    risk_prob = float(row["Predicted_Risk_RandomForest"])
    risk_cls = int(row.get("Predicted_Risk_Class", 1 if risk_prob >= 0.5 else 0))
    rul_days = max(0, int(rul_years * 365))
    risk_percent = max(0, min(100, round(risk_prob * 100, 1)))
    health_score = max(0, min(100, round(100 - risk_percent, 1)))
    health_status = "Critical" if risk_cls == 1 else "Good"
    model_confidence = None
    try:
        m = _get_model_metrics_json()
        reg = m.get("regression_models") or {}
        lb = reg.get("LightGBM") or {}
        if lb.get("R²") is not None:
            model_confidence = round(float(lb["R²"]), 3)
    except Exception:
        pass
    return HealthRUL(
        health_score=health_score,
        rul_days=rul_days,
        risk_percent=risk_percent,
        updated_at=_now_iso(),
        model_confidence=model_confidence,
        source="bridge_sample",
        health_status=health_status,
    )


@router.get("/predictions/bridge", response_model=List[BridgePrediction])
def get_bridge_predictions(
    limit: int = 100,
    material_type: Optional[str] = Query(None, description="Filter by Material_Type"),
    current_user: dict = Depends(get_current_user),
):
    """Bridge RUL predictions (RF, XGBoost, LightGBM). RUL in years."""
    df = _get_bridge_comparison()
    if material_type:
        mt = str(material_type).strip()
        if "Material_Type" in df.columns and mt:
            df = df[df["Material_Type"].astype(str).str.equals(mt)]
    df = df.head(limit)
    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        out.append(BridgePrediction(
            sample_id=i,
            material_type=str(r["Material_Type"]) if "Material_Type" in r else None,
            actual_rul_years=float(r["Actual_RUL"]),
            pred_rf=float(r["Pred_RandomForest"]),
            pred_xgb=float(r["Pred_XGBoost"]),
            pred_lgb=float(r["Pred_LightGBM"]),
        ))
    return out


@router.get("/predictions/xgb", response_model=List[XGBPrediction])
def get_xgb_predictions(limit: int = 100, current_user: dict = Depends(get_current_user)):
    """RUL predictions from bridge comparison (RF, XGBoost, LightGBM). actual_rul in years; pred_lstm = LightGBM."""
    df = _get_bridge_comparison().head(limit)
    return [
        XGBPrediction(
            engine_id=i,
            actual_rul=float(r["Actual_RUL"]),
            pred_xgb=float(r["Pred_XGBoost"]),
            pred_lstm=float(r["Pred_LightGBM"]),
            pred_rf=float(r["Pred_RandomForest"]),
        )
        for i, (_, r) in enumerate(df.iterrows())
    ]


@router.get("/predictions/xgb/{engine_id}", response_model=XGBPrediction)
def get_xgb_prediction_by_engine(engine_id: int, current_user: dict = Depends(get_current_user)):
    """Single sample RUL prediction from bridge comparison. engine_id = row index."""
    df = _get_bridge_comparison()
    if engine_id < 0 or engine_id >= len(df):
        raise HTTPException(404, f"Sample {engine_id} not found")
    r = df.iloc[engine_id]
    return XGBPrediction(
        engine_id=engine_id,
        actual_rul=float(r["Actual_RUL"]),
        pred_xgb=float(r["Pred_XGBoost"]),
        pred_lstm=float(r["Pred_LightGBM"]),
        pred_rf=float(r["Pred_RandomForest"]),
    )


@router.get("/model-metrics", response_model=List[ModelMetrics])
def get_model_metrics(current_user: dict = Depends(get_current_user)):
    """Metrics for all 6 bridge models (3 RUL regressors + 3 Health/Risk classifiers). Best RUL: LightGBM; Best classifier: RF."""
    m = _get_model_metrics_json()
    out = []
    best_reg = (m.get("best_reg_model") or "LightGBM").strip()
    best_clf = (m.get("best_clf_model") or "RandomForest").strip()
    for name, vals in (m.get("regression_models") or {}).items():
        out.append(ModelMetrics(
            model=str(name),
            task="regression",
            test_MAE=float(vals["MAE"]) if vals.get("MAE") is not None else None,
            test_RMSE=float(vals["RMSE"]) if vals.get("RMSE") is not None else None,
            test_R2=float(vals["R²"]) if vals.get("R²") is not None else None,
            is_best=(str(name).strip() == best_reg),
        ))
    for name, vals in (m.get("classification_models") or {}).items():
        out.append(ModelMetrics(
            model=str(name),
            task="classification",
            Accuracy=float(vals["Accuracy"]) if vals.get("Accuracy") is not None else None,
            AUC=float(vals["AUC"]) if vals.get("AUC") is not None else None,
            F1=float(vals["F1"]) if vals.get("F1") is not None else None,
            is_best=(str(name).strip() == best_clf),
        ))
    return out


def _predict_from_material_input(
    material: str,
    environment: str,
    temperature_celsius: float,
    humidity_percent: float,
    ph: float,
    salinity_psu: float,
) -> Tuple[float, int, float]:
    """Compute health_score, rul_days, risk_percent from custom material + sensor input."""
    mat = MATERIALS.get((material or "").strip().lower(), MATERIALS[DEFAULT_MATERIAL])
    env = ENVIRONMENTS.get((environment or "").strip().lower(), ENVIRONMENTS[DEFAULT_ENVIRONMENT])
    base_health = mat["base_health"]
    base_rul = mat["base_rul"]
    stress_mult = env.get("stress", 1.0)
    t_min, t_max = mat.get("min_temp", 15), mat.get("max_temp", 35)
    h_min, h_max = mat.get("min_humidity", 40), mat.get("max_humidity", 80)
    ph_min, ph_max = mat.get("ph_min", 6.0), mat.get("ph_max", 9.0)
    s_max = mat.get("max_salinity", 40)
    t_mid = (t_min + t_max) / 2
    h_mid = (h_min + h_max) / 2
    ph_mid = (ph_min + ph_max) / 2
    # Deviation-based penalty (0 = ideal, higher = worse)
    t_dev = max(0, temperature_celsius - t_max) / 5 + max(0, t_min - temperature_celsius) / 5
    t_dev += abs(temperature_celsius - t_mid) / 20
    h_dev = max(0, humidity_percent - h_max) / 10 + max(0, h_min - humidity_percent) / 10
    h_dev += abs(humidity_percent - h_mid) / 25
    ph_dev = max(0, ph_min - ph, ph - ph_max) if (ph < ph_min or ph > ph_max) else 0
    ph_dev += abs(ph - ph_mid) * 0.5
    s_dev = max(0, salinity_psu - s_max) / 5 + max(0, salinity_psu - 35) / 15
    total_dev = (t_dev * 1.2 + h_dev * 1.0 + ph_dev * 0.8 + s_dev * 1.0) * stress_mult
    health = max(0, min(100, base_health - total_dev * 4))
    rul = max(0, int(base_rul * (health / 100) * (0.7 + 0.6 * (health / 100))))
    risk = max(5, min(95, (100 - health) * stress_mult * 0.85))
    return round(health, 1), rul, round(risk, 1)


@router.post("/predict", response_model=MaterialInputResponse)
def post_predict(
    body: MaterialInputRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run prediction from custom material info (material, environment, temp, humidity, pH, salinity)."""
    health, rul, risk = _predict_from_material_input(
        body.material,
        body.environment,
        body.temperature_celsius,
        body.humidity_percent,
        body.ph,
        body.salinity_psu,
    )
    msg = "Prediction from your material input."
    if body.notes:
        msg = f"Notes: {body.notes[:100]}. " + msg
    return MaterialInputResponse(
        health_score=health,
        rul_days=rul,
        risk_percent=risk,
        message=msg,
    )


def _build_real_timeline_from_env(mat: dict, env: dict) -> Optional[tuple]:
    """Build historical degradation from environmental_data.json: real dates + env-driven integrity. Returns (historical, last_date) or None."""
    from datetime import datetime, timedelta
    from collections import defaultdict
    data = _get_env_data()
    if not data or len(data) < 24:
        return None
    # Group by date (YYYY-MM-DD), average temp/humidity/pH/salinity per day
    by_day = defaultdict(lambda: {"temp": [], "humidity": [], "ph": [], "salinity": []})
    for r in data:
        ts = r.get("timestamp", "")
        if not ts or len(ts) < 10:
            continue
        day = ts[:10]
        by_day[day]["temp"].append(float(r.get("temperature_celsius", 25)))
        by_day[day]["humidity"].append(float(r.get("humidity_percent", 65)))
        by_day[day]["ph"].append(float(r.get("pH", 7.2)))
        by_day[day]["salinity"].append(float(r.get("salinity_psu", 35)))
    days_sorted = sorted(by_day.keys())
    if not days_sorted:
        return None
    base = mat["base_health"]
    stress_mult = env.get("stress", 1.0)
    historical = []
    cumulative = 0.0
    for day in days_sorted:
        agg = by_day[day]
        n = max(1, len(agg["temp"]))
        t_avg = sum(agg["temp"]) / n
        h_avg = sum(agg["humidity"]) / n
        p_avg = sum(agg["ph"]) / n
        s_avg = sum(agg["salinity"]) / n
        # Daily stress: high temp + high humidity + off pH + high salinity = more degradation
        day_stress = (
            max(0, (t_avg - 22) / 10) * 0.5
            + max(0, (h_avg - 60) / 30) * 0.4
            + abs(p_avg - 7.0) * 0.1
            + max(0, (s_avg - 34) / 5) * 0.2
        )
        cumulative += day_stress * stress_mult * mat["degradation_rate"] * 0.15
        integrity = max(0, min(100, base - cumulative + (random.random() * 2 - 1)))
        historical.append(DegradationPoint(x=day, y=round(integrity, 2)))
    last_date = datetime.strptime(days_sorted[-1], "%Y-%m-%d") if days_sorted else datetime.utcnow()
    return historical, last_date


@router.get("/degradation-timeline", response_model=DegradationTimeline)
def get_degradation_timeline(
    material: Optional[str] = Query(None, description="Material type: steel, concrete, polymer, aluminum"),
    environment: Optional[str] = Query(None, description="Environment: coastal, industrial, urban, arctic"),
    use_real_timeline: bool = Query(True, description="Use real dates and env data for historical when available"),
    current_user: dict = Depends(get_current_user),
):
    """Historical + model-predicted degradation (bridge digital twin). use_real_timeline: env data for history."""
    from datetime import datetime, timedelta
    mat, env = _material_env(material, environment)
    stress = env.get("stress", 1.0)
    rate = mat["degradation_rate"] * stress
    base = mat["base_health"]
    now = datetime.utcnow()

    historical = []
    last_historical_date = now

    if use_real_timeline:
        real = _build_real_timeline_from_env(mat, env)
        if real:
            historical, last_historical_date = real
            last_y = historical[-1].y if historical else base
        else:
            last_y = base
    if not historical:
        for i in range(31, 0, -1):
            d = now - timedelta(days=i)
            v = base - (31 - i) * rate * 0.3 * (1 + (random.random() * 0.1 - 0.05))
            historical.append(DegradationPoint(x=d.strftime("%Y-%m-%d"), y=round(max(0, min(100, v)), 2)))
        last_y = historical[-1].y if historical else base

    if use_real_timeline and historical:
        last_y = historical[-1].y

    # Prediction: real future dates from last historical date (or now)
    start_pred = last_historical_date if (use_real_timeline and historical) else now
    prediction = []
    for i in range(1, 61):
        d = start_pred + timedelta(days=i)
        v = last_y - i * rate * (1 + (random.random() * 0.15 - 0.075))
        prediction.append(DegradationPoint(x=d.strftime("%Y-%m-%d"), y=round(max(0, min(100, v)), 2)))

    return DegradationTimeline(historical=historical, prediction=prediction)


# --- AI-style variable recommendations (context-aware, multiple variants per scenario) ---
# Optional: set OPENAI_API_KEY to use LLM for recommendations; otherwise template-based.
RECOMMENDATION_TEMPLATES: Dict[str, List[str]] = {
    "temp_high_critical": [
        "Reduce exposure or add shading/ventilation. For {material} in {environment}, keeping temp below {limit}°C extends service life.",
        "Immediate action: cool the asset (e.g. ventilation, insulation). At {value}°C, {material} degrades faster in {environment}.",
        "Consider thermal barriers or scheduling inspections in the next 7 days. Current {value}°C exceeds {material} limit ({limit}°C).",
    ],
    "temp_low_warning": [
        "Low temperature may affect coatings or crack risk. For {material} in {environment}, ensure heating or protective measures if needed.",
        "Monitor for thermal stress or condensation. Below {limit}°C, {material} in {environment} may need different maintenance.",
    ],
    "humidity_high_warning": [
        "Improve ventilation or dehumidification. Humidity {value}% accelerates corrosion for {material} in {environment}.",
        "Consider moisture barriers or more frequent inspections. At {value}% humidity, {material} in {environment} is at higher risk.",
        "Reduce humidity below {limit}% where possible; apply or refresh protective coatings for {material}.",
    ],
    "humidity_low_info": [
        "Low humidity is generally favorable for {material}. No action required unless other factors are elevated.",
    ],
    "ph_out_warning": [
        "pH {value} is outside optimal range for {material}. Consider buffering or isolating the surface from aggressive media in {environment}.",
        "Adjust exposure or apply pH-resistant coating. For {material} in {environment}, pH near 7 is ideal.",
    ],
    "salinity_high_warning": [
        "Rinse or isolate from salt spray where feasible. Salinity {value} ppt increases corrosion for {material} in {environment}.",
        "Apply or refresh anti-corrosion coating; schedule inspection within 14 days. High salinity in {environment} accelerates degradation.",
    ],
    "risk_high_critical": [
        "Schedule inspection within 3–5 days. With {risk}% risk and RUL ~{rul} days, prioritize this asset for {material} in {environment}.",
        "Immediate review recommended: health {health}%, risk {risk}%. Consider load reduction or protective measures for {material}.",
        "Combine sensor insights: high risk ({risk}%) and low RUL ({rul} days). Plan maintenance or replacement for {material} in {environment}.",
    ],
    "risk_elevated_warning": [
        "Increase monitoring frequency. At {risk}% risk in {environment}, track health and RUL ({rul} days) for {material}.",
        "Consider preventive measures (coating, environment control) before risk rises further. Current RUL ~{rul} days for {material}.",
    ],
    "general_warning": [
        "Review sensor readings and degradation timeline. For {material} in {environment}, risk is {risk}%; RUL ~{rul} days.",
        "Adjust operating conditions or schedule a check. {material} in {environment} shows elevated stress (risk {risk}%).",
    ],
    "general_info": [
        "Continue monitoring. {material} in {environment} — current risk {risk}%, RUL ~{rul} days.",
    ],
}


def _build_recommendation(
    alert_type: str,
    severity: str,
    context: Dict[str, Any],
) -> str:
    """Generate a variable, context-aware recommendation (template-based or optional LLM)."""
    material_label = context.get("material_label") or "this material"
    environment = context.get("environment") or "current"
    env_label = ENV_LABELS.get(environment, environment.title()) if isinstance(environment, str) else "current"
    risk = context.get("risk_percent")
    rul = context.get("rul_days")
    health = context.get("health_score")
    value = context.get("value")
    limit = context.get("limit")
    fill = {
        "material": material_label,
        "environment": env_label,
        "risk": risk if risk is not None else "—",
        "rul": rul if rul is not None else "—",
        "health": health if health is not None else "—",
        "value": value if value is not None else "—",
        "limit": limit if limit is not None else "—",
    }
    key = f"{alert_type}_{severity}"
    templates = RECOMMENDATION_TEMPLATES.get(key) or RECOMMENDATION_TEMPLATES.get(f"general_{severity}") or RECOMMENDATION_TEMPLATES.get("general_warning")
    if not templates:
        return f"Review {material_label} in {env_label}. Risk: {fill['risk']}%, RUL: {fill['rul']} days."
    template = random.choice(templates)
    try:
        return template.format(**fill)
    except KeyError:
        return template.format(material=material_label, environment=env_label, risk=fill["risk"], rul=fill["rul"], health=fill["health"], value=fill["value"], limit=fill["limit"])


def _generate_ai_recommendation_if_available(
    title: str,
    message: str,
    severity: str,
    context: Dict[str, Any],
) -> Optional[str]:
    """If OPENAI_API_KEY is set, call OpenAI for a short recommendation; else return None (caller uses templates)."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.request
        import urllib.error
        prompt = (
            f"Alert: {title}. Detail: {message}. Severity: {severity}. "
            f"Context: material={context.get('material_label')}, environment={context.get('environment')}, "
            f"risk={context.get('risk_percent')}%, RUL={context.get('rul_days')} days. "
            "Reply with one short, actionable recommendation (1-2 sentences) for the operator. No preamble."
        )
        body = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 120,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        choices = data.get("choices", [])
        if choices and choices[0].get("message", {}).get("content"):
            return choices[0]["message"]["content"].strip()
    except Exception:
        pass
    return None


def _evaluate_alerts(
    material: str,
    temperature_celsius: float,
    humidity_percent: float,
    ph: float,
    salinity_psu: float,
    risk_percent: float,
) -> List[Dict[str, Any]]:
    """Evaluate material + environment thresholds; return new alerts with severity and alert_type for recommendations."""
    mat = MATERIALS.get(material.lower(), MATERIALS[DEFAULT_MATERIAL])
    out = []
    if temperature_celsius > mat.get("max_temp", 35):
        out.append({
            "title": "Temperature above limit",
            "message": f"Temp {temperature_celsius}°C exceeds {mat['max_temp']}°C for {mat['label']}.",
            "severity": "critical",
            "alert_type": "temp_high",
            "value": temperature_celsius,
            "limit": mat["max_temp"],
        })
    elif temperature_celsius < mat.get("min_temp", 15):
        out.append({
            "title": "Temperature below limit",
            "message": f"Temp {temperature_celsius}°C below {mat['min_temp']}°C for {mat['label']}.",
            "severity": "warning",
            "alert_type": "temp_low",
            "value": temperature_celsius,
            "limit": mat["min_temp"],
        })
    if humidity_percent > mat.get("max_humidity", 80):
        out.append({
            "title": "Humidity above limit",
            "message": f"Humidity {humidity_percent}% may accelerate corrosion for {mat['label']}.",
            "severity": "warning",
            "alert_type": "humidity_high",
            "value": humidity_percent,
            "limit": mat["max_humidity"],
        })
    elif humidity_percent < mat.get("min_humidity", 40):
        out.append({
            "title": "Low humidity",
            "message": f"Humidity {humidity_percent}% below typical range.",
            "severity": "info",
            "alert_type": "humidity_low",
            "value": humidity_percent,
            "limit": mat["min_humidity"],
        })
    if ph < mat.get("ph_min", 6.5) or ph > mat.get("ph_max", 8.5):
        out.append({
            "title": "pH out of range",
            "message": f"pH {ph} outside recommended range for {mat['label']}.",
            "severity": "warning",
            "alert_type": "ph_out",
            "value": ph,
            "limit": f"{mat['ph_min']}-{mat['ph_max']}",
        })
    if salinity_psu > mat.get("max_salinity", 40):
        out.append({
            "title": "Salinity elevated",
            "message": f"Salinity {salinity_psu} ppt increases corrosion risk for {mat['label']}.",
            "severity": "warning",
            "alert_type": "salinity_high",
            "value": salinity_psu,
            "limit": mat["max_salinity"],
        })
    if risk_percent > 70:
        out.append({
            "title": "High degradation risk",
            "message": f"Risk at {risk_percent:.0f}%. Consider inspection.",
            "severity": "critical",
            "alert_type": "risk_high",
        })
    elif risk_percent > 50:
        out.append({
            "title": "Elevated degradation risk",
            "message": f"Risk at {risk_percent:.0f}%. Monitor closely.",
            "severity": "warning",
            "alert_type": "risk_elevated",
        })
    return out


def _infer_alert_type_from_title(title: Optional[str]) -> str:
    """Infer alert_type from title for stored alerts (for recommendation lookup)."""
    if not title:
        return "general"
    t = (title or "").lower()
    if "temperature" in t and ("above" in t or "high" in t or "exceed" in t):
        return "temp_high"
    if "temperature" in t and ("below" in t or "low" in t):
        return "temp_low"
    if "humidity" in t and ("above" in t or "elevated" in t):
        return "humidity_high"
    if "humidity" in t and "low" in t:
        return "humidity_low"
    if "ph" in t or "pH" in title:
        return "ph_out"
    if "salinity" in t:
        return "salinity_high"
    if "high" in t and "risk" in t:
        return "risk_high"
    if "elevated" in t and "risk" in t:
        return "risk_elevated"
    return "general"


@router.get("/alerts")
def get_alerts(
    material: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    temperature_celsius: Optional[float] = Query(None),
    humidity_percent: Optional[float] = Query(None),
    ph: Optional[float] = Query(None),
    salinity_psu: Optional[float] = Query(None),
    risk_percent: Optional[float] = Query(None),
    rul_days: Optional[int] = Query(None, description="Current RUL (days) for context-aware recommendations"),
    health_score: Optional[float] = Query(None, description="Current health score for recommendations"),
    current_user: dict = Depends(get_current_user),
):
    """Active alerts with AI-style variable recommendations. Pass sensor + material + risk (and optionally rul_days, health_score) for context-aware recommendations."""
    mat, _ = _material_env(material, environment)
    material_key = (material or "").strip().lower() or DEFAULT_MATERIAL
    env_key = (environment or "").strip().lower() or DEFAULT_ENVIRONMENT
    material_label = mat["label"]
    risk = risk_percent if risk_percent is not None else 30.0
    rul = rul_days if rul_days is not None else mat.get("base_rul", 150)
    health = health_score if health_score is not None else mat.get("base_health", 78)

    base_context: Dict[str, Any] = {
        "material_label": material_label,
        "environment": env_key,
        "risk_percent": risk,
        "rul_days": rul,
        "health_score": health,
    }

    # Seed default alerts if store empty
    if not _alerts_store:
        for a in [
            {"title": "Elevated Humidity Detected", "message": "Humidity above 65% may accelerate corrosion. Monitor closely.", "severity": "warning"},
            {"title": "Degradation Rate Increased", "message": "Corrosion rate +15% over last 48h.", "severity": "warning"},
        ]:
            _alerts_store.append({"id": str(uuid.uuid4()), "title": a["title"], "message": a["message"], "severity": a["severity"], "acknowledged": False, "created_at": _now_iso()})
    result = list(_alerts_store)

    # Live-evaluate thresholds when sensor data provided (don't persist; merge into response)
    if temperature_celsius is not None and humidity_percent is not None and ph is not None and salinity_psu is not None:
        for a in _evaluate_alerts(material_key, temperature_celsius, humidity_percent, ph, salinity_psu, risk):
            ctx = {**base_context, "value": a.get("value"), "limit": a.get("limit")}
            rec = _generate_ai_recommendation_if_available(a["title"], a["message"], a["severity"], ctx)
            if rec is None:
                rec = _build_recommendation(a.get("alert_type", "general"), a["severity"], ctx)
            result.append({
                "id": "live-" + str(uuid.uuid4())[:8],
                "title": a["title"],
                "message": a["message"],
                "severity": a["severity"],
                "recommendation": rec,
                "acknowledged": False,
                "created_at": _now_iso(),
            })

    # Attach variable recommendation to every alert (stored + live)
    for item in result:
        if "recommendation" in item:
            continue
        alert_type = _infer_alert_type_from_title(item.get("title"))
        severity = item.get("severity") or "warning"
        ctx = base_context.copy()
        rec = _generate_ai_recommendation_if_available(
            item.get("title", ""), item.get("message", ""), severity, ctx
        )
        if rec is None:
            rec = _build_recommendation(alert_type, severity, ctx)
        item["recommendation"] = rec

    return result


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    """Mark alert as acknowledged."""
    for a in _alerts_store:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return {"ok": True, "id": alert_id}
    raise HTTPException(404, "Alert not found")


@router.get("/materials")
def get_materials(current_user: dict = Depends(get_current_user)):
    """List materials and environments for dropdowns. Load data for a material via ?material=steel&environment=coastal on sensors, health-rul, degradation-timeline."""
    return {
        "materials": [{"value": k, "label": v["label"]} for k, v in MATERIALS.items()],
        "environments": [
            {"value": "coastal", "label": "Coastal Marine"},
            {"value": "industrial", "label": "Industrial"},
            {"value": "urban", "label": "Urban"},
            {"value": "arctic", "label": "Arctic"},
        ],
    }


@router.get("/export/report", response_class=Response)
def export_report(
    material: Optional[str] = Query(None, description="Material type"),
    environment: Optional[str] = Query(None, description="Environment"),
    health_score: Optional[float] = Query(None, description="Current health score (optional)"),
    rul_days: Optional[int] = Query(None, description="Current RUL in days (optional)"),
    risk_percent: Optional[float] = Query(None, description="Current risk % (optional)"),
    temperature_celsius: Optional[float] = Query(None),
    humidity_percent: Optional[float] = Query(None),
    ph: Optional[float] = Query(None),
    salinity_psu: Optional[float] = Query(None),
    format: str = Query("csv", description="Report format: csv or json"),
    current_user: dict = Depends(get_current_user),
):
    """Export a material degradation report as a downloadable file (CSV or JSON)."""
    mat, env = _material_env(material, environment)
    material_key = (material or "").strip().lower() or DEFAULT_MATERIAL
    env_key = (environment or "").strip().lower() or DEFAULT_ENVIRONMENT
    material_label = mat["label"]
    env_label = ENV_LABELS.get(env_key, env_key.title())

    # Use provided values or compute from sensors/defaults
    if all(x is not None for x in (temperature_celsius, humidity_percent, ph, salinity_psu)):
        health_score, rul_days, risk_percent = _predict_from_material_input(
            material_key, env_key,
            float(temperature_celsius), float(humidity_percent), float(ph), float(salinity_psu),
        )
    elif health_score is None or rul_days is None or risk_percent is None:
        temp = temperature_celsius if temperature_celsius is not None else 22.0
        hum = humidity_percent if humidity_percent is not None else 60.0
        p = ph if ph is not None else 7.2
        sal = salinity_psu if salinity_psu is not None else 35.0
        health_score, rul_days, risk_percent = _predict_from_material_input(
            material_key, env_key, temp, hum, p, sal,
        )

    health_score = health_score or 0
    rul_days = rul_days or 0
    risk_percent = risk_percent or 0

    methodology = (
        "Health and RUL from sensor-driven model (material + environment + temp/humidity/pH/salinity) or bridge ML samples. "
        "Bridge models: LightGBM (RUL, best), Random Forest (Health/Risk, best). "
        "Degradation timeline uses environmental data and material-specific degradation rate."
    )
    try:
        m = _get_model_metrics_json()
        reg = m.get("regression_models") or {}
        lb = reg.get("LightGBM") or {}
        if lb.get("MAE") is not None:
            mae_h = float(lb["MAE"])
            mae_y = mae_h / 8760.0
            methodology += f" RUL MAE ~{mae_y:.1f} years (LightGBM)."
    except Exception:
        pass

    now_str = _now_iso()
    filename_date = now_str[:10]

    if format.lower() == "json":
        payload = {
            "report_generated_at": now_str,
            "material": material_label,
            "material_key": material_key,
            "environment": env_label,
            "environment_key": env_key,
            "health_score": round(health_score, 1),
            "rul_days": rul_days,
            "risk_percent": round(risk_percent, 1),
            "temperature_celsius": temperature_celsius,
            "humidity_percent": humidity_percent,
            "ph": ph,
            "salinity_psu": salinity_psu,
            "methodology": methodology,
        }
        body = json.dumps(payload, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="matxsense_report_{filename_date}.json"'
            },
        )

    # CSV
    rows = [
        ["field", "value"],
        ["report_generated_at", now_str],
        ["material", material_label],
        ["environment", env_label],
        ["health_score", str(round(health_score, 1))],
        ["rul_days", str(rul_days)],
        ["risk_percent", str(round(risk_percent, 1))],
        ["temperature_celsius", str(temperature_celsius) if temperature_celsius is not None else ""],
        ["humidity_percent", str(humidity_percent) if humidity_percent is not None else ""],
        ["ph", str(ph) if ph is not None else ""],
        ["salinity_psu", str(salinity_psu) if salinity_psu is not None else ""],
        ["methodology", methodology],
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    body = buf.getvalue()

    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="matxsense_report_{filename_date}.csv"'
        },
    )
