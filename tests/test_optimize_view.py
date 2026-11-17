"""Optimize page logic (SYNTHETIC): best efficiency inside limits, lever signs, mass-balance closure, guidance actions, fail-safe on missing data."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src import chem_advice, combustion as cb, guardrails as gd, optimize_view as ov

ROOT = ov.ROOT


@pytest.fixture(scope="module")
def ctx():
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv").merge(pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv")[["timestamp_local", "split"]], on="timestamp_local")
    recs = {json.loads(line)["timestamp"]: json.loads(line) for line in (ROOT / "data" / "advisory" / "advisory_records_test.jsonl").read_text(encoding="utf-8").splitlines()}
    return d, recs, joblib.load(ROOT / "models" / "effect_model.joblib"), gd.load_limits(), ov.stack_reference(d)


def snap(ctx, decision="ADVICE"):
    d, recs, eff, G, ref = ctx
    ts = next(t for t, r in recs.items() if r["decision"] == decision)
    i = d.index[d.timestamp_local == ts][0]
    return ov.snapshot(d.loc[i], chem_advice.lot_moisture(d, i), recs[ts], eff, G, ref), d, i


def test_best_efficiency_is_inside_limits_and_not_below_now(ctx):
    s, *_ = snap(ctx)
    assert s["o2_best"] >= s["floor"] - 1e-9
    assert s["eta_best"] >= s["now"]["eta_indirect_pct"] - 1e-9
    assert s["best"]["total"] == pytest.approx(100 - s["eta_best"])


def test_levers_have_the_right_signs(ctx):
    s, *_ = snap(ctx)
    lv = s["levers"].set_index("Lever")["Δη (points)"]
    assert lv["Stack temperature"] > 0 and lv["Combustion air (O2)"] >= 0
    assert (lv >= -1e-9).all()


def test_mass_balance_closes_and_heat_balance_adds_up(ctx):
    s, *_ = snap(ctx)
    assert abs(s["mass"]["closure_pct"]) < 0.5
    assert s["q_in"] == pytest.approx(s["q_out"] + sum(s["loss_mw"].values()) + s["unaccounted_mw"])


def test_params_cover_operations_and_actions_follow_status(ctx):
    s, *_ = snap(ctx)
    p = s["params"]
    for must in ("Flue-gas O2", "Excess air λ", "FD fan command", "Furnace draft", "Grate command", "CO", "Stack temperature", "Economizer ΔP", "Fuel moisture", "HTF supply temperature"):
        assert must in set(p["Parameter"]), must
    act = p[p["Status"] == "act"]
    assert len(s["actions"]) == len(act)
    assert set(p["Status"]) <= {"ok", "watch", "act"}


def test_fd_candidates_reduce_air_when_fd_reduced_and_respect_checks(ctx):
    s, *_ = snap(ctx)
    c = s["candidates"].set_index("FD move (%)")
    assert c.loc[-2.0, "O2 predicted"] < c.loc[0.0, "O2 predicted"] < c.loc[2.0, "O2 predicted"]
    assert not bool(c.loc[0.0, "Checks pass"])           # a HOLD has no pessimistic benefit, so it is not a candidate


def test_gate_is_carried_and_missing_data_gives_no_guess(ctx):
    d, recs, eff, G, ref = ctx
    s, d, i = snap(ctx, "NO_ADVICE")
    assert s is None or s["gate"] == "NO_ADVICE"
    row = d.loc[i].copy()
    row["O2_pct_dry"] = np.nan
    assert ov.snapshot(row, 17.0, {"decision": "NO_ADVICE"}, eff, G, ref) is None


def test_mass_balance_function_is_independent_of_losses():
    fuel = cb.load_fuel()
    r = cb.mass_balance(fuel, 17.0, 7.0, 3000.0)
    assert abs(r["closure_pct"]) < 0.01
    assert r["out"]["ash"] == pytest.approx(3000.0 * fuel["ultimate_dry_wt_pct"]["ash"] / 100 * (1 - 0.17))
