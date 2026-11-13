"""SPEC C3 energy engineering with uncertainty and per-row status.

m_HTF = V/3600 x rho(Tmean); Q_out = m x integral cp dT; Q_in = m_fuel x LHV; eta = 100 Q_out/Q_in;
SFC kg/GJ = fuel / (3.6 Q_out) = 1 / (eta x LHV[GJ/kg]).  Startup/standby excluded; auxiliaries outside.
Status per quantity: CALCULATED | ESTIMATED | UNAVAILABLE.  LHV is never invented: unknown LHV gives an interval
from lab-assayed lots in the trailing days (or the C5 envelope), and no point eta.

Run: python -m src.engineering --help
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning import load_cfg
from src.units import HTFTable, MKCAL_H_TO_MW

ROOT = Path(__file__).resolve().parents[1]
OPERATING = ("STEADY", "RAMP")


def heat_with_uncertainty(V, Tin, Tout, cfg, tab=None):
    """Q_out (MW) with standard uncertainty: flow +-2 %, dT +-0.5 K (quadrature). Arrays in, arrays out."""
    tab = tab or HTFTable()
    V, Tin, Tout = (np.asarray(x, float) for x in (V, Tin, Tout))
    ok = tab.in_range(np.nan_to_num(Tin, nan=-1)) & tab.in_range(np.nan_to_num(Tout, nan=-1)) & ~np.isnan(V)
    Ts, To, Vs = np.where(ok, Tin, tab.tmin), np.where(ok, Tout, tab.tmin), np.where(ok, V, 0.0)
    q = np.where(ok, tab.heat_mw(Vs, Ts, To), np.nan)
    m = np.where(ok, Vs / 3600.0 * tab.rho((Ts + To) / 2), np.nan)
    dT = To - Ts
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.sqrt(cfg["unc"]["flow_rel"] ** 2 + (cfg["unc"]["dT_K"] / np.where(np.abs(dT) > 1e-9, dT, np.nan)) ** 2)
    return q, q * rel, m


def trailing_lhv_band(df, cfg):
    """(lo, hi, basis) per row for rows with unknown LHV: min/max of assayed lots started in the trailing window
    before the row (strictly earlier); falls back to the C5 envelope. Never a point value."""
    t = pd.to_datetime(df["timestamp_local"], utc=True)
    lots = df[df["lhv_known"] == 1].groupby("fuel_lot").agg(t0=("timestamp_local", "first"), lhv=("fuel_LHV_asfired_MJkg", "first"))
    lots["t0"] = pd.to_datetime(lots["t0"], utc=True)
    lots = lots.sort_values("t0")
    t0 = lots["t0"].to_numpy("datetime64[ns]")
    lv = lots["lhv"].to_numpy()
    lo = np.full(len(df), cfg["lhv_band"]["envelope_mjkg"][0])
    hi = np.full(len(df), cfg["lhv_band"]["envelope_mjkg"][1])
    basis = np.full(len(df), "ENVELOPE_BAND", dtype=object)
    win = np.timedelta64(int(cfg["lhv_band"]["trailing_days"] * 24 * 3600), "s")
    tn = t.to_numpy("datetime64[ns]")
    for i in np.where(df["lhv_known"].to_numpy() == 0)[0]:
        a = np.searchsorted(t0, tn[i] - win, "left")
        b = np.searchsorted(t0, tn[i], "left")
        if b - a >= cfg["lhv_band"]["min_lots"]:
            lo[i], hi[i], basis[i] = lv[a:b].min(), lv[a:b].max(), "TRAILING_LOT_BAND"
    return lo, hi, basis


def compute(df, cfg=None):
    """Add engineering columns to a cleaned frame (not modified in place)."""
    cfg = cfg or load_cfg()
    u, z = cfg["unc"], cfg["unc"]["z95"]
    tab = HTFTable()
    x = df.copy()
    q, uq, m = heat_with_uncertainty(x["HTF_flow_m3h"], x["HTF_Tin_C"], x["HTF_Tout_C"], cfg, tab)
    x["m_HTF_kgs"], x["Q_out_MW"], x["Q_out_u_MW"] = m, q, uq
    x["Q_out_lo_MW"], x["Q_out_hi_MW"] = q - z * uq, q + z * uq
    op = x["operating_mode"].isin(OPERATING).to_numpy()
    steady = (x["operating_mode"] == "STEADY").to_numpy()
    bypass = (x["heat_balance_status"] == "UNVERIFIED").to_numpy()
    qok = ~np.isnan(q) & op
    st_q = np.where(qok & steady & ~bypass, "CALCULATED", np.where(qok, "ESTIMATED", "UNAVAILABLE"))
    x["status_Q_out"] = st_q
    # fuel and LHV
    fuel = x["fuel_rate_aligned_kgh"].to_numpy(float)
    uf = x["fuel_rel_unc"].to_numpy(float)
    known = (x["lhv_known"] == 1).to_numpy() & x["fuel_LHV_asfired_MJkg"].notna().to_numpy()
    lhv = np.where(known, x["fuel_LHV_asfired_MJkg"], np.nan)
    lo_b, hi_b, basis = trailing_lhv_band(x, cfg)
    x["LHV_used_MJkg"] = lhv
    x["LHV_lo_MJkg"] = np.where(known, lhv - z * u["lhv_lab_abs_mjkg"], lo_b)
    x["LHV_hi_MJkg"] = np.where(known, lhv + z * u["lhv_lab_abs_mjkg"], hi_b)
    x["LHV_basis"] = np.where(known, "LAB_LOT", basis)
    fok = ~np.isnan(fuel) & op
    x["Q_in_MW"] = fuel / 3600.0 * lhv
    x["Q_in_lo_MW"] = fuel * (1 - z * uf) / 3600.0 * x["LHV_lo_MJkg"]
    x["Q_in_hi_MW"] = fuel * (1 + z * uf) / 3600.0 * x["LHV_hi_MJkg"]
    belt = (x["fuel_mass_basis"] == "WEIGH_BELT").to_numpy()
    x["status_Q_in"] = np.where(~fok, "UNAVAILABLE", np.where(known & belt & steady, "CALCULATED", "ESTIMATED"))
    # eta (point only when LHV is a lab value)
    with np.errstate(divide="ignore", invalid="ignore"):
        eta = 100.0 * q / x["Q_in_MW"].to_numpy()
        rel_eta = np.sqrt((uq / q) ** 2 + uf ** 2 + (u["lhv_lab_abs_mjkg"] / lhv) ** 2)
        x["eta_pct"] = np.where(qok & fok & known & ~bypass, eta, np.nan)
        x["eta_lo_pct"] = np.where(known, x["eta_pct"] * (1 - z * rel_eta), 100.0 * x["Q_out_lo_MW"] / x["Q_in_hi_MW"])
        x["eta_hi_pct"] = np.where(known, x["eta_pct"] * (1 + z * rel_eta), 100.0 * x["Q_out_hi_MW"] / x["Q_in_lo_MW"])
    have_int = qok & fok & ~bypass
    x.loc[~have_int, ["eta_pct", "eta_lo_pct", "eta_hi_pct"]] = np.nan
    x["status_eta"] = np.where(~have_int, "UNAVAILABLE",
                               np.where(known & belt & steady & (st_q == "CALCULATED"), "CALCULATED", "ESTIMATED"))
    # SFC (does not need LHV: kg fuel per GJ useful heat)
    with np.errstate(divide="ignore", invalid="ignore"):
        sfc = np.where(qok & fok & (q > 0.5) & (fuel > 0) & ~bypass, fuel / (3.6 * q), np.nan)
        rel_s = np.sqrt((uq / q) ** 2 + uf ** 2)
    x["SFC_kg_GJ"], x["SFC_u_kg_GJ"] = sfc, sfc * rel_s
    x["SFC_lo_kg_GJ"], x["SFC_hi_kg_GJ"] = sfc * (1 - z * rel_s), sfc * (1 + z * rel_s)
    x["status_SFC"] = np.where(np.isnan(sfc), "UNAVAILABLE", np.where(belt & steady & (st_q == "CALCULATED"), "CALCULATED", "ESTIMATED"))
    # trailing window ratio of sums (reduces bed-lag noise); needs a contiguous full window
    n = cfg["stable_steps"]
    t = pd.to_datetime(x["timestamp_local"], utc=True)
    contiguous = (t.diff() == pd.Timedelta(minutes=cfg["step_min"])).to_numpy()
    win_ok = pd.Series(contiguous).astype(int).rolling(n - 1).sum().to_numpy() == n - 1
    fs, qs = pd.Series(np.where(np.isnan(sfc), np.nan, fuel)), pd.Series(np.where(np.isnan(sfc), np.nan, q))
    with np.errstate(divide="ignore", invalid="ignore"):
        w = fs.rolling(n, min_periods=n).sum() / (3.6 * qs.rolling(n, min_periods=n).sum())
    x["SFC_win_kg_GJ"] = np.where(win_ok, w, np.nan)
    x["Q_out_win_MW"] = np.where(win_ok, qs.rolling(n, min_periods=n).mean(), np.nan)
    x["row_status"] = x["status_SFC"]
    return x


def layer1_layer2(x, cfg):
    """SPEC C7 layer 1 (data) and layer 2 (constraints). Returns reason-code strings: ELIGIBLE,
    DIAGNOSTIC_ONLY:NO_CO or NO_ADVICE:<codes>."""
    mode = x["operating_mode"].to_numpy()
    st = x["status_SFC"].to_numpy()
    eta = x["eta_pct"].to_numpy()
    codes = {
        "TRANSIENT": (mode != "STEADY") & ~np.isin(mode, ["TRIP", "FEEDER_STOP"]) | (x["sootblow"] > 0).to_numpy() | (x["after_gap"] > 0).to_numpy(),
        "LOW_FUEL_CONF": (x["fuel_mass_basis"] == "VOLUMETRIC").to_numpy() | (x["lhv_known"] == 0).to_numpy() | (mode == "FEEDER_STOP")
        | (x["totalizer_reset"] > 0).to_numpy() | np.isnan(x["fuel_rate_aligned_kgh"].to_numpy()),
        "BAD_FLOW": (x["HTF_flow_m3h"] < cfg["flow_valid_m3h"][0] * 0.98).to_numpy() | (x["HTF_flow_m3h"] > cfg["flow_valid_m3h"][1] * 1.02).to_numpy(),
        "STALE_DATA": x["frozen_signals"].astype(str).str.len().gt(0).to_numpy(),
        "ENERGY_BALANCE": (x["heat_balance_status"] == "UNVERIFIED").to_numpy()
        | ((mode == "STEADY") & ~np.isnan(eta) & ((eta < 100 * cfg["eta_valid"][0]) | (eta > 100 * cfg["eta_valid"][1]))),
        "TRIP_ACTIVE": (x["interlock_active"] > 0).to_numpy() | (x["alarm_code"].fillna("") .isin(["ALM_TRIP_DRAFT", "ALM_FEEDER_STOP", "ALM_HTF_T_HIGH", "ALM_FURNACE_T_HIGH"])).to_numpy(),
        "FAN_DERATE": (x["fan_derated"] > 0).to_numpy(),
        "CMD_FEEDBACK": (x["cmd_feedback_mismatch"] > 0).to_numpy(),
        "UNSAFE_DRAFT": ((x["draft_pa"] < cfg["draft_band_pa"][0]) | (x["draft_pa"] > cfg["draft_band_pa"][1])).to_numpy(),
        "HIGH_TEMP": ((x["furnace_temp_C"] > cfg["furnace_temp_limit_c"]) | (x["HTF_Tout_C"] > cfg["htf_out_limit_c"])).to_numpy(),
        "LOW_O2": (x["O2_pct_dry"] < cfg["o2_floor"]).to_numpy(),
        "HIGH_CO": (x["CO_ppm"] > cfg["co_limit_ppm"]).to_numpy(),
        "NO_DATA": (st == "UNAVAILABLE") & ~np.isin(mode, ["STARTUP", "STANDBY", "TRIP", "FEEDER_STOP"]),
    }
    blocking = np.zeros(len(x), bool)
    for v in codes.values():
        blocking |= v
    t = pd.to_datetime(x["timestamp_local"], utc=True)
    contig = (t.diff() == pd.Timedelta(minutes=cfg["step_min"])).to_numpy()
    run = np.zeros(len(x), int)
    for i in range(len(x)):
        run[i] = 0 if blocking[i] else (run[i - 1] + 1 if i > 0 and contig[i] else 1)
    out = np.full(len(x), "ELIGIBLE", dtype=object)
    short = ~blocking & (run < cfg["stable_steps"])
    out[~blocking & ~short & (x["co_available"] == 0).to_numpy()] = "DIAGNOSTIC_ONLY:NO_CO"
    for i in np.where(blocking | short)[0]:
        out[i] = "NO_ADVICE:" + ";".join([k for k, v in codes.items() if v[i]] or ["TRANSIENT"])
    return pd.Series(out, index=x.index)


def daily_energy(df, step_min=5):
    """Integrate heat per day: MWh, GJ and Mkcal (1 Mkcal/h = 1.16222 MW), and fuel kg from rate and totalizer."""
    t = pd.to_datetime(df["timestamp_local"], utc=True).dt.tz_convert("Asia/Bangkok")
    h = step_min / 60.0
    g = df.assign(_d=t.dt.date).groupby("_d")
    out = pd.DataFrame({
        "rows": g.size(),
        "Q_out_MWh": g["Q_out_MW"].sum(min_count=1) * h,
    })
    out["Q_out_GJ"] = out["Q_out_MWh"] * 3.6
    out["Q_out_Mkcal"] = out["Q_out_MWh"] / MKCAL_H_TO_MW
    out["fuel_kg_rate"] = g["fuel_rate_measured_kgh"].sum(min_count=1) * h
    if "fuel_kg_interval_totalizer" in df:
        out["fuel_kg_totalizer"] = g["fuel_kg_interval_totalizer"].sum(min_count=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean", default="data/clean/clean_heater_c.csv")
    ap.parse_args()
    print("engineering runs inside the pipeline clean stage: python -m src.pipeline --stage clean")


if __name__ == "__main__":
    main()
