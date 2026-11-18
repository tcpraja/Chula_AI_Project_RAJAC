"""Screen — Optimize: efficiency from the chemical heat and mass balance, the best efficiency inside the safety bounds, and what to raise or reduce.

Simple operations view of the replayed heater. Suggestions for human review only; nothing is sent to any plant system.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import chem_advice, combustion as cb, optimize_view as ov
from src.dashboard import common as C
from src.dashboard.p1_live import cursor_controls

STATUS_STYLE = {"act": "background-color:#fde8ed;color:#CC0033;font-weight:700", "watch": "background-color:#fff6dc;color:#8a6100;font-weight:700",
                "ok": "background-color:#e9f6ee;color:#006b24;font-weight:600"}


@st.cache_data(show_spinner=False)
def stack_ref():
    return ov.stack_reference(C.load_default())


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("optimize")
    df, label, is_def = C.filtered()
    if df.empty:
        st.warning("No rows in the selected time range.")
        return
    if not is_def:
        st.info("The efficiency view needs the default synthetic data and its effect model; it is not computed for uploaded files.")
        return
    i = cursor_controls(len(df))
    row = df.iloc[i]
    gate = C.gate_state(row["timestamp_local"])
    st.markdown(f"**Replay time:** {row['t']:%Y-%m-%d %H:%M} {C.TZ_LABEL} · mode `{row['operating_mode']}` · lot `{row['fuel_lot']}`")
    s = ov.snapshot(row, chem_advice.lot_moisture(df, i), gate, C.effect_model(), C.limits(), stack_ref())
    if s is None:
        miss = ov.missing_inputs(row, chem_advice.lot_moisture(df, i))
        st.warning("No heat and mass balance for this row, and no guess is made. Missing: " + (", ".join(miss) or "inputs") + f". Fuel lot `{row['fuel_lot']}` "
                   + ("has no lab assay yet (LHV and moisture are never invented)." if any("lab" in m for m in miss) else "lacks measurements.")
                   + " Step back to a row from an assayed lot, or widen the replay.")
        return
    now, best = s["now"], s["best"]
    gain = (s["eta_best"] - now["eta_indirect_pct"]) if best else 0.0
    k = st.columns(4)
    k[0].metric("Efficiency now (chemistry)", f"{now['eta_indirect_pct']:.1f} %", f"HTF heat balance {s['eta_heat_balance']:.1f} %", delta_color="off")
    k[1].metric("Best reachable, inside limits", f"{s['eta_best']:.1f} %" if best else "n/a", f"at O2 {s['o2_best']:.1f} % (λ {cb.excess_air_ratio(s['o2_best']):.2f})" if best else None, delta_color="off")
    k[2].metric("Room to improve", f"{gain:+.1f} points", f"≈ {100 * gain / max(now['eta_indirect_pct'], 1e-9):.1f} % less fuel", delta_color="off")
    k[3].metric("Advisory gate", str(gate.get("decision", "NO_ADVICE")).replace("_", " "), ", ".join(gate.get("reason_codes") or []) or "all guardrails passed", delta_color="off")

    if gate.get("decision") == "ADVICE":
        st.success("Gate passed: the suggestions below are consistent with the guarded optimizer. Human review required.")
    else:
        st.warning("Gate is NO ADVICE / diagnostic for this moment: the table is information to understand the heater, not a suggested change. Hold current settings unless your operating procedure says otherwise.")
    st.subheader("What to change now")
    if s["actions"]:
        for a in s["actions"]:
            st.markdown(f"🔧 **{a}**")
        st.caption("Largest lever first is the air line; one bounded FD step at a time (max step from the guardrail config), then re-check CO and draft before the next step.")
    else:
        st.success("Everything is inside its target band: hold current settings.")

    st.subheader("All operating parameters")
    sty = s["params"].style.map(lambda v: STATUS_STYLE.get(v, ""), subset=["Status"])
    st.dataframe(sty, hide_index=True, width="stretch", height=36 * (len(s["params"]) + 1) + 3)
    C.provenance(f"{label}. Parameter targets from the chemistry (best allowed O2), the synthetic guardrail envelope (ASSUMED / NOT APPROVED) and rule-of-thumb thresholds in config/ops_guidance.yaml (ASSUMED). "
                 "Status: act = suggests a change, watch = needs attention, ok = hold.")

    c1, c2 = st.columns(2)
    with c1:
        lv = s["levers"]
        fig = go.Figure(go.Bar(y=lv["Lever"] + "<br><sub>" + lv["Change"] + "</sub>", x=lv["Δη (points)"], orientation="h", marker_color="#009933"))
        fig.update_layout(yaxis=dict(autorange="reversed"), height=300)
        fig.update_xaxes(title_text="efficiency gain, percentage points (each lever alone)")
        C.chart(fig, f"{label}. Lever sensitivities from the loss balance: air to the best allowed O2, stack temperature −{ov.load_ops()['sensitivity_dt_k']:g} K, fuel moisture, CO burn-out, unburnt carbon. "
                     "OWN-ESTIMATE on an ASSUMED fuel analysis; the stack and moisture levers are not real-time controls.", "levers", height=300,
                title="Efficiency gain per lever")
    with c2:
        mw = s["loss_mw"]
        names = ["Fuel heat in", "Dry flue gas", "Water vapour", "CO", "Unburnt carbon", "Radiation / other (ASSUMED)", "Unaccounted (closure)", "Useful heat to HTF"]
        vals = [s["q_in"], -mw["dry_flue_gas"], -mw["water_vapour"], -mw["CO"], -mw["unburnt_carbon"], -mw["radiation_other"], -s["unaccounted_mw"], s["q_out"]]
        fig = go.Figure(go.Waterfall(x=names, y=vals, measure=["absolute"] + ["relative"] * 6 + ["total"], connector=dict(line=dict(color="#999")),
                                     increasing=dict(marker=dict(color="#009933")), decreasing=dict(marker=dict(color="#CC0033")), totals=dict(marker=dict(color="#002E61"))))
        fig.update_layout(height=300)
        fig.update_yaxes(title_text="MW")
        C.chart(fig, f"{label}. Heat balance now: fuel heat = fuel kg/h × LHV ÷ 3600; losses from the chemistry; useful heat = HTF flow × cp × ΔT (property table). "
                     "'Unaccounted' is what the chemistry does not explain (the synthetic efficiency is a generator assumption, so a gap is expected).", "heat", height=300,
                title="Heat balance waterfall (MW)")

    st.subheader("Predicted effect of a forward-fan move (grate unchanged)")
    cd = s["candidates"].copy()
    if cd.empty:
        st.info("No forward-fan move can be evaluated on this row (the what-if model needs complete inputs and a move inside the allowed range).")
    else:
        cd["Checks pass"] = cd["Checks pass"].map({True: "✅ pass", False: "❌ fail / hold"})
        st.dataframe(cd.round(2), hide_index=True, width="stretch")
    C.provenance(f"{label}. Each row re-runs the what-if model (ridge efficiency response, stoichiometric O2 from FD, CO and draft models, OOD check) plus the chemistry efficiency at the predicted O2. "
                 "A move is only a candidate if every constraint passes. Associational model on synthetic data.")

    st.subheader("Mass balance (kg per hour)")
    mb = s["mass"]
    m1, m2 = st.columns(2)
    m1.dataframe(pd.DataFrame({"In": list(mb["in"]), "kg/h": [f"{v:,.0f}" for v in mb["in"].values()]}), hide_index=True, width="stretch")
    m2.dataframe(pd.DataFrame({"Out": list(mb["out"]), "kg/h": [f"{v:,.0f}" for v in mb["out"].values()]}), hide_index=True, width="stretch")
    st.caption(f"In {mb['in_total']:,.0f} kg/h, out {mb['out_total']:,.0f} kg/h: closure {mb['closure_pct']:+.3f} % (species balance from the fuel analysis and the measured O2).")

    st.subheader("Performance trend (trailing 6 h)")
    win = df.iloc[max(0, i - 71): i + 1]
    lm = df.groupby("fuel_lot")["fuel_moisture_wb_pct"].transform("first")
    fuel, rows = cb.load_fuel(), []
    for j in win.index:
        r = df.loc[j]
        m = lm.loc[j]
        if pd.isna(m) or pd.isna(r["O2_pct_dry"]) or pd.isna(r["stack_temp_C"]) or pd.isna(r["LHV_used_MJkg"]):
            rows.append((r["t"], np.nan, np.nan, r["O2_pct_dry"]))
            continue
        co = r["CO_ppm"] if r["co_available"] == 1 and pd.notna(r["CO_ppm"]) else 0.0
        e = cb.losses(fuel, float(m), float(r["LHV_used_MJkg"]), float(r["O2_pct_dry"]), float(r["stack_temp_C"]), float(r["ambient_temp_C"]), co, None, float(r["ambient_RH_pct"]) if pd.notna(r["ambient_RH_pct"]) else 70.0)
        rows.append((r["t"], e["eta_indirect_pct"], r["eta_pct"] if r["status_eta"] != "UNAVAILABLE" else np.nan, r["O2_pct_dry"]))
    tr = pd.DataFrame(rows, columns=["t", "eta_chem", "eta_hb", "o2"])
    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=tr["t"], y=tr["eta_chem"], name="η chemistry %", line=dict(color="#002E61", width=3))
    fig.add_scatter(x=tr["t"], y=tr["eta_hb"], name="η HTF heat balance %", line=dict(color="#009933", dash="dot"))
    fig.add_scatter(x=tr["t"], y=tr["o2"], name="flue O2 % dry", line=dict(color="#CC0033"), secondary_y=True)
    if best:
        fig.add_hline(y=s["o2_best"], line=dict(color="#CC0033", dash="dash"), secondary_y=True, annotation_text="best allowed O2")
    C.bands(fig, tr["t"], tr["eta_hb"], "eta_pct", "#009933", label=False)
    C.bands(fig, tr["t"], tr["o2"], "O2_pct_dry", "#CC0033", secondary_y=True, label=False)
    fig.update_yaxes(title_text="efficiency, %", secondary_y=False, range=[60, 95])
    fig.update_yaxes(title_text="O2, % dry", secondary_y=True, range=[4, 12], showgrid=False)
    C.chart(fig, f"{label}. Trailing 6 h to the replay cursor, 5-min rows: indirect efficiency from the loss balance, HTF heat-balance efficiency where computable, and flue O2 against the best allowed O2 for the current row. "
                 "Moisture per row is the lab value of its fuel lot (never interpolated).", "trend",
            title="Efficiency and flue O2 trend (trailing 6 h)")
