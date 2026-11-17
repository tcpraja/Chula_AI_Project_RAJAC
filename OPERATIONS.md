# OPERATIONS: running the Heater C advisory package (v0.9)
DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. Advisory only: humans decide; BMS / SIS / hardwired trips / DCS remain the only control authorities.

## Modes
| Mode | What it does | Allowed when |
|---|---|---|
| SHADOW | scores everything, shows nothing to operators (banner "SHADOW MODE — READ-ONLY …") | always |
| ADVISORY | shows advice with banner "ADVISORY ONLY — OPERATOR DECIDES" | all limits filled AND approver, date, MOC reference set |
| NO_ADVICE (forced) | every row answers NO ADVICE with a reason code | automatically, from the monitor |

## Daily routine (shift supervisor / data engineer)
1. Put the newest historian export in `incoming/`; the shadow cycle (container) or `run_real_retrospective.ps1` picks it up.
2. Open `reports/monitoring/latest.json` (or the dashboard footer): mode NORMAL or NO_ADVICE, reasons, data quality %, eligible %, PSI drift per feature, weekly MAE against the simple regression, false alerts per shift.
3. Review the operator decision log (dashboard, Decisions tab) and `python -m src.audit --verify`.

## Monitor rules (config/monitoring.yaml, ASSUMED)
- PSI above 0.25 on a monitored feature → MODEL_DRIFT → NO_ADVICE. Lot-level features need at least 30 lots in each sample, otherwise they are listed as INSUFFICIENT_DATA.
- Critical data invalid more than 3 consecutive days → DATA_FAILURE → NO_ADVICE (docs/PILOT_SPEC.md stop condition).
- Model MAE worse than the simple regression 2 consecutive weeks → NO_ADVICE (stop condition).
- False alerts above 3 per shift → NO_ADVICE (stop condition); target is 1 per shift.
- Eligible windows target is 60 % (reported, not a stop).
NO_ADVICE is lifted only by fixing the cause and re-running the monitor; never by editing `reports/monitoring/mode.json`.

## Retraining (engineer role)
`python -m src.retrain --dry-run --site config/site.yaml` compares the champion with a challenger and the simple regression. A challenger is promoted only if it is better than the champion, at least 10 % better than the simple regression, the guardrail tests pass, and (ADVISORY mode) an approver is given with `--approver "<role>"`. Without `--dry-run` the promotion also rewrites the models and logs a MODEL_PROMOTION entry in the audit log. `models/registry.json` lists every version with its data hash, metrics and approver.

## Audit log (`data/audit_log.db`)
Append-only SQLite with a hash chain: who (role operator/engineer/admin and a role ID), when, what was recommended, what was decided. UPDATE/DELETE are blocked and `python -m src.audit --verify` detects any edit. Roles: operator logs decisions; engineer also model events and monitor mode; admin also configuration and role changes. Names are never stored.

## Measurement and verification
`python -m src.mv_report --mode trial --site config/site.yaml` (needs the four window dates in `site.yaml` under `mv:`). A saving is reported only if the 90 % CI of the normalised SFC change lies entirely below 0; otherwise the report says NO SAVING CLAIMED. On the synthetic data the smallest effect the method can resolve is about 0.8 % of fuel, so a smaller real effect will not be shown within a six-week pilot.

## Stop conditions (verbatim from docs/PILOT_SPEC.md)
Stop: any safety/OT incident linked to pilot; any guardrail failure; critical data invalid >3 consecutive days; MAE worse than simple regression 2 consecutive weeks; false alerts >3/shift for 1 week; approval withdrawn/unavailable.
