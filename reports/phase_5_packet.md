# Phase 5 Packet — Dashboard, shadow replay, QA (SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION)
## 1 Implemented
Built a six-page Streamlit app (st.navigation / st.Page, one module per page) with a sidebar loader (default synthetic file; CSV upload only after a schema check), time filter, Asia/Bangkok label, permanent red banner, CALCULATED / PROXY / UNAVAILABLE badges, a provenance caption under every chart and st.cache_data loading. Added a single-move what-if evaluator, a SQLite operator-decision log, a shadow replay of the held-out split with a rule comparator, a `shadow` pipeline stage, launch scripts, README, 16 tests and a QA note.
## 2 Files
app.py; src/dashboard/{common,p1_live,p2_combustion,p3_recs,p4_whatif,p5_decisions,p6_value}.py; src/whatif.py, oplog.py, shadow.py; src/pipeline.py (stage shadow); run_dashboard.ps1/.sh; README.md; .streamlit/config.toml (bind 127.0.0.1); tests/test_app_smoke.py; reports/shadow_replay.csv, dashboard_qa.md.
## 3 Provenance & assumption IDs
All data SYNTHETIC (seed 42). Effect model, baseline band: OWN-ESTIMATE. Limits ASSUMED / NOT APPROVED (config/guardrail_limits.yaml). Screen 6 price 2,500 THB/t, 7,000 h/yr, 4 THB/kWh, 30 W model server = ASSUMED placeholders, editable in the UI, not in the register yet.
## 4 Formulas + one worked example
Simulated SFC index = 100 × (1 + share_ADVICE × mean(ΔSFC/SFC)); THB/yr = −effect × (kg/h × h/yr ÷ 1000) × price × fuel_price_index multiplier; model kWh = W/1000 × h.
Test split: 708 of 3,041 rows ADVICE (23.3 %), mean ΔSFC on advised rows −0.99 % → index 99.77 (−0.23 %, 90 % bound mean −0.28…−0.18 %). Fuel 2,860 kg/h × 7,000 h = 20,020 t × 2,500 THB/t = 50.1 M THB → ≈ 0.115 M THB/yr as a sensitivity on an assumed price. Not a saving.
## 5 Evidence
- Tests: 99 passed (83 + 16). Shadow run twice: identical sha256 2c03d90fae1c9ba2…78ba51c; counts match Phase 4 (ADVICE 708 / NO_ADVICE 1,518 / DIAGNOSTIC_ONLY 815).
- Shadow vs rule P75 (3,041 rows): rule undefined 1,334; both alert 203; AI only 505; rule only 164; neither 835. Of 708 AI advice rows, 8.9 % are rows where the generator's best action is HOLD/NONE.
- App started in background; http://localhost:8501 → HTTP 200, /_stcore/health ok. Screenshots: not yet taken.
## 6 Checklist
- 6 pages run, banner + timezone label on each: PASS
- NO ADVICE shown large on gated row, with reason codes and human-review text: PASS
- What-if out-of-bounds → error, no output: PASS
- Operator log OP-A/OP-B only, SQLite + CSV download: PASS
- Shadow replay deterministic: PASS
- Upload accepted only after schema check: PASS (function-level; widget not driven)
- Visual review / six screenshots: NEEDS DATA (user to take)
- Play/auto-advance behaviour in a real browser: NEEDS DATA
- Business value verified: FAIL by design ("no verified savings")
## 7 Known faults/limits & fix
- Replay split is 16.3 % of rows, not 20 %; to hit 20 % the split fractions of Phase 3 would have to change (not done).
- Uploads get no advice (no records) and no what-if; running the optimizer on uploads would need an OOD/lot check on foreign data — deferred.
- Phase 4 open items unchanged (355 off-menu moves, AI not clearly better than the rule on hit rate / false alerts).
- pandas FutureWarning in guardrails.py (fillna on float column); fix before pandas 4.
## 8 Decision needed
APPROVE PHASE 4 and PHASE 5 after you open http://localhost:8501 and take the six screenshots? Also: keep the 16.3 % test split as "held-out", and confirm or replace the ASSUMED screen-6 inputs.
