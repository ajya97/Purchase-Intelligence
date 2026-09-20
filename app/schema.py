"""Single source of truth for the 16 model inputs.

Used for three things so they can never drift apart:
  1. rendering the form (labels, help text, ranges, defaults),
  2. server-side validation of /predict and /api/predict,
  3. the "outside the training range" warnings.

Field `name`s are the exact dataset/model column names. The only column the model does
not use is `Month` (dropped in the training notebook).
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from src.feature_engineering import FEATURE_ORDER, VISITOR_CODES

# Largest values seen in the training data (used for warnings, not for rejecting input).
TRAIN_MAX = {
    "Administrative": 27,
    "Administrative_Duration": 3398.75,
    "Informational": 24,
    "Informational_Duration": 2549.375,
    "ProductRelated": 705,
    "ProductRelated_Duration": 63973.52,
    "BounceRates": 0.2,
    "ExitRates": 0.2,
    "PageValues": 361.76,
}

COUNT_MAX = 5000          # sanity limit for page counts
DURATION_MAX = 200_000    # sanity limit, seconds
PAGE_VALUE_MAX = 10_000


def _field(name: str, label: str, kind: str, help: str, default: Any, **extra: Any) -> dict:
    return {"name": name, "label": label, "kind": kind, "help": help, "default": default, **extra}


def _codes(prefix: str, n: int) -> list[dict]:
    return [{"value": i, "label": f"{prefix} {i}"} for i in range(1, n + 1)]


GROUPS: list[dict] = [
    {
        "id": "engagement",
        "title": "Page engagement",
        "description": "How many pages the visitor viewed, and for how long.",
        "icon": "layers",
        "fields": [
            _field("Administrative", "Administrative pages visited", "int",
                   "Account-management pages viewed in this session.", 1,
                   min=0, max=COUNT_MAX, step=1, unit="pages"),
            _field("Administrative_Duration", "Time on administrative pages", "float",
                   "Total time spent on those pages.", 8,
                   min=0, max=DURATION_MAX, step="any", unit="sec"),
            _field("Informational", "Informational pages visited", "int",
                   "Pages about the site or shop, such as contact or about pages.", 0,
                   min=0, max=COUNT_MAX, step=1, unit="pages"),
            _field("Informational_Duration", "Time on informational pages", "float",
                   "Total time spent on those pages.", 0,
                   min=0, max=DURATION_MAX, step="any", unit="sec"),
            _field("ProductRelated", "Product pages visited", "int",
                   "Product and category pages viewed.", 18,
                   min=0, max=COUNT_MAX, step=1, unit="pages"),
            _field("ProductRelated_Duration", "Time on product pages", "float",
                   "Total time spent on product and category pages.", 600,
                   min=0, max=DURATION_MAX, step="any", unit="sec"),
        ],
    },
    {
        "id": "behavior",
        "title": "Session behavior",
        "description": "Signals from web analytics about how the session unfolded.",
        "icon": "activity",
        "fields": [
            _field("BounceRates", "Bounce rate", "rate",
                   "Share of visits that left after a single page, averaged over the pages viewed.", 0.006,
                   min=0, max=1, step=0.001, slider_max=0.2),
            _field("ExitRates", "Exit rate", "rate",
                   "How often the pages viewed were the last page of a session, averaged.", 0.03,
                   min=0, max=1, step=0.001, slider_max=0.2),
            _field("PageValues", "Page value", "float",
                   "Average value of the pages viewed before a purchase, as tracked by e-commerce analytics.", 0,
                   min=0, max=PAGE_VALUE_MAX, step="any", unit=""),
            _field("SpecialDay", "Special day", "special",
                   "Closeness of the visit to a shopping occasion such as Valentine's Day. "
                   "0 means none nearby; 1 means the day itself.", 0,
                   min=0, max=1, step=0.2),
        ],
    },
    {
        "id": "context",
        "title": "Visitor context",
        "description": "Who is visiting and how they arrived.",
        "icon": "user",
        "fields": [
            _field("OperatingSystems", "Operating system", "choice",
                   "Operating-system code from the dataset (1 to 8).", 2,
                   options=_codes("Operating system", 8), numeric=True),
            _field("Browser", "Browser", "choice",
                   "Browser code from the dataset (1 to 13).", 2,
                   options=_codes("Browser", 13), numeric=True),
            _field("Region", "Region", "choice",
                   "Region code from the dataset (1 to 9).", 1,
                   options=_codes("Region", 9), numeric=True),
            _field("TrafficType", "Traffic type", "choice",
                   "Traffic-source code from the dataset (1 to 20).", 2,
                   options=_codes("Traffic type", 20), numeric=True),
            _field("VisitorType", "Visitor type", "choice",
                   "Whether the visitor has been to the site before.", "Returning_Visitor",
                   options=[
                       {"value": "New_Visitor", "label": "New visitor"},
                       {"value": "Returning_Visitor", "label": "Returning visitor"},
                       {"value": "Other", "label": "Other"},
                   ], numeric=False),
            _field("Weekend", "Weekend visit", "bool",
                   "Turn on if the session took place on a weekend.", False),
        ],
    },
]

FIELDS: list[dict] = [f for g in GROUPS for f in g["fields"]]
FIELD_BY_NAME: dict[str, dict] = {f["name"]: f for f in FIELDS}
assert tuple(f["name"] for f in FIELDS) == FEATURE_ORDER, "schema order must match the model's feature order"
DEFAULTS: dict[str, Any] = {f["name"]: f["default"] for f in FIELDS}

# Example sessions for the preset buttons. They describe behaviour; they are not outcomes.
PRESETS: list[dict] = [
    {"id": "typical", "label": "Typical session", "values": dict(DEFAULTS)},
    {"id": "deep", "label": "Deep product browsing", "values": {
        **DEFAULTS, "Administrative": 3, "Administrative_Duration": 90, "Informational": 1,
        "Informational_Duration": 40, "ProductRelated": 45, "ProductRelated_Duration": 1800,
        "BounceRates": 0.005, "ExitRates": 0.015, "PageValues": 22}},
    {"id": "single", "label": "Single-page visit", "values": {
        **DEFAULTS, "Administrative": 0, "Administrative_Duration": 0, "Informational": 0,
        "Informational_Duration": 0, "ProductRelated": 1, "ProductRelated_Duration": 12,
        "BounceRates": 0.2, "ExitRates": 0.2, "PageValues": 0, "VisitorType": "New_Visitor"}},
]

# Facts shown in "About the model". Metrics come from scripts/evaluate_model.py
# (20% hold-out, random_state=42, threshold 0.5).
MODEL_FACTS = {
    "sessions": 12330,
    "purchase_share": 15.5,
    "inputs": 16,
    "parameters": 417,
    "test_sessions": 2466,
    "accuracy": 87.9,
    "precision": 66.0,
    "recall": 56.2,
    "baseline": 84.5,
}


# ----------------------------------------------------------------------------- validation
_TRUE = {"true", "1", "on", "yes"}
_FALSE = {"false", "0", "off", "no"}


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: Any, f: dict) -> float:
    if _blank(value):
        raise ValueError("This field is required.")
    if isinstance(value, bool):
        raise ValueError("Enter a number.")
    try:
        number = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        raise ValueError("Enter a number.") from None
    if not math.isfinite(number):
        raise ValueError("Enter a finite number.")
    if number < f["min"]:
        raise ValueError(f"Must be at least {f['min']:g}.")
    if number > f["max"]:
        raise ValueError(f"Must be at most {f['max']:g}.")
    return number


def _coerce(value: Any, f: dict) -> Any:
    kind = f["kind"]
    if kind == "int":
        number = _number(value, f)
        if not number.is_integer():
            raise ValueError("Use a whole number.")
        return int(number)
    if kind in ("float", "rate", "special"):
        return _number(value, f)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower() if value is not None else ""
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError("Must be true or false.")
    if kind == "choice":
        if _blank(value):
            raise ValueError("Select an option.")
        if f["numeric"]:
            try:
                code = int(float(value)) if not isinstance(value, bool) else None
            except (TypeError, ValueError):
                code = None
            allowed = {o["value"] for o in f["options"]}
            if code is None or code not in allowed:
                raise ValueError("Select one of the listed options.")
            return code
        if value not in VISITOR_CODES:
            raise ValueError("Select one of the listed options.")
        return value
    raise ValueError("Unsupported field.")  # pragma: no cover


def validate(raw: Mapping[str, Any]) -> tuple[dict, dict]:
    """Validate a raw payload. Returns (clean_values, errors_by_field)."""
    clean: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for f in FIELDS:
        try:
            clean[f["name"]] = _coerce(raw.get(f["name"]), f)
        except ValueError as exc:
            errors[f["name"]] = str(exc)
    return clean, errors


def range_warnings(clean: Mapping[str, Any]) -> list[str]:
    """Plain-language notes for inputs above anything the model saw in training."""
    notes = []
    for name, limit in TRAIN_MAX.items():
        if clean.get(name, 0) > limit:
            label = FIELD_BY_NAME[name]["label"]
            notes.append(f"{label} is above the largest value in the training data ({limit:g}).")
    return notes
