"""Single-move what-if evaluation (SPEC C7), same math as optimizer.optimize_rows for ONE chosen FD/grate target.
SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION. Out-of-bounds inputs raise/return violations and produce NO output.

validate(row, fd_new, g_new, G) -> list[str] of violations (empty = in bounds).
evaluate(row, fd_new, g_new, eff, G) -> dict (raises ValueError when validate() finds violations or the row is incomplete).
Run: python -m src.whatif --help
"""
import argparse

import numpy as np

from src import optimizer as op
from src.units import sfc_kg_gj

NEED = ["FD_command_pct", "grate_command_pct", "Q_out_MW", "fuel_moisture_wb_pct", "O2_pct_dry", "draft_pa", "ID_command_pct",
        "economizer_dP_pa", "ambient_temp_C", "LHV_used_MJkg", "CO_ppm"]


def validate(row, fd_new, g_new, G):
    """Bounds from config (guardrail_limits.yaml). Non-finite values are violations."""
    L = G["limits"]
    out = []
    try:
        fd_new, g_new = float(fd_new), float(g_new)
    except (TypeError, ValueError):
        return ["inputs must be numbers"]
    if not (np.isfinite(fd_new) and np.isfinite(g_new)):
        return ["inputs must be finite numbers"]
    lo, hi = L["fd_range_pct"]
    if not lo <= fd_new <= hi:
        out.append(f"FD command {fd_new:g} % outside the allowed range [{lo:g}, {hi:g}] %")
    lo, hi = L["grate_range_pct"]
    if not lo <= g_new <= hi:
        out.append(f"Grate command {g_new:g} % outside the allowed range [{lo:g}, {hi:g}] %")
    if abs(fd_new - float(row["FD_command_pct"])) > L["max_step_fd_pct"] + 1e-9:
        out.append(f"FD move {fd_new - float(row['FD_command_pct']):+.2f} % exceeds the maximum step ±{L['max_step_fd_pct']:g} %")
    if abs(g_new - float(row["grate_command_pct"])) > L["max_step_grate_pct"] + 1e-9:
        out.append(f"Grate move {g_new - float(row['grate_command_pct']):+.2f} % exceeds the maximum step ±{L['max_step_grate_pct']:g} %")
    return out


def evaluate(row, fd_new, g_new, eff, G):
    bad = validate(row, fd_new, g_new, G)
    if bad:
        raise ValueError("; ".join(bad))
    if any(c not in row or not np.isfinite(float(row[c])) for c in NEED):
        raise ValueError("row has missing values required by the effect model")
    L, O = G["limits"], G["optimizer"]
    f = lambda c: np.array([float(row[c])])
    fd, gr, q, m, o2c, dr = f("FD_command_pct"), f("grate_command_pct"), f("Q_out_MW"), f("fuel_moisture_wb_pct"), f("O2_pct_dry"), f("draft_pa")
    dp, tamb, lhv, co_c = f("economizer_dP_pa"), f("ambient_temp_C"), f("LHV_used_MJkg"), f("CO_ppm")
    fdn, grn = np.array([float(fd_new)]), np.array([float(g_new)])
    dfd = fdn - fd
    o2n = np.minimum(21.0 * (1.0 - 1.0 / (21.0 / (21.0 - o2c) * fdn / fd)), 20.9)
    drn = dr + eff["draft_beta"][2] * dfd
    Xc = op._std(op.eta_design(o2c, gr, q, m, dp, tamb), eff["mu"], eff["sd"])
    Xo = op._std(op.eta_design(o2n, grn, q, m, dp, tamb), eff["mu"], eff["sd"])
    dX = Xo - Xc
    d_eta = float((dX @ eff["beta"])[0])
    d_eta_b = dX @ eff["boots"].T
    eta_cur = float(np.clip(Xc @ eff["beta"], 40.0, 90.0)[0])
    sfc_cur = float(sfc_kg_gj(eta_cur / 100.0, lhv)[0])
    sfc_opt = float(sfc_kg_gj((eta_cur + d_eta) / 100.0, lhv)[0])
    d_b = sfc_kg_gj((eta_cur + d_eta_b) / 100.0, lhv[:, None]) - sfc_cur
    a = (1 - O["ci_level"]) / 2
    lo, hi = float(np.quantile(d_b, a)), float(np.quantile(d_b, 1 - a))
    d_kw = float(eff["k_fan_fd"] * ((fdn / 100.0) ** 3 - (fd / 100.0) ** 3)[0])
    Cc = op._std(op.co_design(o2c, gr, q, m), eff["co_mu"], eff["co_sd"])
    Co = op._std(op.co_design(o2n, grn, q, m), eff["co_mu"], eff["co_sd"])
    co_n = float((co_c * np.exp((Co - Cc) @ eff["co_beta"]))[0])
    Z = np.stack([q, m, o2n, fdn, grn, drn], axis=1)
    ood = bool(op.ood_d2(eff, Z)[0] > eff["ood_thr"])
    o2n, drn = float(o2n[0]), float(drn[0])
    checks = {
        "O2 stays above floor + margin": (o2n >= L["o2_floor_pct"] + O["o2_margin_pct"], f"{o2n:.2f} % vs ≥ {L['o2_floor_pct'] + O['o2_margin_pct']:.2f} %"),
        "CO (with safety factor) below limit": (co_n * O["co_margin_factor"] <= L["co_limit_ppm"],
                                                f"{co_n:.1f} ppm × {O['co_margin_factor']} vs ≤ {L['co_limit_ppm']:g} ppm"),
        "Draft stays inside band": (L["draft_band_pa"][0] <= drn <= L["draft_band_pa"][1], f"{drn:.1f} Pa vs {L['draft_band_pa']}"),
        "Operating point in training distribution": (not ood, "in distribution" if not ood else "OUT of distribution"),
        "Interval width within limit": (hi - lo <= L["interval_width_max_sfc_kg_gj"], f"{hi - lo:.3f} vs ≤ {L['interval_width_max_sfc_kg_gj']:g} kg/GJ"),
        "Pessimistic (95th pct) SFC change is a reduction": (hi < -O["min_benefit_sfc_kg_gj"], f"{hi:+.3f} kg/GJ vs < {-O['min_benefit_sfc_kg_gj']:g}"),
    }
    return {"O2_option_pct": o2n, "CO_option_ppm": co_n, "draft_option_pa": drn, "SFC_current": sfc_cur, "SFC_option": sfc_opt,
            "dSFC_point": sfc_opt - sfc_cur, "dSFC_lo90": lo, "dSFC_hi90": hi, "deta_pp": d_eta, "dfan_kw": d_kw,
            "dSFC_pct": 100.0 * (sfc_opt - sfc_cur) / sfc_cur, "checks": checks, "all_pass": all(v[0] for v in checks.values()),
            "label": op.action_label(int(round(float(fd_new) - float(fd[0]))), int(round(float(g_new) - float(gr[0]))))}


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()


if __name__ == "__main__":
    main()
