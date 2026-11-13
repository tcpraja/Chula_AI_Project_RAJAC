# 06 Options Comparison (no money estimated; no real savings claimed)
Cost is given as cost drivers plus "quote required". No currency amounts are guessed (C8: refuse to guess unmeasurable money).

| Option | Cost drivers (quote required) | Complexity | Benefit | Limits | Risk | Data source | Runs where | PDPA | Testable now (synthetic)? |
|---|---|---|---|---|---|---|---|---|---|
| 1 No change | None | None | None; baseline stays | Operator-dependent air/grate, infrequent LHV tests persist | Continued avoidable fuel use | Existing HMI only | n/a | n/a | Yes: baseline in simulation |
| 2 Process change (SOP, lot LHV/moisture sampling, training) | Lab time, sampling labour, training hours | Low | Better fuel data, consistent practice | Discipline-dependent; no live detection | Drift to old habits | Lab assays, shift logs | Paper/spreadsheet | Shift logs name operators: restrict access | Partly: generator models operator variability |
| 3 Simple automation (rule monitoring + SFC regression + alerts) | Engineering hours, historian read access, display | Low-medium | Transparent detection of high SFC | Fixed thresholds; no action ranking | False alerts; rule rot | Historian export (read-only) | On-site read-only workstation | Alert acknowledgements pseudonymized | Yes: rules + regression comparator |
| 4 AI (forecast next-interval fuel; rank simulated feasible actions with uncertainty) | Option 3 costs + data engineering, validation, model governance | High | Possible action ranking beyond rules | Needs LHV/moisture/CO data; generalization unproven | Over-trust, leakage, unsafe advice | Historian + lot assays | On-site read-only server, offline | As option 3 plus model-log retention | Yes: synthetic ground truth only |

## Choice rule
AI (option 4) is chosen ONLY if Phase 3 meets all success criteria in 00 (MAE ≥10 % below simple regression, better detection than rules at equal false-alert rate, 0 guardrail failures). Otherwise option 3, or 2, is recommended. No option is selected until Phase 3 completes.

## Common to all options
Read-only; operator decides; BMS/SIS/DCS remain control authorities; no personal data in process features.
