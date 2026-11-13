"""Simulated operator-option optimizer (SPEC C7). SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION.

For guardrail-eligible rows, evaluates a grid of FD x grate command moves at FIXED demand with an action-effect model
(OWN-ESTIMATE, fit on the training split only, lot-bootstrap uncertainty) and picks the lowest objective
J = dSFC + l1 dFanPower + l2 move + l3 interval width. Candidates that are OOD or fail a constraint are dropped; "less excess O2"
candidates are kept apart from "low-O2 / CO risk" candidates. Output records carry no actuation fields; humans decide.
Effect model is associational (observational plus generator exploration): it is NOT proof of causal savings.
Run: python -m src.optimizer --split test
"""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src import features as ft, guardrails as gd, predict as pr, train
from src.cleaning import load_cfg
from src.units import sfc_kg_gj

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
OUT = ROOT / "data" / "advisory"
BANNER = "SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION"
OOD_COLS = ["Q_out_MW", "fuel_moisture_wb_pct", "O2_pct_dry", "FD_command_pct", "grate_command_pct", "draft_pa"]


# ---------------------------------------------------------------- effect model
def eta_design(o2, g, q, m, dp, tamb):
    o2, g, q, m = (np.asarray(x, float) for x in (o2, g, q, m))
    dp, tamb = np.asarray(dp, float), np.asarray(tamb, float)
    return np.column_stack([np.ones_like(o2), o2, o2 ** 2, o2 * q, o2 * m, g, g ** 2, g * q, g * m, q, m, dp, tamb])


def co_design(o2, g, q, m):
    o2, g, q, m = (np.asarray(x, float) for x in (o2, g, q, m))
    return np.column_stack([np.ones_like(o2), o2, o2 ** 2, g, g ** 2, m, q, g * q, g * m])


def _ridge(X, y, alpha, scale):
    A = X.T @ X + alpha * np.diag(np.r_[0.0, np.ones(X.shape[1] - 1)] * scale)
    return np.linalg.solve(A, X.T @ y)


def fit_effect(tr, ocfg):
    """tr: training rows (eligible, eta_pct known). Returns the effect-model dict (coefficients + lot-bootstrap draws)."""
    rng = np.random.default_rng(ocfg["seed"])
    X = eta_design(tr["O2_pct_dry"], tr["grate_command_pct"], tr["Q_out_MW"], tr["fuel_moisture_wb_pct"], tr["economizer_dP_pa"], tr["ambient_temp_C"])
    y = tr["eta_pct"].to_numpy(float)
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Xs = np.column_stack([X[:, 0], (X[:, 1:] - mu) / sd])
    scale = np.ones(X.shape[1])
    beta = _ridge(Xs, y, 1.0, scale)
    lots = tr["fuel_lot"].to_numpy()
    ids = np.unique(lots)
    groups = [np.where(lots == c)[0] for c in ids]
    boots = np.empty((ocfg["n_boot"], len(beta)))
    for b in range(ocfg["n_boot"]):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(ids), len(ids))])
        boots[b] = _ridge(Xs[idx], y[idx], 1.0, scale)
    # CO model (rows with CO measured)
    c = tr[(tr["co_available"] == 1) & tr["CO_ppm"].notna() & (tr["CO_ppm"] > 0)]
    Xc = co_design(c["O2_pct_dry"], c["grate_command_pct"], c["Q_out_MW"], c["fuel_moisture_wb_pct"])
    cmu, csd = Xc[:, 1:].mean(0), Xc[:, 1:].std(0) + 1e-9
    Xcs = np.column_stack([Xc[:, 0], (Xc[:, 1:] - cmu) / csd])
    bco = _ridge(Xcs, np.log(c["CO_ppm"].to_numpy(float)), 1.0, np.ones(Xc.shape[1]))
    # draft model: linear in ID, FD, load
    Xd = np.column_stack([np.ones(len(tr)), tr["ID_command_pct"], tr["FD_command_pct"], tr["Q_out_MW"]])
    bd, *_ = np.linalg.lstsq(Xd, tr["draft_pa"].to_numpy(float), rcond=None)
    # fan power: kW = k (cmd/100)^3 through the origin (fan-law proxy, checked by correlation)
    kfd = float(np.sum(tr["fan_power_kW_FD"] * (tr["FD_command_pct"] / 100) ** 3) / np.sum((tr["FD_command_pct"] / 100) ** 6))
    resid = y - Xs @ beta
    # out-of-distribution detector: Mahalanobis^2 on key state, threshold from training quantile
    Z = tr[OOD_COLS].to_numpy(float)
    zmu, cov = Z.mean(0), np.cov(Z.T) + 1e-6 * np.eye(Z.shape[1])
    ci = np.linalg.inv(cov)
    d2 = np.einsum("ij,jk,ik->i", Z - zmu, ci, Z - zmu)
    return {"beta": beta, "boots": boots, "mu": mu, "sd": sd, "co_beta": bco, "co_mu": cmu, "co_sd": csd, "draft_beta": bd,
            "k_fan_fd": kfd, "eta_resid_sd": float(resid.std()), "eta_r2_train": float(1 - resid.var() / y.var()),
            "ood_mu": zmu, "ood_ci": ci, "ood_thr": float(np.quantile(d2, ocfg["ood_quantile"])), "n_train": len(tr),
            "n_lots": len(ids), "fan_corr": float(np.corrcoef(tr["fan_power_kW_FD"], tr["FD_command_pct"] ** 3)[0, 1])}


