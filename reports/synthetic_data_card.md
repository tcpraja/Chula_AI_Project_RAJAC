# Synthetic Data Card - Heater C (SYNTHETIC)
Heater: HEATER_C_SYNTHETIC at PET Resin Plant P (anonymized). Every number below is computed by `src/generate_synthetic.py` from the CSVs; provenance SYNTHETIC unless stated. Not for plant operation.

## Files
- data/raw_synthetic/synthetic_heater_c_5min.csv (seed 42; measured columns), synthetic_truth.csv (hidden state), fault_cases.csv, operator_action_log.csv
- data/stress/stress_seed77.csv (+ _truth, _fault_cases, _operator_action_log) and display_reconciliation.csv
- config/synthetic_parameters.yaml, config/htf_properties.csv; column definitions in reports/03_data_dictionary.csv (earlier variable inventory kept as 03b)

## Size
- Main: 18,706 rows x 52 columns = 17,280 normal rows (60 d x 288) + 1,426 fault-block rows (15 fault cases of 8 h; 14 rows removed by DATA_GAP).
- Operator log: 6,722 setting changes (10.1 % EXPLORATION).
- Lots: 132 lots; median length 11.6 h.

## How it is generated (SPEC C6)
Demand (6-11 MW) -> lot moisture/LHV -> fuel feed by feed-forward on last efficiency and a slowly learned LHV -> bed lag (10-20 min) -> latent eta = f(moisture, fouling, excess-air deviation from a hidden optimum, grate-air mismatch, fan derate, AR(1)) -> HTF temperatures from the heat balance with the property table -> measurements = truth + noise/bias/lag. Operators (OP-A/B/C) change FD, ID and grate commands with shift-dependent habits; 15 % of decisions are randomized EXPLORATION so action effects are identifiable in synthetic data (not identifiable from observational plant data).

## Headline statistics (normal block)
| Measure | Result | Method |
|---|---|---|
| Latent eta, STEADY | median 67.8 %, 5-95 %: 64.8..69.7 % | truth column, SYNTHETIC |
| SFC (valid STEADY rows) | median 93.1 kg/GJ | measured fuel / (3.6 x Q_out) |
| Hidden-optimum gap | mean best-action eta gain 0.67 pp, median 0.55 pp | generator illustration, never a real saving |
| ELIGIBLE / DIAGNOSTIC_ONLY / NO_ADVICE | 27.1 / 16.9 / 56.0 % of rows | SPEC C7 rules, 12-step stable window |
| Top NO_ADVICE reasons | LOW_FUEL_CONF 6384, TRANSIENT 3496, LOW_O2 352, ENERGY_BALANCE 191, HIGH_CO 109 | row counts |
| CO available | 60.0 % of normal rows (days: 60 % exactly) | config |
| Truth balance closure | max absolute residual between Q_out from HTF side and eta x Q_in = 0.0003 % | independent table integration |
| Weigh-belt vs volumetric | 6.7 % of normal rows volumetric | service episodes |
| Display records (stress) | {'WINDOW_MISMATCH': 23, 'OK': 6, 'REJECT': 1} | units.reconcile_display |

## Fault cases
| Case | Type | Injected rows | Expected detection |
|---|---|---|---|
| F01 | FEEDER_STOP | 12 | mode FEEDER_STOP; NO_ADVICE LOW_FUEL_CONF |
| F02 | FAN_DERATE | 76 | fan_derated=1; NO_ADVICE FAN_DERATE |
| F03 | POOR_AIR | 48 | low O2, high CO; NO_ADVICE LOW_O2/HIGH_CO |
| F04 | FROZEN_O2 | 12 | quality FROZEN_SENSOR; NO_ADVICE STALE_DATA |
| F05 | FROZEN_FLOW | 10 | quality FROZEN_SENSOR; NO_ADVICE STALE_DATA |
| F06 | CO_MISSING | 64 | co_available=0; DIAGNOSTIC_ONLY NO_CO |
| F07 | DATA_GAP | 0 | quality GAP_AFTER; TRANSIENT after gap |
| F08 | TOTALIZER_RESET | 1 | quality TOTALIZER_RESET |
| F09 | HIGH_HTF_FLOW | 36 | BAD_FLOW; NO_ADVICE |
| F10 | LOW_HTF_FLOW | 36 | BAD_FLOW; NO_ADVICE |
| F11 | ADVERSE_DRAFT | 30 | UNSAFE_DRAFT; NO_ADVICE |
| F12 | TRIP | 20 | TRIP_ACTIVE; mode TRIP |
| F13 | FUEL_SPIKE | 3 | quality FUEL_IMPLAUSIBLE |
| F14 | HEAT_IMPLAUSIBLE | 34 | quality HEAT_IMPLAUSIBLE |
| F15 | PROPERTY_OOR | 3 | quality PROPERTY_OOR; cp/rho NaN |

## Extensions to SPEC C7 reason codes
Added LOW_O2 (O2 below floor) and HIGH_CO (CO above limit) because SPEC C7 names those conditions without codes. LIMITS_NOT_APPROVED is unused in synthetic mode.

## Figures
- reports/figs/p1_trend_24h.png (2026-02-04)
- reports/figs/p1_histograms.png
- reports/figs/p1_energy_balance_residuals.png

## Limits and known faults
- Effects (O2 optimum, grate optimum, fouling, derate) are generator-defined (A12, A17); success on this data shows the method works under known ground truth, not that the same gain exists on a real heater.
- Stress (seed 77) uses a shifted optimum, wider moisture, all-volumetric fuel and noisier sensors; site-style (seed 101) is configured but not generated in Phase 1.
- fuel_rate_true_kgh, fuel_moisture (when lhv_known=0 is NaN) and the truth file must never be model inputs; true_synthetic_best_action is evaluation-only.
- HTF setpoint, draft setpoint and pump status are constants in this build.
- Eligibility is low by design (volumetric periods, unassayed lots, 60-min stable window); real eligibility is unknown.

