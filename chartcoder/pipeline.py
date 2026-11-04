"""Chart PDF -> per-visit coding suggestions with MEAT evidence and a routing decision."""
from __future__ import annotations
from collections import defaultdict

from .codes import CodeSet
from .extractor import OfflineExtractor
from .meat import meat_elements
from .pdf_text import extract_text
from .visits import split_sections, split_visits

ACCEPT_CONF = 0.75
SUPPORT_SECTIONS = {"ap", "hpi", "exam", "labs"}
# ICD-10-CM guideline: "with" presumes a link between diabetes and CKD -> combination code.
COMBINATIONS = [({"E11.9", "N18.3"}, "E11.9", "E11.22"), ({"E11.9", "N18.4"}, "E11.9", "E11.22"),
                ({"E11.9", "N18.6"}, "E11.9", "E11.22")]
LESS_SPECIFIC = {"E11.9": ["E11.22", "E11.42", "E11.65"], "I50.9": ["I50.22"], "E66.9": ["E66.01"],
                 "F32.9": ["F33.1"], "D64.9": ["D63.1"]}


def code_visit(sections, extractor, cs: CodeSet) -> list[dict]:
    by_code: dict[str, list[dict]] = defaultdict(list)
    for m in extractor.extract(sections):
        by_code[m["icd10"]].append(m)

    active_ap = {c for c, ms in by_code.items() if any(m["status"] == "active" and m["section"] == "ap" for m in ms)}
    for need, drop, add in COMBINATIONS:
        if need <= active_ap and add not in by_code:
            by_code[add] = [dict(m, icd10=add, mention=m["mention"] + " (+CKD, combination rule)")
                            for m in by_code[drop]]
    results = []
    for code, ms in by_code.items():
        active = [m for m in ms if m["status"] == "active"]
        sections_seen = sorted({m["section"] for m in ms})
        rec = {"icd10": code, "description": cs.describe(code), "mentions": sorted({m["mention"] for m in ms}),
               "sections": sections_seen, "status": "active" if active else ms[0]["status"],
               "valid_code": cs.is_valid(code), "evidence": [], "meat": {}, "confidence": 0.0}
        if active:
            support = [m["sentence"] for m in active if m["section"] in SUPPORT_SECTIONS]
            rec["evidence"] = support[:4]
            rec["meat"] = meat_elements(support)
            rec["confidence"] = max(m["confidence"] for m in active)
        rec["route"], rec["reason"] = route(rec, active)
        results.append(rec)

    present = {r["icd10"] for r in results if r["route"] != "WITHHOLD"}
    for generic, specifics in LESS_SPECIFIC.items():
        if generic in present and any(s in present for s in specifics):
            for r in results:
                if r["icd10"] == generic:
                    r["route"], r["reason"] = "WITHHOLD", "a more specific code is supported at this visit"
    return sorted(results, key=lambda r: ("SUBMIT", "CODER_REVIEW", "WITHHOLD").index(r["route"]))


def route(rec: dict, active: list[dict]) -> tuple[str, str]:
    if not rec["valid_code"]:
        return "CODER_REVIEW", "code not in the validated code set"
    if not active:
        return "WITHHOLD", f"only {rec['status']} mentions"
    if not any(m["section"] in SUPPORT_SECTIONS for m in active):
        return "WITHHOLD", "listed only in problem list / history / meds, no MEAT at this visit"
    if not rec["meat"]:
        return "CODER_REVIEW", "mentioned in the note but no MEAT cue found"
    if rec["confidence"] < ACCEPT_CONF:
        return "CODER_REVIEW", "low-confidence match (short or ambiguous term)"
    return "SUBMIT", "valid code, active, MEAT: " + "".join(sorted(rec["meat"]))


def process_text(text: str, extractor=None, cs: CodeSet | None = None) -> list[dict]:
    cs = cs or CodeSet()
    extractor = extractor or OfflineExtractor(cs)
    return [{"dos": v["dos"], "codes": code_visit(split_sections(v["text"]), extractor, cs)}
            for v in split_visits(text)]


def process_pdf(path: str, extractor=None, cs: CodeSet | None = None) -> dict:
    text, methods = extract_text(path)
    return {"file": path, "page_methods": methods, "visits": process_text(text, extractor, cs)}
