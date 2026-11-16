# Six-week pilot plan — Heater C advisory (DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL)
Source of scope: docs/PILOT_SPEC.md. One heater, read-only, human decides. Everything below is a plan, not a result.
Provenance: plan text OWN-ESTIMATE; every number from this repository is SYNTHETIC. Owners are roles, not people.

## 0 Boundaries
- Read-only: no write path to DCS/PLC/BMS/SIS, no setpoint writes, no interlock bypass. BMS / SIS / hardwired trips / DCS remain the only control authorities.
- This repository's tool never reads real plant data (CLAUDE.md rule 1). A site pilot needs a separate, approved decision on where real data are processed and by whom (executive_decision_gate.md, decision D3). Until then every pilot step below is a plan.
- Limits come only from a signed site config. Any value left as REQUIRES_OEM_APPROVAL forces NO_ADVICE.

## 1 Week by week
| Week | Purpose | Activities | Exit evidence | Owner role |
|---|---|---|---|---|
| 1 | Approvals | Sponsor, OT, EHS, OEM and MOC approvals requested; data-protection review (privacy_PDPA.md); risk register walk-through; scorecard baseline definitions agreed | Signed approval register (all five present) | Project sponsor |
| 2 | Data readiness | Tag walk-down against the candidate tag list; HTF datasheet obtained; lot assay plan; historian export (read-only); baseline definition frozen; signed site limits config | Tag map signed, at least 1 month of export loaded, limits config signed | Data/OT engineer, Process engineer |
| 3 | Shadow, part 1 | Read-only shadow: model scores every window, nothing shown to operators except in the blind review sheet; daily guardrail re-check | T1, T2, T4 started; stop-condition checks daily | Data scientist |
| 4 | Shadow, part 2 | Operators review advisories blind (no knowledge of what the rule says); log decision, reason, time | T3, T5 (blind), T6, T7 numbers; weekly MAE vs simple regression | Shift supervisor |
| 5 | Supervised advisory (only if authorised) | Advisory shown to the operator; operator decides in the existing DCS; advice never actuates anything | Decision log with reasons; T5 on live advice | Shift supervisor, EHS lead |
| 6 | Measurement and decision | M&V: normalised SFC with 90 % CI (T8), cost and energy accounting, operator feedback, GO / REVISE / STOP | Filled pilot_scorecard.csv; economics_and_energy.xlsx with measured inputs replacing the yellow ASSUMED cells | Energy manager, Project sponsor |

If week 5 is not authorised, it repeats shadow and the decision rests on shadow evidence only; T8 is then "not measured".

## 2 Roles
Project sponsor (decides), OT/IT lead (data access, read-only), EHS lead (safety review, T2/T3), OEM contact (limits), Process engineer (T7, T9), Energy manager (T8, economics), Data scientist (T4), Shift supervisor (operator decisions; operators appear as OP-A / OP-B only).

## 3 Measurement (details in pilot_scorecard.csv)
Nine targets (T1–T9) and six stop conditions (S1–S6), quoted verbatim from docs/PILOT_SPEC.md. Actuals are blank until measured. The weekly review checks S1–S6 first.

## 4 Compute and energy of the AI itself (times MEASURED-IN-PROTOTYPE; power OWN-ESTIMATE)
Wall times on the development PC: generate 2.55 s, train 18.5 s, shadow replay (3,041 rows) 2.36 s, dashboard start-to-healthy 1.54 s, page render about 0.3 s. At an assumed 60 W (range 35–100 W, no wattmeter) the whole six-week AI workload is about 3.6 kWh (range 1.4–9.1); monthly about 2.6 kWh. Source: reports/economics_and_energy.xlsx, sheet Model.

## 5 Deliverables at week 6
Filled scorecard, decision-log export, MAE comparison, normalised SFC with CI (or "not measured"), cost and energy sheet with measured inputs, lessons learned, GO / REVISE / STOP recommendation to the sponsor.
