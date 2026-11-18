"""Screen 1 — Live Performance (replay of the filtered period; the cursor never reveals future rows)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard import common as C

WINDOWS = {"2 h": 24, "6 h": 72, "12 h": 144, "24 h": 288}


def step_play(ss, key, n):
    """One timer tick: advance one row, or at the last row ask for Play to stop. Never assigns the toggle key (a widget) from the timer."""
    if ss[key] >= n - 1:
        ss["stop_play"] = True
    else:
        ss["cursor_next"] = ss[key] + 1


def cursor_controls(n, key="cursor_slider"):
    """Slider + step buttons + autoplay. Returns the cursor index. Autoplay advances via a fragment timer."""
    ss = st.session_state
    if key not in ss and "pos" in st.query_params:           # optional deep link: ?pos=<row> starts the replay at that row
        try:
            ss[key] = int(st.query_params["pos"])
        except ValueError:
            pass
    if ss.pop("stop_play", False):                           # set by the timer at the last row; applied here, before the toggle exists
        ss["playing"] = False
    if "cursor_next" in ss:                       # applied before the widget exists (safe to set)
        ss[key] = min(max(int(ss.pop("cursor_next")), 0), n - 1)
    ss[key] = min(int(ss.get(key, n - 1)), n - 1)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 5])
    if c1.button("◀ step", key="b_prev"):
        ss["cursor_next"] = ss[key] - 1
        st.rerun()
    if c2.button("step ▶", key="b_next"):
        ss["cursor_next"] = ss[key] + 1
        st.rerun()
    playing = c3.toggle("▶ Play", key="playing", help="Advance one 5-min row per second")
    c4.slider("Replay position (row in the selected period)", 0, n - 1, key=key)

    @st.fragment(run_every=1.0 if playing else None)
    def tick():
        if playing:
            step_play(ss, key, n)
            st.rerun()
    tick()
    return ss[key]


def metric(col, label, value, unit, status=None, fmt="{:.1f}"):
    with col:
        txt = "—" if value is None or value != value else fmt.format(value) + f" {unit}"
        st.metric(label, txt)
        if status:
            st.markdown(C.badge(status))


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("live")
    df, label, _ = C.filtered()
    if df.empty:
        st.warning("No rows in the selected time range.")
        return
    i = cursor_controls(len(df))
    r = df.iloc[i]
    st.markdown(f"**Replay time:** {r['t']:%Y-%m-%d %H:%M} {C.TZ_LABEL} · mode `{r['operating_mode']}` · lot `{r['fuel_lot']}` · row {i + 1}/{len(df)}")
    m = st.columns(6)
    metric(m[0], "HTF in / out", r["HTF_Tout_C"], "°C out", None)
    m[0].caption(f"in {r['HTF_Tin_C']:.1f} °C · flow {r['HTF_flow_m3h']:.0f} m³/h")
    metric(m[1], "Fuel (time-aligned)", r["fuel_rate_aligned_kgh"], "kg/h", None, "{:.0f}")
    m[1].caption(f"basis {r['fuel_mass_basis']}")
    metric(m[2], "SFC", r["SFC_kg_GJ"], "kg/GJ", r["status_SFC"])
    metric(m[3], "Useful heat", r["Q_out_MW"], "MW", r["status_Q_out"], "{:.2f}")
    if r["status_eta"] == "UNAVAILABLE":
        with m[4]:
            st.metric("Efficiency η", "UNAVAILABLE")
            st.markdown(C.badge("UNAVAILABLE"))
    elif pd.isna(r["eta_pct"]) and pd.notna(r.get("eta_lo_pct")):
        with m[4]:
            st.metric("Efficiency η", f"{r['eta_lo_pct']:.0f}–{r['eta_hi_pct']:.0f} %")
            st.markdown(C.badge(r["status_eta"]))
            st.caption("no point value: this lot has no lab LHV, only an interval")
    else:
        metric(m[4], "Efficiency η", r["eta_pct"], "%", r["status_eta"])
    with m[5]:
        st.metric("Advisory gate", str(r["eligibility"]).split(":")[0])
        st.caption("PROXY = estimated, unverified")

    win = st.select_slider("Trailing window shown", list(WINDOWS), value="6 h")
    w = df.iloc[max(0, i - WINDOWS[win] + 1): i + 1]
    band = C.baseline_band()
    ctr = band.index.to_numpy(float) + 0.5                       # smooth band: interpolate P25/P75 between 1 MW band centres
    q = w["Q_out_MW"].to_numpy(float)
    ok = ~np.isnan(q)
    w = w.assign(p25=np.where(ok, np.interp(np.nan_to_num(q), ctr, band["p25"].to_numpy(float)), np.nan),
                 p75=np.where(ok, np.interp(np.nan_to_num(q), ctr, band["p75"].to_numpy(float)), np.nan))

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=w["t"], y=w["HTF_Tin_C"], name="HTF in °C", row=1, col=1)
    fig.add_scatter(x=w["t"], y=w["HTF_Tout_C"], name="HTF out °C", row=1, col=1)
    fig.add_scatter(x=w["t"], y=w["HTF_flow_m3h"], name="HTF flow m³/h", line=dict(dash="dot"), secondary_y=True)
    C.bands(fig, w["t"], w["HTF_Tin_C"], "HTF_Tin_C", C.COLORWAY[0], label=False)
    C.bands(fig, w["t"], w["HTF_Tout_C"], "HTF_Tout_C", C.COLORWAY[1], label=False)
    C.bands(fig, w["t"], w["HTF_flow_m3h"], "HTF_flow_m3h", C.COLORWAY[2], secondary_y=True, label=False)
    fig.update_yaxes(title_text="°C", secondary_y=False)
    fig.update_yaxes(title_text="m³/h", secondary_y=True)
    C.chart(fig, f"{label}. HTF temperatures and volumetric flow, trailing {win} to the replay cursor, 5-min rows. Measured-in-simulation signals, no uncertainty shown.", "c1",
            title="HTF inlet / outlet temperature and flow")

    fig = go.Figure(go.Scatter(x=w["t"], y=w["fuel_rate_aligned_kgh"], name="fuel kg/h"))
    C.bands(fig, w["t"], w["fuel_rate_aligned_kgh"], "fuel_rate_aligned_kgh")
    fig.update_yaxes(title_text="kg/h")
    C.chart(fig, f"{label}. Fuel mass flow (belt/volumetric basis per row, shifted by the estimated fuel→heat lag), kg/h, trailing {win}.", "c2", title="Fuel feed rate (lag-aligned)")

    fig = go.Figure()
    fig.add_scatter(x=w["t"], y=w["p75"], line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=w["t"], y=w["p25"], line=dict(width=0), fill="tonexty", fillcolor="rgba(0,46,97,.12)", name="baseline P25–P75")
    fig.add_scatter(x=w["t"], y=w["SFC_kg_GJ"], name="SFC kg/GJ", line=dict(color="#009933"))
    C.bands(fig, w["t"], w["SFC_kg_GJ"].where(w["status_SFC"] == "CALCULATED"), "SFC_kg_GJ", "#009933")
    fig.update_yaxes(title_text="kg/GJ")
    C.chart(fig, f"{label}. SFC = fuel mass (kg) ÷ useful HTF heat (GJ), per 5-min row; PROXY/UNAVAILABLE rows left blank or flagged on the tile. "
                 "Band = P25–P75 of training-split eligible CALCULATED SFC in the same 1 MW load band (OWN-ESTIMATE), a reference, not a target.", "c3",
            title="Specific fuel consumption vs. baseline band")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=w["t"], y=w["Q_out_MW"], name="useful MW")
    eta = w["eta_pct"].where(w["status_eta"] != "UNAVAILABLE")
    fig.add_scatter(x=w["t"], y=eta, name="η % (only where computable)", line=dict(dash="dot"), secondary_y=True)
    C.bands(fig, w["t"], w["Q_out_MW"], "Q_out_MW", C.COLORWAY[0], label=False)
    C.bands(fig, w["t"], eta, "eta_pct", C.COLORWAY[1], secondary_y=True, label=False)
    fig.update_yaxes(title_text="MW", secondary_y=False)
    fig.update_yaxes(title_text="η %", secondary_y=True)
    C.chart(fig, f"{label}. Useful heat = m_HTF·cp(T)·ΔT (HTF property table, no water cp), MW; η = useful heat ÷ fuel LHV heat (PROXY when LHV is estimated). "
                 "Gaps = not computable.", "c4", title="Useful heat output and efficiency")

    with st.expander("Operating window and SPC control limits (table)", expanded=False):
        C.window_table(w, ["HTF_Tin_C", "HTF_Tout_C", "HTF_flow_m3h", "fuel_rate_aligned_kgh", "SFC_kg_GJ", "Q_out_MW", "eta_pct"], f"{label}, trailing {win}")
