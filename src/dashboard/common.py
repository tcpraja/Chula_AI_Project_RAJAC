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
    st.markdown(f"<div class='hc-banner'>{BANNER}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hc-sub'>{SUB_BANNER} Times shown in {TZ_LABEL}.</div>", unsafe_allow_html=True)


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


CSS = """
<style>
.block-container{padding-top:4.2rem;max-width:1400px}
html, body, [class*="css"]{font-family:'Inter','Segoe UI',system-ui,-apple-system,sans-serif}
[data-testid="stSidebar"]{background:#0b0f14;border-right:1px solid #1f2733}
[data-testid="stSidebar"] h2{font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:#8b98a5;margin-top:.8rem}
.stAppDeployButton{display:none}
h1,h2,h3{letter-spacing:-.01em}
h2,h3{font-weight:650}
[data-testid="stMetric"]{background:#141a22;border:1px solid #232c38;border-radius:12px;padding:14px 16px}
[data-testid="stMetricLabel"]{color:#8b98a5}
[data-testid="stMetricValue"]{font-size:1.55rem;font-weight:650}
[data-testid="stMetricValue"]>div{overflow:visible;text-overflow:clip;white-space:normal}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px;border-color:#232c38}
[data-testid="stCaptionContainer"]{color:#8b98a5}
/* top page tabs as buttons */
[data-testid="stTopNavLinkContainer"]{gap:.3rem}
a[data-testid="stTopNavLink"]{background:#141a22;border:1px solid #2a3442;border-radius:9px;padding:.3rem .6rem;font-size:.82rem;color:#c9d3dd;font-weight:600;transition:all .15s;white-space:nowrap}
a[data-testid="stTopNavLink"]:hover{border-color:#ff9f1c;color:#fff;background:#1b2330}
a[data-testid="stTopNavLink"][aria-current="page"]{background:#ff9f1c;border-color:#ff9f1c;color:#10141a}
a[data-testid="stTopNavLink"][aria-current="page"] *{color:#10141a}
.hc-banner{background:linear-gradient(90deg,#8e0019,#c1122f);color:#fff;padding:10px 16px;border-radius:10px;font-weight:700;text-align:center;
  letter-spacing:.08em;font-size:.95rem;box-shadow:0 2px 10px rgba(193,18,47,.35)}
.hc-sub{color:#8b98a5;font-size:.8rem;margin:.35rem 0 .2rem}
.hc-head{margin:.6rem 0 1rem;padding-bottom:.6rem;border-bottom:1px solid #232c38}
.hc-kicker{color:#ff9f1c;font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase}
.hc-title{font-size:2rem;font-weight:750;line-height:1.15;margin:.1rem 0}
.hc-lead{color:#aab6c2;font-size:.95rem}
.hc-noadv{background:#3a0a14;border:2px solid #ff4d6d;border-radius:14px;padding:26px;text-align:center}
.hc-noadv b{display:block;font-size:2.9rem;color:#ff4d6d;letter-spacing:.06em}
.hc-noadv span{color:#ffd6dd}
</style>
"""

PAGE_INFO = {"live": ("1 of 6", "Live Performance", "Replay of the held-out period, row by row. The cursor never shows future rows."),
             "combustion": ("2 of 6", "Combustion Diagnostics", "Fuel quality, flue gas, commands (not airflow), temperatures, draft, faults."),
             "recs": ("3 of 6", "AI Recommendations", "A simulated option with interval and checklist. NO ADVICE is the fail-safe state."),
             "whatif": ("4 of 6", "What-if Simulator", "Try a bounded FD / grate move. Out-of-bounds input gives an error and no result."),
             "decisions": ("5 of 6", "Operator Decisions", "Role IDs only (OP-A / OP-B). Logs opinions; changes nothing in the plant."),
             "value": ("6 of 6", "Business Value", "Simulated effect and assumption-driven sensitivities. No verified savings.")}


def page_header(key):
    kicker, title, lead = PAGE_INFO[key]
    st.markdown(f"<div class='hc-head'><div class='hc-kicker'>Heater C · synthetic · {kicker}</div><div class='hc-title'>{title}</div>"
                f"<div class='hc-lead'>{lead}</div></div>", unsafe_allow_html=True)


def no_advice_box(text, prefix=""):
    st.markdown(f"<div class='hc-noadv'><b>NO ADVICE</b><span>{prefix}{text}</span></div>", unsafe_allow_html=True)


def setup():
    st.set_page_config(page_title="Heater C advisory (synthetic)", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    banner()
    sidebar()


def badge(status):
    s = STATUS_MAP.get(str(status), "UNAVAILABLE")
    return f":{STATUS_COLOR[s]}-badge[{s}]"


def provenance(text):
    st.caption("Provenance: SYNTHETIC · " + text)


COLORWAY = ["#4c9be8", "#ff9f1c", "#3fb27f", "#e5484d", "#a78bfa", "#2dd4bf"]


def chart(fig, prov, key=None, height=300):
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=28, b=8), colorway=COLORWAY, hovermode="x unified",
                      legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#c9d3dd"))
    fig.update_xaxes(gridcolor="#1c2430", zeroline=False, showline=False)
    fig.update_yaxes(gridcolor="#1c2430", zeroline=False, showline=False)
    with st.container(border=True):
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
