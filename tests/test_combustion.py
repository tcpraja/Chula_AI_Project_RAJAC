"""Combustion chemistry checks (SYNTHETIC context): stoichiometry, excess air, flue gas, loss balance, moisture-LHV round trip."""
import numpy as np
import pytest

from src import combustion as cb

PURE_C = {"ultimate_dry_wt_pct": {"C": 100.0, "H": 0.0, "O": 0.0, "N": 0.0, "S": 0.0, "ash": 0.0}, "air_o2_vol_frac": 0.2095, "mw_air_kg_kmol": 28.96,
          "mcp_dry_flue_kj_kmolk": 31.0, "cp_vapour_kj_kgk": 1.9, "heat_of_combustion_co_kj_kmol": 283000.0, "heat_of_combustion_c_mj_kg": 32.8,
          "radiation_other_loss_pct": 0.0, "default_unburnt_in_ash_pct": 3.0}
FUEL = cb.load_fuel()


def test_pure_carbon_stoichiometric_air():
    st = cb.stoichiometry(PURE_C, 0.0)
    assert st["o2_kmol"] == pytest.approx(1 / 12)                          # C + O2 -> CO2: 1/12 kmol O2 per kg C
    assert st["air_kg"] == pytest.approx(1 / 12 / 0.2095 * 28.96)           # ~11.5 kg air per kg carbon


def test_fuel_analysis_sums_to_100_and_hydrogen_raises_air_need():
    assert sum(FUEL["ultimate_dry_wt_pct"].values()) == pytest.approx(100.0)
    assert cb.stoichiometry(FUEL, 0.0)["air_kg"] > 0
    assert cb.stoichiometry(FUEL, 30.0)["air_kg"] < cb.stoichiometry(FUEL, 5.0)["air_kg"]   # wetter fuel: less combustible per kg


def test_excess_air_ratio():
    assert cb.excess_air_ratio(0.0) == pytest.approx(1.0)
    assert cb.excess_air_ratio(10.5) == pytest.approx(2.0)
    assert cb.excess_air_ratio(7.0) == pytest.approx(21 / 14)


def test_flue_gas_carbon_balance_and_dry_loss_recomputed_independently():
    fg = cb.flue_gas(FUEL, 17.0, 7.0, 0.0)
    comp = cb.composition_ar(FUEL, 17.0)
    lam = 21 / 14
    air = lam * (comp["C"] / 12 + comp["H"] / 4 + comp["S"] / 32 - comp["O"] / 32) / 0.2095
    n_dry = comp["C"] / 12 + comp["S"] / 32 + comp["N"] / 28 + 0.7905 * air + 0.2095 * (lam - 1) * (air / lam)
    assert fg["n_dry"] == pytest.approx(n_dry)
    r = cb.losses(FUEL, 17.0, 15.0, 7.0, 230.0, 30.0)
    assert r["dry_flue_gas"] == pytest.approx(n_dry * 31.0 * 200.0 / 15000.0 * 100.0)


def test_losses_sum_and_monotonic_in_excess_air():
    prev = None
    for o2 in (3, 5, 7, 9, 11):
        r = cb.losses(FUEL, 17.0, 15.0, o2, 230.0, 30.0)
        assert r["total"] == pytest.approx(r["dry_flue_gas"] + r["water_vapour"] + r["CO"] + r["unburnt_carbon"] + r["radiation_other"])
        assert r["eta_indirect_pct"] == pytest.approx(100 - r["total"])
        if prev is not None:
            assert r["dry_flue_gas"] > prev                               # more air, more hot flue gas, more loss
        prev = r["dry_flue_gas"]
    assert cb.losses(FUEL, 17.0, 15.0, 7.0, 260.0, 30.0)["total"] > cb.losses(FUEL, 17.0, 15.0, 7.0, 200.0, 30.0)["total"]


def test_co_and_unburnt_carbon_losses_increase_with_their_inputs():
    base = cb.losses(FUEL, 17.0, 15.0, 7.0, 230.0, 30.0, co_ppm=0.0, unburnt_in_ash_pct=1.0)
    assert cb.losses(FUEL, 17.0, 15.0, 7.0, 230.0, 30.0, co_ppm=2000.0, unburnt_in_ash_pct=1.0)["CO"] > base["CO"] == 0.0
    assert cb.losses(FUEL, 17.0, 15.0, 7.0, 230.0, 30.0, co_ppm=0.0, unburnt_in_ash_pct=10.0)["unburnt_carbon"] > base["unburnt_carbon"]


def test_lhv_dry_round_trip_and_humidity():
    m, lhv_dry = 20.0, 18.5
    lhv_ar = lhv_dry * (1 - m / 100) - 2.442 * m / 100
    assert cb.lhv_dry_from_asfired(lhv_ar, m) == pytest.approx(lhv_dry)
    assert cb.humidity_ratio(30.0, 70.0) == pytest.approx(0.0188, abs=0.0015)
    assert np.isclose(cb.humidity_ratio(30.0, 0.0), 0.0)
