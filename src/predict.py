"""Inference for the Shoppers Purchasing Intention model.

The trained network (16 -> 16 -> 8 -> 1, ReLU/ReLU/sigmoid) is a Keras model. To keep the
deployed app small (no TensorFlow at runtime) its weights are exported once to
`models/shoppers_weights.npz` by `scripts/export_weights.py`, and the forward pass is
evaluated with NumPy. The export is verified to give identical labels to the Keras model.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from src.feature_engineering import feature_evaluation

WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "models" / "shoppers_weights.npz"
THRESHOLD = 0.5

_lock = threading.Lock()
_weights: dict | None = None


def _load_weights() -> dict:
    """Load the exported weights once and cache them."""
    global _weights
    if _weights is None:
        with _lock:
            if _weights is None:
                if not WEIGHTS_PATH.exists():
                    raise FileNotFoundError(
                        f"Model weights not found at {WEIGHTS_PATH}. "
                        "Run `python scripts/export_weights.py` once."
                    )
                with np.load(WEIGHTS_PATH) as data:
                    _weights = {k: data[k].astype("float64") for k in data.files}
    return _weights


def model_ready() -> bool:
    """True when the model weights can be loaded (used by /api/health)."""
    try:
        _load_weights()
        return True
    except Exception:
        return False


def predicter(payload: dict) -> dict:
    """Score one session.

    Returns {"prediction": bool, "probability": float, "threshold": float} where
    `probability` is the raw sigmoid output of the network for the "purchase" class.
    """
    w = _load_weights()
    x = np.asarray(feature_evaluation(payload), dtype="float64")
    h1 = np.maximum(x @ w["W1"] + w["b1"], 0.0)
    h2 = np.maximum(h1 @ w["W2"] + w["b2"], 0.0)
    z = float((h2 @ w["W3"] + w["b3"]).ravel()[0])
    probability = float(1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0))))
    return {
        "prediction": probability > THRESHOLD,
        "probability": probability,
        "threshold": THRESHOLD,
    }
