"""Write the RESULTS section of reports/model_card.md and the plain-English reports/model_error_analysis.md."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MARK = "RESULTS (appended after training)"
DESIGN_SHA = "5d1c2ca2563de16ccc2e0128a6cedef8db5b17f9c782603cd5147223e906b9c7"
NAMES = ["P", "P2", "A", "B", "L", "C0", "C"]
ABL = ["C0_nofeed", "C0_nolot", "C0_noco"]
LABEL = {"P": "P last fuel (ref)", "P2": "P2 current feed = feeder speed (ref)", "A": "A physics", "B": "B linear load+moisture",
         "L": "L linear, all non-settings features", "C0": "C0 boosting, no settings", "C": "C boosting",
         "C0_nofeed": "C0 without feeder speed", "C0_nolot": "C0 without lot features", "C0_noco": "C0 without CO"}
AMENDMENTS = [
    ("A1", "Reference P2 (current feed = feeder_speed_pct x capacity) added; rule 3 now compares with the better of P and P2.", "critic K1, K2"),
    ("A2", "Candidate L (linear on all non-settings features) inserted in the ladder A < B < L < C0 < C; ablations C0_nofeed, C0_nolot, C0_noco reported.", "K1, K3, K4, K17"),
    ("A3", "Rules 2 and 3 use validation (part b) MAE; test MAE only reports and feeds the safety gates.", "K10"),
    ("A4", "Validation is split by lot: part a tunes C, part b calibrates the conformal interval and drives selection.", "K8"),
    ("A5", "Purge between splits raised from 3 to 12 steps (longest feature look-back).", "K19"),
    ("A6", "Leakage self-test: future-feature canary must lift R2 by >= 0.04 over the honest model; truncation test added (features unchanged when later rows are deleted).", "K16"),
    ("A7", "Reporting: extended-population ALL also on rows all of A, B, L predict; fuel-energy error in MW; lot-level coverage; segments inside/outside injected-fault windows.", "K6, K7, K14, K15"),
    ("A8", "Scope: safety gates apply to the population in which the model may speak (eligible rows). Extended-population results are informational; src/predict.py returns NO_ADVICE outside eligibility.", "K9, K15"),
]


def f3(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def write(res, out, cfg):
    tbl, comp, imp, sel = res["tbl"], res["comp"], res["imp"], cfg["model"]["selection"]
    L = ["", f"Design section SHA-256 (text above the horizontal rule, recorded before training): `{DESIGN_SHA}`.", "",
         "### Dated amendments (2026-11-13, after the critic review; the frozen design above is unchanged)", "| ID | Amendment | Origin |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in AMENDMENTS]
    L += ["", f"Run: seed {cfg['model']['seed']}; eligible rows train {len(res['tr'])} / validation a {len(res['va_a'])} + b {len(res['va_b'])} / test {len(res['te'])} "
          f"(lots {res['tr'].fuel_lot.nunique()} / {res['va'].fuel_lot.nunique()} / {res['te'].fuel_lot.nunique()}). C hyper-parameters (depth, lr, iterations, min leaf) = {tuple(res['hp'])} (validation-a MAE {res['val_mae_grid']:.3f} kg/h). "
          f"eta_base (A) = {res['eta_base']:.4f} (median measured eta, training rows).", "",
          "### Eligible test metrics (kg/h; MAPE on targets > 500 kg/h; MAE also as fuel energy input in MW)",
          "| Model | MAE | MAPE % | RMSE | P90 err | R2 | MAE MW | 90 % cover | lot cover median / p10 | better than B % | MAE val-b | val→test | worst seg |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in NAMES + ABL:
        r = tbl[k]
        L.append(f"| {LABEL[k]} | {f3(r['MAE'])} | {f3(r['MAPE'])} | {f3(r['RMSE'])} | {f3(r['P90'])} | {f3(r['R2'])} | {f3(r.get('MAE_fuel_MW'))} | {f3(r['coverage'])} | "
                 f"{f3(r.get('cov_lot_median'))} / {f3(r.get('cov_lot_p10'))} | {f3(r.get('pct_better_than_B'))} | {f3(r['MAE_valb'])} | {f3(r['val_test_gap'])} | {f3(r['worst_seg_ratio'])} |")
    L += ["", "MAE 95 % intervals (lot-cluster bootstrap, 17 test lots): " + "; ".join(f"{k} [{tbl[k]['MAE_ci_lo']:.1f}, {tbl[k]['MAE_ci_hi']:.1f}]" for k in NAMES) + ".", "",
          "### Eligible test segments (MAE kg/h, n) for P2, L, C0",
          "| Segment | n | P2 | L | C0 |", "|---|---|---|---|---|"]
    el = comp[comp.population == "eligible_test"]
    for seg in list(dict.fromkeys(el.segment)):
        if seg == "ALL":
            continue
        s = el[el.segment == seg].set_index("model")
        L.append(f"| {seg} | {int(s.loc['C0', 'n'])} | {f3(s.loc['P2', 'MAE'])} | {f3(s.loc['L', 'MAE'])} | {f3(s.loc['C0', 'MAE'])} |")
    L += ["", "### Extended population (not eligible for advice; informational), MAE kg/h (share of rows predicted)"]
    ext = comp[comp.population == "extended_test"]
    L += ["| Segment | n rows | " + " | ".join(NAMES) + " |", "|---|---|" + "---|" * len(NAMES)]
    for seg in list(dict.fromkeys(ext.segment)):
        s = ext[ext.segment == seg].set_index("model")
        L.append(f"| {seg} | {int(s.loc['P', 'n_rows'])} | " + " | ".join(f"{f3(s.loc[k, 'MAE'])} ({s.loc[k].get('pred_share', 0) * 100:.0f} %)" for k in NAMES) + " |")
    lk = res["leak"]
    L += ["", "### Leakage and sanity checks",
          f"- Shuffled target: MAE {lk['shuffled_target_mae']:.1f} vs mean-model {lk['mean_model_mae']:.1f} kg/h → no skill: {lk['shuffled_has_no_skill']}.",
          f"- Future-feature canary (y added as a column): R2 {lk['future_feature_r2']:.4f} vs honest model {lk['honest_r2']:.4f} → lift ≥ 0.04 detected: {lk['future_feature_detected']}. (Histogram binning keeps the canary just under 1, so an absolute 0.995 cut-off is fragile.)",
          f"- Features unchanged when later rows are deleted (truncation test): {lk['truncation_invariant']}.",
          f"- No forbidden or truth column among the model inputs: {lk['no_forbidden_columns']}.",
          f"- R2 > {sel['leak_r2']} flag (\"learning the generator\"): " + (str({k: v for k, v in res['r2_flag'].items() if v}) + " — raised" if any(res['r2_flag'].values()) else "not raised for any model") + ".", "",
          "### Permutation importance (MAE increase when a feature is shuffled, test)"]
    for m in ("C", "C0", "C0_nofeed"):
        s = imp[imp.model == m].head(6)
        L.append(f"- {m}: " + ", ".join(f"{r.feature} {r.mae_increase_kgh:.1f}" for r in s.itertuples()))
    L += ["", "### Selection (frozen rule with amendments A1–A8)", "| Candidate | safe | MAE val-b | MAE test | reasons |", "|---|---|---|---|---|"]
    for k in ("A", "B", "L", "C0", "C"):
        r = tbl[k]
        L.append(f"| {k} | {res['safe'][k]} | {r['MAE_valb']:.1f} | {r['MAE']:.1f} | coverage {r['coverage']:.3f} (≥{sel['coverage_min']}), val→test {r['val_test_gap']:.3f} (≤{sel['gap_max']}), worst segment {r['worst_seg_ratio']:.2f}x (≤{sel['worst_seg_max']}) |")
    ch, ref = res["chosen"], res["best_ref"]
    L += ["", f"**Simplicity-ladder winner: {ch}.** Best reference: {ref} (validation-b MAE {tbl[ref]['MAE_valb']:.1f}, test {tbl[ref]['MAE']:.1f} kg/h)."]
    if ch:
        L.append(f"{ch} MAE: validation-b {tbl[ch]['MAE_valb']:.1f}, test {tbl[ch]['MAE']:.1f} kg/h → {(1 - tbl[ch]['MAE'] / tbl[ref]['MAE']) * 100:.1f} % lower than {ref} on test. "
                 f"Beats the best reference by ≥{sel['persistence_margin'] * 100:.0f} % — validation: {res['beats_ref']}, test: {res['beats_test']}.")
        verdict = ("DEPLOYABLE as the forecast model (still advisory, eligible rows only)." if res['beats_ref'] and res['beats_test']
                   else f"NOT DEPLOYABLE: the margin over the current-feed reference is not met on both validation and test, so the honest statement is that '{ref}' (repeat the current feed) suffices; {ch} is kept as a research model.")
        L += ["", f"**Verdict: {verdict}**"]
    L += ["", "Selection reasoning: simplest safe candidate first; a more complex one replaces it only for a ≥10 % validation-MAE gain. Score alone does not select. "
          "Settings add nothing to the forecast (C ≈ C0), so a model that must rank operator actions cannot come from this forecaster; Phase 4 needs its own effect model or the simulator.", ""]
    p = ROOT / "reports" / "model_card.md"
    txt = p.read_text(encoding="utf-8")
    p.write_text(txt[: txt.index(MARK) + len(MARK)] + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    error_analysis(res, out, cfg)


def error_analysis(res, out, cfg):
    tbl, comp = res["tbl"], res["comp"]
    k = res["chosen"] or "C0"
    ref = res["best_ref"]
    e = out[out.eligible].copy()
    e["err"], e["abs"] = e["y"] - e["pred_" + k], (e["y"] - e["pred_" + k]).abs()
    top = e.sort_values("abs", ascending=False).head(6)
    share = e.sort_values("abs", ascending=False).head(max(1, int(len(e) * 0.01)))["abs"].sum() / e["abs"].sum() * 100
    bad = e[e["abs"] > e["half_" + k]]
    ctx = bad["analysis_scenario_id"].fillna("n/a").str.replace("FAULT_", "fault: ", regex=False).value_counts().head(6)
    stop = e[e["y"] < 1000]
    inj = e["analysis_fault_injected"].fillna(0) == 1
    mae_in, mae_out = e.loc[inj, "abs"].mean(), e.loc[~inj, "abs"].mean()
    ext = comp[(comp.population == "extended_test") & (comp.model == k)].set_index("segment")
    extR = comp[(comp.population == "extended_test") & (comp.model == ref)].set_index("segment")
    r2 = tbl[k]["R2"]
    L = ["# Model Error Analysis (SYNTHETIC) — plain English", "",
         f"Model discussed: **{k}** ({LABEL[k]}), the simplicity-ladder winner, always set against the best simple reference **{ref}** ({LABEL[ref]}). Numbers are from the held-out test period (the last 20 % of lots), which also holds the injected faults.", "",
         "## What the model gets right",
         f"- On {len(e):,} eligible test rows the typical error of {k} is {tbl[k]['MAE']:.0f} kg/h (MAPE {tbl[k]['MAPE']:.1f} %, about {tbl[k]['MAE_fuel_MW']:.2f} MW of fuel energy input), against {tbl[ref]['MAE']:.0f} kg/h for the reference {ref}, {tbl['P']['MAE']:.0f} kg/h for repeating the last fuel value and {tbl['B']['MAE']:.0f} kg/h for the linear load-and-moisture model.",
         f"- Nine in ten errors are below {tbl[k]['P90']:.0f} kg/h. The 90 % interval (± {tbl[k]['halfwidth']:.0f} kg/h, calibrated on a separate validation block) covered {tbl[k]['coverage'] * 100:.1f} % of test rows; per lot the median coverage was {tbl[k]['cov_lot_median'] * 100:.0f} % and the weakest tenth of lots {tbl[k]['cov_lot_p10'] * 100:.0f} %.", "",
         "## Where it fails (real failures, not hidden)",
         f"- A few rows carry much of the error: the worst 1 % of rows account for {share:.0f} % of all absolute error.",
         f"- {len(bad)} of {len(e):,} eligible test rows ({len(bad) / len(e) * 100:.1f} %) fall outside the 90 % interval; by context: " + ", ".join(f"{i} ({v})" for i, v in ctx.items()) + ".",
         f"- Inside injected-fault windows the MAE is {mae_in:.0f} kg/h ({int(inj.sum())} rows) versus {mae_out:.0f} kg/h outside ({int((~inj).sum())} rows).",
         f"- {len(stop)} eligible row(s) had a next-15-minute fuel rate below 1,000 kg/h (feeders stopped or tripped). {k} predicted a mean of {stop['pred_' + k].mean():.0f} kg/h for them against an actual mean of {stop['y'].mean():.0f} kg/h. It cannot know a trip is coming because the inputs at time t show a healthy furnace. This is a real limit, not a bug: the guardrail layer has to catch it, not the forecast.",
         "", "Largest single misses:", "", "| Time (Asia/Bangkok) | Context (evaluation label) | Actual kg/h | Predicted kg/h | Error kg/h |", "|---|---|---|---|---|"]
    for r in top.itertuples():
        L.append(f"| {r.timestamp_local[:16]} | {r.analysis_scenario_id} | {r.y:.0f} | {getattr(r, 'pred_' + k):.0f} | {r.err:+.0f} |")
    L += ["", "## Outside the eligible window (extended population, informational)",
          "The tool returns NO_ADVICE on these rows; the table shows what a forecast would have been worth anyway.", "",
          f"| Condition | Rows | MAE of {k} | MAE of {ref} |", "|---|---|---|---|"]
    for seg in ext.index:
        if seg.startswith("ALL") or ext.loc[seg, "n"] < 20:
            continue
        L.append(f"| {seg} | {int(ext.loc[seg, 'n_rows'])} | {f3(ext.loc[seg, 'MAE'])} | {f3(extR.loc[seg, 'MAE'])} |")
    L += ["", "## Why the scores are high and why that is not proof of skill",
          f"- Fuel feed changes slowly and the models see the feeder speed (a proxy for the fuel being fed right now). Repeating the current feed already gives {tbl['P2']['MAE']:.0f} kg/h; {k} gives {tbl[k]['MAE']:.0f} kg/h (R2 {r2:.3f}).",
          f"- Skill over the current-feed reference: {(1 - tbl[k]['MAE'] / tbl['P2']['MAE']) * 100:.1f} % lower MAE (test) — {'above' if res['beats_test'] else 'below'} the 5 % bar. Skill over the last-value reference P: {(1 - tbl[k]['MAE'] / tbl['P']['MAE']) * 100:.1f} %. "
          f"Without feeder speed C0 degrades to {tbl['C0_nofeed']['MAE']:.0f} kg/h, so the forecast value comes almost entirely from knowing the current feed.",
          "- The generator defines the demand-to-fuel relationship, so these results show the method works under known ground truth. They do not predict plant accuracy.", "",
          "## Plain-English reading for an operator or manager",
          "- Inside a steady, assayed, weigh-belt window the next quarter-hour of fuel use is close to what the feeders are doing now. A model adds little beyond that.",
          "- The forecast cannot warn about sudden stops or trips; those stay with the BMS/SIS and alarms.",
          "- The interval has one fixed width, so it is too wide in calm periods and too narrow around fault episodes."]
    (ROOT / "reports" / "model_error_analysis.md").write_text("\n".join(L) + "\n", encoding="utf-8")
