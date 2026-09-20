"""Reproduce the held-out metrics shown in the "About the model" section.

Uses the same split as the notebook: train_test_split(test_size=0.2, random_state=42).
Needs: numpy, pandas, scikit-learn.
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.predict import predicter  # noqa: E402

df = pd.read_csv(ROOT / "dataset" / "online_shoppers_intention.csv").drop(columns=["Month"])
X, y = df.drop(columns="Revenue"), df["Revenue"].astype(int)
_, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rows = X_test.to_dict("records")
results = [predicter(r) for r in rows]
proba = [r["probability"] for r in results]
pred = [int(r["prediction"]) for r in results]

print(f"held-out sessions : {len(y_test)} ({int(y_test.sum())} purchases)")
print(f"accuracy          : {accuracy_score(y_test, pred):.3f}")
print(f"precision         : {precision_score(y_test, pred):.3f}")
print(f"recall            : {recall_score(y_test, pred):.3f}")
print(f"F1                : {f1_score(y_test, pred):.3f}")
print(f"ROC AUC           : {roc_auc_score(y_test, proba):.3f}")
print(f"majority baseline : {1 - y_test.mean():.3f}")
