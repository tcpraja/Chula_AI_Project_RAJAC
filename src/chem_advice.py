"""Chemical-engineering view of one operating point and one advisory option (diagnostic, SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION).

Shows WHY an air/grate move is or is not sensible: excess air from O2, indirect heat-loss balance, the loss-vs-O2 trade-off curve (stack loss
rises with excess air, CO and unburnt-carbon risk rise when air is short), the chemistry-based efficiency change for the proposed O2, and
the cross-check against the ridge effect model. Also the optimizer objective J = dSFC + l1 dFanPower + l2 |move| + l3 width, term by term.
All fuel properties are ASSUMED (config/fuel_properties.yaml). Run: python -m src.chem_advice --help
"""
import argparse

import numpy as np
import pandas as pd

from src import combustion as cb, optimizer as op, whatif


def lot_moisture(df, i):
    """Lab moisture of the row, or of its fuel lot (first lab value), else NaN. Lab values are never invented."""
    v = df.at[i, "fuel_moisture_wb_pct"]
    if pd.notna(v):
        return float(v)
    s = df.loc[df["fuel_lot"] == df.at[i, "fuel_lot"], "fuel_moisture_wb_pct"].dropna()
    return float(s.iloc[0]) if len(s) else float("nan")


def co_curve(row, eff, o2_grid):
    """Predicted CO (ppm) over an O2 grid at the row's grate, load and moisture (ridge CO model, OWN-ESTIMATE); NaN if CO is not measured."""
    co_c = row.get("CO_ppm")
    if row.get("co_available", 0) != 1 or pd.isna(co_c):
        return np.full(len(o2_grid), np.nan)
    n = len(o2_grid)
    rep = lambda v: np.full(n, float(v))
    q, m, gr = rep(row["Q_out_MW"]), rep(row["fuel_moisture_wb_pct"] if pd.notna(row["fuel_moisture_wb_pct"]) else 17.0), rep(row["grate_command_pct"])
    Cc = op._std(op.co_design(rep(row["O2_pct_dry"]), gr, q, m), eff["co_mu"], eff["co_sd"])
    Co = op._std(op.co_design(np.asarray(o2_grid, float), gr, q, m), eff["co_mu"], eff["co_sd"])
    return float(co_c) * np.exp((Co - Cc) @ eff["co_beta"])


