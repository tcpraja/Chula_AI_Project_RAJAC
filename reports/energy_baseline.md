# Energy Baseline (SYNTHETIC) - Heater C

Baseline learned from cleaned synthetic data. It is **not** the 85 % design value and not a plant claim; every number is SYNTHETIC. Built by `python -m src.baseline` from data/clean/clean_heater_c.csv.

## Definitions
- Window SFC = trailing 12-step (60 min) sum of aligned fuel kg / (3.6 x sum of Q_out MW); kg fuel per GJ useful heat (SPEC C3).
- Eligible stable row = SPEC C7 layers 1-2 give ELIGIBLE or DIAGNOSTIC_ONLY (CO is not needed for SFC), status_SFC = CALCULATED (weigh belt, STEADY, no bypass), lab moisture present. No imputation.
- Load = trailing 60-min mean Q_out (MW). Model: SFC = b0 + b1 (load-8.5) + b2 (load-8.5)^2 + b3 (moisture-17).
- Split: chronological and lot-aware (70% of eligible windows to a lot boundary). CIs: 500 lot-cluster bootstrap resamples (rows inside a lot are autocorrelated, so naive OLS CIs would be too narrow).

## Coefficients (training windows)
n = 5849 windows from 59 lots; test n = 2362.

| Term | Estimate (kg/GJ per unit) | 95 % CI | Method |
|---|---|---|---|
| intercept | 94.692 | [93.933, 95.518] | OLS, lot-cluster bootstrap |
| load (MW, centred 8.5) | 0.341 | [0.030, 0.687] | OLS, lot-cluster bootstrap |
| load^2 | 0.096 | [-0.133, 0.319] | OLS, lot-cluster bootstrap |
| moisture (%wb, centred 17) | 1.982 | [1.834, 2.148] | OLS, lot-cluster bootstrap |

## Accuracy on held-out later lots
| Measure | Result | Method |
|---|---|---|
| R2 (train) | 0.910 | OLS |
| MAE train / test | 2.36 / 2.37 kg/GJ | mean absolute error |
| MAE of train-mean model (test) | 5.77 kg/GJ | no-skill reference |
| MAPE test | 2.6 % | |

## Rule comparator (monitoring alternative)
Alert if window SFC > trailing 7-day P75 of earlier eligible windows in the same 1 MW load band (needs >= 30 earlier windows).
Truth label (generator illustration, held-out only): avoidable = best feasible action raises eta by >= 1.0 percentage point. Scored on 2362 held-out windows.

| Detector | Alerts | Precision | Recall | Alert rate | Base rate |
|---|---|---|---|---|---|
| Rule P75 by load band | 696 | 0.11 | 0.20 | 0.29 | 0.16 |
| OLS residual > train P75 (same rows) | 328 | 0.26 | 0.22 | 0.14 | 0.16 |

Mean hidden gain when rule alerts vs not: {False: 0.5881414705882353, True: 0.5316967385057471}. Correlation of OLS residual with hidden gain (test): 0.15.

## How to read this
- The Phase 3 model must beat these two detectors on the same held-out windows (and MAE >= 10 % below the OLS) or the simple option is chosen.
- The hidden-gain label comes from the generator; precision/recall show method behaviour under known ground truth, not plant performance.
- Figures: reports/figs/p2_sfc_vs_load.png, p2_baseline_holdout.png, p2_rule_comparator.png.

## Limits
- Only windows with a lab-assayed lot, weigh-belt fuel and no bypass qualify, so coverage is a minority of operating time.
- Fuel-quality and operator effects are confounded in observational data; synthetic exploration (15 % of decisions) makes action effects identifiable only here.
