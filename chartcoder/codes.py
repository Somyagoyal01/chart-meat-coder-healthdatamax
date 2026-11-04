"""Small ICD-10-CM code set (public CMS code titles) with synonym lookup and validation."""
from __future__ import annotations
import csv
import os
import re

CODE_RE = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")
_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "data", "icd10_subset.csv")


class CodeSet:
    def __init__(self, path: str = _DEFAULT):
        self.codes: dict[str, str] = {}
        self.synonyms: list[tuple[str, str]] = []  # (phrase, code), longest first
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.codes[row["code"]] = row["description"]
                for s in row["synonyms"].split("|"):
                    if s.strip():
                        self.synonyms.append((s.strip().lower(), row["code"]))
        self.synonyms.sort(key=lambda t: len(t[0]), reverse=True)

    def is_valid(self, code: str) -> bool:
        return bool(CODE_RE.match(code or "")) and code in self.codes

    def well_formed(self, code: str) -> bool:
        return bool(CODE_RE.match(code or ""))

    def describe(self, code: str) -> str:
        return self.codes.get(code, "")
