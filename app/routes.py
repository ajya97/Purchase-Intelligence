from flask import Blueprint, current_app, jsonify, render_template, request

from app.schema import (DEFAULTS, GROUPS, MODEL_FACTS, PRESETS, range_warnings, validate)
from src.predict import model_ready, predicter

main = Blueprint("main", __name__)

LABELS = {True: "Purchase likely", False: "Purchase unlikely"}


def render_home(values=None, errors=None, error=None):
    """Render the landing page + predictor (also used to re-show a form with errors)."""
    return render_template(
        "index.html",
        groups=GROUPS,
        presets=PRESETS,
        facts=MODEL_FACTS,
        values=values or DEFAULTS,
        errors=errors or {},
        error=error,
    )


def _score(clean: dict) -> dict:
    result = predicter(clean)
    return {
        "prediction": result["prediction"],
        "label": LABELS[result["prediction"]],
        "probability": round(result["probability"], 4),
        "threshold": result["threshold"],
        "warnings": range_warnings(clean),
    }


# --------------------------------------------------------------------------- pages
@main.get("/")
def home():
    return render_home()


@main.post("/predict")
def predict():
    """Server-rendered fallback for the form (used when JavaScript is unavailable)."""
    raw = request.form.to_dict()
    # An unchecked checkbox is simply absent from a form post.
    raw["Weekend"] = "true" if "Weekend" in request.form else "false"

    clean, errors = validate(raw)
    if errors:
        return render_home(values={**DEFAULTS, **raw, "Weekend": raw["Weekend"] == "true"},
                           errors=errors,
                           error="Some values need attention before we can predict."), 400
    try:
        result = _score(clean)
    except Exception:
        current_app.logger.exception("Prediction failed")
        return render_home(values=clean, error="The model couldn't produce a prediction. Please try again."), 500

    return render_template("predict.html", groups=GROUPS, values=clean, **result)


# --------------------------------------------------------------------------- API
@main.post("/api/predict")
def api_predict():
    """JSON API. Body: the 16 model inputs, using the exact dataset column names.

    Example: {"Administrative": 1, ..., "VisitorType": "Returning_Visitor", "Weekend": false}
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify({"success": False,
                        "error": "Send a JSON object containing the 16 session inputs."}), 400

    clean, errors = validate(payload)
    if errors:
        return jsonify({"success": False,
                        "error": "Some values are missing or invalid.",
                        "errors": errors}), 400
    try:
        return jsonify({"success": True, **_score(clean)}), 200
    except FileNotFoundError:
        current_app.logger.exception("Model weights missing")
        return jsonify({"success": False, "error": "The model isn't available right now."}), 503
    except Exception:
        current_app.logger.exception("Prediction failed")
        return jsonify({"success": False, "error": "The model couldn't produce a prediction."}), 500


@main.get("/api/health")
def health():
    ready = model_ready()
    body = {
        "status": "healthy" if ready else "degraded",
        "model_loaded": ready,
        "service": "Shoppers Purchasing Intention Predictor",
    }
    return jsonify(body), (200 if ready else 503)
