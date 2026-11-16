# Risk register — Heater C advisory pilot (DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL)
Scoring: likelihood L and impact I from 1 (low) to 5 (high), score = L × I. Both are OWN-ESTIMATE judgements on synthetic evidence, to be re-scored on site. Owners are roles.

| ID | Risk | L | I | Score | Control (existing or planned) | Owner role | Residual / trigger |
|---|---|---|---|---|---|---|---|
| R01 | Operator follows advice that is wrong or unsafe | 2 | 5 | 10 | Advisory only; operator decides in the existing DCS; BMS/SIS/trips untouched; NO_ADVICE on any doubt; EHS re-check (T2, T3) | EHS lead | Any unsafe advice: stop (S2) |
| R02 | Software path to plant control created by mistake | 1 | 5 | 5 | No DCS/PLC/OPC/Modbus write code in the repo; read-only export; code review before install | OT/IT lead | Any write capability found: stop |
| R03 | Limits in config are not the real limits | 3 | 5 | 15 | Limits are synthetic/ASSUMED; REQUIRES_OEM_APPROVAL forces NO_ADVICE; signed site config only | OEM contact | No signed config = no advice |
| R04 | Bad data (flow, LHV, fuel basis, stale tags) give confident but wrong numbers | 4 | 4 | 16 | Layer-1 checks, UNVERIFIED PROXY labels, critical-data stop (S3), lot assay plan | Data/OT engineer | More than 3 invalid days: stop |
| R05 | Model works on synthetic data, fails on the real plant (distribution shift, confounding) | 4 | 3 | 12 | Shadow first; MAE vs simple regression (T4, S4); OOD gate; effect model is associational only | Data scientist | MAE worse 2 weeks: stop |
| R06 | Effect model suggests moves that look good but are not causal | 4 | 3 | 12 | Effect claimed only from measured normalised SFC with 90 % CI excluding 0 (T8) | Energy manager | No claim without T8 |
| R07 | Too many false alerts, alarm fatigue, advice ignored | 3 | 3 | 9 | At most 1 false alert/shift; stop above 3/shift for a week (S5); NO_ADVICE is the default | Process engineer | S5 |
| R08 | Synthetic gains quoted as real savings by a reader | 3 | 4 | 12 | Banner on every screen; "no verified savings"; labelled provenance; economics use fictional THB | Project sponsor | Remove any figure lacking a label |
| R09 | Fuel lot change, moisture swing or sensor outage invalidates a week | 4 | 2 | 8 | Lot-aware evaluation; lab moisture/LHV per lot; report by lot | Process engineer | Excluded window reported |
| R10 | CO analyser missing or unusable, advice limited to DIAGNOSTIC ONLY | 4 | 2 | 8 | NO_CO rule; CO-analyser allowance in economics (OWN-ESTIMATE range) | OT/IT lead | No CO = no air advice |
| R11 | Personal data (operator names, notes) enter logs | 2 | 3 | 6 | Role IDs OP-A / OP-B only; 200-character note with warning; privacy_PDPA.md | Privacy contact | Names found: purge and fix |
| R12 | Software not maintained; model drifts | 3 | 2 | 6 | Upkeep line in economics; weekly MAE check; frozen model card | Data scientist | Upkeep unfunded = REVISE |
| R13 | Approvals lapse mid-pilot | 2 | 4 | 8 | Weekly approval-register check (S6) | Project sponsor | S6 |
| R14 | Reliance on one developer / one laptop | 3 | 2 | 6 | Repo, deterministic pipeline, README, tests | Data scientist | Handover before week 5 |
| R15 | Economics do not pay back at the simulated effect size | 4 | 3 | 12 | Break-even analysis in economics_and_energy.xlsx; decision gate shows required vs simulated fuel saving | Energy manager | See executive_decision_gate.md |

Highest scores: R04 (16), R03 (15), then R05, R06, R08, R15 (12 each). Nothing here is a measured probability.
