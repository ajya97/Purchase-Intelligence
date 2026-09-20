"""Turn a validated session payload into the numeric vector the model expects.

The order and encoding below mirror the training notebook exactly:
  * the `Month` column was dropped before training,
  * VisitorType was label-encoded (alphabetical): New_Visitor=0, Other=1, Returning_Visitor=2,
  * Weekend was encoded False=0 / True=1,
  * no scaling was applied.
"""

FEATURE_ORDER = (
    "Administrative",
    "Administrative_Duration",
    "Informational",
    "Informational_Duration",
    "ProductRelated",
    "ProductRelated_Duration",
    "BounceRates",
    "ExitRates",
    "PageValues",
    "SpecialDay",
    "OperatingSystems",
    "Browser",
    "Region",
    "TrafficType",
    "VisitorType",
    "Weekend",
)

VISITOR_CODES = {"New_Visitor": 0, "Other": 1, "Returning_Visitor": 2}


def feature_evaluation(payload: dict) -> list:
    """Return the 16 model inputs, in training order, as plain floats.

    `payload` must already be validated (see app/schema.py): numeric fields are
    numbers, VisitorType is one of VISITOR_CODES, Weekend is a bool.
    """
    row = dict(payload)
    row["VisitorType"] = VISITOR_CODES[row["VisitorType"]]
    row["Weekend"] = 1 if row["Weekend"] else 0
    return [float(row[name]) for name in FEATURE_ORDER]
