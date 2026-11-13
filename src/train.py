"""Train and compare the fuel-forecast models (SYNTHETIC) and select by the frozen rule plus dated amendments.

References: P (last fuel), P2 (current feeder feed = feeder_speed x capacity). Candidates: A physics, B linear (load+moisture),
L linear on the full non-settings feature set, C0 boosting without settings, C boosting. Ablations: C0 without feeder speed / lot / CO.
Run: python -m src.train   (also: python -m src.pipeline --stage train)
"""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from src import features as ft
from src.cleaning import load_cfg

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figs"
MODELS = ROOT / "models"
TAG = "SYNTHETIC - NOT FOR PLANT OPERATION"
NAMES = ["P", "P2", "A", "B", "L", "C0", "C"]
ABL = {"C0_nofeed": ft.FEATURES_NOFEED, "C0_nolot": ft.FEATURES_NOLOT, "C0_noco": ft.FEATURES_NOCO}
ALL = NAMES + list(ABL)
ORDER = ["A", "B", "L", "C0", "C"]  # complexity order for selection
REFS = ["P", "P2"]
COL = {"P": "#66737d", "P2": "#9aa5ad", "A": "#edae49", "B": "#d1495b", "L": "#a06cd5", "C0": "#6a994e", "C": "#1f6f8b",
       "C0_nofeed": "#bc6c25", "C0_nolot": "#ae2012", "C0_noco": "#0a9396"}
CAP = 5000.0  # feeder capacity kg/h at 100 % speed (config feeder_cap_kgh)


# ---------------------------------------------------------------- split
def assign_split(F, cfg):
    m = cfg["model"]
    ok = F["eligible"] & F["has_target"]
    cnt = F[ok].groupby("fuel_lot").size().reindex(F.drop_duplicates("fuel_lot")["fuel_lot"], fill_value=0)
    mid = (cnt.cumsum() - cnt / 2) / cnt.sum()
    s = pd.Series(np.where(mid < m["split"][0], "train", np.where(mid < m["split"][0] + m["split"][1], "val", "test")), index=cnt.index)
    # validation is split by lot into a tuning half (a) and a calibration/selection half (b)
    vc = cnt[s == "val"]
    vmid = (vc.cumsum() - vc / 2) / vc.sum()
    sub = pd.Series(np.where(vmid < 0.5, "val_a", "val_b"), index=vc.index)
    F = F.copy()
    F["split"] = F["fuel_lot"].map(s)
    F["val_part"] = F["fuel_lot"].map(sub)
    nxt = pd.Series(F.set_index("t")["split"].reindex(F["t"] + m["purge_steps"] * ft.STEP).to_numpy(), index=F.index)
    F["purged"] = nxt.notna() & (nxt != F["split"])
    F["y_ok"] = F["has_target"] & ~F["purged"]
    return F


# ---------------------------------------------------------------- models
def ols_fit(X, y):
    return np.linalg.lstsq(np.column_stack([np.ones(len(X)), X]), y, rcond=None)[0]


def lin_predict(F, cols, coef):
    X = F[cols]
    return np.where(X.notna().all(axis=1), coef[0] + X.fillna(0).to_numpy() @ coef[1:], np.nan)


def predict_A(F, eta_base):
    return (F["Q_out_MW"] * 3600.0 / (eta_base * F["bed_LHV_MJkg"])).to_numpy()


def hgb(hp, seed):
    d, lr, it, leaf = hp
    return HistGradientBoostingRegressor(loss="absolute_error", max_depth=d, learning_rate=lr, max_iter=it, min_samples_leaf=leaf,
                                         l2_regularization=1.0, early_stopping=False, random_state=seed)


def mae(a, b):
    m = ~(np.isnan(a) | np.isnan(b))
    return float(np.abs(a[m] - b[m]).mean()) if m.any() else float("nan")


# ---------------------------------------------------------------- metrics
def conformal_half(y, p, level):
    r = np.abs(np.asarray(y, float) - np.asarray(p, float))
    r = np.sort(r[~np.isnan(r)])
    return float(r[min(len(r), math.ceil((len(r) + 1) * level)) - 1])


