# ROLLBACK: returning to the previous state (v0.9)
DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. Because the package is read-only and advisory, rollback never touches the plant: operators simply stop using the advice.

## Fastest: stop using the advice (seconds)
1. Set `mode: SHADOW` in `config/site.yaml` (or start the container with `-e MODE=SHADOW`) and restart the app. Advice is withheld at once.
2. Tell the shift supervisor; operate as before. Nothing in the DCS, PLC, BMS or SIS was changed by this package, so nothing there needs reverting.
3. Log the event (admin or engineer): `python -c "from src import audit; audit.append('admin','<role id>','ROLLBACK',None,'MODE=SHADOW','reason')"`.

## Roll back the model (minutes)
1. Open `models/registry.json`; find the previous version (status `retired`) and its data hash.
2. Restore that version's model files from your backup of the `models/` folder (backups are taken before every promotion: copy `models/` to `models_backup_<date>/` first).
3. Edit the registry: set the restored entry to `champion`, the current one to `retired`; add a MODEL_PROMOTION or ROLLBACK audit entry.
4. Run `python -m src.monitor` and confirm mode NORMAL; run `python -m pytest -q tests/test_advisory_gate.py`.

## Roll back the software (minutes)
`docker compose down`, then start the previous image tag (`heater-c-advisory:<previous>`) with the same SITE_DIR. Keep at least the two latest tags on the site computer. Data, models, reports and the audit log live in SITE_DIR and are not affected.

## Remove everything
`docker compose down --rmi local`, delete the image, and keep or archive SITE_DIR according to the site retention rule (privacy note proposes the pilot plus 90 days). The audit log should be archived, not deleted, until the pilot review is signed.

## What does NOT need rolling back
No setpoint was written, no interlock changed, no historian configuration touched, no firewall rule opened for this package.
