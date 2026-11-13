# 00 Scope Charter — Heater C AI Decision Support (SYNTHETIC)
Organization: PET Resin Plant P (anonymized). heater_id = HEATER_C_SYNTHETIC. Status: DRAFT for Phase 0 approval.

## In scope
- ONE biomass (palm-kernel-shell) travelling-grate thermic-fluid (HTF) heater, "Heater C", supplying HTF to a PET process.
- Offline, auditable decision support: predict fuel for the next eligible interval; rank simulated operator options against a simple rule/regression baseline.
- Synthetic data only inside this tool (generator seeds 42 main / 77 stress / 101 site-style; 5-min data; Asia/Bangkok).

## Out of scope
- Cutters; all other heaters; plantwide optimization; predictive maintenance.
- Any plant control: no DCS/PLC/OPC/Modbus write, no setpoint writes, no interlock bypass. BMS/SIS/hardwired trips/DCS stay the only control authorities.
- Reading real HMI, P&ID, interlock, operating or maintenance data inside this tool; real limits or trip settings; runtime LLM or network use.

## Two levels
| | Level 1 — synthetic demonstrator | Level 2 — read-only pilot |
|---|---|---|
| Data | Generated here, SYN_ aliases, labeled SYNTHETIC | Historian export, read-only, after approvals |
| Output | "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION" | "ADVISORY ONLY — OPERATOR DECIDES" |
| Claims | Method works on known ground truth; gains are generator illustrations, never savings | Normalized SFC effect only if 90 % CI excludes 0 |
| Gate | Phase approvals in this repo | Sponsor, OT, EHS, OEM, MOC approvals (see 07, docs/PILOT_SPEC.md) |
| Status | This build | Not started; requires a company-data access decision |

## MVP question
"For an eligible stable window, can the tool detect avoidable high SFC and rank a simulated feasible operator action better than rule-based monitoring?"
SFC = specific fuel consumption (fuel energy per unit useful heat, as-fired LHV basis; formula in SPEC C3, implemented Phase 1+).

## Success / failure (proposed in pilot spec; not yet measured)
- Success: model MAE ≥10 % below simple regression AND ranked action beats rule-based monitoring on synthetic ground truth. Otherwise choose the simple option (see 06).
- Failure/stop: any guardrail failure; invalid critical data produces NO_ADVICE; no fabricated numbers.

## Constraints
Fail-safe output is NO_ADVICE with reason codes. Placeholder REQUIRES_OEM_APPROVAL limits force NO_ADVICE. Limits in code are arbitrary normalized synthetic envelopes (ASSUMED, NOT APPROVED).

## Course context
Chula LGO 2130511, individual proposal (≤3 pages) due 19 Nov 2026 23:59; talk 20 Nov.
