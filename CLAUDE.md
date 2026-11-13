# CLAUDE.md — Heater C AI solution (synthetic build; real data never read by this tool)
## Mission
Offline, auditable decision-support for ONE biomass (palm-kernel-shell) thermic-fluid heater "Heater C" supplying HTF
to a PET process. AI scope is small: predict fuel for the next eligible interval and rank simulated operator options
versus a simple rule/regression. Humans decide. BMS/SIS/hardwired trips/DCS remain the only control authorities.
Spec: docs/SPEC.md (read only the section a prompt names). Pilot spec: docs/PILOT_SPEC.md. Progress: reports/PHASE_STATUS.md.
## Non-negotiable rules
1 Synthetic only inside this tool. Never read/transcribe/request real HMI, P&ID, interlock, operating or maintenance
  data, plant values, trip settings, usernames or person names. Public outputs: "PET Resin Plant P (anonymized)",
  heater_id=HEATER_C_SYNTHETIC, SYN_ tag aliases. No real company names/logos.
2 No network, no external APIs, no LLM at runtime, no new installs without asking.
3 No plant control: no DCS/PLC/OPC/Modbus write code, no setpoint writes, no interlock bypass. Every recommendation
  view shows "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION" (real mode: "ADVISORY ONLY — OPERATOR DECIDES").
  Fail-safe output is NO_ADVICE with reason codes.
4 Limits in code are arbitrary normalized synthetic envelopes in config; real limits come only from a signed site
  config, never invented. Placeholder "REQUIRES_OEM_APPROVAL" forces NO_ADVICE.
5 No leakage: chronological, lot-aware splits; features known at forecast time only; future target never an input
  (past lags ≥1 step allowed, tested); trailing windows only.
6 No fabricated results. Every number is computed by code here and labeled SYNTHETIC | MEASURED-IN-PROTOTYPE |
  PUBLISHED(source) | OWN-ESTIMATE(method) | COMPANY-APPROVED. Charts state numerator/denominator, units, horizon,
  provenance, uncertainty.
7 Invalid/missing heat flow, LHV, fuel basis or combustion feedback → UNVERIFIED PROXY or NO_ADVICE.
8 Synthetic optimization gains are generator illustrations, never real savings.
9 Thermic fluid: never water cp 4.186; never extrapolate cp/rho beyond the property table.
10 Phase gates: finish → packet → wait for "APPROVE PHASE N". If "RUN ALL SYNTHETIC PHASES" was given, continue but
  still write packets; always stop for installs, network, company data, irreversible actions.
## Token discipline
Never print whole CSVs/dataframes (head(5), describe().round(3), shape, value_counts). Tests: pytest -q --tb=short,
show only the last 40 lines. Write code to files, don't paste it in chat. Step summaries ≤ 15 lines. Don't re-read files
you just wrote. Ask me only for critical info, installs/network, company data, safety/plant access.
## Conventions
Python 3.11+, seeds 42 main / 77 stress / 101 site-style, Asia/Bangkok, 5-min data. Each src module runs as
`python -m src.<module> --help`. Pipeline: `python -m src.pipeline --stage all|generate|clean|train|optimize|shadow|final|dryrun`
with optional `--site <yaml> --source synthetic|csv --path <file>`. After each phase: git add -A; git commit -m "Phase N: ...".
## Phase packet (reports/phase_N_packet.md, ≤ 60 lines, then show it)
1 Implemented (past tense) 2 Files 3 Provenance & assumption IDs 4 Formulas + one worked example 5 Evidence (test counts,
real metric values, figure paths) 6 Checklist 5–10 items PASS/FAIL/NEEDS DATA 7 Known faults/limits & fix 8 Decision needed.
Then update reports/PHASE_STATUS.md in ≤ 10 lines.
