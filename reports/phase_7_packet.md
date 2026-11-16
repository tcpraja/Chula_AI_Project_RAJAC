# Phase 7 Packet — Submission set (SYNTHETIC DATA — NOT FOR PLANT OPERATION)
## 1 Implemented
Built `src/build_final.py` (plus final_nums, final_pdf, final_deck, final_text) that derives baseline/test counts from data CSVs into reports/final_numbers.csv, pulls every metric from reports/*.csv through a ledger, and prints/writes a number→source map (89 numbers). Added the `final` pipeline stage, a 2-page proposal PDF, a 3-page appendix PDF, a 5-slide 16:9 deck with watermark and speaker notes, 6-minute notes, 10-question panel Q&A, source and AI error log, and a scored rubric with the two weakest criteria fixed. Captured the six dashboard screenshots headlessly (src/capture_screenshots.py) and fixed dashboard defects found on them.
## 2 Files
src/{build_final,final_nums,final_pdf,final_deck,final_text,capture_screenshots}.py; final/{Heater_C_Final_Proposal.pdf, Appendix.pdf, Heater_C_Final_Deck.pptx, 6_min_speaker_notes.md, panel_QA.md, source_and_AI_error_log.md, rubric_checklist.md, number_source_map.csv, figs/}; reports/{final_numbers.csv, economics_summary.csv}; assets/screenshots/screen_1..6.png; tests/test_final.py; pipeline stage `final`.
## 3 Provenance & assumption IDs
All metrics keep their Phase 1–6 labels (SYNTHETIC, MEASURED-IN-PROTOTYPE run times, OWN-ESTIMATE 60 W power and CO-analyser range, ASSUMED/fictional THB). Sources: ASME PTC 4 (method reference) and Angelopoulos & Bates 2021 (conformal intervals) as PUBLISHED; name/ID/course parsed from docs/SPEC.md C8.
## 4 Formulas + one worked example
Unchanged from Phase 6 (kWh = W×s/3.6e6; kWh_th = Δfuel kg × LHV / 3.6). Example in the proposal: AI computing for the pilot = 3.6 kWh vs a synthetic fuel-energy reduction of 7,559 kWh thermal over a 253 h replay (≈2,080:1, carriers not netted).
## 5 Evidence
- pypdf: proposal 2 pages (≤3), appendix 3 pages. Deck: 5 slides, 16:9, notes 155/157/158/151/152 words (all 150–170), watermark on slides 1–4 only, one picture each, none is an HMI/P&ID image (hash-checked).
- Tests: 115 passed (107 + 8 in test_final.py incl. denylist scan over PDF/PPTX text and file names).
- `python -m src.pipeline --stage all` clean rebuild: generate→clean→baseline→train→optimize→shadow→final ran; shadow hash unchanged (2c03d90f…), no tracked data/report CSV changed.
- Rubric self-score 75 → 77 of 100 after fixing sustainability (energy boundary table) and talk (shorter notes, cue cards, slack ≈ 16 s).
## 6 Checklist
- Proposal ≤ 3 pages, required identity and sections, baseline "requires validation": PASS
- Simple vs AI + failure + fix + kWh vs fuel energy + countable go/no-go + stop: PASS
- Deck exactly 5 slides, 16:9, notes 150–170 words: PASS
- No hand-typed metrics (map printed): PASS (identity/course text parsed; the 6-week and 60 W constants carry sources)
- No-secrets/denylist over final/: PASS
- Visual review of PDFs and slides in a viewer: NEEDS DATA (no renderer here; only text/geometry tests)
- Live 6-minute rehearsal: NEEDS DATA (estimate ≈ 5:44 at 135 wpm)
## 7 Known faults/limits
- Proposal PDF is dense (9.3 pt) and unseen by a human; slide layout is geometry-checked only.
- Screens 2 and 5 and the Play button were not reviewed by a person. The what-if page now opens on the advisory option.
- PC power remains an unmetered 60 W estimate; THB values fictional; AI not clearly better than the rule (Phase 4).
- Appendix quotes the critique-log paragraph verbatim, so it contains numbers typed in an earlier phase (cited as such).
## 8 Decision needed
APPROVE PHASE 7 and tag v1.0-submission? Please open final/*.pdf and the deck once before submitting (deadline Thu 19 Nov 2026 23:59), and time one rehearsal.
