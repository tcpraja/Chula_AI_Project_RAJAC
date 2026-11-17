"""Operations-level efficiency view: where the heater is, the best efficiency chemistry allows inside the safety bounds, and what to raise or reduce.

Built on the heat and mass balance (src.combustion): indirect efficiency = 100 - dry-flue-gas, vapour, CO, unburnt-carbon and radiation losses.
`snapshot` returns plain dicts for one row: parameter table with targets and actions, lever sensitivities (O2, stack temperature, moisture, CO,
unburnt carbon), predicted FD moves with constraint checks, hourly mass balance, and the heat balance in MW.
Everything is a SUGGESTION FOR HUMAN REVIEW on a SYNTHETIC heater: not an instruction, no write path. Thresholds: config/ops_guidance.yaml (ASSUMED).
Run: python -m src.optimize_view --help
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src import chem_advice, combustion as cb, whatif

ROOT = Path(__file__).resolve().parents[1]


def load_ops(path=None):
    return yaml.safe_load(Path(path or ROOT / "config" / "ops_guidance.yaml").read_text(encoding="utf-8"))


def stack_reference(df):
    """Median stack temperature per 1 MW load band from eligible training-split rows (the load-matched expectation, OWN-ESTIMATE)."""
    x = df[(df["split"] == "train") & df["eligibility"].str.startswith("ELIGIBLE")].dropna(subset=["Q_out_MW", "stack_temp_C"]).copy()
    x["band"] = np.floor(x["Q_out_MW"])
    g = x.groupby("band")["stack_temp_C"].agg(["median", "size"])
    g = g[g["size"] >= 30]
    return pd.DataFrame({"q": g.index.to_numpy(float) + 0.5, "t": g["median"].to_numpy()})


def _pick(row, name, default=np.nan):
    v = row.get(name, default)
    return float(v) if pd.notna(v) else default


def snapshot(row, moisture, gate, eff, G, stack_ref, fuel=None, ops=None):
    """gate: advisory record (or fail-safe stub). Returns None if the row lacks the data for a balance (no guesses are made)."""
    fuel, ops = fuel or cb.load_fuel(), ops or load_ops()
    L, O = G["limits"], G["optimizer"]
    o2, lhv, ts, ta = (_pick(row, k) for k in ("O2_pct_dry", "LHV_used_MJkg", "stack_temp_C", "ambient_temp_C"))
    fuel_kgh, q_out = _pick(row, "fuel_rate_aligned_kgh"), _pick(row, "Q_out_MW")
    if not all(np.isfinite(v) for v in (moisture, o2, lhv, ts, ta, fuel_kgh, q_out)):
        return None
    rh = _pick(row, "ambient_RH_pct", 70.0)
    co = _pick(row, "CO_ppm") if row.get("co_available", 0) == 1 else float("nan")
    unb = _pick(row, "unburnt_in_ash_pct")
    unb = unb if np.isfinite(unb) else None
    now = cb.losses(fuel, moisture, lhv, o2, ts, ta, co if np.isfinite(co) else 0.0, unb, rh)
    # best efficiency inside the safety bounds (O2 floor + margin, predicted CO with safety factor)
    grid = np.round(np.arange(3.0, 12.01, 0.1), 2)
    cog = chem_advice.co_curve(row, eff, grid)
    floor = L["o2_floor_pct"] + O["o2_margin_pct"]
    ok = (grid >= floor) & (np.isnan(cog) | (cog * O["co_margin_factor"] <= L["co_limit_ppm"]))
    tot = np.array([cb.losses(fuel, moisture, lhv, g, ts, ta, c if np.isfinite(c) else 0.0, unb, rh)["total"] for g, c in zip(grid, cog)])
    k = int(np.argmin(np.where(ok, tot, np.inf))) if ok.any() else None
    o2_best = float(grid[k]) if k is not None else None
    best = cb.losses(fuel, moisture, lhv, o2_best, ts, ta, float(cog[k]) if (k is not None and np.isfinite(cog[k])) else 0.0, unb, rh) if k is not None else None
    # levers (Delta efficiency, percentage points, each alone)
    lev = []
    def add(name, change, res):
        lev.append({"Lever": name, "Change": change, "Δη (points)": now["total"] - res["total"]})
    if best is not None:
        add("Combustion air (O2)", f"{o2:.1f} → {o2_best:.1f} % O2", best)
    add("Stack temperature", f"−{ops['sensitivity_dt_k']:g} K (clean surfaces)", cb.losses(fuel, moisture, lhv, o2, ts - ops["sensitivity_dt_k"], ta, co if np.isfinite(co) else 0.0, unb, rh))
    m2 = max(moisture - ops["sensitivity_moisture_pts"], 0.0)
    lhv2 = cb.lhv_dry_from_asfired(lhv, moisture) * (1 - m2 / 100) - 2.442 * m2 / 100
    add("Fuel moisture", f"−{ops['sensitivity_moisture_pts']:g} points ({moisture:.0f} → {m2:.0f} %wb)", cb.losses(fuel, m2, lhv2, o2, ts, ta, co if np.isfinite(co) else 0.0, unb, rh))
    if np.isfinite(co) and now["CO"] > 0:
        add("CO burn-out", "CO → 0 ppm", cb.losses(fuel, moisture, lhv, o2, ts, ta, 0.0, unb, rh))
    if unb is not None and unb > 1.0:
        add("Unburnt carbon in ash", f"{unb:.1f} → 1.0 %", cb.losses(fuel, moisture, lhv, o2, ts, ta, co if np.isfinite(co) else 0.0, 1.0, rh))
    # predicted FD moves (grate unchanged)
    fd, gr = _pick(row, "FD_command_pct"), _pick(row, "grate_command_pct")
    cand = []
    for dfd in (-4.0, -2.0, 0.0, 2.0, 4.0):
        try:
            r = whatif.evaluate(row, fd + dfd, gr, eff, G)
        except ValueError:
            continue
        e = cb.losses(fuel, moisture, lhv, r["O2_option_pct"], ts, ta, r["CO_option_ppm"] if np.isfinite(co) else 0.0, unb, rh)
        cand.append({"FD move (%)": dfd, "FD command": fd + dfd, "O2 predicted": r["O2_option_pct"], "CO predicted (ppm)": r["CO_option_ppm"], "Draft predicted (Pa)": r["draft_option_pa"],
                     "η chemistry (%)": e["eta_indirect_pct"], "ΔSFC model (kg/GJ)": r["dSFC_point"], "Checks pass": bool(r["all_pass"])})
    # parameter table
    p, lam_best = [], (float(cb.excess_air_ratio(o2_best)) if o2_best is not None else None)
    def row_(group, name, val, unit, target, status, action, why):
        p.append({"Group": group, "Parameter": name, "Now": val, "Unit": unit, "Target / band": target, "Status": status, "Action": action, "Why": why})
    if o2_best is not None:
        diff = o2 - o2_best
        st, act = ("act", "Reduce air") if diff > ops["o2_tolerance_pct"] else (("act", "Increase air") if o2 < floor else ("ok", "Hold"))
        row_("Air / combustion", "Flue-gas O2", f"{o2:.2f}", "% dry", f"{o2_best:.1f} (floor {floor:.1f})", st, act, "Excess air carries heat up the stack; too little raises CO and unburnt carbon")
        row_("Air / combustion", "Excess air λ", f"{now['lambda']:.2f}", "-", f"{lam_best:.2f}", st, act, "λ = 21 / (21 − O2)")
        fd_t = fd * lam_best / now["lambda"]
        step = float(np.clip(fd_t - fd, -L["max_step_fd_pct"], L["max_step_fd_pct"]))
        row_("Air / combustion", "FD fan command", f"{fd:.1f}", "%", f"{fd_t:.1f} (next step {step:+.1f})", st, "Reduce FD" if step < -0.25 else ("Increase FD" if step > 0.25 else "Hold"),
             "Command, not airflow; air ∝ FD at fixed demand (model assumption); one bounded step at a time")
    dr = _pick(row, "draft_pa")
    lo, hi = L["draft_band_pa"]
    st = "ok" if lo <= dr <= hi else "act"
    row_("Draft", "Furnace draft", f"{dr:.1f}", "Pa", f"{lo:g} … {hi:g} (aim {ops['draft_target_pa']:g})", st, "Hold" if st == "ok" else ("Increase ID (draft too weak)" if dr > hi else "Reduce ID (draft too strong)"),
         "Draft must stay negative; trim ID after any FD change")
    row_("Draft", "ID fan command", f"{_pick(row, 'ID_command_pct'):.1f}", "%", "trim to hold draft", "ok", "Hold", "Follows draft, not efficiency")
    row_("Grate", "Grate command", f"{gr:.1f}", "%", "burn-out", "ok", "Hold", "Change with load and fuel, together with air; guarded by the optimizer")
    if np.isfinite(co):
        warn = co > ops["co_warn_fraction"] * L["co_limit_ppm"]
        row_("Combustion quality", "CO", f"{co:.0f}", "ppm", f"< {ops['co_warn_fraction'] * L['co_limit_ppm']:.0f} (limit {L['co_limit_ppm']:g})", "act" if warn else "ok",
             "Increase air / check grate" if warn else "Hold", "CO means incomplete burn-out")
    else:
        row_("Combustion quality", "CO", "n/a", "ppm", "sensor needed", "watch", "No CO measurement", "Without CO no air advice can be trusted")
    if unb is not None:
        row_("Combustion quality", "Unburnt carbon in ash", f"{unb:.1f}", "%", f"< {ops['unburnt_high_pct']:g}", "act" if unb > ops["unburnt_high_pct"] else "ok",
             "Improve burn-out (air, grate speed)" if unb > ops["unburnt_high_pct"] else "Hold", "Lab value, updated slowly")
    exp_t = float(np.interp(q_out, stack_ref["q"], stack_ref["t"])) if len(stack_ref) else float("nan")
    if np.isfinite(exp_t):
        ex = ts - exp_t
        row_("Heat recovery", "Stack temperature", f"{ts:.0f}", "°C", f"{exp_t:.0f} expected at {q_out:.1f} MW", "act" if ex > ops["stack_excess_k"] else "ok",
             "Clean surfaces / soot-blow" if ex > ops["stack_excess_k"] else "Hold", f"{ex:+.0f} K against the load-matched expectation; fouling raises stack temperature")
    dp = _pick(row, "economizer_dP_pa")
    if np.isfinite(dp):
        row_("Heat recovery", "Economizer ΔP", f"{dp:.0f}", "Pa", f"< {ops['economizer_dp_high_pa']:g}", "act" if dp > ops["economizer_dp_high_pa"] else "ok",
             "Soot-blow / inspect economizer" if dp > ops["economizer_dp_high_pa"] else "Hold", "Rising ΔP means fouling")
    row_("Fuel", "Fuel moisture", f"{moisture:.1f}", "% wb", f"< {ops['moisture_high_pct']:g}", "act" if moisture > ops["moisture_high_pct"] else "ok",
         "Dry or blend fuel (not a real-time lever)" if moisture > ops["moisture_high_pct"] else "Hold", "Water in fuel lowers LHV and adds vapour loss")
    tout, sp = _pick(row, "HTF_Tout_C"), _pick(row, "HTF_Tout_SP_C")
    if np.isfinite(sp):
        dev = tout - sp
        row_("HTF side", "HTF supply temperature", f"{tout:.1f}", "°C", f"{sp:.1f} set point", "watch" if abs(dev) > ops["htf_tout_dev_k"] else "ok",
             "Check load / bypass" if abs(dev) > ops["htf_tout_dev_k"] else "Hold", f"{dev:+.1f} K from set point")
    row_("HTF side", "HTF flow / ΔT", f"{_pick(row, 'HTF_flow_m3h'):.0f} / {_pick(row, 'HTF_Tout_C') - _pick(row, 'HTF_Tin_C'):.1f}", "m³/h / K", "process demand", "ok", "Hold", "Demand-driven, not an efficiency lever")
    row_("Electricity", "Fan power FD + ID", f"{_pick(row, 'fan_power_kW_FD') + _pick(row, 'fan_power_kW_ID'):.1f}", "kW", "lower with less air", "ok", "Hold", "Fan power rises roughly with the cube of fan speed")
    # heat and mass balance
    q_in = fuel_kgh * lhv / 3600.0
    mw = {n: now[n] / 100.0 * q_in for n in ("dry_flue_gas", "water_vapour", "CO", "unburnt_carbon", "radiation_other")}
    unacc = q_in - q_out - sum(mw.values())
    mb = cb.mass_balance(fuel, moisture, o2, fuel_kgh, ta, rh)
    watch = [r for r in p if r["Status"] in ("act",)]
    actions = [f"{r['Action']}: {r['Parameter']} {r['Now']} {r['Unit']} → {r['Target / band']}" for r in watch]
    return {"now": now, "best": best, "o2_best": o2_best, "eta_best": best["eta_indirect_pct"] if best else None, "floor": floor,
            "eta_heat_balance": q_out / q_in * 100.0, "params": pd.DataFrame(p), "levers": pd.DataFrame(lev).sort_values("Δη (points)", ascending=False),
            "candidates": pd.DataFrame(cand), "q_in": q_in, "q_out": q_out, "loss_mw": mw, "unaccounted_mw": unacc, "mass": mb, "actions": actions,
            "gate": gate.get("decision", "NO_ADVICE"), "gate_codes": gate.get("reason_codes", []), "co_measured": bool(np.isfinite(co)),
            "curve": pd.DataFrame({"O2_pct": grid, "total_loss": tot, "allowed": ok})}


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()


if __name__ == "__main__":
    main()
