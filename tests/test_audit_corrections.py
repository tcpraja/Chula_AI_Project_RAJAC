"""Regression tests for the final audit corrections (CP10 menu calibration, CP17 M&V power, CP15/16 market-anchored economics). SYNTHETIC."""
import json
from pathlib import Path

import pandas as pd
import yaml

from src import calibrate_menu as cm, economics

ROOT = Path(__file__).resolve().parents[1]


def test_selection_rule_uses_validation_rows_only_and_is_preregistered():
    val = pd.DataFrame([
        {"combo_max_step_pct": None, "min_benefit_sfc_kg_gj": 0.0, "hit_rate_exact": 0.30, "false_alert_rate": 0.50, "rule_false_alert_rate": 0.40, "alerts": 9},
        {"combo_max_step_pct": 2, "min_benefit_sfc_kg_gj": 0.0, "hit_rate_exact": 0.20, "false_alert_rate": 0.30, "rule_false_alert_rate": 0.40, "alerts": 8},
        {"combo_max_step_pct": 2, "min_benefit_sfc_kg_gj": 0.1, "hit_rate_exact": 0.20, "false_alert_rate": 0.10, "rule_false_alert_rate": 0.40, "alerts": 5}])
    pick = cm.choose(val)
    assert pick["min_benefit_sfc_kg_gj"] == 0.1                     # best hit among false-alert-passing rows; tie -> fewer alerts
    assert cm.choose(val.assign(rule_false_alert_rate=0.0)) is None  # nothing passes -> keep the original config
    import inspect
    assert '"test"' not in inspect.getsource(cm.choose)


def test_calibration_report_scores_test_only_for_original_and_chosen():
    t = pd.read_csv(ROOT / "reports" / "menu_calibration.csv")
    assert set(t["split"]) == {"val", "test_original", "test_chosen"}
    assert (t["split"] == "val").sum() == len(cm.GRID)
    ch = t[t["split"] == "test_chosen"].iloc[0]
    G = yaml.safe_load((ROOT / "config" / "guardrail_limits.yaml").read_text(encoding="utf-8"))["optimizer"]
    assert (G["combo_max_step_pct"] or 0) == (0 if pd.isna(ch["combo_max_step_pct"]) else int(ch["combo_max_step_pct"]))
    assert G["min_benefit_sfc_kg_gj"] == ch["min_benefit_sfc_kg_gj"]


def test_scenario_comparison_matches_the_chosen_test_row():
    t = pd.read_csv(ROOT / "reports" / "menu_calibration.csv")
    ch = t[t["split"] == "test_chosen"].iloc[0]
    s = pd.read_csv(ROOT / "reports" / "scenario_comparison.csv")
    ai = s[(s["method"] == "AI_advisory") & s["subset"].str.startswith("actionable")].iloc[0]
    assert abs(ai["hit_rate_exact"] - ch["hit_rate_exact"]) < 1e-3 and abs(ai["false_alert_rate"] - ch["false_alert_rate"]) < 1e-3


def test_mv_power_shrinks_with_duration_and_shows_short_trial_cannot_detect_the_effect():
    r = json.loads((ROOT / "reports" / "mv" / "mv_power.json").read_text(encoding="utf-8"))
    assert r["fit_hw90_pct"]["b"] < 0
    w = pd.DataFrame(r["windows"]).sort_values("window_days")
    assert w["mde80_pct"].iloc[0] > w["mde80_pct"].iloc[-1]
    assert r["six_week_trial_mde80_pct"] > 0.24                      # the illustrated effect is below the detectable size
    assert r["required_days_per_window"]["generator_illustration_0.24pct"] > 42


def test_market_inputs_are_labelled_with_their_source():
    A = economics.assumptions()
    assert A["tariff"][5].startswith("PUBLISHED") and 3.0 < A["tariff"][3] < 5.0
    assert "OWN-ESTIMATE" in A["price"][5] and "DEDE" in A["price"][5]
    assert "PUBLISHED" in A["co_an"][6]
