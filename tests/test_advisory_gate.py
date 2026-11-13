"""Phase 4 advisory gate: 1 ACCEPT + 12 NO_ADVICE cases on pure guardrails, plus optimizer record contract. All SYNTHETIC."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from src import guardrails as gd, optimizer as op

BASE = dict(timestamp_local="2026-02-01 10:00:00+07:00", operating_mode="STEADY", HTF_flow_m3h=700.0, HTF_Tin_C=255.0, HTF_Tout_C=275.0,
            fuel_mass_basis="WEIGH_BELT", lhv_known=1, fuel_rate_aligned_kgh=2800.0, interlock_active=0, alarm_code="", fan_derated=0,
            draft_pa=-35.0, furnace_temp_C=850.0, O2_pct_dry=7.0, CO_ppm=60.0, co_available=1, frozen_signals="", heat_balance_status="OK",
            eta_pct=67.5, sootblow=0, after_gap=0, totalizer_reset=0, cmd_feedback_mismatch=0, steady_run_steps=40)
G = gd.load_limits()


def check(row=None, limits=None, ood=None, **chg):
    r = {**BASE, **(row or {}), **chg}
    return gd.evaluate(r, limits or G, ood=ood).iloc[0]


def test_accept_clean_row():
    r = check()
    assert r["eligible"] and r["outcome"] == "ELIGIBLE" and r["reason_codes"] == ""


def _unapproved():
    lim = copy.deepcopy(G)
    lim["limits"]["co_limit_ppm"] = "REQUIRES_OEM_APPROVAL"
    return lim


NO_ADVICE_CASES = [
    ("missing_CO", dict(co_available=0, CO_ppm=np.nan), None, None, "NO_CO"),
    ("faulty_flow", dict(HTF_flow_m3h=300.0), None, None, "BAD_FLOW"),
    ("low_fuel_confidence", dict(fuel_mass_basis="VOLUMETRIC"), None, None, "LOW_FUEL_CONF"),
    ("active_trip", dict(interlock_active=1, alarm_code="ALM_TRIP_DRAFT"), None, None, "TRIP_ACTIVE"),
    ("fan_derate", dict(fan_derated=1), None, None, "FAN_DERATE"),
    ("unsafe_draft", dict(draft_pa=2.0), None, None, "UNSAFE_DRAFT"),
    ("high_temp", dict(furnace_temp_C=1100.0), None, None, "HIGH_TEMP"),
    ("stale_data", dict(frozen_signals="O2_pct_dry"), None, None, "STALE_DATA"),
    ("ood", {}, np.array([True]), None, "OOD"),
    ("implausible_energy_balance", dict(eta_pct=120.0), None, None, "ENERGY_BALANCE"),
    ("property_out_of_range", dict(HTF_Tout_C=400.0), None, None, "PROPERTY_OOR"),
    ("limits_not_approved", {}, None, _unapproved(), "LIMITS_NOT_APPROVED"),
]


@pytest.mark.parametrize("name,chg,ood,lim,code", NO_ADVICE_CASES, ids=[c[0] for c in NO_ADVICE_CASES])
def test_no_advice(name, chg, ood, lim, code):
    r = check(limits=lim, ood=ood, **chg)
    assert not r["eligible"], name
    assert code in r["reason_codes"].split(";"), (name, r["reason_codes"])
    assert r["outcome"] in ("NO_ADVICE", "DIAGNOSTIC_ONLY")   # missing CO is DIAGNOSTIC_ONLY per SPEC C7; never ADVICE
    if code != "NO_CO":
        assert r["outcome"] == "NO_ADVICE"


def test_missing_CO_is_diagnostic_only():
    assert check(co_available=0, CO_ppm=np.nan)["outcome"] == "DIAGNOSTIC_ONLY"


def test_transient_and_nan_fail_closed():
    assert "TRANSIENT" in check(steady_run_steps=3)["reason_codes"]
    assert "UNSAFE_DRAFT" in check(draft_pa=np.nan)["reason_codes"]
    assert "HIGH_TEMP" in check(furnace_temp_C=np.nan)["reason_codes"]


def test_placeholder_blocks_every_row():
    df = pd.DataFrame([BASE, BASE])
    out = gd.evaluate(df, _unapproved())
    assert (out["reason_codes"] == "LIMITS_NOT_APPROVED").all() and not out["eligible"].any()


def test_config_limits_match_phase2_and_are_synthetic():
    from src.cleaning import load_cfg
    c = load_cfg()
    L = G["limits"]
    assert G["provenance"].startswith("SYNTHETIC")
    assert L["draft_band_pa"] == c["draft_band_pa"] and L["o2_floor_pct"] == c["o2_floor"] and L["co_limit_ppm"] == c["co_limit_ppm"]


# ---------------------------------------------------------------- optimizer contract
@pytest.fixture(scope="module")
def run():
    d, F, _ = op.load_frames()
    eff = op.fit_from_clean(d, G)
    x, R = op.run_split(d, F, eff, G, "test")
    return d, x, R, eff


def test_guardrails_agree_with_phase2_eligibility(run):
    d, *_ = run
    out = gd.evaluate(d)
    old = d["eligibility"].str.split(":").str[0]
    assert (out["outcome"].to_numpy() == old.to_numpy()).mean() > 0.999


def test_record_fields_and_no_actuation(run):
    _, _, R, _ = run
    need = {"timestamp", "eligible", "decision", "reason_codes", "current_simulated_settings", "proposed_simulated_settings",
            "predicted_SFC_current", "predicted_SFC_option", "uncertainty", "constraint_checks", "predicted_benefit_synthetic_only",
            "human_review_required", "model_version"}
    assert need <= set(R.columns)
    assert R["human_review_required"].all() and set(R["decision"]) <= {"ADVICE", "NO_ADVICE", "DIAGNOSTIC_ONLY"}
    bad = [c for c in R.columns if any(w in c.lower() for w in ("actuat", "write", "opc", "modbus", "setpoint_out", "command_out"))]
    assert not bad
    assert set(R["banner"]) == {op.BANNER}


def test_advice_only_when_eligible_and_within_constraints(run):
    _, _, R, _ = run
    adv = R[R["decision"] == "ADVICE"]
    assert len(adv) > 0
    assert adv["eligible"].all()
    assert not R[~R["eligible"]]["proposed_simulated_settings"].notna().any()
    L = G["limits"]
    for r in adv.itertuples():
        cur, new, cc = r.current_simulated_settings, r.proposed_simulated_settings, r.constraint_checks
        assert abs(new["FD_command_pct"] - cur["FD_command_pct"]) <= L["max_step_fd_pct"] + 1e-6
        assert abs(new["grate_command_pct"] - cur["grate_command_pct"]) <= L["max_step_grate_pct"] + 1e-6
        assert cc["O2_option_pct"] >= L["o2_floor_pct"] and cc["CO_option_ppm"] <= L["co_limit_ppm"] and not cc["ood_option"]
        assert L["draft_band_pa"][0] <= cc["draft_option_pa"] <= L["draft_band_pa"][1]
        assert r.uncertainty["dSFC_hi90"] < 0 and r.uncertainty["width_kg_GJ"] <= L["interval_width_max_sfc_kg_gj"]
        assert r.predicted_SFC_option < r.predicted_SFC_current


def test_diagnostic_rows_get_no_proposal(run):
    _, _, R, _ = run
    dg = R[R["decision"] == "DIAGNOSTIC_ONLY"]
    assert len(dg) > 0 and not dg["proposed_simulated_settings"].notna().any()


def test_jsonl_roundtrip(run, tmp_path):
    _, _, R, _ = run
    p = tmp_path / "r.jsonl"
    op.write_records(R.head(50), p)
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 50 and all(r["human_review_required"] is True for r in rows)


def test_effect_model_uses_train_split_only_and_fan_law(run):
    d, *_ = run
    _, _, _, eff = run
    assert eff["fan_corr"] > 0.99 and eff["n_lots"] > 20
    assert eff["n_train"] <= int((d["split"] == "train").sum())
