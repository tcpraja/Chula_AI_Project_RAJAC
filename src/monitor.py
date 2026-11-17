"""Monitoring: data quality %, eligible %, PSI drift, weekly MAE vs the simple regression, false alerts per shift.

Writes reports/monitoring/ (latest.json, psi.csv, weekly_mae.csv, daily_quality.csv, mode.json). Drift above psi_max, critical data invalid for more
than the allowed consecutive days, MAE worse than the simple regression for N consecutive weeks, or too many false alerts switches the system to
NO_ADVICE mode (mode.json); the guardrails and the dashboard honour it when a site config is active. Thresholds: config/monitoring.yaml (ASSUMED).
Prints aggregates only. Run: python -m src.monitor [--out reports/monitoring]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "monitoring"


def load_cfg(path=None):
    return yaml.safe_load(Path(path or ROOT / "config" / "monitoring.yaml").read_text(encoding="utf-8"))


def psi(ref, cur, bins=10):
    """Population stability index with reference-quantile bins. NaN if either sample is too small."""
    ref, cur = pd.Series(ref).dropna().to_numpy(float), pd.Series(cur).dropna().to_numpy(float)
    if len(ref) < 30 or len(cur) < 30:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(ref, edges)[0] / len(ref)
    q = np.histogram(cur, edges)[0] / len(cur)
    p, q = np.clip(p, 1e-4, None), np.clip(q, 1e-4, None)
    return float(np.sum((q - p) * np.log(q / p)))


def _lot_values(df, f):
    """One value per fuel lot (first lab value): lot-level features must not be counted once per 5-min row."""
    return df.dropna(subset=[f]).groupby("fuel_lot")[f].first()


def drift_table(ref, cur, cfg):
    rows = []
    for f in cfg["psi_features"]:
        if f not in ref or f not in cur:
            continue
        lot = f in cfg.get("lot_level_features", [])
        r, c = (_lot_values(ref, f), _lot_values(cur, f)) if lot else (ref[f], cur[f])
        rows.append({"feature": f, "level": "lot" if lot else "row", "psi": psi(r, c, cfg["psi_bins"]), "n_ref": int(r.notna().sum()), "n_recent": int(c.notna().sum())})
    t = pd.DataFrame(rows)
    t["status"] = np.where(t["psi"].isna(), "INSUFFICIENT_DATA", np.where(t["psi"] > cfg["psi_max"], "DRIFT", np.where(t["psi"] > cfg["psi_warn"], "WATCH", "OK")))
    return t


def daily_quality(d, cfg):
    sig = [c for c in cfg["critical_signals"] if c in d.columns]
    ok = d[sig].notna().all(axis=1) & (d.get("row_status", pd.Series("CALCULATED", index=d.index)) != "UNAVAILABLE")
    day = pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok").dt.date
    t = pd.DataFrame({"day": day, "ok": ok}).groupby("day")["ok"].agg(["mean", "size"]).reset_index()
    t["valid_pct"] = 100 * t["mean"]
    t["invalid"] = t["valid_pct"] < cfg["dq_day_valid_min_pct"]
    return t[["day", "size", "valid_pct", "invalid"]].rename(columns={"size": "rows"})


def max_consecutive(flags):
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def trailing_consecutive(flags):
    run = 0
    for f in reversed(list(flags)):
        if not f:
            break
        run += 1
    return run


def weekly_mae(F, d, model_pred, simple_pred):
    """MAE per ISO week of the selected model and of the simple regression on eligible rows with a known target."""
    m = F["eligible"].to_numpy() & F["y_ok"].to_numpy() & ~np.isnan(model_pred) & ~np.isnan(simple_pred)
    x = pd.DataFrame({"t": pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok"), "y": F["y"].to_numpy(), "pm": model_pred, "ps": simple_pred})[m]
    x["week"] = x["t"].dt.strftime("%G-W%V")
    g = x.groupby("week").apply(lambda s: pd.Series({"n": len(s), "mae_model": float(np.abs(s["y"] - s["pm"]).mean()), "mae_simple": float(np.abs(s["y"] - s["ps"]).mean())}), include_groups=False)
    g["model_worse"] = g["mae_model"] > g["mae_simple"]
    return g.reset_index()


def false_alert_rate(shadow, cfg, log=None):
    """False alerts per 8 h shift. Synthetic replay: ADVICE where the generator says HOLD/NONE. Real sites: operator rejections with a 'no change needed' style reason."""
    if shadow is not None and "eval_best_action" in shadow and shadow["eval_best_action"].notna().any():
        fa = int(((shadow["ai_decision"] == "ADVICE") & shadow["eval_best_action"].isin(["HOLD", "NONE"])).sum())
        hours = len(shadow) * 5 / 60
    elif log is not None and len(log):
        fa = int((log["decision"] == "reject").sum())
        hours = max((pd.to_datetime(log["logged_at"]).max() - pd.to_datetime(log["logged_at"]).min()).total_seconds() / 3600, cfg["shift_hours"])
    else:
        return float("nan"), 0
    return fa / (hours / cfg["shift_hours"]), fa


def decide_mode(m, cfg):
    """m: metrics dict. Returns (mode, reasons). NO_ADVICE on drift, critical-data failure, MAE worse for N weeks, or too many false alerts."""
    reasons = []
    if m.get("psi_max_value") is not None and np.isfinite(m["psi_max_value"]) and m["psi_max_value"] > cfg["psi_max"]:
        reasons.append(f"MODEL_DRIFT: PSI {m['psi_max_value']:.2f} on {m['psi_worst_feature']} > {cfg['psi_max']}")
    if m.get("invalid_days_consecutive", 0) > cfg["dq_invalid_days_max"]:
        reasons.append(f"DATA_FAILURE: critical data invalid {m['invalid_days_consecutive']} consecutive days > {cfg['dq_invalid_days_max']}")
    if m.get("weeks_worse_trailing", 0) >= cfg["mae_worse_weeks"]:
        reasons.append(f"MAE_WORSE_THAN_SIMPLE: {m['weeks_worse_trailing']} consecutive weeks")
    fa = m.get("false_alerts_per_shift")
    if fa is not None and np.isfinite(fa) and fa > cfg["false_alerts_per_shift_max"]:
        reasons.append(f"FALSE_ALERTS: {fa:.1f} per shift > {cfg['false_alerts_per_shift_max']}")
    return ("NO_ADVICE" if reasons else "NORMAL"), reasons


def current_mode(path=None):
    """Mode written by the last monitor run, or None when no run exists."""
    p = Path(path or OUT / "mode.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def enforced_codes(path=None):
    """Reason codes that force NO_ADVICE, read from mode.json. Enforced only when a site config is active (HEATER_SITE) or HEATER_ENFORCE_MONITOR=1,
    so the plain synthetic demo is not switched off by its own monitor."""
    import os
    if not (os.environ.get("HEATER_SITE") or os.environ.get("HEATER_ENFORCE_MONITOR") == "1"):
        return []
    m = current_mode(path)
    return [r.split(":")[0] for r in m["reasons"]] if m and m.get("mode") == "NO_ADVICE" else []


def run(out=None, cfg=None, quiet=False):
    from src import optimizer as op, predict as pr
    cfg = cfg or load_cfg()
    out = Path(out or OUT)
    out.mkdir(parents=True, exist_ok=True)
    d, F, _ = op.load_frames()
    d["t_local"] = pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    ref = d[d["split"] == "train"]
    cur = d[d["t_local"] >= d["t_local"].max() - pd.Timedelta(days=cfg["recent_days"])]
    dt = drift_table(ref, cur, cfg)
    dq = daily_quality(d, cfg)
    p_sel = pr.predict_raw(F, pr.resolve("selected"))[0]
    p_simple = pr.predict_raw(F, "B")[0]
    wk = weekly_mae(F, d, p_sel, p_simple)
    sh = ROOT / "reports" / "shadow_replay.csv"
    shadow = pd.read_csv(sh) if sh.exists() else None
    fa, n_fa = false_alert_rate(shadow, cfg)
    el = d["eligibility"].str.startswith("ELIGIBLE")
    worst = dt.loc[dt["psi"].idxmax()] if dt["psi"].notna().any() else None   # features with too little data are listed, never guessed
    m = {"generated": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="seconds"), "rows": int(len(d)), "recent_rows": int(len(cur)),
         "data_quality_pct": float(dq["rows"].mul(dq["valid_pct"]).sum() / dq["rows"].sum()), "data_quality_recent_pct": float(dq.tail(cfg["recent_days"])["valid_pct"].mean()),
         "invalid_days_consecutive": max_consecutive(dq["invalid"]), "invalid_days_trailing": trailing_consecutive(dq["invalid"]),
         "eligible_pct": float(100 * el.mean()), "eligible_recent_pct": float(100 * el[cur.index].mean()), "eligible_target_pct": cfg["eligible_target_pct"],
         "diagnostic_only_pct": float(100 * d["eligibility"].str.startswith("DIAGNOSTIC_ONLY").mean()),
         "psi_max_value": float(worst["psi"]) if worst is not None else None, "psi_worst_feature": str(worst["feature"]) if worst is not None else None,
         "weeks": int(len(wk)), "weeks_worse_trailing": trailing_consecutive(wk["model_worse"]) if len(wk) else 0,
         "latest_week_mae_model": float(wk["mae_model"].iloc[-1]) if len(wk) else None, "latest_week_mae_simple": float(wk["mae_simple"].iloc[-1]) if len(wk) else None,
         "false_alerts_per_shift": None if not np.isfinite(fa) else float(fa), "false_alerts_total": n_fa, "false_alerts_target": cfg["false_alerts_per_shift_target"],
         "label": "SYNTHETIC unless run on site data; thresholds ASSUMED (config/monitoring.yaml)"}
    mode, reasons = decide_mode(m, cfg)
    m["mode"], m["reasons"] = mode, reasons
    dt.round(4).to_csv(out / "psi.csv", index=False)
    wk.round(3).to_csv(out / "weekly_mae.csv", index=False)
    dq.round(2).to_csv(out / "daily_quality.csv", index=False)
    (out / "latest.json").write_text(json.dumps(m, indent=1, default=str), encoding="utf-8")
    (out / "mode.json").write_text(json.dumps({"mode": mode, "reasons": reasons, "generated": m["generated"]}, indent=1), encoding="utf-8")
    if not quiet:
        print(f"monitor: mode {mode}; data quality {m['data_quality_pct']:.1f} %, eligible {m['eligible_pct']:.1f} % (target {cfg['eligible_target_pct']:g}), "
              f"max PSI {m['psi_max_value']:.2f} ({m['psi_worst_feature']}), weeks worse than simple {m['weeks_worse_trailing']}, false alerts/shift {m['false_alerts_per_shift']}")
        for r in reasons:
            print("  " + r)
        print(f"files: {out}")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None)
    ap.add_argument("--quiet", action="store_true", help="print nothing but the output folder")
    a = ap.parse_args()
    m = run(a.out, quiet=a.quiet)
    if a.quiet:
        print(f"monitoring written: {Path(a.out or OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
