"""Cleaning: schema + unit checks, Asia/Bangkok time, duplicates, gaps, frozen sensors, totalizer resets,
command-vs-feedback, lag alignment. Raw is never modified; nothing is interpolated or filled; LHV is never invented.

Run: python -m src.cleaning --help
"""
import argparse
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.units import HTFTable, MKCAL_H_TO_MW

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config" / "cleaning_engineering.yaml"
SAFETY_COLS = ["draft_pa", "interlock_active", "alarm_code", "FD_command_pct", "ID_command_pct", "grate_command_pct"]
INSTANT_AVG = ["HTF_flow_m3h", "HTF_Tin_C", "HTF_Tout_C", "O2_pct_dry", "CO_ppm", "furnace_temp_C", "flue_temp_C",
               "stack_temp_C", "draft_pa", "fuel_rate_measured_kgh", "feeder_speed_pct", "FD_command_pct",
               "ID_command_pct", "grate_command_pct", "fan_power_kW_FD", "fan_power_kW_ID", "ambient_temp_C",
               "ambient_RH_pct", "economizer_dP_pa", "HTF_bypass_pct"]
FLAG_MAX = ["lhv_known", "co_available", "fan_derated", "sootblow", "interlock_active", "HTF_pump_status"]
REJECT_ORDER = ["SCHEMA_INVALID", "DUPLICATE_TIMESTAMP", "FROZEN_SENSOR", "FUEL_IMPLAUSIBLE", "HEAT_IMPLAUSIBLE",
                "PROPERTY_OOR"]


