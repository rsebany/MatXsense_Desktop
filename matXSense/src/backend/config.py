"""Backend configuration."""
import os
from pathlib import Path

# Project root (MatXSense)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Bridge digital twin ML assets (6 models: 3 RUL + 3 Health/Risk)
ML_MODELS_DIR = PROJECT_ROOT / "src" / "ml_models"
MODEL_METRICS_JSON = ML_MODELS_DIR / "model_metrics.json"
BRIDGE_SAMPLE_PREDICTIONS_CSV = ML_MODELS_DIR / "sample_predictions.csv"
BRIDGE_PREDICTION_COMPARISON_CSV = ML_MODELS_DIR / "prediction_comparison.csv"
BEST_RUL_MODEL_PATH = ML_MODELS_DIR / "best_rul_model.pkl"
BEST_RISK_MODEL_PATH = ML_MODELS_DIR / "best_risk_model.pkl"
PREPROCESSOR_PATH = ML_MODELS_DIR / "preprocessor.pkl"
MODELING_FEATURES_PATH = ML_MODELS_DIR / "modeling_features.pkl"
ENV_JSON = PROJECT_ROOT / "src" / "data_generation" / "environmental_data.json"

# Auth
SECRET_KEY = os.getenv("MATXSENSE_SECRET_KEY", "matxsense-mvp-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Demo users: password "demo123". Use bcrypt hashes in production (passlib.verify in auth).
DEMO_USERS = {"admin": "demo123", "demo": "demo123"}
