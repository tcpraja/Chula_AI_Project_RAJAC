"""Phase 6 energy bookkeeping on the held-out test replay. SYNTHETIC illustration, never a saving.

Per advised 5-min row: dFuel_kg = fuel_rate_aligned_kgh * (5/60) * dSFC/SFC_current (same useful heat, so fuel scales with SFC);
fuel energy change MJ = dFuel_kg * LHV_used_MJkg; kWh = MJ / 3.6. Interval = sum of row-level 90 % bounds (the bounds share one set of
ridge coefficients, so they are fully correlated across rows and add linearly; they cover coefficient uncertainty only).
Fan penalty: fan_power_kW_FD column scaled by the fan law kW ~ FD^3 to the proposed FD command (A-register proxy): dkW = kW*((FD_new/FD)^3 - 1).
No CO2 figure is produced: no lifecycle boundary (fuel supply, biogenic accounting, ash) has been defined.
Writes reports/energy_synthetic.json. Run: python -m src.energy_calc
"""
import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "energy_synthetic.json"
STEP_H = 5.0 / 60.0
MJ_PER_KWH = 3.6


def mj_to_kwh(mj):
    return mj / MJ_PER_KWH


def compute(split="test"):
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv").set_index("timestamp_local")
    sp = pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv").set_index("timestamp_local")["split"]
    recs = [json.loads(line) for line in (ROOT / "data" / "advisory" / f"advisory_records_{split}.jsonl").read_text(encoding="utf-8").splitlines()]
    n_rows = len(recs)
    tot = {"point": 0.0, "lo90": 0.0, "hi90": 0.0}
    mj = dict(tot)
    fan_kwh, fan_up, fan_dn, fuel_adv_kg, n_adv, n_skip = 0.0, 0.0, 0.0, 0.0, 0, 0
    for r in recs:
        if r["decision"] != "ADVICE":
            continue
        row = d.loc[r["timestamp"]]
        if sp.get(r["timestamp"]) != split:
            raise ValueError("advisory record outside the split")
        if pd.isna(row["fuel_rate_aligned_kgh"]) or pd.isna(row["LHV_used_MJkg"]):
            n_skip += 1
            continue
        n_adv += 1
        u, sfc = r["uncertainty"], r["predicted_SFC_current"]
        fuel_kg = row["fuel_rate_aligned_kgh"] * STEP_H
        fuel_adv_kg += fuel_kg
        for k, key in (("point", "dSFC_kg_GJ_point"), ("lo90", "dSFC_lo90"), ("hi90", "dSFC_hi90")):
            dkg = fuel_kg * u[key] / sfc
            tot[k] += dkg
            mj[k] += dkg * row["LHV_used_MJkg"]
        ratio = r["proposed_simulated_settings"]["FD_command_pct"] / r["current_simulated_settings"]["FD_command_pct"]
        e = row["fan_power_kW_FD"] * (ratio ** 3 - 1.0) * STEP_H
        fan_kwh += e
        fan_up += max(e, 0.0)
        fan_dn += min(e, 0.0)
    kwh = {k: mj_to_kwh(v) for k, v in mj.items()}
    return {"label": "SYNTHETIC generator illustration, not a saving; coefficient-uncertainty interval only", "split": split,
            "rows_scored": n_rows, "window_hours": n_rows * STEP_H, "advice_rows_used": n_adv, "advice_rows_skipped_missing_fuel_or_lhv": n_skip,
            "fuel_kg_on_advised_rows": fuel_adv_kg, "fuel_mean_kgh_all_rows": float(d.loc[[r["timestamp"] for r in recs], "fuel_rate_aligned_kgh"].mean()),
            "lhv_mean_MJkg": float(d.loc[[r["timestamp"] for r in recs], "LHV_used_MJkg"].mean()),
            "delta_fuel_kg": tot, "delta_fuel_energy_MJ": mj, "delta_fuel_energy_kWh_thermal": kwh,
            "fan_FD_delta_kWh_electric": fan_kwh, "fan_FD_increase_kWh_electric": fan_up, "fan_FD_decrease_kWh_electric": fan_dn, "fan_penalty_note": "signed: negative = FD fan electricity avoided; LESS_EXCESS_O2 moves lower FD",
            "mean_fan_kW_FD_plus_ID_all_rows": float((d.loc[[r["timestamp"] for r in recs], "fan_power_kW_FD"]
                                                      + d.loc[[r["timestamp"] for r in recs], "fan_power_kW_ID"]).mean())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", choices=["val", "test"])
    a = ap.parse_args()
    r = compute(a.split)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if not isinstance(v, dict)})
    for k in ("delta_fuel_kg", "delta_fuel_energy_MJ", "delta_fuel_energy_kWh_thermal"):
        print(k, {a: round(b, 1) for a, b in r[k].items()})


if __name__ == "__main__":
    main()
