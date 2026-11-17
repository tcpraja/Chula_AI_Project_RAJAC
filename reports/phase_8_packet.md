# Phase 8 Packet — Pilot package (SYNTHETIC only; DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL)
## 1 Implemented
Built read-only adapters (ReadOnlySource, CsvExportSource, SyntheticSource) with a tag map covering all 105 data-dictionary columns (units, conversions mmWC→Pa, Mkcal/h→MW, kg/s→kg/h; unavailable combustion columns force DIAGNOSTIC_ONLY) and a mapping checker that refuses unmapped critical tags; a site config whose ADVISORY mode is refused unless every limit and the approval are filled; champion/challenger retraining with a hard promotion rule and models/registry.json; a monitor (data quality, eligible %, PSI drift, weekly MAE vs the simple regression, false alerts) that can force NO_ADVICE; a hash-chained append-only audit log; an M&V report (matched comparison cells, load and moisture normalisation, lot-cluster bootstrap 90 % CI, fan penalty, AI kWh); Dockerfile, compose, four site documents; three run_real_*.ps1 scripts; 38 new tests.
## 2 Files
src/adapters/{base,conversions,tagmap,csv_export,synthetic,check_mapping,ingest}.py; src/{site_config,retrain,monitor,audit,mv_report,site_demo}.py; src/ops/tcp_proxy.py; ops/shadow_loop.sh; config/{tag_map_template,site_template,monitoring,tag_map_synthetic_site,site_synthetic_demo}.yaml; models/registry.json; Dockerfile, docker-compose.yml, .dockerignore, requirements-runtime.txt; INSTALL_SITE.md, OPERATIONS.md, ROLLBACK.md, SECURITY_NOTES.md; run_real_retrospective.ps1, run_real_live_shadow.ps1, run_real_mv.ps1; tests/test_phase8.py; edits: guardrails (force_codes, site_unavailable), cleaning (unknown bypass = UNVERIFIED), pipeline (site config, label-free clean, extras skipped without truth), oplog (audit copy).
## 3 Provenance & assumption IDs
All SYNTHETIC. Site-style data: generator seed 101 profile site_style, invented tags SITE_<NAME>, example site units. Monitoring thresholds, ops guidance and the demo site approval fields are ASSUMED / NOT APPROVED (config/monitoring.yaml, config/site_synthetic_demo.yaml marks approval "SYNTHETIC-TEST").
## 4 Formulas + one worked example
PSI = Σ (q−p) ln(q/p) over reference-quantile bins; normalised SFC = SFC − f(L,M) + f(L_ref,M_ref); effect = mean(trial) − cell-reweighted mean(baseline); saving only if the 90 % CI upper bound < 0. Example: a −3 % effect injected into the trial half is recovered as −2.86 % with 90 % CI [−3.66, −2.13]; with no effect the estimate is +0.05 % [−0.76, +0.80], so no saving is claimed.
## 5 Evidence
- Tests: 162 passed, 1 skipped (Docker build smoke needs network; set RUN_DOCKER_BUILD=1). `docker compose config` validates the compose file.
- run_real_retrospective.ps1 ran all 7 steps in 27 s on a label-free site-style export (invented tags, mmWC/kg/s/Mkcal/h): check_mapping → ingest → clean → train → shadow → monitor → M&V; round trip of units exact to 1e-12.
- Unavailable CO and O2 turn every ELIGIBLE row into DIAGNOSTIC_ONLY (1,126 rows in the test slice); placeholder limits give NO_ADVICE on all rows.
- Monitor on the main synthetic data: mode NORMAL, data quality 98.2 %, eligible 26.9 % (pilot target 60 %), max PSI 0.20 (Q_out_MW, WATCH), model never worse than the simple regression, false alerts 1.99 per shift (target 1, stop above 3). Lot-level moisture PSI is INSUFFICIENT_DATA (11 lots, needs 30).
- Retrain dry run: challenger identical to champion (MAE 53.92 vs simple regression 106.38) → KEEP_CHAMPION.
## 6 Checklist
- Adapters read-only, no OPC/Modbus/DB-write code (AST test): PASS
- Unmapped critical tag refused: PASS · ADVISORY refused with placeholders / missing approver: PASS
- Promotion only if better AND guardrail tests pass (+10 % vs simple): PASS · drift → NO_ADVICE: PASS
- Audit tamper detected, UPDATE/DELETE blocked, roles enforced: PASS · M&V recovers a known effect within CI: PASS
- Docker image built and run: NEEDS DATA (not built: download needs network; asking) · real-data run: NEEDS DATA (user runs outside)
## 7 Known faults/limits
- The M&V method can only resolve about ±0.8 % of fuel on this data; the simulated 0.24 % effect would not be seen in a six-week trial.
- Audit and operator log actor IDs are free text: there is no login, so the log shows who was typed, not who was authenticated. Dashboard has no authentication (127.0.0.1 binding only).
- The compose gateway needs a host firewall rule against outbound traffic. On site data train may select no model (then NO_ADVICE for every row, by design).
- Run on real data: engineering eligibility still uses the synthetic envelope for its own diagnostics until site limits are filled; advice is refused regardless.
## 8 Decision needed
APPROVE PHASE 8 and tag v0.9-pilot-package? May I build the Docker image (downloads base image and packages)? Who will fill the tag map and which authentication the site wants for the audit roles?
