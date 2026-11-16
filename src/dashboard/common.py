"""Shared dashboard pieces: data loading (cached), upload schema check, sidebar, banner, badges, chart + provenance helper.

Everything shown is SYNTHETIC. No network, no plant write path. Uploaded files are schema-checked only, never verified.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src import guardrails as gd

ROOT = Path(__file__).resolve().parents[2]
TZ = "Asia/Bangkok"
TZ_LABEL = "Asia/Bangkok (UTC+07:00)"
BANNER = "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION"
SUB_BANNER = "Decision-support only. Humans decide; BMS / SIS / hardwired trips / DCS remain the only control authorities."
DEFAULT_CSV = ROOT / "data" / "clean" / "clean_heater_c.csv"
DEFAULT_LABEL = "data/clean/clean_heater_c.csv (SYNTHETIC, seed 42)"
UPLOAD_MAX_MB = 50
PAGE_COLS = ["timestamp_local", "fuel_lot", "fuel_moisture_wb_pct", "fuel_LHV_asfired_MJkg", "LHV_used_MJkg", "LHV_basis", "O2_pct_dry",
             "FD_command_pct", "ID_command_pct", "grate_command_pct", "flue_temp_C", "stack_temp_C", "unburnt_in_ash_pct",
             "economizer_dP_pa", "fan_power_kW_FD", "fan_power_kW_ID", "fuel_price_index", "ambient_temp_C", "Q_out_MW", "SFC_kg_GJ",
             "eta_pct", "status_Q_out", "status_SFC", "status_eta", "eligibility", "CO_ppm", "co_available"]
REQUIRED_COLS = sorted(set(gd.REQUIRED) | set(PAGE_COLS))
STATUS_COLOR = {"CALCULATED": "green", "PROXY": "orange", "UNAVAILABLE": "red"}
STATUS_MAP = {"CALCULATED": "CALCULATED", "ESTIMATED": "PROXY", "PROXY": "PROXY", "UNAVAILABLE": "UNAVAILABLE"}
REASON_TEXT = {
    "NO_CO": "No CO measurement available (diagnostic only)", "BAD_FLOW": "HTF flow outside the valid range",
    "LOW_FUEL_CONF": "Fuel flow / LHV not trusted (volumetric, LHV unknown, feeder stop, totalizer reset or gap)",
    "TRIP_ACTIVE": "Trip / interlock alarm active", "FAN_DERATE": "Fan derated", "UNSAFE_DRAFT": "Draft outside the synthetic band",
    "HIGH_TEMP": "Furnace or HTF outlet temperature above the synthetic limit", "STALE_DATA": "A signal is frozen (stale data)",
    "OOD": "Operating point outside the training distribution", "ENERGY_BALANCE": "Heat balance unverified or efficiency out of range",
    "TRANSIENT": "Not in stable steady operation long enough", "WIDE_INTERVAL": "Predicted-effect interval too wide",
    "PROPERTY_OOR": "HTF temperature outside the property table", "LIMITS_NOT_APPROVED": "Limits require OEM approval",
    "LOW_O2": "O2 below the synthetic floor", "HIGH_CO": "CO above the synthetic limit", "CMD_FEEDBACK": "Command and feedback disagree",
    "NO_BENEFIT": "No option with a pessimistic benefit (hold is best)",
    "NO_RECORD": "No advisory record for this row (outside the held-out replay or an uploaded file) — fail-safe"}


# ---------------------------------------------------------------- data
def _prep(df):
    df = df.copy()
    df["t"] = pd.to_datetime(df["timestamp_local"], utc=True).dt.tz_convert(TZ)
    return df.sort_values("t").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_default():
    d = _prep(pd.read_csv(DEFAULT_CSV))
    sp = pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv", usecols=["timestamp_local", "split"])
    return d.merge(sp, on="timestamp_local", how="left")


@st.cache_data(show_spinner=False)
def load_advisory():
    """Advisory records of the held-out test + validation splits, keyed by timestamp_local (str)."""
    rec = {}
    for name in ("test", "val"):
        p = ROOT / "data" / "advisory" / f"advisory_records_{name}.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                rec[r["timestamp"]] = r
    return rec


@st.cache_data(show_spinner=False)
def load_actions():
    a = pd.read_csv(ROOT / "data" / "raw_synthetic" / "operator_action_log.csv")
    a["t"] = pd.to_datetime(a["timestamp"]).dt.tz_localize(TZ)
    return a


@st.cache_data(show_spinner=False)
def baseline_band():
    """SYNTHETIC SFC band per 1 MW load band: P25-P75 of training-split eligible CALCULATED rows (OWN-ESTIMATE)."""
    d = load_default()
    x = d[(d["split"] == "train") & d["eligibility"].str.startswith("ELIGIBLE") & (d["status_SFC"] == "CALCULATED")].copy()
    x["band"] = np.floor(x["Q_out_MW"]).astype(int)
    g = x.groupby("band")["SFC_kg_GJ"]
    t = pd.DataFrame({"n": g.size(), "p25": g.quantile(0.25), "p50": g.median(), "p75": g.quantile(0.75)})
    return t[t["n"] >= 30]


@st.cache_resource(show_spinner=False)
def effect_model():
    import joblib
    return joblib.load(ROOT / "models" / "effect_model.joblib")


@st.cache_data(show_spinner=False)
def limits():
    return gd.load_limits()


def schema_check(df):
    """Return a list of problems (empty = OK). Checks columns, row count, timestamps and numeric dtypes."""
    miss = [c for c in REQUIRED_COLS if c not in df.columns]
    if miss:
        return [f"missing columns: {miss}"]
    errs = []
    if len(df) < 10:
        errs.append("fewer than 10 rows")
    if pd.to_datetime(df["timestamp_local"], utc=True, errors="coerce").isna().any():
        errs.append("timestamp_local has unparseable values")
    for c in ["O2_pct_dry", "FD_command_pct", "grate_command_pct", "Q_out_MW", "HTF_flow_m3h", "HTF_Tin_C", "HTF_Tout_C", "draft_pa"]:
        if pd.to_numeric(df[c], errors="coerce").isna().mean() > 0.5:
            errs.append(f"column {c} is mostly non-numeric")
    return errs


def active_frame():
    """(full frame, label, is_default). Uploaded data is used only after the schema check passes."""
    up = st.session_state.get("upload_ok")
    if st.session_state.get("source_choice") == "Upload CSV" and up is not None:
        return up["df"], f"UPLOADED {up['name']} (schema-checked only, NOT verified)", False
    return load_default(), DEFAULT_LABEL, True


def filtered():
    """Active frame after the sidebar time filter: (copy, label, is_default)."""
    df, label, is_def = active_frame()
    rng = st.session_state.get("time_range")
    if rng and len(rng) == 2:
        lo = pd.Timestamp(rng[0]).tz_localize(TZ)
        hi = pd.Timestamp(rng[1]).tz_localize(TZ) + pd.Timedelta(days=1)
        df = df[(df["t"] >= lo) & (df["t"] < hi)]
    return df.reset_index(drop=True), label, is_def


# ---------------------------------------------------------------- layout
def banner():
    st.markdown(f"<div style='background:#b00020;color:#fff;padding:10px 14px;border-radius:6px;font-weight:700;text-align:center;"
                f"letter-spacing:.5px'>{BANNER}</div>", unsafe_allow_html=True)
    st.caption(SUB_BANNER + f" Times shown in {TZ_LABEL}.")


def sidebar():
    with st.sidebar:
        st.header("Data")
        choice = st.radio("Source", ["Default synthetic file", "Upload CSV"], key="source_choice", label_visibility="collapsed")
        if choice == "Upload CSV":
            f = st.file_uploader("Clean-schema CSV (same columns as the default file)", type="csv", key="upload_file")
            if f is None:
                st.session_state.pop("upload_ok", None)
            elif f.size > UPLOAD_MAX_MB * 1e6:
                st.error(f"File larger than {UPLOAD_MAX_MB} MB — rejected.")
                st.session_state.pop("upload_ok", None)
            else:
                try:
                    df = pd.read_csv(f)
                    errs = schema_check(df)
                except Exception as e:  # unreadable file
                    df, errs = None, [f"could not read CSV: {type(e).__name__}"]
                if errs:
                    st.error("Schema check failed — using the default file instead.\n\n" + "\n".join(f"- {e}" for e in errs))
                    st.session_state.pop("upload_ok", None)
                else:
                    st.session_state["upload_ok"] = {"df": _prep(df), "name": f.name}
                    st.success(f"Schema OK: {len(df):,} rows. Not verified; no advisory records for uploads.")
        df, label, _ = active_frame()
        st.caption(f"Active: {label}")
        lo, hi = df["t"].min().date(), df["t"].max().date()
        default = (lo, hi)
        if "split" in df.columns and (df["split"] == "test").any():
            ts = df.loc[df["split"] == "test", "t"]
            default = (ts.min().date(), ts.max().date())
        st.header("Time filter")
        st.date_input(f"Date range ({TZ_LABEL})", value=default, min_value=lo, max_value=hi, key="time_range")
        st.caption("Default = held-out test split (replay). Widen to see train/validation periods.")
        st.divider()
        st.caption("Badges: CALCULATED = from validated inputs · PROXY = estimated, unverified · UNAVAILABLE = cannot be computed.")


def setup():
    st.set_page_config(page_title="Heater C advisory (synthetic)", layout="wide")
    st.markdown("<style>[data-testid='stMetricValue']{font-size:1.45rem}[data-testid='stMetricValue']>div{overflow:visible;text-overflow:clip;"
                "white-space:normal}</style>", unsafe_allow_html=True)
    banner()
    sidebar()


def badge(status):
    s = STATUS_MAP.get(str(status), "UNAVAILABLE")
    return f":{STATUS_COLOR[s]}-badge[{s}]"


def provenance(text):
    st.caption("Provenance: SYNTHETIC · " + text)


def chart(fig, prov, key=None):
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.15),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", key=key)
    provenance(prov)


def thin(df, n=3000):
    """Stride-downsample for plotting (display only)."""
    return df.iloc[:: max(1, len(df) // n)] if len(df) > n else df


def gate_state(ts):
    """Advisory record for a timestamp, or a fail-safe NO_ADVICE stub when none exists."""
    r = load_advisory().get(ts)
    if r is not None:
        return r
    return {"timestamp": ts, "eligible": False, "decision": "NO_ADVICE", "reason_codes": ["NO_RECORD"], "proposed_simulated_settings": None,
            "human_review_required": True, "model_version": "n/a", "advice_class": "NONE", "action": "NONE"}
