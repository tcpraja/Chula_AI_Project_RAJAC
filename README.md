# Heater C advisory (SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION)

Offline, auditable decision-support prototype for one anonymized biomass thermic-fluid heater (`HEATER_C_SYNTHETIC`).
All data are synthetic. Humans decide; BMS / SIS / hardwired trips / DCS remain the only control authorities. Nothing here writes to a plant system.
Rules, scope and phase status: `CLAUDE.md`, `docs/SPEC.md`, `reports/PHASE_STATUS.md`.

## Quick start (Windows)
```powershell
.\run_dashboard.ps1          # activates .venv, runs: streamlit run app.py   -> http://localhost:8501
```
Linux / macOS / Git Bash: `./run_dashboard.sh`. The server binds to 127.0.0.1 only (`.streamlit/config.toml`).

## Six screens
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
