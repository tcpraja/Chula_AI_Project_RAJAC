# Model Robustness Checks (SYNTHETIC)

Created after the critic review (reports/ai_critique_log.md): noise floor (K12), action sensitivity (K11), bed time-constant sensitivity (K5), seed spread (K18).

## 1 Noise floor
Mean absolute difference between the measured next-15-min fuel and the mean of the TRUE next three feeds, on 1,694 eligible test rows: **15.3 kg/h**. No forecaster can beat that against this target. L's test MAE is 53.9 kg/h (3.5x the floor); P2 is 58.5 kg/h (3.8x).

## 2 Can the forecaster rank operator actions? (model C, settings changed in the inputs)
True effect from the generator's efficiency model (fuel x (eta_before/eta_after − 1)) vs model C's predicted change, mean over 1,694 eligible test rows (kg/h):

| Action | True mean change | C predicted mean change | Row-wise correlation |
|---|---|---|---|
| FD +5 points | +55.3 | +4.4 | 0.28 |
| FD -5 points | +14.8 | -2.5 | 0.28 |
| grate +5 points | +15.5 | +8.9 | 0.32 |

Reading: when the predicted change is near zero or uncorrelated with the true change, the forecaster has not learned an action effect. Observational settings are confounded with operator habit, so Phase 4 must rank actions with its own effect model or the simulator.

## 3 Bed time-constant sensitivity (feature uses tau minutes; generator draws 10–20 min per lot)
| tau (min) | P2 | B | L | C0 |
|---|---|---|---|---|
| 5 | 58.46 | 105.26 | 53.91 | 55.52 |
| 15 | 58.46 | 106.38 | 53.92 | 55.77 |
| 30 | 58.46 | 107.69 | 53.90 | 55.58 |
| 60 | 58.46 | 109.88 | 53.79 | 55.28 |

## 4 Seed spread (five generator realizations, same split rules, C0 with the chosen hyper-parameters; test MAE kg/h)
| Seed | n test | P | P2 | B | L | C0 | L vs P2 | C0 vs L |
|---|---|---|---|---|---|---|---|---|
| 42 | 1694 | 70.8 | 58.5 | 106.4 | 53.9 | 55.8 | +7.8 % | -3.4 % |
| 43 | 1493 | 69.9 | 59.7 | 95.3 | 53.9 | 57.5 | +9.7 % | -6.7 % |
| 44 | 1882 | 71.7 | 60.0 | 92.6 | 53.9 | 55.8 | +10.2 % | -3.5 % |
| 45 | 1882 | 69.2 | 58.9 | 89.0 | 52.0 | 56.9 | +11.6 % | -9.3 % |
| 46 | 1608 | 76.6 | 65.9 | 102.5 | 61.1 | 63.4 | +7.2 % | -3.7 % |

L beats the current-feed reference P2 by 9.3 % on average (range 7.2 to 11.6 %). C0 vs L (negative = C0 worse): mean -5.3 % (range -9.3 to -3.4 %); C0 is worse than the linear model on 5 of 5 seeds, so boosting adds no gain here.
Seed 42 is the dataset used everywhere else; the other seeds are new draws of the same generator, not new plants.
