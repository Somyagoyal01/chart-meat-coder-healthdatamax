"""Compare pipeline output with gold (coder-reviewed) labels."""
from __future__ import annotations


def score(pred_visits: list[dict], gold_visits: list[dict]) -> dict:
    tp = fp = fn = 0
    withheld_ok = withheld_total = review = total = unsafe = 0
    errors = []
    for pv, gv in zip(pred_visits, gold_visits):
        submitted = {c["icd10"] for c in pv["codes"] if c["route"] == "SUBMIT"}
        reviewed = {c["icd10"] for c in pv["codes"] if c["route"] == "CODER_REVIEW"}
        gold_s, gold_w = set(gv["submit"]), set(gv["withhold"])
        tp += len(submitted & gold_s)
        fp += len(submitted - gold_s)
        fn += len(gold_s - submitted)
        withheld_total += len(gold_w)
        withheld_ok += len(gold_w - submitted)
        unsafe += len(submitted & gold_w)
        review += len(reviewed); total += len(pv["codes"])
        for c in sorted(submitted - gold_s):
            errors.append({"dos": gv["dos"], "type": "false submit", "code": c})
        for c in sorted(gold_s - submitted):
            where = "sent to review" if c in reviewed else "missed"
            errors.append({"dos": gv["dos"], "type": where, "code": c})
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "withhold_accuracy": round(withheld_ok / withheld_total, 3) if withheld_total else None,
            "unsupported_submitted": unsafe, "review_rate": round(review / total, 3) if total else 0.0,
            "visits": len(gold_visits), "errors": errors}
