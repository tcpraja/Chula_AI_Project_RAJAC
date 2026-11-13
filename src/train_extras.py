"""Robustness extras requested by the critic review: noise floor, action-sensitivity check, seed and tau sensitivity.
Writes reports/model_robustness.md. Run: python -m src.train_extras  (also part of pipeline --stage train)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import features as ft
from src import generate_synthetic as gen
from src import train
from src.cleaning import load_cfg

ROOT = Path(__file__).resolve().parents[1]


def quick_fit(d, cfg, tau=ft.BED_TAU_MIN, hp=None):
    """Test MAE (kg/h) of P, P2, B, L, C0 on one dataset using the same split rules."""
    seed = cfg["model"]["seed"]
    F = train.assign_split(ft.build(d, tau), cfg)
    E = F["eligible"] & F["y_ok"]
    tr, te = F[E & (F.split == "train")], F[E & (F.split == "test")]
    cB, cL = ["Q_out_MW", "bed_moisture_wb_pct"], ft.FEATURES_L
    okB, okL = tr[cB].notna().all(axis=1), tr[cL].notna().all(axis=1)
    pB = train.lin_predict(te, cB, train.ols_fit(tr.loc[okB, cB].to_numpy(), tr.loc[okB, "y"].to_numpy()))
    pL = train.lin_predict(te, cL, train.ols_fit(tr.loc[okL, cL].to_numpy(), tr.loc[okL, "y"].to_numpy()))
    m0 = train.hgb(hp or cfg["model"]["grid"][0], seed).fit(tr[ft.FEATURES_C0], tr["y"])
    y = te["y"].to_numpy()
    out = {"P": train.mae(te["fuel_lag1"].to_numpy(float), y), "P2": train.mae((te["feeder_speed_pct"] * train.CAP / 100).to_numpy(float), y),
           "B": train.mae(pB, y), "L": train.mae(pL, y), "C0": train.mae(m0.predict(te[ft.FEATURES_C0]), y)}
    out["n_test"] = len(te)
    return out


def noise_floor(res):
    """MAE between the measured target and the mean of the TRUE next three feeds: the best any forecaster could do
    against this noisy target even with perfect foresight of the true feed."""
    tr_ = pd.read_csv(ROOT / "data" / "raw_synthetic" / "synthetic_truth.csv", usecols=["timestamp_local", "fuel_feed_true_kgh"])
    s = pd.Series(tr_["fuel_feed_true_kgh"].to_numpy(), index=pd.to_datetime(tr_["timestamp_local"]))
    fut = pd.concat([s.shift(-k, freq="5min") for k in (1, 2, 3)], axis=1).mean(axis=1, skipna=False)
    te = res["te"]
    key = pd.to_datetime(te["timestamp_local"].str[:19])
    y_true = fut.reindex(key).to_numpy()
    y = te["y"].to_numpy()
    ok = ~np.isnan(y_true)
    return float(np.abs(y[ok] - y_true[ok]).mean()), int(ok.sum())


def action_sensitivity(res, cfg):
    """Does model C respond to FD/grate changes the way the generator's efficiency model says fuel should?"""
    te = res["te"]
    truth = pd.read_csv(ROOT / "data" / "raw_synthetic" / "synthetic_truth.csv")
    main = pd.read_csv(ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv", usecols=["timestamp_local", "ambient_temp_C", "fan_derated", "sootblow"])
    t = truth.merge(main, on="timestamp_local")
    t["k"] = t["timestamp_local"].str[:19]
    x = te.assign(k=te["timestamp_local"].str[:19]).merge(t, on="k", how="inner", suffixes=("", "_t"))
    P = gen.load_cfg("main")
    out = {}
    fdst = P["combustion"]["fd_stoich_per_mw"] * x["Q_in_true_MW"] + 1e-9
    for name, dfd, dg in (("FD +5 points", 5.0, 0.0), ("FD -5 points", -5.0, 0.0), ("grate +5 points", 0.0, 5.0)):
        fd0 = x["FD_command_pct"].to_numpy()
        lam1 = np.maximum((fd0 + dfd) / fdst * (1.0), 1.0005)
        o2_1 = np.minimum(21 * (1 - 1 / lam1), 20.9)
        g1 = x["grate_command_pct"] + dg
        e0 = gen.eta_fn(P, x["moisture_true_wb_pct"], x["fouling_index"], x["O2_true_pct_dry"], x["O2_opt_true_pct"], x["grate_command_pct"],
                        x["grate_opt_true_pct"], x["fan_derated"].to_numpy(float), x["sootblow"].to_numpy(float), x["ambient_temp_C"])
        e1 = gen.eta_fn(P, x["moisture_true_wb_pct"], x["fouling_index"], o2_1, x["O2_opt_true_pct"], g1, x["grate_opt_true_pct"],
                        x["fan_derated"].to_numpy(float), x["sootblow"].to_numpy(float), x["ambient_temp_C"])
        true_d = (x["y"] * (e0 / e1 - 1.0)).to_numpy()
        Xm = x[ft.FEATURES].copy()
        Xm["FD_command_pct"] = Xm["FD_command_pct"] + dfd
        Xm["grate_command_pct"] = Xm["grate_command_pct"] + dg
        d_model = res["mC"].predict(Xm) - res["mC"].predict(x[ft.FEATURES])
        out[name] = (float(np.mean(true_d)), float(np.mean(d_model)), float(np.corrcoef(true_d, d_model)[0, 1]) if np.std(d_model) > 0 else float("nan"))
    return out, len(x)


def run(res=None):
    cfg = load_cfg()
    res = res or train.run(write=False)
    floor, nfl = noise_floor(res)
    act, nact = action_sensitivity(res, cfg)
    # tau sensitivity (feature constant 15 min vs other bed time constants)
    tau_rows = {t: quick_fit(res["d"], cfg, tau=t, hp=res["hp"]) for t in (5, 15, 30, 60)}
    # seed robustness: regenerate, clean and fit on new generator realizations
    from src.pipeline import clean_frame
    seed_rows = {}
    for sd in (43, 44, 45, 46):
        raw = gen.generate(sd, 60)["main"]
        full, *_ = clean_frame(raw, cfg)
        full["t"] = pd.to_datetime(full["timestamp_local"], utc=True)
        seed_rows[sd] = quick_fit(full.sort_values("t").reset_index(drop=True), cfg, hp=res["hp"])
    seed_rows[42] = {k: res["tbl"][k]["MAE"] for k in ("P", "P2", "B", "L", "C0")} | {"n_test": len(res["te"])}
    tbl = res["tbl"]
    L = ["# Model Robustness Checks (SYNTHETIC)", "", "Created after the critic review (reports/ai_critique_log.md): noise floor (K12), action sensitivity (K11), bed time-constant sensitivity (K5), seed spread (K18).", "",
         "## 1 Noise floor", f"Mean absolute difference between the measured next-15-min fuel and the mean of the TRUE next three feeds, on {nfl:,} eligible test rows: **{floor:.1f} kg/h**. "
         f"No forecaster can beat that against this target. L's test MAE is {tbl['L']['MAE']:.1f} kg/h ({tbl['L']['MAE'] / floor:.1f}x the floor); P2 is {tbl['P2']['MAE']:.1f} kg/h ({tbl['P2']['MAE'] / floor:.1f}x).", "",
         "## 2 Can the forecaster rank operator actions? (model C, settings changed in the inputs)",
         f"True effect from the generator's efficiency model (fuel x (eta_before/eta_after − 1)) vs model C's predicted change, mean over {nact:,} eligible test rows (kg/h):", "",
         "| Action | True mean change | C predicted mean change | Row-wise correlation |", "|---|---|---|---|"]
    for k, (a, b, c) in act.items():
        L.append(f"| {k} | {a:+.1f} | {b:+.1f} | {c:.2f} |")
    L += ["", "Reading: when the predicted change is near zero or uncorrelated with the true change, the forecaster has not learned an action effect. Observational settings are confounded with operator habit, so Phase 4 must rank actions with its own effect model or the simulator.", "",
          "## 3 Bed time-constant sensitivity (feature uses tau minutes; generator draws 10–20 min per lot)", "| tau (min) | P2 | B | L | C0 |", "|---|---|---|---|---|"]
    for t, r in tau_rows.items():
        L.append(f"| {t} | {r['P2']:.2f} | {r['B']:.2f} | {r['L']:.2f} | {r['C0']:.2f} |")
    L += ["", "## 4 Seed spread (five generator realizations, same split rules, C0 with the chosen hyper-parameters; test MAE kg/h)", "| Seed | n test | P | P2 | B | L | C0 | L vs P2 | C0 vs L |", "|---|---|---|---|---|---|---|---|---|"]
    for sd in sorted(seed_rows):
        r = seed_rows[sd]
        L.append(f"| {sd} | {r['n_test']} | {r['P']:.1f} | {r['P2']:.1f} | {r['B']:.1f} | {r['L']:.1f} | {r['C0']:.1f} | {(1 - r['L'] / r['P2']) * 100:+.1f} % | {(1 - r['C0'] / r['L']) * 100:+.1f} % |")
    l_gain = [(1 - r["L"] / r["P2"]) * 100 for r in seed_rows.values()]
    c_gain = [(1 - r["C0"] / r["L"]) * 100 for r in seed_rows.values()]
    worse = sum(g < 0 for g in c_gain)
    L += ["", f"L beats the current-feed reference P2 by {np.mean(l_gain):.1f} % on average (range {min(l_gain):.1f} to {max(l_gain):.1f} %). "
          f"C0 vs L (negative = C0 worse): mean {np.mean(c_gain):+.1f} % (range {min(c_gain):+.1f} to {max(c_gain):+.1f} %); C0 is worse than the linear model on {worse} of {len(c_gain)} seeds, so boosting adds no gain here.",
          "Seed 42 is the dataset used everywhere else; the other seeds are new draws of the same generator, not new plants."]
    (ROOT / "reports" / "model_robustness.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"noise floor {floor:.1f} kg/h; action check {({k: tuple(round(x, 2) for x in v) for k, v in act.items()})}; seeds L vs P2 {np.round(l_gain, 1)}")
    return dict(floor=floor, act=act, tau=tau_rows, seeds=seed_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    run()


if __name__ == "__main__":
    main()
