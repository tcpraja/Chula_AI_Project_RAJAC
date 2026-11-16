"""Screen 2 — Combustion Diagnostics."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard import common as C


def _lot_lines(fig, df):
    ch = df.index[df["fuel_lot"] != df["fuel_lot"].shift()][1:]
    for k in ch[:60]:
        fig.add_vline(x=df.at[k, "t"], line=dict(color="#888", dash="dot", width=1))
    return len(ch)


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("combustion")
    df, label, _ = C.filtered()
    if df.empty:
        st.warning("No rows in the selected time range.")
        return
    n_all = len(df)
    p = C.thin(df).reset_index(drop=True)
    st.caption(f"{n_all:,} rows in range; plots stride-downsampled to {len(p):,} points (display only). {label}")

    # fuel quality
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        mm = p.dropna(subset=["fuel_moisture_wb_pct"])
        fig.add_scatter(x=mm["t"], y=mm["fuel_moisture_wb_pct"], mode="lines+markers", marker=dict(size=3), name="moisture % wb")
        n_lot = _lot_lines(fig, p)
        fig.update_yaxes(title_text="% wet basis")
        C.chart(fig, f"{label}. Fuel moisture, % wet basis, lab sample per lot (gaps = no sample; not imputed). Dotted lines = fuel-lot changes ({n_lot} in view).", "m")
    with c2:
        lhv = p.dropna(subset=["LHV_used_MJkg"])
        fig = go.Figure(go.Scatter(x=lhv["t"], y=lhv["LHV_used_MJkg"], name="LHV used MJ/kg"))
        _lot_lines(fig, p)
        fig.update_yaxes(title_text="MJ/kg as-fired")
        C.chart(fig, f"{label}. As-fired LHV used in the heat balance, MJ/kg. Basis per row below; only LAB_LOT is a lab value, the others are bands/estimates (PROXY).", "lhv")
        vc = df["LHV_basis"].value_counts()
        st.markdown("**LHV status** " + " · ".join(f"{C.badge('CALCULATED' if k == 'LAB_LOT' else 'PROXY')} {k} {v / n_all:.0%}" for k, v in vc.items()))

    # O2 / CO
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Scatter(x=p["t"], y=p["O2_pct_dry"], name="O2 % dry"))
        fig.add_hline(y=C.limits()["limits"]["o2_floor_pct"], line=dict(color="#d1495b", dash="dash"), annotation_text="synthetic floor (ASSUMED)")
        fig.update_yaxes(title_text="% dry")
        C.chart(fig, f"{label}. Flue-gas O2, % dry. Floor is a synthetic normalized envelope (ASSUMED / NOT APPROVED).", "o2")
    with c2:
        if (df["co_available"] == 0).all():
            st.error("CO sensor not available in this data")
        else:
            co = p.assign(CO=p["CO_ppm"].where(p["co_available"] == 1))
            fig = go.Figure(go.Scatter(x=co["t"], y=co["CO"], name="CO ppm"))
            fig.add_hline(y=C.limits()["limits"]["co_limit_ppm"], line=dict(color="#d1495b", dash="dash"), annotation_text="synthetic limit (ASSUMED)")
            cap = 1000.0
            n_clip = int((co["CO"] > cap).sum())
            fig.update_yaxes(title_text="ppm", range=[0, cap])
            C.chart(fig, f"{label}. CO, ppm; blank where the sensor is not available. Limit is a synthetic envelope. Axis clipped at {cap:,.0f} ppm so the limit stays readable: "
                         f"{n_clip} plotted point(s) above it are off-scale (not removed from the data).", "co")
            share = (df["co_available"] == 0).mean()
            if share:
                st.warning(f"CO sensor not available for {share:.0%} of rows in range — those rows can only be DIAGNOSTIC ONLY (no advice).")

    # commands
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_scatter(x=p["t"], y=p["FD_command_pct"], name="FD command %")
        fig.add_scatter(x=p["t"], y=p["ID_command_pct"], name="ID command %")
        fig.update_yaxes(title_text="% of command range")
        C.chart(fig, f"{label}. Fan COMMANDS, % — command, not airflow (no airflow measurement exists). Efficiency ≠ fan command.", "fans")
        st.caption("⚠ FD / ID values are **command, not airflow**.")
    with c2:
        fig = go.Figure(go.Scatter(x=p["t"], y=p["grate_command_pct"], name="grate command %"))
        fig.update_yaxes(title_text="% of command range")
        C.chart(fig, f"{label}. Grate speed COMMAND, % (command, not measured grate position).", "grate")

    # temps, draft
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for col, nm in (("furnace_temp_C", "furnace °C"), ("flue_temp_C", "flue °C"), ("stack_temp_C", "stack °C")):
            fig.add_scatter(x=p["t"], y=p[col], name=nm)
        C.chart(fig, f"{label}. Furnace, flue and stack temperatures, °C, 5-min rows. Synthetic envelope: furnace ≤ {C.limits()['limits']['furnace_temp_limit_c']:g} °C (ASSUMED).", "temps")
    with c2:
        lim = C.limits()["limits"]["draft_band_pa"]
        fig = go.Figure(go.Scatter(x=p["t"], y=p["draft_pa"], name="draft Pa"))
        fig.add_hrect(y0=lim[0], y1=lim[1], fillcolor="rgba(60,160,90,.15)", line_width=0, annotation_text="synthetic band")
        fig.update_yaxes(title_text="Pa (negative = normal)")
        C.chart(fig, f"{label}. Furnace draft, Pa. Shaded = synthetic draft band (ASSUMED / NOT APPROVED).", "draft")

    # ash / economizer
    c1, c2 = st.columns(2)
    with c1:
        u = df.dropna(subset=["unburnt_in_ash_pct"])
        fig = go.Figure(go.Scatter(x=u["t"], y=u["unburnt_in_ash_pct"], mode="markers", name="unburnt in ash %"))
        fig.update_yaxes(title_text="% unburnt in ash")
        C.chart(fig, f"{label}. Unburnt carbon in ash, %, lab samples only ({len(u)} in range); not interpolated.", "ash")
    with c2:
        fig = go.Figure(go.Scatter(x=p["t"], y=p["economizer_dP_pa"], name="economizer dP Pa"))
        fig.update_yaxes(title_text="Pa")
        C.chart(fig, f"{label}. Economizer differential pressure, Pa; a rising trend would indicate fouling (synthetic).", "dp")

    # faults
    st.subheader("Faults and abnormal conditions")
    f = df.assign(alarm=df["alarm_code"].fillna(""))
    ab = f[(f["alarm"] != "") | (f["interlock_active"] > 0) | (f["fan_derated"] > 0) | (f["sootblow"] > 0)]
    k = st.columns(4)
    k[0].metric("Alarm rows", int((f["alarm"] != "").sum()))
    k[1].metric("Interlock-active rows", int((f["interlock_active"] > 0).sum()))
    k[2].metric("Fan-derate rows", int((f["fan_derated"] > 0).sum()))
    k[3].metric("Sootblow rows", int((f["sootblow"] > 0).sum()))
    if ab.empty:
        st.info("No alarms, interlocks, derates or sootblowing in the selected range.")
    else:
        run = (ab["t"].diff() != pd.Timedelta(minutes=5)).cumsum()
        ev = ab.groupby(run).agg(start=("t", "min"), rows=("t", "size"), mode=("operating_mode", "first"),
                                 alarm=("alarm", lambda s: ",".join(sorted(set(s) - {""}))), interlock=("interlock_active", "max"),
                                 derate=("fan_derated", "max"), sootblow=("sootblow", "max")).reset_index(drop=True)
        ev["start"] = ev["start"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(ev.head(50), width="stretch", hide_index=True)
        C.provenance(f"{label}. Contiguous 5-min runs of alarm / interlock / derate / sootblow flags, first 50 of {len(ev)} events. "
                     "Flags come from the synthetic generator's alarm model, not a plant system.")
