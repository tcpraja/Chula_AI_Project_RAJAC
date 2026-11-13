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

## Definitions (proposed; thresholds are normalized synthetic values in config, ASSUMED A20)
- **Eligible stable window:** ≥12 consecutive 5-min steps (60 min) with: SYN_SAFE_OK true; no active alarm; draft inside normal band; HTF supply, HTF flow and load each within a tolerance band of the window mean (band set in config); no ash-removal, soot-blowing or maintenance flag; no fuel-lot change; all ESSENTIAL_* inputs valid. Otherwise: NO_ADVICE with reason codes.
- **Reference SFC:** SFC expected for the same load and as-fired LHV under good practice (synthetic: generator "best-practice" setting; real: lot-matched percentile of the baseline period).
- **Avoidable high SFC:** window SFC minus reference SFC, flagged when the gap exceeds both a config threshold and its 90 % uncertainty band. Not a saving until measured.
- **Feasible operator action:** a change to FD/ID/grate settings inside the signed (real) or synthetic (Level 1) envelope, in the existing operator interface, with guardrails re-checked.
- **Rule-based monitoring (comparator):** fixed thresholds on O2, flue temperature and draft plus an SFC-vs-load regression alert; defined before Phase 3 and frozen.

## Success / failure (proposed in pilot spec; not yet measured)
- Success (all, on held-out lot-aware synthetic data from seeds 77 and 101): (1) forecast MAE ≥10 % below simple regression; (2) detection of avoidable-high-SFC windows beats rule-based monitoring on recall at equal false-alert rate (≤1 per shift); (3) top-1 ranked action matches the generator's best feasible action more often than the rule comparator; (4) 0 guardrail failures. Otherwise choose the simple option (see 06).
- Failure/stop: any guardrail failure; invalid critical data produces NO_ADVICE; no fabricated numbers.

## Known limits of the evidence
- **Circularity:** in Level 1, action effects are defined by the generator (A12, A17). Success shows the method works under known ground truth only. Stress (77) and site-style (101) seeds use differently specified effects to test robustness; no real savings are implied.
- **Identifiability:** without online moisture, per-lot LHV and CO on every day, operator-driven avoidable SFC cannot be separated from fuel-quality variation in real data. Level 2 requires lot-level assays.
- **Timing:** grate-bed lag (A15) makes per-interval SFC noisy; windows aggregate trailing data only.

## Constraints
Fail-safe output is NO_ADVICE with reason codes. Placeholder REQUIRES_OEM_APPROVAL limits force NO_ADVICE. Limits in code are arbitrary normalized synthetic envelopes (ASSUMED, NOT APPROVED).

## Course context
Chula LGO 2130511, individual proposal (≤3 pages) due 19 Nov 2026 23:59; talk 20 Nov.
