# chart-meat-coder

> Personal project by Somya Goyal, built while applying to Health Data Max. Not affiliated with or endorsed by Health Data Max; uses public code titles and synthetic/fictional charts only. No real patient data.

Reads medical-chart PDFs (text or scanned), splits them into visits, finds diagnoses, maps them to ICD-10-CM codes and checks whether each one is **supported by MEAT at that visit** (Monitored, Evaluated, Assessed, Treated). Every code is routed to **SUBMIT**, **CODER_REVIEW** or **WITHHOLD**, with the evidence sentences a coder needs to check it.

## Why this matters for Health Data Max

- **Problem.** In risk adjustment, a diagnosis that is real but not supported by MEAT documentation at the encounter is denied in a RADV audit. Problem-list-only mentions, copied-forward history, negations ("denies chest pain") and family history are the usual traps ([HCC Buddy, MEAT criteria](https://hccbuddy.com/academy/meat-criteria-risk-adjustment)).
- **Who feels it.** Coders reviewing LLM suggestions, and the payers/ACOs whose submissions get audited. Health Data Max describes its platform as validating risk-adjustment submissions ([company profile](https://www.crunchbase.com/organization/health-data-max)). Its Healthcare AI Data Scientist JD (Naukri, Nov 2026) describes a chart system that "reads patient charts (PDFs), extracts the text, and uses LLMs to find diagnoses and their ICD-10 codes for coders to review", with accuracy measured against coder-reviewed samples.
- **What this shows.** A small, testable version of that loop with an explicit MEAT gate and an honest evaluation, so that what the LLM suggests and what a coder should submit stay separate. *Estimate, not measured:* if a coder spends ~1 min confirming a code with evidence shown versus ~3 min hunting for support, a 25% review rate on a 20-code chart saves roughly 30 min per chart. The assumptions are illustrative only.

## How it works

```
PDF ──► text layer (PyMuPDF) ──► OCR fallback for scanned pages (Tesseract)
    ──► split by Date of Service ──► sections (HPI, Problem List, FH, ROS, A/P …)
    ──► extractor (offline scripted "LLM"  |  real LLM returning JSON)
    ──► ICD-10-CM validation + specificity / combination rules (E11.9 + N18.3 → E11.22)
    ──► MEAT evidence check on A/P, HPI, exam and lab sentences
    ──► route: SUBMIT / CODER_REVIEW / WITHHOLD, with reasons and evidence
```

| file | what it does |
|---|---|
| `chartcoder/pdf_text.py` | PDF text extraction; OCR for pages with no text layer |
| `chartcoder/visits.py` | splits a chart into visits and sections |
| `chartcoder/codes.py` | 50-code ICD-10-CM subset (public CMS titles) with synonyms and format checks |
| `chartcoder/extractor.py` | `OfflineExtractor` (rules standing in for the LLM, used in tests) and `LLMExtractor` (OpenAI-compatible, JSON output) |
| `chartcoder/meat.py` | MEAT cue detection |
| `chartcoder/pipeline.py` | combination/specificity rules and routing |
| `chartcoder/evaluate.py` | precision/recall vs gold, withhold accuracy, review rate |
| `scripts/make_synthetic.py` | synthetic multi-visit charts with traps, plus gold labels; 1 in 5 is rendered as a scan |
| `heldout/` | 8 hand-written fictional charts (2 scanned) and hand labels, written **after** the code was frozen |

## Results (real numbers from `python run.py` and `python run.py --heldout`)

| set | charts / visits | precision | recall | withheld correctly | unsupported codes submitted | sent to coder review |
|---|---|---|---|---|---|---|
| synthetic (same templates the rules were written against) | 40 / 85 | 1.00 | 1.00 | 100% | 0 | 0% |
| **hand-written held-out (written after code freeze)** | 8 / 9 | **0.95** | **0.80** | **11/12** | **1** | **25.6%** |

The synthetic score is self-confirming: the generator and the rules were written together. The held-out set is the number to trust, and its errors are the useful part:

1. **One unsupported code submitted.** A bare A/P line "Hyperlipidemia." passed the MEAT check because the cue word *lipid* sits inside the diagnosis name itself. Fix: strip the matched mention before looking for cues.
2. **Specificity lost.** "Chronic systolic CHF" was read as generic CHF (I50.9), not I50.22, because the abbreviation wasn't in the synonym list. It went to review rather than being submitted wrong.
3. **Abbreviation caution costs coder time.** HTN, CAD and PAD are short, ambiguous matches, so they go to review (25.6% review rate). This is deliberate: "RA" also matched "93% RA" (room air), which would otherwise have produced a rheumatoid-arthritis code.
4. **Sentence splitting cut the evidence away.** In "GERD - patient asks about naproxen; continue omeprazole", the split at ";" separated GERD from its treatment, so it went to review. Fix: link MEAT cues to the whole numbered A/P item, not the sentence.
5. **"Former smoker"** was not treated as history, so it was sent to review instead of being withheld.

OCR: the 2 scanned held-out pages were read by Tesseract with no change in results. Speed offline: ~0.2 s per chart.

## Run it

```bash
pip install -r requirements.txt      # tesseract binary is optional (only for scanned PDFs)
python run.py                        # synthetic set
python -m scripts.build_heldout && python run.py --heldout
pytest -q                            # 7 tests
```

Real LLM path: `pip install openai`, set `OPENAI_API_KEY`, and pass `LLMExtractor()` to `process_pdf(path, extractor=...)`. Its output goes through the same code validation, MEAT check and routing, so the LLM can suggest codes but cannot submit them unchecked.

## Limitations / next steps

- The 50-code subset and keyword MEAT cues are a demo. A real version would use the full ICD-10-CM table, an HCC mapping and an LLM or classifier for MEAT, trained on coder decisions.
- Fix the five error types above, then re-test on a *new* blind set rather than re-using this one.
- Track per-code precision against coder overrides, because coder feedback is the real gold.
- MongoDB storage and Azure Functions deployment (as in the JD) are not included here.
