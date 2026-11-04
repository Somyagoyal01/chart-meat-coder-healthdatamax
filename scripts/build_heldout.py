"""Render the hand-written held-out notes (heldout/src/*.txt) to PDF. h04 and h07 are rendered as scans (OCR path)."""
import glob
import json
import os
import shutil

from scripts.make_synthetic import write_pdf

for path in sorted(glob.glob("heldout/src/*.txt")):
    name = os.path.basename(path).replace(".txt", ".pdf")
    write_pdf(open(path).read(), os.path.join("heldout", name), scanned=name in {"h04.pdf", "h07.pdf"})
shutil.copy("heldout/src/gold.json", "heldout/gold.json")
print("held-out PDFs:", len(json.load(open("heldout/gold.json"))))
