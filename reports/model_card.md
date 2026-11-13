# Model Card — Heater C next-interval fuel forecast (SYNTHETIC)
Status: **FROZEN DESIGN (written before any model was trained).** Results are appended below the line "RESULTS" after the run; the design above it is not edited afterwards except through a dated amendment in this file.
All data SYNTHETIC (PET Resin Plant P, anonymized; HEATER_C_SYNTHETIC). Output is decision support only: "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION". Fail-safe output is NO_ADVICE with reason codes.

## 1 Task and target
- Predict **y = mean of fuel_rate_measured_kgh over t+1, t+2, t+3** (the next 15 minutes), from information available at time t.
- Population: **eligible rows** = SPEC C7 layers 1–2 give ELIGIBLE or DIAGNOSTIC_ONLY at t (stable 60-min window, belt fuel, lab-assayed lot), and all three future rows exist (contiguous 5-min timestamps, not rejected by cleaning).
- A second, **extended population** (all clean rows with a valid target and a fuel lag-1) is used only to test behaviour outside the training distribution (transients, derated fans, unassayed lots, volumetric fuel). Models are never trained on it.

## 2 Features at time t (all trailing; no row after t is used)
- Demand: Q_out_MW(t) from engineering (flow x dT x cp), and Q_out lags 1, 2, 3.
- Fuel: measured fuel rate lags 1, 2, 3 and the mean of lags 1–6. **Fuel at t itself is not used.**
- Lot (lab values only when lhv_known=1, NaN otherwise, never filled): bed moisture and bed LHV = blend of the current and previous lot with weight exp(−minutes since lot change / 15 min) on the previous lot (bed lag, assumption A15); lhv_known.
- Combustion: O2, CO (NaN when the analyser is unavailable) and co_available.
- Settings: FD, ID, grate command %.
- Plant state: furnace, flue, stack temperature, economizer dP, draft, ambient temperature and RH, HTF_Tout_SP_C, feeder_speed_pct.
- Time: minutes since last sootblow (NaN before the first), minutes since lot change.
- **Never inputs:** Q_in, eta, SFC (any form), fuel at t, fuel totalizer or interval kg, rep_* (HMI-reported values), anything named true_*/truth, scenario_id, is_fault_injected, eval labels, fuel_ash_pct, unburnt_in_ash_pct (lab results arrive after the lot starts), advice/eligibility strings.

## 3 Split
Chronological 60/20/20 by **lot** (a lot is never split), counted on eligible rows, all rows of a lot take the lot's split; the last 3 rows before a split change are purged (their target spans the next split). Saved in data/holdout/split_keys.csv. The fault block sits at the end of the timeline, so the test period contains injected faults while train and validation contain none (deliberate distribution shift).

## 4 Models
- **P (reference only, not a candidate):** persistence, fuel lag-1.
- **A physics reference:** y = Q_out(t) x 3600 / (eta_base x LHV_bed); eta_base = median measured eta on training eligible rows (data-derived, not the 85 % design value). NaN if LHV unknown.
- **B linear:** OLS on Q_out(t) and bed moisture (no imputation).
- **C HistGradientBoosting** (absolute-error loss, seed 42) on all features; ≤ 6 hyper-parameter combinations chosen by validation MAE: (depth, learning rate, iterations, min leaf) = (3, 0.05, 300, 20), (3, 0.1, 200, 20), (5, 0.05, 300, 20), (5, 0.1, 200, 40), (8, 0.05, 300, 40), (3, 0.03, 500, 20).
- **C0:** C with the three settings removed (same hyper-parameters).
- Uncertainty: split conformal, 90 %, absolute residuals on validation (finite-sample rank ceil((n+1)x0.9)); the interval is the same half-width everywhere (known limit).

