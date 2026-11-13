"""AI advisory vs rule comparator on a held-out split, plus the Phase 4 reports. SYNTHETIC - NOT FOR PLANT OPERATION.

Truth is the generator's true_synthetic_best_action (evaluation only, never an input). Hit rate = share of truly actionable rows
(best action not HOLD/NONE, i.e. true gain >= best_gain_min_pp) where the method proposed the exact best action; false-alert
rate = share of non-actionable rows where the method raised an alert. Same rows, same denominators for every method.
Run: python -m src.optimizer --split test
"""
import numpy as np
import pandas as pd

from src import baseline, guardrails as gd, optimizer as op
from src.cleaning import load_cfg

ROOT = op.ROOT
REP = ROOT / "reports"
CAUSAL = ("Causal limits: the action-effect model is fitted to synthetic observational data with a generator-built exploration component; "
          "its delta-efficiency for a proposed move is an association, not an identified causal effect, and on real plant data confounding "
          "(operators move FD/grate in response to load, fuel and air demand) would bias it. All benefits are synthetic generator "
          "illustrations, never savings; every output requires human review; BMS/SIS/DCS remain the only control authorities.")


def sign(v):
    return int(np.sign(v))


def parse(label):
    fd = g = 0
    for part in str(label).split("&"):
        if part.startswith("FD"):
            fd = int(part[2:])
        elif part.startswith("GRATE"):
            g = int(part[5:])
    return fd, g


def metrics(name, alert, action, label, gain, strong_pp):
    """alert: bool array; action: proposed action label per row ('NONE' if none); label/gain: truth."""
    act = ~pd.Series(label).isin(["HOLD", "NONE"]).to_numpy()
    strong = act & (gain >= strong_pp)
    out = []
    for sub, mask in (("actionable(gain>=0.15pp)", act), (f"avoidable(gain>={strong_pp}pp)", strong)):
        non = ~mask if sub.startswith("act") else (~act | (gain < strong_pp))
        hit = alert & mask & (action == label)
        direc = np.array([alert[i] and mask[i] and parse(action[i]) != (0, 0) and sign(parse(action[i])[0]) == sign(parse(label[i])[0])
                          and sign(parse(action[i])[1]) == sign(parse(label[i])[1]) for i in range(len(alert))])
        out.append({"method": name, "subset": sub, "n_rows": len(alert), "n_target_rows": int(mask.sum()), "alerts": int(alert.sum()),
                    "hit_exact": int(hit.sum()), "hit_rate_exact": hit.sum() / max(mask.sum(), 1),
                    "hit_rate_any_alert": (alert & mask).sum() / max(mask.sum(), 1), "hit_rate_direction": direc.sum() / max(mask.sum(), 1),
                    "false_alerts": int((alert & non).sum()), "false_alert_rate": (alert & non).sum() / max(non.sum(), 1),
                    "precision_exact": hit.sum() / max(alert.sum(), 1)})
    return out


