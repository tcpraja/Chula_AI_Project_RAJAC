"""Predict next-15-minute fuel (kg/h) with a saved model; NO_ADVICE with reason codes outside the eligible window.

Every output row carries the banner "SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION". The forecast is decision support only;
BMS/SIS/DCS remain the only control authorities.
Run: python -m src.predict --model selected --split test --n 5
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src import features as ft

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
BANNER = "SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION"
FILES = {"P": "P_persistence", "P2": "P2_current_feed", "A": "A_physics", "B": "B_linear", "L": "L_linear_full", "C": "C_hgb", "C0": "C0_hgb"}
WIDE_REL = 0.15  # interval width > 15 % of the prediction -> WIDE_INTERVAL


def load_meta():
    return json.loads((MODELS / "metadata.json").read_text(encoding="utf-8"))


def resolve(name):
    return load_meta()["selected"] if name == "selected" else name


def predict_raw(F, name):
    """Point forecast for every row (NaN where the model cannot compute it) and the conformal half-width."""
    m = joblib.load(MODELS / f"{FILES[name]}.joblib")
    t = m["type"]
    if t == "persistence":
        p = F["fuel_lag1"].to_numpy(float)
    elif t == "current_feed":
        p = (F["feeder_speed_pct"] * m["capacity_kgh"] / 100.0).to_numpy(float)
    elif t == "physics":
        p = (F["Q_out_MW"] * 3600.0 / (m["eta_base"] * F["bed_LHV_MJkg"])).to_numpy(float)
    elif t == "linear":
        X = F[m["features"]]
        coef = np.asarray(m["coef"])
        p = np.where(X.notna().all(axis=1), coef[0] + X.fillna(0).to_numpy() @ coef[1:], np.nan)
    else:
        p = m["model"].predict(F[m["features"]])
    return np.asarray(p, float), float(m["half"])


def predict(F, name="selected"):
    """Return a frame: y_hat, lo, hi, status (PREDICTED | NO_ADVICE:<codes>), banner."""
    name = resolve(name)
    if name is None:
        raise SystemExit("no model was selected (no candidate passed the safety gate): NO_ADVICE for every row")
    p, half = predict_raw(F, name)
    status = np.full(len(F), "PREDICTED", dtype=object)
    code = []
    for i in range(len(F)):
        c = []
        if not F["eligible"].iloc[i]:
            c.append(str(F["eligibility"].iloc[i]).split(":")[-1] if ":" in str(F["eligibility"].iloc[i]) else "NOT_ELIGIBLE")
        if np.isnan(p[i]):
            c.append("LOW_FUEL_CONF")
        elif half / max(abs(p[i]), 1.0) * 2 > WIDE_REL:
            c.append("WIDE_INTERVAL")
        code.append(";".join(c))
    code = np.array(code, dtype=object)
    status = np.where(code == "", "PREDICTED", "NO_ADVICE:" + code)
    ok = code == ""
    out = pd.DataFrame({"timestamp_local": F["timestamp_local"].to_numpy(), "model": name, "y_hat_kgh": np.where(ok, p, np.nan),
                        "lo_kgh": np.where(ok, p - half, np.nan), "hi_kgh": np.where(ok, p + half, np.nan), "status": status, "banner": BANNER})
    return out


def features_for(split):
    from src import train
    from src.cleaning import load_cfg
    cfg = load_cfg()
    d = ft.load_clean().sort_values("t").reset_index(drop=True)
    F = train.assign_split(ft.build(d), cfg)
    if split != "all":
        F = F[(F.split == split) & F.y_ok]
    return F.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="selected", help="selected | P | P2 | A | B | L | C0 | C")
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "all"])
    ap.add_argument("--n", type=int, default=5, help="rows to print")
    a = ap.parse_args()
    F = features_for(a.split)
    out = predict(F, a.model)
    out = out.assign(actual_kgh=F["y"].to_numpy())
    print(out.head(a.n).round(1).to_string(index=False))
    print(out["status"].str.split(":").str[0].value_counts().to_dict(), "|", BANNER)


if __name__ == "__main__":
    main()
