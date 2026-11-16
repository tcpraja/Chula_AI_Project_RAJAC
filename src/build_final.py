"""Phase 7: build the submission set in final/ from reports/*.csv (no hand-typed metrics) and print a number -> source map.

Every metric that appears in a final document goes through `Ledger.f(label, value, fmt, source)`; the map is printed and written to
final/number_source_map.csv. Inputs: reports/model_comparison.csv, scenario_comparison.csv, ai_runtime_measured.csv,
economics_summary.csv, pilot_scorecard.csv, shadow_replay.csv, and reports/final_numbers.csv (derived here from data/clean/*.csv and a
pytest run, so that even baseline and test counts are computed, never typed). Identity/course facts are parsed from docs/SPEC.md C8.
All numbers are SYNTHETIC / FICTIONAL / OWN-ESTIMATE as labelled. Run: python -m src.build_final
"""
import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REP, FIN, SHOTS = ROOT / "reports", ROOT / "final", ROOT / "assets" / "screenshots"
FIGS = FIN / "figs"
TAG = "SYNTHETIC - NOT FOR PLANT OPERATION"
SCENARIOS = {"Pessimistic": "pess", "Base": "base", "Optimistic": "opt"}


class Ledger:
    """Formats a number and records where it came from."""

    def __init__(self):
        self.rows = {}

    def f(self, label, value, fmt, source):
        v = float(value)
        self.rows[label] = (v, source)
        return fmt.format(v)

    def table(self):
        return pd.DataFrame([{"label": k, "value": v, "source": s} for k, (v, s) in self.rows.items()])


class Data:
    """Typed access to the CSV sources; every getter returns (value, source string)."""

    def __init__(self):
        self.mc = pd.read_csv(REP / "model_comparison.csv")
        self.sc = pd.read_csv(REP / "scenario_comparison.csv")
        self.rt = pd.read_csv(REP / "ai_runtime_measured.csv").set_index("step")
        self.es = pd.read_csv(REP / "economics_summary.csv")
        self.score = pd.read_csv(REP / "pilot_scorecard.csv")
        self.fn = pd.read_csv(REP / "final_numbers.csv").set_index("key")

    def model(self, m, col):
        r = self.mc[(self.mc.model == m) & (self.mc.population == "eligible_test") & (self.mc.segment_type == "ALL") & (self.mc.segment == "ALL")]
        return float(r[col].iloc[0]), f"reports/model_comparison.csv[model={m},eligible_test,ALL].{col}"

    def scen(self, method_prefix, subset_prefix, col):
        r = self.sc[self.sc.method.str.startswith(method_prefix) & self.sc.subset.str.startswith(subset_prefix)]
        return float(r[col].iloc[0]), f"reports/scenario_comparison.csv[{method_prefix}*,{subset_prefix}*].{col}"

    def run(self, step, col="wall_s_mean"):
        return float(self.rt.at[step, col]), f"reports/ai_runtime_measured.csv[{step}].{col}"

    def econ(self, key, scenario):
        r = self.es[(self.es.key == key) & (self.es.scenario == scenario)]
        v = r["value"].iloc[0]
        return v, f"reports/economics_summary.csv[{key},{scenario}]"

    def final(self, key):
        return float(self.fn.at[key, "value"]), f"reports/final_numbers.csv[{key}]"


# ---------------------------------------------------------------- derived numbers (computed, never typed)
def run_pytest():
    """Run the test-suite except tests that inspect final/ itself; returns {file: (n, passed)} and total passed."""
    xml = ROOT / "reports" / "_junit.xml"
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "--ignore=tests/test_final.py", f"--junitxml={xml}"], cwd=ROOT,
                       capture_output=True, text=True)
    by = {}
    for tc in ET.parse(xml).getroot().iter("testcase"):
        f = tc.get("classname").split(".")[1] + ".py"
        n, ok = by.get(f, (0, 0))
        by[f] = (n + 1, ok + (0 if tc.find("failure") is not None or tc.find("error") is not None else 1))
    xml.unlink()
    return by, p.returncode


