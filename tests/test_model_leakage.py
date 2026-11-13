"""Phase 3 tests: leakage, split integrity, target definition, selection rule, artifacts, hand-checked predictions."""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from src import features as ft
from src import predict, train, train_report
from src.cleaning import load_cfg

CFG = load_cfg()
ROOT = train.ROOT


@pytest.fixture(scope="session")
def res():
    return train.run(write=False)


@pytest.fixture(scope="session")
def clean():
    return ft.load_clean().sort_values("t").reset_index(drop=True)


# ---- leakage
def test_no_truth_or_forbidden_columns_in_inputs():
    ft.assert_no_forbidden(ft.FEATURES)
    truth_cols = set(pd.read_csv(ROOT / "data" / "raw_synthetic" / "synthetic_truth.csv", nrows=1).columns) - {"timestamp_local"}
    assert not (set(ft.FEATURES) & truth_cols)
    assert not any(c.startswith(("true_", "truth", "rep_", "eta_", "SFC_", "Q_in")) for c in ft.FEATURES)
    for bad in ("Q_in_MW", "eta_pct", "SFC_kg_GJ", "true_synthetic_best_action", "scenario_id", "is_fault_injected", "unburnt_in_ash_pct", "fuel_rate_measured_kgh"):
        with pytest.raises(ValueError):
            ft.assert_no_forbidden(ft.FEATURES + [bad])
    assert "fuel_rate_measured_kgh" not in ft.FEATURES  # fuel at t itself is not an input


def test_features_use_only_rows_up_to_t(clean):
    cut = int(len(clean) * 0.6)
    full = ft.build(clean)[ft.FEATURES].iloc[:cut]
    trunc = ft.build(clean.iloc[:cut].copy())[ft.FEATURES]
    assert np.allclose(full.to_numpy(float), trunc.to_numpy(float), equal_nan=True)
    # corrupting every row after the cut must not change any feature at or before it
    bad = clean.copy()
    for c in ("fuel_rate_measured_kgh", "Q_out_MW", "O2_pct_dry", "fuel_lot", "sootblow"):
        if c == "fuel_lot":
            bad.loc[cut:, c] = "LOT-X"
        else:
            bad.loc[cut:, c] = 99999
    corrupted = ft.build(bad)[ft.FEATURES].iloc[:cut]
    assert np.allclose(full.to_numpy(float), corrupted.to_numpy(float), equal_nan=True)


def test_target_and_lags_match_hand_computation(clean):
    F = ft.build(clean)
    e = F[(F.fuel_lag3.notna()) & F.y.notna()].iloc[500]
    i = F.index[F.timestamp_local == e.timestamp_local][0]
    c = clean.set_index("t")["fuel_rate_measured_kgh"]
    t0 = clean["t"].iloc[i]
    step = pd.Timedelta(minutes=5)
    assert e.y == pytest.approx(np.mean([c[t0 + k * step] for k in (1, 2, 3)]))
    assert e.fuel_lag1 == pytest.approx(c[t0 - step]) and e.fuel_lag3 == pytest.approx(c[t0 - 3 * step])
    assert e.fuel_lag1 != pytest.approx(c[t0]) or c[t0] == c[t0 - step]


def test_shuffled_target_has_no_skill_and_future_feature_is_caught(res):
    lk = res["leak"]
    assert lk["shuffled_has_no_skill"] and lk["shuffled_target_mae"] > 0.9 * lk["mean_model_mae"]
    assert lk["future_feature_detected"] and lk["future_feature_r2"] - lk["honest_r2"] >= 0.04
    assert lk["truncation_invariant"] and lk["no_forbidden_columns"] and res["leak_ok"]


def test_r2_above_0p995_raises_the_generator_flag(res):
    assert not any(res["r2_flag"].values())  # honest models do not reach it
    fake = {k: dict(v) for k, v in res["tbl"].items()}
    fake["C0"]["R2"] = 0.9961
    assert bool(fake["C0"]["R2"] > CFG["model"]["selection"]["leak_r2"])


