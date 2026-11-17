"""Combustion chemistry for a biomass (palm-kernel-shell) grate furnace: stoichiometry, excess air, flue gas and the indirect heat-loss balance.

Chemistry used (all per kg of AS-FIRED fuel, LHV basis):
  O2 needed (kmol)  = C/12 + H/4 + S/32 - O/32              (complete combustion to CO2, H2O, SO2)
  stoichiometric air = O2 needed / 0.2095
  excess-air ratio   lambda = 21 / (21 - O2_dry)             (dry-flue-gas O2 in vol %, CO small)
  dry flue gas (kmol) = CO2 + SO2 + N2(fuel + 0.7905 lambda air) + O2 excess
  losses (% of LHV): dry flue gas  n_dfg * Mcp * (T_stack - T_amb) / LHV
                     water vapour (sensible, latent is already inside LHV)  m_H2O * cp_v * (T_stack - T_amb) / LHV
                     CO     n_CO * 283 MJ/kmol / LHV         unburnt carbon in ash   m_C * 32.8 MJ/kg / LHV
                     radiation and other = ASSUMED constant
  indirect efficiency = 100 - sum of losses.
Fuel analysis is ASSUMED (config/fuel_properties.yaml). Results are OWN-ESTIMATE, SYNTHETIC context, never plant values.
Run: python -m src.combustion --help
"""
import argparse
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_fuel(path=None):
    return yaml.safe_load(Path(path or ROOT / "config" / "fuel_properties.yaml").read_text(encoding="utf-8"))


def humidity_ratio(t_c, rh_pct):
    """kg water per kg dry air (Magnus formula for saturation pressure, 101.325 kPa)."""
    psat = 0.61094 * np.exp(17.625 * t_c / (t_c + 243.04))
    pv = np.clip(rh_pct, 0, 100) / 100.0 * psat
    return 0.622 * pv / (101.325 - pv)


def composition_ar(fuel, moisture_wb_pct):
    """kg of each element per kg as-fired fuel (dry analysis scaled by 1 - moisture)."""
    f = 1.0 - float(moisture_wb_pct) / 100.0
    u = fuel["ultimate_dry_wt_pct"]
    c = {k: u[k] / 100.0 * f for k in ("C", "H", "O", "N", "S", "ash")}
    c["M"] = float(moisture_wb_pct) / 100.0
    return c


def lhv_dry_from_asfired(lhv_ar_mj_kg, moisture_wb_pct, latent=2.442):
    """Back out the dry-basis LHV: LHV_ar = LHV_dry (1 - M) - latent M  (evaporating the fuel moisture)."""
    m = float(moisture_wb_pct) / 100.0
    return (lhv_ar_mj_kg + latent * m) / (1.0 - m)


def stoichiometry(fuel, moisture_wb_pct):
    c = composition_ar(fuel, moisture_wb_pct)
    o2 = c["C"] / 12.0 + c["H"] / 4.0 + c["S"] / 32.0 - c["O"] / 32.0
    air = o2 / fuel["air_o2_vol_frac"]
    return {"o2_kmol": o2, "air_kmol": air, "air_kg": air * fuel["mw_air_kg_kmol"], "comp": c}


def excess_air_ratio(o2_dry_pct):
    o2 = np.asarray(o2_dry_pct, float)
    return 21.0 / (21.0 - o2)


def flue_gas(fuel, moisture_wb_pct, o2_dry_pct, co_ppm=0.0, t_amb=30.0, rh=70.0):
    """Dry and wet flue gas per kg fuel (kmol and kg)."""
    st = stoichiometry(fuel, moisture_wb_pct)
    c, lam = st["comp"], float(excess_air_ratio(o2_dry_pct))
    air = lam * st["air_kmol"]
    n_co2_all = c["C"] / 12.0
    n_so2, n_n2 = c["S"] / 32.0, c["N"] / 28.0 + 0.7905 * air
    n_o2 = fuel["air_o2_vol_frac"] * (lam - 1.0) * st["air_kmol"]
    n_dry = n_co2_all + n_so2 + n_n2 + n_o2
    n_co = float(co_ppm) * 1e-6 * n_dry if np.isfinite(co_ppm) else 0.0
    h2o_fuel = c["H"] / 2.0 + c["M"] / 18.0
    w = float(humidity_ratio(t_amb, rh))
    h2o_air = w * air * fuel["mw_air_kg_kmol"] / 18.0
    return {"lambda": lam, "n_dry": n_dry, "n_co": n_co, "n_h2o_fuel": h2o_fuel, "n_h2o_air": h2o_air, "air_kg": air * fuel["mw_air_kg_kmol"],
            "n_wet": n_dry + h2o_fuel + h2o_air, "st": st}


def losses(fuel, moisture_wb_pct, lhv_ar_mj_kg, o2_dry_pct, t_stack_c, t_amb_c, co_ppm=0.0, unburnt_in_ash_pct=None, rh=70.0):
    """Indirect-method loss balance, percent of LHV. Returns dict of named losses, their sum and the indirect efficiency."""
    fg = flue_gas(fuel, moisture_wb_pct, o2_dry_pct, co_ppm, t_amb_c, rh)
    lhv_kj = float(lhv_ar_mj_kg) * 1000.0
    dT = float(t_stack_c) - float(t_amb_c)
    dry = fg["n_dry"] * fuel["mcp_dry_flue_kj_kmolk"] * dT / lhv_kj * 100.0
    vap = (fg["n_h2o_fuel"] + fg["n_h2o_air"]) * 18.0 * fuel["cp_vapour_kj_kgk"] * dT / lhv_kj * 100.0
    co = fg["n_co"] * fuel["heat_of_combustion_co_kj_kmol"] / lhv_kj * 100.0
    u = fuel["default_unburnt_in_ash_pct"] if unburnt_in_ash_pct is None or not np.isfinite(unburnt_in_ash_pct) else float(unburnt_in_ash_pct)
    ash_kg = fg["st"]["comp"]["ash"]
    c_unburnt_kg = ash_kg * u / (100.0 - u)
    unb = c_unburnt_kg * fuel["heat_of_combustion_c_mj_kg"] * 1000.0 / lhv_kj * 100.0
    rad = float(fuel["radiation_other_loss_pct"])
    tot = dry + vap + co + unb + rad
    return {"dry_flue_gas": dry, "water_vapour": vap, "CO": co, "unburnt_carbon": unb, "radiation_other": rad, "total": tot,
            "eta_indirect_pct": 100.0 - tot, "lambda": fg["lambda"], "air_kg_per_kg": fg["air_kg"], "stoich_air_kg_per_kg": fg["st"]["air_kg"],
            "dry_flue_kmol_per_kg": fg["n_dry"], "wet_flue_kmol_per_kg": fg["n_wet"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--o2", type=float, default=7.0)
    ap.add_argument("--moisture", type=float, default=17.0)
    ap.add_argument("--lhv", type=float, default=15.0)
    ap.add_argument("--stack", type=float, default=230.0)
    ap.add_argument("--amb", type=float, default=30.0)
    a = ap.parse_args()
    r = losses(load_fuel(), a.moisture, a.lhv, a.o2, a.stack, a.amb)
    print({k: round(v, 3) for k, v in r.items()})


if __name__ == "__main__":
    main()
