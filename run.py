"""Generate synthetic charts, code them, and score against gold. Usage: python run.py [--heldout]"""
from __future__ import annotations
import json
import os
import sys
import time

from chartcoder.evaluate import score
from chartcoder.pipeline import process_pdf


def evaluate_dir(folder: str) -> dict:
    gold = json.load(open(os.path.join(folder, "gold.json")))
    preds, golds, methods, t0 = [], [], [], time.time()
    for name in sorted(gold):
        out = process_pdf(os.path.join(folder, name))
        methods += out["page_methods"]
        if len(out["visits"]) != len(gold[name]):
            print(f"  ! {name}: found {len(out['visits'])} visits, gold has {len(gold[name])}")
        preds += out["visits"][:len(gold[name])]; golds += gold[name][:len(out["visits"])]
    res = score(preds, golds)
    res.update(charts=len(gold), ocr_pages=methods.count("ocr"), seconds_per_chart=round((time.time() - t0) / len(gold), 2))
    return res


if __name__ == "__main__":
    if "--heldout" in sys.argv:
        folder, tag = "heldout", "heldout"
    else:
        from scripts.make_synthetic import main as make
        make("data/synthetic"); folder, tag = "data/synthetic", "synthetic"
    res = evaluate_dir(folder)
    os.makedirs("results", exist_ok=True)
    json.dump(res, open(f"results/metrics_{tag}.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "errors"}, indent=1))
    for e in res["errors"][:15]:
        print("  ", e)
