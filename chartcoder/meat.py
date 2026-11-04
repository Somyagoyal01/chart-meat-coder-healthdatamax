"""MEAT evidence check: was the condition Monitored, Evaluated, Assessed/Addressed or Treated at THIS visit?"""
from __future__ import annotations
import re

CUES = {
    "M": ["stable", "improving", "improved", "worsening", "worse", "unchanged", "monitor",
          "symptoms", "reports", "controlled", "flare"],
    "E": ["a1c", "hba1c", "egfr", "creatinine", "bp ", "blood pressure", "ejection fraction", "ef ", "echo", "inr",
          "tsh", "ldl", "lipid", "exam", "on exam", "bmi", "spirometry", "fev1", "x-ray", "ct ", "mri", "lab", "reviewed",
          "phq", "edema", "rales", "wheez"],
    "A": ["assessment", "discussed", "counseled", "counselled", "uncontrolled", "well controlled", "at goal",
          "not at goal", "progressing", "diagnosed", "consistent with"],
    "T": ["continue", "start", "started", "increase", "decrease", "titrate", "refill", "prescribe", "metformin",
          "insulin", "lisinopril", "amlodipine", "statin", "atorvastatin", "levothyroxine", "furosemide", "inhaler",
          "dialysis", "refer", "referral", "diet", "sertraline", "apixaban", "warfarin", "therapy", "medication",
          "carvedilol", "donepezil", "levodopa"],
}


def meat_elements(sentences: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {k: [] for k in CUES}
    for s in sentences:
        low = " " + s.lower() + " "
        for k, cues in CUES.items():
            for c in cues:
                if c in low and c.strip() not in hits[k]:
                    hits[k].append(c.strip())
    return {k: v for k, v in hits.items() if v}
