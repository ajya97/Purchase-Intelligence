"""One-off: export the Keras model's weights to a NumPy .npz so the web app doesn't need TensorFlow.

Run locally (needs tensorflow/keras, joblib, numpy, pandas):
    python scripts/export_weights.py

It reads  models/shoppers_model.pkl  (unchanged) and writes  models/shoppers_weights.npz,
then checks the NumPy forward pass against the Keras model on the whole dataset.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
model = joblib.load(ROOT / "models" / "shoppers_model.pkl")

dense = [layer.get_weights() for layer in model.layers if layer.get_weights()]
assert len(dense) == 3, "Expected a 3-layer Dense network (16-16-8-1)."
(W1, b1), (W2, b2), (W3, b3) = dense
out = ROOT / "models" / "shoppers_weights.npz"
np.savez(out, W1=W1, b1=b1, W2=W2, b2=b2, W3=W3, b3=b3)

# --- verify against Keras on the real data (same preprocessing as the notebook) ---
df = pd.read_csv(ROOT / "dataset" / "online_shoppers_intention.csv").drop(columns=["Month", "Revenue"])
df["VisitorType"] = df["VisitorType"].map({"New_Visitor": 0, "Other": 1, "Returning_Visitor": 2})
df["Weekend"] = df["Weekend"].astype(int)
X = df.values.astype("float64")

keras_p = model.predict(X.astype("float32"), verbose=0).ravel()
h = np.maximum(X @ W1 + b1, 0)
h = np.maximum(h @ W2 + b2, 0)
numpy_p = 1 / (1 + np.exp(-(h @ W3 + b3).ravel()))

print(f"Wrote {out}")
print(f"max |keras - numpy| probability difference: {np.abs(keras_p - numpy_p).max():.2e}")
print(f"label mismatches at 0.5: {int(((keras_p > 0.5) != (numpy_p > 0.5)).sum())} of {len(X)}")
