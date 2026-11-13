# 06 Options Comparison (SYNTHETIC / OWN-ESTIMATE; no real savings claimed)
Cost ranges are OWN-ESTIMATE order-of-magnitude placeholders (THB, one heater, 6-week scope) to be replaced by quotes; they are not measured.

| Option | Cost range (OWN-ESTIMATE) | Complexity | Benefit | Limits | Risk | Testable now (synthetic)? |
|---|---|---|---|---|---|---|
| 1 No change | 0 | None | None; keeps current fuel-above-benchmark baseline | Operator-dependent air/grate, infrequent LHV tests persist | Continued avoidable fuel use | Yes: this is the baseline in simulation |
| 2 Process change (SOP, fuel-lot LHV/moisture sampling, operator training) | Low (tens of kTHB) | Low | Better fuel data and consistent practice | Depends on discipline; no live detection | Drift back to old habits | Partly: generator can model operator variability |
| 3 Simple automation (rule-based monitoring: O2/draft/flue-T thresholds, SFC regression, alerts) | Low-medium (≈ 100-300 kTHB) | Low-medium | Detect avoidable high SFC with transparent rules | Fixed thresholds; no ranking of actions | False alerts; rule rot | Yes: rule baseline + simple regression |
| 4 AI (forecast next-interval fuel; rank simulated feasible actions with uncertainty) | Medium (≈ 300-800 kTHB incl. pilot support) | High | Possible ranking of actions beyond rules | Needs LHV/moisture/CO data; generalization unproven; explainability | Over-trust; leakage; unsafe advice | Yes, on synthetic ground truth only |

## Choice rule
AI (option 4) is chosen ONLY if Phase 3 shows model MAE ≥10 % below the simple regression (option 3) and ranked actions beat rule-based monitoring on held-out, lot-aware synthetic data. Otherwise option 3 (or 2) is recommended. Until Phase 3 completes, no option is selected.

## Common to all options
Read-only; data stays on-site; operator decides; BMS/SIS/DCS remain control authorities; PDPA: no personal data in features, operator-log user IDs pseudonymized. Where it runs: offline workstation (Level 1), on-site read-only server (Level 2).
