# How to use the Heater C dashboard (SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION)
Written for the project owner, a reviewer or a manager who opens the dashboard for the first time. All data are synthetic; nothing here controls a plant. The same content is in slides 37–45 of `reports/Heater_C_Full_Project_Presentation.pptx`.

## 1 Start it (5 steps)
1. Open PowerShell in the project folder `heater_c_ai_mvp`. It needs the `.venv` (Python 3.11, packages pinned in `requirements.lock.txt`); no internet is needed.
2. Run `.\run_dashboard.ps1` (it activates the venv and runs `streamlit run app.py`). On Linux, macOS or Git Bash: `./run_dashboard.sh`.
3. Open **http://localhost:8501** in a browser on the same computer. The server listens on 127.0.0.1 only.
4. Use the tabs along the top and the sidebar on the left.
5. Stop with Ctrl+C in the terminal. If the port is busy, add `--server.port 8502` to the command.
Rebuild all results with `python -m src.pipeline --stage all`, run the tests with `python -m pytest -q`, retake the screenshots with `python -m src.capture_screenshots`.
Deep links: `/optimize?pos=295` starts the replay at row 295; `/recommendations?filter=advice` opens on advised rows.

## 2 Always visible
Red banner "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION"; time zone label Asia/Bangkok (UTC+07:00); badges CALCULATED (from validated inputs), PROXY (estimated, unverified), UNAVAILABLE (cannot be computed); a provenance note under every chart saying where the numbers come from and what they are not.

## 3 Inputs: every control
| Input | Where | Allowed values | Effect |
|---|---|---|---|
| Data source | Sidebar | Default synthetic file, or Upload CSV (up to 50 MB, same columns as the default file; schema-checked) | An uploaded file is never verified and gets no advice (every row NO ADVICE) |
| Date range | Sidebar | Within the data dates; default is the held-out test period | Filters every page |
| Replay position, ◀ step, step ▶, Play | Live, Optimize | A row of the selected period; Play moves one row (5 minutes of plant time) per second | Sets "now"; future rows are never shown |
| Trailing window | Live | 2, 6, 12 or 24 hours | Chart span |
| Row filter and timestamp | Advice | All, ADVICE only, NO ADVICE only | Chooses the recommendation to read |
| FD and grate targets | What-if | FD 20–100 %, grate 0–100 %, move at most ±4 % per axis (from `config/guardrail_limits.yaml`) | Outside the bounds: an error and no result (values are not clipped) |
| Role ID, decision, reason, note | Decisions | OP-A or OP-B; accept, reject or defer; a coded reason; note up to 200 characters, no names | Saved in `data/operator_log.db` and the audit log; accept only on an ADVICE row |
| Price, hours, tariff, watts | Value | Editable ASSUMED numbers | Recomputes the THB sensitivity |

## 4 What each page shows and how to read it
- **Live**: tiles (HTF outlet, fuel, SFC, useful heat, efficiency, advisory gate), then trend charts. The SFC chart has a baseline band (P25–P75 in the same load band): a reference, not a target. Efficiency shows an interval when the fuel lot has no lab LHV.
- **Combustion**: lab moisture and LHV per lot (gaps are shown, never filled), O2 and CO against the synthetic floor and limit, FD/ID/grate commands (commands, not airflow), temperatures, draft, ash, economizer ΔP, a fault table.
- **Optimize**: efficiency now (chemistry) against the best reachable inside the limits, a list "What to change now", every operating parameter with target and action, lever sensitivities, heat balance, predicted forward-fan moves, mass balance, 6-hour trend. Take one bounded FD step, then re-check CO and draft.
- **Advice**: the gate first (big red NO ADVICE with reason codes, or ADVICE), then current vs proposed settings, the 90 % interval, a seven-line constraint checklist, and the chemistry view. Always "human review required".
- **What-if**: try an FD and grate target inside the bounds; see predicted SFC, O2, CO, draft and which checks pass.
- **Decisions**: log accept, reject or defer with a reason; table and CSV download; action log by shift.
- **Value**: SFC index, THB sensitivity on ASSUMED inputs, electricity. "No verified savings."

## 5 Reading rules that keep you safe
NO ADVICE is the default and is correct whenever data are missing, stale, transient or outside limits. A suggestion is never an instruction: the operator decides in the existing DCS, within signed limits. If the page says a lot has no lab assay, do not trust any efficiency number for it.