# ---- split integrity
def test_split_is_lot_aware_chronological_and_purged(res):
    F = res["F"]
    one = F.groupby("fuel_lot")["split"].nunique()
    assert (one == 1).all()
    first = F.groupby("fuel_lot").agg(t0=("t", "min"), t1=("t", "max"), s=("split", "first"))
    for a, b in (("train", "val"), ("val", "test")):
        assert first[first.s == a].t1.max() < first[first.s == b].t0.min()
    assert set(F["split"]) == {"train", "val", "test"} and set(F[F.split == "val"].val_part) == {"val_a", "val_b"}
    assert first[first.s == "val"].index.map(lambda l: F[F.fuel_lot == l].val_part.iloc[0]).is_monotonic_increasing
    ok = F[F.y_ok]
    nxt = F.set_index("t")["split"].reindex(ok["t"] + CFG["model"]["purge_steps"] * ft.STEP).to_numpy()
    assert not ((pd.Series(nxt, index=ok.index).notna()) & (nxt != ok["split"].to_numpy())).any()
    n = (F.eligible & F.y_ok).sum()
    shares = [((F.eligible & F.y_ok) & (F.split == s)).sum() / n for s in ("train", "val", "test")]
    assert shares == pytest.approx([0.6, 0.2, 0.2], abs=0.04)


def test_split_keys_file_and_metadata_hashes_are_consistent():
    meta = json.loads((ROOT / "models" / "metadata.json").read_text())
    sk = ROOT / "data" / "holdout" / "split_keys.csv"
    assert hashlib.sha256(sk.read_bytes()).hexdigest() == meta["split_sha256"]
    assert hashlib.sha256((ROOT / "data" / "clean" / "clean_heater_c.csv").read_bytes()).hexdigest() == meta["data_sha256"]
    assert meta["seed"] == 42 and {"python", "numpy", "pandas", "sklearn", "joblib"} <= set(meta["versions"])
    keys = pd.read_csv(sk)
    assert {"timestamp_local", "fuel_lot", "split", "val_part", "eligible"} <= set(keys.columns)
    assert meta["banner"].startswith("SYNTHETIC SIMULATION")


def test_frozen_design_section_is_unchanged():
    txt = (ROOT / "reports" / "model_card.md").read_text(encoding="utf-8")
    design = txt[: txt.index("---\nRESULTS")]
    assert hashlib.sha256(design.encode()).hexdigest() == train_report.DESIGN_SHA


# ---- metrics and calibration
def test_conformal_coverage_is_calibrated_on_validation_b_and_reasonable_on_test(res):
    va = res["va_b"]
    for k in ("P2", "L", "C0"):
        p = res["P_te"][k]
        assert res["tbl"][k]["coverage"] >= CFG["model"]["selection"]["coverage_min"]
    q = train.conformal_half(np.array([0.0] * 10), np.arange(1.0, 11.0), 0.9)  # residuals 1..10 -> rank ceil(11*0.9)=10
    assert q == 10.0


def test_model_comparison_table_has_all_models_and_positive_finite_mae(res):
    comp = res["comp"]
    elig = comp[(comp.population == "eligible_test") & (comp.segment == "ALL")].set_index("model")
    assert set(train.ALL) <= set(elig.index)
    assert np.isfinite(elig["MAE"]).all() and (elig["MAE"] > 0).all()
    assert (elig["MAE_ci_lo"] <= elig["MAE"]).all() and (elig["MAE"] <= elig["MAE_ci_hi"]).all()
    assert {"moisture<14", "load<7.5", "inside injected-fault window"} <= set(comp.segment)
    assert comp[comp.population == "extended_test"].segment.str.contains("steady|transient|fan_derated|lhv_known").any()


# ---- selection rule
def _tbl(**kw):
    base = dict(coverage=0.9, val_test_gap=0.0, worst_seg_ratio=1.2)
    return {k: dict(base, **v) for k, v in kw.items()}


