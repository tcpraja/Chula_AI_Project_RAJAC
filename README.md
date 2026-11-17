# Heater C advisory (SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION)

Offline, auditable decision-support prototype for one anonymized biomass thermic-fluid heater (`HEATER_C_SYNTHETIC`).
All data are synthetic. Humans decide; BMS / SIS / hardwired trips / DCS remain the only control authorities. Nothing here writes to a plant system.
Rules, scope and phase status: `CLAUDE.md`, `docs/SPEC.md`, `reports/PHASE_STATUS.md`.

## Quick start (Windows)
```powershell
.\run_dashboard.ps1          # activates .venv, runs: streamlit run app.py   -> http://localhost:8501
```
Linux / macOS / Git Bash: `./run_dashboard.sh`. The server binds to 127.0.0.1 only (`.streamlit/config.toml`).

## Six screens (page tabs along the top; data source and time filter in the sidebar)
1 Live Performance (replay slider / play) · 2 Combustion Diagnostics · 3 AI Recommendations (NO ADVICE is the fail-safe) ·
4 What-if Simulator (inputs bounded by `config/guardrail_limits.yaml`) · 5 Operator Decisions (OP-A / OP-B → `data/operator_log.db`, CSV download) ·
6 Business Value (index, ASSUMED-input THB sensitivity, "no verified savings").
Sidebar: default synthetic file or CSV upload (schema-checked, never verified), time filter, Asia/Bangkok label.

## Rebuild and checks
```powershell
.venv\Scripts\python -m src.pipeline --stage all        # generate, clean, baseline, train, optimize, shadow
.venv\Scripts\python -m src.pipeline --stage shadow     # held-out replay -> reports/shadow_replay.csv (deterministic)
.venv\Scripts\python -m pytest -q --tb=short            # 99 tests, includes streamlit AppTest smoke tests
```
Screenshots for the report go in `assets/screenshots/screen_1.png … screen_6.png`. QA notes: `reports/dashboard_qa.md`.

## Submission set (Phase 7)
```powershell
.venv\Scripts\python -m src.capture_screenshots          # six dashboard screenshots via headless Edge/Chrome (optional)
.venv\Scripts\python -m src.pipeline --stage all         # clean rebuild incl. final/ (proposal, appendix, deck, notes, Q&A) and number -> source map
```
`final/` holds Heater_C_Final_Proposal.pdf (2 pages), Appendix.pdf, Heater_C_Final_Deck.pptx (5 slides), 6_min_speaker_notes.md, panel_QA.md, source_and_AI_error_log.md, rubric_checklist.md and number_source_map.csv. Every number in them comes from reports/*.csv via `src/build_final.py`.

## Pilot package (Phase 8, synthetic only)
Read-only adapters (`src/adapters/`), site config (`config/site_template.yaml`), tag map (`config/tag_map_template.yaml`), monitor (`python -m src.monitor`), retrain (`python -m src.retrain --dry-run`), audit log (`python -m src.audit --verify`), M&V (`python -m src.mv_report --mode retrospective`), Docker files and site documents (INSTALL_SITE.md, OPERATIONS.md, ROLLBACK.md, SECURITY_NOTES.md).
Scripts to run yourself outside Claude Code, printing file paths only: `run_real_retrospective.ps1`, `run_real_live_shadow.ps1`, `run_real_mv.ps1`. Demo data: `python -m src.site_demo` (invented tags, site units).
