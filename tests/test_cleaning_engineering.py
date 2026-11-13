"""Phase 2 tests: cleaning, engineering (SPEC C3), eligibility flags and baseline mechanics. Small hand-built frames."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from src import baseline, cleaning, engineering, units

CFG = cleaning.load_cfg()
ROOT = cleaning.ROOT
RAW = ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv"


def mk(n=40, seed=0, start="2026-01-05 00:00:00", **over):
    """Valid raw frame: steady, weigh belt, lab LHV 15, ~8 MW. Noise keeps sensors from looking frozen."""
    r = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=n, freq="5min").strftime("%Y-%m-%d %H:%M:%S")
    fuel = 2850 + r.normal(0, 20, n)
    df = pd.DataFrame({
        "timestamp_local": ts, "heater_id": "HEATER_C_SYNTHETIC", "operating_mode": "STEADY", "fuel_lot": "LOT-0001",
        "fuel_moisture_wb_pct": 17.0, "fuel_LHV_asfired_MJkg": 15.0, "lhv_known": 1, "fuel_rate_true_kgh": fuel,
        "fuel_rate_measured_kgh": fuel, "fuel_totalizer_kg": np.cumsum(fuel * 5 / 60),
        "HTF_flow_m3h": 700 + r.normal(0, 3, n), "HTF_Tin_C": 260 + r.normal(0, 0.1, n), "HTF_Tout_C": 280 + r.normal(0, 0.1, n),
        "HTF_rho_kgm3": 791.0, "HTF_cp_kJkgK": 2.61, "Q_out_MW": 8.04, "Q_in_MW": 11.9, "eta_direct_pct": 67.6, "SFC_kg_GJ": 98.4,
        "O2_pct_dry": 7 + r.normal(0, 0.1, n), "CO_ppm": 50 + r.normal(0, 3, n), "co_available": 1, "FD_command_pct": 55.0,
        "ID_command_pct": 66.0, "grate_command_pct": 40.0, "furnace_temp_C": 800 + r.normal(0, 2, n), "flue_temp_C": 300 + r.normal(0, 1, n),
        "draft_pa": -35 + r.normal(0, 0.5, n), "fan_derated": 0, "sootblow": 0, "interlock_active": 0, "quality_flag": "OK",
        "advice_eligibility": "", "true_synthetic_best_action": "HOLD", "scenario_id": "STEADY", "is_fault_injected": 0,
        "HTF_bypass_pct": 0.0, "HTF_pump_status": 1, "ambient_RH_pct": 70.0, "fan_power_kW_FD": 45 * 0.55 ** 3, "fan_power_kW_ID": 75 * 0.66 ** 3,
        "feeder_speed_pct": fuel / 50.0, "fuel_mass_basis": "WEIGH_BELT", "alarm_code": "",
    })
    for k, v in over.items():
        df[k] = v
    return df


def jit(n, base):
    """Constant operating point plus a micro-ramp so the frozen-sensor check does not (correctly) reject it."""
    return base + 1e-6 * np.arange(n)


def run(df, lag=0):
    good, rej, rep = cleaning.clean(df, CFG, lag_steps=lag)
    full = engineering.compute(good, CFG)
    full["eligibility"] = engineering.layer1_layer2(full, CFG)
    return full, rej, rep


# ---- hand-worked cases (linear table: rho = 820 - (T-150) x 40/170, cp = 2.40 + (T-150) x 0.30/170)
def test_hand_case_a_heat_matches_code_within_0p1_percent():
    # V=700, Tin 260, Tout 280, Tmean 270: rho 791.765, m 153.954 kg/s, cp 2.61176, integral 52.2353 kJ/kg -> 8.04185 MW
    q, uq, m = engineering.heat_with_uncertainty([700.0], [260.0], [280.0], CFG)
    assert q[0] == pytest.approx(8.041845, rel=1e-3)
    assert m[0] == pytest.approx(153.954, rel=1e-3)
    assert uq[0] == pytest.approx(0.257465, rel=1e-3)  # sqrt(0.02^2 + (0.5/20)^2) x Q


def test_hand_case_b_second_operating_point_and_eta_sfc():
    # V=520, Tin 255.5, Tout 278: rho(266.75)=792.529, m=114.476, cp=2.60603, integral 58.6357 -> 6.71240 MW
    q, _, _ = engineering.heat_with_uncertainty([520.0], [255.5], [278.0], CFG)
    assert q[0] == pytest.approx(6.712404, rel=1e-3)
    # eta/SFC on case A with fuel 2850 kg/h, LHV 15: Q_in 11.875 MW, eta 67.72 %, SFC 98.4434 kg/GJ = 1/(eta x 0.015)
    df = mk(40, HTF_flow_m3h=jit(40, 700.0), HTF_Tin_C=jit(40, 260.0), HTF_Tout_C=jit(40, 280.0), fuel_rate_measured_kgh=jit(40, 2850.0), feeder_speed_pct=jit(40, 57.0))
    full, _, _ = run(df)
    r = full.iloc[-1]
    assert r["eta_pct"] == pytest.approx(67.7208, rel=1e-3)
    assert r["SFC_kg_GJ"] == pytest.approx(98.4434, rel=1e-3)
    assert r["SFC_kg_GJ"] == pytest.approx(units.sfc_kg_gj(r["eta_pct"] / 100, 15.0), rel=1e-3)


def test_mkcal_per_hour_and_mw_roundtrip():
    assert units.mkcal_h_to_mw(10.0) == pytest.approx(11.6222, rel=1e-4)
    assert units.mw_to_mkcal_h(units.mkcal_h_to_mw(7.3)) == pytest.approx(7.3, rel=1e-9)


def test_daily_integration_energy_and_fuel():
    df = mk(288, HTF_flow_m3h=jit(288, 700.0), HTF_Tin_C=jit(288, 260.0), HTF_Tout_C=jit(288, 280.0))
    df["fuel_rate_measured_kgh"] = jit(288, 3000.0)
    df["fuel_totalizer_kg"] = np.arange(1, 289) * 250.0
    df["feeder_speed_pct"] = jit(288, 60.0)
    full, _, _ = run(df)
    full["Q_out_MW"] = 8.0
    de = engineering.daily_energy(full).iloc[0]
    assert de["Q_out_MWh"] == pytest.approx(192.0, rel=1e-6) and de["Q_out_GJ"] == pytest.approx(691.2, rel=1e-6)
    assert de["Q_out_Mkcal"] == pytest.approx(192.0 / 1.16222, rel=1e-6)
    assert de["fuel_kg_rate"] == pytest.approx(72000.0, rel=1e-6)
    assert de["fuel_kg_totalizer"] == pytest.approx(72000.0 - 250.0, rel=1e-3)  # first interval has no predecessor


# ---- cleaning
def test_totalizer_reset_increments_and_flag():
    df = pd.DataFrame({"fuel_totalizer_kg": [100.0, 200.0, 300.0, 50.0, 150.0]})
    inc, reset = cleaning.totalizer_increments(df)
    assert list(reset) == [False, False, False, True, False]
    assert inc.iloc[1:].tolist() == [100.0, 100.0, 50.0, 100.0] and inc.iloc[1:].sum() == 350.0
    g, _, rep = cleaning.clean(mk(10).assign(fuel_totalizer_kg=[100, 200, 300, 400, 50, 150, 250, 350, 450, 550.0]), CFG)
    assert rep["flag_counts"]["totalizer_reset"] == 1 and (g["fuel_kg_interval_totalizer"].dropna() >= 0).all()


def test_frozen_sensor_rows_are_rejected():
    df = mk(40)
    df.loc[10:15, "O2_pct_dry"] = 6.9
    df.loc[21:25, "fuel_rate_measured_kgh"] = 0.0  # stopped feeders are not "frozen"
    df.loc[21:25, "feeder_speed_pct"] = 0.0
    good, rej, _ = cleaning.clean(df, CFG)
    assert set(rej.reject_reason) == {"FROZEN_SENSOR"} and len(rej) >= 6
    hit = set(df.index[df.timestamp_local.isin(rej.timestamp_local)])
    assert hit <= set(range(9, 17)) and {11, 12, 13, 14, 15} <= hit and len(good) == 40 - len(rej)
    assert good["frozen_signals"].eq("").all()


def test_duplicates_schema_and_gaps_are_handled_without_filling():
    df = mk(30)
    df = pd.concat([df, df.iloc[[5]]], ignore_index=True)
    df.loc[3, "FD_command_pct"] = 150.0
    df.loc[4, "heater_id"] = "OTHER"
    df.loc[7, "draft_pa"] = np.nan
    df = df.drop(index=[12, 13, 14]).reset_index(drop=True)
    good, rej, rep = cleaning.clean(df, CFG)
    assert dict(rej.reject_reason.value_counts()) == {"SCHEMA_INVALID": 2, "DUPLICATE_TIMESTAMP": 1}
    assert len(good) == len(df) - 3 and rep["missing_rows"] == 5  # 3 dropped + 2 rejected rows leave gaps; nothing is filled
    assert sorted(good.loc[good["after_gap"] == 1, "gap_before_steps"].tolist()) == [2, 3]
    assert good["draft_pa"].isna().sum() == 1  # safety signal not interpolated
    assert good["timestamp_local"].str.endswith("+07:00").all()


def test_raw_is_not_modified_and_truth_columns_are_dropped():
    df = mk(30)
    before = df.copy(deep=True)
    good, _, _ = cleaning.clean(df, CFG)
    pd.testing.assert_frame_equal(df, before)
    for c in ("fuel_rate_true_kgh", "true_synthetic_best_action", "scenario_id", "is_fault_injected", "quality_flag", "advice_eligibility"):
        assert c not in good.columns
    raw = pd.read_csv(RAW)
    h = hashlib.sha256(RAW.read_bytes()).hexdigest()
    g, r, rep = cleaning.clean(raw, CFG)
    assert hashlib.sha256(RAW.read_bytes()).hexdigest() == h
    assert len(g) + len(r) == len(raw) and rep["n_raw"] == len(raw) and g["timestamp_local"].is_monotonic_increasing


def test_property_table_violation_is_rejected_not_extrapolated():
    df = mk(30)
    df.loc[10, "HTF_Tout_C"] = 335.0
    full, rej, _ = run(df)
    assert len(rej) == 1 and "PROPERTY_OOR" in rej.iloc[0]["all_reasons"]
    q, _, _ = engineering.heat_with_uncertainty([700.0], [260.0], [335.0], CFG)
    assert np.isnan(q[0])


def test_implausible_heat_and_fuel_rejected():
    df = mk(30)
    df.loc[5, "HTF_Tout_C"] = 330.0 - 15  # dT 55 K
    df.loc[8, "fuel_rate_measured_kgh"] = 4 * 2850.0
    _, rej, _ = cleaning.clean(df, CFG)
    assert dict(rej.reject_reason.value_counts()) == {"HEAT_IMPLAUSIBLE": 1, "FUEL_IMPLAUSIBLE": 1}


def test_command_vs_feedback_mismatch_flagged():
    df = mk(30)
    df.loc[10, "fan_power_kW_FD"] = 3 * 45 * 0.55 ** 3
    full, _, rep = run(df)
    assert rep["flag_counts"]["cmd_feedback_mismatch"] == 1
    assert full.loc[full["cmd_feedback_mismatch"] == 1, "eligibility"].str.contains("CMD_FEEDBACK").all()


def test_resample_mean_for_instantaneous_and_diff_sum_for_totalizer():
    ts = pd.date_range("2026-01-05", periods=30, freq="1min").strftime("%Y-%m-%d %H:%M:%S")
    tot = np.concatenate([np.arange(1, 16) * 10.0, np.arange(1, 16) * 10.0])  # reset after 15 samples
    df = pd.DataFrame({"timestamp_local": ts, "HTF_flow_m3h": np.arange(30.0), "fuel_totalizer_kg": tot, "lhv_known": 1, "operating_mode": "STEADY"})
    out = cleaning.resample_to_grid(df, 5)
    assert len(out) == 6 and out["HTF_flow_m3h"].iloc[0] == pytest.approx(2.0)
    assert out["fuel_kg_interval_totalizer"].sum() == pytest.approx(tot[-1] + 140.0 + 10.0 - 10.0 + 0.0, abs=1e-9)  # 140 before reset, 10 at reset row, then 140


def test_lag_alignment_is_trailing_and_estimable():
    f = np.concatenate([np.full(30, 2500.0), np.full(30, 3200.0), np.full(30, 2600.0)]) + np.random.default_rng(1).normal(0, 5, 90)
    q = pd.Series(f).shift(2).bfill().to_numpy() / 3600 * 15 * 0.675
    df = mk(90, fuel_rate_measured_kgh=f, feeder_speed_pct=f / 50.0, Q_out_MW=q)
    g, _, _ = cleaning.clean(df, CFG, lag_steps=0)
    lag, _ = cleaning.estimate_lag(g, CFG)
    assert lag == 2
    g2, _, _ = cleaning.clean(df, CFG, lag_steps=2)
    assert g2["fuel_rate_aligned_kgh"].iloc[:2].isna().all()
    assert g2["fuel_rate_aligned_kgh"].iloc[5] == pytest.approx(g2["fuel_rate_measured_kgh"].iloc[3])


# ---- engineering status, uncertainty, LHV
def test_bypass_makes_heat_balance_unverified_and_eta_sfc_unavailable():
    df = mk(40)
    df.loc[30:, "HTF_bypass_pct"] = 10.0
    full, _, rep = run(df)
    b = full[full["HTF_bypass_pct"] > 0]
    assert (b["heat_balance_status"] == "UNVERIFIED").all() and b["status_eta"].eq("UNAVAILABLE").all() and b["status_SFC"].eq("UNAVAILABLE").all()
    assert b["eta_pct"].isna().all() and b["eligibility"].str.contains("ENERGY_BALANCE").all()


def test_volumetric_fuel_widens_uncertainty_and_blocks_advice():
    a, _, _ = run(mk(40))
    b, _, _ = run(mk(40, fuel_mass_basis="VOLUMETRIC"))
    assert (a["fuel_rel_unc"] == 0.02).all() and (b["fuel_rel_unc"] == 0.10).all()
    assert b["SFC_u_kg_GJ"].iloc[-1] / b["SFC_kg_GJ"].iloc[-1] > 2.5 * a["SFC_u_kg_GJ"].iloc[-1] / a["SFC_kg_GJ"].iloc[-1]
    assert (b["status_SFC"] == "ESTIMATED").all() and b["eligibility"].str.contains("LOW_FUEL_CONF").all()


def test_unknown_lhv_is_never_invented():
    rows = []
    for k, lhv in enumerate([13.0, 14.0, 15.0, 16.0]):
        rows.append(mk(12, start=f"2026-01-0{1 + k} 00:00:00", fuel_lot=f"LOT-{k}", fuel_LHV_asfired_MJkg=lhv))
    unk = mk(12, start="2026-01-06 00:00:00", fuel_lot="LOT-9", lhv_known=0, fuel_LHV_asfired_MJkg=np.nan, fuel_moisture_wb_pct=np.nan)
    full, _, _ = run(pd.concat(rows + [unk], ignore_index=True))
    u = full[full["fuel_lot"] == "LOT-9"]
    assert u["LHV_used_MJkg"].isna().all() and u["eta_pct"].isna().all() and u["fuel_LHV_asfired_MJkg"].isna().all()
    assert (u["LHV_basis"] == "TRAILING_LOT_BAND").all() and (u["LHV_lo_MJkg"] == 13.0).all() and (u["LHV_hi_MJkg"] == 16.0).all()
    assert (u["eta_hi_pct"] > u["eta_lo_pct"]).all() and (u["status_eta"] == "ESTIMATED").all()
    alone, _, _ = run(unk)
    assert (alone["LHV_basis"] == "ENVELOPE_BAND").all() and (alone["LHV_lo_MJkg"] == 12.0).all() and (alone["LHV_hi_MJkg"] == 18.0).all()


def test_status_values_and_non_operating_rows_unavailable():
    df = mk(40)
    df.loc[0:4, "operating_mode"] = "STARTUP"
    df.loc[5:9, "operating_mode"] = "RAMP"
    full, _, _ = run(df)
    assert set(full["status_SFC"]) <= {"CALCULATED", "ESTIMATED", "UNAVAILABLE"}
    assert full.loc[full["operating_mode"] == "STARTUP", "status_Q_out"].eq("UNAVAILABLE").all()
    assert full.loc[full["operating_mode"] == "RAMP", "status_Q_out"].eq("ESTIMATED").all()
    assert full.loc[full["operating_mode"] == "STEADY", "status_Q_out"].eq("CALCULATED").all()


# ---- eligibility flags (SPEC C7 layer 1 and 2)
def test_eligibility_stable_window_and_reason_codes():
    full, _, _ = run(mk(40))
    assert full["eligibility"].iloc[:11].str.startswith("NO_ADVICE:TRANSIENT").all()
    assert full["eligibility"].iloc[11:].eq("ELIGIBLE").all()
    cases = {
        "DIAGNOSTIC_ONLY:NO_CO": dict(co_available=0, CO_ppm=np.nan),
        "UNSAFE_DRAFT": dict(draft_pa=-5.0), "LOW_O2": dict(O2_pct_dry=np.linspace(4.0, 4.5, 40)),
        "FAN_DERATE": dict(fan_derated=1), "TRIP_ACTIVE": dict(interlock_active=1), "HIGH_CO": dict(CO_ppm=400.0),
        "LOW_FUEL_CONF": dict(lhv_known=0, fuel_LHV_asfired_MJkg=np.nan), "BAD_FLOW": dict(HTF_flow_m3h=450.0 + 0.01 * np.arange(40)),
        "TRANSIENT": dict(operating_mode="RAMP"),
    }
    for code, over in cases.items():
        f, _, _ = run(mk(40, **over))
        assert f["eligibility"].iloc[-1].startswith(("DIAGNOSTIC_ONLY", "NO_ADVICE")) and code in f["eligibility"].iloc[-1], (code, f["eligibility"].iloc[-1])


def test_eligibility_restarts_after_a_gap():
    df = mk(60).drop(index=range(30, 33)).reset_index(drop=True)
    full, _, _ = run(df)
    after = full.index[full["after_gap"] == 1][0]
    assert full["eligibility"].iloc[after].startswith("NO_ADVICE")
    assert full["eligibility"].iloc[after + 5].startswith("NO_ADVICE:TRANSIENT")
    assert full["eligibility"].iloc[after + 11].startswith("NO_ADVICE:TRANSIENT") and full["eligibility"].iloc[after + 12] == "ELIGIBLE"


# ---- baseline mechanics
def test_ols_recovers_known_coefficients_and_ci_covers_truth():
    rng = np.random.default_rng(3)
    load, moist = rng.uniform(6, 11, 3000), rng.uniform(8, 30, 3000)
    true = np.array([95.0, 0.5, 0.1, 2.0])
    X = baseline.design(load, moist)
    y = X @ true + rng.normal(0, 1.0, 3000)
    lots = np.repeat(np.arange(60), 50)
    beta = baseline.ols(X, y)
    ci = baseline.cluster_bootstrap(X, y, lots, 200, 1)
    assert np.allclose(beta, true, atol=0.3)
    assert ((ci[0] <= true) & (true <= ci[1])).all()


def test_rule_comparator_uses_only_earlier_windows():
    n = 120
    t = pd.date_range("2026-01-05", periods=n, freq="5min", tz="UTC")
    sfc = np.full(n, 100.0)
    sfc[100] = 150.0
    d = pd.DataFrame({"t": t, "SFC_win_kg_GJ": sfc, "Q_out_win_MW": 8.0})
    cfg = {"baseline": dict(CFG["baseline"], min_obs=10)}
    x = baseline.rule_alerts(d, pd.Series(True, index=d.index), cfg)
    assert x["rule_alert"].iloc[:10].isna().all()
    assert x["rule_alert"].iloc[100] and not x["rule_alert"].iloc[10:100].astype(bool).any()
    assert x["p75"].iloc[101] == pytest.approx(100.0)  # one spike of 150 is below P75 of earlier windows
