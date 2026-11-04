"""Split a chart into visits (by date of service) and each visit into sections."""
from __future__ import annotations
import re

DOS_RE = re.compile(r"^\s*(?:date of service|dos|visit date|encounter date)\s*[:\-]\s*(.+?)\s*$", re.I | re.M)
SECTION_ALIASES = {
    "hpi": ["history of present illness", "hpi", "subjective", "chief complaint", "cc"],
    "ros": ["review of systems", "ros"],
    "pmh": ["past medical history", "pmh", "medical history"],
    "fh": ["family history", "fh"],
    "sh": ["social history", "sh"],
    "problems": ["problem list", "active problems", "problems"],
    "meds": ["medications", "current medications", "meds"],
    "exam": ["physical exam", "exam", "objective", "vitals"],
    "labs": ["labs", "results", "data reviewed"],
    "ap": ["assessment and plan", "assessment & plan", "assessment/plan", "a/p", "assessment", "plan", "impression"],
}
_HDR = {alias: key for key, aliases in SECTION_ALIASES.items() for alias in aliases}
HDR_RE = re.compile(r"^\s*(" + "|".join(sorted(map(re.escape, _HDR), key=len, reverse=True)) + r")\s*:\s*(.*)$", re.I)


def split_visits(text: str) -> list[dict]:
    marks = list(DOS_RE.finditer(text))
    if not marks:
        return [{"dos": None, "text": text}]
    visits = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        visits.append({"dos": m.group(1).strip(), "text": text[m.end():end]})
    return visits


def split_sections(visit_text: str) -> list[tuple[str, str]]:
    """Return [(section_key, line)] for every non-empty line; unknown text keeps the last header."""
    current, out = "other", []
    for raw in visit_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = HDR_RE.match(line)
        if m:
            current = _HDR[m.group(1).lower()]
            line = m.group(2).strip()
            if not line:
                continue
        out.append((current, line))
    return out
