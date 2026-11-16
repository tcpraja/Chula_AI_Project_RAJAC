# Phase 6 Packet — Pilot plan, scorecard, economics and energy, risk, SOP, privacy (SYNTHETIC / FICTIONAL — NOT FOR PLANT OPERATION)
## 1 Implemented
Timed the pipeline and dashboard on this PC, computed the synthetic fuel-energy and fan-electricity change from the held-out replay, built a formula-driven workbook (assumptions, model, tornado) with a tiny formula evaluator to check it without Excel, drew the tornado chart, and wrote the six-week plan, scorecard, risk register, operator SOP draft, executive decision gate and privacy note. Targets and stop conditions are quoted verbatim from docs/PILOT_SPEC.md and tested.
## 2 Files
reports/{pilot_plan_6_weeks.md, pilot_scorecard.csv, economics_and_energy.xlsx, risk_register.md, operator_SOP_draft.md, executive_decision_gate.md, privacy_PDPA.md, ai_runtime_measured.csv, energy_synthetic.json, economics_calc.json, figs/p6_tornado.png}; src/{measure_runtime, energy_calc, economics, xl_eval}.py; tests/test_energy_math.py.
## 3 Provenance & assumption IDs
Run times MEASURED-IN-PROTOTYPE (wall clock, 3 repeats). PC power OWN-ESTIMATE: 60 W busy (35–100 W), 20 W dashboard open (15–30 W); no wattmeter, method in the workbook. Fuel/fan energy SYNTHETIC. Fuel price 1,800–3,200 THB/t, tariff 3–5.5 THB/kWh, hours, labour, engineering, upkeep, realisation share (0.2/0.5/1.0): ASSUMED, fictional, yellow cells. CO-analyser 0.35–1.2 M THB: OWN-ESTIMATE range, not a quote. Not yet added to reports/04_assumptions_register.csv.
## 4 Formulas + one worked example
kWh = W × s ÷ 3.6e6; fuel energy kWh = Δfuel_kg × LHV_MJ/kg ÷ 3.6; Δfuel_kg per row = fuel_kg/h × 5/60 × ΔSFC/SFC; fan Δ = kW_FD × ((FD_new/FD)³ − 1) × 5/60 h; net = simulated saving × realisation × fuel cost − running cost; payback = one-time ÷ net if net > 0.
Example (base): train 18.5 s × 7 runs × 60 W ÷ 3.6e6 = 0.0022 kWh; whole 6-week AI workload 3.63 kWh (dashboard left open 6 h/day at 20 W dominates: 3.6 kWh).
## 5 Evidence
- Tests: 107 passed (99 + 8). test_energy_math recomputes kWh, MJ→kWh, fuel/fan energy and the cost chain independently and compares with the workbook formulas; checks every row is labelled, formulas are live, targets/stops verbatim, SOP header.
- Measured wall s (mean of 3): generate 2.55, train 18.5, shadow 2.36, dashboard start 1.54, page render 0.18–0.51.
- AI electricity base (range): 3.63 kWh / 6 weeks (1.37–9.06), 2.60 kWh/month (0.98–6.47), 31.6 kWh/yr.
- Synthetic fuel energy change over the 253.4 h window: −7,559 kWh thermal (90 %: −9,111…−5,936; coefficient uncertainty only); FD fan electricity −49.7 kWh (+12.1 / −61.8). No CO2 claim (no lifecycle boundary).
- Economics, THB (fictional) pess/base/opt: one-time 1.58 M / 0.88 M / 0.43 M; running 0.43 / 0.21 / 0.08 M per yr; net −416 k / −155 k / +93 k per yr; payback NO PAYBACK / NO PAYBACK / 4.6 yr; fuel saving needed 1.40 / 0.43 / 0.11 % vs simulated 0.05 / 0.12 / 0.24 % after realisation. Tornado: reports/figs/p6_tornado.png.
## 6 Checklist
- All seven requested documents exist, DRAFT/approval headers present: PASS
- Workbook formulas live, every row labelled, evaluator = independent recomputation: PASS
- Stop conditions and targets verbatim from PILOT_SPEC: PASS
- AI run times measured now: PASS (wall time, not CPU time; one dashboard start sample)
- PC power measured: FAIL (OWN-ESTIMATE only, no meter)
- Excel/LibreOffice opened the workbook: NEEDS DATA (not available here; checked by Python evaluator)
- Any saving or payback verified: FAIL by design (NO VERIFIED SAVINGS)
## 7 Known faults/limits
- AI electricity is negligible next to every business term; the tornado shows it as no visible bar. Power and run counts are guesses; a plug-in meter would fix the power.
- Tornado is on net annual effect; one-time costs (engineering, CO analyser) change payback only and do not show as bars.
- Fuel-energy interval covers ridge-coefficient uncertainty only; realisation share and price are placeholders.
- The workbook has no cached values until opened in Excel; the evaluator does the check meanwhile.
- models/effect_model.joblib is rewritten by the Phase 4 tests with different bytes; I reverted it to the committed file before committing.
## 8 Decision needed
APPROVE PHASE 6 (and Phases 4–5, still unconfirmed)? Replace the ASSUMED THB inputs with site values or keep them as fictional ranges? Executive gate currently recommends REVISE, not GO.
