"""Energy baseline: OLS SFC ~ load + load^2 + moisture on eligible steady windows (95 % CI by lot-cluster bootstrap)
and a rule comparator (alert if window SFC > trailing 7-day P75 in the same load band).
Learned from the data, NOT the 85 % design value. All numbers SYNTHETIC. Run: python -m src.baseline
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.cleaning import load_cfg

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figs"
LOAD_REF, MOIST_REF = 8.5, 17.0
NAMES = ["intercept", "load (MW, centred 8.5)", "load^2", "moisture (%wb, centred 17)"]
TAG = "SYNTHETIC - NOT FOR PLANT OPERATION"
C = {"a": "#1f6f8b", "b": "#d1495b", "c": "#edae49", "g": "#66737d"}


def design(load, moist):
    l = np.asarray(load, float) - LOAD_REF
    return np.column_stack([np.ones_like(l), l, l ** 2, np.asarray(moist, float) - MOIST_REF])


def ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def cluster_bootstrap(X, y, clusters, n_boot, seed):
    """95 % CI by resampling lots (rows within a lot are strongly autocorrelated)."""
    rng = np.random.default_rng(seed)
    ids = np.unique(clusters)
    groups = {c: np.where(clusters == c)[0] for c in ids}
    out = np.empty((n_boot, X.shape[1]))
    for b in range(n_boot):
        pick = rng.choice(ids, len(ids), replace=True)
        idx = np.concatenate([groups[c] for c in pick])
        out[b] = ols(X[idx], y[idx])
    return np.percentile(out, [2.5, 97.5], axis=0)


def load_data():
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv")
    ev = pd.read_csv(ROOT / "data" / "clean" / "eval_labels.csv")
    d = d.merge(ev, on="timestamp_local", how="left")
    d["t"] = pd.to_datetime(d["timestamp_local"], utc=True)
    return d


def baseline_rows(d):
    """Eligible stable windows with a calculated SFC and a lab moisture (no imputation)."""
    ok = d["eligibility"].str.startswith(("ELIGIBLE", "DIAGNOSTIC_ONLY")) & (d["status_SFC"] == "CALCULATED")
    ok &= d["SFC_win_kg_GJ"].notna() & d["Q_out_win_MW"].notna() & d["fuel_moisture_wb_pct"].notna()
    return ok


def rule_alerts(d, rows, cfg):
    """Alert if SFC_win > trailing P75 of earlier eligible windows in the same load band (strictly earlier rows)."""
    b = cfg["baseline"]
    x = d[rows].copy()
    x["band"] = np.floor(x["Q_out_win_MW"] / b["band_mw"]).astype(int)
    x["p75"] = np.nan
    for _, g in x.groupby("band"):
        s = g.set_index("t")["SFC_win_kg_GJ"]
        q = s.rolling(f"{b['trailing_days']}D", closed="left", min_periods=b["min_obs"]).quantile(b["quantile"])
        x.loc[g.index, "p75"] = q.to_numpy()
    x["rule_alert"] = (x["SFC_win_kg_GJ"] > x["p75"]).where(x["p75"].notna())
    return x


def prf(alert, label):
    a, l = alert.astype(bool), label.astype(bool)
    tp, fp, fn = int((a & l).sum()), int((a & ~l).sum()), int((~a & l).sum())
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return dict(alerts=int(a.sum()), tp=tp, fp=fp, fn=fn, precision=p, recall=r, alert_rate=float(a.mean()), base_rate=float(l.mean()))


def run(cfg=None):
    cfg = cfg or load_cfg()
    b = cfg["baseline"]
    d = load_data()
    rows = baseline_rows(d)
    x = rule_alerts(d, rows, cfg)
    x["label"] = x["best_action_eta_gain_pp"] >= b["avoidable_gain_pp"]
    # chronological, lot-aware split
    cut = int(len(x) * b["train_frac"])
    cut_lot = x["fuel_lot"].iloc[cut]
    first_after = x.index[x["fuel_lot"] == cut_lot][-1] + 1
    tr, te = x[x.index < first_after], x[x.index >= first_after]
    Xtr, ytr = design(tr["Q_out_win_MW"], tr["fuel_moisture_wb_pct"]), tr["SFC_win_kg_GJ"].to_numpy()
    Xte, yte = design(te["Q_out_win_MW"], te["fuel_moisture_wb_pct"]), te["SFC_win_kg_GJ"].to_numpy()
    beta = ols(Xtr, ytr)
    ci = cluster_bootstrap(Xtr, ytr, tr["fuel_lot"].to_numpy(), b["n_boot"], b["seed"])
    pred_tr, pred_te = Xtr @ beta, Xte @ beta
    r2 = 1 - ((ytr - pred_tr) ** 2).sum() / ((ytr - ytr.mean()) ** 2).sum()
    res = dict(n_rows=int(rows.sum()), n_train=len(tr), n_test=len(te), n_lots_train=int(tr["fuel_lot"].nunique()),
               beta=beta, ci=ci, r2=float(r2), mae_train=float(np.abs(ytr - pred_tr).mean()), mae_test=float(np.abs(yte - pred_te).mean()),
               mae_test_mean_model=float(np.abs(yte - ytr.mean()).mean()),
               mape_test=float((np.abs(yte - pred_te) / yte).mean() * 100), resid_sd=float(np.std(ytr - pred_tr)))
    # alerts on the test period
    thr = np.percentile(ytr - pred_tr, 75)
    te = te.assign(pred=pred_te, resid=yte - pred_te)
    te["ols_alert"] = te["resid"] > thr
    t2 = te[te["rule_alert"].notna()]
    res["rule"] = prf(t2["rule_alert"].astype(bool), t2["label"])
    res["ols_monitor"] = prf(te["ols_alert"], te["label"])
    res["ols_monitor_same_rows"] = prf(t2["ols_alert"], t2["label"])
    res["n_rule_scored"] = len(t2)
    res["gain_by_alert"] = {k: float(v) for k, v in t2.groupby("rule_alert")["best_action_eta_gain_pp"].mean().items()}
    res["corr_resid_gain"] = float(te["resid"].corr(te["best_action_eta_gain_pp"]))
    figs(x, tr, te, beta, res)
    write_md(res, cfg)
    print(f"baseline: train {len(tr)} / test {len(te)} windows; MAE test {res['mae_test']:.2f} kg/GJ (mean-model {res['mae_test_mean_model']:.2f}); R2 {r2:.3f}")
    print("coefficients (95% lot-cluster bootstrap CI):")
    for n, bb, lo, hi in zip(NAMES, beta, ci[0], ci[1]):
        print(f"  {n:28s} {bb:9.3f}  [{lo:9.3f}, {hi:9.3f}]")
    print("rule comparator (test):", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res["rule"].items()})
    return res


def figs(x, tr, te, beta, res):
    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    sc = ax.scatter(x["Q_out_win_MW"], x["SFC_win_kg_GJ"], c=x["fuel_moisture_wb_pct"], s=6, cmap="viridis", alpha=0.6)
    L = np.linspace(6, 11, 60)
    for m, ls in ((10, "--"), (17, "-"), (26, ":")):
        ax.plot(L, design(L, np.full_like(L, m)) @ beta, color=C["b"], ls=ls, lw=2, label=f"OLS at moisture {m} %wb")
    ax.set_xlabel("Q_out, trailing 60-min mean (MW)")
    ax.set_ylabel("SFC, 60-min window (kg fuel / GJ useful heat)")
    ax.legend(fontsize=8)
    fig.colorbar(sc, label="lab moisture (%wb)")
    ax.set_title(f"Baseline SFC vs load, eligible windows (n={len(x)}) | {TAG}", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(FIG / "p2_sfc_vs_load.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ax[0].scatter(te["pred"], te["SFC_win_kg_GJ"], s=6, alpha=0.5, color=C["a"])
    lim = [te["pred"].min(), te["pred"].max()]
    ax[0].plot(lim, lim, color=C["b"])
    ax[0].set_xlabel("OLS prediction (kg/GJ)"); ax[0].set_ylabel("actual window SFC (kg/GJ)")
    ax[0].set_title(f"Held-out windows (later lots): MAE {res['mae_test']:.2f} vs mean-model {res['mae_test_mean_model']:.2f} kg/GJ", fontsize=9)
    ax[1].plot(te["t"], te["resid"], lw=0.6, color=C["g"])
    ax[1].axhline(0, color=C["b"], lw=1)
    ax[1].set_ylabel("residual (kg/GJ)"); ax[1].set_title("Held-out residual over time (excess SFC > 0)", fontsize=9)
    for a in ax: a.grid(alpha=0.25)
    fig.suptitle(TAG, fontsize=9); fig.tight_layout(); fig.savefig(FIG / "p2_baseline_holdout.png", dpi=130); plt.close(fig)

    t2 = te[te["rule_alert"].notna()]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for k, col, lab in ((False, C["a"], "no rule alert"), (True, C["b"], "rule alert")):
        ax[0].hist(t2.loc[t2["rule_alert"].astype(bool) == k, "best_action_eta_gain_pp"], bins=30, alpha=0.6, color=col, label=lab, density=True)
    ax[0].axvline(1.0, color="k", ls="--", lw=1)
    ax[0].set_xlabel("generator best-action eta gain (% points) - hidden truth"); ax[0].set_ylabel("density"); ax[0].legend(fontsize=8)
    ax[0].set_title("Do rule alerts coincide with avoidable loss?", fontsize=9)
    r, o = res["rule"], res["ols_monitor_same_rows"]
    xs = np.arange(2)
    ax[1].bar(xs - 0.18, [r["precision"], r["recall"]], 0.36, color=C["b"], label="rule (7-day P75 by band)")
    ax[1].bar(xs + 0.18, [o["precision"], o["recall"]], 0.36, color=C["a"], label="OLS residual > train P75")
    ax[1].axhline(r["base_rate"], color="k", ls=":", lw=1, label=f"base rate of avoidable windows {r['base_rate']:.2f}")
    ax[1].set_xticks(xs); ax[1].set_xticklabels(["precision", "recall"]); ax[1].legend(fontsize=8)
    ax[1].set_title("Detection of avoidable SFC (held-out windows)", fontsize=9)
    for a in ax: a.grid(alpha=0.25)
    fig.suptitle(TAG, fontsize=9); fig.tight_layout(); fig.savefig(FIG / "p2_rule_comparator.png", dpi=130); plt.close(fig)


def write_md(r, cfg):
    b = cfg["baseline"]
    L = ["# Energy Baseline (SYNTHETIC) - Heater C", "",
         "Baseline learned from cleaned synthetic data. It is **not** the 85 % design value and not a plant claim; every number is SYNTHETIC. Built by `python -m src.baseline` from data/clean/clean_heater_c.csv.", "",
         "## Definitions",
         "- Window SFC = trailing 12-step (60 min) sum of aligned fuel kg / (3.6 x sum of Q_out MW); kg fuel per GJ useful heat (SPEC C3).",
         "- Eligible stable row = SPEC C7 layers 1-2 give ELIGIBLE or DIAGNOSTIC_ONLY (CO is not needed for SFC), status_SFC = CALCULATED (weigh belt, STEADY, no bypass), lab moisture present. No imputation.",
         "- Load = trailing 60-min mean Q_out (MW). Model: SFC = b0 + b1 (load-8.5) + b2 (load-8.5)^2 + b3 (moisture-17).",
         f"- Split: chronological and lot-aware ({b['train_frac']:.0%} of eligible windows to a lot boundary). CIs: {b['n_boot']} lot-cluster bootstrap resamples (rows inside a lot are autocorrelated, so naive OLS CIs would be too narrow).", "",
         "## Coefficients (training windows)", f"n = {r['n_train']} windows from {r['n_lots_train']} lots; test n = {r['n_test']}.", "",
         "| Term | Estimate (kg/GJ per unit) | 95 % CI | Method |", "|---|---|---|---|"]
    for n, bb, lo, hi in zip(NAMES, r["beta"], r["ci"][0], r["ci"][1]):
        L.append(f"| {n} | {bb:.3f} | [{lo:.3f}, {hi:.3f}] | OLS, lot-cluster bootstrap |")
    L += ["", "## Accuracy on held-out later lots", "| Measure | Result | Method |", "|---|---|---|",
          f"| R2 (train) | {r['r2']:.3f} | OLS |",
          f"| MAE train / test | {r['mae_train']:.2f} / {r['mae_test']:.2f} kg/GJ | mean absolute error |",
          f"| MAE of train-mean model (test) | {r['mae_test_mean_model']:.2f} kg/GJ | no-skill reference |",
          f"| MAPE test | {r['mape_test']:.1f} % | |", "",
          "## Rule comparator (monitoring alternative)",
          f"Alert if window SFC > trailing {b['trailing_days']}-day P{int(b['quantile'] * 100)} of earlier eligible windows in the same {b['band_mw']:.0f} MW load band (needs >= {b['min_obs']} earlier windows).",
          f"Truth label (generator illustration, held-out only): avoidable = best feasible action raises eta by >= {b['avoidable_gain_pp']} percentage point. Scored on {r['n_rule_scored']} held-out windows.", "",
          "| Detector | Alerts | Precision | Recall | Alert rate | Base rate |", "|---|---|---|---|---|---|"]
    for name, k in (("Rule P75 by load band", "rule"), ("OLS residual > train P75 (same rows)", "ols_monitor_same_rows")):
        v = r[k]
        L.append(f"| {name} | {v['alerts']} | {v['precision']:.2f} | {v['recall']:.2f} | {v['alert_rate']:.2f} | {v['base_rate']:.2f} |")
    L += ["", f"Mean hidden gain when rule alerts vs not: {r['gain_by_alert']}. Correlation of OLS residual with hidden gain (test): {r['corr_resid_gain']:.2f}.", "",
          "## How to read this", "- The Phase 3 model must beat these two detectors on the same held-out windows (and MAE >= 10 % below the OLS) or the simple option is chosen.",
          "- The hidden-gain label comes from the generator; precision/recall show method behaviour under known ground truth, not plant performance.",
          "- Figures: reports/figs/p2_sfc_vs_load.png, p2_baseline_holdout.png, p2_rule_comparator.png.", "",
          "## Limits", "- Only windows with a lab-assayed lot, weigh-belt fuel and no bypass qualify, so coverage is a minority of operating time.",
          "- Fuel-quality and operator effects are confounded in observational data; synthetic exploration (15 % of decisions) makes action effects identifiable only here."]
    (ROOT / "reports" / "energy_baseline.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    run()


if __name__ == "__main__":
    main()