def load_cfg(path=None):
    with open(path or CFG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class RawRow(BaseModel):
    """Schema for one raw 5-min record (NaN is passed as None)."""
    model_config = ConfigDict(extra="ignore")
    timestamp_local: str
    heater_id: str
    operating_mode: Literal["STARTUP", "STEADY", "RAMP", "STANDBY", "TRIP", "FEEDER_STOP"]
    fuel_mass_basis: Literal["WEIGH_BELT", "VOLUMETRIC"]
    lhv_known: Literal[0, 1]
    co_available: Literal[0, 1]
    fan_derated: Literal[0, 1]
    sootblow: Literal[0, 1]
    interlock_active: Literal[0, 1]
    fuel_LHV_asfired_MJkg: Optional[float] = Field(None, ge=5, le=30)
    fuel_moisture_wb_pct: Optional[float] = Field(None, ge=0, le=60)
    fuel_rate_measured_kgh: Optional[float] = Field(None, ge=0, le=20000)
    fuel_totalizer_kg: Optional[float] = Field(None, ge=0)
    HTF_flow_m3h: Optional[float] = Field(None, ge=0, le=3000)
    HTF_Tin_C: Optional[float] = Field(None, ge=-50, le=1000)
    HTF_Tout_C: Optional[float] = Field(None, ge=-50, le=1000)
    O2_pct_dry: Optional[float] = Field(None, ge=0, le=21.5)
    CO_ppm: Optional[float] = Field(None, ge=0, le=20000)
    FD_command_pct: float = Field(ge=0, le=100)
    ID_command_pct: float = Field(ge=0, le=100)
    grate_command_pct: float = Field(ge=0, le=100)
    furnace_temp_C: Optional[float] = Field(None, ge=-50, le=2000)
    flue_temp_C: Optional[float] = Field(None, ge=-50, le=2000)
    draft_pa: Optional[float] = Field(None, ge=-5000, le=5000)
    HTF_bypass_pct: float = Field(ge=0, le=100)
    ambient_RH_pct: Optional[float] = Field(None, ge=0, le=100)
    feeder_speed_pct: Optional[float] = Field(None, ge=0, le=100)


def validate_schema(df, cfg):
    """Return a Series of '' (valid) or the first schema error."""
    recs = df.astype(object).where(df.notna(), None).to_dict("records")
    out = []
    for r in recs:
        try:
            m = RawRow.model_validate(r)
            out.append("" if m.heater_id == cfg["heater_id"] else "heater_id")
        except ValidationError as e:
            out.append(str(e.errors()[0]["loc"][0]))
    return pd.Series(out, index=df.index)


def parse_time(s, tz):
    t = pd.to_datetime(s)
    return t.dt.tz_localize(tz) if t.dt.tz is None else t.dt.tz_convert(tz)


def detect_frozen(df, cfg):
    """True for rows in a run of >= frozen_run identical consecutive values of a monitored signal."""
    n = cfg["frozen_run"]
    flagged = pd.Series(False, index=df.index)
    which = pd.Series("", index=df.index, dtype=object)
    for c in cfg["frozen_cols"]:
        if c not in df:
            continue
        v = df[c]
        same = (v == v.shift(1)) & v.notna()
        if c in cfg["frozen_ignore_zero"]:
            same &= v != 0
        run_id = (~same).cumsum()
        run_len = same.groupby(run_id).transform("sum") + 1  # includes the run's first (genuine) sample
        in_run = same | same.shift(-1, fill_value=False)
        hit = in_run & (run_len >= n)
        flagged |= hit
        which = which.where(~hit, which + c + ";")
    return flagged, which


def totalizer_increments(df):
    """Interval kg from a cumulative totalizer: diff, then (on a reset) the post-reset value. Never negative."""
    tot = df["fuel_totalizer_kg"]
    d = tot.diff()
    reset = d < 0
    inc = d.where(~reset, tot)
    return inc, reset.fillna(False)


def resample_to_grid(df, step_min=5):
    """Instantaneous signals -> mean; totalizers -> diff (reset-aware) then sum; flags -> max; labels -> last."""
    x = df.copy()
    t = pd.to_datetime(x["timestamp_local"])
    inc, _ = totalizer_increments(x)
    x["_inc"] = inc
    g = x.groupby(t.dt.floor(f"{step_min}min"))
    out = g[[c for c in INSTANT_AVG if c in x]].mean()
    out["fuel_kg_interval_totalizer"] = g["_inc"].sum(min_count=1)
    out["fuel_totalizer_kg"] = g["fuel_totalizer_kg"].last()
    for c in FLAG_MAX:
        if c in x:
            out[c] = g[c].max()
    for c in x.columns:
        if c not in out and c not in ("timestamp_local", "_inc"):
            out[c] = g[c].last()
    out.insert(0, "timestamp_local", out.index.strftime("%Y-%m-%d %H:%M:%S"))
    return out.reset_index(drop=True)


def estimate_lag(clean_df, cfg, until_frac=None):
    """Lag (steps) of reported heat behind measured fuel: argmax correlation of first differences.
    Uses cleaned rows only, trailing relationship only; pass until_frac to estimate on the training period."""
    x = clean_df[clean_df["operating_mode"].isin(["STEADY", "RAMP"]) & (clean_df["fuel_mass_basis"] == "WEIGH_BELT")
                 & (clean_df["after_gap"] == 0)]
    if until_frac:
        x = x.iloc[: int(len(x) * until_frac)]
    d = cfg["lag"]["diff_steps"]
    f, q = x["fuel_rate_measured_kgh"].diff(d), x["rep_Q_out_MW"].diff(d)
    rs = [f.shift(k).corr(q) for k in range(cfg["lag"]["max_steps"] + 1)]
    return int(np.nanargmax(rs)), rs


def clean(raw, cfg=None, lag_steps=0):
    """Return (clean_df, rejected_df, report). `raw` is not modified."""
    cfg = cfg or load_cfg()
    tab = HTFTable()
    df = raw.copy()
    df.insert(0, "_row", np.arange(len(df)))
    step = pd.Timedelta(minutes=cfg["step_min"])
    df["_ts"] = parse_time(df["timestamp_local"], cfg["timezone"])
    reasons = {k: pd.Series(False, index=df.index) for k in REJECT_ORDER}
    # 1 schema
    err = validate_schema(df, cfg)
    reasons["SCHEMA_INVALID"] = err != ""
    # 2 order and duplicates
    df = df.sort_values(["_ts", "_row"], kind="stable")
    err, reasons = err.loc[df.index], {k: v.loc[df.index] for k, v in reasons.items()}
    reasons["DUPLICATE_TIMESTAMP"] = df["_ts"].duplicated(keep="first")
    # 3 gaps (on the de-duplicated, schema-valid sequence)
    ok_seq = ~(reasons["SCHEMA_INVALID"] | reasons["DUPLICATE_TIMESTAMP"])
    dt = df["_ts"].where(ok_seq).ffill().diff()
    df["gap_before_steps"] = (dt / step - 1).where(ok_seq).round().clip(lower=0).fillna(0).astype(int)
    df["after_gap"] = (df["gap_before_steps"] > 0).astype(int)
    # 4 frozen sensors
    frozen, which = detect_frozen(df.where(ok_seq), cfg)
    reasons["FROZEN_SENSOR"] = frozen & ok_seq
    df["frozen_signals"] = which
    # 5 totalizer
    inc, reset = totalizer_increments(df)
    df["fuel_kg_interval_totalizer"] = inc
    df["totalizer_reset"] = reset.astype(int)
    # 6 plausibility and property table (recomputed here, generator labels are not trusted)
    tin, tout = df["HTF_Tin_C"], df["HTF_Tout_C"]
    tm = (tin + tout) / 2
    in_tab = tab.in_range(tin.fillna(-1)) & tab.in_range(tout.fillna(-1)) & tab.in_range(tm.fillna(-1))
    reasons["PROPERTY_OOR"] = pd.Series(~in_tab, index=df.index)
    Tin_s, Tout_s = tin.where(in_tab, tab.tmin), tout.where(in_tab, tab.tmin)
    q_calc = pd.Series(np.where(in_tab, tab.heat_mw(df["HTF_flow_m3h"].fillna(0).to_numpy(), Tin_s.to_numpy(), Tout_s.to_numpy()), np.nan), index=df.index)
    operating = df["operating_mode"].isin(["STEADY", "RAMP"])
    dT = tout - tin
    reasons["HEAT_IMPLAUSIBLE"] = (q_calc > cfg["heat_max_mw"]) | (operating & ((dT < cfg["dT_valid_K"][0]) | (dT > cfg["dT_valid_K"][1])))
    implied = df["feeder_speed_pct"] * cfg["feeder_cap_kgh"] / 100.0
    reasons["FUEL_IMPLAUSIBLE"] = (implied > 50) & ((df["fuel_rate_measured_kgh"] - implied).abs() / implied.clip(lower=1) > cfg["fuel_speed_mismatch"])
    # 7 unit and command-vs-feedback checks (flags, not rejects)
    rep_q = df["Q_out_MW"]
    ratio = rep_q / q_calc
    unit_slip = np.zeros(len(df), bool)
    for fac in (MKCAL_H_TO_MW, 1 / MKCAL_H_TO_MW, 4.184, 1 / 4.184):
        unit_slip |= ((ratio / fac - 1).abs() < 0.03).fillna(False).to_numpy()
    df["unit_suspect"] = (unit_slip | (df["draft_pa"].abs() > cfg["draft_abs_max_pa"]).fillna(False).to_numpy()).astype(int)
    fb = np.zeros(len(df), bool)
    for key, cmd, pw in (("FD", "FD_command_pct", "fan_power_kW_FD"), ("ID", "ID_command_pct", "fan_power_kW_ID")):
        exp = cfg["fan_rated_kw"][key] * (df[cmd] / 100.0) ** 3
        fb |= ((df[cmd] >= cfg["cmd_feedback_min_cmd"]) & ((df[pw] / exp - 1).abs() > cfg["cmd_feedback_tol"])).fillna(False).to_numpy()
    df["cmd_feedback_mismatch"] = fb.astype(int)
    # 8 flags carried to engineering
    df["heat_balance_status"] = np.where(df["HTF_bypass_pct"] > 0, "UNVERIFIED", "OK")
    df["fuel_rel_unc"] = np.where(df["fuel_mass_basis"] == "VOLUMETRIC", cfg["unc"]["fuel_vol_rel"], cfg["unc"]["fuel_belt_rel"])
    # 9 split
    all_r = pd.concat({k: v.fillna(False).astype(bool) for k, v in reasons.items()}, axis=1)
    primary = pd.Series(np.select([all_r[k].to_numpy() for k in REJECT_ORDER], REJECT_ORDER, default=""), index=df.index)
    allr = pd.Series(["" for _ in range(len(df))], index=df.index, dtype=object)
    for k in REJECT_ORDER:
        allr = allr.where(~all_r[k], allr + np.where(allr == "", "", ";") + k)
    bad = primary != ""
    rej = raw.iloc[df.loc[bad, "_row"].to_numpy()].copy()
    rej.insert(0, "reject_reason", primary[bad].to_numpy())
    rej.insert(1, "all_reasons", allr[bad].to_numpy())
    good = df[~bad].copy()
    # 10 lag alignment by timestamp (trailing only; NaN if the earlier row is missing)
    if lag_steps > 0:
        s = good.set_index("_ts")["fuel_rate_measured_kgh"]
        s = s[~s.index.duplicated()]
        good["fuel_rate_aligned_kgh"] = s.reindex(good["_ts"] - lag_steps * step).to_numpy()
    else:
        good["fuel_rate_aligned_kgh"] = good["fuel_rate_measured_kgh"]
    good["lag_steps"] = lag_steps
    good["timestamp_local"] = good["_ts"].dt.strftime("%Y-%m-%d %H:%M:%S%z").str.replace(r"(\+\d\d)(\d\d)$", r"\1:\2", regex=True)
    good = good.rename(columns=cfg["rename_reported"]).drop(columns=[c for c in cfg["drop_from_clean"] if c in good] + ["_row", "_ts"])
    report = dict(
        n_raw=len(raw), n_clean=len(good), n_rejected=len(rej),
        reject_counts=primary[bad].value_counts().to_dict(),
        flag_counts=dict(after_gap=int(good["after_gap"].sum()), totalizer_reset=int(good["totalizer_reset"].sum()),
                         unit_suspect=int(good["unit_suspect"].sum()), cmd_feedback_mismatch=int(good["cmd_feedback_mismatch"].sum()),
                         heat_balance_unverified=int((good["heat_balance_status"] == "UNVERIFIED").sum()),
                         volumetric_fuel=int((good["fuel_mass_basis"] == "VOLUMETRIC").sum())),
        gaps=int((good["gap_before_steps"] > 0).sum()), missing_rows=int(good["gap_before_steps"].sum()), lag_steps=lag_steps,
    )
    return good.reset_index(drop=True), rej.reset_index(drop=True), report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw_synthetic/synthetic_heater_c_5min.csv")
    ap.add_argument("--out", default="data/clean/clean_heater_c.csv")
    ap.add_argument("--rejected", default="data/clean/rejected_rows.csv")
    a = ap.parse_args()
    from src.pipeline import stage_clean
    stage_clean(ROOT / a.raw, ROOT / a.out, ROOT / a.rejected)


if __name__ == "__main__":
    main()