def metrics(y, p, half, cfg, pB=None, lhv=None, lots=None):
    y, p = np.asarray(y, float), np.asarray(p, float)
    n_all, ok = len(y), ~np.isnan(p)
    if ok.sum() == 0:
        return dict(n=0, n_rows=n_all, pred_share=0.0)
    y, p = y[ok], p[ok]
    e = np.abs(y - p)
    big = y > cfg["model"]["mape_min_y_kgh"]
    out = dict(n=len(y), n_rows=n_all, pred_share=len(y) / n_all, MAE=e.mean(), MAPE=(e[big] / y[big]).mean() * 100 if big.any() else np.nan,
               RMSE=float(np.sqrt((e ** 2).mean())), P90=float(np.quantile(e, 0.9)),
               R2=1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum() if len(y) > 1 else np.nan,
               coverage=float((e <= half).mean()), halfwidth=half, n_stopped=int((~big).sum()))
    if lhv is not None:
        l = np.asarray(lhv, float)[ok]
        out["MAE_fuel_MW"] = float(np.nanmean(e * l / 3600.0)) if np.isfinite(l).any() else np.nan
    if lots is not None and len(y) >= 20:
        c = pd.Series(e <= half).groupby(np.asarray(lots)[ok]).mean()
        out["cov_lot_median"], out["cov_lot_p10"] = float(c.median()), float(c.quantile(0.1))
    if pB is not None:
        pb = np.asarray(pB, float)[ok]
        m = ~np.isnan(pb)
        out["pct_better_than_B"] = float((e[m] < np.abs(y[m] - pb[m])).mean() * 100) if m.any() else np.nan
    return out


def segments(F, cfg):
    mb, lb = cfg["model"]["moisture_bands"], cfg["model"]["load_bands"]
    mo, ld = F["bed_moisture_wb_pct"], F["load_MW"]
    fi = F["analysis_fault_injected"].fillna(0)
    elig = {f"moisture<{mb[0]}": mo < mb[0], f"moisture {mb[0]}-{mb[1]}": (mo >= mb[0]) & (mo <= mb[1]), f"moisture>{mb[1]}": mo > mb[1],
            f"load<{lb[0]}": ld < lb[0], f"load {lb[0]}-{lb[1]}": (ld >= lb[0]) & (ld < lb[1]), f"load>={lb[1]}": ld >= lb[1],
            "outside injected-fault window": fi == 0, "inside injected-fault window": fi == 1}
    ext = {"steady": F["operating_mode"] == "STEADY", "transient/other": F["operating_mode"] != "STEADY",
           "fan_derated=0": F["fan_derated"] == 0, "fan_derated=1": F["fan_derated"] == 1,
           "lhv_known=1": F["lhv_known"] == 1, "lhv_known=0": F["lhv_known"] == 0,
           "belt fuel": F["fuel_mass_basis"] == "WEIGH_BELT", "volumetric fuel": F["fuel_mass_basis"] == "VOLUMETRIC"}
    return elig, ext


def cluster_boot_mae(err, lots, n_boot, seed):
    rng = np.random.default_rng(seed)
    ok = ~np.isnan(err)
    err, lots = err[ok], np.asarray(lots)[ok]
    ids = np.unique(lots)
    idx = {l: np.where(lots == l)[0] for l in ids}
    out = np.empty(n_boot)
    for b in range(n_boot):
        out[b] = err[np.concatenate([idx[l] for l in rng.choice(ids, len(ids))])].mean()
    return np.percentile(out, [2.5, 97.5])


