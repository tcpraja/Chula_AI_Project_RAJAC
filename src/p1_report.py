"""Phase 1 figures (reports/figs/p1_*) and reports/synthetic_data_card.md, computed from the generated CSVs.
Run: python -m src.p1_report
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.units import HTFTable

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_synthetic"
FIG = ROOT / "reports" / "figs"
C = {"a": "#1f6f8b", "b": "#d1495b", "c": "#edae49", "g": "#66737d"}
TAG = "SYNTHETIC - NOT FOR PLANT OPERATION"


def load():
    m = pd.read_csv(RAW / "synthetic_heater_c_5min.csv", parse_dates=["timestamp_local"])
    t = pd.read_csv(RAW / "synthetic_truth.csv", parse_dates=["timestamp_local"])
    return m, t, pd.read_csv(RAW / "fault_cases.csv"), pd.read_csv(RAW / "operator_action_log.csv", parse_dates=["timestamp"])


def pick_day(m):
    """Day (normal block) with a sootblow and a lot change, else the one with most events."""
    n = m[~m.scenario_id.str.startswith("FAULT_")].copy()
    n["d"] = n.timestamp_local.dt.date
    score = n.groupby("d").apply(lambda g: (g.sootblow.max() > 0) * 2 + (g.scenario_id == "LOT_CHANGE").any() + (g.operating_mode == "RAMP").any(),
                                 include_groups=False)
    cand = [d for d, s in score.items() if s == score.max() and d > n.d.min()]
    return cand[len(cand) // 2]


def fig_trend(m, t):
    d = pick_day(m)
    g = m[m.timestamp_local.dt.date == d].reset_index(drop=True)
    tg = t[t.timestamp_local.dt.date == d].reset_index(drop=True)
    fig, ax = plt.subplots(5, 1, figsize=(12, 11), sharex=True)
    x = g.timestamp_local
    ax[0].plot(x, g.Q_out_MW, color=C["a"], label="Q_out measured (MW)")
    ax[0].plot(x, tg.Q_demand_MW, color=C["g"], lw=1, ls="--", label="demand (truth)")
    ax[0].set_ylabel("MW")
    ax[1].plot(x, g.fuel_rate_measured_kgh, color=C["c"], label="fuel measured (kg/h)")
    ax2 = ax[1].twinx()
    ax2.plot(x, g.SFC_kg_GJ, color=C["b"], lw=1, label="SFC (kg/GJ)")
    ax2.set_ylim(60, 160)
    ax[1].set_ylabel("kg/h")
    ax2.set_ylabel("kg/GJ")
    ax[2].plot(x, g.O2_pct_dry, color=C["a"], label="O2 measured (% dry)")
    ax[2].plot(x, tg.O2_opt_true_pct, color=C["b"], ls="--", lw=1, label="hidden optimum O2 (truth)")
    ax[2].set_ylabel("% dry")
    ax[3].plot(x, g.FD_command_pct, label="FD cmd %", color=C["a"])
    ax[3].plot(x, g.ID_command_pct, label="ID cmd %", color=C["c"])
    ax[3].plot(x, g.grate_command_pct, label="grate cmd %", color=C["b"])
    ax[3].set_ylabel("command %")
    ax[4].plot(x, tg.eta_true * 100, color=C["a"], label="latent eta % (truth)")
    ax[4].plot(x, g.eta_direct_pct, color=C["g"], lw=1, label="eta direct % (measured)")
    ax[4].set_ylabel("%")
    ax[4].set_ylim(30, 100)
    for k, w in g.groupby((g.fuel_lot != g.fuel_lot.shift()).cumsum()):
        if k > 1 and w.index[0] > 0:
            for a in ax:
                a.axvline(w.timestamp_local.iloc[0], color=C["g"], lw=0.8, ls=":")
            ax[0].annotate("lot change", (w.timestamp_local.iloc[0], ax[0].get_ylim()[1]), fontsize=8, va="top")
    for _, w in g[g.sootblow > 0].groupby((g.sootblow.diff() != 0).cumsum()):
        ax[4].annotate("sootblow", (w.timestamp_local.iloc[0], 35), fontsize=8, color=C["b"])
    for _, w in g[g.operating_mode == "RAMP"].groupby((g.operating_mode != "RAMP").cumsum()):
        ax[0].axvspan(w.timestamp_local.iloc[0], w.timestamp_local.iloc[-1], color=C["c"], alpha=0.15)
    for _, w in g[g.advice_eligibility.str.startswith("ELIGIBLE")].groupby((~g.advice_eligibility.str.startswith("ELIGIBLE")).cumsum()):
        ax[4].axvspan(w.timestamp_local.iloc[0], w.timestamp_local.iloc[-1], color=C["a"], alpha=0.08)
    for a in ax:
        a.legend(loc="upper right", fontsize=8, ncol=3)
        a.grid(alpha=0.25)
    fig.suptitle(f"Heater C 24 h trend, {d} (seed 42) | amber = ramp, blue = ELIGIBLE window | {TAG}", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "p1_trend_24h.png", dpi=130)
    plt.close(fig)
    return str(d)


def fig_hist(m, t):
    n = m[~m.scenario_id.str.startswith("FAULT_")]
    nt = t.loc[n.index]
    v = n[(n.quality_flag == "OK")]
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    items = [(nt.moisture_true_wb_pct.drop_duplicates() if False else nt.groupby("fuel_lot_idx").moisture_true_wb_pct.first(), "lot moisture (% wb), per lot", "%wb"),
             (nt.groupby("fuel_lot_idx").LHV_true_MJkg.first(), "lot as-fired LHV (MJ/kg), per lot", "MJ/kg"),
             (nt.eta_true[n.operating_mode == "STEADY"] * 100, "latent eta, STEADY rows (truth)", "%"),
             (v.SFC_kg_GJ[v.operating_mode == "STEADY"].clip(upper=200), "SFC, valid STEADY rows (measured)", "kg/GJ"),
             (v.O2_pct_dry, "O2 measured, valid rows", "% dry"),
             (nt.best_action_eta_gain_pp[nt.best_action_eta_gain_pp > 0], "eta gain of best feasible action (generator illustration)", "% points")]
    for a, (x, ttl, u) in zip(ax.ravel(), items):
        a.hist(x.dropna(), bins=40, color=C["a"])
        a.set_title(ttl, fontsize=9)
        a.set_xlabel(f"{u} (n={x.notna().sum()})")
        a.grid(alpha=0.25)
    fig.suptitle(f"Distributions, normal block (seed 42, 60 days) | {TAG}", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "p1_histograms.png", dpi=130)
    plt.close(fig)


def balance_residuals(t):
    tab = HTFTable()
    op = t.Q_out_true_MW > 1.0
    q = tab.heat_mw(t.HTF_flow_true_m3h[op], t.HTF_Tin_true_C[op], t.HTF_Tout_heater_true_C[op])
    qt = t.Q_out_true_MW[op]
    return (q - qt) / qt * 100.0, (qt - t.eta_true[op] * t.Q_in_true_MW[op]) / qt * 100.0


def fig_resid(m, t):
    r_hx, r_eta = balance_residuals(t)
    n = m[(m.quality_flag == "OK") & (m.lhv_known == 1) & (m.operating_mode == "STEADY") & (m.HTF_bypass_pct == 0)]
    tt = t.loc[n.index]
    meas_err = (n.Q_out_MW - tt.Q_out_true_MW) / tt.Q_out_true_MW * 100
    fuel_err = (n.Q_in_MW - tt.Q_in_true_MW) / tt.Q_in_true_MW * 100
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.5))
    ax[0].hist(r_hx, bins=60, color=C["a"])
    ax[0].set_title(f"Truth: HTF-side heat vs eta x fuel heat\nmax |residual| = {r_hx.abs().max():.4f} %", fontsize=9)
    ax[1].hist(meas_err.clip(-15, 15), bins=60, color=C["c"])
    ax[1].set_title(f"Measured Q_out vs truth (valid STEADY, no bypass)\nmedian {meas_err.median():.2f} %, 5-95 %: {meas_err.quantile(.05):.1f}..{meas_err.quantile(.95):.1f}", fontsize=9)
    ax[2].hist(fuel_err.clip(-25, 25), bins=60, color=C["b"])
    ax[2].set_title(f"Measured Q_in (feed x lab LHV) vs true heat release\nmedian {fuel_err.median():.2f} %, 5-95 %: {fuel_err.quantile(.05):.1f}..{fuel_err.quantile(.95):.1f}", fontsize=9)
    for a in ax:
        a.set_xlabel("residual (%) = (a - b) / b x 100")
        a.grid(alpha=0.25)
    fig.suptitle(f"Energy-balance residuals | {TAG}", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "p1_energy_balance_residuals.png", dpi=130)
    plt.close(fig)
    return float(r_hx.abs().max()), float(r_eta.abs().max())


def card(m, t, f, lg, day, resid):
    n = m[~m.scenario_id.str.startswith("FAULT_")]
    nt = t.loc[n.index]
    elig = n.advice_eligibility.str.split(":").str[0].value_counts(normalize=True)
    reasons = n.advice_eligibility[n.advice_eligibility.str.startswith("NO_ADVICE")].str.split(":").str[1].str.split(";").explode().value_counts()
    steady = n.operating_mode == "STEADY"
    lots = m.groupby("fuel_lot").size()
    dis = pd.read_csv(ROOT / "data" / "stress" / "display_reconciliation.csv")
    L = []
    L.append("# Synthetic Data Card - Heater C (SYNTHETIC)\nHeater: HEATER_C_SYNTHETIC at PET Resin Plant P (anonymized). Every number below is computed by `src/generate_synthetic.py` from the CSVs; provenance SYNTHETIC unless stated. Not for plant operation.\n")
    L.append("## Files\n- data/raw_synthetic/synthetic_heater_c_5min.csv (seed 42; measured columns), synthetic_truth.csv (hidden state), fault_cases.csv, operator_action_log.csv\n- data/stress/stress_seed77.csv (+ _truth, _fault_cases, _operator_action_log) and display_reconciliation.csv\n- config/synthetic_parameters.yaml, config/htf_properties.csv; column definitions in reports/03_data_dictionary.csv (earlier variable inventory kept as 03b)\n")
    L.append(f"## Size\n- Main: {len(m):,} rows x {m.shape[1]} columns = {len(n):,} normal rows (60 d x 288) + {len(m) - len(n):,} fault-block rows ({len(f)} fault cases of 8 h; 14 rows removed by DATA_GAP).\n- Operator log: {len(lg):,} setting changes ({(lg.source == 'EXPLORATION').mean() * 100:.1f} % EXPLORATION).\n- Lots: {m.fuel_lot.nunique()} lots; median length {lots.median() * 5 / 60:.1f} h.\n")
    L.append("## How it is generated (SPEC C6)\nDemand (6-11 MW) -> lot moisture/LHV -> fuel feed by feed-forward on last efficiency and a slowly learned LHV -> bed lag (10-20 min) -> latent eta = f(moisture, fouling, excess-air deviation from a hidden optimum, grate-air mismatch, fan derate, AR(1)) -> HTF temperatures from the heat balance with the property table -> measurements = truth + noise/bias/lag. Operators (OP-A/B/C) change FD, ID and grate commands with shift-dependent habits; 15 % of decisions are randomized EXPLORATION so action effects are identifiable in synthetic data (not identifiable from observational plant data).\n")
    L.append("## Headline statistics (normal block)\n| Measure | Result | Method |\n|---|---|---|")
    L.append(f"| Latent eta, STEADY | median {nt.eta_true[steady].median() * 100:.1f} %, 5-95 %: {nt.eta_true[steady].quantile(.05) * 100:.1f}..{nt.eta_true[steady].quantile(.95) * 100:.1f} % | truth column, SYNTHETIC |")
    L.append(f"| SFC (valid STEADY rows) | median {n.SFC_kg_GJ[steady & (n.quality_flag == 'OK')].median():.1f} kg/GJ | measured fuel / (3.6 x Q_out) |")
    L.append(f"| Hidden-optimum gap | mean best-action eta gain {nt.best_action_eta_gain_pp[steady].mean():.2f} pp, median {nt.best_action_eta_gain_pp[steady].median():.2f} pp | generator illustration, never a real saving |")
    L.append(f"| ELIGIBLE / DIAGNOSTIC_ONLY / NO_ADVICE | {elig.get('ELIGIBLE', 0) * 100:.1f} / {elig.get('DIAGNOSTIC_ONLY', 0) * 100:.1f} / {elig.get('NO_ADVICE', 0) * 100:.1f} % of rows | SPEC C7 rules, 12-step stable window |")
    L.append(f"| Top NO_ADVICE reasons | {', '.join(f'{k} {v}' for k, v in reasons.head(5).items())} | row counts |")
    L.append(f"| CO available | {n.co_available.mean() * 100:.1f} % of normal rows (days: 60 % exactly) | config |")
    L.append(f"| Truth balance closure | max absolute residual between Q_out from HTF side and eta x Q_in = {resid[0]:.4f} % | independent table integration |")
    L.append(f"| Weigh-belt vs volumetric | {(n.fuel_mass_basis == 'VOLUMETRIC').mean() * 100:.1f} % of normal rows volumetric | service episodes |")
    L.append(f"| Display records (stress) | {dis.verdict.value_counts().to_dict()} | units.reconcile_display |\n")
    L.append("## Fault cases\n| Case | Type | Injected rows | Expected detection |\n|---|---|---|---|")
    for _, r in f.iterrows():
        L.append(f"| {r.case_id} | {r.fault_type} | {r.injected_rows} | {r.expected_detection} |")
    L.append("\n## Extensions to SPEC C7 reason codes\nAdded LOW_O2 (O2 below floor) and HIGH_CO (CO above limit) because SPEC C7 names those conditions without codes. LIMITS_NOT_APPROVED is unused in synthetic mode.\n")
    L.append("## Figures\n- reports/figs/p1_trend_24h.png (" + day + ")\n- reports/figs/p1_histograms.png\n- reports/figs/p1_energy_balance_residuals.png\n")
    L.append("## Limits and known faults\n- Effects (O2 optimum, grate optimum, fouling, derate) are generator-defined (A12, A17); success on this data shows the method works under known ground truth, not that the same gain exists on a real heater.\n- Stress (seed 77) uses a shifted optimum, wider moisture, all-volumetric fuel and noisier sensors; site-style (seed 101) is configured but not generated in Phase 1.\n- fuel_rate_true_kgh, fuel_moisture (when lhv_known=0 is NaN) and the truth file must never be model inputs; true_synthetic_best_action is evaluation-only.\n- HTF setpoint, draft setpoint and pump status are constants in this build.\n- Eligibility is low by design (volumetric periods, unassayed lots, 60-min stable window); real eligibility is unknown.\n")
    (ROOT / "reports" / "synthetic_data_card.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    m, t, f, lg = load()
    day = fig_trend(m, t)
    fig_hist(m, t)
    resid = fig_resid(m, t)
    card(m, t, f, lg, day, resid)
    print(f"figures + card written; trend day {day}; max HX residual {resid[0]:.5f} %")


if __name__ == "__main__":
    main()
