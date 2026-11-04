import json
import os

import pytest

from chartcoder.codes import CodeSet
from chartcoder.evaluate import score
from chartcoder.extractor import parse_json_array
from chartcoder.meat import meat_elements
from chartcoder.pipeline import process_pdf, process_text
from chartcoder.visits import split_sections, split_visits
from scripts.make_synthetic import main as make_synthetic

NOTE = """Date of Service: 01/02/2025
HPI: follow up of type 2 diabetes and hypertension.
Problem List: type 2 diabetes, hypertension, GERD.
Family History: Mother had breast cancer at 60.
ROS: Patient denies chest pain or palpitations.
Assessment and Plan:
1. Type 2 diabetes: A1c 7.4 today, continue metformin.
2. Hypertension: BP 138/84 today, continue lisinopril 20 mg.
3. Possible early dementia, will reassess with cognitive testing.
"""


def routes(text):
    return {c["icd10"]: c["route"] for c in process_text(text)[0]["codes"]}


def test_codeset_validation():
    cs = CodeSet()
    assert cs.is_valid("E11.9") and not cs.is_valid("E11.99") and not cs.well_formed("U07")


def test_visit_and_section_split():
    text = NOTE + "\nDate of Service: 03/04/2025\nAssessment and Plan:\n1. GERD: continue omeprazole.\n"
    visits = split_visits(text)
    assert [v["dos"] for v in visits] == ["01/02/2025", "03/04/2025"]
    keys = {k for k, _ in split_sections(visits[0]["text"])}
    assert {"hpi", "problems", "fh", "ros", "ap"} <= keys


def test_meat_and_routing_on_traps():
    r = routes(NOTE)
    assert r["E11.9"] == "SUBMIT" and r["I10"] == "SUBMIT"
    assert r["K21.9"] == "WITHHOLD"          # problem list only, no MEAT at this visit
    assert r["C50.919"] == "WITHHOLD"        # family history
    assert r["R07.9"] == "WITHHOLD"          # negated
    assert r["F03.90"] == "WITHHOLD"         # uncertain ("possible")


def test_combination_rule_diabetes_ckd():
    note = ("Date of Service: 01/02/2025\nAssessment and Plan:\n1. Type 2 diabetes: A1c 7.1, continue metformin.\n"
            "2. CKD stage 3: eGFR 48, stable.\n")
    r = routes(note)
    assert r["E11.22"] == "SUBMIT" and r["N18.3"] == "SUBMIT" and r["E11.9"] == "WITHHOLD"


def test_meat_cues():
    assert set(meat_elements(["Hypertension: BP 150/90, increase amlodipine."])) == {"E", "T"}
    assert meat_elements(["Hypertension."]) == {}


def test_llm_json_parsing_is_tolerant():
    raw = "```json\n[{\"mention\": \"HTN\", \"icd10\": \"I10\"}, {\"bad\": 1}]\n```"
    assert parse_json_array(raw) == [{"mention": "HTN", "icd10": "I10"}]
    assert parse_json_array("no json here") == []


def test_end_to_end_synthetic_pdfs_including_ocr(tmp_path):
    make_synthetic(str(tmp_path), n=5, seed=1)
    gold = json.load(open(tmp_path / "gold.json"))
    preds, golds, methods = [], [], []
    for name in sorted(gold):
        out = process_pdf(str(tmp_path / name))
        methods += out["page_methods"]
        preds += out["visits"]; golds += gold[name]
    assert "ocr" in methods                   # chart_004 is an image-only scan
    res = score(preds, golds)
    assert res["unsupported_submitted"] == 0 and res["recall"] >= 0.9