## 5 Evaluation
Test (eligible) metrics per model: MAE kg/h, MAPE (targets > 500 kg/h only; stopped-feeder targets are counted separately), RMSE, P90 absolute error, R2, conformal coverage, MAE 95 % interval by lot-cluster bootstrap, share of rows better than B. Segments: moisture band (<14, 14–22, >22 %wb), load band (<7.5, 7.5–9.5, ≥9.5 MW) on eligible rows; steady vs transient, fan derated, lhv_known on the extended population. Permutation importance (MAE) for C on test.
Leakage tests: shuffled-target model has no skill; a deliberately added future feature is caught; features at t unchanged when later rows are deleted; no truth/forbidden column in X. **If any model has R2 > 0.995 on test, flag "learning the generator" and explain.**

## 6 Selection rule (frozen)
1. Safety gate for a candidate (A, B, C0, C): leakage tests pass; conformal test coverage ≥ 0.80; validation→test MAE degradation ≤ 50 %; worst eligible segment MAE ≤ 3 x its overall MAE.
2. Complexity order A < B < C0 < C. Start from the simplest safe candidate; a more complex safe candidate replaces it only if its test MAE is at least **10 % lower**.
3. If the winner does not beat persistence P by at least 5 % MAE, the report states that persistence suffices and the winner is kept only as a research model.
4. Score alone never selects; ties go to the simpler model. C (with settings) is the only candidate able to rank simulated operator actions; that need is stated but does not override rule 2.

## 7 Limits (design time)
Synthetic generator effects (A12, A15, A17) define the signal; a good score shows the method works under known ground truth only. Models are valid only for eligible rows; outside them the output is NO_ADVICE. No plant control path exists.

---
RESULTS (appended after training)

Design section SHA-256 (text above the horizontal rule, recorded before training): `5d1c2ca2563de16ccc2e0128a6cedef8db5b17f9c782603cd5147223e906b9c7`.

### Dated amendments (2026-11-13, after the critic review; the frozen design above is unchanged)
| ID | Amendment | Origin |
|---|---|---|
| A1 | Reference P2 (current feed = feeder_speed_pct x capacity) added; rule 3 now compares with the better of P and P2. | critic K1, K2 |
| A2 | Candidate L (linear on all non-settings features) inserted in the ladder A < B < L < C0 < C; ablations C0_nofeed, C0_nolot, C0_noco reported. | K1, K3, K4, K17 |
| A3 | Rules 2 and 3 use validation (part b) MAE; test MAE only reports and feeds the safety gates. | K10 |
| A4 | Validation is split by lot: part a tunes C, part b calibrates the conformal interval and drives selection. | K8 |
| A5 | Purge between splits raised from 3 to 12 steps (longest feature look-back). | K19 |
| A6 | Leakage self-test: future-feature canary must lift R2 by >= 0.04 over the honest model; truncation test added (features unchanged when later rows are deleted). | K16 |
| A7 | Reporting: extended-population ALL also on rows all of A, B, L predict; fuel-energy error in MW; lot-level coverage; segments inside/outside injected-fault windows. | K6, K7, K14, K15 |
| A8 | Scope: safety gates apply to the population in which the model may speak (eligible rows). Extended-population results are informational; src/predict.py returns NO_ADVICE outside eligibility. | K9, K15 |

Run: seed 42; eligible rows train 4926 / validation a 761 + b 805 / test 1694 (lots 51 / 15 / 17). C hyper-parameters (depth, lr, iterations, min leaf) = (3, 0.03, 500, 20) (validation-a MAE 51.257 kg/h). eta_base (A) = 0.6749 (median measured eta, training rows).

