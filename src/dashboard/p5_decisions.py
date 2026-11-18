"""Screen 5 — Operator Decisions (role IDs only; log to SQLite; nothing is sent to any plant system)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import oplog
from src.dashboard import common as C


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("decisions")
    st.error("SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION · this log records opinions about simulated advice; it does not change any setting.")
    df, label, is_def = C.filtered()
    recs = C.load_advisory() if is_def else {}
    st.subheader("Record a decision")
    if df.empty:
        st.warning("No rows in the selected time range.")
    else:
        dec = df["timestamp_local"].map(lambda t: recs.get(t, {}).get("decision", "NO_ADVICE"))
        show_gated = st.checkbox("Include NO ADVICE rows", value=not (dec == "ADVICE").any(), key="op_gated")
        pool = df[dec == "ADVICE"] if not show_gated else df
        ts = pool["timestamp_local"].tolist()
        if not ts:
            st.info("No ADVICE rows in this range. Tick 'Include NO ADVICE rows' to log a decision on a gated row.")
        else:
            ts = ts[::len(ts) // 3000 + 1]
            pre = st.session_state.get("decision_ts")
            sel = st.selectbox("Advisory row", ts, index=ts.index(pre) if pre in ts else 0, key="op_ts",
                               format_func=lambda s: f"{pd.Timestamp(s):%Y-%m-%d %H:%M}")
            rec = C.gate_state(sel) if is_def else {**C.gate_state("none"), "timestamp": sel}
            if rec["decision"] == "ADVICE":
                st.success(f"ADVICE (simulated): {rec['action']} — human review required")
            else:
                st.markdown("**NO ADVICE** — " + ", ".join(rec.get("reason_codes") or ["gated"]) + " (accept is disabled)")
            with st.form("op_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                role = c1.selectbox("Role ID", list(oplog.ROLES))
                choices = list(oplog.DECISIONS) if rec["decision"] == "ADVICE" else ["reject", "defer"]
                choice = c2.selectbox("Decision", choices)
                reason = c3.selectbox("Reason", list(oplog.REASONS))
                note = st.text_input(f"Note (max {oplog.NOTE_MAX} characters; no personal names)", max_chars=oplog.NOTE_MAX)
                if st.form_submit_button("Log decision"):
                    try:
                        oplog.add(role, choice, reason, note, rec, label)
                        st.success("Logged to data/operator_log.db (local). Nothing was sent to a plant system.")
                    except ValueError as e:
                        st.error(f"Not logged: {e}")
    st.subheader("Decision log")
    log = oplog.read()
    if log.empty:
        st.info("No decisions logged yet.")
    else:
        st.dataframe(log, hide_index=True, width="stretch")
        st.download_button("Download CSV", log.to_csv(index=False).encode("utf-8"), "operator_decisions.csv", "text/csv", key="op_dl")
    C.provenance("data/operator_log.db, entries typed in this dashboard (SYNTHETIC session; role IDs OP-A / OP-B, no names).")

    st.subheader("Synthetic operator action log by shift")
    a = C.load_actions()
    rng = st.session_state.get("time_range")
    if rng and len(rng) == 2:
        lo = pd.Timestamp(rng[0]).tz_localize(C.TZ)
        a = a[(a["t"] >= lo) & (a["t"] < pd.Timestamp(rng[1]).tz_localize(C.TZ) + pd.Timedelta(days=1))]
    if a.empty:
        st.info("No action-log rows in the selected range.")
        return
    g = a.groupby(["shift_id", "variable"]).size().reset_index(name="changes")
    fig = px.bar(g, x="shift_id", y="changes", color="variable", barmode="group")
    C.chart(fig, "data/raw_synthetic/operator_action_log.csv — count of simulated setpoint/command changes per synthetic shift crew "
                 f"(OP-A / OP-B / OP-C labels are generator shift IDs), {len(a):,} changes in range, selected time filter.", "shift",
            title="Operator changes per shift crew")
    src = a["source"].value_counts()
    st.caption("Change sources in range: " + ", ".join(f"{k} {v}" for k, v in src.items()) + " (EXPLORATION = generator-injected variation).")
