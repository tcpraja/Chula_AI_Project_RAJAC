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
    "MODEL_DRIFT": "Monitor: inputs have drifted from the training data", "DATA_FAILURE": "Monitor: critical data invalid for too many days",
    "MAE_WORSE_THAN_SIMPLE": "Monitor: the model is worse than the simple regression", "FALSE_ALERTS": "Monitor: too many false alerts per shift",
    "SHADOW_MODE": "Shadow mode: advice is recorded but not shown to operators",
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
        st.markdown("<div class='hc-side-title'>Heater C advisory</div><div class='hc-side-sub'>Synthetic decision support · PET Resin Plant P</div><div class='hc-side-bar'></div>", unsafe_allow_html=True)
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
.stApp{background:#f7f9fc}
[data-testid="stHeader"]{background:rgba(255,255,255,.92);border-bottom:3px solid #002E61}
.block-container{padding-top:4.2rem;max-width:1400px}
html, body, [class*="css"]{font-family:Arial,Calibri,'Segoe UI',sans-serif}
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #d9dfe7;box-shadow:2px 0 10px rgba(0,46,97,.05)}
[data-testid="stSidebar"] *{color:#333333 !important}
[data-testid="stSidebar"] h2{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;color:#009933 !important;margin-top:.8rem}
[data-testid="stSidebar"] [data-baseweb="input"],[data-testid="stSidebar"] [data-baseweb="input"]>div,[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#fff;border-color:#CCCCCC}
[data-testid="stSidebar"] [data-baseweb="input"] *,[data-testid="stSidebar"] [data-baseweb="select"] *{color:#002E61 !important}
.stAppDeployButton{display:none}
[data-testid="stSidebar"] [data-testid="stDateInput"] *,[data-testid="stSidebar"] input{color:#002E61 !important;-webkit-text-fill-color:#002E61 !important}
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-baseweb="input"]{background:#f7f9fc}
[data-testid="stSidebar"] [data-testid="stDateInput"] label *{color:#333333 !important;-webkit-text-fill-color:#333333 !important}
h1,h2,h3{letter-spacing:-.01em;color:#002E61;font-family:'Century Gothic','Antonio',Arial,sans-serif}
h2,h3{font-weight:650}
[data-testid="stMetric"]{background:#fff;border:1px solid #5f7b9e;border-left:4px solid #002E61;border-radius:12px;padding:14px 16px;box-shadow:0 2px 10px rgba(0,46,97,.08)}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"]{border-left-color:#009933}
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"]{border-left-color:#CC0033}
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"]{border-left-color:#666666}
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"]{border-left-color:#002E61}
[data-testid="stColumn"]:nth-child(6) [data-testid="stMetric"]{border-left-color:#009933}
[data-testid="stMetricLabel"]{color:#666666}
[data-testid="stMetricValue"]{font-size:1.4rem;font-weight:700;color:#002E61}
[data-testid="stMetricValue"]>div{overflow:visible;text-overflow:clip;white-space:normal}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:14px;border:1px solid #d5dde9;box-shadow:0 2px 8px rgba(0,46,97,.06);padding:.35rem}
[data-testid="stMain"] [data-testid="stCaptionContainer"]{color:#555;border-left:3px solid #009933;padding-left:.6rem}
[data-testid="stColumn"] [data-testid="stCaptionContainer"]{border-left:none;padding-left:0}
/* top page tabs as pill buttons */
[data-testid="stTopNavLinkContainer"]{gap:.25rem}
a[data-testid="stTopNavLink"]{width:130px;justify-content:center;overflow:visible;background:#fff;border:1px solid #d3d9e2;border-radius:999px;padding:.32rem .4rem;font-size:.77rem;color:#002E61;font-weight:600;
  transition:all .15s;white-space:nowrap;box-shadow:0 1px 2px rgba(0,46,97,.06)}
a[data-testid="stTopNavLink"]:hover{border-color:#009933;color:#006b24;background:#f1f9f4;transform:translateY(-1px);box-shadow:0 3px 8px rgba(0,153,51,.18)}
a[data-testid="stTopNavLink"][aria-current="page"]{background:#002E61;border-color:#002E61;color:#fff;box-shadow:0 3px 0 #009933,0 4px 10px rgba(0,46,97,.25)}
a[data-testid="stTopNavLink"][aria-current="page"] *{color:#fff}
[data-testid="stSidebar"] .hc-side-title{color:#002E61 !important;font-size:1.05rem;font-weight:800;letter-spacing:.02em;line-height:1.2;font-family:'Century Gothic','Antonio',Arial,sans-serif}
[data-testid="stSidebar"] .hc-side-sub{color:#666666 !important;font-size:.72rem;margin-bottom:.4rem}
[data-testid="stSidebar"] .hc-side-bar{height:3px;width:46px;background:#009933;border-radius:2px;margin:.4rem 0 .8rem}
.hc-foot{margin:2rem 0 .5rem;padding-top:.6rem;border-top:1px solid #d3d9e2;color:#666;font-size:.74rem;text-align:center}
[data-testid="stDataFrame"]{border-radius:10px;overflow:hidden;border:1px solid #5f7b9e;background:#fff}
[data-testid="stRadio"] label p,[data-testid="stCheckbox"] label p{font-size:.9rem}
[data-testid="stAlert"]{border-radius:10px;border:1px solid #5f7b9e;border-left:4px solid #002E61;background-clip:padding-box}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{border:1px solid #8fa3bf !important;border-radius:9px}
[data-testid="stSidebar"] [data-baseweb="input"],[data-testid="stSidebar"] [data-baseweb="select"]>div{border-color:#cfd8e6 !important;background:#f7f9fc}
.hc-note{margin:.4rem .1rem .2rem;padding:.55rem .8rem;border:1px dashed #8fa3bf;border-left:3px solid #009933;border-radius:9px;background:#f6f9fc;color:#444;font-size:.78rem;line-height:1.45}
.hc-note b{color:#002E61}
.stButton>button,.stDownloadButton>button{border-radius:9px;border:1px solid #002E61;color:#002E61;font-weight:600;background:#fff}
.stButton>button:hover,.stDownloadButton>button:hover{background:#002E61;color:#fff;border-color:#002E61}
.hc-logo{position:fixed;top:9px;right:64px;z-index:1000001;display:flex;align-items:center;gap:8px;height:34px;padding:0 12px;
  background:#fff;border:1px solid #CCCCCC;border-radius:9px;color:#002E61;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.hc-logo img{height:24px}
.hc-banner{background:#CC0033;color:#fff;padding:10px 16px;border-radius:10px;font-weight:700;text-align:center;
  letter-spacing:.08em;font-size:.95rem;box-shadow:0 3px 12px rgba(204,0,51,.30)}
.hc-sub{color:#666666;font-size:.8rem;margin:.35rem 0 .2rem}
.hc-head{margin:.6rem 0 1rem;padding:14px 18px;border-radius:14px;background:#fff;border:1px solid #5f7b9e;border-left:4px solid #009933;box-shadow:0 3px 12px rgba(0,46,97,.10)}
.hc-kicker{color:#009933;font-size:.75rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase}
.hc-title{font-size:2rem;font-weight:800;line-height:1.15;margin:.1rem 0;color:#002E61;font-family:'Century Gothic','Antonio',Arial,sans-serif}
.hc-lead{color:#666666;font-size:.95rem}
.hc-noadv{background:#fde8ed;border:1px solid #CC0033;border-radius:14px;padding:26px;text-align:center}
.hc-noadv b{display:block;font-size:2.9rem;color:#CC0033;letter-spacing:.06em}
.hc-noadv span{color:#7a1a2b}
</style>
"""

PAGE_INFO = {"live": ("1 of 7", "Live Performance", "Replay of the held-out period, row by row. The cursor never shows future rows."),
             "combustion": ("2 of 7", "Combustion Diagnostics", "Fuel quality, flue gas, commands (not airflow), temperatures, draft, faults."),
             "recs": ("3 of 7", "AI Recommendations", "A simulated option with interval and checklist. NO ADVICE is the fail-safe state."),
             "whatif": ("4 of 7", "What-if Simulator", "Try a bounded FD / grate move. Out-of-bounds input gives an error and no result."),
             "decisions": ("5 of 7", "Operator Decisions", "Role IDs only (OP-A / OP-B). Logs opinions; changes nothing in the plant."),
             "optimize": ("7 of 7", "Optimize", "Efficiency from the heat and mass balance: best reachable efficiency inside the limits, and what to raise or reduce."),
             "value": ("6 of 7", "Business Value", "Simulated effect and assumption-driven sensitivities. No verified savings.")}


def footer():
    st.markdown("<div class='hc-foot'>SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION · humans decide; BMS / SIS / DCS remain the only control authorities · "
                "every number carries its provenance</div>", unsafe_allow_html=True)


def page_header(key):
    kicker, title, lead = PAGE_INFO[key]
    st.markdown(f"<div class='hc-head'><div class='hc-kicker'>Heater C · synthetic · {kicker}</div><div class='hc-title'>{title}</div>"
                f"<div class='hc-lead'>{lead}</div></div>", unsafe_allow_html=True)


def no_advice_box(text, prefix=""):
    st.markdown(f"<div class='hc-noadv'><b>NO ADVICE</b><span>{prefix}{text}</span></div>", unsafe_allow_html=True)


LOGO = ROOT / "assets" / "brand" / "logo.png"      # optional; CLAUDE.md rule 1 keeps public outputs anonymized unless the owner changes it


def logo_html():
    if LOGO.exists():
        import base64
        return f"<div class='hc-logo'><img alt='logo' src='data:image/png;base64,{base64.b64encode(LOGO.read_bytes()).decode()}'></div>"
    return "<div class='hc-logo'>Plant P</div>"


def setup():
    st.set_page_config(page_title="Heater C advisory (synthetic)", layout="wide")
    st.markdown(CSS + logo_html(), unsafe_allow_html=True)
    banner()
    sidebar()


def badge(status):
    s = STATUS_MAP.get(str(status), "UNAVAILABLE")
    return f":{STATUS_COLOR[s]}-badge[{s}]"


def provenance(text):
    st.markdown(f"<div class='hc-note'><b>Provenance:</b> SYNTHETIC · {text}</div>", unsafe_allow_html=True)


COLORWAY = ["#002E61", "#009933", "#CC0033", "#4d7aa8", "#66b87a", "#e07a90"]


# ---------------------------------------------------------------- operating window + SPC bands
# Operating window = synthetic guardrail envelope (config/guardrail_limits.yaml, ASSUMED / NOT APPROVED; CLAUDE rule 4).
# value: limit key holding [lo, hi], or (lo_key, hi_key) for one-sided limits; scale converts fractions to %.
WINDOWS = {"O2_pct_dry": (("o2_floor_pct", None), 1.0), "CO_ppm": ((None, "co_limit_ppm"), 1.0),
           "furnace_temp_C": ((None, "furnace_temp_limit_c"), 1.0), "HTF_Tout_C": ((None, "htf_out_limit_c"), 1.0),
           "draft_pa": ("draft_band_pa", 1.0), "HTF_flow_m3h": ("flow_valid_m3h", 1.0), "eta_pct": ("eta_valid", 100.0),
           "FD_command_pct": ("fd_range_pct", 1.0), "grate_command_pct": ("grate_range_pct", 1.0)}
SPC_LABELS = {"HTF_Tin_C": "HTF inlet temp, °C", "HTF_Tout_C": "HTF outlet temp, °C", "HTF_flow_m3h": "HTF flow, m³/h",
              "fuel_rate_aligned_kgh": "Fuel rate, kg/h", "SFC_kg_GJ": "SFC, kg/GJ", "Q_out_MW": "Useful heat, MW", "eta_pct": "Efficiency η, %",
              "fuel_moisture_wb_pct": "Fuel moisture, % wb", "LHV_used_MJkg": "LHV used, MJ/kg", "O2_pct_dry": "Flue O2, % dry",
              "CO_ppm": "CO, ppm", "FD_command_pct": "FD command, %", "ID_command_pct": "ID command, %", "grate_command_pct": "Grate command, %",
              "furnace_temp_C": "Furnace temp, °C", "flue_temp_C": "Flue temp, °C", "stack_temp_C": "Stack temp, °C", "draft_pa": "Furnace draft, Pa",
              "unburnt_in_ash_pct": "Unburnt in ash, %", "economizer_dP_pa": "Economizer dP, Pa"}
SPC_NOTE = ("Bands: shaded = SPC control band, CL ± 3σ (OWN-ESTIMATE: mean and overall SD of the reference rows; overall SD, not moving range, "
            "because 5-min data are autocorrelated); red lines = operating window ({prov}). ● orange = beyond ±3σ, ✕ red = outside the window.")


@st.cache_data(show_spinner=False)
def _lhv_envelope():
    import yaml
    return yaml.safe_load((ROOT / "config" / "cleaning_engineering.yaml").read_text(encoding="utf-8"))["lhv_band"]["envelope_mjkg"]


def window(col):
    """(lo, hi, status) of the operating window for a column; status '' when none is defined."""
    if col == "LHV_used_MJkg":
        lo, hi = _lhv_envelope()
        return float(lo), float(hi), "ASSUMED (LHV plausibility envelope)"
    if col not in WINDOWS:
        return None, None, ""
    spec, scale = WINDOWS[col]
    L = limits()["limits"]
    raw = L.get(spec) if isinstance(spec, str) else [L.get(spec[0]) if spec[0] else None, L.get(spec[1]) if spec[1] else None]
    if raw is None or isinstance(raw, str) or any(isinstance(v, str) for v in raw):
        return None, None, gd.PLACEHOLDER
    num = [float(v) * scale if v is not None else None for v in raw]
    return num[0], num[1], "ASSUMED"


def _valid(df, col):
    s = pd.to_numeric(df[col], errors="coerce")
    if col == "CO_ppm" and "co_available" in df.columns:
        s = s.where(df["co_available"] == 1)
    if col == "eta_pct" and "status_eta" in df.columns:
        s = s.where(df["status_eta"] != "UNAVAILABLE")
    if col == "SFC_kg_GJ" and "status_SFC" in df.columns:
        s = s.where(df["status_SFC"] == "CALCULATED")
    if col == "fuel_moisture_wb_pct" and "fuel_lot" in df.columns:   # one lab value per lot, not one per 5-min row
        return s.groupby(df["fuel_lot"]).first().dropna()
    return s.dropna()


def _ref_stats(df):
    """Reference period for the control limits: training split (else the first 30 % of the file), steady ELIGIBLE rows when ≥ 30."""
    if "split" in df.columns and (df["split"] == "train").any():
        r, src = df[df["split"] == "train"], "training split"
    else:
        r, src = df.iloc[: max(10, int(len(df) * 0.3))], "first 30 % of the file"
    if "eligibility" in r.columns:
        e = r[r["eligibility"].astype(str).str.startswith("ELIGIBLE")]
        if len(e) >= 30:
            r, src = e, src + ", steady ELIGIBLE rows"
    out = {}
    for col in SPC_LABELS:
        if col in r.columns:
            s = _valid(r, col)
            if len(s) >= 10 and s.std() > 0:
                m, sd = float(s.mean()), float(s.std())
                lcl = m - 3 * sd if col == "draft_pa" else max(0.0, m - 3 * sd)   # physical floor: only draft can be negative
                out[col] = {"cl": m, "sigma": sd, "lcl": lcl, "ucl": m + 3 * sd, "n": int(len(s)), "src": src}
    return out


@st.cache_data(show_spinner=False)
def _default_stats():
    return _ref_stats(load_default())


def spc_stats():
    df, _, is_def = active_frame()
    return _default_stats() if is_def else _ref_stats(df)


def _rgba(hex_color, a):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def bands(fig, t, y, col, color="#002E61", secondary_y=False, label=True):
    """Draw the SPC control band (CL ± 3σ) and the operating window for one series, and mark the points outside either."""
    kw = {"secondary_y": True} if secondary_y else {}
    s = spc_stats().get(col)
    lo, hi, _ = window(col)
    y = pd.to_numeric(pd.Series(y).reset_index(drop=True), errors="coerce")
    t = pd.Series(t).reset_index(drop=True)
    font = dict(size=9, color=color)
    if s:
        fig.add_hrect(y0=s["lcl"], y1=s["ucl"], fillcolor=_rgba(color, .07), line_width=0, layer="below", **kw)
        fig.add_hline(y=s["cl"], line=dict(color=color, width=1, dash="dot"), **kw,
                      **({"annotation_text": f"CL {s['cl']:,.3g}", "annotation_position": "top left", "annotation_font": font} if label else {}))
        for v, nm in ((s["ucl"], "UCL"), (s["lcl"], "LCL")):
            fig.add_hline(y=v, line=dict(color=_rgba(color, .55), width=1, dash="dash"), **kw,
                          **({"annotation_text": f"{nm} {v:,.3g}", "annotation_position": "top left" if nm == "UCL" else "bottom left",
                              "annotation_font": font} if label else {}))
        ooc = (y > s["ucl"]) | (y < s["lcl"])
    else:
        ooc = pd.Series(False, index=y.index)
    red = "#CC0033"
    out = pd.Series(False, index=y.index)
    for v, nm in ((lo, "window min"), (hi, "window max")):
        if v is not None:
            fig.add_hline(y=v, line=dict(color=red, width=1.6), annotation_text=f"{nm} {v:,.4g}", annotation_position="top right" if nm == "window max" else "bottom right",
                          annotation_font=dict(size=9, color=red), **kw)
            out |= (y > v) if nm == "window max" else (y < v)
    name = SPC_LABELS.get(col, col)
    ooc &= ~out
    if ooc.any():
        fig.add_scatter(x=t[ooc], y=y[ooc], mode="markers", marker=dict(size=6, color="#f28e2b", line=dict(width=0.5, color="#fff")),
                        name=f"{name}: beyond ±3σ", legendgroup="ooc", **kw)
    if out.any():
        fig.add_scatter(x=t[out], y=y[out], mode="markers", marker=dict(size=7, color=red, symbol="x"), name=f"{name}: outside window", legendgroup="out", **kw)
    fig.update_layout(meta={"spc": True})


def window_table(df, cols, prov_label):
    """Operating window + SPC limits + in-view behaviour per signal (one row each)."""
    stats, rows = spc_stats(), []
    for col in cols:
        if col not in df.columns:
            continue
        s, (lo, hi, status), v = stats.get(col), window(col), _valid(df, col)
        win = "none defined (SPC only)" if not status else (status if status == gd.PLACEHOLDER else
              (f"{lo:,.4g} – {hi:,.4g}" if lo is not None and hi is not None else (f"≥ {lo:,.4g}" if lo is not None else f"≤ {hi:,.4g}")))
        out_w = ((v < lo) if lo is not None else False) | ((v > hi) if hi is not None else False)
        cpk = None
        if len(v) > 1 and v.std() > 0 and (lo is not None or hi is not None):
            m, sd = v.mean(), v.std()
            cpk = min(([(m - lo) / (3 * sd)] if lo is not None else []) + ([(hi - m) / (3 * sd)] if hi is not None else []))
        rows.append({"Signal": SPC_LABELS.get(col, col), "Operating window": win,
                     "CL": round(s["cl"], 3) if s else None, "LCL (−3σ)": round(s["lcl"], 3) if s else None,
                     "UCL (+3σ)": round(s["ucl"], 3) if s else None, "σ": round(s["sigma"], 3) if s else None,
                     "Reference n": s["n"] if s else None, "Points in view": int(len(v)),
                     "% outside window": round(100 * float(np.mean(out_w)), 2) if status and status != gd.PLACEHOLDER and len(v) else None,
                     "% beyond ±3σ": round(100 * float(((v > s["ucl"]) | (v < s["lcl"])).mean()), 2) if s and len(v) else None,
                     "Cpk vs window": round(float(cpk), 2) if cpk is not None and np.isfinite(cpk) else None})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    src = next(iter(stats.values()))["src"] if stats else "n/a"
    provenance(f"{prov_label}. Window = {limits().get('provenance', 'SYNTHETIC_ASSUMED_NOT_APPROVED')} guardrail envelope (LHV: cleaning-config plausibility envelope). "
               f"CL / LCL / UCL = mean and mean ± 3 × overall SD of the reference rows ({src}); OWN-ESTIMATE. % columns and Cpk = rows in the current time filter "
               "(numerator = rows outside, denominator = valid rows in view; CO only where measured, moisture one value per fuel lot). "
               "Cpk = distance from the in-view mean to the nearest window limit ÷ 3σ (in-view σ); < 1.33 means the process is tight against the window. Synthetic data: not a plant capability.")


def chart(fig, prov, key=None, height=300, title=None):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=8, r=8, t=28, b=8), colorway=COLORWAY, hovermode="x unified",
                      legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)), paper_bgcolor="#ffffff", plot_bgcolor="#fafbfd",
                      font=dict(family="Arial, Calibri, sans-serif", size=12, color="#333333"))
    if title:
        # title in the top margin; legend moves just above the plot area so the two never overlap
        fig.update_layout(title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", xref="paper", y=1, yref="container", yanchor="top",
                                     pad=dict(t=8), font=dict(size=14, color="#002E61")),
                          margin=dict(t=72), legend=dict(y=1.02, yanchor="bottom"))
    fig.update_xaxes(gridcolor="#e6e9ee", zeroline=False, showline=True, mirror=True, linecolor="#dfe5ee", linewidth=1)
    fig.update_yaxes(gridcolor="#e6e9ee", zeroline=False, showline=True, mirror=True, linecolor="#dfe5ee", linewidth=1)
    if isinstance(fig.layout.meta, dict) and fig.layout.meta.get("spc"):
        prov = f"{prov} {SPC_NOTE.format(prov=limits().get('provenance', 'SYNTHETIC_ASSUMED_NOT_APPROVED'))}"
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch", key=key)
        provenance(prov)


def thin(df, n=3000):
    """Stride-downsample for plotting (display only)."""
    return df.iloc[:: max(1, len(df) // n)] if len(df) > n else df


def gate_state(ts):
    """Advisory record for a timestamp, or a fail-safe NO_ADVICE stub when none exists. A monitor NO_ADVICE mode or SHADOW mode overrides it on site."""
    from src import monitor, site_config
    forced = monitor.enforced_codes()
    site = site_config.from_env()
    if site is not None and site.mode == "SHADOW":
        forced = forced + ["SHADOW_MODE"]
    if forced:
        return {"timestamp": ts, "eligible": False, "decision": "NO_ADVICE", "reason_codes": forced, "proposed_simulated_settings": None,
                "human_review_required": True, "model_version": "n/a", "advice_class": "NONE", "action": "NONE"}
    r = load_advisory().get(ts)
    if r is not None:
        return r
    return {"timestamp": ts, "eligible": False, "decision": "NO_ADVICE", "reason_codes": ["NO_RECORD"], "proposed_simulated_settings": None,
            "human_review_required": True, "model_version": "n/a", "advice_class": "NONE", "action": "NONE"}
