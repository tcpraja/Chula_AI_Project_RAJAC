#!/bin/sh
# Live SHADOW cycle inside the container (no network, read-only source, outputs to the mounted site folders).
# Every cycle: take the newest historian export in /incoming, check the tag map, ingest, clean, score in shadow, monitor. Prints only file names.
set -u
SITE="${HEATER_SITE:-/app/config/site.yaml}"
CYCLE="${CYCLE_SECONDS:-3600}"
export MODE="${MODE:-SHADOW}"
log() { echo "[$(date +%H:%M:%S)] $*"; }
while true; do
  F=$(ls -t /incoming/*.csv 2>/dev/null | head -n 1)
  if [ -z "$F" ]; then log "no export found in /incoming"; else
    log "cycle on $(basename "$F")"
    python -m src.adapters.check_mapping --site "$SITE" --path "$F" > /app/reports/shadow_check_mapping.log 2>&1 || { log "REFUSED by check_mapping (see reports/shadow_check_mapping.log)"; sleep "$CYCLE"; continue; }
    python -m src.adapters.ingest --site "$SITE" --path "$F" --out /app/data/raw_site/raw.csv > /app/reports/shadow_ingest.log 2>&1 \
      && python -m src.pipeline --stage clean --source csv --path /app/data/raw_site/raw.csv --site "$SITE" > /app/reports/shadow_clean.log 2>&1 \
      && python -m src.pipeline --stage shadow > /app/reports/shadow_stage.log 2>&1 \
      && python -m src.monitor --quiet > /app/reports/shadow_monitor.log 2>&1 \
      && log "cycle done: reports/shadow_replay.csv, reports/monitoring/" || log "cycle failed (see reports/shadow_*.log)"
  fi
  [ "${ONCE:-0}" = "1" ] && break
  sleep "$CYCLE"
done
