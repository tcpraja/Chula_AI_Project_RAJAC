"""Phase 1 physics and integrity tests on the generated synthetic data."""
import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from src import generate_synthetic as gen
from src import units
from src.data_dictionary import build as build_dictionary

ROOT = gen.ROOT
RAW = ROOT / "data" / "raw_synthetic"
STRESS = ROOT / "data" / "stress"
MAIN_CSV = RAW / "synthetic_heater_c_5min.csv"


@pytest.fixture(scope="session")
def data():
    if not MAIN_CSV.exists():
        gen.write_outputs(gen.generate(42, 60), MAIN_CSV)
    m = pd.read_csv(MAIN_CSV)
    return dict(
        m=m, t=pd.read_csv(RAW / "synthetic_truth.csv"), log=pd.read_csv(RAW / "operator_action_log.csv"),
        f=pd.read_csv(RAW / "fault_cases.csv"), tab=pd.read_csv(ROOT / "config" / "htf_properties.csv"),
    )


def normal(m):
    return m[~m.scenario_id.str.startswith("FAULT_")]


def test_seed_determinism_hash():
    a, b, c = gen.generate(42, 3), gen.generate(42, 3), gen.generate(43, 3)
    assert gen.frame_hash(a["main"]) == gen.frame_hash(b["main"])
    assert gen.frame_hash(a["truth"]) == gen.frame_hash(b["truth"])
    assert gen.frame_hash(a["main"]) != gen.frame_hash(c["main"])


def test_normal_row_count_17280(data):
    assert len(normal(data["m"])) == 60 * 288 == 17280


def test_timestamps_monotonic_except_injected_gaps(data):
    m = data["m"]
    t = pd.to_datetime(m.timestamp_local)
    d = t.diff().dropna()
    assert (d > pd.Timedelta(0)).all()
    gaps = m.loc[d[d > pd.Timedelta(minutes=5)].index]
    assert len(gaps) == 2 and gaps.scenario_id.eq("FAULT_DATA_GAP").all()
    assert int((d / pd.Timedelta(minutes=5) - 1).sum()) == 14
    assert (normal(m).timestamp_local.pipe(pd.to_datetime).diff().dropna() == pd.Timedelta(minutes=5)).all()


def test_eta_between_0_and_1_on_valid_rows(data):
    m = data["m"]
    v = m[(m.quality_flag == "OK") & m.eta_direct_pct.notna()]
    assert len(v) > 5000
    assert ((v.eta_direct_pct > 0) & (v.eta_direct_pct < 100)).all()
    assert ((data["t"].eta_true > 0) & (data["t"].eta_true < 1)).all()


def test_q_out_positive_in_operation(data):
    m, t = data["m"], data["t"]
    op = m.operating_mode.isin(["STEADY", "RAMP"])
    q = m.Q_out_MW[op]
    assert (q.dropna() > 0).all()
    assert m.quality_flag[op][q.isna()].str.contains("PROPERTY_OOR").all()  # NaN only where the table cannot be used
    assert (t.Q_out_true_MW[op] > 0).all()


def test_fuel_non_negative(data):
    m = data["m"]
    assert (m.fuel_rate_true_kgh >= 0).all() and (m.fuel_rate_measured_kgh >= 0).all()
    assert (m.fuel_totalizer_kg >= -1e-9).all()


def test_totalizer_monotonic_except_flagged_reset(data):
    m = data["m"]
    drops = m.fuel_totalizer_kg.diff() < 0
    assert drops.sum() == 1
    assert m.quality_flag[drops].str.contains("TOTALIZER_RESET").all()
    assert m.scenario_id[drops].eq("FAULT_TOTALIZER_RESET").all()


def _independent_heat(V, Tin, Tout, tab):
    """Trapezoid integral on a fine grid, written independently of src.units."""
    T, rho, cp = tab.T_C.values, tab.rho_kgm3.values, tab.cp_kJkgK.values
    h = (Tout - Tin) / 400.0
    Tg = Tin[:, None] + (Tout - Tin)[:, None] * np.linspace(0, 1, 401)[None, :]
    cg = np.interp(Tg, T, cp)
    integ = h * (cg.sum(1) - 0.5 * (cg[:, 0] + cg[:, -1]))
    return V / 3600.0 * np.interp((Tin + Tout) / 2, T, rho) * integ / 1000.0


