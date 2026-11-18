"""CP10 correction: calibrate the action menu and the minimum-benefit threshold on the VALIDATION split only,
then score the chosen variant once on the test split. SYNTHETIC - NOT FOR PLANT OPERATION.

Pre-registered selection rule (written before any test score is seen):
  1 candidates: combo_max_step_pct in {None, 2} x min_benefit_sfc_kg_gj in {0.0, 0.1, 0.2, 0.3}
  2 keep variants whose validation false-alert rate (actionable subset) <= the rule comparator's validation false-alert rate
  3 among those, take the highest validation exact-hit rate; ties -> fewer alerts, then the smaller change from the original
  4 if no variant passes step 2, keep the original config and report that the false-alert gap is not closed
The test split is scored once, for the original and the chosen variant only. The generator is not changed.
Writes reports/menu_calibration.csv (validation grid + test for original/chosen) and reports/menu_calibration.md.
Run: python -m src.calibrate_menu [--apply]   (--apply writes the chosen values to config/guardrail_limits.yaml)
"""
import argparse
import copy
import re

import numpy as np
import pandas as pd

from src import baseline, compare, guardrails as gd, optimizer as op
from src.cleaning import load_cfg

ROOT = op.ROOT
REP = ROOT / "reports"
GRID = [(c, b) for c in (None, 2) for b in (0.0, 0.1, 0.2, 0.3)]


def score(d, F, eff, G, cfg, split):
    x, R = op.run_split(d, F, eff, G, split)
    rows = baseline.baseline_rows(d)
    rl = baseline.rule_alerts(d, rows, cfg)
    rl = rl[(rl["split"] == split) & rl["rule_alert"].notna()]
    S = x.assign(**{k: R[k].to_numpy() for k in ("decision", "action")}).set_index("timestamp_local")
    S = S.loc[rl["timestamp_local"]].reset_index()
    S = S[S["true_synthetic_best_action"].notna()]
    rl = rl.set_index("timestamp_local").loc[S["timestamp_local"]]
    label = S["true_synthetic_best_action"].to_numpy(object)
    gain = S["best_action_eta_gain_pp"].to_numpy(float)
    strong = cfg["baseline"]["avoidable_gain_pp"]
    ai = pd.DataFrame(compare.metrics("AI", (S["decision"] == "ADVICE").to_numpy(), S["action"].to_numpy(object), label, gain, strong))
    ra = rl["rule_alert"].astype(bool).to_numpy()
    tr_lab = d[(d["split"] == "train") & d["eligibility"].str.startswith("ELIGIBLE")]["true_synthetic_best_action"]
    default = tr_lab[~tr_lab.isin(["HOLD", "NONE"])].mode().iat[0]
    ru = pd.DataFrame(compare.metrics("rule", ra, np.where(ra, default, "NONE").astype(object), label, gain, strong))
    a, r = ai.iloc[0], ru.iloc[0]                                  # actionable subset
    return {"n_rows": int(a["n_rows"]), "n_actionable": int(a["n_target_rows"]), "alerts": int(a["alerts"]),
            "hit_rate_exact": a["hit_rate_exact"], "hit_rate_direction": a["hit_rate_direction"], "false_alert_rate": a["false_alert_rate"],
            "precision_exact": a["precision_exact"], "avoidable_hit_exact": ai.iloc[1]["hit_rate_exact"],
            "rule_hit_rate_exact": r["hit_rate_exact"], "rule_false_alert_rate": r["false_alert_rate"], "rule_alerts": int(r["alerts"])}


def variant(G0, combo, mb):
    G = copy.deepcopy(G0)
    G["optimizer"]["combo_max_step_pct"] = combo
    G["optimizer"]["min_benefit_sfc_kg_gj"] = mb
    return G


def choose(val):
    ok = val[val["false_alert_rate"] <= val["rule_false_alert_rate"] + 1e-12]
    if ok.empty:
        return None
    ok = ok.assign(_chg=(ok["combo_max_step_pct"].notna()).astype(int) + ok["min_benefit_sfc_kg_gj"])
    return ok.sort_values(["hit_rate_exact", "alerts", "_chg"], ascending=[False, True, True]).iloc[0]


