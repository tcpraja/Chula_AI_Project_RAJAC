"""Advisory guardrails (SPEC C7): layer 1 data validity and layer 2 constraints, as pure functions.

evaluate(df, limits, ood=None) -> DataFrame[eligible, outcome, reason_codes]. Missing or NaN required values fail closed.
Outcome: ELIGIBLE (no code) | DIAGNOSTIC_ONLY (only NO_CO) | NO_ADVICE. Any limit equal to "REQUIRES_OEM_APPROVAL" forces
NO_ADVICE with LIMITS_NOT_APPROVED for every row. Limits are synthetic normalized envelopes from config/guardrail_limits.yaml.
Run: python -m src.guardrails --help
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.units import HTFTable

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "REQUIRES_OEM_APPROVAL"
CODES = ["NO_CO", "BAD_FLOW", "LOW_FUEL_CONF", "TRIP_ACTIVE", "FAN_DERATE", "UNSAFE_DRAFT", "HIGH_TEMP", "STALE_DATA", "OOD",
         "ENERGY_BALANCE", "TRANSIENT", "WIDE_INTERVAL", "PROPERTY_OOR", "LIMITS_NOT_APPROVED",
         "LOW_O2", "HIGH_CO", "CMD_FEEDBACK",
         "MODEL_DRIFT", "DATA_FAILURE", "MAE_WORSE_THAN_SIMPLE", "FALSE_ALERTS"]  # LOW_O2..CMD_FEEDBACK: Phase 2 checks; last four: monitor-forced NO_ADVICE (Phase 8)
TRIP_ALARMS = ["ALM_TRIP_DRAFT", "ALM_FEEDER_STOP", "ALM_HTF_T_HIGH", "ALM_FURNACE_T_HIGH"]
REQUIRED = ["operating_mode", "HTF_flow_m3h", "HTF_Tin_C", "HTF_Tout_C", "fuel_mass_basis", "lhv_known", "fuel_rate_aligned_kgh",
            "interlock_active", "alarm_code", "fan_derated", "draft_pa", "furnace_temp_C", "O2_pct_dry", "CO_ppm", "co_available",
            "frozen_signals", "heat_balance_status", "eta_pct", "sootblow", "after_gap", "totalizer_reset", "cmd_feedback_mismatch"]


def load_limits(path=None):
    """Return the full guardrail config dict (keys: provenance, limits, optimizer). With HEATER_SITE set (site mode) the limits come from the site
    config and any limit left as REQUIRES_OEM_APPROVAL keeps every row at NO_ADVICE."""
    import os
    if path is None and os.environ.get("HEATER_SITE") and Path(os.environ["HEATER_SITE"]).exists():
        from src import site_config
        return site_config.load_site(os.environ["HEATER_SITE"]).guardrail_config()
    return yaml.safe_load(Path(path or ROOT / "config" / "guardrail_limits.yaml").read_text(encoding="utf-8"))


def unapproved(limits):
    """Names of limits whose value is the REQUIRES_OEM_APPROVAL placeholder (searches lists too)."""
    lim = limits.get("limits", limits)
    return [k for k, v in lim.items() if v == PLACEHOLDER or (isinstance(v, (list, tuple)) and PLACEHOLDER in v)]


def steady_run_steps(blocked, timestamps):
    """Length of the current run of contiguous 5-min rows that are not blocked (0 at a blocked row)."""
    t = pd.to_datetime(pd.Series(timestamps), utc=True).reset_index(drop=True)
    contig = (t.diff() == pd.Timedelta(minutes=5)).to_numpy()
    run = np.zeros(len(t), int)
    for i in range(len(t)):
        run[i] = 0 if blocked[i] else (run[i - 1] + 1 if i > 0 and contig[i] else 1)
    return run


def evaluate(df, limits=None, ood=None, force_codes=None):
    """Pure layer 1 + layer 2 check. df: frame (or dict of scalars) with the clean-frame columns in REQUIRED.
    Optional df['steady_run_steps'] (else computed from timestamp_local). ood: bool array, True = out of distribution."""
    limits = limits or load_limits()
    if isinstance(df, dict):
        df = pd.DataFrame([df])
    df = df.reset_index(drop=True)
    n = len(df)
    if unapproved(limits):
        return pd.DataFrame({"eligible": False, "outcome": "NO_ADVICE", "reason_codes": "LIMITS_NOT_APPROVED"}, index=range(n))
    if force_codes:                                   # monitor switched the system to NO_ADVICE mode (drift, data failure, ...)
        return pd.DataFrame({"eligible": False, "outcome": "NO_ADVICE", "reason_codes": ";".join(force_codes)}, index=range(n))
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise KeyError(f"guardrails: required columns missing: {missing}")
    L = limits["limits"]
    mode = df["operating_mode"].to_numpy()
    num = lambda c: pd.to_numeric(df[c], errors="coerce").to_numpy(float)
    flow, tin, tout, draft = num("HTF_flow_m3h"), num("HTF_Tin_C"), num("HTF_Tout_C"), num("draft_pa")
    furn, o2, co, eta = num("furnace_temp_C"), num("O2_pct_dry"), num("CO_ppm"), num("eta_pct")
    tab = HTFTable()
    prop_ok = tab.in_range(np.nan_to_num(tin, nan=-1e9)) & tab.in_range(np.nan_to_num(tout, nan=-1e9))
    d0, d1 = L["draft_band_pa"]
    with np.errstate(invalid="ignore"):
        c = {
            "BAD_FLOW": ~((flow >= L["flow_valid_m3h"][0] * 0.98) & (flow <= L["flow_valid_m3h"][1] * 1.02)),
            "LOW_FUEL_CONF": (df["fuel_mass_basis"] == "VOLUMETRIC").to_numpy() | (df["lhv_known"] == 0).to_numpy()
            | (mode == "FEEDER_STOP") | (num("totalizer_reset") > 0) | np.isnan(num("fuel_rate_aligned_kgh")),
            "TRIP_ACTIVE": (num("interlock_active") > 0) | df["alarm_code"].fillna("").isin(TRIP_ALARMS).to_numpy() | (mode == "TRIP"),
            "FAN_DERATE": num("fan_derated") > 0,
            "UNSAFE_DRAFT": ~((draft >= d0) & (draft <= d1)),
            "HIGH_TEMP": ~((furn <= L["furnace_temp_limit_c"]) & (tout <= L["htf_out_limit_c"])),
            "STALE_DATA": df["frozen_signals"].fillna("").astype(str).str.len().gt(0).to_numpy(),
            "ENERGY_BALANCE": (df["heat_balance_status"] == "UNVERIFIED").to_numpy()
            | ((mode == "STEADY") & ~((eta >= 100 * L["eta_valid"][0]) & (eta <= 100 * L["eta_valid"][1]))),
            "PROPERTY_OOR": ~prop_ok,
            "CMD_FEEDBACK": num("cmd_feedback_mismatch") > 0,
            "LOW_O2": ~(o2 >= L["o2_floor_pct"]),
            "HIGH_CO": co > L["co_limit_ppm"],
            "OOD": np.zeros(n, bool) if ood is None else np.asarray(ood, bool),
        }
    c["NO_CO"] = (num("co_available") == 0) | np.isnan(co)
    if "site_unavailable" in df.columns:                     # Phase 8: combustion columns the site does not have force DIAGNOSTIC_ONLY
        unav = df["site_unavailable"].fillna("").astype(str)
        any_u = unav.str.len().gt(0).to_numpy()
        c["LOW_O2"] = c["LOW_O2"] & ~unav.str.contains("O2_pct_dry").to_numpy()
        c["HIGH_CO"] = c["HIGH_CO"] & ~unav.str.contains("CO_ppm").to_numpy()
        no_furn = unav.str.contains("furnace_temp_C").to_numpy()
        c["HIGH_TEMP"] = np.where(no_furn, ~(tout <= L["htf_out_limit_c"]), c["HIGH_TEMP"])
        c["NO_CO"] = c["NO_CO"] | any_u
    c["TRANSIENT"] = (mode != "STEADY") & ~np.isin(mode, ["TRIP", "FEEDER_STOP"]) | (num("sootblow") > 0) | (num("after_gap") > 0)
    c["WIDE_INTERVAL"] = np.zeros(n, bool)  # set by the optimizer once an interval exists
    if "steady_run_steps" in df.columns:
        run = num("steady_run_steps")
    else:
        blocking = np.zeros(n, bool)
        for k, v in c.items():
            if k not in ("NO_CO", "TRANSIENT", "WIDE_INTERVAL"):
                blocking |= v
        blocking |= c["TRANSIENT"]
        run = steady_run_steps(blocking, df["timestamp_local"]) if "timestamp_local" in df.columns else np.zeros(n)
    c["TRANSIENT"] = c["TRANSIENT"] | ~(run >= L["stable_steps"])
    c["LIMITS_NOT_APPROVED"] = np.zeros(n, bool)
    for k in ("MODEL_DRIFT", "DATA_FAILURE", "MAE_WORSE_THAN_SIMPLE", "FALSE_ALERTS"):   # set only through force_codes
        c[k] = np.zeros(n, bool)
    code_str = np.array([";".join(k for k in CODES if c[k][i]) for i in range(n)], dtype=object)
    outcome = np.where(code_str == "", "ELIGIBLE", np.where(code_str == "NO_CO", "DIAGNOSTIC_ONLY", "NO_ADVICE"))
    return pd.DataFrame({"eligible": code_str == "", "outcome": outcome, "reason_codes": code_str})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limits", default=None)
    a = ap.parse_args()
    cfg = load_limits(a.limits)
    print("provenance:", cfg["provenance"], "| unapproved limits:", unapproved(cfg) or "none")
    print("reason codes:", ", ".join(CODES))


if __name__ == "__main__":
    main()
