"""Measurement and verification (M&V): baseline vs trial windows, SFC normalised for load and moisture, comparable-load matching, lot-cluster bootstrap.

Method (SFC = kg fuel per GJ useful heat, trailing 60-min windows, eligible CALCULATED rows only, lot lab moisture, no imputation):
 1. fit SFC = b0 + b1 L + b2 L^2 + b3 M on the BASELINE rows (L = load MW, M = moisture %wb); SFC_norm = SFC - f(L, M) + f(L_ref, M_ref).
 2. comparable-load matching: keep only (1 MW load band x 4-point moisture band) cells that have enough rows in BOTH windows, and re-weight the
    baseline cells to the trial cell mix (direct standardisation), so the two windows are compared at the same operating mix.
 3. effect = mean(trial SFC_norm) - weighted mean(baseline SFC_norm); 90 % CI from 500 lot-cluster bootstrap resamples (each window resampled by fuel lot,
    model refitted each time).  4. fan penalty = change in mean FD+ID power x trial hours; AI kWh from the energy workbook.
A saving is REPORTED ONLY IF the whole CI is below 0. Otherwise the verdict is NO SAVING CLAIMED. Prints aggregates only, never rows.
Modes: retrospective (no intervention: first half vs second half of the data, or the site-config windows; the effect should be about 0) | trial (needs all four window dates).
Run: python -m src.mv_report --mode retrospective --path data/clean/clean_heater_c.csv
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "mv"
LOAD_REF, MOIST_REF = 8.5, 17.0


def design(load, moist):
    l = np.asarray(load, float) - LOAD_REF
    return np.column_stack([np.ones_like(l), l, l ** 2, np.asarray(moist, float) - MOIST_REF])


def prepare(df):
    """Eligible CALCULATED windows with load, lot moisture and fuel lot; one row per 5-min window."""
    d = df.copy()
    d["moist"] = d.groupby("fuel_lot")["fuel_moisture_wb_pct"].transform("first")
    ok = d["eligibility"].astype(str).str.startswith(("ELIGIBLE", "DIAGNOSTIC_ONLY")) & (d["status_SFC"] == "CALCULATED")
    ok &= d["SFC_win_kg_GJ"].notna() & d["Q_out_win_MW"].notna() & d["moist"].notna()
    d["usable"] = ok
    d["load"] = d["Q_out_win_MW"]
    d["sfc"] = d["SFC_win_kg_GJ"]
    d["t_local"] = pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    return d


def _fit(base):
    X, y = design(base["load"], base["moist"]), base["sfc"].to_numpy(float)
    return np.linalg.lstsq(X, y, rcond=None)[0]


def _effect(base, trial, min_cell=10):
    """Point effect for given baseline / trial frames (already restricted to usable rows). Returns (delta, base_norm_mean, n_matched_base, n_matched_trial) or None."""
    if len(base) < 50 or len(trial) < 50:
        return None
    beta = _fit(base)
    ref = float((design([base["load"].median()], [base["moist"].median()]) @ beta)[0])
    norm = lambda x: x["sfc"].to_numpy(float) - design(x["load"], x["moist"]) @ beta + ref
    b, t = base.assign(sn=norm(base)), trial.assign(sn=norm(trial))
    for x in (b, t):
        x["cell"] = np.floor(x["load"]).astype(int).astype(str) + "|" + np.floor(x["moist"] / 4).astype(int).astype(str)
    nb, nt = b["cell"].value_counts(), t["cell"].value_counts()
    cells = [c for c in nb.index if c in nt.index and nb[c] >= min_cell and nt[c] >= min_cell]
    if not cells:
        return None
    b, t = b[b["cell"].isin(cells)], t[t["cell"].isin(cells)]
    w = (t["cell"].value_counts() / b["cell"].value_counts()).reindex(b["cell"]).to_numpy()
    base_mean = float(np.average(b["sn"], weights=w))
    return float(t["sn"].mean() - base_mean), base_mean, len(b), len(t)


def estimate(df, base_mask, trial_mask, n_boot=500, seed=42, level=0.90):
    """df: prepared frame (see prepare); masks select the windows. Returns the effect with a lot-cluster bootstrap CI and the verdict."""
    base, trial = df[base_mask & df["usable"]], df[trial_mask & df["usable"]]
    pt = _effect(base, trial)
    if pt is None:
        return {"ok": False, "reason": "too few comparable rows in the two windows", "verdict": "NO SAVING CLAIMED (insufficient comparable data)"}
    delta, base_mean, nb, nt = pt
    rng = np.random.default_rng(seed)
    gb = [g for _, g in base.groupby("fuel_lot")]
    gt = [g for _, g in trial.groupby("fuel_lot")]
    boots = []
    for _ in range(n_boot):
        rb = pd.concat([gb[i] for i in rng.integers(0, len(gb), len(gb))])
        rt = pd.concat([gt[i] for i in rng.integers(0, len(gt), len(gt))])
        e = _effect(rb, rt)
        if e is not None:
            boots.append(e[0])
    a = (1 - level) / 2
    lo, hi = (float(np.quantile(boots, a)), float(np.quantile(boots, 1 - a))) if len(boots) >= 20 else (float("nan"), float("nan"))
    verdict = ("SAVING (90 % CI below 0)" if hi < 0 else "SFC INCREASE (90 % CI above 0)" if lo > 0 else "NO SAVING CLAIMED (CI includes 0)") if np.isfinite(lo) else "NO SAVING CLAIMED (CI not computable)"
    gj = float(trial["Q_out_MW"].sum() * 300 / 1000.0) if "Q_out_MW" in trial else float("nan")        # MW x 300 s = MJ; /1000 = GJ (matched windows only)
    lhv = float(trial["LHV_used_MJkg"].mean()) if "LHV_used_MJkg" in trial else float("nan")
    fan = (trial[["fan_power_kW_FD", "fan_power_kW_ID"]].sum(axis=1).mean() - base[["fan_power_kW_FD", "fan_power_kW_ID"]].sum(axis=1).mean()) if "fan_power_kW_FD" in trial else float("nan")
    return {"ok": True, "delta_sfc_kg_gj": delta, "ci90_lo": lo, "ci90_hi": hi, "delta_pct": 100 * delta / base_mean, "ci90_pct": [100 * lo / base_mean, 100 * hi / base_mean],
            "baseline_norm_sfc": base_mean, "n_base_windows": int(nb), "n_trial_windows": int(nt), "n_lots_base": len(gb), "n_lots_trial": len(gt), "n_boot_used": len(boots),
            "trial_useful_heat_gj": gj, "fuel_kg_change": delta * gj, "fuel_kg_change_ci90": [lo * gj, hi * gj], "fuel_energy_kwh_thermal": delta * gj * lhv / 3.6,
            "fan_kw_change": float(fan), "fan_kwh_change_over_trial": float(fan * len(trial) * 5 / 60), "verdict": verdict,
            "saving_reported": bool(hi < 0)}


def windows(d, mode, site=None, cli=None):
    """Baseline / trial masks. retrospective: first half vs second half of the days (split on a lot boundary); trial: all four dates are required."""
    cli = cli or {}
    mv = dict((site.raw.get("mv") if site is not None else None) or {})
    mv.update({k: v for k, v in cli.items() if v})
    keys = ("baseline_start", "baseline_end", "trial_start", "trial_end")
    if all(mv.get(k) for k in keys):
        day = lambda s: pd.Timestamp(s).tz_localize("Asia/Bangkok")
        bm = (d["t_local"] >= day(mv["baseline_start"])) & (d["t_local"] < day(mv["baseline_end"]) + pd.Timedelta(days=1))
        tm = (d["t_local"] >= day(mv["trial_start"])) & (d["t_local"] < day(mv["trial_end"]) + pd.Timedelta(days=1))
        return bm, tm, "dates"
    if mode == "trial":
        raise SystemExit("REFUSED: trial mode needs baseline_start/end and trial_start/end (CLI or the site config mv section); no default windows are guessed")
    usable = d[d["usable"]]
    cut = usable["t_local"].iloc[len(usable) // 2]
    lot_cut = usable.loc[usable["t_local"] >= cut, "fuel_lot"].iloc[0]
    first_trial = usable.index[usable["fuel_lot"] == lot_cut][0]
    return d.index < first_trial, d.index >= first_trial, "first half vs second half (split on a lot boundary)"


def ai_kwh(path=None):
    p = Path(path or ROOT / "reports" / "economics_summary.csv")
    if not p.exists():
        return None
    e = pd.read_csv(p)
    r = e[(e["key"] == "kwh_6w") & (e["scenario"] == "Base")]
    return float(r["value"].iloc[0]) if len(r) else None


def write_report(res, mode, how, out, ai):
    out.mkdir(parents=True, exist_ok=True)
    payload = {**res, "mode": mode, "windows": how, "ai_kwh_6w_base": ai, "label": "SYNTHETIC unless run on site data; a saving is claimed only if the 90 % CI excludes 0"}
    (out / f"mv_{mode}.json").write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    pd.DataFrame([{k: v for k, v in payload.items() if not isinstance(v, (list, dict))}]).to_csv(out / f"mv_{mode}.csv", index=False)
    if res.get("ok"):
        md = [f"# M&V report ({mode}) - {payload['label']}", f"Windows: {how}. Baseline {res['n_base_windows']} matched windows ({res['n_lots_base']} lots), trial {res['n_trial_windows']} ({res['n_lots_trial']} lots).",
              f"**Verdict: {res['verdict']}**", f"Normalised SFC change (trial - baseline): {res['delta_sfc_kg_gj']:+.3f} kg/GJ ({res['delta_pct']:+.2f} %), 90 % CI [{res['ci90_lo']:+.3f}, {res['ci90_hi']:+.3f}] kg/GJ "
              f"([{res['ci90_pct'][0]:+.2f}, {res['ci90_pct'][1]:+.2f}] %), {res['n_boot_used']} lot-cluster bootstrap draws.",
              f"Fuel change over the trial: {res['fuel_kg_change']:+,.0f} kg ({res['fuel_energy_kwh_thermal']:+,.0f} kWh thermal), only meaningful if the CI excludes 0.",
              f"Fan penalty: {res['fan_kw_change']:+.2f} kW ({res['fan_kwh_change_over_trial']:+,.0f} kWh over the trial). AI computing: {ai if ai is not None else 'n/a'} kWh (6 weeks, base, OWN-ESTIMATE).",
              "Retrospective mode has no intervention: the expected effect is about 0; a CI that excludes 0 would show the normalisation is not adequate." if mode == "retrospective" else
              "Trial mode: attribute a saving only after the stop conditions and approvals in docs/PILOT_SPEC.md were respected."]
    else:
        md = [f"# M&V report ({mode})", f"Verdict: {res['verdict']}", res.get("reason", "")]
    (out / f"mv_{mode}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out / f"mv_{mode}.md"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=["retrospective", "trial"])
    ap.add_argument("--path", default=str(ROOT / "data" / "clean" / "clean_heater_c.csv"), help="clean frame CSV")
    ap.add_argument("--site", default=None)
    for k in ("baseline_start", "baseline_end", "trial_start", "trial_end"):
        ap.add_argument("--" + k.replace("_", "-"), default=None, help="YYYY-MM-DD")
    ap.add_argument("--out", default=None)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--ai-kwh", type=float, default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    site = None
    if a.site:
        from src import site_config
        site = site_config.load_site(a.site)
    d = prepare(pd.read_csv(a.path))
    bm, tm, how = windows(d, a.mode, site, {k: getattr(a, k) for k in ("baseline_start", "baseline_end", "trial_start", "trial_end")})
    res = estimate(d, bm, tm, a.n_boot)
    md = write_report(res, a.mode, how, Path(a.out or OUT), a.ai_kwh if a.ai_kwh is not None else ai_kwh())
    if a.quiet:
        print(f"mv report written: {md}")
    else:
        print(f"M&V {a.mode}: {res['verdict']}" + (f"; effect {res['delta_pct']:+.2f} % (90 % CI {res['ci90_pct'][0]:+.2f} to {res['ci90_pct'][1]:+.2f}); files: {md}" if res.get("ok") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
