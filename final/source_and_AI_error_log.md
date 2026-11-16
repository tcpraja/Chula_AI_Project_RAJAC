# Sources and AI error log (SYNTHETIC DATA; Raja Chairmapandi, 69900089BG)

## Published sources (two, one line each)
- ASME PTC 4, Fired Steam Generators: method reference only for useful heat, fuel input and efficiency (input-output basis); no compliance claim.
- Angelopoulos and Bates (2021), A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification, arXiv:2107.07511: basis of the split-conformal 90 % forecast interval.

## Project sources
- docs/SPEC.md and docs/PILOT_SPEC.md (project-controlled). Course midterm, requirements document, P&ID, interlock document and HMI screenshots exist but were NOT read by the tool; only a qualitative summary in SPEC C1 was used (reports/01_source_evidence_matrix.csv).

## Where AI was used
Claude Code (an AI coding assistant) wrote the generator, pipeline, models, dashboard, tests and documents under my instructions in phases with written packets (reports/phase_*_packet.md). I set the rules (CLAUDE.md), reviewed each packet, and the final numbers come from code (final/number_source_map.csv). A separate critic agent attacked the modelling assumptions (reports/ai_critique_log.md). No AI or network call exists at runtime.

## AI errors found and corrected
1. **Unfair reference (K1 + K2) — real error.** The model card compared against persistence of the *last* fuel value (P), yet the models receive `feeder_speed_pct`, which equals the fuel being fed right now. Verified: repeating the current feed (P2) gives MAE 58.5 kg/h on the test set; the first selected model C0 gave 56.0 (4 % better, not the 21 % claimed over P). Rule 3 (beat persistence by ≥5 %) would have failed. Fix: P2 added; rule 3 uses the better of P and P2; ablations added. After the fix the picture changed: the simplest candidate that beats P2 by a margin is the linear model L (test 53.9 vs 58.5, 7.8 %; validation 11.1 %); boosting adds nothing.

2. **Selection on the test set (K10) — real error.** (see reports/ai_critique_log.md, 'Genuine errors found and fixed')
3. **Conformal calibration reused the tuning rows (K8) — real error.** (see reports/ai_critique_log.md, 'Genuine errors found and fixed')
4. **Fragile leakage canary (K16) — real error.** (see reports/ai_critique_log.md, 'Genuine errors found and fixed')
5. **Extended-population "ALL" mixed different rows (K15, part) — real error.** (see reports/ai_critique_log.md, 'Genuine errors found and fixed')

### Errors found while building the dashboard and final set (this repository, Phases 5-7)
| Error (by the AI assistant) | How found | Correction |
|---|---|---|
| Default page of the dashboard returned 'Page not found' because the default page was given a URL path | First headless screenshot of the running app | Removed the path from the default page (app.py) |
| Metric values on the live screen were cut off ('2487 k...') | Same screenshot | CSS lets metric values wrap (src/dashboard/common.py) |
| Business Value screen showed a gross THB figure that disagreed with the Phase 6 workbook (no realisation share, no running costs) | Cross-reading the screenshot against reports/economics_and_energy.xlsx | Added an explicit caption and renamed axes (src/dashboard/p6_value.py) |
| Smoke test did not read success boxes, so a passing page looked like a failure | Test failure in Phase 5 | Test helper now reads st.success (tests/test_app_smoke.py) |
| Phase 4 tests rewrote models/effect_model.joblib with different bytes, dirtying the repo on every run | git status after tests | Session fixture restores the committed bytes (tests/conftest.py) |
