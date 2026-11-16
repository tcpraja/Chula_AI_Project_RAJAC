"""Screen 4 — What-if Simulator. Bounds come from config/guardrail_limits.yaml; out-of-bounds -> error and NO output."""
import numpy as np
import pandas as pd
import streamlit as st

from src import whatif
from src.dashboard import common as C


def render():
    C.page_header("whatif")
    df, label, is_def = C.filtered()
    st.error("SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION · human review required · results are model illustrations, not instructions.")
    if not is_def:
        st.warning("Uploaded data: the effect model was fitted on the default synthetic file; the simulator is disabled for uploads.")
        return
    G = C.limits()
    L = G["limits"]
    recs = C.load_advisory()
    el = df[df["timestamp_local"].map(lambda t: recs.get(t, {}).get("eligible", False))]
    if el.empty:
        st.info("No guardrail-eligible rows in the selected range (the simulator only starts from rows that pass the gate). Widen the time filter.")
        return
    ts = el["timestamp_local"].tolist()
    ts = ts[::len(ts) // 3000 + 1]
    sel = st.selectbox("Starting point (guardrail-eligible rows only)", ts, key="wi_ts", format_func=lambda s: f"{pd.Timestamp(s):%Y-%m-%d %H:%M}")
    row = df[df["timestamp_local"] == sel].iloc[0]
    st.markdown(f"Allowed (config): FD {L['fd_range_pct']} %, grate {L['grate_range_pct']} %, max move ±{L['max_step_fd_pct']:g} % FD / ±{L['max_step_grate_pct']:g} % grate. "
                "Values outside are rejected, not clipped.")
    c1, c2 = st.columns(2)
    fd0, g0 = float(row["FD_command_pct"]), float(row["grate_command_pct"])
    prop = recs.get(sel, {}).get("proposed_simulated_settings") or {"FD_command_pct": fd0, "grate_command_pct": g0}   # open on the advisory option if one exists
    fd = c1.number_input("FD fan command target (%)", value=round(float(prop["FD_command_pct"]), 1), step=0.5, key=f"wi_fd_{sel}")
    g = c2.number_input("Grate command target (%)", value=round(float(prop["grate_command_pct"]), 1), step=0.5, key=f"wi_g_{sel}")
    st.caption(f"Current settings: FD {fd0:.1f} %, grate {g0:.1f} %. Targets start at the advisory option for this row when one exists.")
    bad = whatif.validate(row, fd, g, G)
    if bad:
        st.error("Input out of bounds — no result is produced.\n\n" + "\n".join(f"- {b}" for b in bad))
        return
    try:
        res = whatif.evaluate(row, fd, g, C.effect_model(), G)
    except ValueError as e:
        st.error(f"Cannot evaluate this row: {e}. No result is produced.")
        return
    if abs(fd - fd0) < 1e-9 and abs(g - g0) < 1e-9:
        st.info("Targets equal the current settings (HOLD) — change a target to simulate a move.")
    k = st.columns(4)
    k[0].metric("SFC now → option (kg/GJ)", f"{res['SFC_current']:.2f} → {res['SFC_option']:.2f}")
    k[1].metric("ΔSFC point (kg/GJ)", f"{res['dSFC_point']:+.3f}", f"{res['dSFC_pct']:+.2f} %", delta_color="inverse")
    k[2].metric("90 % interval", f"[{res['dSFC_lo90']:+.3f}, {res['dSFC_hi90']:+.3f}]")
    k[3].metric("Δ FD fan power (model)", f"{res['dfan_kw']:+.2f} kW")
    st.markdown(f"Predicted O2 {row['O2_pct_dry']:.2f} → **{res['O2_option_pct']:.2f} %**, CO → **{res['CO_option_ppm']:.0f} ppm**, "
                f"draft → **{res['draft_option_pa']:.1f} Pa**, Δη {res['deta_pp']:+.2f} pp, move label `{res['label']}`.")
    st.subheader("Constraint checklist")
    for name, (ok, detail) in res["checks"].items():
        st.markdown(f"{'✅' if ok else '❌'} **{name}** — {detail}")
    if res["all_pass"]:
        st.success("All checks pass → this move would be a candidate, still **human review required**.")
    else:
        C.no_advice_box("a check failed for this move")
    C.provenance(f"{label}. Ridge efficiency-response model (OWN-ESTIMATE, train split), O2 from FD by stoichiometry at fixed demand, fan power ∝ FD³, "
                 "ΔSFC in kg fuel per GJ useful heat for the next 5-min interval; interval = 90 % of 200 lot-bootstraps (coefficient uncertainty only). "
                 "Associational model, synthetic only.")