### Eligible test metrics (kg/h; MAPE on targets > 500 kg/h; MAE also as fuel energy input in MW)
| Model | MAE | MAPE % | RMSE | P90 err | R2 | MAE MW | 90 % cover | lot cover median / p10 | better than B % | MAE val-b | val→test | worst seg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P last fuel (ref) | 70.844 | 2.597 | 109.258 | 142.419 | 0.916 | 0.315 | 0.924 | 0.921 / 0.870 | 64.699 | 74.909 | -0.054 | 1.182 |
| P2 current feed = feeder speed (ref) | 58.460 | 2.159 | 93.864 | 115.756 | 0.938 | 0.260 | 0.916 | 0.911 / 0.855 | 70.425 | 61.871 | -0.055 | 1.145 |
| A physics | 85.178 | 3.128 | 128.047 | 177.058 | 0.885 | 0.379 | 0.920 | 0.918 / 0.859 | 60.272 | 83.988 | 0.014 | 1.241 |
| B linear load+moisture | 106.376 | 3.908 | 145.886 | 216.363 | 0.851 | 0.472 | 0.900 | 0.910 / 0.801 | 0.000 | 115.931 | -0.082 | 1.290 |
| L linear, all non-settings features | 53.922 | 2.016 | 89.889 | 107.635 | 0.943 | 0.240 | 0.901 | 0.893 / 0.816 | 73.849 | 54.984 | -0.019 | 1.234 |
| C0 boosting, no settings | 55.770 | 2.073 | 93.249 | 113.959 | 0.939 | 0.248 | 0.907 | 0.920 / 0.808 | 73.967 | 57.066 | -0.023 | 1.222 |
| C boosting | 55.367 | 2.060 | 92.951 | 113.885 | 0.940 | 0.246 | 0.909 | 0.909 / 0.833 | 73.377 | 56.937 | -0.028 | 1.239 |
| C0 without feeder speed | 63.558 | 2.363 | 103.496 | 127.978 | 0.925 | 0.283 | 0.911 | 0.925 / 0.819 | 68.772 | 64.134 | -0.009 | 1.243 |
| C0 without lot features | 55.290 | 2.060 | 93.106 | 112.335 | 0.939 | 0.246 | 0.913 | 0.914 / 0.816 | 74.498 | 56.495 | -0.021 | 1.225 |
| C0 without CO | 55.720 | 2.070 | 93.026 | 116.107 | 0.939 | 0.248 | 0.907 | 0.909 / 0.808 | 73.022 | 57.355 | -0.029 | 1.260 |

MAE 95 % intervals (lot-cluster bootstrap, 17 test lots): P [65.0, 77.6]; P2 [53.4, 64.0]; A [75.1, 96.7]; B [89.5, 124.7]; L [48.8, 59.6]; C0 [50.2, 62.3]; C [49.7, 61.9].

### Eligible test segments (MAE kg/h, n) for P2, L, C0
| Segment | n | P2 | L | C0 |
|---|---|---|---|---|
| moisture<14 | 561 | 57.435 | 51.083 | 52.742 |
| moisture 14-22 | 1000 | 57.907 | 53.833 | 55.822 |
| moisture>22 | 133 | 66.934 | 66.563 | 68.155 |
| load<7.5 | 294 | 57.147 | 59.368 | 59.443 |
| load 7.5-9.5 | 1179 | 57.260 | 51.706 | 54.341 |
| load>=9.5 | 221 | 66.604 | 58.497 | 58.508 |
| outside injected-fault window | 1623 | 58.992 | 54.532 | 56.339 |
| inside injected-fault window | 71 | 46.288 | 39.969 | 42.763 |

