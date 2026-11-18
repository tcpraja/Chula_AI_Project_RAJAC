"""Screen 6 — Business Value. Simulated effect only; THB figures are sensitivities on ASSUMED inputs, never verified savings."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard import common as C


def effect_stats(df, recs):
    """Weighted simulated effect over scored rows of df: share of rows with ADVICE x mean row-level dSFC %, with 90 % bound means."""
    scored = df[df["timestamp_local"].isin(recs)]
    adv = [recs[t] for t in scored["timestamp_local"] if recs[t]["decision"] == "ADVICE"]
    n, k = len(scored), len(adv)
    if n == 0:
        return None
    share = k / n
    if k == 0:
        return {"n": n, "k": 0, "share": 0.0, "pt": 0.0, "lo": 0.0, "hi": 0.0, "mean_adv_pct": 0.0}
    pct = lambda r, key: 100.0 * r["uncertainty"][key] / r["predicted_SFC_current"]
    pt, lo, hi = (np.mean([pct(r, key) for r in adv]) for key in ("dSFC_kg_GJ_point", "dSFC_lo90", "dSFC_hi90"))
    return {"n": n, "k": k, "share": share, "pt": share * pt, "lo": share * lo, "hi": share * hi, "mean_adv_pct": pt}


def render():
    _render_body()
    C.footer()


def _render_body():
    C.page_header("value")
    df, label, is_def = C.filtered()
    st.error("NO VERIFIED SAVINGS. Everything below is a synthetic simulation or an assumption-driven sensitivity — not a measured or approved benefit.")
    if df.empty:
        st.warning("No rows in the selected time range.")
        return
    recs = C.load_advisory() if is_def else {}
    es = effect_stats(df, recs)
    if es is None:
        st.info("No advisory records cover the selected range (held-out replay only), or an uploaded file is active. Pick a range inside the test split.")
        return

    st.subheader("Simulated efficiency effect (index, baseline = 100)")
    k = st.columns(4)
    k[0].metric("Rows scored", f"{es['n']:,}")
    k[1].metric("Rows with ADVICE", f"{es['k']:,}", f"{es['share']:.1%} of rows", delta_color="off")
    k[2].metric("Mean ΔSFC on advised rows", f"{es['mean_adv_pct']:+.2f} %")
    k[3].metric("Simulated SFC index", f"{100 + es['pt']:.2f}", f"{es['pt']:+.2f} %", delta_color="inverse")
    fig = go.Figure()
    fig.add_bar(x=["Baseline (no advice)", "Simulated, advice followed"], y=[100, 100 + es["pt"]],
                error_y=dict(type="data", symmetric=False, array=[0, es["hi"] - es["pt"]], arrayminus=[0, es["pt"] - es["lo"]]),
                marker_color=["#999999", "#009933"])
    fig.update_yaxes(range=[min(98, 100 + es["lo"] - 0.3), 100.3], title_text="SFC index (base = 100)")
    C.chart(fig, f"{label}. Index = 100 × (1 + share of rows with ADVICE × mean predicted ΔSFC ÷ SFC), next-interval, same useful heat; error bar = mean of row-level 90 % "
                 "bootstrap bounds × share (coefficient uncertainty only, not model error). Assumes every advice is followed, which no one has verified. OWN-ESTIMATE model on synthetic data.", "idx",
            title="Simulated SFC index: baseline vs. advice followed")

    st.subheader("THB sensitivity (ASSUMED inputs — edit them)")
    c = st.columns(5)
    price = c[0].number_input("Fuel price, THB/tonne (ASSUMED)", 0.0, 100000.0, 2500.0, 100.0, key="v_price")
    hours = c[1].number_input("Operating hours / year (ASSUMED)", 0.0, 8760.0, 7000.0, 100.0, key="v_hours")
    tariff = c[2].number_input("Electricity, THB/kWh (ASSUMED)", 0.0, 100.0, 4.0, 0.1, key="v_tariff")
    watts = c[3].number_input("Model server power, W (ASSUMED)", 0.0, 5000.0, 30.0, 5.0, key="v_watts")
    mhours = c[4].number_input("Model run hours / year (ASSUMED)", 0.0, 8760.0, 8760.0, 100.0, key="v_mhours")

    scored = df[df["timestamp_local"].isin(recs)]
    fuel_kgh = float(scored["fuel_rate_aligned_kgh"].mean())
    fuel_t = fuel_kgh * hours / 1000.0
    idx = df["fuel_price_index"].dropna()
    p10, p50, p90 = (float(idx.quantile(q)) for q in (0.1, 0.5, 0.9))
    scen = {"low (index P10)": p10 / p50, "base (index P50)": 1.0, "high (index P90)": p90 / p50}
    rows = []
    for nm, mult in scen.items():
        cost = fuel_t * price * mult
        rows.append({"fuel_price_index scenario": nm, "price × base": round(mult, 3), "fuel cost THB/yr": round(cost),
                     "saving pessimistic": round(-es["hi"] / 100 * cost), "saving point": round(-es["pt"] / 100 * cost),
                     "saving optimistic": round(-es["lo"] / 100 * cost)})
    t = pd.DataFrame(rows)
    st.caption("Gross sensitivity: before the realisation share (ASSUMED 0.2–1.0) and before running costs. The Phase 6 workbook (reports/economics_and_energy.xlsx) nets these off: base case is negative, no payback.")
    st.dataframe(t, hide_index=True, width="stretch")
    fig = go.Figure(go.Bar(x=t["fuel_price_index scenario"], y=t["saving point"],
                           error_y=dict(type="data", symmetric=False, array=(t["saving optimistic"] - t["saving point"]),
                                        arrayminus=(t["saving point"] - t["saving pessimistic"]))))
    fig.update_yaxes(title_text="THB/yr (simulated)")
    C.chart(fig, f"{label}. THB/yr = simulated ΔSFC share × fuel tonnes/yr ({fuel_kgh:,.0f} kg/h mean over scored rows × {hours:,.0f} h) × ASSUMED price × fuel_price_index scenario "
                 f"(P10/P50/P90 of the synthetic index relative to P50). Bars = point; whiskers = 90 % bounds. ASSUMED inputs, synthetic effect: not a savings claim.", "thb",
            title="Simulated fuel saving by price scenario (THB/yr)")

    st.subheader("Electricity")
    fan_kw = float((scored["fan_power_kW_FD"] + scored["fan_power_kW_ID"]).mean())
    fan_thb = fan_kw * hours * tariff
    model_kwh = watts / 1000.0 * mhours
    model_thb = model_kwh * tariff
    e = st.columns(4)
    e[0].metric("Fan electricity (FD + ID)", f"{fan_kw:,.1f} kW mean", f"≈ {fan_thb:,.0f} THB/yr", delta_color="off")
    e[1].metric("Model electricity", f"{model_kwh:,.0f} kWh/yr", f"≈ {model_thb:,.0f} THB/yr", delta_color="off")
    base_pt = int(t.loc[t["price × base"] == 1.0, "saving point"].iloc[0])
    e[2].metric("Simulated gain − model electricity (base)", f"{base_pt - model_thb:,.0f} THB/yr")
    e[3].metric("Model electricity share of simulated gain", f"{(model_thb / base_pt):.1%}" if base_pt > 0 else "n/a")
    C.provenance(f"{label}. Fan electricity = mean of fan_power_kW_FD + fan_power_kW_ID columns (synthetic) × hours × ASSUMED tariff; the simulated FD-command changes are "
                 "not converted to kWh here. Model electricity = power × time (ASSUMED W × hours). No saving is verified; verification requires a measured pilot.")
    st.caption("Stop condition: nothing here is a result. A trial with measured fuel mass, LHV and heat output is needed before any THB figure is reported as a saving.")
