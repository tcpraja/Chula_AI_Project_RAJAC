# Phase 2 Packet — Cleaning, engineering (SPEC C3), baseline
## 1 Implemented
Cleaning (pydantic schema, unit checks, Asia/Bangkok, duplicates, gaps, frozen sensors, totalizer resets, command-vs-feedback, lag alignment, bypass and volumetric handling, 1-min→5-min resampler), engineering with uncertainty and per-row status, SPEC C7 layer 1–2 eligibility, `pipeline` stages generate/clean/baseline, OLS energy baseline with lot-cluster bootstrap CIs, and a 7-day-P75 rule comparator. Raw files untouched.
## 2 Files
config/cleaning_engineering.yaml; src/cleaning.py, engineering.py, pipeline.py, baseline.py, dq_report.py; data/clean/{clean_heater_c,rejected_rows,eval_labels}.csv, clean_report.json; reports/energy_baseline.md, data_quality.md, figs/p2_{data_quality,uncertainty_day,sfc_vs_load,baseline_holdout,rule_comparator}.png; tests/test_cleaning_engineering.py.
## 3 Provenance & assumption IDs
All SYNTHETIC. Thresholds are normalized synthetic values (A20 window 12 steps; A16 uncertainties: flow ±2 %, dT ±0.5 K, fuel 2 % belt / 10 % volumetric, lab LHV ±0.3 MJ/kg are OWN-ESTIMATE). Truth labels live only in eval_labels.csv (evaluation, never a model input).
## 4 Formulas + worked example
Q_out = V/3600·rho(Tm)·∫cp dT; u(Q)/Q = √(0.02² + (0.5/ΔT)²); SFC = fuel/(3.6·Q_out) = 1/(eta·LHV[GJ/kg]).
Hand case: V 700 m3/h, 260→280 C: rho 791.765, m 153.954 kg/s, cp 2.6118 → 8.0418 MW ±0.257; fuel 2850 kg/h, LHV 15 → Q_in 11.875 MW, eta 67.72 %, SFC 98.44 kg/GJ (test matches code ≤0.1 %).
## 5 Evidence
- Tests: 45 passed (24 earlier + 21 new). Raw 18,706 rows → clean 18,655 + rejected 51 (FROZEN_SENSOR 27, HEAT_IMPLAUSIBLE 14, SCHEMA_INVALID 7 [negative O2], FUEL_IMPLAUSIBLE 3). Lag estimate 2 steps (10 min).
- status_SFC: CALCULATED 15,939 / ESTIMATED 2,380 / UNAVAILABLE 336. Eligibility: ELIGIBLE 5,023 / DIAGNOSTIC_ONLY 3,188 / NO_ADVICE 10,444.
- Injected faults: 0 of 386 injected rows left ELIGIBLE.
- Baseline (5,849 train / 2,362 held-out windows): intercept 94.69 [93.93, 95.52]; load 0.34 [0.03, 0.69]; load² 0.10 [−0.13, 0.32]; moisture 1.98 [1.83, 2.15] kg/GJ per %wb. R² 0.91; test MAE 2.37 vs 5.77 kg/GJ (mean model).
- Rule P75-by-band: precision 0.11, recall 0.20, alert rate 0.29 (base rate of avoidable 0.16); OLS-residual monitor: precision 0.26, recall 0.22.
## 6 Checklist
- Hand cases ≤0.1 %, Mkcal/h↔MW, daily integration: PASS
- Totalizer reset, frozen sensor rejected, eligibility flags: PASS
- No interpolation of safety signals; LHV never invented: PASS
- Bypass → heat balance UNVERIFIED; volumetric → wider uncertainty: PASS
- Baseline CIs by lot-cluster bootstrap: PASS
- Independent validation of cleaner on non-synthetic data: NEEDS DATA
## 7 Known faults/limits
- Cleaner and generator share rules and table, so 100 % label agreement and 0.00 % Q_out difference test plumbing, not realism.
- Negative O2 readings (starved combustion) are rejected as schema-invalid; real analysers may read slightly negative.
- Rule comparator is weak (precision below base rate): moisture raises SFC without being avoidable. OLS monitor is also weak (corr with hidden gain 0.15). Baselines are low bars for Phase 3.
- Baseline uses only belt-fuel, lab-assayed, no-bypass windows (about 8.2k of 18.7k rows).
## 8 Decision needed
APPROVE PHASE 2? Also: should Phase 3 predict the next-interval fuel rate (CLAUDE mission) and rank actions with the hidden gain as truth, using these two detectors as comparators?
