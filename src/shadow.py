"""Shadow replay: score the held-out test split row by row as if live, with NO actuation, and compare against the rule comparator.

Writes reports/shadow_replay.csv (advice / no-advice / reason codes / rule P75 alert). Deterministic: uses the saved effect model
(models/effect_model.joblib, fitted on the training split only) and fixed seeds, so two runs give an identical file.
SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION. Truth columns are evaluation-only and never an input.
Run: python -m src.shadow [--split test]
"""
import argparse
import hashlib

import joblib
import numpy as np
import pandas as pd

from src import baseline, guardrails as gd, optimizer as op
from src.cleaning import load_cfg

OUT = op.ROOT / "reports" / "shadow_replay.csv"


def run(split="test", out=OUT):
    G = gd.load_limits()
    cfg = load_cfg()
    d, F, _ = op.load_frames()
    p = op.MODELS / "effect_model.joblib"
    eff = joblib.load(p) if p.exists() else op.fit_from_clean(d, G)
    x, R = op.run_split(d, F, eff, G, split)
    rl = baseline.rule_alerts(d, baseline.baseline_rows(d), cfg).set_index("timestamp_local")["rule_alert"]
    S = pd.DataFrame({
        "timestamp_local": R["timestamp"], "split": split,
        "ai_decision": R["decision"], "ai_advice": (R["decision"] == "ADVICE"),
        "reason_codes": R["reason_codes"].map(lambda c: ";".join(c)), "action": R["action"], "advice_class": R["advice_class"],
        "dSFC_kg_GJ_point": R["uncertainty"].map(lambda u: np.nan if not u else u["dSFC_kg_GJ_point"]).where(R["decision"] == "ADVICE"),
        "model_version": R["model_version"], "human_review_required": R["human_review_required"]})
    r = S["timestamp_local"].map(rl)
    S["rule_P75_alert"] = r.map(lambda v: "" if pd.isna(v) else str(bool(v)))   # blank = rule undefined (too little history)
    ev = x.set_index("timestamp_local")
    S["eval_best_action"] = S["timestamp_local"].map(ev["true_synthetic_best_action"])      # generator label, evaluation only
    S["eval_best_gain_pp"] = S["timestamp_local"].map(ev["best_action_eta_gain_pp"]).round(4)
    S["dSFC_kg_GJ_point"] = S["dSFC_kg_GJ_point"].round(4)
    S["agreement"] = np.where(S["rule_P75_alert"] == "", "rule_undefined",
                              np.where(S["ai_advice"] & (S["rule_P75_alert"] == "True"), "both_alert",
                                       np.where(S["ai_advice"], "ai_only", np.where(S["rule_P75_alert"] == "True", "rule_only", "neither"))))
    out.parent.mkdir(parents=True, exist_ok=True)
    S.to_csv(out, index=False, lineterminator="\n")
    return S


def file_hash(path=OUT):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", choices=["val", "test"])
    a = ap.parse_args()
    S = run(a.split)
    print(f"shadow[{a.split}]: {len(S)} rows; decisions {S['ai_decision'].value_counts().to_dict()}; agreement {S['agreement'].value_counts().to_dict()}")
    print("sha256:", file_hash())


if __name__ == "__main__":
    main()