def run(apply=False):
    G0 = gd.load_limits(None)
    cfg = load_cfg()
    d, F, _ = op.load_frames()
    eff = op.fit_from_clean(d, G0)
    rows = []
    for combo, mb in GRID:
        s = score(d, F, eff, variant(G0, combo, mb), cfg, "val")
        rows.append({"split": "val", "combo_max_step_pct": combo, "min_benefit_sfc_kg_gj": mb, **s})
    val = pd.DataFrame(rows)
    orig = (G0["optimizer"].get("combo_max_step_pct"), float(G0["optimizer"]["min_benefit_sfc_kg_gj"]))
    pick = choose(val)
    chosen = orig if pick is None else (None if pd.isna(pick["combo_max_step_pct"]) else int(pick["combo_max_step_pct"]), float(pick["min_benefit_sfc_kg_gj"]))
    test = []
    for tag, (combo, mb) in (("original", orig), ("chosen", chosen)):
        s = score(d, F, eff, variant(G0, combo, mb), cfg, "test")
        test.append({"split": f"test_{tag}", "combo_max_step_pct": combo, "min_benefit_sfc_kg_gj": mb, **s})
    out = pd.concat([val, pd.DataFrame(test)], ignore_index=True)
    out["provenance"] = "SYNTHETIC; selection on validation only; test scored once for original and chosen"
    REP.mkdir(exist_ok=True)
    out.round(4).to_csv(REP / "menu_calibration.csv", index=False)
    write_md(out, orig, chosen, pick is None)
    if apply and chosen != orig:
        p = ROOT / "config" / "guardrail_limits.yaml"
        t = p.read_text(encoding="utf-8")
        t = re.sub(r"(min_benefit_sfc_kg_gj:\s*)[0-9.]+", lambda m: m.group(1) + f"{chosen[1]}", t)
        t = re.sub(r"(combo_max_step_pct:\s*)(null|[0-9.]+)", lambda m: m.group(1) + ("null" if chosen[0] is None else str(chosen[0])), t)
        p.write_text(t, encoding="utf-8")
    print(out[["split", "combo_max_step_pct", "min_benefit_sfc_kg_gj", "alerts", "hit_rate_exact", "false_alert_rate",
               "rule_hit_rate_exact", "rule_false_alert_rate"]].round(3).to_string(index=False))
    print("original", orig, "chosen", chosen)
    return out, orig, chosen


def write_md(out, orig, chosen, none_passed):
    f = lambda v: "full grid" if v is None or (isinstance(v, float) and np.isnan(v)) else f"<= {int(v)} %"
    L = ["# Action-menu and alert-threshold calibration (CP10) - SYNTHETIC, NOT FOR PLANT OPERATION", "",
         "Selection on the validation split only, with a rule fixed before the test split was scored: keep variants whose false-alert rate "
         "is no worse than the rule comparator's on validation, then take the highest exact-hit rate. Test scored once for the original and the chosen variant.", "",
         "| split | two-axis menu | min benefit kg/GJ | alerts | exact hit | false alert | rule exact hit | rule false alert |", "|---|---|---|---|---|---|---|---|"]
    for r in out.itertuples(index=False):
        L.append(f"| {r.split} | {f(r.combo_max_step_pct)} | {r.min_benefit_sfc_kg_gj} | {r.alerts} | {100*r.hit_rate_exact:.1f} % | "
                 f"{100*r.false_alert_rate:.1f} % | {100*r.rule_hit_rate_exact:.1f} % | {100*r.rule_false_alert_rate:.1f} % |")
    L += ["", f"Original: menu {f(orig[0])}, min benefit {orig[1]}. Chosen: menu {f(chosen[0])}, min benefit {chosen[1]}."]
    if none_passed:
        L.append("No variant met the false-alert condition on validation; the original config is kept and the gap stays OPEN.")
    L += ["", "Truth labels are generator outputs used for evaluation only. Exact hit = proposed action equals the generator's best action on actionable rows; "
          "false alert = advice on rows where the generator's best action is HOLD. Associations only, no causal claim."]
    (REP / "menu_calibration.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    run(ap.parse_args().apply)