def derive_numbers(with_tests=True):
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv", usecols=["timestamp_local", "fuel_lot", "eligibility", "status_SFC", "SFC_kg_GJ", "Q_out_MW"])
    sp = pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv", usecols=["timestamp_local", "split"])
    d = d.merge(sp, on="timestamp_local")
    el = d["eligibility"].str.startswith("ELIGIBLE")
    base = d[(d["split"] == "train") & el & (d["status_SFC"] == "CALCULATED")]["SFC_kg_GJ"]
    sh = pd.read_csv(REP / "shadow_replay.csv")
    rows = [("rows_total", len(d), "rows", "data/clean/clean_heater_c.csv"),
            ("days_total", len(d) * 5 / 60 / 24, "days", "rows x 5 min"),
            ("lots_total", d["fuel_lot"].nunique(), "lots", "data/clean/clean_heater_c.csv"),
            ("eligible_share_pct", 100 * el.mean(), "% of rows", "eligibility starts with ELIGIBLE"),
            ("diag_only_share_pct", 100 * d["eligibility"].str.startswith("DIAGNOSTIC_ONLY").mean(), "% of rows", "eligibility starts with DIAGNOSTIC_ONLY (CO missing, otherwise valid)"),
            ("baseline_sfc_median", base.median(), "kg/GJ", "median SFC_kg_GJ, train split, eligible, CALCULATED"),
            ("baseline_sfc_p25", base.quantile(.25), "kg/GJ", "same, 25th percentile"),
            ("baseline_sfc_p75", base.quantile(.75), "kg/GJ", "same, 75th percentile"),
            ("baseline_sfc_n", len(base), "rows", "same rows"),
            ("test_rows", len(sh), "rows", "reports/shadow_replay.csv"),
            ("test_share_pct", 100 * len(sh) / len(d), "% of rows", "test rows / all rows"),
            ("shadow_advice", int((sh["ai_decision"] == "ADVICE").sum()), "rows", "reports/shadow_replay.csv"),
            ("shadow_no_advice", int((sh["ai_decision"] == "NO_ADVICE").sum()), "rows", "reports/shadow_replay.csv"),
            ("shadow_diag_only", int((sh["ai_decision"] == "DIAGNOSTIC_ONLY").sum()), "rows", "reports/shadow_replay.csv"),
            ("shadow_advice_share_pct", 100 * (sh["ai_decision"] == "ADVICE").mean(), "% of rows", "reports/shadow_replay.csv"),
            ("shadow_ai_only", int((sh["agreement"] == "ai_only").sum()), "rows", "reports/shadow_replay.csv agreement"),
            ("shadow_rule_only", int((sh["agreement"] == "rule_only").sum()), "rows", "reports/shadow_replay.csv agreement"),
            ("shadow_both", int((sh["agreement"] == "both_alert").sum()), "rows", "reports/shadow_replay.csv agreement")]
    if with_tests:
        by, rc = run_pytest()
        for f, (n, ok) in sorted(by.items()):
            rows += [(f"tests_{f}_n", n, "tests", "pytest junit"), (f"tests_{f}_passed", ok, "tests", "pytest junit")]
        rows += [("tests_total", sum(v[0] for v in by.values()), "tests", "pytest junit (excluding tests/test_final.py)"),
                 ("tests_passed", sum(v[1] for v in by.values()), "tests", "pytest junit"), ("tests_exit_code", rc, "code", "pytest")]
    else:
        old = pd.read_csv(REP / "final_numbers.csv")
        rows += [(r.key, r.value, r.unit, r.source) for r in old.itertuples() if r.key.startswith("tests_")]
    shots = len(list(SHOTS.glob("screen_*.png")))
    rows.append(("screenshots", shots, "files", "assets/screenshots/screen_*.png"))
    out = pd.DataFrame(rows, columns=["key", "value", "unit", "source"])
    out["provenance"] = "SYNTHETIC (computed by src.build_final from repository outputs)"
    out.round(4).to_csv(REP / "final_numbers.csv", index=False)
    return out


