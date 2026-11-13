"""Features at time t for the next-interval fuel forecast. Trailing information only (rule 5).

y = mean fuel_rate_measured_kgh over t+1..t+3. Fuel at t, Q_in, eta, SFC and any truth/label column are never inputs.
Run: python -m src.features --help
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STEP = pd.Timedelta(minutes=5)
BED_TAU_MIN = 15.0  # assumption A15 (bed lag 10-20 min)
SETTINGS = ["FD_command_pct", "ID_command_pct", "grate_command_pct"]
FEATURES = [
    "Q_out_MW", "Q_out_lag1", "Q_out_lag2", "Q_out_lag3",
    "fuel_lag1", "fuel_lag2", "fuel_lag3", "fuel_lag_mean_1_6",
    "bed_moisture_wb_pct", "bed_LHV_MJkg", "lhv_known",
    "O2_pct_dry", "CO_ppm", "co_available",
    *SETTINGS,
    "furnace_temp_C", "flue_temp_C", "stack_temp_C", "economizer_dP_pa", "draft_pa",
    "ambient_temp_C", "ambient_RH_pct", "HTF_Tout_SP_C", "feeder_speed_pct",
    "min_since_sootblow", "min_since_lot_change",
]
FEATURES_C0 = [f for f in FEATURES if f not in SETTINGS]
LOT_FEATURES = ["bed_moisture_wb_pct", "bed_LHV_MJkg", "lhv_known", "min_since_lot_change"]
FEATURES_NOFEED = [f for f in FEATURES_C0 if f != "feeder_speed_pct"]   # ablation: feeder speed is a proxy for fuel at t
FEATURES_NOLOT = [f for f in FEATURES_C0 if f not in LOT_FEATURES]
FEATURES_NOCO = [f for f in FEATURES_C0 if f not in ("CO_ppm", "co_available")]
# info-matched linear model L: numeric C0 features without NaN-prone or constant columns
FEATURES_L = [f for f in FEATURES_C0 if f not in ("CO_ppm", "HTF_Tout_SP_C", "lhv_known", "min_since_sootblow")]
FORBIDDEN_EXACT = {
    "Q_in_MW", "Q_in_lo_MW", "Q_in_hi_MW", "eta_pct", "eta_lo_pct", "eta_hi_pct", "SFC_kg_GJ", "SFC_u_kg_GJ", "SFC_lo_kg_GJ",
    "SFC_hi_kg_GJ", "SFC_win_kg_GJ", "Q_out_win_MW", "fuel_rate_measured_kgh", "fuel_rate_aligned_kgh", "fuel_rate_true_kgh",
    "fuel_totalizer_kg", "fuel_kg_interval_totalizer", "fuel_ash_pct", "unburnt_in_ash_pct", "scenario_id", "is_fault_injected",
    "true_synthetic_best_action", "eligibility", "advice_eligibility", "quality_flag", "best_action_eta_gain_pp",
}
FORBIDDEN_PREFIX = ("true_", "truth", "rep_", "gen_", "eta_", "SFC_", "Q_in", "moisture_true", "LHV_true", "fuel_burn", "fuel_feed")


def assert_no_forbidden(cols):
    bad = [c for c in cols if c in FORBIDDEN_EXACT or c.startswith(FORBIDDEN_PREFIX)]
    if bad:
        raise ValueError(f"forbidden model inputs: {bad}")


def load_clean(path=None):
    d = pd.read_csv(path or ROOT / "data" / "clean" / "clean_heater_c.csv")
    d["t"] = pd.to_datetime(d["timestamp_local"], utc=True)
    return d


def build(d, tau=BED_TAU_MIN):
    """Return one row per clean row: keys, FEATURES, target y, flags. `d` must be time-ordered clean rows."""
    d = d.sort_values("t").reset_index(drop=True)
    grid = pd.date_range(d["t"].iloc[0], d["t"].iloc[-1], freq=STEP)
    g = d.set_index("t").reindex(grid)  # missing 5-min rows become NaN rows; shifts are then exact
    fuel = g["fuel_rate_measured_kgh"]
    out = pd.DataFrame(index=grid)
    out["Q_out_MW"] = g["Q_out_MW"]
    for k in (1, 2, 3):
        out[f"Q_out_lag{k}"] = g["Q_out_MW"].shift(k)
        out[f"fuel_lag{k}"] = fuel.shift(k)
    out["fuel_lag_mean_1_6"] = pd.concat([fuel.shift(k) for k in range(1, 7)], axis=1).mean(axis=1, skipna=False)
    # target: mean over t+1..t+3, all three required
    fut = pd.concat([fuel.shift(-k) for k in (1, 2, 3)], axis=1)
    out["y"] = fut.mean(axis=1, skipna=False)
    # lot features: lab values only for assayed lots (never filled across unknown lots)
    t = pd.Series(grid, index=grid)
    lot = g["fuel_lot"]
    start = t.where(lot.notna()).groupby(lot).transform("min")
    since_lot = (t - start).dt.total_seconds() / 60.0
    lots = g.dropna(subset=["fuel_lot"]).groupby("fuel_lot", sort=False).agg(
        m=("fuel_moisture_wb_pct", "first"), lhv=("fuel_LHV_asfired_MJkg", "first"), known=("lhv_known", "first"))
    prev = lots.shift(1)
    cur_m, cur_l = lot.map(lots["m"]), lot.map(lots["lhv"])
    prv_m, prv_l = lot.map(prev["m"]), lot.map(prev["lhv"])
    w_prev = np.exp(-since_lot / tau)
    first_lot = lot == lots.index[0]
    for name, cur, prv in (("bed_moisture_wb_pct", cur_m, prv_m), ("bed_LHV_MJkg", cur_l, prv_l)):
        mix = (1 - w_prev) * cur + w_prev * prv
        # first lot: no predecessor; unknown predecessor: only trusted long after the change; unknown current: NaN
        val = np.where(first_lot, cur, np.where(prv.notna(), mix, np.where(since_lot >= 30, cur, np.nan)))
        out[name] = pd.Series(val, index=grid).where(cur.notna())
    out["lhv_known"] = g["lhv_known"]
    out["min_since_lot_change"] = since_lot
    ss = t.where(g["sootblow"] == 1).ffill()
    out["min_since_sootblow"] = ((t - ss).dt.total_seconds() / 60.0).where(ss.notna())
    for c in ("O2_pct_dry", "CO_ppm", "co_available", *SETTINGS, "furnace_temp_C", "flue_temp_C", "stack_temp_C", "economizer_dP_pa",
              "draft_pa", "ambient_temp_C", "ambient_RH_pct", "HTF_Tout_SP_C", "feeder_speed_pct"):
        out[c] = g[c]
    out = out.reindex(d["t"])  # back to the original (present) rows
    keys = d[["timestamp_local", "t", "fuel_lot", "operating_mode", "fan_derated", "fuel_mass_basis", "eligibility", "Q_out_MW"]].copy()
    keys = keys.rename(columns={"Q_out_MW": "load_MW"})
    F = pd.concat([keys.reset_index(drop=True), out.reset_index(drop=True)], axis=1)
    F["eligible"] = F["eligibility"].str.startswith(("ELIGIBLE", "DIAGNOSTIC_ONLY"))
    F["has_target"] = F["y"].notna()
    F["has_lag1"] = F["fuel_lag1"].notna()
    return F


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean", default=None)
    a = ap.parse_args()
    F = build(load_clean(a.clean))
    assert_no_forbidden(FEATURES)
    print(f"rows {len(F)}, eligible with target {int((F.eligible & F.has_target).sum())}, features {len(FEATURES)}")


if __name__ == "__main__":
    main()
