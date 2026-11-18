"""Screen 3 — AI Recommendations (simulated scenario; NO ADVICE is the fail-safe state)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import chem_advice
from src.dashboard import common as C


def _row(label, a, b, unit=""):
    return {"Quantity": label, "Current": a, "Proposed (simulated)": b, "Unit": unit}


def checklist(rec, L):
    cc = rec.get("constraint_checks")
    if not cc:
        return None
    u = rec["uncertainty"]
    return [("O2 stays above floor", cc["O2_option_pct"] >= cc["O2_floor_pct"], f"{cc['O2_option_pct']} % vs floor {cc['O2_floor_pct']} %"),
            ("CO below limit (with safety factor)", cc["CO_option_ppm"] <= cc["CO_limit_ppm"], f"{cc['CO_option_ppm']} ppm vs limit {cc['CO_limit_ppm']} ppm"),
            ("Draft inside band", cc["draft_band_pa"][0] <= cc["draft_option_pa"] <= cc["draft_band_pa"][1], f"{cc['draft_option_pa']} Pa vs {cc['draft_band_pa']}"),
            ("In training distribution", not cc["ood_option"], "in distribution" if not cc["ood_option"] else "OUT of distribution"),
            ("Move within max step", True, f"≤ ±{cc['max_step_pct']} % per axis"),
            ("Interval width within limit", u["width_kg_GJ"] <= L["interval_width_max_sfc_kg_gj"], f"{u['width_kg_GJ']} vs ≤ {L['interval_width_max_sfc_kg_gj']} kg/GJ"),
            ("Pessimistic (95th pct) change is a reduction", u["dSFC_hi90"] < 0, f"{u['dSFC_hi90']:+.3f} kg/GJ")]


def _chem_section(df, row, rec, is_def, label):
    """Chemical-engineering view: excess air, flue gas, indirect loss balance, loss-vs-O2 trade-off, objective terms, cross-check."""
    st.subheader("Chemical engineering view: why this is (or is not) sensible")
    if not is_def:
        st.info("Chemistry view needs the default synthetic data and its effect model; it is not computed for uploaded files.")
        return
    i = row.name
    v = chem_advice.chem_view(row, chem_advice.lot_moisture(df, i), rec, C.effect_model(), C.limits())
    if v is None:
        st.warning("Not enough data for the chemistry view on this row (needs moisture, LHV, O2 and stack temperature). No guess is made.")
        return
    c = v["current"]
    k = st.columns(5)
    k[0].metric("Excess air λ", f"{c['lambda']:.2f}", f"{100 * (c['lambda'] - 1):.0f} % above stoichiometric", delta_color="off")
    k[1].metric("Stoichiometric air", f"{c['stoich_air_kg_per_kg']:.2f} kg/kg fuel")
    k[2].metric("Dry flue-gas loss", f"{c['dry_flue_gas']:.1f} % of LHV")
    k[3].metric("Indirect η (chemistry)", f"{c['eta_indirect_pct']:.1f} %")
    hb = v["eta_heat_balance"]
    k[4].metric("η from HTF heat balance", f"{hb:.1f} %" if hb is not None else "n/a", f"gap {c['eta_indirect_pct'] - hb:+.1f} points" if hb is not None else None, delta_color="off")
    for line in chem_advice.explain(v, rec):
        st.markdown("• " + line)
    names = {"dry_flue_gas": "Dry flue gas", "water_vapour": "Water vapour", "CO": "CO (incomplete)", "unburnt_carbon": "Unburnt carbon in ash", "radiation_other": "Radiation / other (ASSUMED)"}
    cols = ["#002E61", "#4d7aa8", "#CC0033", "#e07a90", "#999999"]
    fig = go.Figure()
    cats = ["Now"] + (["Proposed"] if "option" in v else [])
    for (key, nm), col in zip(names.items(), cols):
        fig.add_bar(y=cats, x=[c[key]] + ([v["option"][key]] if "option" in v else []), name=nm, orientation="h", marker_color=col)
    fig.update_layout(barmode="stack", height=230)
    fig.update_xaxes(title_text="loss, % of fuel LHV")
    C.chart(fig, f"{label}. Indirect heat-loss balance per kg as-fired fuel (LHV basis): dry flue gas = n·Mcp·(T_stack − T_amb); vapour sensible heat; CO = n_CO·283 MJ/kmol; unburnt carbon in ash × 32.8 MJ/kg; "
                 "radiation ASSUMED. Fuel analysis is ASSUMED generic palm-kernel shell (config/fuel_properties.yaml), so this is an OWN-ESTIMATE; "
                 "the gap to the HTF heat-balance η is a closure check, not an error bar.", "chem_loss",
            title="Heat-loss breakdown: now vs. proposed")
    cv = v["curve"]
    fig = go.Figure()
    fig.add_scatter(x=cv["O2_pct"], y=cv["dry_flue_gas_loss"], name="dry flue-gas loss", line=dict(color="#002E61"))
    if v["co_measured"]:
        fig.add_scatter(x=cv["O2_pct"], y=cv["co_loss"], name="CO loss", line=dict(color="#CC0033"))
    fig.add_scatter(x=cv["O2_pct"], y=cv["total_loss"], name="stack + CO loss", line=dict(color="#009933", width=3))
    fig.add_vrect(x0=cv["O2_pct"].min(), x1=v["floor"], fillcolor="rgba(204,0,51,.10)", line_width=0, annotation_text="below O2 floor", annotation_position="top left")
    o2_now = 21 - 21 / c["lambda"]
    fig.add_vline(x=o2_now, line=dict(color="#333", dash="dash"), annotation_text="now")
    if "option" in v:
        fig.add_vline(x=v["o2_option"], line=dict(color="#009933", dash="dot"), annotation_text="proposed", annotation_position="bottom")
    fig.update_xaxes(title_text="flue-gas O2, % dry")
    fig.update_yaxes(title_text="loss, % of LHV")
    C.chart(fig, f"{label}. Trade-off at this row's stack temperature, load, moisture and grate: stack loss falls as air is cut, CO loss (ridge CO model, OWN-ESTIMATE) rises when air gets short; "
                 "red band = below the synthetic O2 floor (ASSUMED / NOT APPROVED). CO curve is blank where CO is not measured.", "chem_curve",
            title="Excess-air trade-off: stack loss vs. CO loss")
    if "objective" in v:
        st.markdown("**Optimizer objective, term by term** (lower is better; weights OWN-ESTIMATE, set before results, not tuned): J = ΔSFC + λ₁·Δfan power + λ₂·|move| + λ₃·interval width")
        o = pd.DataFrame({"Term": list(v["objective"]), "Value (kg/GJ-equivalent)": [f"{x:+.3f}" for x in v["objective"].values()]})
        o.loc[len(o)] = ["J (hold = 0)", f"{v['objective_J']:+.3f}"]
        st.dataframe(o, hide_index=True, width="stretch")


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("recs")
    df, label, is_def = C.filtered()
    if df.empty:
        st.warning("No rows in the selected time range.")
        return
    st.error("Human review required. This is a simulated scenario from a synthetic model — it is not an instruction.")
    L = C.limits()["limits"]
    recs = C.load_advisory() if is_def else {}
    if not is_def:
        st.warning("Uploaded data: no optimizer records exist for it, so every row is shown as NO ADVICE (fail-safe).")
    flt = st.radio("Rows to list", ["All", "ADVICE only", "NO ADVICE only"], horizontal=True, key="rec_filter", index=1 if st.query_params.get("filter") == "advice" else 0)
    dec = df["timestamp_local"].map(lambda t: recs.get(t, {}).get("decision", "NO_ADVICE"))
    keep = {"All": dec != "x", "ADVICE only": dec == "ADVICE", "NO ADVICE only": dec != "ADVICE"}[flt]
    sub = df[keep]
    if sub.empty:
        st.info("No rows match this filter in the selected range.")
        return
    ts = sub["timestamp_local"].tolist()
    if len(ts) > 4000:
        ts = ts[::len(ts) // 4000 + 1]
    sel = st.selectbox("Timestamp", ts, key="rec_ts", format_func=lambda s: f"{pd.Timestamp(s):%Y-%m-%d %H:%M}")
    row = df[df["timestamp_local"] == sel].iloc[0]
    rec = C.gate_state(sel) if is_def else {**C.gate_state("none"), "timestamp": sel}
    st.session_state["decision_ts"] = sel

    if rec["decision"] == "ADVICE":
        st.success(f"## ADVICE (simulated) — {rec['action']} · {rec['advice_class'].replace('_', ' ').title()}")
    else:
        C.no_advice_box("the system will not propose a change for this moment", "DIAGNOSTIC ONLY — " if rec["decision"] == "DIAGNOSTIC_ONLY" else "")
    st.markdown("**HUMAN REVIEW REQUIRED** · model " + rec.get("model_version", "n/a") + " · " + rec.get("banner", C.BANNER))
    codes = rec.get("reason_codes") or []
    if codes:
        st.markdown("**Reason codes**")
        for c in codes:
            st.markdown(f"- `{c}` — {C.REASON_TEXT.get(c, c)}")
    elif rec["decision"] == "ADVICE":
        st.markdown("**Reason codes:** none (all guardrails passed)")

    if rec["decision"] != "ADVICE":
        st.caption("Gated rows show no proposed settings, no predicted benefit and no interval by design. The chemistry below is diagnostic only.")
        _chem_section(df, row, rec, is_def, label)
        return

    cur, prop, u, cc = rec["current_simulated_settings"], rec["proposed_simulated_settings"], rec["uncertainty"], rec["constraint_checks"]
    t = pd.DataFrame([_row("FD fan command", cur["FD_command_pct"], prop["FD_command_pct"], "%"),
                      _row("Grate command", cur["grate_command_pct"], prop["grate_command_pct"], "%"),
                      _row("ID fan command (unchanged)", cur["ID_command_pct"], cur["ID_command_pct"], "%"),
                      _row("Flue O2 (predicted)", cur["O2_pct_dry"], cc["O2_option_pct"], "% dry"),
                      _row("SFC (model)", rec["predicted_SFC_current"], rec["predicted_SFC_option"], "kg/GJ"),
                      _row("CO (predicted)", row["CO_ppm"] if row["co_available"] == 1 else "n/a", cc["CO_option_ppm"], "ppm"),
                      _row("Draft (predicted)", round(float(row["draft_pa"]), 1), cc["draft_option_pa"], "Pa")]).astype(str)
    st.subheader("Current vs proposed (synthetic scenario)")
    st.dataframe(t, hide_index=True, width="stretch")
    b = rec["predicted_benefit_synthetic_only"]
    st.markdown(f"**Predicted change:** ΔSFC {u['dSFC_kg_GJ_point']:+.3f} kg/GJ ({b['dSFC_pct']:+.2f} %), 90 % interval "
                f"[{u['dSFC_lo90']:+.3f}, {u['dSFC_hi90']:+.3f}] kg/GJ; Δη {b['deta_pp']:+.2f} pp. "
                "_" + b["label"] + "; the effect model is associational, not proven causal._")
    st.subheader("Constraint checklist")
    for name, ok, detail in checklist(rec, L):
        st.markdown(f"{'✅' if ok else '❌'} **{name}** — {detail}")
    C.provenance(f"{label}. Advisory record {rec['model_version']} (ridge effect model, OWN-ESTIMATE, training split only, 200 lot-bootstraps); "
                 "ΔSFC = SFC(option) − SFC(current), kg fuel per GJ useful heat, same demand, next 5-min interval; interval covers coefficient "
                 "uncertainty only. Synthetic generator illustration, never a savings claim.")
    _chem_section(df, row, rec, is_def, label)
