"""Generate synthetic multi-visit charts (PDF) with gold labels. No real patient data.

Gold per visit:
  submit   - codes a coder should report (active and supported by MEAT at that visit)
  withhold - conditions present in the text that should NOT be reported (problem-list only,
             negated, family history, uncertain)
"""
from __future__ import annotations
import json
import os
import random
import sys

import pymupdf

# condition -> (code, phrasings, A/P sentences with MEAT, HPI/exam sentence)
CONDITIONS = {
    "t2dm": ("E11.9", ["type 2 diabetes", "T2DM", "diabetes mellitus type 2"],
             ["{x}: A1c 7.4 today, continue metformin 1000 mg twice daily.", "{x} - stable, reviewed glucose log, refill metformin."]),
    "htn": ("I10", ["hypertension", "HTN", "essential hypertension"],
            ["{x}: BP 138/84 today, continue lisinopril 20 mg.", "{x}, not at goal; increase amlodipine to 10 mg."]),
    "ckd3": ("N18.3", ["CKD stage 3", "chronic kidney disease stage 3"],
             ["{x}: eGFR 48, stable; avoid NSAIDs, recheck creatinine in 3 months."]),
    "chf": ("I50.22", ["chronic systolic heart failure", "HFrEF"],
            ["{x}: EF 35% on last echo, mild edema; continue carvedilol and furosemide."]),
    "afib": ("I48.91", ["atrial fibrillation", "afib"],
             ["{x}: rate controlled, continue apixaban 5 mg twice daily."]),
    "copd": ("J44.9", ["COPD", "chronic obstructive pulmonary disease"],
             ["{x}: mild wheezing on exam, continue tiotropium inhaler."]),
    "hld": ("E78.5", ["hyperlipidemia", "dyslipidemia"],
            ["{x}: LDL 132, start atorvastatin 20 mg."]),
    "hypothyroid": ("E03.9", ["hypothyroidism"],
                    ["{x}: TSH 2.1, continue levothyroxine 75 mcg."]),
    "depression": ("F32.9", ["depression", "major depressive disorder"],
                   ["{x}: PHQ-9 of 12, improving; continue sertraline 50 mg, counseled."]),
    "morbid_obesity": ("E66.01", ["morbid obesity", "severe obesity"],
                       ["{x}: BMI 41, discussed diet and referral to weight management."]),
    "pvd": ("I73.9", ["peripheral vascular disease", "peripheral artery disease"],
            ["{x}: diminished pulses on exam, continue statin, refer to vascular."]),
    "gerd": ("K21.9", ["GERD", "acid reflux"],
             ["{x}: symptoms controlled, continue omeprazole."]),
}
TRAPS = {
    "problem_list": ["copd", "afib", "gerd", "hypothyroid", "pvd", "depression"],
    "negated": [("R07.9", "Patient denies chest pain or palpitations."),
                ("I21.9", "No evidence of acute myocardial infarction on ECG.")],
    "family": [("C50.919", "Mother had breast cancer at 60."), ("I63.9", "Father with stroke at 70.")],
    "uncertain": [("F03.90", "Possible early dementia, will reassess with cognitive testing."),
                  ("J45.909", "Rule out asthma; spirometry ordered.")],
}


def make_visit(rng: random.Random, dos: str) -> tuple[str, dict]:
    active = rng.sample(sorted(CONDITIONS), rng.randint(2, 4))
    lines = [f"Date of Service: {dos}", "Chief Complaint: follow-up of chronic conditions."]
    submit, withhold = set(), set()
    hpi = []
    for c in active:
        code, names, aps = CONDITIONS[c]
        hpi.append(rng.choice(names))
    lines.append("HPI: Patient here for follow up of " + ", ".join(hpi) + ".")
    trap_kind = rng.sample(["problem_list", "negated", "family", "uncertain"], 2)
    pl = [c for c in TRAPS["problem_list"] if c not in active]
    pl_choice = rng.choice(pl) if "problem_list" in trap_kind and pl else None
    lines.append("Problem List: " + ", ".join(
        [CONDITIONS[c][1][0] for c in active] + ([CONDITIONS[pl_choice][1][0]] if pl_choice else [])) + ".")
    if pl_choice:
        withhold.add(CONDITIONS[pl_choice][0])
    if "family" in trap_kind:
        code, s = rng.choice(TRAPS["family"]); lines.append("Family History: " + s); withhold.add(code)
    if "negated" in trap_kind:
        code, s = rng.choice(TRAPS["negated"]); lines.append("ROS: " + s); withhold.add(code)
    lines.append("Assessment and Plan:")
    for i, c in enumerate(active, 1):
        code, names, aps = CONDITIONS[c]
        lines.append(f"{i}. " + rng.choice(aps).format(x=rng.choice(names).capitalize() if rng.random() < .5 else rng.choice(names)))
        submit.add(code)
    if "uncertain" in trap_kind:
        code, s = rng.choice(TRAPS["uncertain"]); lines.append(f"{len(active)+1}. {s}"); withhold.add(code)
    if {"E11.9", "N18.3"} <= submit:
        submit.discard("E11.9"); submit.add("E11.22")
    lines.append("Follow up in 3 months.")
    return "\n".join(lines), {"dos": dos, "submit": sorted(submit), "withhold": sorted(withhold - submit)}


def write_pdf(text: str, path: str, scanned: bool = False) -> None:
    doc = pymupdf.open()
    for chunk in [text[i:i + 2600] for i in range(0, len(text), 2600)]:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 560, 800), chunk, fontsize=9.5, fontname="helv")
    if scanned:  # re-render each page as an image so there is no text layer
        img_doc = pymupdf.open()
        for p in doc:
            pix = p.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
            np_ = img_doc.new_page(width=p.rect.width, height=p.rect.height)
            np_.insert_image(np_.rect, stream=pix.tobytes("jpeg", jpg_quality=70))
        doc = img_doc
    doc.save(path, garbage=3, deflate=True)


def main(out_dir: str = "data/synthetic", n: int = 40, seed: int = 7) -> None:
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    gold = {}
    for i in range(n):
        visits, golds = [], []
        for v in range(rng.randint(1, 3)):
            text, g = make_visit(rng, f"0{rng.randint(1, 9)}/{rng.randint(10, 28)}/2025")
            visits.append(text); golds.append(g)
        name = f"chart_{i:03d}.pdf"
        write_pdf("Patient: SYNTHETIC-{:03d} (not a real person)\n".format(i) + "\n\n".join(visits),
                  os.path.join(out_dir, name), scanned=(i % 5 == 4))
        gold[name] = golds
    with open(os.path.join(out_dir, "gold.json"), "w") as fh:
        json.dump(gold, fh, indent=1)
    print(f"wrote {n} charts to {out_dir}")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["data/synthetic"]))
