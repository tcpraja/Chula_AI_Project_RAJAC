"""Champion / challenger retraining with a hard promotion rule, plus models/registry.json (version, data hash, metrics, approver).

A challenger replaces the champion ONLY IF all of: (1) its test MAE is lower than the champion's on the same rows, (2) it is at least
`min_gain_vs_simple` (10 %, PILOT_SPEC target T4) better than the simple regression, (3) the guardrail tests pass, (4) an approver is recorded when
a site runs ADVISORY mode. Otherwise the champion stays; if the champion itself is not 10 % better than the simple regression the report
recommends the simple regression. Nothing is promoted automatically on real data without an approver. Every decision is written to the audit log.
Run: python -m src.retrain [--init] [--dry-run] [--approver "<role>"] [--site site.yaml]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models" / "registry.json"
MIN_GAIN_VS_SIMPLE = 0.10


def now():
    return datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="seconds")


def load_registry(path=None):
    p = Path(path or REGISTRY)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"schema": 1, "champion": None, "entries": []}


def save_registry(reg, path=None):
    p = Path(path or REGISTRY)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, indent=1), encoding="utf-8")


def promotion_decision(champion_mae, challenger_mae, simple_mae, guardrail_ok, approver=None, require_approver=False, min_gain=MIN_GAIN_VS_SIMPLE):
    """Pure rule. Returns {decision: PROMOTE|KEEP_CHAMPION, reasons, simple_recommended}."""
    reasons = []
    if challenger_mae is None or not np.isfinite(challenger_mae):
        reasons.append("no challenger passed the safety gate")
    elif not challenger_mae < champion_mae:
        reasons.append(f"challenger MAE {challenger_mae:.2f} is not lower than champion {champion_mae:.2f}")
    if challenger_mae is not None and np.isfinite(challenger_mae) and not challenger_mae <= (1 - min_gain) * simple_mae:
        reasons.append(f"challenger is not at least {100 * min_gain:.0f} % better than the simple regression ({challenger_mae:.2f} vs {simple_mae:.2f})")
    if not guardrail_ok:
        reasons.append("guardrail tests failed")
    if require_approver and not approver:
        reasons.append("no approver recorded (required in ADVISORY mode)")
    return {"decision": "KEEP_CHAMPION" if reasons else "PROMOTE", "reasons": reasons,
            "simple_recommended": bool(not champion_mae <= (1 - min_gain) * simple_mae)}


def guardrail_tests_pass():
    """Run the guardrail test file; True only if every test passes."""
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "tests/test_advisory_gate.py"], cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0


def new_entry(version, data_sha, metrics, status, approver=None, note=""):
    return {"version": version, "created": now(), "data_sha256": data_sha, "metrics": metrics, "status": status, "approver": approver, "note": note}


def promote(reg, entry, actor_id="retrain", audit_path=None):
    """Make `entry` the champion, retire the previous one, log it. Returns the registry."""
    for e in reg["entries"]:
        if e["status"] == "champion":
            e["status"] = "retired"
    entry["status"] = "champion"
    reg["entries"].append(entry)
    reg["champion"] = entry["version"]
    from src import audit
    audit.append("engineer", actor_id, "MODEL_PROMOTION", {"version": entry["version"], "data_sha256": entry["data_sha256"]}, "PROMOTE", json.dumps(entry["metrics"]), audit_path)
    return reg


def init_registry(path=None):
    """Register the model currently on disk (the Phase 3 selection) as the initial champion."""
    import pandas as pd
    meta = json.loads((ROOT / "models" / "metadata.json").read_text(encoding="utf-8"))
    mc = pd.read_csv(ROOT / "reports" / "model_comparison.csv")
    sel = mc[(mc.model == meta["selected"]) & (mc.population == "eligible_test") & (mc.segment_type == "ALL") & (mc.segment == "ALL")].iloc[0]
    simple = mc[(mc.model == "B") & (mc.population == "eligible_test") & (mc.segment_type == "ALL") & (mc.segment == "ALL")].iloc[0]
    e = new_entry(f"{meta['selected']}-{meta['data_sha256'][:8]}", meta["data_sha256"],
                  {"test_mae_kgh": round(float(sel["MAE"]), 3), "simple_regression_mae_kgh": round(float(simple["MAE"]), 3), "valb_mae_kgh": round(float(sel["MAE_valb"]), 3)},
                  "champion", "SYNTHETIC-BASELINE (not a real approval)", "initial champion from the Phase 3 selection; SYNTHETIC")
    reg = {"schema": 1, "champion": e["version"], "entries": [e]}
    save_registry(reg, path)
    return reg


def retrain(dry_run=True, approver=None, require_approver=False, registry_path=None, guardrail_check=guardrail_tests_pass):
    from src import predict as pr, train
    cfg = train.load_cfg()
    res = train.run(cfg, write=False)
    reg = load_registry(registry_path) or {}
    if not reg.get("entries"):
        reg = init_registry(registry_path)
    champ_name = pr.resolve("selected")
    te = res["te"]
    y = te["y"].to_numpy(float)
    champ_pred = pr.predict_raw(te, champ_name)[0]
    ok = ~np.isnan(champ_pred)
    champ_mae = float(np.abs(y[ok] - champ_pred[ok]).mean())
    chosen = res["chosen"]
    chall_mae = float(res["tbl"][chosen]["MAE"]) if chosen else None
    simple_mae = float(res["tbl"]["B"]["MAE"])
    g_ok = bool(guardrail_check())
    dec = promotion_decision(champ_mae, chall_mae, simple_mae, g_ok, approver, require_approver)
    clean = ROOT / "data" / "clean" / "clean_heater_c.csv"
    data_sha = train.sha(clean)
    out = {"champion": champ_name, "challenger": chosen, "champion_mae": champ_mae, "challenger_mae": chall_mae, "simple_mae": simple_mae, "guardrail_ok": g_ok, **dec,
           "dry_run": dry_run, "label": "SYNTHETIC unless run on site data"}
    if dec["decision"] == "PROMOTE" and not dry_run:
        train.write_outputs(res, cfg, clean)
        reg = promote(reg, new_entry(f"{chosen}-{data_sha[:8]}", data_sha, {"test_mae_kgh": chall_mae, "simple_regression_mae_kgh": simple_mae}, "challenger", approver,
                                     "promoted by src.retrain"))
        save_registry(reg, registry_path)
    else:
        from src import audit
        audit.append("engineer", "retrain", "MODEL_REJECTION", {"challenger": chosen, "data_sha256": data_sha}, "KEEP_CHAMPION", "; ".join(dec["reasons"]) or "dry run")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true", help="register the model on disk as the initial champion")
    ap.add_argument("--dry-run", action="store_true", help="compare and report, never write models")
    ap.add_argument("--approver", default=None, help="role/title of the approver (no personal names)")
    ap.add_argument("--site", default=None)
    a = ap.parse_args()
    if a.init:
        reg = init_registry()
        print(f"registry written: {REGISTRY} (champion {reg['champion']})")
        return 0
    req = False
    if a.site:
        from src import site_config
        s = site_config.load_site(a.site).validate()
        req = s.mode == "ADVISORY"
    r = retrain(a.dry_run, a.approver, req)
    print(f"retrain: champion {r['champion']} MAE {r['champion_mae']:.2f} | challenger {r['challenger']} MAE {r['challenger_mae']} | simple regression MAE {r['simple_mae']:.2f} -> {r['decision']}")
    for x in r["reasons"]:
        print("  " + x)
    if r["simple_recommended"]:
        print("  NOTE: the champion is not 10 % better than the simple regression: prefer the simple regression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
