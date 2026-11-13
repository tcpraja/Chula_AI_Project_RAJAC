"""reports/data_quality.md and figures p2_data_quality / p2_uncertainty_day from the cleaning outputs.
Run: python -m src.dq_report
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.cleaning import load_cfg
from src.engineering import daily_energy

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figs"
TAG = "SYNTHETIC - NOT FOR PLANT OPERATION"
C = {"a": "#1f6f8b", "b": "#d1495b", "c": "#edae49", "g": "#66737d"}


def run(raw_path=None, cfg=None):
    cfg = cfg or load_cfg()
    raw = pd.read_csv(raw_path or ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv")
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv")
    rej = pd.read_csv(ROOT / "data" / "clean" / "rejected_rows.csv")
    ev = pd.read_csv(ROOT / "data" / "clean" / "eval_labels.csv")
    rep = json.loads((ROOT / "data" / "clean" / "clean_report.json").read_text())
    d = d.merge(ev[["timestamp_local", "scenario_id", "is_fault_injected", "gen_advice_eligibility"]], on="timestamp_local", how="left")
    d["k"] = d["timestamp_local"].str[:19]
    rej_keys = set(rej["timestamp_local"].str[:19])
    # --- fault detection table (uses generator labels; evaluation only)
    inj = raw[raw["is_fault_injected"] == 1].assign(k=lambda x: x["timestamp_local"].str[:19])
    inj["fault"] = inj["scenario_id"].str.replace("FAULT_", "", regex=False)
    elig = d.set_index("k")["eligibility"]
    rows = []
    for f, g in inj.groupby("fault", sort=False):
        k = g["k"]
        rj = k.isin(rej_keys)
        el = k.map(elig)
        still = el.fillna("").str.startswith("ELIGIBLE")
        rows.append((f, len(g), int(rj.sum()), int((~rj & ~still).sum()), int((still & ~rj).sum())))
    det = pd.DataFrame(rows, columns=["fault", "injected_rows", "rejected", "flagged_not_eligible", "still_ELIGIBLE"])
    # --- reconciliation
    de = daily_energy(d)
    full = de[de["rows"] >= 280]
    rel_fuel = ((full["fuel_kg_totalizer"] - full["fuel_kg_rate"]).abs() / full["fuel_kg_rate"])
    rel_q = ((d["rep_Q_out_MW"] - d["Q_out_MW"]).abs() / d["Q_out_MW"]).dropna()
    q_unit = int(d["unit_suspect"].sum())
    belt = d["fuel_mass_basis"] == "WEIGH_BELT"
    known = d["lhv_known"] == 1
    op = d["operating_mode"].isin(["STEADY", "RAMP"])
    unc_q = (d["Q_out_u_MW"] / d["Q_out_MW"])[op].median() * 100
    unc_s_b = (d["SFC_u_kg_GJ"] / d["SFC_kg_GJ"])[belt & op].median() * 100
    unc_s_v = (d["SFC_u_kg_GJ"] / d["SFC_kg_GJ"])[~belt & op].median() * 100
    wid_k = ((d["eta_hi_pct"] - d["eta_lo_pct"]) / 2)[known & op & d["eta_pct"].notna()].median()
    wid_u = ((d["eta_hi_pct"] - d["eta_lo_pct"]) / 2)[~known & op & d["eta_lo_pct"].notna()].median()
    reasons = d["eligibility"][d["eligibility"].str.startswith("NO_ADVICE")].str.split(":").str[1].str.split(";").explode().value_counts()
    agree = (d["eligibility"].str.split(":").str[0] == d["gen_advice_eligibility"].str.split(":").str[0]).mean() * 100
    n_nan_safety = {c: int(d[c].isna().sum()) for c in ("draft_pa", "interlock_active")}
    figs(d, rep, reasons)
    L = ["# Data Quality Report (SYNTHETIC) - Heater C", "",
         "Produced by `python -m src.pipeline --stage clean` (src/cleaning.py, src/engineering.py). Raw files are never modified; "
         "nothing is interpolated or filled; LHV is never invented. Times are Asia/Bangkok (+07:00, no DST).", "",
         "## Counts", "| Measure | Result | Method |", "|---|---|---|",
         f"| Raw rows | {rep['n_raw']:,} | main file, seed 42 |",
         f"| Clean rows | {rep['n_clean']:,} | passed schema, duplicates, frozen, plausibility, property table |",
         f"| Rejected rows | {rep['n_rejected']:,} | {', '.join(f'{k} {v}' for k, v in rep['reject_counts'].items())} |",
         f"| Gaps / missing 5-min rows | {rep['gaps']} / {rep['missing_rows']} | left as gaps, not filled |",
         f"| Totalizer resets | {rep['flag_counts']['totalizer_reset']} | negative diff; interval = post-reset value |",
         f"| Heat balance UNVERIFIED (bypass > 0) | {rep['flag_counts']['heat_balance_unverified']} rows | eta and SFC set UNAVAILABLE |",
         f"| Volumetric fuel rows | {rep['flag_counts']['volumetric_fuel']} | fuel uncertainty 10 % instead of 2 % |",
         f"| Command-vs-feedback mismatches | {rep['flag_counts']['cmd_feedback_mismatch']} | fan power vs cube law, 25 % tolerance |",
         f"| Unit-suspect rows | {q_unit} | draft > 500 Pa or reported heat off by a Mkcal/kcal factor |",
         f"| Estimated fuel-to-heat lag | {rep['lag_steps']} steps ({rep['lag_steps'] * 5} min) | 3-step-difference correlation on first {cfg['lag']['train_frac']:.0%} of rows; trailing alignment only |", "",
         "## Reasons for rejection (priority order)", "SCHEMA_INVALID (here: negative O2 readings below the analyser range, which are physically impossible) > DUPLICATE_TIMESTAMP > FROZEN_SENSOR (>2 identical samples) > FUEL_IMPLAUSIBLE (vs feeder speed) > HEAT_IMPLAUSIBLE (> 13.75 MW or dT outside 5-40 K) > PROPERTY_OOR (temperature outside the HTF table).", "",
         "## Engineering status counts (SFC / eta / Q_out)",
         f"- status_SFC: {rep['status_SFC']}", f"- status_eta: {rep['status_eta']}", f"- status_Q_out: {rep['status_Q_out']}", f"- LHV basis: {rep['lhv_basis']}", "",
         "## Eligibility (SPEC C7 layers 1-2, 12-step stable window)",
         f"- Counts: {rep['eligibility']}", f"- Top NO_ADVICE reasons: {', '.join(f'{k} {v}' for k, v in reasons.head(8).items())}",
         f"- Agreement with the generator's own labels at the ELIGIBLE/DIAGNOSTIC/NO_ADVICE level: {agree:.1f} % (not independent evidence: generator and cleaner were written together and share the same rules and property table)", "",
         "## Uncertainty (standard, SPEC C3: flow 2 %, dT 0.5 K, fuel 2 % belt / 10 % volumetric)",
         f"- Median Q_out relative uncertainty in operation: {unc_q:.1f} %.", f"- Median SFC relative uncertainty: {unc_s_b:.1f} % (weigh belt) vs {unc_s_v:.1f} % (volumetric).",
         f"- Median eta 95 % half-width: {wid_k:.1f} points with a lab LHV vs {wid_u:.1f} points when only a lot-band interval exists (no point eta is reported then).", "",
         "## Reconciliation",
         f"- Recomputed vs reported Q_out: median relative difference {rel_q.median() * 100:.2f} % (n={len(rel_q):,}); expected ~0 because the generator uses the same table, so this checks plumbing, not plant agreement.",
         f"- Daily fuel from rate integration vs totalizer increments (full days, n={len(full)}): median difference {rel_fuel.median() * 100:.2f} %, max {rel_fuel.max() * 100:.2f} %.",
         f"- Safety signals left unfilled: draft_pa NaN {n_nan_safety['draft_pa']}, interlock_active NaN {n_nan_safety['interlock_active']}.", "",
         "## Injected-fault detection (evaluation only; labels never enter the clean file)",
         "| Fault | Injected rows | Rejected | Flagged not ELIGIBLE | Still ELIGIBLE (missed) |", "|---|---|---|---|---|"]
    for _, r in det.iterrows():
        L.append(f"| {r.fault} | {r.injected_rows} | {r.rejected} | {r.flagged_not_eligible} | {r.still_ELIGIBLE} |")
    miss = det.set_index("fault")["still_ELIGIBLE"]
    L += ["", f"Total still ELIGIBLE inside injected windows: {int(miss.sum())} of {int(det.injected_rows.sum())} rows.",
          "", "## Known limits", "- Detection rules and thresholds are normalized synthetic values (config/cleaning_engineering.yaml), not site limits.",
          "- A frozen sensor is only detected after 3 identical samples; the first genuine-looking sample is flagged with the run.",
          "- Gaps are not filled, so the 60-min windows after a gap restart; eligible coverage falls accordingly.",
          "- Figures: reports/figs/p2_data_quality.png, p2_uncertainty_day.png."]
    (ROOT / "reports" / "data_quality.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("data_quality.md written; missed injected rows:", int(miss.sum()))
    return det


def figs(d, rep, reasons):
    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    rc = rep["reject_counts"]
    ax[0].barh(list(rc), list(rc.values()), color=C["b"])
    ax[0].set_title(f"Rejected rows by primary reason (n={rep['n_rejected']})", fontsize=9)
    ax[1].barh(list(reasons.index[:8][::-1]), list(reasons.values[:8][::-1]), color=C["a"])
    ax[1].set_title("Top NO_ADVICE reason codes (rows)", fontsize=9)
    t = pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    day = d.assign(day=t.dt.date).groupby("day")["eligibility"].apply(lambda s: s.str.startswith("ELIGIBLE").mean())
    ax[2].plot(pd.to_datetime(day.index), day.values * 100, color=C["a"])
    ax[2].set_ylabel("% rows ELIGIBLE per day"); ax[2].set_title("Daily eligible share", fontsize=9)
    for a in ax: a.grid(alpha=0.25)
    fig.suptitle(f"Data quality summary | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p2_data_quality.png", dpi=130); plt.close(fig)

    t = pd.to_datetime(d["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    n = d[~d["scenario_id"].fillna("").str.startswith("FAULT_")]
    days = n.assign(day=t[n.index].dt.date).groupby("day").apply(lambda g: (g["status_SFC"] == "CALCULATED").mean() + (g["lhv_known"] == 0).mean() * 0.5, include_groups=False)
    day = days.sort_values().index[len(days) // 2]
    g = n[t[n.index].dt.date == day]
    x = pd.to_datetime(g["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    ax[0].plot(x, g["Q_out_MW"], color=C["a"]); ax[0].fill_between(x, g["Q_out_lo_MW"], g["Q_out_hi_MW"], color=C["a"], alpha=0.25)
    ax[0].set_ylabel("Q_out (MW), 95 % band")
    ax[1].plot(x, g["SFC_kg_GJ"], color=C["b"], lw=1); ax[1].fill_between(x, g["SFC_lo_kg_GJ"], g["SFC_hi_kg_GJ"], color=C["b"], alpha=0.25)
    ax[1].plot(x, g["SFC_win_kg_GJ"], color="k", lw=1.5, label="60-min window SFC"); ax[1].set_ylabel("SFC (kg/GJ), 95 % band"); ax[1].set_ylim(60, 170); ax[1].legend(fontsize=8)
    ax[2].plot(x, g["eta_pct"], color=C["g"], label="eta (lab LHV)"); ax[2].fill_between(x, g["eta_lo_pct"], g["eta_hi_pct"], color=C["c"], alpha=0.3, label="95 % interval (lab-LHV band or lot-band)")
    ax[2].set_ylim(30, 100); ax[2].set_ylabel("eta (%)"); ax[2].legend(fontsize=8)
    cols = {"CALCULATED": C["a"], "ESTIMATED": C["c"], "UNAVAILABLE": C["b"]}
    for a in ax: a.grid(alpha=0.25)
    for s, c in cols.items():
        m = g["status_SFC"] == s
        ax[1].scatter(x[m], np.full(m.sum(), 62), color=c, s=8, label=f"status {s}")
    ax[1].legend(fontsize=7, ncol=4, loc="upper right")
    fig.suptitle(f"Engineering values with uncertainty and status, {day} | {TAG}", fontsize=10); fig.tight_layout()
    fig.savefig(FIG / "p2_uncertainty_day.png", dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    run()


if __name__ == "__main__":
    main()