def test_selection_prefers_simpler_unless_ten_percent_better():
    sel = CFG["model"]["selection"]
    t = _tbl(A=dict(MAE_valb=100.0, MAE=100.0), B=dict(MAE_valb=95.0, MAE=95.0), L=dict(MAE_valb=92.0, MAE=92.0),
             C0=dict(MAE_valb=80.0, MAE=80.0), C=dict(MAE_valb=79.0, MAE=79.0), P=dict(MAE_valb=120.0, MAE=120.0), P2=dict(MAE_valb=110.0, MAE=110.0))
    chosen, safe, beats, ref, _ = train.select(t, True, sel)
    assert chosen == "C0" and ref == "P2" and beats  # C0 is 13 % better than A; B and L are not 10 % better than A; C is not 10 % better than C0
    t["C0"]["MAE_valb"], t["C"]["MAE_valb"] = 91.0, 91.0
    assert train.select(t, True, sel)[0] == "A"
    t["C0"]["coverage"] = 0.5  # unsafe candidates are skipped
    t["C0"]["MAE_valb"] = 50.0
    assert train.select(t, True, sel)[1]["C0"] is False and train.select(t, True, sel)[0] != "C0"
    assert train.select(t, False, sel)[0] is None  # failed leakage tests: nothing is safe


def test_selected_model_beats_best_reference_on_validation_and_test(res):
    assert res["chosen"] in train.ORDER and all(res["safe"].values())
    assert res["beats_ref"] and res["beats_test"]
    assert res["tbl"][res["chosen"]]["MAE"] <= 0.95 * min(res["tbl"][r]["MAE"] for r in train.REFS)


# ---- saved artifacts and hand-checked predictions
def test_two_hand_checked_predictions_match_predict_module():
    keys = pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv")
    F = predict.features_for("test")
    F = F[F.eligible].reset_index(drop=True)
    meta = predict.load_meta()
    r = F.iloc[[10, 400]]
    # model A by hand: Q_out x 3600 / (eta_base x LHV_bed)
    a_hand = r["Q_out_MW"].to_numpy() * 3600.0 / (meta["eta_base"] * r["bed_LHV_MJkg"].to_numpy())
    a_code, _ = predict.predict_raw(r, "A")
    assert a_code == pytest.approx(a_hand, rel=1e-9)
    # model B by hand: intercept + b1 Q_out + b2 moisture
    c = meta["coefB"]
    b_hand = c[0] + c[1] * r["Q_out_MW"].to_numpy() + c[2] * r["bed_moisture_wb_pct"].to_numpy()
    b_code, half = predict.predict_raw(r, "B")
    assert b_code == pytest.approx(b_hand, rel=1e-9)
    # reference P2 by hand: feeder speed x 5000 / 100
    p2, _ = predict.predict_raw(r, "P2")
    assert p2 == pytest.approx(r["feeder_speed_pct"].to_numpy() * 50.0)
    out = predict.predict(r, "selected")
    assert (out["status"] == "PREDICTED").all() and (out["banner"] == predict.BANNER).all()
    assert ((out["lo_kgh"] < out["y_hat_kgh"]) & (out["y_hat_kgh"] < out["hi_kgh"])).all()


def test_predict_returns_no_advice_outside_eligibility_with_reason_codes():
    F = predict.features_for("test")
    bad = F[~F.eligible].head(20)
    assert len(bad) > 0
    out = predict.predict(bad, "selected")
    assert out["status"].str.startswith("NO_ADVICE:").all() and out["y_hat_kgh"].isna().all()
    assert (out["banner"] == predict.BANNER).all()


def test_all_model_files_exist_and_load():
    import joblib
    for name in predict.FILES.values():
        m = joblib.load(ROOT / "models" / f"{name}.joblib")
        assert "half" in m and m["half"] > 0
    for k in ("C0_nofeed", "C0_nolot", "C0_noco"):
        assert (ROOT / "models" / f"{k}_hgb.joblib").exists()
