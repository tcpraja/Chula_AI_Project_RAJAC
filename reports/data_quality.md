# Data Quality Report (SYNTHETIC) - Heater C

Produced by `python -m src.pipeline --stage clean` (src/cleaning.py, src/engineering.py). Raw files are never modified; nothing is interpolated or filled; LHV is never invented. Times are Asia/Bangkok (+07:00, no DST).

## Counts
| Measure | Result | Method |
|---|---|---|
| Raw rows | 18,706 | main file, seed 42 |
| Clean rows | 18,655 | passed schema, duplicates, frozen, plausibility, property table |
| Rejected rows | 51 | FROZEN_SENSOR 27, HEAT_IMPLAUSIBLE 14, SCHEMA_INVALID 7, FUEL_IMPLAUSIBLE 3 |
| Gaps / missing 5-min rows | 7 / 21 | left as gaps, not filled |
| Totalizer resets | 1 | negative diff; interval = post-reset value |
| Heat balance UNVERIFIED (bypass > 0) | 191 rows | eta and SFC set UNAVAILABLE |
| Volumetric fuel rows | 1152 | fuel uncertainty 10 % instead of 2 % |
| Command-vs-feedback mismatches | 0 | fan power vs cube law, 25 % tolerance |
| Unit-suspect rows | 0 | draft > 500 Pa or reported heat off by a Mkcal/kcal factor |
| Estimated fuel-to-heat lag | 2 steps (10 min) | 3-step-difference correlation on first 70% of rows; trailing alignment only |

## Reasons for rejection (priority order)
SCHEMA_INVALID (here: negative O2 readings below the analyser range, which are physically impossible) > DUPLICATE_TIMESTAMP > FROZEN_SENSOR (>2 identical samples) > FUEL_IMPLAUSIBLE (vs feeder speed) > HEAT_IMPLAUSIBLE (> 13.75 MW or dT outside 5-40 K) > PROPERTY_OOR (temperature outside the HTF table).

## Engineering status counts (SFC / eta / Q_out)
- status_SFC: {'CALCULATED': 15939, 'ESTIMATED': 2380, 'UNAVAILABLE': 336}
- status_eta: {'CALCULATED': 10956, 'ESTIMATED': 7369, 'UNAVAILABLE': 330}
- status_Q_out: {'CALCULATED': 17047, 'ESTIMATED': 1492, 'UNAVAILABLE': 116}
- LHV basis: {'LAB_LOT': 12693, 'TRAILING_LOT_BAND': 5704, 'ENVELOPE_BAND': 258}

## Eligibility (SPEC C7 layers 1-2, 12-step stable window)
- Counts: {'NO_ADVICE': 10444, 'ELIGIBLE': 5023, 'DIAGNOSTIC_ONLY': 3188}
- Top NO_ADVICE reasons: LOW_FUEL_CONF 6672, TRANSIENT 3823, LOW_O2 499, HIGH_CO 241, NO_DATA 220, ENERGY_BALANCE 198, FAN_DERATE 69, UNSAFE_DRAFT 41
- Agreement with the generator's own labels at the ELIGIBLE/DIAGNOSTIC/NO_ADVICE level: 100.0 % (not independent evidence: generator and cleaner were written together and share the same rules and property table)

## Uncertainty (standard, SPEC C3: flow 2 %, dT 0.5 K, fuel 2 % belt / 10 % volumetric)
- Median Q_out relative uncertainty in operation: 3.1 %.
- Median SFC relative uncertainty: 3.7 % (weigh belt) vs 10.5 % (volumetric).
- Median eta 95 % half-width: 5.5 points with a lab LHV vs 16.1 points when only a lot-band interval exists (no point eta is reported then).

## Reconciliation
- Recomputed vs reported Q_out: median relative difference 0.00 % (n=18,655); expected ~0 because the generator uses the same table, so this checks plumbing, not plant agreement.
- Daily fuel from rate integration vs totalizer increments (full days, n=62): median difference 0.00 %, max 0.14 %.
- Safety signals left unfilled: draft_pa NaN 0, interlock_active NaN 0.

## Injected-fault detection (evaluation only; labels never enter the clean file)
| Fault | Injected rows | Rejected | Flagged not ELIGIBLE | Still ELIGIBLE (missed) |
|---|---|---|---|---|
| FEEDER_STOP | 12 | 0 | 12 | 0 |
| FAN_DERATE | 76 | 7 | 69 | 0 |
| POOR_AIR | 48 | 0 | 48 | 0 |
| FROZEN_O2 | 12 | 12 | 0 | 0 |
| FROZEN_FLOW | 10 | 10 | 0 | 0 |
| CO_MISSING | 64 | 0 | 64 | 0 |
| DATA_GAP | 1 | 0 | 1 | 0 |
| TOTALIZER_RESET | 1 | 0 | 1 | 0 |
| HIGH_HTF_FLOW | 36 | 0 | 36 | 0 |
| LOW_HTF_FLOW | 36 | 0 | 36 | 0 |
| ADVERSE_DRAFT | 30 | 0 | 30 | 0 |
| TRIP | 20 | 0 | 20 | 0 |
| FUEL_SPIKE | 3 | 3 | 0 | 0 |
| HEAT_IMPLAUSIBLE | 34 | 14 | 20 | 0 |
| PROPERTY_OOR | 3 | 3 | 0 | 0 |

Total still ELIGIBLE inside injected windows: 0 of 386 rows.

## Known limits
- Detection rules and thresholds are normalized synthetic values (config/cleaning_engineering.yaml), not site limits.
- A frozen sensor is only detected after 3 identical samples; the first genuine-looking sample is flagged with the run.
- Gaps are not filled, so the 60-min windows after a gap restart; eligible coverage falls accordingly.
- Figures: reports/figs/p2_data_quality.png, p2_uncertainty_day.png.
