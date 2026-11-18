"""Single source of numbers for the final submission set (submission/Heater_C_Final_*). SYNTHETIC - NOT FOR PLANT OPERATION.

Every value is read from a repository output and logged with its source and evidence label in submission/number_source_map_final.csv.
Original (pre-audit) values are kept in reports/audit/original_values.json so the before/after table is reproducible.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
SUB = ROOT / "submission"
ORIG = REP / "audit" / "original_values.json"

# Values reported before this audit (reports/project_deck_number_map.csv at commit 9554b7b, and the master brief).
ORIGINAL = {"ai_exact_pct": 8.99, "ai_direction_pct": 17.37, "ai_precision_pct": 18.93, "ai_fa_pct": 29.17, "ai_any_pct": 43.26, "ai_alerts": 708,
            "rule_exact_pct": 8.58, "rule_fa_pct": 15.28, "rule_any_pct": 22.40, "net_base": -154779, "net_pess": -416337, "net_opt": 93079,
            "breakeven_base_pct": 0.429, "sim_full_pct": 0.240, "sim_base_pct": 0.120, "fuel_kwh_th": 7558.8, "fan_kwh": -49.69,
            "payback_opt_yr": 4.60, "tariff_base": 4.0, "price_base": 2500, "mv_hw_pct": 0.78, "mde80_6wk_pct": None, "tests_passed": 168, "tests_skipped": 1,
            "combo_menu": "full 5x5 grid", "min_benefit": 0.0}


class Num(dict):
    def __init__(self):
        super().__init__()
        self.log = []

    def put(self, key, value, source, label):
        self[key] = value
        self.log.append({"key": key, "value": value, "source": source, "evidence_label": label})
        return value


def _econ():
    e = pd.read_csv(REP / "economics_summary.csv")
    return lambda k, s: e[(e["key"] == k) & (e["scenario"] == s)]["value"].iat[0]


def build():
    N = Num()
    S, M, P, O = "SYNTHETIC", "MEASURED-IN-PROTOTYPE", "PUBLISHED", "OWN-ESTIMATE"
    fn = pd.read_csv(REP / "final_numbers.csv").set_index("key")["value"]
    for k in ("rows_total", "days_total", "lots_total", "eligible_share_pct", "baseline_sfc_median", "baseline_sfc_p25", "baseline_sfc_p75",
              "test_rows", "shadow_advice", "shadow_no_advice", "shadow_diag_only"):
        N.put(k, float(fn[k]), f"reports/final_numbers.csv[{k}]", S)
    cr = json.loads((ROOT / "data" / "clean" / "clean_report.json").read_text(encoding="utf-8"))
    N.put("raw_rows", float(cr["n_raw"]), "data/clean/clean_report.json", S)
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv", usecols=["eta_pct", "eligibility"])
    el = d[d["eligibility"].astype(str).str.startswith("ELIGIBLE")]
    N.put("eligible_rows", float(len(el)), "data/clean/clean_heater_c.csv eligibility=ELIGIBLE*", S)
    N.put("eta_median", float(el["eta_pct"].median()), "data/clean/clean_heater_c.csv eta_pct, eligible rows", S)
    N.put("eta_p25", float(el["eta_pct"].quantile(.25)), "same, 25th percentile", S)
    N.put("eta_p75", float(el["eta_pct"].quantile(.75)), "same, 75th percentile", S)
    mc = pd.read_csv(REP / "model_comparison.csv")
    g = lambda m, c: float(mc[(mc["model"] == m) & (mc["population"] == "eligible_test") & (mc["segment"] == "ALL")][c].iat[0])
    for m in ("L", "P2", "P", "B", "C0"):
        N.put(f"mae_{m}", g(m, "MAE"), f"reports/model_comparison.csv[{m},eligible_test,ALL].MAE", S)
    N.put("mae_L_lo", g("L", "MAE_ci_lo"), "reports/model_comparison.csv L MAE_ci_lo", S)
    N.put("mae_L_hi", g("L", "MAE_ci_hi"), "reports/model_comparison.csv L MAE_ci_hi", S)
    N.put("cov_L", 100 * g("L", "coverage") if g("L", "coverage") <= 1 else g("L", "coverage"), "reports/model_comparison.csv L coverage", S)
    N.put("gain_vs_P2", 100 * (N["mae_P2"] - N["mae_L"]) / N["mae_P2"], "computed: (MAE_P2 - MAE_L) / MAE_P2", S)
    sc = pd.read_csv(REP / "scenario_comparison.csv")
    row = lambda m: sc[sc["method"].str.startswith(m) & sc["subset"].str.startswith("actionable")].iloc[0]
    a, r, ro = row("AI_advisory"), row("rule_P75+default"), row("rule_P75_alert_only")
    for k, c in (("exact", "hit_rate_exact"), ("direction", "hit_rate_direction"), ("precision", "precision_exact"), ("fa", "false_alert_rate"), ("any", "hit_rate_any_alert")):
        N.put(f"ai_{k}_pct", 100 * float(a[c]), f"reports/scenario_comparison.csv[AI_advisory,actionable].{c}", S)
    for k, c in (("exact", "hit_rate_exact"), ("direction", "hit_rate_direction"), ("precision", "precision_exact"), ("fa", "false_alert_rate")):
        N.put(f"rule_{k}_pct", 100 * float(r[c]), f"reports/scenario_comparison.csv[rule_P75+default,actionable].{c}", S)
    N.put("rule_any_pct", 100 * float(ro["hit_rate_any_alert"]), "reports/scenario_comparison.csv[rule_P75_alert_only,actionable]", S)
    N.put("ai_alerts", float(a["alerts"]), "reports/scenario_comparison.csv AI alerts", S)
    N.put("rule_alerts", float(r["alerts"]), "reports/scenario_comparison.csv rule alerts", S)
    N.put("n_actionable", float(a["n_target_rows"]), "reports/scenario_comparison.csv n_target_rows", S)
    cal = pd.read_csv(REP / "menu_calibration.csv")
    v = cal[cal["split"] == "val"]
    N.put("val_rule_fa_pct", 100 * float(v["rule_false_alert_rate"].iat[0]), "reports/menu_calibration.csv validation rule false-alert", S)
    N.put("val_best_exact_pct", 100 * float(v["hit_rate_exact"].max()), "reports/menu_calibration.csv validation max exact", S)
    ch = cal[cal["split"] == "test_chosen"].iloc[0]
    N.put("chosen_combo", "≤2 % two-axis" if pd.notna(ch["combo_max_step_pct"]) else "full grid", "reports/menu_calibration.csv chosen", O)
    N.put("chosen_min_benefit", float(ch["min_benefit_sfc_kg_gj"]), "reports/menu_calibration.csv chosen", O)
    mon = json.loads((REP / "monitoring" / "latest.json").read_text(encoding="utf-8"))
    N.put("fa_per_shift", float(mon["false_alerts_per_shift"]), "reports/monitoring/latest.json false_alerts_per_shift", S)
    N.put("data_quality_pct", float(mon["data_quality_pct"]), "reports/monitoring/latest.json data_quality_pct", S)
    mvr = json.loads((REP / "mv" / "mv_retrospective.json").read_text(encoding="utf-8"))
    N.put("mv_hw_pct", (mvr["ci90_pct"][1] - mvr["ci90_pct"][0]) / 2, "reports/mv/mv_retrospective.json (A/A 90 % half-width)", S)
    pw = json.loads((REP / "mv" / "mv_power.json").read_text(encoding="utf-8"))
    w = {x["window_days"]: x for x in pw["windows"]}
    N.put("mde80_21d", float(w[21]["mde80_pct"]), "reports/mv/mv_power.json windows[21].mde80_pct", f"{S} A/A, {O} method")
    N.put("mde80_42d", float(pw["six_week_trial_mde80_pct"]), "reports/mv/mv_power.json six_week_trial_mde80_pct (fit, extrapolated)", f"{O} extrapolation")
    N.put("days_for_024", float(pw["required_days_per_window"]["generator_illustration_0.24pct"]), "reports/mv/mv_power.json", f"{O} extrapolation")
    N.put("days_for_1pct", float(pw["required_days_per_window"]["one_pct"]), "reports/mv/mv_power.json", f"{O} extrapolation")
    E = _econ()
    for k in ("net", "running", "one_time", "breakeven", "sim_pct", "kwh_6w", "kwh_year", "gross", "fuel_cost"):
        for s in ("Pessimistic", "Base", "Optimistic"):
            N.put(f"{k}_{s[:4].lower()}", float(E(k, s)), f"reports/economics_summary.csv[{k},{s}]", "SYNTHETIC x ASSUMED/PUBLISHED inputs (FICTIONAL sensitivity)")
    pb = E("payback", "Optimistic")
    N.put("payback_opt", float(pb) if str(pb).replace(".", "", 1).isdigit() else None, "reports/economics_summary.csv[payback,Optimistic]", "FICTIONAL sensitivity")
    N.put("fuel_kwh_th", -float(E("energy_delta_fuel_energy_kWh_thermal", "point")), "reports/economics_summary.csv energy point", S)
    N.put("fuel_kwh_lo", -float(E("energy_delta_fuel_energy_kWh_thermal", "hi90")), "reports/economics_summary.csv energy hi90", S)
    N.put("fuel_kwh_hi", -float(E("energy_delta_fuel_energy_kWh_thermal", "lo90")), "reports/economics_summary.csv energy lo90", S)
    N.put("fuel_kg", -float(E("energy_delta_fuel_kg", "point")), "reports/economics_summary.csv energy_delta_fuel_kg", S)
    N.put("fan_kwh", -float(E("energy_fan_FD_delta_kWh_electric", "synthetic")), "reports/economics_summary.csv fan", S)
    N.put("win_h", float(E("energy_window_hours", "synthetic")), "reports/economics_summary.csv window hours", S)
    N.put("fuel_kgh", float(E("energy_fuel_mean_kgh_all_rows", "synthetic")), "reports/economics_summary.csv fuel mean", S)
    from src import economics
    A = economics.assumptions()
    for k in ("tariff", "price", "eng_d", "eng_rate", "rev_h", "rate", "co_an", "hours", "p_busy", "real"):
        lab = A[k][5]
        for i, s in enumerate(("pess", "base", "opt")):
            N.put(f"a_{k}_{s}", float(A[k][2 + i]), f"src/economics.py assumptions()['{k}']", lab)
    # shadow-only pilot cost (no supervised advice, no new analyser): engineering + 6 weeks of review labour
    for s in ("pess", "base", "opt"):
        N.put(f"pilot_cost_{s}", N[f"a_eng_d_{s}"] * N[f"a_eng_rate_{s}"] + 6 * N[f"a_rev_h_{s}"] * N[f"a_rate_{s}"],
              "computed: eng_d x eng_rate + 6 wk x rev_h x rate (src/economics.py assumptions)", f"{O} (ASSUMED inputs)")
    rt = pd.read_csv(REP / "ai_runtime_measured.csv")
    N.put("t_train", float(rt.set_index("step").at["train", "wall_s_mean"]), "reports/ai_runtime_measured.csv[train].wall_s_mean", M)
    N.put("ai_kwh_cost_base", N["kwh_6w_base"] * N["a_tariff_base"], "computed: kWh_6w x tariff", "OWN-ESTIMATE x PUBLISHED")
    N.put("fuel_per_ai_kwh", N["fuel_kwh_th"] / N["kwh_6w_base"], "computed: thermal kWh (253 h window) / AI kWh (6 weeks)", S)
    return N


def save_map(N):
    SUB.mkdir(exist_ok=True)
    pd.DataFrame(N.log).to_csv(SUB / "number_source_map_final.csv", index=False)
    ORIG.parent.mkdir(parents=True, exist_ok=True)
    if not ORIG.exists():
        ORIG.write_text(json.dumps(ORIGINAL, indent=2), encoding="utf-8")


if __name__ == "__main__":
    N = build()
    save_map(N)
    for k in ("ai_exact_pct", "ai_fa_pct", "rule_fa_pct", "gain_vs_P2", "net_base", "breakeven_base", "sim_pct_base", "fuel_kwh_th", "mde80_42d",
              "pilot_cost_pess", "pilot_cost_base", "pilot_cost_opt", "eta_median", "eligible_rows", "raw_rows", "t_train", "cov_L"):
        print(k, N[k])