def test_truth_energy_balance_closes_within_0p5_percent(data):
    t, tab = data["t"], data["tab"]
    op = t.Q_out_true_MW > 1.0
    assert op.sum() > 15000
    q_hx = _independent_heat(t.HTF_flow_true_m3h[op].values, t.HTF_Tin_true_C[op].values, t.HTF_Tout_heater_true_C[op].values, tab)
    q_fuel = (t.eta_true * t.Q_in_true_MW)[op].values
    assert np.max(np.abs(q_hx - q_fuel) / q_fuel) <= 0.005


def test_cp_is_not_water(data):
    m, tab = data["m"], data["tab"]
    cp = m.HTF_cp_kJkgK.dropna()
    assert (cp != units.WATER_CP).all()
    assert cp.between(tab.cp_kJkgK.min() - 1e-9, tab.cp_kJkgK.max() + 1e-9).all()
    assert tab.cp_kJkgK.max() < 3.0 and tab.rho_kgm3.between(700, 900).all()


def test_no_property_extrapolation(data):
    m, tab = data["m"], data["tab"]
    t = units.HTFTable()
    for bad in (tab.T_C.min() - 0.1, tab.T_C.max() + 0.1):
        with pytest.raises(units.PropertyOutOfRange):
            t.cp(bad)
        with pytest.raises(units.PropertyOutOfRange):
            t.rho(bad)
    tm = (m.HTF_Tin_C + m.HTF_Tout_C) / 2
    oor = (m.HTF_Tin_C < tab.T_C.min()) | (m.HTF_Tout_C > tab.T_C.max()) | (tm > tab.T_C.max())
    assert oor.sum() >= 3
    assert m.HTF_cp_kJkgK[oor].isna().all() and m.HTF_rho_kgm3[oor].isna().all() and m.Q_out_MW[oor].isna().all()
    assert m.quality_flag[oor].str.contains("PROPERTY_OOR").all()


def test_lot_duration_in_band(data):
    m = data["m"]
    t = pd.to_datetime(m.timestamp_local)
    span = (t.groupby(m.fuel_lot).max() - t.groupby(m.fuel_lot).min()) / pd.Timedelta(minutes=5) + 1
    interior = span.iloc[1:-1]
    assert len(interior) > 100
    assert interior.between(72, 216).all()


def test_contradictory_display_record_is_rejected():
    d = pd.read_csv(STRESS / "display_reconciliation.csv")
    rej = d[d.verdict == "REJECT"]
    assert len(rej) == 1 and rej.injected_case.iloc[0] == "CONTRADICTORY"
    assert units.reconcile_display(1.05, 21000.0, 4.0, 4.65, 96.0)[0] == "REJECT"
    assert units.reconcile_display(1.0, 86400.0, 4.0, 4.649, 96.0)[0] == "OK"
    assert units.reconcile_display(1.0, 75000.0, 4.0, 4.649, 96.0)[0] == "WINDOW_MISMATCH"


def test_implausible_heat_and_fuel_flagged(data):
    m = data["m"]
    fuel_bad = (m.fuel_rate_measured_kgh > 2 * m.fuel_rate_true_kgh) & (m.fuel_rate_true_kgh > 500)
    assert fuel_bad.sum() >= 3
    assert m.quality_flag[fuel_bad].str.contains("FUEL_IMPLAUSIBLE").all()
    heat_bad = m.Q_out_MW > 13.75
    assert heat_bad.sum() >= 3
    assert m.quality_flag[heat_bad].str.contains("HEAT_IMPLAUSIBLE").all()
    assert not m.advice_eligibility[fuel_bad | heat_bad].str.startswith("ELIGIBLE").any()


def test_fan_power_rises_with_command(data):
    m = data["m"]
    for cmd, pw in (("FD_command_pct", "fan_power_kW_FD"), ("ID_command_pct", "fan_power_kW_ID")):
        assert spearmanr(m[cmd], m[pw])[0] > 0.98
        med = m.groupby(pd.cut(m[cmd], [0, 40, 55, 70, 85, 101]), observed=True)[pw].median()
        assert med.is_monotonic_increasing
    c = np.polyfit(np.log(m.FD_command_pct / 100), np.log(m.fan_power_kW_FD), 1)[0]
    assert 2.7 < c < 3.3


def test_bypass_triggers_heat_balance_check(data):
    m = data["m"]
    b = m.HTF_bypass_pct > 0
    assert b.sum() > 100
    assert m.quality_flag[b].str.contains("HEAT_BALANCE_CHECK").all()
    assert m.advice_eligibility[b].str.contains("ENERGY_BALANCE").all()


