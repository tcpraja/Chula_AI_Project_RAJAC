"""CP17: M&V power analysis on synthetic data. SYNTHETIC - NOT FOR PLANT OPERATION.

A/A design: no intervention exists in the data, so any baseline-vs-trial difference is noise. For window lengths w (days) we slide
adjacent baseline/trial pairs, estimate the normalised-SFC effect with the same method as src.mv_report (matched load x moisture
cells, lot-cluster bootstrap 90 % CI) and record the CI half-width. Minimum detectable effect at 80 % power, two-sided alpha 0.10:
MDE80 = HW90 x (1.645 + 0.842) / 1.645. Half-width is fitted as HW = a * w^b (log-log, OWN-ESTIMATE) and extrapolated to the
duration where MDE80 reaches a target effect. Extrapolation beyond the 64 days of data is labelled as such.
Writes reports/mv/mv_power.csv, reports/mv/mv_power.json and reports/mv/mv_power.md.
Run: python -m src.mv_power [--boot 200]
"""
import argparse
import json

import numpy as np
import pandas as pd

from src import mv_report as mv

ROOT = mv.ROOT
OUT = mv.OUT
WINDOWS = (7, 10, 14, 21, 28)
K80 = (1.645 + 0.842) / 1.645
TARGETS = {"generator_illustration_0.24pct": 0.24, "half_of_it_0.12pct": 0.12, "one_pct": 1.0}


def run(n_boot=200):
    d = mv.prepare(pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv"))
    t0, t1 = d["t_local"].min().normalize(), d["t_local"].max()
    rows = []
    for w in WINDOWS:
        s = t0
        while s + pd.Timedelta(days=2 * w) <= t1 + pd.Timedelta(hours=1):
            bm = (d["t_local"] >= s) & (d["t_local"] < s + pd.Timedelta(days=w))
            tm = (d["t_local"] >= s + pd.Timedelta(days=w)) & (d["t_local"] < s + pd.Timedelta(days=2 * w))
            r = mv.estimate(d, bm, tm, n_boot=n_boot)
            if r["ok"] and np.isfinite(r["ci90_pct"][0]):
                rows.append({"window_days": w, "start": str(s.date()), "aa_effect_pct": r["delta_pct"], "ci90_lo_pct": r["ci90_pct"][0],
                             "ci90_hi_pct": r["ci90_pct"][1], "hw90_pct": (r["ci90_pct"][1] - r["ci90_pct"][0]) / 2,
                             "false_saving": bool(r["saving_reported"]), "n_lots_base": r["n_lots_base"], "n_lots_trial": r["n_lots_trial"]})
            s += pd.Timedelta(days=7)
    T = pd.DataFrame(rows)
    T["mde80_pct"] = T["hw90_pct"] * K80
    T["provenance"] = "SYNTHETIC A/A (no intervention); OWN-ESTIMATE method"
    OUT.mkdir(parents=True, exist_ok=True)
    T.round(4).to_csv(OUT / "mv_power.csv", index=False)
    g = T.groupby("window_days").agg(pairs=("hw90_pct", "size"), hw90_pct=("hw90_pct", "median"), mde80_pct=("mde80_pct", "median"),
                                     aa_sd_pct=("aa_effect_pct", "std"), false_saving_share=("false_saving", "mean")).reset_index()
    b, loga = np.polyfit(np.log(g["window_days"]), np.log(g["hw90_pct"]), 1)
    need = {k: float(np.exp((np.log(v / K80) - loga) / b)) if b < 0 else float("inf") for k, v in TARGETS.items()}
    res = {"windows": g.round(4).to_dict("records"), "fit_hw90_pct": {"a": float(np.exp(loga)), "b": float(b)},
           "k80": K80, "required_days_per_window": {k: round(v, 1) for k, v in need.items()},
           "data_days": float((t1 - t0).total_seconds() / 86400), "six_week_trial_mde80_pct": float(np.exp(loga) * 42 ** b * K80),
           "provenance": "SYNTHETIC A/A; extrapolated beyond the data where required_days > data_days/2 (OWN-ESTIMATE)"}
    (OUT / "mv_power.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    L = ["# M&V power analysis (CP17) - SYNTHETIC A/A, NOT FOR PLANT OPERATION", "",
         "Adjacent baseline/trial windows with no intervention. Same estimator as the M&V report. MDE80 = 90 % half-width x 1.51.", "",
         "| window (days each) | pairs | median 90 % half-width | MDE at 80 % power | A/A effect SD | A/A windows wrongly showing a saving |", "|---|---|---|---|---|---|"]
    for r in g.itertuples(index=False):
        L.append(f"| {r.window_days} | {r.pairs} | ±{r.hw90_pct:.2f} % | {r.mde80_pct:.2f} % | {r.aa_sd_pct:.2f} % | {100*r.false_saving_share:.0f} % |")
    L += ["", f"Fit: half-width = {np.exp(loga):.2f} x days^{b:.2f}. Six-week windows (42 days each): MDE80 ≈ {res['six_week_trial_mde80_pct']:.2f} %.",
          f"Days per window needed for MDE80 = 0.24 %: {need['generator_illustration_0.24pct']:.0f}; for 0.12 %: {need['half_of_it_0.12pct']:.0f}; for 1 %: {need['one_pct']:.0f}.",
          f"The data cover {res['data_days']:.0f} days, so anything above {res['data_days']/2:.0f} days per window is an extrapolation.",
          "Conclusion: a fuel saving of the size the generator illustrates cannot be confirmed by a short trial; the pilot can only test "
          "safety, adoption and data quality, plus detect a large (≥ MDE) change."]
    (OUT / "mv_power.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot", type=int, default=200)
    run(ap.parse_args().boot)
