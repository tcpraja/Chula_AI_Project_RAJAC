# Model Error Analysis (SYNTHETIC) — plain English

Model discussed: **L** (L linear, all non-settings features), the simplicity-ladder winner, always set against the best simple reference **P2** (P2 current feed = feeder speed (ref)). Numbers are from the held-out test period (the last 20 % of lots), which also holds the injected faults.

## What the model gets right
- On 1,694 eligible test rows the typical error of L is 54 kg/h (MAPE 2.0 %, about 0.24 MW of fuel energy input), against 58 kg/h for the reference P2, 71 kg/h for repeating the last fuel value and 106 kg/h for the linear load-and-moisture model.
- Nine in ten errors are below 108 kg/h. The 90 % interval (± 108 kg/h, calibrated on a separate validation block) covered 90.1 % of test rows; per lot the median coverage was 89 % and the weakest tenth of lots 82 %.

## Where it fails (real failures, not hidden)
- A few rows carry much of the error: the worst 1 % of rows account for 9 % of all absolute error.
- 168 of 1,694 eligible test rows (9.9 %) fall outside the 90 % interval; by context: STEADY (106), fault: FEEDER_STOP (10), fault: FROZEN_O2 (9), fault: TOTALIZER_RESET (9), fault: FAN_DERATE (5), HIGH_FLOW (4).
- Inside injected-fault windows the MAE is 40 kg/h (71 rows) versus 55 kg/h outside (1623 rows).
- 1 eligible row(s) had a next-15-minute fuel rate below 1,000 kg/h (feeders stopped or tripped). L predicted a mean of 2698 kg/h for them against an actual mean of 917 kg/h. It cannot know a trip is coming because the inputs at time t show a healthy furnace. This is a real limit, not a bug: the guardrail layer has to catch it, not the forecast.

Largest single misses:

| Time (Asia/Bangkok) | Context (evaluation label) | Actual kg/h | Predicted kg/h | Error kg/h |
|---|---|---|---|---|
| 2026-03-09 18:25 | FAULT_TRIP | 917 | 2698 | -1780 |
| 2026-03-09 18:20 | FAULT_TRIP | 1807 | 2666 | -860 |
| 2026-03-01 15:35 | STEADY | 2859 | 2258 | +601 |
| 2026-03-09 10:10 | FAULT_ADVERSE_DRAFT | 3054 | 2511 | +543 |
| 2026-03-04 23:50 | STEADY | 2731 | 3229 | -498 |
| 2026-03-04 23:45 | STEADY | 2942 | 3353 | -411 |

## Outside the eligible window (extended population, informational)
The tool returns NO_ADVICE on these rows; the table shows what a forecast would have been worth anyway.

| Condition | Rows | MAE of L | MAE of P2 |
|---|---|---|---|
| steady | 2727 | 64.160 | 66.961 |
| transient/other | 261 | 258.675 | 181.344 |
| fan_derated=0 | 2937 | 81.170 | 76.995 |
| fan_derated=1 | 51 | 82.858 | 74.482 |
| lhv_known=1 | 2616 | 81.193 | 79.084 |
| belt fuel | 2988 | 81.193 | 76.952 |

## Why the scores are high and why that is not proof of skill
- Fuel feed changes slowly and the models see the feeder speed (a proxy for the fuel being fed right now). Repeating the current feed already gives 58 kg/h; L gives 54 kg/h (R2 0.943).
- Skill over the current-feed reference: 7.8 % lower MAE (test) — above the 5 % bar. Skill over the last-value reference P: 23.9 %. Without feeder speed C0 degrades to 64 kg/h, so the forecast value comes almost entirely from knowing the current feed.
- The generator defines the demand-to-fuel relationship, so these results show the method works under known ground truth. They do not predict plant accuracy.

## Plain-English reading for an operator or manager
- Inside a steady, assayed, weigh-belt window the next quarter-hour of fuel use is close to what the feeders are doing now. A model adds little beyond that.
- The forecast cannot warn about sudden stops or trips; those stay with the BMS/SIS and alarms.
- The interval has one fixed width, so it is too wide in calm periods and too narrow around fault episodes.
