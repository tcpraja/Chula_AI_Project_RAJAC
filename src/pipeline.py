"""Pipeline stages. Phase 7: generate, clean, baseline, train, optimize, shadow, final. Later phase adds dryrun.

Run: python -m src.pipeline --stage all|generate|clean|baseline [--site <yaml>] [--source synthetic|csv --path <file>]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from src import cleaning, engineering, generate_synthetic as gen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv"
CLEAN = ROOT / "data" / "clean" / "clean_heater_c.csv"
REJ = ROOT / "data" / "clean" / "rejected_rows.csv"
LATER = ("dryrun",)


def stage_generate():
    res = gen.generate(42, 60)
    gen.write_outputs(res, RAW)
    st = gen.generate(77, 30)
    gen.write_outputs(st, ROOT / "data" / "stress" / "stress_seed77.csv", ROOT / "data" / "stress" / "display_reconciliation.csv")
    print(f"generate: main {res['main'].shape}, stress {st['main'].shape}")


def clean_frame(raw, cfg):
    """raw -> (full engineered clean frame with eligibility, rejected rows, report, lag). Pure function."""
    probe, _, _ = cleaning.clean(raw, cfg, lag_steps=0)
    lag, rs = cleaning.estimate_lag(probe, cfg, until_frac=cfg["lag"]["train_frac"])
    good, rej, rep = cleaning.clean(raw, cfg, lag_steps=lag)
    full = engineering.compute(good, cfg)
    full["eligibility"] = engineering.layer1_layer2(full, cfg)
    return full, rej, rep, lag, rs


def stage_clean(raw_path=RAW, out=CLEAN, rejected=REJ, cfg_path=None):
    cfg = cleaning.load_cfg(cfg_path)
    raw = pd.read_csv(raw_path)
    full, rej, rep, lag, rs = clean_frame(raw, cfg)
    out, rejected = Path(out), Path(rejected)
    out.parent.mkdir(parents=True, exist_ok=True)
    full.round(5).to_csv(out, index=False)
    rej.to_csv(rejected, index=False)
    # evaluation-only sidecar (generator labels; never a model input)
    key = raw["timestamp_local"].str[:19]
    lab = raw.assign(_k=key)[["_k", "scenario_id", "is_fault_injected", "true_synthetic_best_action", "fuel_rate_true_kgh", "quality_flag", "advice_eligibility"]]
    lab = lab.rename(columns={"quality_flag": "gen_quality_flag", "advice_eligibility": "gen_advice_eligibility"})
    truth_path = Path(raw_path).parent / ("synthetic_truth.csv" if Path(raw_path).name == "synthetic_heater_c_5min.csv" else Path(raw_path).stem + "_truth.csv")
    if truth_path.exists():
        tr = pd.read_csv(truth_path, usecols=["timestamp_local", "best_action_eta_gain_pp", "eta_true", "Q_out_true_MW", "O2_true_pct_dry", "O2_opt_true_pct"])
        lab = lab.merge(tr.rename(columns={"timestamp_local": "_k"}), on="_k", how="left")
    lab = lab.drop_duplicates("_k")
    ev = full[["timestamp_local"]].assign(_k=full["timestamp_local"].str[:19]).merge(lab, on="_k", how="left").drop(columns="_k")
    ev.to_csv(out.parent / "eval_labels.csv", index=False)
    rep.update(lag_corr=[round(float(r), 4) for r in rs], eligibility=full["eligibility"].str.split(":").str[0].value_counts().to_dict(),
               status_SFC=full["status_SFC"].value_counts().to_dict(), status_eta=full["status_eta"].value_counts().to_dict(),
               status_Q_out=full["status_Q_out"].value_counts().to_dict(), lhv_basis=full["LHV_basis"].value_counts().to_dict())
    (out.parent / "clean_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    from src import dq_report
    dq_report.run(raw_path, cfg)
    print(f"clean: raw {rep['n_raw']} -> clean {rep['n_clean']} + rejected {rep['n_rejected']}; lag_steps={lag}")
    print("rejected reasons:", rep["reject_counts"])
    print("status_SFC:", rep["status_SFC"], "| status_eta:", rep["status_eta"])
    print("eligibility:", rep["eligibility"])
    return rep


def stage_train():
    from src import train, train_extras
    r = train.run()
    print(train.table_print(r["tbl"], train.NAMES))
    print("selected:", r["chosen"], "| best reference:", r["best_ref"], "| beats it (val/test):", r["beats_ref"], r["beats_test"])
    train_extras.run(r)


def stage_optimize():
    from src import compare
    compare.run("test")


def stage_shadow():
    from src import shadow
    S = shadow.run("test")
    print(f"shadow: {len(S)} held-out rows replayed; decisions {S['ai_decision'].value_counts().to_dict()}; sha256 {shadow.file_hash()[:16]}")


def stage_final():
    """Energy bookkeeping, economics workbook, then the submission set in final/ (needs reports/ai_runtime_measured.csv)."""
    from src import build_final, economics, energy_calc
    energy_calc.run("test")
    economics.run()
    build_final.run()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="all", choices=["all", "generate", "clean", "baseline", "train", "optimize", "shadow", "final", *LATER])
    ap.add_argument("--site", default=None, help="site yaml (thresholds); default config/cleaning_engineering.yaml")
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "csv"])
    ap.add_argument("--path", default=None, help="raw CSV when --source csv")
    a = ap.parse_args()
    if a.stage in LATER:
        raise SystemExit(f"stage '{a.stage}' is not implemented yet (added in a later phase)")
    raw = Path(a.path) if a.source == "csv" and a.path else RAW
    if a.stage in ("all", "generate") and a.source == "synthetic":
        stage_generate()
    if a.stage in ("all", "clean"):
        stage_clean(raw, cfg_path=a.site)
    if a.stage in ("all", "baseline"):
        from src import baseline
        baseline.run()
    if a.stage in ("all", "train"):
        stage_train()
    if a.stage in ("all", "optimize"):
        stage_optimize()
    if a.stage in ("all", "shadow"):
        stage_shadow()
    if a.stage in ("all", "final"):
        stage_final()


if __name__ == "__main__":
    main()
