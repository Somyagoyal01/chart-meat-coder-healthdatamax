"""Diagnosis extraction.

Two interchangeable extractors return the same JSON-style records:
- OfflineExtractor: a scripted, rule-based stand-in for the LLM (no API key needed). Used for tests and the demo.
- LLMExtractor: sends each visit to an OpenAI-compatible chat model and asks for JSON. Same downstream checks.
"""
from __future__ import annotations
import json
import os
import re

from .codes import CodeSet

NEG_CUES = ["denies", "no evidence of", "negative for", "without", "no ", "not ", "ruled out", "free of"]
UNCERTAIN_CUES = ["possible", "probable", "suspected", "suspect", "rule out", "r/o", "likely", "concern for", "versus", " vs "]
HISTORY_CUES = ["history of", "h/o", "s/p", "resolved", "prior", "previous", "remote", "in remission"]
FAMILY_CUES = ["mother", "father", "brother", "sister", "family history", "grandmother", "grandfather", "sibling"]
SHORT_AMBIGUOUS = 3  # synonyms this short (e.g. 'ra', 'af', 'pad') get lower confidence
SENT_RE = re.compile(r"(?<=[.;])\s+")


def _window(sentence: str, start: int, before: int = 40) -> str:
    return sentence[max(0, start - before):start].lower()


def _status(sentence: str, start: int, section: str) -> str:
    pre = _window(sentence, start)
    if section == "fh" or any(c in pre for c in FAMILY_CUES):
        return "family"
    if any(c in pre for c in NEG_CUES):
        return "negated"
    if any(c in pre for c in UNCERTAIN_CUES):
        return "uncertain"
    if any(c in pre for c in HISTORY_CUES) or section == "pmh" and "resolved" in sentence.lower():
        return "historical"
    return "active"


class OfflineExtractor:
    name = "offline-scripted"

    def __init__(self, codeset: CodeSet | None = None):
        self.cs = codeset or CodeSet()
        self._pats = [(re.compile(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])"), p, c) for p, c in self.cs.synonyms]

    def extract(self, sections: list[tuple[str, str]]) -> list[dict]:
        found = []
        for section, line in sections:
            for sent in SENT_RE.split(line):
                low = sent.lower()
                taken: list[tuple[int, int]] = []
                for pat, phrase, code in self._pats:
                    for m in pat.finditer(low):
                        s, e = m.span()
                        if any(s < te and e > ts for ts, te in taken):
                            continue  # a longer phrase already claimed this text
                        taken.append((s, e))
                        conf = 0.9 if section == "ap" else 0.8
                        if len(phrase) <= SHORT_AMBIGUOUS:
                            conf -= 0.2
                        found.append({"mention": sent[s:e], "icd10": code, "section": section,
                                      "status": _status(sent, s, section), "sentence": sent.strip(),
                                      "confidence": round(conf, 2)})
        return found


PROMPT = """You are a medical coding assistant. From the visit note below, list every diagnosis mentioned.
Return ONLY a JSON array. Each item: {{"mention": exact words from the note, "icd10": the most specific ICD-10-CM code,
"section": one of hpi|ros|pmh|fh|problems|meds|exam|labs|ap|other, "status": active|negated|historical|family|uncertain,
"sentence": the full sentence it came from, "confidence": 0-1}}.
Do not invent codes. Mark ruled-out or 'possible' diagnoses as uncertain.

VISIT NOTE:
{note}"""


class LLMExtractor:
    """Real-LLM path (not used in tests). Needs `pip install openai` and OPENAI_API_KEY."""
    name = "llm"

    def __init__(self, model: str | None = None):
        from openai import OpenAI  # imported lazily so the offline mode has no dependency
        self.client = OpenAI()
        self.model = model or os.getenv("CHARTCODER_MODEL", "gpt-4o-mini")

    def extract(self, sections: list[tuple[str, str]]) -> list[dict]:
        note = "\n".join(f"[{s}] {l}" for s, l in sections)
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(note=note)}])
        return parse_json_array(resp.choices[0].message.content)


def parse_json_array(text: str) -> list[dict]:
    """Tolerant JSON parsing: strips code fences and keeps only dict items with an icd10 field."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and d.get("icd10")]