def admin_facts():
    """Name, ID, course, deadline parsed from docs/SPEC.md C8 (not typed in code)."""
    t = re.sub(r"\s+", " ", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8").split("## C8 Course")[1])
    m = re.search(r"^ (\d+ [^,]+, Chula LGO), individual\. ([^,]+), (\w+)\. Due ([^;]+);", t)
    return {"course": m.group(1), "name": m.group(2), "id": m.group(3), "due": m.group(4)}


# ---------------------------------------------------------------- figures (all from CSVs)
def figures(D, L):
    FIGS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    # F1 baseline SFC by load band (from data/clean, eligible CALCULATED train rows)
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv", usecols=["timestamp_local", "eligibility", "status_SFC", "SFC_kg_GJ", "Q_out_MW"])
    d = d.merge(pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv", usecols=["timestamp_local", "split"]), on="timestamp_local")
    x = d[(d["split"] == "train") & d["eligibility"].str.startswith("ELIGIBLE") & (d["status_SFC"] == "CALCULATED")].copy()
    x["band"] = np.floor(x["Q_out_MW"]).astype(int)
    g = x.groupby("band")["SFC_kg_GJ"].agg(["median", lambda s: s.quantile(.25), lambda s: s.quantile(.75), "size"])
    g.columns = ["med", "p25", "p75", "n"]
    g = g[g["n"] >= 30]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.fill_between(g.index + 0.5, g["p25"], g["p75"], alpha=.3, color="#1f6f8b", label="P25-P75")
    ax.plot(g.index + 0.5, g["med"], "o-", color="#1f6f8b", label="median")
    ax.set_xlabel("useful heat (MW, 1 MW bands)")
    ax.set_ylabel("SFC (kg fuel per GJ useful heat)")
    ax.set_title(f"Synthetic baseline SFC by load  ({TAG})", fontsize=10)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGS / "f1_baseline.png", dpi=150)
    plt.close(fig)
    # F2 options ladder (qualitative table image)
    opts = [("1  No change", "nothing", "Keeps the avoidable-fuel question unanswered"),
            ("2  Process change", "SOP + lot-matched air/grate guide, more LHV assays", "Needs lab time; no per-moment feedback"),
            ("3  Simple automation", "Rule alert (trailing P75) + regression baseline", "Cannot name an action; false alerts"),
            ("4  AI advisory", "Fuel forecast + ranked simulated options, all gated", "Must beat option 3 on real data (MAE >= 10 %)")]
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.axis("off")
    t = ax.table(cellText=[[a, b, c] for a, b, c in opts], colLabels=["Option", "What it is", "Limit"], loc="center", cellLoc="left", colWidths=[.2, .42, .38])
    t.auto_set_font_size(False)
    t.set_fontsize(11)
    t.scale(1, 2.3)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#999")
        if r == 0:
            cell.set_facecolor("#dfe7ee")
        if r == 3 + 0 and c >= 0 and r == 3:
            cell.set_facecolor("#f4f4f4")
        if r == 3:
            cell.set_facecolor("#fff3b0")
    fig.tight_layout()
    fig.savefig(FIGS / "f2_options.png", dpi=150)
    plt.close(fig)
    # F3 results: MAE bars + rule/AI alert rates
    names = [("P2", "repeat current feed"), ("B", "2-variable regression"), ("L", "linear, all features (chosen)"), ("C0", "boosted trees (AI)")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1.15, 1]})
    mae = [D.model(m, "MAE")[0] for m, _ in names]
    lo = [D.model(m, "MAE_ci_lo")[0] for m, _ in names]
    hi = [D.model(m, "MAE_ci_hi")[0] for m, _ in names]
    a1.bar(range(4), mae, yerr=[np.array(mae) - lo, np.array(hi) - mae], color=["#888", "#888", "#1f6f8b", "#d1495b"], capsize=4)
    a1.set_xticks(range(4), [n for _, n in names], fontsize=8, rotation=12)
    a1.set_ylabel("next-15-min fuel MAE, kg/h (lower = better)")
    a1.set_title("Fuel forecast, held-out later lots", fontsize=10)
    ai_h, _ = D.scen("AI_advisory", "actionable", "hit_rate_exact")
    ru_h, _ = D.scen("rule_P75+default_action", "actionable", "hit_rate_exact")
    ai_f, _ = D.scen("AI_advisory", "actionable", "false_alert_rate")
    ru_f, _ = D.scen("rule_P75+default_action", "actionable", "false_alert_rate")
    w = .36
    a2.bar(np.arange(2) - w / 2, [100 * ai_h, 100 * ai_f], w, label="AI advisory", color="#d1495b")
    a2.bar(np.arange(2) + w / 2, [100 * ru_h, 100 * ru_f], w, label="rule + default action", color="#888")
    a2.set_xticks(range(2), ["exact best action\n(higher = better)", "false alerts\n(lower = better)"])
    a2.set_ylabel("% of rows")
    a2.legend(frameon=False, fontsize=9)
    a2.set_title("Option ranking vs rule, same rows", fontsize=10)
    fig.suptitle(TAG, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGS / "f3_results.png", dpi=150)
    plt.close(fig)
    # F4 energy (log scale)
    vals = {"AI computing\n(6 weeks, 60 W est.)": abs(float(D.econ("kwh_6w", "Base")[0])),
            "FD fan electricity change\n(253 h replay)": abs(float(D.econ("energy_fan_FD_delta_kWh_electric", "synthetic")[0])),
            "Synthetic fuel energy change\n(253 h replay, thermal)": abs(float(D.econ("energy_delta_fuel_energy_kWh_thermal", "point")[0]))}
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.barh(list(vals), list(vals.values()), color=["#1f6f8b", "#edae49", "#d1495b"])
    ax.set_xscale("log")
    ax.set_xlabel("kWh (absolute value, log scale; fuel = thermal, others electric)")
    for i, v in enumerate(vals.values()):
        ax.text(v * 1.15, i, f"{v:,.1f}", va="center")
    ax.set_xlim(1, max(vals.values()) * 8)
    ax.set_title(f"AI energy is tiny next to the synthetic fuel effect  ({TAG})", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGS / "f4_energy.png", dpi=150)
    plt.close(fig)
    # F5 timeline with stop gates
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.axis("off")
    ph = [(0, 2, "Wk 1-2\napprovals + data", "#dfe7ee"), (2, 4, "Wk 3-4\nread-only shadow", "#cfe8d5"), (4, 5, "Wk 5\nadvisory\nif authorised", "#fff3b0"), (5, 6, "Wk 6\nM&V + GO/REVISE/STOP", "#f4cccc")]
    for a, b, t, c in ph:
        ax.barh(0, b - a, left=a, color=c, edgecolor="#555")
        ax.text((a + b) / 2, 0, t, ha="center", va="center", fontsize=9)
    ax.axvline(2, color="#b00020", lw=2)
    ax.text(2, .62, "STOP check every week (6 stop conditions)", color="#b00020", fontsize=9, ha="left")
    ax.set_xlim(0, 6)
    ax.set_ylim(-.6, 1)
    fig.tight_layout()
    fig.savefig(FIGS / "f5_timeline.png", dpi=150)
    plt.close(fig)
    L.f("figure_baseline_bands", len(g), "{:.0f}", "data/clean/clean_heater_c.csv load bands with >=30 windows")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-tests", action="store_true", help="reuse test counts from reports/final_numbers.csv instead of running pytest")
    run(ap.parse_args().skip_tests)


def run(skip_tests=False):
    FIN.mkdir(exist_ok=True)
    derive_numbers(with_tests=not skip_tests)
    D, L = Data(), Ledger()
    admin = admin_facts()
    figures(D, L)
    from src import final_deck, final_pdf, final_text
    final_pdf.proposal(D, L, admin)
    final_pdf.appendix(D, L, admin)
    notes = final_text.speaker_notes(D, L)
    final_deck.build(D, L, notes)
    final_text.write_docs(D, L, admin, notes)
    m = L.table()
    m.round(4).to_csv(FIN / "number_source_map.csv", index=False)
    print(f"number -> source map ({len(m)} numbers), written to final/number_source_map.csv")
    for r in m.itertuples():
        print(f"  {r.label:38s} {r.value:>14,.4f}  <- {r.source}")


if __name__ == "__main__":
    main()