# ---------------------------------------------------------------- leakage self-checks
def leakage_checks(F, d, cfg, hp, seed=42):
    tr = F[(F.split == "train") & F.eligible & F.y_ok]
    te = F[(F.split == "test") & F.eligible & F.y_ok]
    rng = np.random.default_rng(seed)
    shuf = hgb(hp, seed).fit(tr[ft.FEATURES], rng.permutation(tr["y"].to_numpy()))
    mae_shuf = mae(shuf.predict(te[ft.FEATURES]), te["y"].to_numpy())
    mae_mean = mae(np.full(len(te), tr["y"].mean()), te["y"].to_numpy())
    r2 = lambda p: 1 - ((te["y"] - p) ** 2).sum() / ((te["y"] - te["y"].mean()) ** 2).sum()
    honest = r2(hgb(hp, seed).fit(tr[ft.FEATURES], tr["y"]).predict(te[ft.FEATURES]))
    mf = hgb(hp, seed).fit(tr[ft.FEATURES].assign(future=tr["y"].to_numpy()), tr["y"])
    r2_future = r2(mf.predict(te[ft.FEATURES].assign(future=te["y"].to_numpy())))
    try:
        ft.assert_no_forbidden(ft.FEATURES)
        forbidden_ok = True
    except ValueError:
        forbidden_ok = False
    cut = int(len(d) * 0.6)
    full = ft.build(d)[ft.FEATURES].iloc[:cut]
    trunc = ft.build(d.iloc[:cut].copy())[ft.FEATURES]
    trunc_ok = bool(np.allclose(full.to_numpy(float), trunc.to_numpy(float), equal_nan=True))
    return dict(shuffled_target_mae=mae_shuf, mean_model_mae=mae_mean, shuffled_has_no_skill=bool(mae_shuf >= 0.9 * mae_mean),
                honest_r2=float(honest), future_feature_r2=float(r2_future), future_feature_detected=bool(r2_future - honest >= 0.04),
                no_forbidden_columns=forbidden_ok, truncation_invariant=trunc_ok)