def chem_view(row, moisture_wb, rec, eff, G, fuel=None):
    fuel = fuel or cb.load_fuel()
    o2, lhv, ts, ta = float(row["O2_pct_dry"]), float(row["LHV_used_MJkg"]), float(row["stack_temp_C"]), float(row["ambient_temp_C"])
    rh = float(row["ambient_RH_pct"]) if pd.notna(row.get("ambient_RH_pct")) else 70.0
    co = float(row["CO_ppm"]) if row.get("co_available", 0) == 1 and pd.notna(row.get("CO_ppm")) else float("nan")
    unb = float(row["unburnt_in_ash_pct"]) if pd.notna(row.get("unburnt_in_ash_pct")) else None
    if not np.isfinite(moisture_wb) or not np.isfinite(lhv) or not np.isfinite(o2) or not np.isfinite(ts):
        return None
    cur = cb.losses(fuel, moisture_wb, lhv, o2, ts, ta, co if np.isfinite(co) else 0.0, unb, rh)
    L = G["limits"]
    grid = np.round(np.arange(3.0, 12.01, 0.1), 2)
    cog = co_curve(row, eff, grid)
    tot = []
    for g, c in zip(grid, cog):
        r = cb.losses(fuel, moisture_wb, lhv, g, ts, ta, c if np.isfinite(c) else 0.0, unb, rh)
        tot.append((r["dry_flue_gas"], r["CO"], r["total"]))
    tot = np.array(tot)
    floor = L["o2_floor_pct"] + G["optimizer"]["o2_margin_pct"]
    allowed = (grid >= floor) & (np.isnan(cog) | (cog * G["optimizer"]["co_margin_factor"] <= L["co_limit_ppm"]))
    k = int(np.argmin(np.where(allowed, tot[:, 2], np.inf))) if allowed.any() else None
    out = {"current": cur, "co_measured": np.isfinite(co), "curve": pd.DataFrame({"O2_pct": grid, "dry_flue_gas_loss": tot[:, 0], "co_loss": tot[:, 1],
                                                                                   "total_loss": tot[:, 2], "CO_ppm": cog, "allowed": allowed}),
           "o2_opt": float(grid[k]) if k is not None else None, "moisture_wb": moisture_wb, "floor": floor,
           "eta_heat_balance": float(row["eta_pct"]) if pd.notna(row.get("eta_pct")) else None}
    if rec and rec.get("decision") == "ADVICE":
        cc, ben = rec["constraint_checks"], rec["predicted_benefit_synthetic_only"]
        o2n = cc["O2_option_pct"]
        opt = cb.losses(fuel, moisture_wb, lhv, o2n, ts, ta, cc["CO_option_ppm"] if np.isfinite(co) else 0.0, unb, rh)
        out["option"] = opt
        out["deta_chem"] = cur["total"] - opt["total"]          # percentage points of LHV saved by the O2 change at constant stack temperature
        out["deta_ridge"] = ben["deta_pp"]
        out["o2_option"] = o2n
        res = whatif.evaluate(row, rec["proposed_simulated_settings"]["FD_command_pct"], rec["proposed_simulated_settings"]["grate_command_pct"], eff, G)
        O = G["optimizer"]
        dfd = rec["proposed_simulated_settings"]["FD_command_pct"] - rec["current_simulated_settings"]["FD_command_pct"]
        dg = rec["proposed_simulated_settings"]["grate_command_pct"] - rec["current_simulated_settings"]["grate_command_pct"]
        terms = {"dSFC (kg/GJ)": res["dSFC_point"], "fan power term": O["lambda_fan_kg_gj_per_kw"] * res["dfan_kw"],
                 "move penalty": O["lambda_move_kg_gj_per_pct"] * (abs(dfd) + abs(dg)), "interval-width penalty": O["lambda_width"] * (res["dSFC_hi90"] - res["dSFC_lo90"])}
        out["objective"] = terms
        out["objective_J"] = float(sum(terms.values()))
    return out


def explain(v, rec):
    """Plain-language reasons from the chemistry (no numbers invented: every figure comes from v)."""
    c = v["current"]
    lines = [f"Excess air ratio λ = 21 / (21 − O2) = {c['lambda']:.2f}: the furnace is fed {100 * (c['lambda'] - 1):.0f} % more air than the {c['stoich_air_kg_per_kg']:.2f} kg air per kg fuel that complete combustion needs."]
    lines.append(f"Heat lost with the dry flue gas is {c['dry_flue_gas']:.1f} % of the fuel heat; every extra point of O2 adds flue gas that leaves hot, so air above what burn-out needs wastes fuel.")
    if v["co_measured"]:
        lines.append(f"CO and unburnt carbon cost {c['CO'] + c['unburnt_carbon']:.2f} % now; cutting air too far raises both, which is why the O2 floor ({v['floor']:.1f} %) and the CO limit bound any move.")
    else:
        lines.append("CO is not measured here, so the incomplete-combustion side of the trade-off cannot be checked: diagnostic only, no air advice.")
    if v.get("o2_opt") is not None:
        o2_now = 21 - 21 / c["lambda"]
        at_bound = abs(v["o2_opt"] - v["floor"]) < 0.25
        lines.append(f"Within the allowed band the lowest total loss is at O2 ≈ {v['o2_opt']:.1f} % (now {o2_now:.1f} %)." + (
            " That is the lower safety bound: the loss curve alone would keep lowering air, so the O2 floor and the CO limit, not the model, decide how far to go." if at_bound else ""))
    if "option" in v:
        agree = "agrees in sign with" if (v["deta_chem"] > 0) == (v["deta_ridge"] > 0) else "DISAGREES with"
        lines.append(f"Moving O2 to {v['o2_option']:.2f} % changes the chemistry loss balance by {v['deta_chem']:+.2f} points; this {agree} the ridge model's Δη of {v['deta_ridge']:+.2f} pp (the ridge also includes the grate move).")
    return lines


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()


if __name__ == "__main__":
    main()