def _std(M, mu, sd):
    return np.column_stack([M[:, 0], (M[:, 1:] - mu) / sd])


def ood_d2(eff, Z):
    D = np.asarray(Z, float) - eff["ood_mu"]
    return np.einsum("ij,jk,ik->i", D, eff["ood_ci"], D)


def model_version(eff):
    h = hashlib.sha256(np.concatenate([eff["beta"], eff["co_beta"], eff["draft_beta"]]).tobytes()).hexdigest()[:8]
    return f"L-forecast+effect-ridge-v1:{h}"


# ---------------------------------------------------------------- candidates
def action_label(dfd, dg):
    if dfd == 0 and dg == 0:
        return "HOLD"
    if dg == 0:
        return f"FD{dfd:+d}"
    if dfd == 0:
        return f"GRATE{dg:+d}"
    return f"FD{dfd:+d}&GRATE{dg:+d}"


def optimize_rows(x, eff, G, forecast=None, ood_rows=None):
    """x: eligible-candidate rows (frame). Returns list of decision dicts (one per row). Pure given eff/G."""
    L, O = G["limits"], G["optimizer"]
    steps = [(a, b) for a in O["grid_steps_fd"] for b in O["grid_steps_grate"]]
    K, n = len(steps), len(x)
    dfd = np.array([s[0] for s in steps], float)[None, :]
    dg = np.array([s[1] for s in steps], float)[None, :]
    col = lambda c: x[c].to_numpy(float)[:, None]
    fd, gr, q, m, o2c, dr, idc = (col(c) for c in ("FD_command_pct", "grate_command_pct", "Q_out_MW", "fuel_moisture_wb_pct",
                                                 "O2_pct_dry", "draft_pa", "ID_command_pct"))
    dp, tamb, lhv, co_c = col("economizer_dP_pa"), col("ambient_temp_C"), col("LHV_used_MJkg"), col("CO_ppm")
    fdn, grn = fd + dfd, gr + dg
    lam_c = 21.0 / (21.0 - o2c)                                   # excess-air ratio from the measured O2
    lam_n = lam_c * fdn / fd                                      # air flow proportional to FD command at fixed demand
    o2n = np.minimum(21.0 * (1.0 - 1.0 / lam_n), 20.9)
    drn = dr + eff["draft_beta"][2] * dfd                         # ID unchanged
    flat = lambda a: np.broadcast_to(a, (n, K)).reshape(-1)
    # eta change, point and bootstrap
    Xc = _std(eta_design(flat(o2c), flat(gr), flat(q), flat(m), flat(dp), flat(tamb)), eff["mu"], eff["sd"])
    Xo = _std(eta_design(o2n.reshape(-1), grn.reshape(-1), flat(q), flat(m), flat(dp), flat(tamb)), eff["mu"], eff["sd"])
    dX = Xo - Xc
    d_eta = (dX @ eff["beta"]).reshape(n, K)
    d_eta_b = (dX @ eff["boots"].T).reshape(n, K, -1)
    eta_cur = (Xc @ eff["beta"]).reshape(n, K)[:, :1]
    eta_cur = np.clip(eta_cur, 40.0, 90.0)
    sfc_cur = sfc_kg_gj(eta_cur / 100.0, lhv)
    sfc_opt = sfc_kg_gj((eta_cur + d_eta) / 100.0, lhv)
    d_sfc = sfc_opt - sfc_cur
    d_sfc_b = sfc_kg_gj((eta_cur[:, :, None] + d_eta_b) / 100.0, lhv[:, :, None]) - sfc_cur[:, :, None]
    a = (1 - O["ci_level"]) / 2
    lo, hi = np.quantile(d_sfc_b, a, axis=2), np.quantile(d_sfc_b, 1 - a, axis=2)
    width = hi - lo
    # fan power change (FD only), CO prediction
    d_kw = eff["k_fan_fd"] * ((fdn / 100.0) ** 3 - (fd / 100.0) ** 3)
    Cc = _std(co_design(flat(o2c), flat(gr), flat(q), flat(m)), eff["co_mu"], eff["co_sd"])
    Co = _std(co_design(o2n.reshape(-1), grn.reshape(-1), flat(q), flat(m)), eff["co_mu"], eff["co_sd"])
    co_n = co_c * np.exp(((Co - Cc) @ eff["co_beta"]).reshape(n, K))
    # constraint checks per candidate
    c_range = (fdn >= L["fd_range_pct"][0]) & (fdn <= L["fd_range_pct"][1]) & (grn >= L["grate_range_pct"][0]) & (grn <= L["grate_range_pct"][1])
    c_move = np.broadcast_to((np.abs(dfd) <= L["max_step_fd_pct"]) & (np.abs(dg) <= L["max_step_grate_pct"]), (n, K))
    c_o2 = o2n >= L["o2_floor_pct"] + O["o2_margin_pct"]
    c_co = co_n * O["co_margin_factor"] <= L["co_limit_ppm"]
    c_draft = (drn >= L["draft_band_pa"][0]) & (drn <= L["draft_band_pa"][1])
    Z = np.stack([flat(q), flat(m), o2n.reshape(-1), fdn.reshape(-1), grn.reshape(-1), drn.reshape(-1)], axis=1)
    c_ood = (ood_d2(eff, Z) <= eff["ood_thr"]).reshape(n, K)
    c_width = width <= L["interval_width_max_sfc_kg_gj"]
    cm = O.get("combo_max_step_pct")
    c_menu = np.broadcast_to(True if cm is None else ~((dfd != 0) & (dg != 0) & (np.maximum(np.abs(dfd), np.abs(dg)) > cm)), (n, K))
    ok_all = c_range & c_move & c_o2 & c_co & c_draft & c_ood & c_menu
    hold = (dfd == 0) & (dg == 0)
    J = d_sfc + O["lambda_fan_kg_gj_per_kw"] * d_kw + O["lambda_move_kg_gj_per_pct"] * (np.abs(dfd) + np.abs(dg)) + O["lambda_width"] * width
    J = np.where(hold, 0.0, J)
    Jm = np.where(ok_all | hold, J, np.inf)
    best = Jm.argmin(axis=1)
    out = []
    for i in range(n):
        j = int(best[i])
        lab = action_label(int(dfd[0, j]), int(dg[0, j]))
        risk = (~c_o2[i] | ~c_co[i]) & ~hold[0]
        drop = {"LOW_O2_OR_CO_RISK": int(risk.sum()), "OOD": int((~c_ood[i] & ~risk).sum()), "DRAFT": int((~c_draft[i] & ~risk).sum()),
                "RANGE_OR_MOVE": int((~(c_range[i] & c_move[i] & c_menu[i])).sum())}
        codes, decision, cls = [], "NO_ADVICE", "NONE"
        if lab == "HOLD":
            codes = ["NO_BENEFIT"]
        elif hi[i, j] >= -O["min_benefit_sfc_kg_gj"]:
            codes = ["WIDE_INTERVAL"] if not c_width[i, j] else ["NO_BENEFIT"]
        elif not c_width[i, j]:
            codes = ["WIDE_INTERVAL"]
        else:
            decision = "ADVICE"
            cls = ("LESS_EXCESS_O2" if o2n[i, j] < o2c[i, 0] - 0.05 else "MORE_AIR_COMPLETE_COMBUSTION" if o2n[i, j] > o2c[i, 0] + 0.05
                   else "GRATE_BALANCE")
        sfc_c = float(sfc_cur[i, 0])
        rec = {"decision": decision, "reason_codes": codes, "advice_class": cls, "action": lab if decision == "ADVICE" else "NONE",
               "proposed": ({"FD_command_pct": round(float(fdn[i, j]), 2), "grate_command_pct": round(float(grn[i, j]), 2)}
                            if decision == "ADVICE" else None),
               "predicted_SFC_current": round(sfc_c, 3), "predicted_SFC_option": round(float(sfc_opt[i, j]), 3) if decision == "ADVICE" else None,
               "uncertainty": {"dSFC_kg_GJ_point": round(float(d_sfc[i, j]), 3), "dSFC_lo90": round(float(lo[i, j]), 3),
                               "dSFC_hi90": round(float(hi[i, j]), 3), "width_kg_GJ": round(float(width[i, j]), 3),
                               "eta_resid_sd_pp": round(eff["eta_resid_sd"], 3)},
               "constraint_checks": {"O2_option_pct": round(float(o2n[i, j]), 2), "O2_floor_pct": L["o2_floor_pct"],
                                     "CO_option_ppm": round(float(co_n[i, j]), 1), "CO_limit_ppm": L["co_limit_ppm"],
                                     "draft_option_pa": round(float(drn[i, j]), 1), "draft_band_pa": L["draft_band_pa"],
                                     "ood_option": bool(not c_ood[i, j]), "max_step_pct": L["max_step_fd_pct"],
                                     "candidates_dropped": drop},
               "predicted_benefit_synthetic_only": ({"dSFC_pct": round(100.0 * float(d_sfc[i, j]) / sfc_c, 3),
                                                     "deta_pp": round(float(d_eta[i, j]), 3),
                                                     "label": "SYNTHETIC generator illustration, not a savings claim"}
                                                    if decision == "ADVICE" else None),
               "_d_sfc_point": float(d_sfc[i, j]), "_fan_kw": float(d_kw[i, j])}
        out.append(rec)
    return out