# ---------------------------------------------------------------- selection (frozen rule + amendments A1-A6)
def select(tbl, leak_ok, sel):
    safe = {m: bool(leak_ok and tbl[m]["coverage"] >= sel["coverage_min"] and tbl[m]["val_test_gap"] <= sel["gap_max"]
                    and tbl[m]["worst_seg_ratio"] <= sel["worst_seg_max"]) for m in ORDER}
    chosen = None
    for m in ORDER:
        if safe[m] and (chosen is None or tbl[m]["MAE_valb"] <= (1 - sel["margin"]) * tbl[chosen]["MAE_valb"]):
            chosen = m
    best_ref = min(REFS, key=lambda r: tbl[r]["MAE_valb"])
    beats = bool(chosen and tbl[chosen]["MAE_valb"] <= (1 - sel["persistence_margin"]) * tbl[best_ref]["MAE_valb"])
    beats_test = bool(chosen and tbl[chosen]["MAE"] <= (1 - sel["persistence_margin"]) * min(tbl[r]["MAE"] for r in REFS))
    return chosen, safe, beats, best_ref, beats_test


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- main run
def run(cfg=None, write=True):
    cfg = cfg or load_cfg()
    mc, seed = cfg["model"], cfg["model"]["seed"]
    clean_path = ROOT / "data" / "clean" / "clean_heater_c.csv"
    d = ft.load_clean(clean_path).sort_values("t").reset_index(drop=True)
    F = assign_split(ft.build(d), cfg)
    F["_eta"] = d["eta_pct"].to_numpy()
    ev = pd.read_csv(ROOT / "data" / "clean" / "eval_labels.csv")[["timestamp_local", "scenario_id", "is_fault_injected"]].rename(
        columns={"scenario_id": "analysis_scenario_id", "is_fault_injected": "analysis_fault_injected"})
    F = F.merge(ev, on="timestamp_local", how="left")
    ft.assert_no_forbidden(ft.FEATURES)
    E = F["eligible"] & F["y_ok"]
    tr = F[E & (F.split == "train")]
    va = F[E & (F.split == "val")]
    va_a, va_b = va[va.val_part == "val_a"], va[va.val_part == "val_b"]
    te = F[E & (F.split == "test")]
    ext_te = F[(F.split == "test") & F["y_ok"] & F["has_lag1"]]

    eta_base = float(np.nanmedian(tr["_eta"])) / 100.0
    cB = ["Q_out_MW", "bed_moisture_wb_pct"]
    okB = tr[cB].notna().all(axis=1)
    coefB = ols_fit(tr.loc[okB, cB].to_numpy(), tr.loc[okB, "y"].to_numpy())
    okL = tr[ft.FEATURES_L].notna().all(axis=1)
    coefL = ols_fit(tr.loc[okL, ft.FEATURES_L].to_numpy(), tr.loc[okL, "y"].to_numpy())
    best = None
    for hp in mc["grid"]:  # tuned on the first validation half only
        m = hgb(hp, seed).fit(tr[ft.FEATURES], tr["y"])
        v = mae(m.predict(va_a[ft.FEATURES]), va_a["y"].to_numpy())
        if best is None or v < best[0]:
            best = (v, hp, m)
    hp_best, mC = best[1], best[2]
    mods = {"C0": hgb(hp_best, seed).fit(tr[ft.FEATURES_C0], tr["y"])}
    for k, cols in ABL.items():
        mods[k] = hgb(hp_best, seed).fit(tr[cols], tr["y"])
    feat_of = {"C": ft.FEATURES, "C0": ft.FEATURES_C0, **ABL}

    def predict_all(X):
        out = {"P": X["fuel_lag1"].to_numpy(float), "P2": (X["feeder_speed_pct"] * CAP / 100.0).to_numpy(float), "A": predict_A(X, eta_base),
               "B": lin_predict(X, cB, coefB), "L": lin_predict(X, ft.FEATURES_L, coefL), "C": mC.predict(X[ft.FEATURES])}
        for k, mm in mods.items():
            out[k] = mm.predict(X[feat_of[k]])
        return out

    P_vb, P_te, P_ext = predict_all(va_b), predict_all(te), predict_all(ext_te)
    half = {k: conformal_half(va_b["y"].to_numpy()[~np.isnan(P_vb[k])], P_vb[k][~np.isnan(P_vb[k])], mc["conformal_coverage"]) for k in ALL}

    rows, tbl = [], {}
    seg_e, _ = segments(te, cfg)
    _, seg_x = segments(ext_te, cfg)
    common = np.all([~np.isnan(P_ext[k]) for k in ("A", "B", "L")], axis=0)
    lhv_te, lhv_ext = te["bed_LHV_MJkg"].to_numpy(), ext_te["bed_LHV_MJkg"].to_numpy()
    for k in ALL:
        r = metrics(te["y"], P_te[k], half[k], cfg, P_te["B"], lhv_te, te["fuel_lot"])
        r["MAE_valb"] = mae(P_vb[k], va_b["y"].to_numpy())
        r["val_test_gap"] = (r["MAE"] - r["MAE_valb"]) / r["MAE_valb"]
        r["MAE_ci_lo"], r["MAE_ci_hi"] = cluster_boot_mae(np.abs(te["y"].to_numpy() - P_te[k]), te["fuel_lot"].to_numpy(), mc["n_boot"], seed)
        worst = 0.0
        for name, mk in seg_e.items():
            mk = mk.to_numpy()
            if "fault" in name:
                continue
            s = metrics(te["y"].to_numpy()[mk], P_te[k][mk], half[k], cfg, P_te["B"][mk])
            if s["n"] >= 50:
                worst = max(worst, s["MAE"] / r["MAE"])
        r["worst_seg_ratio"] = worst
        tbl[k] = r
        rows.append(dict(model=k, population="eligible_test", segment_type="ALL", segment="ALL", **r))
        for name, mk in seg_e.items():
            mk = mk.to_numpy()
            rows.append(dict(model=k, population="eligible_test", segment_type="band", segment=name,
                             **metrics(te["y"].to_numpy()[mk], P_te[k][mk], half[k], cfg, P_te["B"][mk], lhv_te[mk], te["fuel_lot"].to_numpy()[mk])))
        rows.append(dict(model=k, population="extended_test", segment_type="ALL", segment="ALL (each model's own rows)",
                         **metrics(ext_te["y"], P_ext[k], half[k], cfg, P_ext["B"], lhv_ext)))
        rows.append(dict(model=k, population="extended_test", segment_type="ALL", segment="ALL (rows all of A,B,L predict)",
                         **metrics(ext_te["y"].to_numpy()[common], P_ext[k][common], half[k], cfg, P_ext["B"][common], lhv_ext[common])))
        for name, mk in seg_x.items():
            mk = mk.to_numpy()
            rows.append(dict(model=k, population="extended_test", segment_type="condition", segment=name,
                             **metrics(ext_te["y"].to_numpy()[mk], P_ext[k][mk], half[k], cfg, P_ext["B"][mk], lhv_ext[mk])))
    comp = pd.DataFrame(rows)

    leak = leakage_checks(F, d, cfg, hp_best, seed)
    leak_ok = leak["shuffled_has_no_skill"] and leak["future_feature_detected"] and leak["no_forbidden_columns"] and leak["truncation_invariant"]
    r2_flag = {k: bool(tbl[k]["R2"] > mc["selection"]["leak_r2"]) for k in ALL}
    chosen, safe, beats, best_ref, beats_test = select(tbl, leak_ok, mc["selection"])

    imp = {}
    for name, mdl, cols in (("C", mC, ft.FEATURES), ("C0", mods["C0"], ft.FEATURES_C0), ("C0_nofeed", mods["C0_nofeed"], ft.FEATURES_NOFEED)):
        pi = permutation_importance(mdl, te[cols], te["y"], n_repeats=mc["perm_repeats"], scoring="neg_mean_absolute_error", random_state=seed)
        imp[name] = pd.DataFrame({"model": name, "feature": cols, "mae_increase_kgh": pi.importances_mean, "sd": pi.importances_std})
    imp = pd.concat(imp.values()).sort_values(["model", "mae_increase_kgh"], ascending=[True, False])

    res = dict(F=F, d=d, tr=tr, va=va, va_a=va_a, va_b=va_b, te=te, ext_te=ext_te, P_te=P_te, P_ext=P_ext, half=half, tbl=tbl, comp=comp, leak=leak,
               leak_ok=leak_ok, r2_flag=r2_flag, chosen=chosen, safe=safe, beats_ref=beats, best_ref=best_ref, beats_test=beats_test, imp=imp,
               eta_base=eta_base, coefB=coefB, coefL=coefL, hp=hp_best, mC=mC, mods=mods, val_mae_grid=best[0])
    if write:
        write_outputs(res, cfg, clean_path)
    return res