def run(split="test", limits_path=None):
    G = gd.load_limits(limits_path)
    cfg = load_cfg()
    d, F, _ = op.load_frames()
    eff = op.fit_from_clean(d, G)
    x, R = op.run_split(d, F, eff, G, split)
    op.write_records(R, op.OUT / f"advisory_records_{split}.jsonl")
    # rule comparator on the same rows
    rows = baseline.baseline_rows(d)
    rl = baseline.rule_alerts(d, rows, cfg)
    rl = rl[(rl["split"] == split) & rl["rule_alert"].notna()]
    S = x.assign(**{k: R[k].to_numpy() for k in ("decision", "action", "advice_class")}).set_index("timestamp_local")
    S = S.loc[rl["timestamp_local"]].reset_index()
    S = S[S["true_synthetic_best_action"].notna()]
    rl = rl.set_index("timestamp_local").loc[S["timestamp_local"]]
    label = S["true_synthetic_best_action"].to_numpy(object)
    gain = S["best_action_eta_gain_pp"].to_numpy(float)
    strong_pp = cfg["baseline"]["avoidable_gain_pp"]
    tr_lab = d[(d["split"] == "train") & d["eligibility"].str.startswith("ELIGIBLE")]["true_synthetic_best_action"]
    default = tr_lab[~tr_lab.isin(["HOLD", "NONE"])].mode().iat[0]
    ai_alert = (S["decision"] == "ADVICE").to_numpy()
    r_alert = rl["rule_alert"].astype(bool).to_numpy()
    n = len(S)
    M = []
    M += metrics("AI_advisory", ai_alert, S["action"].to_numpy(object), label, gain, strong_pp)
    M += metrics("rule_P75_alert_only(no action given)", r_alert, np.full(n, "ANY", object), label, gain, strong_pp)
    M += metrics(f"rule_P75+default_action({default})", r_alert, np.where(r_alert, default, "NONE").astype(object), label, gain, strong_pp)
    M += metrics("no_change", np.zeros(n, bool), np.full(n, "NONE", object), label, gain, strong_pp)
    # 'alert only' rule cannot name an action: score it as exact-hit-agnostic (any_alert) and exact = n/a
    M2 = pd.DataFrame(M)
    M2.loc[M2["method"].str.startswith("rule_P75_alert_only"), ["hit_exact", "hit_rate_exact", "hit_rate_direction", "precision_exact"]] = np.nan
    M2.insert(0, "split", split)
    M2["provenance"] = "SYNTHETIC; test-period rows with rule P75 defined; truth = generator labels (evaluation only)"
    # benefit calibration (AI advice rows)
    adv = S[ai_alert].copy()
    pb = R.set_index("timestamp").loc[adv["timestamp_local"], "predicted_benefit_synthetic_only"]
    adv["pred_deta"] = [p["deta_pp"] for p in pb]
    cal = {"n_advice": int(len(adv)), "pred_deta_mean": float(adv["pred_deta"].mean()) if len(adv) else float("nan"),
           "true_best_gain_mean": float(adv["best_action_eta_gain_pp"].mean()) if len(adv) else float("nan"),
           "corr_pred_vs_true_best": float(adv["pred_deta"].corr(adv["best_action_eta_gain_pp"])) if len(adv) > 2 else float("nan"),
           "share_overclaim_gt1pp": float((adv["pred_deta"] - adv["best_action_eta_gain_pp"] > 1.0).mean()) if len(adv) else float("nan")}
    # outputs
    if split == "test":
        REP.mkdir(exist_ok=True)
        M2.round(4).to_csv(REP / "scenario_comparison.csv", index=False)
        constraints_matrix(R, x, eff, G, cal)
        failure_cases(S, R, adv, cal, label)
    print_summary(M2, R, cal, split, eff, default, n)
    return M2, R, cal


