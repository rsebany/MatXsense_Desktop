# Bridge Digital Twin Models (MatXSense)

The MatXSense backend uses **6 ML models** trained on the **bridge digital twin** dataset.  

---

## 1. Regression models → RUL prediction

Predict **Remaining Useful Life** (hours → years) before material failure.

| Model | R² | MAE (years) | RMSE (years) |
|-------|-----|-------------|--------------|
| Random Forest | ~0.61 | ~6.5 | ~17 |
| XGBoost | ~0.63 | ~6.2 | ~16.5 |
| **LightGBM** ✅ best | **~0.65** | **~6.0** | **~16.2** |

**Target:** `RUL_Hours` (converted to years for reporting).  
**Use:** Predictive maintenance, asset lifecycle planning, budget & intervention scheduling.

---

## 2. Classification models → Health / Risk prediction

Classify **bridge material condition** (risk / health status).

| Model | Accuracy | AUC | F1 |
|-------|----------|-----|-----|
| **Random Forest** ✅ best | **~95%** | **~0.99** | **~0.97** |
| XGBoost | ~95% | ~0.98 | ~0.97 |
| LightGBM | ~95% | ~0.99 | ~0.97 |

**Target:** `Health_Status` → {Excellent, Good, Fair, Poor, Critical}.  
**Use:** Risk alerts, dashboard indicators (green → red), safety decisions.

**Note:** Poor/Fair classes are harder due to class imbalance (most samples are “Critical”).

---

## 3. Data the models learned from

- **Dataset:** 43,200 samples, 54 raw features → 38 modeling features.  
- **Time series:** Hourly, Jan 2023.  
- **Materials:** Steel, Concrete, Polymer Composite, Aluminum Alloy.  
- **Sensors & physics:** Stress, strain, vibration, fatigue accumulation, corrosion level, crack propagation, temperature, humidity, wind, traffic load, etc.  
- **Engineered features:** Lag (t−1h), change rates, Stress×Humidity, Temp×Humidity, hour/day/month.

→ **Physics-informed + data-driven digital twin.**

---

## 4. Feature importance (top drivers)

1. **Corrosion level** (~70%)  
2. Material type  
3. Stress–humidity interaction  
4. Fatigue accumulation  
5. Crack propagation  

Aligned with real bridge degradation mechanisms.

---

## 5. API & assets

- **Config:** `ML_MODELS_DIR`, `model_metrics.json`, `sample_predictions.csv`, `prediction_comparison.csv`.  
- **Models:** `best_rul_model.pkl` (LightGBM), `best_risk_model.pkl` (Random Forest).  
- **Preprocessing:** `preprocessor.pkl`, `modeling_features.pkl` (38 features).  
- **Endpoints:**  
  - `GET /api/health-rul` → health score, RUL (days), risk %; source `sensor_driven` or `bridge_sample`.  
  - `GET /api/model-metrics` → all 6 models (reg + clf).  
  - `GET /api/predictions/bridge` → RUL comparison (RF, XGB, LightGBM).  
  - `GET /api/predictions/xgb` → legacy-friendly view (same data, different schema).

---

## 6. Dashboard

- **Health / RUL / Risk:** From sensor-driven formula (when all 4 sensors provided) or **bridge sample** (LightGBM RUL + RF risk).  
- **Model metrics:** LightGBM MAE (RUL), RF AUC (Health).  
- **Degradation timeline:** Historical + model-predicted integrity.