def table_print(tbl, names=None):
    cols = ["MAE", "MAPE", "RMSE", "P90", "R2", "coverage", "MAE_valb", "val_test_gap", "worst_seg_ratio"]
    return pd.DataFrame({k: {c: tbl[k].get(c, np.nan) for c in cols} for k in (names or ALL)}).T.round(3).to_string()


def write_outputs(res, cfg, clean_path):
    mc = cfg["model"]
    MODELS.mkdir(exist_ok=True)
    (ROOT / "data" / "holdout").mkdir(parents=True, exist_ok=True)
    F = res["F"]
    split_path = ROOT / "data" / "holdout" / "split_keys.csv"
    F[["timestamp_local", "fuel_lot", "split", "val_part", "eligible", "purged", "y_ok"]].to_csv(split_path, index=False)
    joblib.dump({"type": "persistence", "feature": "fuel_lag1", "half": res["half"]["P"]}, MODELS / "P_persistence.joblib")
    joblib.dump({"type": "current_feed", "formula": "feeder_speed_pct*capacity/100", "capacity_kgh": CAP, "half": res["half"]["P2"]}, MODELS / "P2_current_feed.joblib")
    joblib.dump({"type": "physics", "eta_base": res["eta_base"], "half": res["half"]["A"]}, MODELS / "A_physics.joblib")
    joblib.dump({"type": "linear", "features": ["Q_out_MW", "bed_moisture_wb_pct"], "coef": res["coefB"].tolist(), "half": res["half"]["B"]}, MODELS / "B_linear.joblib")
    joblib.dump({"type": "linear", "features": ft.FEATURES_L, "coef": res["coefL"].tolist(), "half": res["half"]["L"]}, MODELS / "L_linear_full.joblib")
    joblib.dump({"type": "hgb", "model": res["mC"], "features": ft.FEATURES, "half": res["half"]["C"]}, MODELS / "C_hgb.joblib")
    feat = {"C0": ft.FEATURES_C0, **ABL}
    for k, mm in res["mods"].items():
        joblib.dump({"type": "hgb", "model": mm, "features": feat[k], "half": res["half"][k]}, MODELS / f"{k}_hgb.joblib")
    design = (ROOT / "reports" / "model_card.md").read_text(encoding="utf-8")
    meta = dict(seed=mc["seed"], data_sha256=sha(clean_path), split_sha256=sha(split_path),
                n_train=len(res["tr"]), n_val_a=len(res["va_a"]), n_val_b=len(res["va_b"]), n_test=len(res["te"]),
                versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, sklearn=sklearn.__version__, joblib=joblib.__version__),
                features=ft.FEATURES, features_C0=ft.FEATURES_C0, features_L=ft.FEATURES_L,
                hyperparameters_C=dict(zip(["max_depth", "learning_rate", "max_iter", "min_samples_leaf"], res["hp"])),
                eta_base=res["eta_base"], coefB=res["coefB"].tolist(), conformal_halfwidth_kgh=res["half"],
                selected=res["chosen"], best_reference=res["best_ref"], selected_beats_best_reference_val=res["beats_ref"],
                selected_beats_best_reference_test=res["beats_test"], safe=res["safe"], r2_gt_0p995_flag=res["r2_flag"], leakage=res["leak"],
                selection_rule=mc["selection"], design_section_sha256_before_training="5d1c2ca2563de16ccc2e0128a6cedef8db5b17f9c782603cd5147223e906b9c7",
                banner="SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION")
    (MODELS / "metadata.json").write_text(json.dumps(meta, indent=1, default=float), encoding="utf-8")
    res["comp"].round(5).to_csv(ROOT / "reports" / "model_comparison.csv", index=False)
    res["imp"].round(4).to_csv(ROOT / "reports" / "permutation_importance.csv", index=False)
    ext = res["ext_te"]
    out = ext[["timestamp_local", "fuel_lot", "eligible", "operating_mode", "fan_derated", "lhv_known", "load_MW", "bed_moisture_wb_pct", "y",
               "analysis_scenario_id", "analysis_fault_injected"]].copy()
    for k in ALL:
        out[f"pred_{k}"] = res["P_ext"][k]
        out[f"half_{k}"] = res["half"][k]
    out.to_csv(ROOT / "data" / "holdout" / "test_predictions.csv", index=False)
    figures(res, out)
    from src import train_report
    train_report.write(res, out, cfg)


