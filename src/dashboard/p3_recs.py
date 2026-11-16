"""Screen 3 — AI Recommendations (simulated scenario; NO ADVICE is the fail-safe state)."""
import pandas as pd
import streamlit as st

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
    flt = st.radio("Rows to list", ["All", "ADVICE only", "NO ADVICE only"], horizontal=True, key="rec_filter")
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
        st.caption("Gated rows show no proposed settings, no predicted benefit and no interval by design.")
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