def test_unburnt_rises_at_low_o2_and_high_grate(data):
    m, t = data["m"], data["t"]
    op = m.operating_mode.isin(["STEADY", "RAMP"])
    o2, g, u = t.O2_true_pct_dry[op], m.grate_command_pct[op], t.unburnt_true_pct[op]
    assert u[o2 < 5.0].mean() > u[(o2 >= 7) & (o2 <= 9)].mean() + 1.0
    mid = (o2 >= 7) & (o2 <= 9)
    assert u[mid & (g > 60)].mean() > u[mid & (g < 45)].mean() + 0.3


def test_every_action_log_change_matches_a_setting_change(data):
    m, log = data["m"], data["log"]
    rows = []
    for var in ("FD_command_pct", "ID_command_pct", "grate_command_pct"):
        ch = m[var] != m[var].shift()
        ch.iloc[0] = False
        rows.append(pd.DataFrame({"timestamp": m.timestamp_local[ch], "variable": var, "old": m[var].shift()[ch], "new": m[var][ch]}))
    a = pd.concat(rows).round(1).sort_values(["timestamp", "variable"]).reset_index(drop=True)
    b = log[["timestamp", "variable", "old", "new"]].round(1).sort_values(["timestamp", "variable"]).reset_index(drop=True)
    assert len(a) == len(b) > 1000
    pd.testing.assert_frame_equal(a, b)
    assert set(log.shift_id) == {"OP-A", "OP-B", "OP-C"} and set(log.source) == {"OPERATOR", "EXPLORATION"}
    assert 0.05 < (log.source == "EXPLORATION").mean() < 0.35


def test_every_dataset_column_in_data_dictionary(data):
    dd = pd.read_csv(ROOT / "reports" / "03_data_dictionary.csv")
    assert list(dd.columns[:9]) == ["column", "group", "description", "unit", "type", "role", "how_generated", "use_in_model", "provenance"]
    assert (dd.provenance == "SYNTHETIC").all() and dd.column.is_unique
    names = set(dd.column)
    stress = pd.read_csv(STRESS / "stress_seed77.csv", nrows=5)
    disp = pd.read_csv(STRESS / "display_reconciliation.csv", nrows=5)
    assert list(data["m"].columns) == gen.COLUMNS and list(stress.columns) == gen.COLUMNS
    for df in (data["m"], data["t"], data["log"], data["f"], stress, disp):
        assert set(df.columns) <= names, set(df.columns) - names
    assert set(build_dictionary().column) == names
    assert dd[dd.column.isin(gen.COLUMNS)].group.notna().all()


def test_unit_identities_and_spec_worked_example():
    assert units.mkcal_h_to_mw(1.0) == pytest.approx(1.16222)
    assert units.mmwc_to_pa(10.0) == pytest.approx(98.0665)
    assert units.kgs_to_kgday(1.0) == 86400.0
    assert units.sfc_kg_gj(0.675, 15.0) == pytest.approx(98.77, abs=0.01)
    assert 100 * units.fuel_reduction(0.675, 0.700) == pytest.approx(3.57, abs=0.01)
    tab = units.HTFTable()
    q = tab.heat_mw(700.0, 270.0, 290.3)
    assert 7.5 < q < 8.6


def test_co_available_on_60_percent_of_days(data):
    m = normal(data["m"])
    day = pd.to_datetime(m.timestamp_local).dt.date
    per_day = m.groupby(day).co_available.mean()
    assert set(per_day.unique()) <= {0.0, 1.0}
    assert per_day.mean() == pytest.approx(0.6, abs=0.02)
    assert m.CO_ppm[m.co_available == 0].isna().all() and m.CO_ppm[m.co_available == 1].notna().all()


def test_stress_dataset_profile(data):
    s = pd.read_csv(STRESS / "stress_seed77.csv")
    assert len(normal(s)) == 30 * 288
    assert (normal(s).fuel_mass_basis == "VOLUMETRIC").all()
    assert (s.heater_id == "HEATER_C_SYNTHETIC").all()
    assert gen.frame_hash(s) != gen.frame_hash(data["m"])


def test_envelope_ranges_spec_c5(data):
    m, t = normal(data["m"]), data["t"].loc[normal(data["m"]).index]
    op = m.operating_mode.isin(["STEADY", "RAMP"])
    assert t.Q_demand_MW[op].between(6.0, 11.0).all()
    assert t.moisture_true_wb_pct.between(8, 30).all() and t.LHV_true_MJkg.between(12, 18).all()
    assert m.FD_command_pct.between(0, 100).all() and m.grate_command_pct.between(0, 100).all()
    # LHV falls with moisture
    assert np.corrcoef(t.moisture_true_wb_pct, t.LHV_true_MJkg)[0, 1] < -0.9
    assert m.HTF_flow_m3h[op & (m.HTF_bypass_pct >= 0)].between(480, 920).mean() > 0.99
