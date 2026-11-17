# INSTALL_SITE: installing the Heater C advisory package at a site (v0.9 pilot package)
Status: DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. Built and tested on SYNTHETIC data only. Nothing here has been run against a plant.

## 0 What you get, and what it can never do
A read-only analysis tool: it reads a historian CSV EXPORT, scores it, and shows advice for a human. It has no OPC, Modbus, serial or database-write code and no path to the DCS, PLC, BMS or SIS (tested: `tests/test_phase8.py::test_adapters_have_no_plant_write_or_network_code`). Operators decide in the existing DCS.

## 1 Before you start (week 1–2 of docs/PILOT_SPEC.md)
- [ ] Sponsor, OT, EHS, OEM and MOC approvals recorded; MOC reference number in hand.
- [ ] Data-protection review done (reports/privacy_PDPA.md); operators appear only as role IDs.
- [ ] Tag walk-down finished; HTF datasheet table (T_C, rho_kgm3, cp_kJkgK) obtained; lot assay plan agreed.
- [ ] A person with read access exports the historian data to CSV (5-minute rows) into the `incoming/` folder. The tool never connects to the historian.

## 2 Prepare the site folder
Create a folder (called SITE_DIR below) with this layout. Keep it on a site computer; never commit it anywhere.
```
SITE_DIR/
  config/site.yaml        copy of config/site_template.yaml, filled in
  config/tag_map.yaml     copy of config/tag_map_template.yaml, filled in (site_tag, available, units)
  config/htf_properties.csv   the site HTF table (replaces the generic one)
  incoming/               historian CSV exports (read-only mount)
  data/  models/  reports/    created and written by the tool
```
1. `site.yaml`: set `tag_map_path: tag_map.yaml` (same folder), keep `mode: SHADOW`. Leave every limit as `REQUIRES_OEM_APPROVAL` until the OEM/EHS-signed values exist. In SHADOW mode (or with any placeholder left) the tool answers NO ADVICE.
2. `tag_map.yaml`: for EVERY site column choose `available: true|false` (the checker refuses undecided columns), enter the site tag, the site unit and the conversion (mmWC→Pa, Mkcal/h→MW, kg/s→kg/h, kg/day→kg/h are built in). Critical tags (time, operating mode, fuel lot, fuel rate or totalizer, HTF flow and temperatures, draft, FD/ID/grate commands, interlock status) must be mapped or the checker refuses.
3. Missing combustion data: columns O2, CO, furnace, flue, stack temperature and economizer dP marked `available: false` force DIAGNOSTIC ONLY (no air advice).

## 3 First run on a historical export (outside Claude Code, on the site computer)
```powershell
.\run_real_retrospective.ps1 -Site D:\SITE_DIR\config\site.yaml -Path D:\SITE_DIR\incoming\export.csv -OutDir D:\SITE_DIR\out
```
The script runs check_mapping → ingest → clean → train → shadow → monitor → M&V retrospective inside a working copy under `OutDir\workspace`, writes logs under `OutDir\logs`, and prints only file paths. Read `OutDir\workspace\reports\monitoring\latest.json` and `reports\mv\mv_retrospective.md`.

## 4 Container (for the live shadow run)
Build once on a machine WITH network access (base image and pinned packages are downloaded then): `docker build -t heater-c-advisory:0.9 .`
Copy the image to the site by your approved route (`docker save` / `docker load`). Then run it without network:
```powershell
.\run_real_live_shadow.ps1 -SiteDir D:\SITE_DIR
```
or `SITE_DIR=D:/SITE_DIR docker compose up -d` for the dashboard (published on 127.0.0.1:8501 only). See SECURITY_NOTES.md for the network design.

## 5 Acceptance checks before week 3
- `python -m src.adapters.check_mapping --site site.yaml --path export.csv` prints "tag map OK".
- `python -m src.site_config --site site.yaml` prints the mode and the number of unfilled limits.
- Monitor shows data quality %, eligible % and no DATA_FAILURE.
- `python -m src.audit --verify` reports the audit chain as VERIFIED.
ADVISORY mode is refused by the software until all limits are filled and approver, date and MOC reference are set. Do not work around this.
