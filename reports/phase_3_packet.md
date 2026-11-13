# Phase 3 Packet — Next-interval fuel forecast, critic review, selection
## 1 Implemented
Froze the design in reports/model_card.md (SHA-256 recorded) before training; built features at t, a lot-aware 60/20/20 split, references P and P2, candidates A, B, L, C0, C, three ablations, conformal 90 % intervals, permutation importance, leakage tests, predict module with NO_ADVICE, robustness checks, and a fresh-context critic whose 20 findings are logged with fixes. Train stage added to the pipeline.
## 2 Files
src/features.py, train.py, train_report.py, train_extras.py, predict.py; models/{P,P2,A,B,L,C,C0,C0_nofeed,C0_nolot,C0_noco}*.joblib + metadata.json; data/holdout/{split_keys,test_predictions}.csv; reports/model_card.md, model_comparison.csv, permutation_importance.csv, model_error_analysis.md, model_robustness.md, ai_critique_log.md, figs/p3_{model_comparison,segments,pred_vs_actual,perm_importance,failure_cases}.png; tests/test_model_leakage.py.
## 3 Provenance & assumption IDs
SYNTHETIC; seed 42; hyper-parameters chosen on validation-a from 6 combinations; A15 bed constant 15 min (generator 10–20 min per lot); A12/A17 generator effects. Register rows A10, A12, A14, A15 corrected after the critique.
## 4 Formulas + worked example
y = mean fuel over t+1..t+3. A: Q_out·3600/(eta_base·LHV_bed). Hand check (test row 2026-02-28 06:20): Q_out 8.177 MW, LHV 17.021, eta_base 0.6749 → A = 2,562.7 kg/h (code 2,562.7); B = 2,475.2 (code 2,475.2); P2 = 52.43 % x 50 = 2,621.3; selected L 2,640.5 [2,532.1, 2,748.9]; actual 2,571.5. Second row 2026-03-02 01:35: A 3,336.9 = code; actual 3,395.5; L 3,260.9.
## 5 Evidence
- Tests: 60 passed (45 earlier + 15 new). Eligible rows train 4,926 / validation 1,566 (a 761, b 805) / test 1,694; lots 51/15/17.
- Test MAE kg/h: P 70.844, P2 58.460, A 85.178, B 106.376, L 53.922, C0 55.770, C 55.367; MAPE %: 2.597, 2.159, 3.128, 3.908, 2.016, 2.073, 2.060; coverage 0.924, 0.916, 0.920, 0.900, 0.901, 0.907, 0.909; R2 ≤ 0.943 (flag R2>0.995 not raised).
- Selected L: 7.8 % below P2 on test, 11.1 % on validation; five generator seeds 7.2–11.6 %; C0 worse than L on 5 of 5 seeds. Noise floor 15.3 kg/h.
- Leakage: shuffled target no skill (327.0 vs 327.7 kg/h); canary R2 0.9951 vs honest 0.9395; truncation test passes; no forbidden column.
- Figures reports/figs/p3_*.png; error analysis reports/model_error_analysis.md (worst miss: a trip, 917 actual vs 2,675 predicted).
## 6 Checklist
- Design frozen before training, hash tested: PASS
- Lot-aware chronological split, purge 12: PASS
- Leakage tests (shuffle, canary, truncation, forbidden): PASS
- Selection by rule, not score; critic ≥1 genuine error fixed (5 fixed): PASS
- Model ranks operator actions: FAIL (FD +5 true +55 kg/h, model +4; row corr 0.28)
- Validity on real plant data: NEEDS DATA
## 7 Known faults/limits
- Value of the forecast comes from knowing the current feed (without feeder speed C0 = 63.6 kg/h); a model beats "repeat the current feed" by only ~8 %.
- Interval width is fixed; trips and feeder stops are not predictable from inputs at t.
- Eligible test rows inside injected-fault windows are only 71 of 1,694, so fault robustness is barely tested.
- Lab moisture/LHV assumed available at lot receipt; ash/unburnt excluded.
## 8 Decision needed
APPROVE PHASE 3? Phase 4 cannot rank actions from this forecaster: allow it to use a separate effect model (or the simulator's true response) and keep L only as the fuel forecast?