def figures(res, out):
    FIG.mkdir(parents=True, exist_ok=True)
    tbl, comp = res["tbl"], res["comp"]
    show = NAMES
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    for i, k in enumerate(show):
        r = tbl[k]
        ax[0].bar(i, r["MAE"], color=COL[k])
        ax[0].errorbar(i, r["MAE"], yerr=[[r["MAE"] - r["MAE_ci_lo"]], [r["MAE_ci_hi"] - r["MAE"]]], color="k", capsize=3)
        ax[1].bar(i, r["coverage"] * 100, color=COL[k])
    for a in ax[:2]:
        a.set_xticks(range(len(show))); a.set_xticklabels(show)
    ax[0].set_ylabel("test MAE (kg/h), 95 % lot-bootstrap CI"); ax[0].set_title("Eligible test MAE (P, P2 = references)", fontsize=9)
    ax[1].axhline(90, color="k", ls="--", lw=1); ax[1].set_ylim(60, 100); ax[1].set_ylabel("coverage of 90 % conformal interval (%)"); ax[1].set_title("Test coverage", fontsize=9)
    abl = ["C0", "C0_nofeed", "C0_nolot", "C0_noco", "P2"]
    for i, k in enumerate(abl):
        ax[2].bar(i, tbl[k]["MAE"], color=COL[k])
    ax[2].set_xticks(range(len(abl))); ax[2].set_xticklabels(abl, fontsize=8); ax[2].set_title("Ablations: what C0 relies on (MAE kg/h)", fontsize=9)
    for a in ax: a.grid(alpha=0.25)
    fig.suptitle(f"Model comparison | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p3_model_comparison.png", dpi=130); plt.close(fig)

    seg = comp[(comp.population == "eligible_test") & (comp.segment != "ALL") & comp.model.isin(["P2", "B", "L", "C0"])]
    segx = comp[(comp.population == "extended_test") & (comp.segment_type == "condition") & (comp.n >= 20) & comp.model.isin(["P2", "B", "L", "C0"])]
    fig, ax = plt.subplots(2, 1, figsize=(13, 8))
    for a, s, ttl in ((ax[0], seg, "Eligible test segments"), (ax[1], segx, "Extended population (outside the training distribution)")):
        names = list(dict.fromkeys(s.segment))
        for j, k in enumerate(["P2", "B", "L", "C0"]):
            v = s[s.model == k].set_index("segment").reindex(names)["MAE"]
            a.bar(np.arange(len(names)) + (j - 1.5) * 0.2, v.values, 0.2, color=COL[k], label=k)
        a.set_xticks(range(len(names))); a.set_xticklabels([f"{n}\n(n={int(s[(s.model == 'C0') & (s.segment == n)]['n'].iloc[0])})" for n in names], fontsize=7)
        a.set_ylabel("MAE (kg/h)"); a.set_title(ttl, fontsize=9); a.grid(alpha=0.25); a.legend(fontsize=7, ncol=4)
    ax[1].set_yscale("log")
    fig.suptitle(f"MAE by segment | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p3_segments.png", dpi=130); plt.close(fig)

    k = res["chosen"] or "C0"
    e = out[out.eligible]
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    ax[0].scatter(e["pred_" + k], e["y"], s=5, alpha=0.4, color=COL[k]); ax[0].plot([0, 4500], [0, 4500], color="k", lw=1)
    ax[0].set_xlabel(f"predicted next-15-min fuel, model {k} (kg/h)"); ax[0].set_ylabel("actual (kg/h)"); ax[0].set_title("Eligible test rows", fontsize=9)
    err = e["y"] - e["pred_" + k]
    ax[1].hist(err.clip(-600, 600), bins=80, color=COL[k]); h = e["half_" + k].iloc[0]
    ax[1].axvline(h, color="k", ls="--"); ax[1].axvline(-h, color="k", ls="--"); ax[1].set_xlabel("actual - predicted (kg/h), clipped at +-600; dashed = 90 % conformal half-width")
    for a in ax: a.grid(alpha=0.25)
    fig.suptitle(f"Model {k} on the test split | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p3_pred_vs_actual.png", dpi=130); plt.close(fig)

    imp = res["imp"]
    fig, ax = plt.subplots(1, 3, figsize=(17, 6))
    for a, m in zip(ax, ("C", "C0", "C0_nofeed")):
        s = imp[imp.model == m].head(10)[::-1]
        a.barh(s["feature"], s["mae_increase_kgh"], xerr=s["sd"], color=COL[m]); a.set_title(f"{m}: MAE increase when shuffled (kg/h)", fontsize=9); a.grid(alpha=0.25)
    fig.suptitle(f"Permutation importance, eligible test | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p3_perm_importance.png", dpi=130); plt.close(fig)

    worst = out.assign(err=(out["y"] - out["pred_" + k]).abs()).sort_values("err", ascending=False)
    worst = worst[worst.eligible].head(3)
    allp = out.reset_index(drop=True)
    fig, ax = plt.subplots(len(worst), 1, figsize=(12, 3.2 * len(worst)))
    for a, (_, r) in zip(np.atleast_1d(ax), worst.iterrows()):
        i = allp.index[allp.timestamp_local == r.timestamp_local][0]
        w = allp.iloc[max(0, i - 24):i + 12]
        x = np.arange(len(w)) - (i - max(0, i - 24))
        a.plot(x, w["y"], label="actual next-15-min fuel", color="k"); a.plot(x, w["pred_" + k], label=f"predicted ({k})", color=COL[k])
        a.plot(x, w["pred_P2"], label="current feed (P2)", color=COL["P2"], ls=":"); a.axvline(0, color="r", lw=0.8)
        a.set_title(f"{r.timestamp_local[:16]} scenario {r.analysis_scenario_id}: |error| {r.err:.0f} kg/h", fontsize=8); a.grid(alpha=0.25); a.legend(fontsize=7)
    fig.suptitle(f"Largest eligible-test failures (x = 5-min rows) | {TAG}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "p3_failure_cases.png", dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args()
    r = run()
    print(f"train {len(r['tr'])} / val_a {len(r['va_a'])} / val_b {len(r['va_b'])} / test {len(r['te'])} eligible rows; C hyper-parameters {r['hp']}; eta_base {r['eta_base']:.4f}")
    print(table_print(r["tbl"]))
    print("leakage:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r["leak"].items()})
    print("R2>0.995:", {k: v for k, v in r["r2_flag"].items() if v} or "none", "| safe:", r["safe"], "| selected:", r["chosen"],
          "| best reference:", r["best_ref"], "| beats it by 5% (val/test):", r["beats_ref"], r["beats_test"])


if __name__ == "__main__":
    main()