def print_summary(M2, R, cal, split, eff, default, n):
    print(f"[{split}] rows scored {n}; decisions (all rows): {R['decision'].value_counts().to_dict()}; model {eff['version']}")
    cols = ["method", "subset", "n_target_rows", "alerts", "hit_rate_exact", "hit_rate_any_alert", "hit_rate_direction", "false_alert_rate", "precision_exact"]
    print(M2[cols].round(3).to_string(index=False))
    print("benefit calibration:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in cal.items()})
    print(CAUSAL)


def constraints_matrix(R, x, eff, G, cal):
    L, O = G["limits"], G["optimizer"]
    codes = R["_guard_codes"].str.split(";").explode()
    anyc = codes[codes != ""].value_counts()
    only = R["_guard_codes"][~R["_guard_codes"].str.contains(";")].value_counts()
    layer = {"NO_CO": ("2", "CO available (co_available=1, CO measured)"), "BAD_FLOW": ("1", f"HTF flow {L['flow_valid_m3h']} m3/h (+-2 %)"),
             "LOW_FUEL_CONF": ("1", "belt-weighed fuel, lab LHV known, no feeder stop/totalizer reset"), "TRIP_ACTIVE": ("2", "no interlock/trip alarm"),
             "FAN_DERATE": ("2", "no fan derate"), "UNSAFE_DRAFT": ("2", f"draft in {L['draft_band_pa']} Pa"),
             "HIGH_TEMP": ("2", f"furnace <= {L['furnace_temp_limit_c']} C, HTF out <= {L['htf_out_limit_c']} C"),
             "STALE_DATA": ("1", "no signal frozen > 2 samples"), "OOD": ("1", f"Mahalanobis^2 <= train {O['ood_quantile']} quantile ({eff['ood_thr']:.1f})"),
             "ENERGY_BALANCE": ("1", f"{L['eta_valid']} efficiency, heat balance verified"), "TRANSIENT": ("1", f"STEADY, >= {L['stable_steps']} contiguous steps, no sootblow/gap"),
             "WIDE_INTERVAL": ("2 (optimizer)", f"dSFC 90 % interval width <= {L['interval_width_max_sfc_kg_gj']} kg/GJ"), "PROPERTY_OOR": ("1", "HTF temps inside property table"),
             "LIMITS_NOT_APPROVED": ("2", "no limit equals REQUIRES_OEM_APPROVAL"), "LOW_O2": ("2", f"O2 >= {L['o2_floor_pct']} %"),
             "HIGH_CO": ("2", f"CO <= {L['co_limit_ppm']} ppm"), "CMD_FEEDBACK": ("1", "command vs feedback agree"), "NO_BENEFIT": ("2 (optimizer)", "pessimistic dSFC must be below 0")}
    drop = {"LOW_O2_OR_CO_RISK": 0, "OOD": 0, "DRAFT": 0, "RANGE_OR_MOVE": 0}
    for cc in R["constraint_checks"].dropna():
        for k, v in cc["candidates_dropped"].items():
            drop[k] += v
    oc = R[R["eligible"] & (R["decision"] == "NO_ADVICE")]["reason_codes"].explode().value_counts()
    for k in ("WIDE_INTERVAL", "NO_BENEFIT"):
        anyc[k] = int(oc.get(k, 0))
        only[k] = int(oc.get(k, 0))
    nel = int(R["eligible"].sum())
    cls = R["advice_class"].value_counts().to_dict()
    lines = ["# Constraints matrix (SYNTHETIC - NOT FOR PLANT OPERATION)",
             f"Test split rows: {len(R)}; guardrail-eligible: {nel}; decisions: {R['decision'].value_counts().to_dict()}. Limits are synthetic normalized "
             "envelopes (config/guardrail_limits.yaml, ASSUMED / NOT APPROVED); any REQUIRES_OEM_APPROVAL value forces NO_ADVICE.", "",
             "| Reason code | Layer | Pass condition | Rows with code | Rows with only this code |", "|---|---|---|---|---|"]
    for k, (ly, cond) in layer.items():
        lines.append(f"| {k} | {ly} | {cond} | {int(anyc.get(k, 0))} | {int(only.get(k, 0))} |")
    lines += ["", "## Candidate constraints (per eligible row, 25-move FD x grate grid at fixed demand)",
              f"Move <= {L['max_step_fd_pct']} % FD / {L['max_step_grate_pct']} % grate; FD in {L['fd_range_pct']}, grate in {L['grate_range_pct']}; "
              f"predicted O2 >= floor + {O['o2_margin_pct']}; predicted CO x {O['co_margin_factor']} <= limit; predicted draft in band; candidate state not OOD.",
              f"Candidates dropped (sum over eligible rows x 25): {drop}.",
              "'Less excess O2' (O2 falls, floor and CO margin kept) is kept apart from 'low-O2 / CO risk' (dropped, never offered). "
              f"Advice classes on test rows: {cls}.", "",
              "## Models behind the checks (OWN-ESTIMATE, training split only)",
              f"Efficiency response ridge: train R2 {eff['eta_r2_train']:.3f}, residual SD {eff['eta_resid_sd']:.2f} pp, {eff['n_lots']} lots, {O['n_boot']} lot-bootstraps. "
              f"O2 from FD: lambda proportional to FD at fixed demand (stoichiometric). Fan power: kW = k (FD/100)^3, correlation with data {eff['fan_corr']:.4f}.",
              "", "## Causal-limits statement", CAUSAL, ""]
    (REP / "constraints_matrix.md").write_text("\n".join(lines), encoding="utf-8")


def failure_cases(S, R, adv, cal, label):
    adv = adv.assign(label=adv["true_synthetic_best_action"])
    fa = adv[adv["label"].isin(["HOLD", "NONE"])].sort_values("pred_deta", ascending=False).head(5)
    wrong = adv[~adv["label"].isin(["HOLD", "NONE"]) & (adv["action"] != adv["label"])]
    opposite = wrong[[parse(a)[0] * parse(b)[0] < 0 or parse(a)[1] * parse(b)[1] < 0 for a, b in zip(wrong["action"], wrong["label"])]]
    over = adv.assign(over=adv["pred_deta"] - adv["best_action_eta_gain_pp"]).sort_values("over", ascending=False).head(5)
    eligible = S[S["decision"].isin(["NO_ADVICE"]) & ~S["true_synthetic_best_action"].isin(["HOLD", "NONE"])]
    missed = eligible.sort_values("best_action_eta_gain_pp", ascending=False).head(5)
    t = lambda df, cols: "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + [
        "| " + " | ".join(str(round(v, 2)) if isinstance(v, float) else str(v) for v in r) + " |" for r in df[cols].itertuples(index=False)])
    by = adv.assign(exact=(adv["action"] == adv["label"]).astype(float)).groupby("label").agg(n_advice=("exact", "size"), exact_rate=("exact", "mean")).round(3)
    by_md = "\n".join(["| generator best action | advice rows | exact rate |", "|---|---|---|"] + [f"| {i} | {r.n_advice} | {r.exact_rate} |" for i, r in by.iterrows()])
    L = ["# Optimization failure cases (SYNTHETIC - NOT FOR PLANT OPERATION)",
         f"Test advice rows scored: {cal['n_advice']}. Predicted efficiency gain averages {cal['pred_deta_mean']:.2f} pp vs the generator's best-available "
         f"{cal['true_best_gain_mean']:.2f} pp; correlation {cal['corr_pred_vs_true_best']:.2f}; {100 * cal['share_overclaim_gt1pp']:.1f} % of advice over-claims by > 1 pp.",
         f"Advice where the generator says HOLD (false alerts): {int(adv['label'].isin(['HOLD', 'NONE']).sum())}; advice with a different action than the generator's best: "
         f"{len(wrong)} (of which opposite direction on FD or grate: {len(opposite)}).", "",
         f"Advice outside the generator's action menu (4-step move combined with a second axis, can never be an exact hit): {int(sum(1 for a in adv['action'] if parse(a)[0] != 0 and parse(a)[1] != 0 and max(abs(parse(a)[0]), abs(parse(a)[1])) > 2))}.", "",
         "## 1 False alerts with the largest predicted gain", t(fa, ["timestamp_local", "action", "label", "pred_deta", "best_action_eta_gain_pp"]), "",
         "## 2 Largest over-claims (predicted minus generator best gain, pp)", t(over, ["timestamp_local", "action", "label", "pred_deta", "best_action_eta_gain_pp"]), "",
         "## 3 Eligible rows with no advice but a large true gain (missed)", t(missed, ["timestamp_local", "true_synthetic_best_action", "best_action_eta_gain_pp"]) if len(missed) else "none", "",
         "## 4 Exact-action rate by generator best action", by_md if len(by) else "none", "",
         "## Why it fails (diagnosis)",
         "- The effect model is smooth and sees only O2/grate/load/moisture; the generator's optimum depends on a hidden O2 target and a grate optimum, so compound moves are often mis-ranked.",
         "- Bootstrap intervals cover coefficient uncertainty only, not model misspecification, so over-claims occur even when the interval is narrow.",
         "- Guardrails remove unsafe rows, not wrong ones: an eligible, in-distribution row can still get a wrong move. Humans must review.", "", CAUSAL, ""]
    (REP / "optimization_failure_cases.md").write_text("\n".join(L), encoding="utf-8")
