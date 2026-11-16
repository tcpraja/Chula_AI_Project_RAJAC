"""All formatted numbers used by the final documents, each registered in the Ledger with its source. No literals for metrics."""
from types import SimpleNamespace

SC = ("Pessimistic", "Base", "Optimistic")


def numbers(D, L):
    n = SimpleNamespace()
    m = lambda mod, col: D.model(mod, col)
    for mod in ("P", "P2", "B", "L", "C0", "C"):
        v, s = m(mod, "MAE")
        setattr(n, f"mae_{mod}", L.f(f"MAE kg/h {mod}", v, "{:.1f}", s))
    P, P2, B, Lm, C0 = (m(x, "MAE")[0] for x in ("P", "P2", "B", "L", "C0"))
    src = "computed from reports/model_comparison.csv MAE"
    n.L_vs_P = L.f("L better than P (persistence) %", 100 * (P - Lm) / P, "{:.1f}", src)
    n.L_vs_P2 = L.f("L better than P2 (repeat current feed) %", 100 * (P2 - Lm) / P2, "{:.1f}", src)
    n.L_vs_B = L.f("L better than B (2-variable regression) %", 100 * (B - Lm) / B, "{:.1f}", src)
    n.C0_vs_L = L.f("C0 (boosting) worse than L %", 100 * (C0 - Lm) / Lm, "{:.1f}", src)
    n.cov_L = L.f("L 90 % interval coverage %", 100 * m("L", "coverage")[0], "{:.0f}", m("L", "coverage")[1])
    n.ci_L = f"{L.f('L MAE CI low', m('L', 'MAE_ci_lo')[0], '{:.1f}', m('L', 'MAE_ci_lo')[1])}-{L.f('L MAE CI high', m('L', 'MAE_ci_hi')[0], '{:.1f}', m('L', 'MAE_ci_hi')[1])}"
    s = lambda mp, col: D.scen(mp, "actionable", col)
    n.ai_hit = L.f("AI exact-action hit %", 100 * s("AI_advisory", "hit_rate_exact")[0], "{:.1f}", s("AI_advisory", "hit_rate_exact")[1])
    n.rule_hit = L.f("Rule+default exact hit %", 100 * s("rule_P75+default_action", "hit_rate_exact")[0], "{:.1f}", s("rule_P75+default_action", "hit_rate_exact")[1])
    n.ai_fa = L.f("AI false-alert rate %", 100 * s("AI_advisory", "false_alert_rate")[0], "{:.0f}", s("AI_advisory", "false_alert_rate")[1])
    n.rule_fa = L.f("Rule false-alert rate %", 100 * s("rule_P75+default_action", "false_alert_rate")[0], "{:.0f}", s("rule_P75+default_action", "false_alert_rate")[1])
    n.ai_any = L.f("AI any-alert hit %", 100 * s("AI_advisory", "hit_rate_any_alert")[0], "{:.0f}", s("AI_advisory", "hit_rate_any_alert")[1])
    n.rule_any = L.f("Rule any-alert hit %", 100 * s("rule_P75_alert_only", "hit_rate_any_alert")[0], "{:.0f}", s("rule_P75_alert_only", "hit_rate_any_alert")[1])
    f = lambda key, fmt, label=None: L.f(label or key, D.final(key)[0], fmt, D.final(key)[1])
    n.rows_total, n.days, n.lots = f("rows_total", "{:,.0f}"), f("days_total", "{:.0f}"), f("lots_total", "{:.0f}")
    n.elig, n.diag_share = f("eligible_share_pct", "{:.0f}"), f("diag_only_share_pct", "{:.0f}")
    n.sfc_med, n.sfc_p25, n.sfc_p75, n.sfc_n = f("baseline_sfc_median", "{:.1f}"), f("baseline_sfc_p25", "{:.1f}"), f("baseline_sfc_p75", "{:.1f}"), f("baseline_sfc_n", "{:,.0f}")
    n.test_rows, n.test_share = f("test_rows", "{:,.0f}"), f("test_share_pct", "{:.1f}")
    n.adv, n.noadv, n.diag, n.adv_share = f("shadow_advice", "{:,.0f}"), f("shadow_no_advice", "{:,.0f}"), f("shadow_diag_only", "{:,.0f}"), f("shadow_advice_share_pct", "{:.0f}")
    n.ai_only, n.rule_only, n.both = f("shadow_ai_only", "{:,.0f}"), f("shadow_rule_only", "{:,.0f}"), f("shadow_both", "{:,.0f}")
    n.tests_total, n.tests_passed, n.shots = f("tests_total", "{:.0f}"), f("tests_passed", "{:.0f}"), f("screenshots", "{:.0f}")
    r = lambda step, fmt="{:.1f}": L.f(f"wall s {step}", D.run(step)[0], fmt, D.run(step)[1])
    n.t_gen, n.t_train, n.t_shadow, n.t_dash = r("generate", "{:.2f}"), r("train", "{:.1f}"), r("shadow", "{:.2f}"), r("dashboard_start_to_healthy", "{:.2f}")
    e = lambda key, sc, fmt, scale=1.0: L.f(f"{key} [{sc}]", float(D.econ(key, sc)[0]) * scale, fmt, D.econ(key, sc)[1])
    for sc, tag in zip(SC, ("pess", "base", "opt")):
        setattr(n, f"one_{tag}", e("one_time", sc, "{:.2f}", 1e-6))
        setattr(n, f"run_{tag}", e("running", sc, "{:.2f}", 1e-6))
        setattr(n, f"net_{tag}", e("net", sc, "{:,.0f}", 1e-3))
        setattr(n, f"be_{tag}", e("breakeven", sc, "{:.2f}"))
        setattr(n, f"sim_{tag}", e("sim_pct", sc, "{:.2f}"))
        setattr(n, f"kwh6_{tag}", e("kwh_6w", sc, "{:.1f}"))
        pb = D.econ("payback", sc)[0]
        setattr(n, f"pb_{tag}", "no payback" if str(pb) == "NO PAYBACK" else L.f(f"payback years [{sc}]", float(pb), "{:.1f} years", D.econ("payback", sc)[1]))
    n.kwh_month = e("kwh_month", "Base", "{:.1f}")
    n.kwh_year = e("kwh_year", "Base", "{:.0f}")
    x = lambda key, sc, fmt, scale=1.0: L.f(f"{key} [{sc}]", abs(float(D.econ(key, sc)[0])) * scale, fmt, D.econ(key, sc)[1])
    n.fuel_pt, n.fuel_lo, n.fuel_hi = (x("energy_delta_fuel_energy_kWh_thermal", k, "{:,.0f}") for k in ("point", "lo90", "hi90"))
    n.fan_kwh = x("energy_fan_FD_delta_kWh_electric", "synthetic", "{:.0f}")
    n.win_h = x("energy_window_hours", "synthetic", "{:.0f}")
    n.ratio = L.f("fuel kWh per AI kWh (window vs 6 wk)", abs(float(D.econ("energy_delta_fuel_energy_kWh_thermal", "point")[0])) / float(D.econ("kwh_6w", "Base")[0]),
                  "{:,.0f}", "computed from reports/economics_summary.csv")
    sc_ = D.score
    n.n_targets = L.f("pilot targets (count)", (sc_["type"] == "target").sum(), "{:.0f}", "reports/pilot_scorecard.csv type=target")
    n.n_stops = L.f("pilot stop conditions (count)", (sc_["type"] == "stop").sum(), "{:.0f}", "reports/pilot_scorecard.csv type=stop")
    n.stops = "; ".join(sc_[sc_["type"] == "stop"]["target_verbatim_from_PILOT_SPEC"])
    n.targets = sc_[sc_["type"] == "target"]["target_verbatim_from_PILOT_SPEC"].tolist()
    n.weeks = L.f("pilot weeks", 6, "{:.0f}", "docs/PILOT_SPEC.md 'Six-week pilot'")
    return n