# ---------------------------------------------------------------- orchestration
def load_frames():
    """Clean frame + eval labels + Phase-3 split + forecast status for every row."""
    cfg = load_cfg()
    d = ft.load_clean().sort_values("t").reset_index(drop=True)
    F = train.assign_split(ft.build(d), cfg)
    ev = pd.read_csv(ROOT / "data" / "clean" / "eval_labels.csv")
    d = d.merge(F[["timestamp_local", "split", "y_ok"]], on="timestamp_local", how="left").merge(
        ev.drop_duplicates("timestamp_local"), on="timestamp_local", how="left")
    return d, F, cfg


def fit_from_clean(d, G):
    """Fit on the training split: eligible rows with a calculated eta and CO-free features present."""
    tr = d[(d["split"] == "train") & d["eligibility"].str.startswith(("ELIGIBLE", "DIAGNOSTIC_ONLY")) & d["eta_pct"].notna()
           & d["fuel_moisture_wb_pct"].notna() & (d["operating_mode"] == "STEADY")]
    eff = fit_effect(tr, G["optimizer"])
    eff["version"] = model_version(eff)
    joblib.dump(eff, MODELS / "effect_model.joblib")
    return eff


def run_split(d, F, eff, G, split):
    """Decision records for every row of a split. Guardrails -> optimizer."""
    x = d[d["split"] == split].reset_index(drop=True)
    need = OOD_COLS + ["LHV_used_MJkg", "economizer_dP_pa", "ambient_temp_C", "ID_command_pct"]
    complete = x[need].notna().all(axis=1).to_numpy()
    ood = np.zeros(len(x), bool)
    ood[complete] = ood_d2(eff, x.loc[complete, OOD_COLS].to_numpy(float)) > eff["ood_thr"]
    gr = gd.evaluate(x, G, ood=ood)
    gr.loc[~complete & gr["eligible"], ["eligible", "outcome", "reason_codes"]] = [False, "NO_ADVICE", "LOW_FUEL_CONF"]
    fc = pr.predict(F[F["timestamp_local"].isin(x["timestamp_local"])].reset_index(drop=True), "selected").set_index("timestamp_local")["y_hat_kgh"]
    ver = eff["version"]
    recs = [None] * len(x)
    el = np.where(gr["eligible"].to_numpy())[0]
    res = optimize_rows(x.iloc[el], eff, G) if len(el) else []
    for i in range(len(x)):
        base = {"timestamp": x.at[i, "timestamp_local"], "eligible": bool(gr.at[i, "eligible"]), "model_version": ver,
                "human_review_required": True, "banner": BANNER,
                "current_simulated_settings": {"FD_command_pct": _f(x.at[i, "FD_command_pct"]), "ID_command_pct": _f(x.at[i, "ID_command_pct"]),
                                               "grate_command_pct": _f(x.at[i, "grate_command_pct"]), "O2_pct_dry": _f(x.at[i, "O2_pct_dry"])},
                "forecast_fuel_kgh_next": _f(fc.get(x.at[i, "timestamp_local"], np.nan))}
        if not gr.at[i, "eligible"]:
            dec = gr.at[i, "outcome"]
            base.update(decision=dec, reason_codes=gr.at[i, "reason_codes"].split(";"), proposed_simulated_settings=None,
                        predicted_SFC_current=None, predicted_SFC_option=None, uncertainty=None, constraint_checks=None,
                        predicted_benefit_synthetic_only=None, advice_class="NONE", action="NONE")
        recs[i] = base
    for k, i in enumerate(el):
        r = res[k]
        recs[i].update(decision=r["decision"], reason_codes=r["reason_codes"], proposed_simulated_settings=r["proposed"],
                       predicted_SFC_current=r["predicted_SFC_current"], predicted_SFC_option=r["predicted_SFC_option"],
                       uncertainty=r["uncertainty"], constraint_checks=r["constraint_checks"],
                       predicted_benefit_synthetic_only=r["predicted_benefit_synthetic_only"], advice_class=r["advice_class"], action=r["action"])
    R = pd.DataFrame(recs)
    R["_guard_codes"] = gr["reason_codes"].to_numpy()
    return x, R


def _f(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 3)


def write_records(R, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["timestamp", "eligible", "decision", "reason_codes", "current_simulated_settings", "proposed_simulated_settings",
            "predicted_SFC_current", "predicted_SFC_option", "uncertainty", "constraint_checks", "predicted_benefit_synthetic_only",
            "human_review_required", "model_version", "advice_class", "action", "forecast_fuel_kgh_next", "banner"]
    with open(path, "w", encoding="utf-8") as f:
        for rec in R[cols].to_dict("records"):
            rec = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in rec.items()}
            f.write(json.dumps(rec, default=str, allow_nan=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", choices=["val", "test"])
    ap.add_argument("--limits", default=None)
    a = ap.parse_args()
    from src import compare
    compare.run(a.split, a.limits)


if __name__ == "__main__":
    main()
