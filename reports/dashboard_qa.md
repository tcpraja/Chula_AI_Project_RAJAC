# Dashboard QA (Phase 5) — SYNTHETIC SIMULATION, NOT FOR PLANT OPERATION
Scope: `app.py` + `src/dashboard/` (6 pages), `src/whatif.py`, `src/oplog.py`, `src/shadow.py`. Streamlit 1.67.0, Plotly 7.1.0.

## What was checked automatically (tests/test_app_smoke.py, 16 tests, all pass; full suite 99 pass)
| Check | Result |
|---|---|
| Each of the 6 pages runs under `AppTest` with no exception | PASS |
| `app.py` (st.navigation, default page) runs with no exception | PASS |
| Red banner "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION" and the Asia/Bangkok label present on every page | PASS |
| Screen 3 on a gated test row: shows NO ADVICE, reason code, HUMAN REVIEW REQUIRED, no proposed-settings table | PASS |
| Screen 3 on an ADVICE row: shows proposal table | PASS |
| Screen 4 out-of-bounds input (FD 500 %): error shown, zero result metrics | PASS |
| What-if evaluator reproduces the Phase 4 advice record (SFC option, 90 % bound within 0.002); NaN, out-of-range and over-step moves raise | PASS |
| Operator log: only OP-A / OP-B (also enforced by SQLite CHECK), reason mandatory, note ≤ 200 chars, cannot accept NO ADVICE; page logs a decision | PASS |
| Upload schema check rejects missing columns / <10 rows | PASS |
| Shadow replay: fail-safe rows carry no action, human review true; two runs byte-identical (sha256 `2c03d90f…ba51c`) and equal to the committed file | PASS |

## Design decisions to know about
- Held-out replay = the Phase 3 test split: 3,041 rows = 16.3 % of 18,655 (chronological, lot-aware split), not exactly 20 %.
- Gating is fail-safe: any timestamp without an advisory record (outside test/val, or any uploaded file) is shown as NO ADVICE with reason NO_RECORD. Uploads therefore never receive advice, and the what-if page is disabled for them.
- Badges: CALCULATED, PROXY (= pipeline status ESTIMATED), UNAVAILABLE. η is shown only when `status_eta` is not UNAVAILABLE.
- Baseline band (screen 1) = P25–P75 of training-split eligible CALCULATED SFC per 1 MW load band (OWN-ESTIMATE); a reference, not a target.
- Fan values are labelled "command, not airflow". CO shows "sensor not available" / a warning when `co_available = 0`.
- Screen 5 "operator action log by shift" uses generator shift IDs OP-A / OP-B / OP-C; new decisions are limited to OP-A / OP-B. Log DB `data/operator_log.db` is git-ignored.
- Server binds to 127.0.0.1 only (config); no external calls from the app.

## Not verified (honest limits)
- No human has looked at the rendered pages yet: the six screenshots (assets/screenshots/screen_1..6.png) are still to be taken. Visual layout, colours and chart readability are untested.
- Play / auto-advance (fragment timer) is not exercised by AppTest; only the step buttons and slider path are plain code. Test it by hand.
- File upload through the browser widget is not driven in tests (schema function is).
- Screen 6 THB values come from ASSUMED inputs (price 2,500 THB/t, 7,000 h/yr, 4 THB/kWh, 30 W) — placeholders, not data.
- Streamlit prints a pandas FutureWarning from `guardrails.py` (fillna on float column); harmless today, not changed in this phase.
