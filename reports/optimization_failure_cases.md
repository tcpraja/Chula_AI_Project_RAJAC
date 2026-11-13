# Optimization failure cases (SYNTHETIC - NOT FOR PLANT OPERATION)
Test advice rows scored: 708. Predicted efficiency gain averages 0.67 pp vs the generator's best-available 0.60 pp; correlation 0.86; 0.0 % of advice over-claims by > 1 pp.
Advice where the generator says HOLD (false alerts): 63; advice with a different action than the generator's best: 511 (of which opposite direction on FD or grate: 2).

Advice outside the generator's action menu (4-step move combined with a second axis, can never be an exact hit): 355.

## 1 False alerts with the largest predicted gain
| timestamp_local | action | label | pred_deta | best_action_eta_gain_pp |
|---|---|---|---|---|
| 2026-03-07 06:55:00+07:00 | FD-4 | HOLD | 0.56 | 0.14 |
| 2026-03-01 17:20:00+07:00 | FD-2&GRATE-4 | HOLD | 0.46 | 0.04 |
| 2026-03-01 08:50:00+07:00 | FD+2&GRATE-2 | HOLD | 0.4 | 0.06 |
| 2026-03-01 09:10:00+07:00 | FD+2&GRATE-2 | HOLD | 0.39 | 0.03 |
| 2026-03-01 08:55:00+07:00 | FD+2&GRATE-2 | HOLD | 0.39 | 0.04 |

## 2 Largest over-claims (predicted minus generator best gain, pp)
| timestamp_local | action | label | pred_deta | best_action_eta_gain_pp |
|---|---|---|---|---|
| 2026-03-01 05:25:00+07:00 | FD-4 | FD-4 | 1.49 | 0.51 |
| 2026-03-05 19:40:00+07:00 | FD-4&GRATE-4 | FD-2&GRATE-2 | 1.02 | 0.25 |
| 2026-03-02 16:35:00+07:00 | FD-4&GRATE-4 | FD-4 | 1.23 | 0.48 |
| 2026-03-07 17:00:00+07:00 | FD-4&GRATE-4 | FD-2&GRATE-2 | 1.11 | 0.41 |
| 2026-03-06 07:55:00+07:00 | FD+4&GRATE-2 | FD+2&GRATE-2 | 1.38 | 0.69 |

## 3 Eligible rows with no advice but a large true gain (missed)
| timestamp_local | true_synthetic_best_action | best_action_eta_gain_pp |
|---|---|---|
| 2026-03-04 02:25:00+07:00 | FD-4 | 2.08 |
| 2026-02-28 07:40:00+07:00 | FD-4 | 2.01 |
| 2026-02-28 07:45:00+07:00 | FD-4 | 1.91 |
| 2026-03-03 22:20:00+07:00 | FD-4 | 1.9 |
| 2026-03-04 02:30:00+07:00 | FD-4 | 1.89 |

## 4 Exact-action rate by generator best action
| generator best action | advice rows | exact rate |
|---|---|---|
| FD+2 | 20.0 | 0.6 |
| FD+2&GRATE+2 | 6.0 | 0.0 |
| FD+2&GRATE-2 | 22.0 | 0.364 |
| FD+4 | 52.0 | 0.423 |
| FD-2 | 11.0 | 0.364 |
| FD-2&GRATE+2 | 35.0 | 0.0 |
| FD-2&GRATE-2 | 69.0 | 0.072 |
| FD-4 | 352.0 | 0.134 |
| GRATE+4 | 1.0 | 0.0 |
| GRATE-4 | 77.0 | 0.468 |
| HOLD | 63.0 | 0.0 |

## Why it fails (diagnosis)
- The effect model is smooth and sees only O2/grate/load/moisture; the generator's optimum depends on a hidden O2 target and a grate optimum, so compound moves are often mis-ranked.
- Bootstrap intervals cover coefficient uncertainty only, not model misspecification, so over-claims occur even when the interval is narrow.
- Guardrails remove unsafe rows, not wrong ones: an eligible, in-distribution row can still get a wrong move. Humans must review.

Causal limits: the action-effect model is fitted to synthetic observational data with a generator-built exploration component; its delta-efficiency for a proposed move is an association, not an identified causal effect, and on real plant data confounding (operators move FD/grate in response to load, fuel and air demand) would bias it. All benefits are synthetic generator illustrations, never savings; every output requires human review; BMS/SIS/DCS remain the only control authorities.