### Extended population (not eligible for advice; informational), MAE kg/h (share of rows predicted)
| Segment | n rows | P | P2 | A | B | L | C0 | C |
|---|---|---|---|---|---|---|---|---|
| ALL (each model's own rows) | 2988 | 99.858 (100 %) | 76.952 (100 %) | 152.348 (87 %) | 169.615 (87 %) | 81.193 (86 %) | 92.713 (100 %) | 91.716 (100 %) |
| ALL (rows all of A,B,L predict) | 2558 | 102.726 (100 %) | 79.132 (100 %) | 149.183 (100 %) | 167.151 (100 %) | 81.193 (100 %) | 95.980 (100 %) | 94.991 (100 %) |
| steady | 2727 | 83.688 (100 %) | 66.961 (100 %) | 126.076 (87 %) | 142.785 (87 %) | 64.160 (86 %) | 65.721 (100 %) | 64.913 (100 %) |
| transient/other | 261 | 268.804 (100 %) | 181.344 (100 %) | 426.130 (87 %) | 449.217 (87 %) | 258.675 (86 %) | 374.730 (100 %) | 371.757 (100 %) |
| fan_derated=0 | 2937 | 99.715 (100 %) | 76.995 (100 %) | 140.412 (87 %) | 162.172 (87 %) | 81.170 (86 %) | 92.202 (100 %) | 91.374 (100 %) |
| fan_derated=1 | 51 | 108.060 (100 %) | 74.482 (100 %) | 749.842 (100 %) | 542.222 (100 %) | 82.858 (69 %) | 122.138 (100 %) | 111.416 (100 %) |
| lhv_known=1 | 2616 | 102.804 (100 %) | 79.084 (100 %) | 152.348 (100 %) | 169.615 (100 %) | 81.193 (98 %) | 97.047 (100 %) | 95.805 (100 %) |
| lhv_known=0 | 372 | 79.142 (100 %) | 61.962 (100 %) | n/a (0 %) | n/a (0 %) | n/a (0 %) | 62.233 (100 %) | 62.960 (100 %) |
| belt fuel | 2988 | 99.858 (100 %) | 76.952 (100 %) | 152.348 (87 %) | 169.615 (87 %) | 81.193 (86 %) | 92.713 (100 %) | 91.716 (100 %) |
| volumetric fuel | 0 | n/a (0 %) | n/a (0 %) | n/a (0 %) | n/a (0 %) | n/a (0 %) | n/a (0 %) | n/a (0 %) |

### Leakage and sanity checks
- Shuffled target: MAE 327.0 vs mean-model 327.7 kg/h → no skill: True.
- Future-feature canary (y added as a column): R2 0.9951 vs honest model 0.9395 → lift ≥ 0.04 detected: True. (Histogram binning keeps the canary just under 1, so an absolute 0.995 cut-off is fragile.)
- Features unchanged when later rows are deleted (truncation test): True.
- No forbidden or truth column among the model inputs: True.
- R2 > 0.995 flag ("learning the generator"): not raised for any model.

### Permutation importance (MAE increase when a feature is shuffled, test)
- C: feeder_speed_pct 172.6, fuel_lag_mean_1_6 52.9, fuel_lag1 49.1, fuel_lag2 14.4, grate_command_pct 2.8, fuel_lag3 2.2
- C0: feeder_speed_pct 168.0, fuel_lag_mean_1_6 54.7, fuel_lag1 51.1, fuel_lag2 17.8, fuel_lag3 4.0, Q_out_lag3 0.9
- C0_nofeed: fuel_lag_mean_1_6 145.3, fuel_lag1 79.7, fuel_lag2 41.2, fuel_lag3 13.1, flue_temp_C 1.6, bed_moisture_wb_pct 1.2

### Selection (frozen rule with amendments A1–A8)
| Candidate | safe | MAE val-b | MAE test | reasons |
|---|---|---|---|---|
| A | True | 84.0 | 85.2 | coverage 0.920 (≥0.8), val→test 0.014 (≤0.5), worst segment 1.24x (≤3.0) |
| B | True | 115.9 | 106.4 | coverage 0.900 (≥0.8), val→test -0.082 (≤0.5), worst segment 1.29x (≤3.0) |
| L | True | 55.0 | 53.9 | coverage 0.901 (≥0.8), val→test -0.019 (≤0.5), worst segment 1.23x (≤3.0) |
| C0 | True | 57.1 | 55.8 | coverage 0.907 (≥0.8), val→test -0.023 (≤0.5), worst segment 1.22x (≤3.0) |
| C | True | 56.9 | 55.4 | coverage 0.909 (≥0.8), val→test -0.028 (≤0.5), worst segment 1.24x (≤3.0) |

**Simplicity-ladder winner: L.** Best reference: P2 (validation-b MAE 61.9, test 58.5 kg/h).
L MAE: validation-b 55.0, test 53.9 kg/h → 7.8 % lower than P2 on test. Beats the best reference by ≥5 % — validation: True, test: True.

**Verdict: DEPLOYABLE as the forecast model (still advisory, eligible rows only).**

Selection reasoning: simplest safe candidate first; a more complex one replaces it only for a ≥10 % validation-MAE gain. Score alone does not select. Settings add nothing to the forecast (C ≈ C0), so a model that must rank operator actions cannot come from this forecaster; Phase 4 needs its own effect model or the simulator.

