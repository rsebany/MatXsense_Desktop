"""
Bridge digital twin ML inference.

- RUL (regression): LightGBM best. Output in years.
- Health/Risk (classification): Random Forest best. Binary risk (0/1) or health class.

Loads: best_rul_model.pkl, best_risk_model.pkl, preprocessor.pkl, modeling_features.pkl.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Lazy-loaded singletons
_rul_model = None
_risk_model = None
_preprocessor = None
_feature_names: Optional[List[str]] = None
_models_dir: Optional[Path] = None


def _models_dir_path() -> Path:
    global _models_dir
    if _models_dir is None:
        _models_dir = Path(__file__).resolve().parent
    return _models_dir


def _load_assets() -> None:
    global _rul_model, _risk_model, _preprocessor, _feature_names
    if _rul_model is not None:
        return
    import pickle

    d = _models_dir_path()
    with open(d / "best_rul_model.pkl", "rb") as f:
        _rul_model = pickle.load(f)
    with open(d / "best_risk_model.pkl", "rb") as f:
        _risk_model = pickle.load(f)
    with open(d / "preprocessor.pkl", "rb") as f:
        _preprocessor = pickle.load(f)
    with open(d / "modeling_features.pkl", "rb") as f:
        _feature_names = pickle.load(f)


def get_modeling_features() -> List[str]:
    """Return the 38 modeling feature names."""
    _load_assets()
    return list(_feature_names)


def _ensure_features(X: pd.DataFrame) -> pd.DataFrame:
    _load_assets()
    missing = [c for c in _feature_names if c not in X.columns]
    if missing:
        raise ValueError(f"Missing required features: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    return X[_feature_names].copy()


def predict_rul(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
    """
    Predict Remaining Useful Life (years) using the best RUL model (LightGBM).
    X: DataFrame with modeling features, or 2d array of shape (n, 38).
    """
    _load_assets()
    if isinstance(X, np.ndarray):
        X = pd.DataFrame(X, columns=_feature_names)
    X = _ensure_features(X)
    X_scaled = _preprocessor.transform(X)
    return _rul_model.predict(X_scaled)


def predict_risk(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
    """
    Predict risk class (0/1) using the best risk model (Random Forest).
    X: DataFrame with modeling features, or 2d array of shape (n, 38).
    """
    _load_assets()
    if isinstance(X, np.ndarray):
        X = pd.DataFrame(X, columns=_feature_names)
    X = _ensure_features(X)
    X_scaled = _preprocessor.transform(X)
    return _risk_model.predict(X_scaled)


def predict_risk_proba(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
    """Predict risk probabilities (n, 2) for classes 0, 1."""
    _load_assets()
    if isinstance(X, np.ndarray):
        X = pd.DataFrame(X, columns=_feature_names)
    X = _ensure_features(X)
    X_scaled = _preprocessor.transform(X)
    return _risk_model.predict_proba(X_scaled)
