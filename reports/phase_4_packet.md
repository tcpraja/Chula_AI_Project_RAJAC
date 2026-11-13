# Phase 4 Packet — Guardrails, simulated-option optimizer, AI vs rule (SYNTHETIC - NOT FOR PLANT OPERATION)
## 1 Implemented
Built pure-function guardrails (layer 1 data + layer 2 constraints, limits from config, REQUIRES_OEM_APPROVAL forces NO_ADVICE), an action-effect model (ridge efficiency response with 200 lot-bootstraps, stoichiometric O2-from-FD, draft/CO/fan-law models, Mahalanobis OOD detector; training split only), a 25-move FD x grate optimizer at fixed demand with objective SFC + λ1 fan power + λ2 move + λ3 interval width, advisory records (no actuation fields, human_review_required=True), the AI-vs-rule comparison on the test split, three reports, an `optimize` pipeline stage and 23 new tests.
## 2 Files
src/guardrails.py, optimizer.py, compare.py; config/guardrail_limits.yaml; tests/test_advisory_gate.py; models/effect_model.joblib; data/advisory/advisory_records_{val,test}.jsonl; reports/scenario_comparison.csv, constraints_matrix.md, optimization_failure_cases.md; pipeline.py (stage optimize).
## 3 Provenance & assumption IDs
All SYNTHETIC, seed 42, limits ASSUMED / NOT APPROVED (A-register limits; same values as config/cleaning_engineering.yaml, tested equal). Effect model = OWN-ESTIMATE (ridge, associational). Weights λ1 0.02 kg/GJ per kW, λ2 0.03 per % move, λ3 0.25, O2 margin 0.3, CO factor 1.25 are arbitrary, set before looking at results, not tuned. Fan law kW∝FD^3 (A-register fan proxy).
## 4 Formulas + one worked example
SFC = 1000/(eta·LHV_MJ/kg); λ_air = 21/(21−O2), λ_new = λ·FD_new/FD; O2_new = 21(1−1/λ_new); J = ΔSFC + λ1ΔkW + λ2(|dFD|+|dG|) + λ3·width90. ADVICE needs the 95th-percentile ΔSFC < 0 and width ≤ 3.0 kg/GJ.
Test row 2026-03-01 00:35: FD 62.5→60.5 (FD-2), grate 42.8 unchanged, O2 7.34 %; predicted SFC 90.848→90.513 kg/GJ (Δ −0.334, 90 % interval [−0.422, −0.243], −0.37 %, +0.25 pp eta); class LESS_EXCESS_O2. Synthetic illustration only.
## 5 Evidence
- Tests: 83 passed (60 + 23). Gate: 1 ACCEPT + 12 NO_ADVICE cases pass (missing CO → DIAGNOSTIC_ONLY per SPEC C7, still no advice). Guardrails reproduce the Phase 2 eligibility on all 18,655 rows.
- Test split 3,041 rows: ADVICE 708, NO_ADVICE 1,518, DIAGNOSTIC_ONLY 815; guardrail-eligible 826 (118 had no benefit). Candidates dropped for low-O2/CO risk 1,018, OOD 252.
- Comparison (1,707 common rows, 1,491 actionable ≥0.15 pp, 309 avoidable ≥1 pp): exact hit rate AI 9.0 % / 10.0 %; rule+default action (FD-4) 8.6 % / 8.1 %; rule alert-only (no action) any-alert hit 22.4 % / 21.0 % vs AI any-alert 43.3 % / 35.0 %. False-alert rate (non-actionable rows): AI 29.2 % / 42.9 %; rule 15.3 % / 21.6 %.
- Predicted vs generator best gain on advice rows: 0.67 vs 0.60 pp mean, corr 0.865; over-claim > 1 pp: 0 %.
- Sensitivity (validation only, not test): restricting two-axis moves to ≤2 % raises exact hit 16.1 %→30.1 % (19.0→36.2 % avoidable).
## 6 Checklist
- Pure guardrails, limits from config, placeholder forces NO_ADVICE: PASS
- 1 ACCEPT + 12 NO_ADVICE gate tests: PASS
- Records have required fields, no actuation fields, human review True: PASS
- Candidates OOD / constraint-failing dropped; less-excess-O2 separate from low-O2/CO risk: PASS
- AI beats rule on exact action: FAIL (9.0 % vs 8.6 %, within noise)
- AI false-alert rate no worse than rule: FAIL (29 % vs 15 %)
- Causal validity of the effect model on real plant data: NEEDS DATA
## 7 Known faults/limits
- 355 of 708 advised moves are two-axis 4 % moves the generator's action menu does not contain, so they can never be exact hits; the full grid was kept as specified.
- Ridge R² only 0.47 (residual 1.7 pp); bootstrap intervals cover coefficients, not misspecification; trip/derate rows are excluded, not predicted.
- Effect sizes come from the generator's exploration; real data would be confounded. No furnace/HTF temperature effect of a move is modelled (only checked at the current state).
- Fix options: restrict the menu (config combo_max_step_pct) or calibrate alert threshold on validation; neither applied to test.
## 8 Decision needed
APPROVE PHASE 4? And choose: (a) keep full grid and report as is, (b) adopt the ≤2 % two-axis menu as the default (chosen on validation, then re-run on test), or (c) raise the benefit threshold to cut false alerts.
