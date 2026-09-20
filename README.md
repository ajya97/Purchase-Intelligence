# Shoppers Purchasing Intention Predictor

Flask app that scores whether an e-commerce session will end in a purchase.

## Run locally
    python -m venv venv
    venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
    pip install -r requirements.txt
    python run.py                  # http://127.0.0.1:10000

## Deploy on Render
Build: `pip install -r requirements.txt`  Start: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
Python version comes from `.python-version` (Render does not read `runtime.txt`).

## Model
`models/shoppers_model.pkl` is the trained Keras model (unchanged). `models/shoppers_weights.npz` holds its exported
weights so production needs only NumPy. Regenerate with `python scripts/export_weights.py` (needs TensorFlow);
reproduce the reported metrics with `python scripts/evaluate_model.py`.
