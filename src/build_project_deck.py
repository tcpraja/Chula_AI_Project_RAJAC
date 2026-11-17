"""Build reports/Heater_C_Full_Project_Presentation.pptx: a 50-slide, submission-ready walk through the whole project (what was planned, the tools and why,
the AI concepts, the chemistry, the dashboard and how to use it, the pilot package). Every number is read or computed from project files and logged in
reports/project_deck_number_map.csv; screenshots and charts are generated from the real dashboard and data. SYNTHETIC data only; no company name or logo.
Run: python -m src.build_project_deck
"""
import importlib.metadata as md
import json
import re
from pathlib import Path
from types import SimpleNamespace

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from src import chem_advice, combustion as cb, guardrails as gd, mv_report as mv, optimize_view as ov
from src.build_final import Data, Ledger, admin_facts
from src.deck_kit import BLUE, G60, G90, GREEN, HEX, RED, WHITE, Deck, G10, diagram
from src.final_nums import numbers

ROOT = Path(__file__).resolve().parents[1]
REP, SHOT = ROOT / "reports", ROOT / "assets" / "screenshots"
FIG = REP / "figs" / "deck"
OUT = REP / "Heater_C_Full_Project_Presentation.pptx"
TOTAL = 50


# ---------------------------------------------------------------------- numbers (all sourced)
def extras(L, n):
    x = SimpleNamespace()
    f = L.f
    dic = pd.read_csv(REP / "03_data_dictionary.csv")
    x.n_dict = f("data-dictionary columns", len(dic), "{:.0f}", "reports/03_data_dictionary.csv")
    tmap = yaml.safe_load((ROOT / "config" / "tag_map_template.yaml").read_text(encoding="utf-8"))
    site = [e for e in tmap["columns"].values() if e["source"] == "site"]
    x.n_site_cols = f("tag-map site columns", len(site), "{:.0f}", "config/tag_map_template.yaml")
    x.n_critical = f("tag-map critical columns", sum(1 for e in site if e.get("critical")), "{:.0f}", "config/tag_map_template.yaml")
    x.n_pages = f("dashboard pages", len(re.findall(r"st\.Page\(", (ROOT / "app.py").read_text(encoding="utf-8"))), "{:.0f}", "app.py")
    x.n_codes = f("guardrail reason codes", len(gd.CODES), "{:.0f}", "src/guardrails.py CODES")
    cr = json.loads((ROOT / "data" / "clean" / "clean_report.json").read_text(encoding="utf-8"))
    x.n_raw, x.n_clean, x.n_rej = (f(k, cr[j], "{:,.0f}", "data/clean/clean_report.json") for k, j in (("raw rows", "n_raw"), ("clean rows", "n_clean"), ("rejected rows", "n_rejected")))
    x.lag = f("fuel-to-heat lag steps", cr["lag_steps"], "{:.0f}", "data/clean/clean_report.json")
    x.rej_frozen, x.rej_heat = f("rejected FROZEN_SENSOR", cr["reject_counts"]["FROZEN_SENSOR"], "{:.0f}", "data/clean/clean_report.json"), f("rejected HEAT_IMPLAUSIBLE", cr["reject_counts"]["HEAT_IMPLAUSIBLE"], "{:.0f}", "data/clean/clean_report.json")
    x.n_volumetric = f("volumetric-fuel rows", cr["flag_counts"]["volumetric_fuel"], "{:,.0f}", "data/clean/clean_report.json")
    eb = (REP / "energy_baseline.md").read_text(encoding="utf-8")
    x.r2 = f("baseline R2 train", float(re.search(r"R2 \(train\) \| ([\d.]+)", eb).group(1)), "{:.2f}", "reports/energy_baseline.md")
    x.mae_base = f("baseline MAE test kg/GJ", float(re.search(r"MAE train / test \| [\d.]+ / ([\d.]+)", eb).group(1)), "{:.2f}", "reports/energy_baseline.md")
    cl = (REP / "ai_critique_log.md").read_text(encoding="utf-8")
    x.n_findings = f("critic findings", int(re.search(r"Its (\d+) findings", cl).group(1)), "{:.0f}", "reports/ai_critique_log.md")
    x.n_genuine = f("genuine errors fixed", len(re.findall(r"^\d\. \*\*", cl.split("## Genuine errors found and fixed")[1].split("## Point-by-point")[0], re.M)), "{:.0f}", "reports/ai_critique_log.md")
    G = gd.load_limits()
    L_, O = G["limits"], G["optimizer"]
    x.fd_lo, x.fd_hi = f("FD range low", L_["fd_range_pct"][0], "{:.0f}", "config/guardrail_limits.yaml"), f("FD range high", L_["fd_range_pct"][1], "{:.0f}", "config/guardrail_limits.yaml")
    x.gr_lo, x.gr_hi = f("grate range low", L_["grate_range_pct"][0], "{:.0f}", "config/guardrail_limits.yaml"), f("grate range high", L_["grate_range_pct"][1], "{:.0f}", "config/guardrail_limits.yaml")
    x.step = f("max step % per axis", L_["max_step_fd_pct"], "{:.0f}", "config/guardrail_limits.yaml")
    x.o2_floor, x.co_lim = f("O2 floor %", L_["o2_floor_pct"], "{:.0f}", "config/guardrail_limits.yaml"), f("CO limit ppm", L_["co_limit_ppm"], "{:.0f}", "config/guardrail_limits.yaml")
    x.l1, x.l2, x.l3 = (f(k, O[k], "{:g}", "config/guardrail_limits.yaml") for k in ("lambda_fan_kg_gj_per_kw", "lambda_move_kg_gj_per_pct", "lambda_width"))
    x.n_cand = f("candidate moves in grid", len(O["grid_steps_fd"]) * len(O["grid_steps_grate"]), "{:.0f}", "config/guardrail_limits.yaml grid")
    x.n_boot = f("bootstrap draws (effect model)", O["n_boot"], "{:.0f}", "config/guardrail_limits.yaml")
    # chemistry on the example advised row (the one shown on the dashboard)
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv")
    d = d.merge(pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv")[["timestamp_local", "split"]], on="timestamp_local")
    recs = {json.loads(line)["timestamp"]: json.loads(line) for line in (ROOT / "data" / "advisory" / "advisory_records_test.jsonl").read_text(encoding="utf-8").splitlines()}
    ts = next(t for t, r in recs.items() if r["decision"] == "ADVICE")
    i = d.index[d.timestamp_local == ts][0]
    eff = joblib.load(ROOT / "models" / "effect_model.joblib")
    mois = chem_advice.lot_moisture(d, i)
    v = chem_advice.chem_view(d.loc[i], mois, recs[ts], eff, G)
    snap = ov.snapshot(d.loc[i], mois, recs[ts], eff, G, ov.stack_reference(d))
    src_row = f"example advised row {ts} (data/clean + advisory_records_test.jsonl)"
    c = v["current"]
    x.row_ts = ts
    x.lam, x.stoich = f("excess air lambda", c["lambda"], "{:.2f}", src_row), f("stoichiometric air kg/kg", c["stoich_air_kg_per_kg"], "{:.2f}", src_row)
    x.o2_now = f("flue O2 now %", d.at[i, "O2_pct_dry"], "{:.1f}", src_row)
    x.l_dry, x.l_vap, x.l_co, x.l_unb, x.l_rad = (f(f"loss {k}", c[k], "{:.1f}", src_row) for k in ("dry_flue_gas", "water_vapour", "CO", "unburnt_carbon", "radiation_other"))
    x.eta_chem, x.eta_hb = f("eta chemistry %", c["eta_indirect_pct"], "{:.1f}", src_row), f("eta heat balance %", v["eta_heat_balance"], "{:.1f}", src_row)
    x.o2_opt = f("best allowed O2 %", v["o2_opt"], "{:.1f}", src_row)
    x.d_chem, x.d_ridge = f("delta eta chemistry pts", v["deta_chem"], "{:+.2f}", src_row), f("delta eta ridge pp", v["deta_ridge"], "{:+.2f}", src_row)
    x.j = f("objective J", v["objective_J"], "{:+.2f}", src_row)
    x.eta_best = f("best reachable eta %", snap["eta_best"], "{:.1f}", src_row)
    x.gain = f("room to improve points", snap["eta_best"] - c["eta_indirect_pct"], "{:+.1f}", src_row)
    x.close = f("mass balance closure %", snap["mass"]["closure_pct"], "{:+.3f}", src_row)
    x.lev_o2 = f("lever O2 points", float(snap["levers"].set_index("Lever").loc["Combustion air (O2)", "Δη (points)"]), "{:.1f}", src_row)
    x.lev_stack = f("lever stack -10 K points", float(snap["levers"].set_index("Lever").loc["Stack temperature", "Δη (points)"]), "{:.1f}", src_row)
    x.snap, x.v, x.eff, x.d, x.recs = snap, v, eff, d, recs
    # Phase 8 evidence
    m = json.loads((REP / "monitoring" / "latest.json").read_text(encoding="utf-8"))
    x.dq, x.psi, x.psi_feat = f("monitor data quality %", m["data_quality_pct"], "{:.1f}", "reports/monitoring/latest.json"), f("monitor max PSI", m["psi_max_value"], "{:.2f}", "reports/monitoring/latest.json"), m["psi_worst_feature"]
    x.fa = f("false alerts per shift", m["false_alerts_per_shift"], "{:.1f}", "reports/monitoring/latest.json")
    mvj = json.loads((REP / "mv" / "mv_retrospective.json").read_text(encoding="utf-8"))
    x.aa, x.aa_lo, x.aa_hi = (f(k, v_, "{:+.2f}", "reports/mv/mv_retrospective.json") for k, v_ in (("A/A effect %", mvj["delta_pct"]), ("A/A CI low %", mvj["ci90_pct"][0]), ("A/A CI high %", mvj["ci90_pct"][1])))
    pr = mv.prepare(pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv"))
    bm, tm, _ = mv.windows(pr, "retrospective")
    y = pr.copy()
    y.loc[tm, "sfc"] = y.loc[tm, "sfc"] * 0.97
    r3 = mv.estimate(y, bm, tm, n_boot=200)
    s3 = "computed at build: mv_report.estimate with a known -3 % effect injected (200 draws)"
    x.inj, x.inj_lo, x.inj_hi = (f(k, v_, "{:+.2f}", s3) for k, v_ in (("recovered effect %", r3["delta_pct"]), ("recovered CI low %", r3["ci90_pct"][0]), ("recovered CI high %", r3["ci90_pct"][1])))
    x.mde = f("smallest resolvable effect % (half-width of A/A interval)", (mvj["ci90_pct"][1] - mvj["ci90_pct"][0]) / 2, "{:.1f}", "reports/mv/mv_retrospective.json")
    reg = json.loads((ROOT / "models" / "registry.json").read_text(encoding="utf-8"))
    x.champion = reg["champion"]
    x.ver = {p: md.version(p) for p in ("streamlit", "plotly", "pandas", "numpy", "scipy", "scikit-learn", "joblib", "pydantic", "PyYAML", "matplotlib", "python-pptx", "reportlab", "openpyxl", "pytest")}
    tests = pd.read_csv(REP / "final_numbers.csv").set_index("key")
    x.tests_by = {k[len("tests_"):-len("_passed")]: int(v) for k, v in tests["value"].items() if k.startswith("tests_test_") and k.endswith("_passed")}
    return x


# ---------------------------------------------------------------------- diagrams and charts
def make_figures(n, x, a):
    FIG.mkdir(parents=True, exist_ok=True)
    P = lambda k: FIG / f"{k}.png"
    diagram(P("process"), {
        "fuel": (0, 62, 21, 26, "Palm-kernel-shell\nfuel (belt feeder)", "amber"), "fur": (26, 55, 21, 40, "Travelling-grate\nfurnace\nFD air in, ID fan out", "lred"),
        "flue": (53, 62, 16, 26, "Flue gas:\nCO2, N2, O2,\nH2O, CO", "g25"), "eco": (75, 62, 15, 26, "Economizer\nand stack", "g25"),
        "htf": (24, 8, 20, 30, "HTF heater coil\n(thermic fluid)", "lblue"), "pet": (60, 8, 24, 30, "PET resin process\n(heat demand)", "lgreen")},
        [("fuel", "fur", "kg/h"), ("fur", "flue", ""), ("flue", "eco", ""), ("fur", "htf", "heat"), ("htf", "pet", "hot HTF"), ("pet", "htf", "return")], size=(7.6, 4.2), fs=10,
        notes="Efficiency question: how much fuel per GJ of useful HTF heat, and which air and grate settings waste it?")
    diagram(P("authority"), {
        "sis": (5, 74, 90, 20, "BMS / SIS / hardwired trips: safety authority (never touched)", "red"), "dcs": (5, 50, 90, 20, "DCS and control loops: control authority", "blue"),
        "op": (5, 26, 90, 20, "Operator and shift supervisor: decide, in the existing DCS, within signed limits", "green"), "ai": (5, 2, 90, 20, "AI advisory: reads exported data, suggests, never writes (read-only)", "amber")},
        [("ai", "op", "advice only")], size=(7.4, 4.3), fs=10)
    diagram(P("roadmap"), {f"p{i}": (1 + i * 10.9, 40, 10, 22, t, c) for i, (t, c) in enumerate([
        ("0\nScope", "lblue"), ("1\nSynthetic\ndata", "lblue"), ("2\nCleaning,\nbaseline", "lblue"), ("3\nForecast\nmodels", "lblue"), ("4\nGuardrails,\noptimizer", "lblue"),
        ("5\nDashboard", "lgreen"), ("6\nPilot plan,\neconomics", "lgreen"), ("7\nSubmission\nset", "lgreen"), ("8\nPilot\npackage", "amber")])},
        [(f"p{i}", f"p{i + 1}", "") for i in range(8)], size=(12.2, 2.7), fs=11, notes="Each phase ended with a packet, tests, a commit and a human approval gate.")
    diagram(P("generator"), {
        "dem": (1, 40, 12, 22, "Heat demand\n6-11 MW", "lblue"), "lot": (16, 40, 13, 22, "Fuel lots\nmoisture, LHV\n6-18 h", "amber"), "eta": (32, 40, 14, 22, "Latent efficiency\nmoisture, fouling,\nair, grate, fans", "lgreen"),
        "fuel": (49, 40, 14, 22, "Fuel kg/h =\nQ / (eta x LHV)", "lblue"), "htf": (66, 40, 12, 22, "HTF flow,\ntemperatures", "lblue"), "meas": (81, 40, 17, 22, "Measured = truth +\nnoise, bias, lag,\nfaults, gaps", "lred")},
        [("dem", "lot", ""), ("lot", "eta", ""), ("eta", "fuel", ""), ("fuel", "htf", ""), ("htf", "meas", "")], size=(12.2, 2.7), fs=11, notes="The generator knows the truth; the tool only ever sees the noisy measured side.")
    diagram(P("cleaning"), {f"c{i}": (1 + i * 12.4, 40, 11.2, 24, t, c) for i, (t, c) in enumerate([
        ("Raw\nexport", "g25"), ("Schema\nand units", "lblue"), ("Duplicates,\ngaps", "lblue"), ("Frozen\nsensors", "lblue"), ("Totalizer\nresets", "lblue"), ("Heat and fuel\nplausibility", "lblue"), ("Lag\nalignment", "lblue"), ("Clean\nframe", "lgreen")])},
        [(f"c{i}", f"c{i + 1}", "") for i in range(7)], size=(12.2, 2.6), fs=11, notes="Raw data is never modified, nothing is interpolated, LHV is never invented.")
    diagram(P("layers"), {
        "d": (1, 38, 17, 26, "Row from clean\nframe", "g25"), "l1": (23, 38, 19, 26, "Layer 1: data\nvalid? steady?\nfuel, LHV, flow", "lblue"), "l2": (47, 38, 19, 26, "Layer 2: limits,\ndraft, O2, CO,\ntrips, derate", "lblue"),
        "opt": (71, 38, 13, 26, "Optimizer:\n25 moves", "lgreen"), "a": (88, 66, 11, 24, "ADVICE", "green"), "n": (88, 36, 11, 24, "NO ADVICE\n+ reason", "red"), "o": (88, 6, 11, 24, "DIAGNOSTIC\nONLY", "amber")},
        [("d", "l1", ""), ("l1", "l2", ""), ("l2", "opt", ""), ("opt", "a", ""), ("opt", "n", ""), ("opt", "o", "")], size=(12.2, 3.0), fs=11, notes="Anything missing, stale, unapproved or out of range ends in NO ADVICE.")
    diagram(P("dataflow"), {
        "hist": (1, 60, 16, 28, "Historian / DCS", "g25"), "csv": (24, 60, 16, 28, "A person exports\na CSV file\n(no live link)", "amber"), "inc": (47, 60, 15, 28, "incoming/\n(read-only)", "lblue"),
        "cont": (47, 12, 33, 38, "Container, no network:\ncheck_mapping > ingest > clean >\nscore (shadow) > monitor", "lgreen"), "out": (84, 12, 15, 38, "data/ models/\nreports/\naudit log", "lblue"), "dash": (82, 62, 17, 26, "Dashboard\n127.0.0.1\n:8501", "blue")},
        [("hist", "csv", "export"), ("csv", "inc", ""), ("inc", "cont", ""), ("cont", "out", ""), ("out", "dash", "read")], size=(6.6, 3.0), fs=8.5,
        notes="Nothing flows back to the DCS, PLC, BMS or SIS: no OPC, Modbus or write code exists.")
    # split timeline from the real split file
    sp = pd.read_csv(ROOT / "data" / "holdout" / "split_keys.csv")["split"].value_counts()
    fig, ax = plt.subplots(figsize=(12.2, 1.9))
    left = 0
    for k, col in (("train", HEX["blue"]), ("val", HEX["green"]), ("test", HEX["red"])):
        ax.barh(0, sp[k], left=left, color=col)
        ax.text(left + sp[k] / 2, 0, f"{k}\n{sp[k]:,} rows", ha="center", va="center", color="white", fontsize=10)
        left += sp[k]
    ax.axis("off")
    ax.set_title("Chronological, lot-aware split (a fuel lot is never split; 3 rows purged at each boundary)", fontsize=10, loc="left", color=HEX["blue"])
    fig.tight_layout()
    fig.savefig(P("splits"), dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12.2, 1.9))
    for a0, b0, t, col in ((0, 2, "Weeks 1–2: approvals and data", HEX["lblue"]), (2, 4, "Weeks 3–4: read-only shadow", HEX["lgreen"]), (4, 5, "Week 5: advice\nif authorised", HEX["amber"]), (5, 6, "Week 6: M&V and\nGO / REVISE / STOP", HEX["lred"])):
        ax.barh(0, b0 - a0, left=a0, color=col, edgecolor="#555555")
        ax.text((a0 + b0) / 2, 0, t, ha="center", va="center", fontsize=12)
    ax.axvline(2, color=HEX["red"], lw=2)
    ax.text(2.05, 0.62, "stop check every week (6 stop conditions)", color=HEX["red"], fontsize=11)
    ax.set_xlim(0, 6)
    ax.set_ylim(-0.6, 0.9)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(P("timeline"), dpi=170)
    plt.close(fig)
    # loss stack, loss curve, waterfall from the example row
    v, snap = x.v, x.snap
    c = v["current"]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    names = ["dry_flue_gas", "water_vapour", "CO", "unburnt_carbon", "radiation_other"]
    labels = ["Dry flue gas", "Water vapour", "CO", "Unburnt C", "Radiation (assumed)"]
    cols = [HEX["blue"], "#4d7aa8", HEX["red"], "#e07a90", "#999999"]
    left = 0
    for k, lab, col in zip(names, labels, cols):
        ax.barh(0, c[k], left=left, color=col, label=f"{lab} {c[k]:.1f} %")
        left += c[k]
    ax.set_xlim(0, 16)
    ax.set_yticks([])
    ax.set_xlabel("loss, % of fuel LHV (example advised row)")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(P("loss_stack"), dpi=170)
    plt.close(fig)
    cv = v["curve"]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.plot(cv["O2_pct"], cv["dry_flue_gas_loss"], color=HEX["blue"], label="dry flue-gas loss")
    ax.plot(cv["O2_pct"], cv["total_loss"], color=HEX["green"], lw=2.5, label="stack + CO loss")
    ax.axvspan(cv["O2_pct"].min(), v["floor"], color=HEX["red"], alpha=0.12, label="below O2 floor")
    ax.axvline(21 - 21 / c["lambda"], color="#333", ls="--", label="now")
    if "option" in v:
        ax.axvline(v["o2_option"], color=HEX["green"], ls=":", label="proposed")
    ax.set_xlabel("flue-gas O2, % dry")
    ax.set_ylabel("loss, % of LHV")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(P("loss_curve"), dpi=170)
    plt.close(fig)
    mw = snap["loss_mw"]
    steps = [("Fuel heat in", snap["q_in"]), ("Dry flue gas", -mw["dry_flue_gas"]), ("Water vapour", -mw["water_vapour"]), ("CO + unburnt", -(mw["CO"] + mw["unburnt_carbon"])),
             ("Radiation", -mw["radiation_other"]), ("Unaccounted", -snap["unaccounted_mw"]), ("Useful to HTF", snap["q_out"])]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    run = 0.0
    for i, (lab, val) in enumerate(steps):
        if i in (0, len(steps) - 1):
            ax.bar(i, val, color=HEX["blue"])
            run = val if i == 0 else run
        else:
            ax.bar(i, val, bottom=run, color=HEX["red"])
            run += val
        ax.text(i, (val if i in (0, len(steps) - 1) else run) + 0.2, f"{abs(val):.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(steps)), [s[0] for s in steps], fontsize=8, rotation=20)
    ax.set_ylabel("MW")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(P("waterfall"), dpi=170)
    plt.close(fig)
    # AI vs rule bars from scenario_comparison via the shared figure; models chart reuse final f3
    return P


# ---------------------------------------------------------------------- the deck
def build():
    D, L = Data(), Ledger()
    n = numbers(D, L)
    a = admin_facts()
    x = extras(L, n)
    P = make_figures(n, x, a)
    FF = ROOT / "final" / "figs"
    S = lambda k: SHOT / k
    deck = Deck(TOTAL, f"Heater C AI decision support  ·  SYNTHETIC DATA  ·  PET Resin Plant P (anonymized)  ·  {a['name']}, {a['id']}")
    crop_main = (300, 100, 1500, 1330)

    # 1 -------------------------------------------------------------------
    s = deck.slide("Full project presentation", "Heater C: AI decision support for a biomass thermic-fluid heater", "Full walk-through of the project for a manager or committee: problem, plan, tools, AI concepts, chemistry, dashboard and pilot package. All data are synthetic.")
    deck.text(s, 0.55, 1.7, 7.2, 3.5, ["From idea to a pilot-ready, read-only advisory tool", f"{a['name']}  ·  ID {a['id']}", f"{a['course']}", "Organization: PET Resin Plant P (anonymized)", f"Deadline {a['due']}",
                                       "All numbers: SYNTHETIC unless labelled (MEASURED-IN-PROTOTYPE, OWN-ESTIMATE, ASSUMED, PUBLISHED)"], 17, G90, bullets=False)
    deck.image(s, S("screen_7_optimize.png"), 7.9, 1.55, 4.9, 5.3, crop=(300, 70, 1500, 1020))
    deck.callout(s, 0.55, 5.6, 7.2, 1.2, "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION\nDecision support only: humans decide; BMS / SIS / trips / DCS stay in charge.", RED, WHITE, 14, True)

    # 2 -------------------------------------------------------------------
    s = deck.slide("Full project presentation", "How this deck is organised: 50 slides in 7 parts", "Agenda. The deck is the long version; the five-slide talk is in final/.")
    deck.table(s, [["Part", "Slides", "What you will see"], ["A  Problem and context", "3–8", "Plant, problem, baseline, scope, safety principle"], ["B  Plan, tools, rules", "9–14", "Eight phases, rules, every tool (why, how, what), how AI help was checked"],
                   ["C  Data and engineering", "15–22", "Synthetic data, cleaning, heat balance, units, data gates, baseline"], ["D  AI concepts and results", "23–32", "Concept map, forecast, leakage, models, uncertainty, optimizer, guardrails, AI vs rule"],
                   ["E  Chemistry", "33–36", "Combustion, loss balance, efficiency trade-off, mass and heat balance"], ["F  Dashboard and how to use it", "37–45", "Pages, start-up steps, every input, screenshots with reading guide"],
                   ["G  Pilot and deployment", "46–50", "People and risks, pilot, energy and money, pilot package, request and stop"]], 0.55, 1.7, 12.2, [3.2, 1.2, 7.8], 14, 0.55, 5.0)

    # 3 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", "Answer first: a safe read-only advisor is worth a pilot, but no saving is proven", "Executive summary: the evidence supports preparation and a shadow pilot, not a savings claim.")
    deck.cards(s, [("What we built", [f"Synthetic heater data ({n.rows_total} rows, {n.lots} fuel lots)", "Forecast, guardrails, optimizer, chemistry", f"{x.n_pages}-page dashboard, pilot package"]),
                   ("What we found", [f"Linear model {n.mae_L} kg/h vs boosted trees {n.mae_C0}: simple wins", f"AI move ranking {n.ai_hit} % vs rule {n.rule_hit} %: not clearly better", f"Only {n.elig} % of rows pass the data gates"]),
                   ("What it means", [f"Base case net {n.net_base} thousand THB/yr: no payback", f"Needs {n.be_base} % fuel saving; simulated {n.sim_base} %", "Recommendation: REVISE; approve preparation and a read-only shadow pilot"])], 1.65, 3.3, 3, 13)
    deck.callout(s, 0.55, 5.2, 12.2, 1.5, f"Request: a {n.weeks}-week read-only pilot on one heater. Go = {n.n_targets} of {n.n_targets} targets met on measured data and 0 of {n.n_stops} stop conditions fired. "
                 f"Fictional cost range {n.one_opt}–{n.one_pess} million THB one-time. No saving is claimed.", G10, BLUE, 14, True)

    # 4 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", "The plant: a biomass heater heats thermic fluid for a PET resin process", "Qualitative equipment list only; the real P&ID, HMI and interlock documents were never read by the tool.")
    deck.image(s, P("process"), 0.55, 1.6, 7.6, 4.2)
    deck.text(s, 8.4, 1.65, 4.4, 4.6, ["One palm-kernel-shell grate furnace, FD and ID fans, economizer, soot-blowing, ash removal", "Heat goes into a hot thermic-fluid (HTF) loop that feeds the PET process",
                                       "Known issues: fuel above design, operator-dependent air and grate settings, rare LHV tests, ageing fans, display totals that may not reconcile", "Not measured: CO (often), airflow, per-lot LHV, online moisture"], 14)
    deck.callout(s, 0.55, 6.0, 12.2, 0.85, "Source: qualitative summary in docs/SPEC.md section C1. Originals (midterm, P&ID, interlock document, HMI) are confidential and were not read.", G10, G90, 12)

    # 5 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", "The problem: fuel use per unit of useful heat may be higher than it needs to be", "Specific, testable question; the midterm problem is kept.")
    deck.cards(s, [("The question", ["For a stable, trusted window, can the tool spot avoidable high fuel use and suggest a small, safe air or grate move better than a simple rule?"]),
                   ("Specific, not vague", ["Not an 'AI platform'. One heater, one advisory screen, small bounded moves, a human decision, a six-week read-only pilot."]),
                   ("Measure", ["SFC = kg fuel per GJ of useful HTF heat (as-fired LHV basis)", "Efficiency = useful heat / fuel LHV heat"])], 1.7, 3.4, 3, 14)
    deck.callout(s, 0.55, 5.4, 12.2, 1.2, "Same problem as the midterm (no change of topic). The company baseline still requires validation: the numbers here are from a synthetic prototype.", G10, G90, 14, True)

    # 6 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", f"Baseline (synthetic): {n.sfc_med} kg fuel per GJ, and only {n.elig} % of rows are usable for advice", "Baseline table in the course format: Measure, Result, Method. The company baseline still requires validation.")
    deck.image(s, FF / "f1_baseline.png", 0.55, 1.6, 6.3, 3.4)
    deck.table(s, [["Measure", "Result", "Method"], ["Baseline SFC", f"{n.sfc_med} kg/GJ (P25–P75 {n.sfc_p25}–{n.sfc_p75})", f"median of {n.sfc_n} eligible CALCULATED windows, training period"],
                   ["Eligible rows", f"{n.elig} % (+{n.diag_share} % diagnostic only)", f"guardrail layers 1–2 on {n.rows_total} rows"], ["Replay (test) period", f"{n.test_rows} rows ({n.test_share} %)", "held-out later lots, never used to train"]],
               7.0, 1.7, 5.8, [1.7, 2.3, 2.6], 11, 0.4, 3.2)
    deck.callout(s, 0.55, 5.3, 12.2, 1.4, "Company baseline: REQUIRES VALIDATION (measured fuel mass, lot-assayed LHV, a defined stable window). Pilot target T1 is 60 % trusted windows, so real data could fail it.", RED, WHITE, 14, True)

    # 7 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", "Scope: what is in, what is out, and the two levels of this work", "Charter summary: Level 1 is what this repository does; Level 2 needs approvals and company data.")
    deck.table(s, [["", "Level 1: synthetic demonstrator (this work)", "Level 2: read-only pilot (needs approvals)"], ["Data", "Generated here, SYN_ aliases, labelled SYNTHETIC", "Historian CSV export, read-only, after approvals"],
                   ["Output banner", "SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION", "ADVISORY ONLY — OPERATOR DECIDES"], ["Claims", "Method works on known truth; gains are illustrations, never savings", "An effect only if the 90 % CI excludes 0"],
                   ["Gate", "Phase approvals in this repository", "Sponsor, OT, EHS, OEM, MOC approvals"]], 0.55, 1.65, 12.2, [1.5, 5.4, 5.3], 12, 0.5, 2.9)
    deck.cards(s, [("In scope", ["One heater (Heater C), next-interval fuel forecast, ranked simulated options"]), ("Out of scope", ["Any plant control, other heaters, plantwide optimisation, predictive maintenance"]), ("Never", ["Real HMI, P&ID, interlock or operating data in this tool; network or LLM at runtime"])], 4.7, 2.0, 3, 12)

    # 8 -------------------------------------------------------------------
    s = deck.slide("A  Problem and context", "Safety principle: advice flows to people; nothing flows back to the plant", "Authority diagram: the advisory is the lowest layer and read-only.")
    deck.image(s, P("authority"), 0.55, 1.6, 7.4, 4.3)
    deck.text(s, 8.2, 1.7, 4.6, 4.5, ["No DCS, PLC, OPC, Modbus or setpoint-write code exists (tested)", "Fail-safe output is NO ADVICE with reason codes", "Limits are arbitrary synthetic envelopes; a placeholder REQUIRES_OEM_APPROVAL forces NO ADVICE",
                                      "Real mode shows ADVISORY ONLY — OPERATOR DECIDES; ADVISORY is refused until limits and approvals are complete", "Every recommendation says 'human review required'"], 14)

    # 9 -------------------------------------------------------------------
    s = deck.slide("B  Plan, tools, rules", "The plan: eight phases, each ending in tests, a packet and an approval gate", "Roadmap. Blue = engineering, green = product and pilot, amber = deployable package.")
    deck.image(s, P("roadmap"), 0.55, 1.65, 12.2, 2.7)
    deck.text(s, 0.55, 4.6, 12.2, 2.3, ["Phase packet (≤ 60 lines): implemented, files, provenance, formulas with a worked example, evidence, checklist PASS/FAIL/NEEDS DATA, known faults, decision needed",
                                        "Rule: finish → packet → wait for approval; always stop for installs, network, company data and irreversible actions",
                                        f"Every phase is a git commit; tags: v1.0-submission (course set) and v0.9-pilot-package; {n.tests_passed} tests in the last full build"], 14)

    # 10 ------------------------------------------------------------------
    s = deck.slide("B  Plan, tools, rules", "What each phase delivered, with its evidence", "Phase deliverables.")
    deck.table(s, [["Phase", "Delivered", "Evidence"], ["0 Scope", "Charter, tag inventory, options, RACI, assumptions register", "20 assumptions, qualitative sources only"], ["1 Data", "Synthetic generator, HTF table, units, dictionary", f"{n.rows_total} rows, {x.n_dict} documented columns"],
                   ["2 Clean", "Cleaning, heat balance with uncertainty, baseline", f"{x.n_clean} clean rows, {x.n_rej} rejected, lag {x.lag} steps"], ["3 Models", "7 candidate forecasts, leakage tests, critic review", f"linear L {n.mae_L} kg/h chosen"],
                   ["4 Advice", "Guardrails, optimizer, AI vs rule", f"{n.adv} ADVICE rows of {n.test_rows} replayed"], ["5 App", f"{x.n_pages}-page dashboard, what-if, operator log, shadow replay", "deterministic replay file"],
                   ["6 Pilot", "Plan, scorecard, risks, SOP, economics, privacy", f"AI {n.kwh6_base} kWh over {n.weeks} weeks"], ["7 Submit", "Proposal, appendix, 5-slide deck, Q&A, rubric", "2-page proposal, source map"], ["8 Package", "Adapters, monitor, retrain, audit, M&V, Docker", f"{n.tests_passed} tests passing"]],
               0.55, 1.6, 12.2, [1.2, 6.3, 4.7], 11, 0.4, 5.3)

    # 11 ------------------------------------------------------------------
    s = deck.slide("B  Plan, tools, rules", "Working rules that shaped every decision", "The ten non-negotiable rules from CLAUDE.md, summarised.")
    deck.cards(s, [("Data and claims", ["Synthetic only inside the tool", "Every number labelled: SYNTHETIC, MEASURED-IN-PROTOTYPE, OWN-ESTIMATE, PUBLISHED", "No fabricated results; synthetic gains are never savings"]),
                   ("Safety", ["No plant control, no write path", "Fail-safe NO ADVICE; limits only from a signed site config", "Invalid heat, LHV or fuel → UNVERIFIED PROXY or NO ADVICE"]),
                   ("Method", ["No leakage: chronological, lot-aware, trailing windows only", "Thermic fluid cp from the property table, never water", "Phase gates with packets; stop for installs and network"])], 1.65, 4.2, 3, 13)
    deck.callout(s, 0.55, 6.0, 12.2, 0.85, "No network, no external API and no LLM at runtime; no real company names or logos in outputs.", G10, G90, 13, True)

    # 12 ------------------------------------------------------------------
    v = x.ver
    s = deck.slide("B  Plan, tools, rules", "Tools used (1 of 2): data and machine-learning stack, with why, how and what", "Versions are read from the environment at build time.")
    deck.table(s, [["Tool (version)", "Why this tool", "How it was used", "What it produced"],
                   [f"Python 3.11, pandas {v['pandas']}, numpy {v['numpy']}", "Standard, transparent, auditable", "Generator, cleaning, features, reports", "All data and tables"],
                   [f"scikit-learn {v['scikit-learn']}", "Proven linear and tree models, simple API", "OLS-style models, HistGradientBoosting, ridge", "Forecast and effect models"],
                   [f"scipy {v['scipy']}", "Statistics and optimisation helpers", "Distances, quantiles, bootstrap support", "OOD detector, intervals"],
                   [f"joblib {v['joblib']}", "Safe model persistence", "Saved models and the registry files", "models/*.joblib"],
                   [f"pydantic {v['pydantic']}", "Schema validation with clear errors", "Raw-row schema in cleaning", "Rejected-row reasons"],
                   [f"PyYAML {v['PyYAML']}", "Human-readable configuration", "Limits, tag map, site config, thresholds", "config/*.yaml"],
                   [f"pytest {v['pytest']}", "Repeatable evidence", f"{n.tests_passed} tests incl. leakage and gates", "Pass/fail on every phase"]], 0.55, 1.6, 12.2, [2.6, 3.0, 3.5, 3.1], 11, 0.42, 5.3)

    # 13 ------------------------------------------------------------------
    s = deck.slide("B  Plan, tools, rules", "Tools used (2 of 2): app, documents, operations and AI assistance", "Docker image has not been built here: the build downloads packages (network).")
    deck.table(s, [["Tool (version)", "Why this tool", "How it was used", "What it produced"],
                   [f"Streamlit {v['streamlit']}", "Fast, local, no web server code", "7-page dashboard on 127.0.0.1", "app.py, src/dashboard/"],
                   [f"Plotly {v['plotly']}, matplotlib {v['matplotlib']}", "Interactive and static charts", "Dashboard charts; deck figures", "Charts with provenance captions"],
                   ["SQLite (Python standard library)", "Local, zero-install, tamper-evident with hashes", "Operator log and audit log", "data/operator_log.db, audit_log.db"],
                   [f"ReportLab {v['reportlab']}, python-pptx {v['python-pptx']}, openpyxl {v['openpyxl']}", "Reproducible documents", "PDFs, decks, the cost workbook (live formulas)", "final/, reports/"],
                   ["Docker + compose", "Same image, no outbound network", "Dockerfile, internal network, read-only container", "Packaging (not built yet)"],
                   ["Git", "History and tags", "Commit per phase, tags", "v1.0-submission, v0.9-pilot-package"],
                   ["Claude Code (AI assistant), headless Edge", "Speed with human review; real screenshots", "Wrote code and documents; captured screenshots", "Every output checked by tests or by eye"]], 0.55, 1.6, 12.2, [2.9, 3.0, 3.4, 2.9], 11, 0.42, 5.3)

    # 14 ------------------------------------------------------------------
    s = deck.slide("B  Plan, tools, rules", f"How AI help was used and checked: a critic found {x.n_genuine} real errors out of {x.n_findings} findings", "AI use, with real errors and corrections.")
    deck.cards(s, [("Where AI helped", ["Wrote generator, pipeline, models, dashboard and documents under written rules", "Separate critic agent attacked assumptions, leakage and units", "Headless browser took the screenshots"]),
                   ("How it was checked", [f"{n.tests_passed} automated tests, including leakage canaries", "Each phase packet reviewed before the next", "Numbers in final documents come from CSV files and a source map"]),
                   ("Errors found and fixed", [f"Unfair reference: the linear model looked {n.L_vs_P} % better than last value but is {n.L_vs_P2} % better than the fair reference", "Selection on the test set; calibration reuse; fragile leakage canary", "Dashboard defects found on screenshots"])], 1.65, 4.2, 3, 12)
    deck.callout(s, 0.55, 6.0, 12.2, 0.85, "I remain responsible for every claim, number and source. Source log: final/source_and_AI_error_log.md.", G10, G90, 13, True)

    # 15 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", "Why synthetic data, and what it can and cannot prove", "Synthetic data are the only data this tool may read.")
    deck.cards(s, [("Why", ["Real plant data may not be read by this tool (confidentiality)", "Known truth lets us test whether the method works and the guardrails behave"]),
                   ("What it can show", ["Method correctness, leakage control, fail-safe behaviour", "How the pipeline copes with faults, gaps, unit slips, missing sensors"]),
                   ("What it cannot show", ["Real savings", "Real confounding: operators react to load and fuel; the synthetic effects are identifiable only because settings include random exploration"])], 1.7, 3.7, 3, 13)
    deck.callout(s, 0.55, 5.6, 12.2, 1.1, "So every gain is a generator illustration. Level 2 (a read-only pilot with measured fuel mass and assayed LHV) is the only way to a savings claim.", RED, WHITE, 14, True)

    # 16 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", "The synthetic generator: physics first, then measurement noise and faults", "Generator design from SPEC section C6.")
    deck.image(s, P("generator"), 0.55, 1.6, 12.2, 2.7)
    deck.table(s, [["Seed", "Profile", "Use"], ["42", f"main, 60 days, {n.rows_total} rows", "training, validation, test"], ["77", "stress", "robustness checks"], ["101", "site_style", "adapter and pilot-package dry runs"]], 0.55, 4.5, 5.6, [0.8, 2.6, 2.6], 11, 0.38, 2.2)
    deck.text(s, 6.4, 4.5, 6.4, 2.4, ["Events: start-up, ramps, steady, soot-blow, lot change, feeder stop, fan derate, poor air, frozen sensor, CO missing, gaps, totalizer reset, high or low flow, adverse draft, trips", "Settings include a random exploration part so effects are identifiable (not true of real plant data)"], 12)

    # 17 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", f"Data dictionary and tags: {x.n_dict} documented columns, {x.n_site_cols} that a site could supply", "Every column has a group, unit, role and provenance; tag names are SYN_ aliases.")
    deck.table(s, [["Group", "Examples", "Role in the tool"], ["HTF", "flow, inlet and outlet temperature, set point", "heat balance (critical)"], ["Fuel", "belt rate, totalizer, lot moisture, lab LHV", "SFC and efficiency (critical rate)"],
                   ["Air and fans", "FD, ID, grate commands; fan power", "action space; commands are not airflow"], ["Combustion", "O2, CO, furnace, flue, stack temperature", "chemistry and guardrails; missing = DIAGNOSTIC ONLY"],
                   ["Draft and safety", "draft Pa, interlock, alarm code", "hard guardrails (critical)"], ["Truth and labels", "true efficiency, best action", "evaluation only, never a model input"]], 0.55, 1.65, 12.2, [2.0, 5.2, 5.0], 12, 0.5, 3.8)
    deck.callout(s, 0.55, 5.7, 12.2, 1.0, f"Tag map template: {x.n_critical} critical site columns must be mapped or the checker refuses; the site must mark every column available or unavailable.", G10, G90, 13, True)

    # 18 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", f"Cleaning: {x.n_raw} raw rows become {x.n_clean} clean rows; nothing is filled or invented", "Cleaning pipeline.")
    deck.image(s, P("cleaning"), 0.55, 1.6, 12.2, 2.6)
    deck.table(s, [["Check", "Result on the main synthetic run"], ["Frozen sensors rejected", f"{x.rej_frozen} rows"], ["Heat implausible rejected", f"{x.rej_heat} rows"], ["Fuel-to-heat lag estimated", f"{x.lag} steps (10 min)"], ["Volumetric (less trusted) fuel rows", f"{x.n_volumetric}"]], 0.55, 4.4, 6.2, [3.2, 3.0], 12, 0.42, 2.5)
    deck.text(s, 7.0, 4.4, 5.8, 2.5, ["Raw data is never modified", "Missing LHV stays missing: an interval, never a point value", "Unit slips (mmWC, Mkcal/h, kcal) are flagged"], 13)

    # 19 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", "Heat and energy balance: the formulas behind every efficiency and SFC", "Formulas from SPEC C3 with a worked example (synthetic).")
    deck.table(s, [["Quantity", "Formula"], ["HTF mass flow", "m = V / 3600 × ρ(T_mean)"], ["Useful heat", "Q_out = m × cp(T_mean) × (T_out − T_in)"], ["Fuel heat", "Q_in = m_fuel × LHV (as fired)"], ["Efficiency", "η = 100 × Q_out / Q_in"], ["SFC", "SFC [kg/GJ] = 1000 / (η × LHV [MJ/kg])"],
                   ["Energy of a fuel change", "kWh = Δfuel_kg × LHV ÷ 3.6"]], 0.55, 1.65, 7.0, [2.2, 4.8], 13, 0.5, 3.8)
    spec = re.sub(r"\s+", " ", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
    worked = re.search(r"Worked \(SYNTHETIC\): (.*?) ASME", spec).group(1)
    deck.callout(s, 7.8, 1.65, 5.0, 3.8, "Worked example (SYNTHETIC, from the spec):\n" + worked, G10, G90, 15)
    deck.callout(s, 0.55, 5.6, 12.2, 1.1, "The thermic fluid never uses water cp (4.186); cp and density come from one property table and are never extrapolated.", RED, WHITE, 13, True)

    # 20 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", "Units and conversions are built into the adapter, not left to chance", "Unit conversion table.")
    deck.table(s, [["Site unit", "Internal unit", "Conversion"], ["mmWC (draft, dP)", "Pa", "× 9.80665"], ["Mkcal/h (heat)", "MW", "× 1.16222"], ["kg/s (fuel)", "kg/h", "× 3600"], ["kg/day (fuel)", "kg/h", "÷ 24"], ["t (totalizer)", "kg", "× 1000"], ["m³/s (flow)", "m³/h", "× 3600"]], 0.55, 1.65, 6.4, [2.4, 2.0, 2.0], 13, 0.5, 3.8)
    deck.text(s, 7.2, 1.7, 5.6, 4.5, ["Conversions live in one module and are tested by a round trip on a site-style export (exact to 1e-12)", "Unit slips are detected: reported heat compared with computed heat for the usual factors",
                                      "Display totals (kg/s × 86,400 vs kg/day) are reconciled; one contradictory record is rejected"], 14)

    # 21 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", f"Data gates: only {n.elig} % of rows are eligible, and that is the point", "Layer 1 and layer 2 checks.")
    deck.image(s, P("layers"), 0.55, 1.6, 12.2, 3.0)
    deck.text(s, 0.55, 4.8, 12.2, 2.0, [f"On the replayed period: ADVICE {n.adv}, NO ADVICE {n.noadv}, DIAGNOSTIC ONLY {n.diag} of {n.test_rows} rows", f"{x.n_codes} reason codes explain every refusal (for example TRANSIENT, NO_CO, LOW_FUEL_CONF, UNSAFE_DRAFT, OOD)",
                                        "A stable window needs 60 minutes of contiguous, unblocked rows"], 14)

    # 22 ------------------------------------------------------------------
    s = deck.slide("C  Data and engineering", f"Energy baseline: SFC follows load and moisture (R² {x.r2}, test MAE {x.mae_base} kg/GJ)", "Baseline OLS with lot-cluster bootstrap CIs, and the rule comparator.")
    deck.image(s, REP / "figs" / "p2_sfc_vs_load.png", 0.55, 1.6, 6.2, 4.4)
    deck.text(s, 7.0, 1.7, 5.8, 4.5, ["Model: SFC = b0 + b1 (load − 8.5) + b2 (load − 8.5)² + b3 (moisture − 17)", "Fitted on eligible windows with lab moisture; confidence intervals by lot-cluster bootstrap because rows inside a lot are autocorrelated",
                                      "Learned from data, not the 85 % design value", "Rule comparator: alert if window SFC exceeds the trailing 7-day P75 in the same load band"], 14)
    deck.callout(s, 0.55, 6.15, 12.2, 0.75, "All numbers SYNTHETIC. The baseline shows moisture and load matter; it is not a plant claim.", G10, G90, 13)

    # 23 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", "AI concepts used, in plain words, with where and why", "Concept map. Several parts are deliberately not machine learning.")
    deck.table(s, [["Concept", "Plain explanation", "Where it is used", "Why chosen"],
                   ["Supervised regression", "Learn a number from examples", "Next-15-min fuel forecast", "Simple, explainable"], ["Honest baselines", "Compare with trivial methods", "Persistence, repeat-feed, rule, 2-variable regression", "A model must beat these"],
                   ["Boosted trees", "Many small trees added up", "Candidate forecast C0, C", "Tested; no better than linear"], ["Ridge + bootstrap", "Stable linear fit with uncertainty", "Action-effect model", "Interval from lot resampling"],
                   ["Conformal prediction", "Intervals from past errors", "90 % forecast interval", "Few assumptions"], ["OOD detection", "Is this input like the training data?", "Mahalanobis distance gate", "Refuse unfamiliar states"],
                   ["Physics models", "Mass and energy balance, stoichiometry", "Efficiency, chemistry, levers", "Not ML; explains why"], ["Rule-based guardrails", "Hard if-then checks", "13+ reason codes", "Fail-safe"],
                   ["Constrained optimisation", "Pick the best allowed option", "25-move grid, weighted objective", "Transparent"], ["Drift monitoring", "Has the world changed?", "PSI, weekly MAE", "Trigger NO ADVICE"], ["Human in the loop", "A person decides", "Advice only, decision log", "Safety, accountability"]],
               0.55, 1.55, 12.2, [2.1, 3.3, 3.6, 3.2], 10, 0.34, 5.4)

    # 24 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", "Forecast task: predict the next 15 minutes of fuel, using only what is known now", "Target and features; leakage-free by design.")
    deck.cards(s, [("Target", ["y = mean fuel rate over t+1, t+2, t+3 (next 15 minutes)", "Population: eligible stable rows with all three future rows present"]),
                   ("Inputs at time t", ["Demand (heat, lags)", "Fuel lags 1–3 (not fuel at t)", "Lot moisture and LHV (lab only), O2, CO", "FD, ID, grate, temperatures, draft, ambient", "Minutes since soot-blow and lot change"]),
                   ("Never an input", ["Q_in, η, SFC in any form", "Fuel at t, totalizer, reported display values", "Anything named true_*, labels, scenario or fault flags"])], 1.7, 4.2, 3, 13)

    # 25 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", "No leakage: chronological, lot-aware splits and four automatic leakage tests", "Splits and tests.")
    deck.image(s, P("splits"), 0.55, 1.6, 12.2, 1.9)
    deck.table(s, [["Leakage test", "What it proves"], ["Shuffled target", "A model on shuffled targets has no skill"], ["Future feature canary", "A deliberately added future feature is caught (must lift R² by at least 0.04)"], ["Truncation", "Features at t are unchanged when later rows are deleted or corrupted"],
                   ["Forbidden columns", "No truth, label, SFC, η or Q_in column reaches the model"]], 0.55, 3.8, 12.2, [3.2, 9.0], 12, 0.5, 2.9)

    # 26 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", "Seven candidate forecasts, from trivial to machine learning", "Why each candidate exists.")
    deck.table(s, [["Model", "What it is", "Why it is in the comparison"], ["P", "Repeat the last fuel value (persistence)", "The obvious naive reference"], ["P2", "Repeat the current feed (feeder speed × capacity)", "The fair reference: models also see the feed"],
                   ["A", "Physics: Q_out ÷ (η_base × LHV)", "Does physics alone suffice?"], ["B", "OLS on load and moisture (the simple regression)", "Pilot target T4 compares with this"],
                   ["L", "Linear model on all trailing features", "Simplest model with the same information"], ["C0 / C", "Boosted trees (without / with settings)", "Does machine learning add anything?"]], 0.55, 1.65, 12.2, [1.4, 5.6, 5.2], 13, 0.55, 4.2)
    deck.callout(s, 0.55, 5.7, 12.2, 1.0, "Selection rule fixed before training: the simplest safe candidate wins unless a more complex one is at least 10 % better; score alone never selects.", G10, BLUE, 13, True)

    # 27 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", f"Result: linear model {n.mae_L} kg/h matches boosted trees {n.mae_C0}; simple wins", "Forecast results on held-out later lots.")
    deck.image(s, FF / "f3_results.png", 0.55, 1.55, 7.8, 3.5)
    deck.table(s, [["Model", "MAE kg/h"], ["Repeat last value (P)", n.mae_P], ["Repeat current feed (P2)", n.mae_P2], ["2-variable regression (B)", n.mae_B], ["Linear, all features (L, chosen)", n.mae_L], ["Boosted trees (C0)", n.mae_C0]], 8.6, 1.65, 4.2, [3.0, 1.2], 11, 0.4, 3.0)
    deck.text(s, 0.55, 5.2, 12.2, 1.7, [f"Linear is {n.L_vs_B} % better than the 2-variable regression and {n.L_vs_P2} % better than repeating the current feed; boosting is {n.C0_vs_L} % worse than linear", f"95 % CI for L: {n.ci_L} kg/h; 90 % interval covers {n.cov_L} % of rows",
                                        "Gain came from using more features (such as the current feed), not from model complexity"], 13)

    # 28 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", f"One real AI error: a weak reference made the model look {n.L_vs_P} % better; the fair gain is {n.L_vs_P2} %", "Critic review, failure and fix (from ai_critique_log.md).")
    deck.cards(s, [("What went wrong", ["First comparison used last fuel value as the reference", f"The linear model looked {n.L_vs_P} % better", "But the models also see the current feed"]),
                   ("How it was found", [f"A critic agent with a fresh context reviewed the model card and results ({x.n_findings} findings, {x.n_genuine} real errors)", "I verified it with code before changing anything"]),
                   ("The fix", [f"Added the fair reference P2: gain is {n.L_vs_P2} %", "Selection moved to validation rows only; calibration split from tuning", "Leakage canary strengthened"])], 1.65, 4.1, 3, 13)
    deck.callout(s, 0.55, 5.95, 12.2, 0.9, "Lesson: always compare with the strongest simple method, and let someone try to break the result.", G10, BLUE, 14, True)

    # 29 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", "Uncertainty: every forecast carries a 90 % interval built from past errors (conformal prediction)", "Split conformal prediction in plain words.")
    deck.image(s, REP / "figs" / "p2_uncertainty_day.png", 0.55, 1.6, 6.4, 4.4)
    deck.text(s, 7.2, 1.7, 5.6, 4.6, ["Idea: look at the absolute errors the model made on validation rows it did not train on; take the 90th percentile as the half-width", "No distribution assumption needed", f"Test coverage for the chosen model: {n.cov_L} % (target 90 %)",
                                      "Known limit: the same half-width everywhere; the coefficient-bootstrap intervals of the effect model cover coefficient uncertainty only, not model error"], 13)

    # 30 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", f"Optimizer: {x.n_cand} small FD × grate moves, scored by one transparent objective", "Action-effect model and optimizer.")
    deck.callout(s, 0.55, 1.65, 12.2, 1.0, "J = ΔSFC + λ1 × Δfan power + λ2 × |move| + λ3 × interval width      (lower is better; hold = 0)", BLUE, WHITE, 16, True)
    deck.table(s, [["Weight", "Value", "Meaning"], ["λ1", f"{x.l1} kg/GJ per kW", "penalise more FD fan power"], ["λ2", f"{x.l2} per % of move", "prefer small moves"], ["λ3", f"{x.l3} per kg/GJ", "penalise uncertain options"]], 0.55, 2.9, 6.4, [0.9, 2.5, 3.0], 12, 0.45, 2.2)
    deck.text(s, 7.2, 2.9, 5.6, 3.9, [f"Effect model: ridge regression of efficiency on O2, grate, load, moisture, fouling; {x.n_boot} lot-bootstraps give the interval", "O2 after a move from stoichiometry: λ_new = λ × FD_new / FD",
                                      f"Moves up to ±{x.step} % per axis; candidates failing O2 floor, CO, draft, range or OOD are dropped", "ADVICE only if the 95th-percentile ΔSFC is below 0 and the interval is narrow enough"], 13)
    deck.callout(s, 0.55, 5.4, 6.4, 1.4, "Weights are OWN-ESTIMATE, set before looking at results, not tuned. The effect model is associational, not proven causal.", G10, G90, 12)

    # 31 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", f"Guardrails: {x.n_codes} reason codes make NO ADVICE the default", "Guardrails and fail-safe output.")
    deck.table(s, [["Family", "Reason codes (examples)"], ["Data validity", "BAD_FLOW, LOW_FUEL_CONF, STALE_DATA, PROPERTY_OOR, ENERGY_BALANCE, TRANSIENT, OOD"], ["Safety limits", "TRIP_ACTIVE, FAN_DERATE, UNSAFE_DRAFT, HIGH_TEMP, LOW_O2, HIGH_CO"],
                   ["Missing information", "NO_CO (diagnostic only), LIMITS_NOT_APPROVED, CMD_FEEDBACK"], ["Optimizer", "WIDE_INTERVAL, NO_BENEFIT"], ["Monitor-forced", "MODEL_DRIFT, DATA_FAILURE, MAE_WORSE_THAN_SIMPLE, FALSE_ALERTS"]], 0.55, 1.65, 12.2, [2.4, 9.8], 13, 0.55, 3.6)
    deck.cards(s, [("ADVICE", ["Everything passed, benefit clear; still human review"]), ("NO ADVICE", ["Reason codes shown; no setting, no benefit, no interval"]), ("DIAGNOSTIC ONLY", ["CO or similar missing: trends only"])], 5.4, 1.5, 3, 12)

    # 32 ------------------------------------------------------------------
    s = deck.slide("D  AI concepts and results", f"AI vs rule on option ranking: {n.ai_hit} % vs {n.rule_hit} % exact hits, but more false alerts", "Honest comparison on the same rows.")
    deck.image(s, FF / "f3_results.png", 0.55, 1.55, 7.6, 3.4)
    deck.table(s, [["Measure", "AI advisory", "Rule + default move"], ["Exact best move (actionable rows)", f"{n.ai_hit} %", f"{n.rule_hit} %"], ["False-alert rate", f"{n.ai_fa} %", f"{n.rule_fa} %"], ["Any alert on actionable rows", f"{n.ai_any} %", f"{n.rule_any} %"]], 8.4, 1.7, 4.4, [2.4, 1.0, 1.2], 11, 0.5, 2.8)
    deck.callout(s, 0.55, 5.2, 12.2, 1.5, "Conclusion: the AI is not clearly better than the rule. So the pilot baseline is the rule and the regression; the AI stays in shadow and is kept only if it earns at least 10 % lower error on real data.", RED, WHITE, 14, True)

    # 33 ------------------------------------------------------------------
    s = deck.slide("E  Chemistry", f"Combustion chemistry: {x.lam} times the stoichiometric air is fed at O2 {x.o2_now} %", "Stoichiometry and excess air, example row.")
    deck.table(s, [["Step", "Equation"], ["Oxygen needed", "C/12 + H/4 + S/32 − O/32 (kmol per kg fuel)"], ["Stoichiometric air", "O2 needed ÷ 0.2095"], ["Excess air ratio", "λ = 21 / (21 − O2 dry %)"], ["Dry flue gas", "CO2 + SO2 + N2 (fuel + 79 % of air) + excess O2"]], 0.55, 1.65, 7.4, [2.2, 5.2], 13, 0.55, 3.2)
    deck.callout(s, 8.2, 1.65, 4.6, 3.0, f"Example row (synthetic)\nO2 {x.o2_now} % dry → λ = {x.lam}\nStoichiometric air = {x.stoich} kg per kg fuel\nFuel analysis ASSUMED: generic palm-kernel shell (config/fuel_properties.yaml)", G10, G90, 15)
    deck.text(s, 0.55, 5.1, 12.2, 1.7, ["More air than needed burns the fuel completely but carries heat up the stack; too little air leaves CO and unburnt carbon", "The best operating point sits between the two, inside the O2 floor and CO limit"], 14)

    # 34 ------------------------------------------------------------------
    s = deck.slide("E  Chemistry", f"Indirect heat-loss balance: chemistry says {x.eta_chem} % efficient, the HTF heat balance says {x.eta_hb} %", "Loss balance. The gap is a closure check, not an error bar.")
    deck.image(s, P("loss_stack"), 0.55, 1.6, 6.4, 3.5)
    deck.table(s, [["Loss", "% of LHV"], ["Dry flue gas", x.l_dry], ["Water vapour", x.l_vap], ["CO", x.l_co], ["Unburnt carbon in ash", x.l_unb], ["Radiation / other (ASSUMED)", x.l_rad]], 7.2, 1.7, 5.6, [3.6, 2.0], 12, 0.45, 3.0)
    deck.callout(s, 0.55, 5.3, 12.2, 1.5, "Indirect efficiency = 100 − losses. The 14-point gap to the HTF heat balance is expected: the synthetic efficiency is a generator assumption, not derived from chemistry, so it shows where a real site would need to reconcile ash, slag, air leakage and radiation.", G10, G90, 13)

    # 35 ------------------------------------------------------------------
    s = deck.slide("E  Chemistry", f"Trade-off: cutting air from O2 {x.o2_now} % toward {x.o2_opt} % gains about {x.lev_o2} points, until the limits stop it", "Loss versus O2 with cross-check against the ridge model.")
    deck.image(s, P("loss_curve"), 0.55, 1.6, 6.6, 3.7)
    deck.text(s, 7.4, 1.7, 5.4, 4.5, [f"Best allowed O2 is {x.o2_opt} %: the lower safety bound (floor {x.o2_floor} % + margin); the O2 floor and the CO limit ({x.co_lim} ppm), not the model, decide how far to go",
                                      f"For the proposed move the chemistry loss balance changes by {x.d_chem} points; the ridge model says Δη {x.d_ridge} pp: same sign", f"Optimizer objective for the move: J = {x.j} (negative is better than holding)"], 13)
    deck.callout(s, 0.55, 5.5, 12.2, 1.3, "This is the chemical-engineering check on the AI: if physics and the model disagree in sign, the advice should not be trusted.", BLUE, WHITE, 14, True)

    # 36 ------------------------------------------------------------------
    sn = x.snap
    s = deck.slide("E  Chemistry", f"Mass and heat balance close; the biggest levers are air ({x.lev_o2} points) and stack temperature ({x.lev_stack} points per −10 K)", "Heat balance waterfall and lever table.")
    deck.image(s, P("waterfall"), 0.55, 1.6, 6.5, 3.6)
    lv = sn["levers"]
    deck.table(s, [["Lever (each alone)", "Change", "Δη points"]] + [[r["Lever"], r["Change"], f"{r['Δη (points)']:.2f}"] for _, r in lv.iterrows()][:4], 7.3, 1.7, 5.5, [2.2, 2.4, 0.9], 11, 0.5, 3.2)
    deck.callout(s, 0.55, 5.4, 12.2, 1.4, f"Mass balance in vs out closes to {x.close} % (species balance from the fuel analysis and measured O2). Best reachable efficiency inside the limits: {x.eta_best} % vs {x.eta_chem} % now. Stack and moisture levers are not real-time controls.", G10, G90, 13)

    # 37 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", f"The dashboard has {x.n_pages} pages, reached by tabs along the top", "Page map.")
    deck.table(s, [["Tab", "You see", "Use it to"], ["Live", "Replay with tiles: HTF, fuel, SFC, heat, η, gate; charts with baseline band", "Watch the heater as if live"], ["Combustion", "Moisture, LHV status, O2, CO, commands, temperatures, draft, ash, faults", "Diagnose combustion"],
                   ["Optimize", "Efficiency now vs best reachable, what to raise or reduce, balances, levers", "Get real-time guidance"], ["Advice", "Simulated option, interval, checklist, reason codes, chemistry view", "Review one recommendation"],
                   ["What-if", "Try FD and grate targets inside bounds", "Test a move safely"], ["Decisions", "Log accept, reject or defer; action log by shift", "Record the human decision"], ["Value", "Index, THB sensitivity, electricity", "See value and its limits"]], 0.55, 1.6, 12.2, [1.5, 6.4, 4.3], 12, 0.5, 4.2)
    deck.callout(s, 0.55, 5.9, 12.2, 0.9, "Every page: red banner SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION, Asia/Bangkok time label, CALCULATED / PROXY / UNAVAILABLE badges, provenance note under each chart.", G10, G90, 13)

    # 38 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "How to start the dashboard, step by step", "Start-up guide. The server binds to this computer only.")
    deck.table(s, [["Step", "Do this", "Notes"], ["1", "Open PowerShell in the project folder (heater_c_ai_mvp)", "Needs the .venv (Python 3.11, pinned in requirements.lock.txt); no internet"], ["2", ".\\run_dashboard.ps1", "Activates the venv and runs: streamlit run app.py. Linux/macOS/Git Bash: ./run_dashboard.sh"],
                   ["3", "Open http://localhost:8501 in a browser on the same PC", "Listens on 127.0.0.1 only; first load takes a few seconds, then data are cached"], ["4", "Use the tabs, the sidebar and the controls described next", "Default view = held-out test period (replay)"],
                   ["5", "Stop with Ctrl+C in the terminal", "Port busy? add --server.port 8502"]], 0.55, 1.6, 12.2, [0.8, 5.4, 6.0], 13, 0.6, 3.6)
    deck.text(s, 0.55, 5.4, 12.2, 1.5, ["Rebuild everything: python -m src.pipeline --stage all   ·   Tests: python -m pytest -q   ·   Screenshots: python -m src.capture_screenshots", "Optional deep links: /optimize?pos=295 starts the replay at row 295; /recommendations?filter=advice opens on advised rows"], 12)

    # 39 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Inputs: every control, where it is, and what values are allowed", "Input reference.")
    deck.table(s, [["Input", "Where", "Allowed values", "Effect"],
                   ["Data source", "Sidebar", "Default synthetic file, or Upload CSV (≤ 50 MB, same columns, schema-checked)", "Uploads are never verified and get no advice"],
                   ["Date range", "Sidebar", "Within the data dates; default = test period", "Filters every page"],
                   ["Replay position, ◀ step, step ▶, Play", "Live, Optimize", "A row of the selected period; Play = one row (5 min) per second", "Sets 'now'; never shows future rows"],
                   ["Trailing window", "Live", "2, 6, 12 or 24 hours", "Chart span"],
                   ["Row filter + timestamp", "Advice", "All, ADVICE only, NO ADVICE only", "Chooses the recommendation to read"],
                   ["FD and grate targets", "What-if", f"FD {x.fd_lo}–{x.fd_hi} %, grate {x.gr_lo}–{x.gr_hi} %, move ≤ ±{x.step} % per axis", "Outside = error and no result (not clipped)"],
                   ["Role ID, decision, reason, note", "Decisions", "OP-A or OP-B; accept, reject, defer; coded reason; note ≤ 200 characters, no names", "Logged locally; accept only on ADVICE"],
                   ["Price, hours, tariff, watts", "Value", "Editable ASSUMED numbers", "Recomputes the THB sensitivity"]], 0.55, 1.55, 12.2, [2.3, 1.4, 5.0, 3.5], 10, 0.4, 5.4)

    # 40 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Live page: read the tiles first, then the trend charts", "Screenshot of the Live page.")
    deck.text(s, 0.55, 1.65, 4.5, 4.9, ["Tiles: HTF outlet, fuel (time-aligned), SFC, useful heat, efficiency η, advisory gate", "Badges: CALCULATED = from validated inputs; PROXY = estimated, unverified; UNAVAILABLE = cannot be computed",
                                        "Efficiency shows an interval, not a point, when the fuel lot has no lab LHV", "SFC chart shows the baseline band (P25–P75 in the same load band): a reference, not a target", "Use ◀ step / step ▶ or Play to move through time"], 13)
    deck.image(s, S("screen_1.png"), 5.25, 1.6, 7.55, 5.3, crop=(300, 70, 1500, 760))

    # 41 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Combustion page: fuel quality, flue gas, commands, temperatures and faults", "Screenshot of the Combustion page.")
    deck.text(s, 0.55, 1.65, 4.5, 4.9, ["Moisture and LHV come from lab samples per lot: gaps are shown, never filled", "O2 and CO against the synthetic floor and limit (axis clipped at 1,000 ppm, with a note on off-scale points)", "FD and ID values are commands, not airflow",
                                        "Unburnt carbon in ash, economizer ΔP and the fault table come further down the page", "If CO is not available the page says so and warns that those rows are DIAGNOSTIC ONLY"], 13)
    deck.image(s, S("screen_2.png"), 5.25, 1.6, 7.55, 5.3, crop=(300, 70, 1500, 900))

    # 42 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Optimize (1 of 2): status, what to change now, and every parameter with its target", "Optimize page, top half.")
    deck.text(s, 0.55, 1.65, 4.5, 5.0, [f"Top cards: efficiency now ({x.eta_chem} %), best reachable inside limits ({x.eta_best} %), room to improve ({x.gain} points), advisory gate", "Green or amber banner tells you whether the suggestions are consistent with the guarded optimizer or only diagnostic",
                                        "'What to change now' lists actions, air first; take one bounded FD step, then re-check CO and draft", "Parameter table: now, target, status (act / watch / ok), action and why, for air, draft, grate, CO, stack, economizer, fuel, HTF and fans"], 13)
    deck.image(s, S("screen_7_optimize.png"), 5.25, 1.6, 7.55, 5.3, crop=(300, 70, 1500, 1020))

    # 43 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Optimize (2 of 2): levers, heat balance, predicted moves, mass balance and trend", "Optimize page, lower half.")
    deck.text(s, 0.55, 1.65, 4.5, 5.0, ["Levers chart: how many efficiency points each action is worth, alone", "Waterfall: fuel heat in, losses, useful heat to the HTF; 'unaccounted' is what chemistry cannot explain",
                                        "Predicted forward-fan moves: new O2, CO, draft, chemistry η and model ΔSFC; only rows with all checks passed are candidates", "Mass balance in kg per hour closes to the rounding shown; the trend shows η and O2 for the last 6 hours"], 13)
    deck.image(s, S("screen_7_optimize.png"), 5.25, 1.6, 7.55, 5.3, crop=(300, 1480, 1500, 2260))

    # 44 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "Advice page: read the gate first, then the option, the interval and the checklist", "Advice page on an advised row, with the chemistry view below.")
    deck.text(s, 0.55, 1.65, 4.5, 5.0, ["Big red NO ADVICE with reason codes is the default; no setting, benefit or interval is shown then", "On ADVICE: current vs proposed settings, predicted ΔSFC with 90 % interval, seven-line constraint checklist",
                                        "Below: chemical engineering view (λ, losses, loss-vs-O2 curve, objective terms)", "Always 'human review required'"], 13)
    deck.image(s, S("screen_3b_advice_chemistry.png"), 5.25, 1.6, 7.55, 5.3, crop=(300, 70, 1500, 1000))

    # 45 ------------------------------------------------------------------
    s = deck.slide("F  Dashboard and how to use it", "What-if, Decisions and Value: test a move, record the decision, see the value and its limits", "Three pages side by side.")
    for i, (k, cap) in enumerate((("screen_4.png", "What-if: bounded FD and grate targets"), ("screen_5.png", "Decisions: OP-A / OP-B, reason, note"), ("screen_6.png", "Value: index, THB sensitivity"))):
        deck.image(s, S(k), 0.55 + i * 4.15, 1.6, 3.95, 4.3, crop=(300, 70, 1500, 1000))
        deck.text(s, 0.55 + i * 4.15, 6.0, 3.95, 0.9, [cap], 12, BLUE, bold=True, bullets=False)

    # 46 ------------------------------------------------------------------
    s = deck.slide("G  Pilot and deployment", "People and risk: operators stay in charge, and each risk has a control", "People, oversight, risk.")
    deck.table(s, [["Who", "Role"], ["Shift supervisor", "Makes and logs every decision (accept, reject, defer) with a reason; reviews in 2 minutes or less"], ["EHS lead", "Re-checks every advisory; unsafe recommendations must be 0"], ["Process engineer", "Judges false alerts; owns draft, stack and fuel actions"],
                   ["Energy manager", "Measures the effect; owns economics"], ["Data scientist", "Runs the shadow, monitor and retrain; compares with the simple regression"], ["Project sponsor", "Decides GO, REVISE or STOP at week 6"]], 0.55, 1.6, 7.4, [1.9, 5.5], 11, 0.5, 3.8)
    deck.cards(s, [("Main risk", ["An operator follows a wrong suggestion"]), ("Control", ["Advisory only, NO ADVICE default, BMS/SIS untouched, EHS re-check 100 %"]), ("Also", ["Bad data → data gates; model drift → monitor → NO ADVICE"])], 5.65, 1.25, 3, 11)
    deck.text(s, 8.2, 1.65, 4.6, 3.8, ["15 risks scored in the register; top: bad data, limits not real, model fails on real plant", "Operators appear only as role IDs; no names stored (PDPA note)", "Operator SOP drafted: how to read NO ADVICE, when to ignore, when to escalate"], 12)

    # 47 ------------------------------------------------------------------
    s = deck.slide("G  Pilot and deployment", f"Pilot plan: {n.weeks} weeks, read-only, with {n.n_targets} countable targets and {n.n_stops} stop conditions", "Pilot plan from docs/PILOT_SPEC.md.")
    deck.image(s, P("timeline"), 0.55, 1.5, 12.2, 1.9)
    deck.table(s, [["Targets (proposed, verbatim)"]] + [[t] for t in n.targets], 0.55, 3.55, 7.4, [7.4], 10, 0.3, 3.4)
    deck.callout(s, 8.2, 3.55, 4.6, 3.3, "Stop: " + n.stops, RED, WHITE, 13, False)

    # 48 ------------------------------------------------------------------
    s = deck.slide("G  Pilot and deployment", f"Energy and money: AI uses {n.kwh6_base} kWh; the simulated fuel effect is {n.sim_base} %, below the {n.be_base} % needed", "Energy and economics, fictional THB ranges.")
    deck.image(s, FF / "f4_energy.png", 0.55, 1.55, 6.3, 2.6)
    deck.image(s, REP / "figs" / "p6_tornado.png", 7.0, 1.55, 5.8, 3.4)
    deck.table(s, [["Item", "Pessimistic", "Base", "Optimistic"], ["Net annual effect (thousand THB)", n.net_pess, n.net_base, n.net_opt], ["Payback", n.pb_pess, n.pb_base, n.pb_opt], ["Fuel saving needed (%)", n.be_pess, n.be_base, n.be_opt]], 0.55, 4.3, 6.3, [2.8, 1.2, 1.1, 1.2], 10, 0.4, 1.9)
    deck.callout(s, 0.55, 6.15, 12.2, 0.75, f"AI energy = assumed 60 W × measured run times (OWN-ESTIMATE): {n.kwh6_base} kWh in {n.weeks} weeks, {n.kwh_month} kWh a month. Synthetic fuel-energy reduction {n.fuel_pt} kWh thermal over {n.win_h} h. No CO2 claim: no lifecycle boundary.", G10, G90, 11)

    # 49 ------------------------------------------------------------------
    s = deck.slide("G  Pilot and deployment", "Pilot package: read-only adapters, retraining, monitor, audit log, M&V and containers", "Phase 8 summary with its evidence.")
    deck.image(s, P("dataflow"), 0.55, 1.5, 6.6, 3.0)
    deck.table(s, [["Part", "What it does", "Evidence"], ["Adapters + tag map", "Site export → internal schema; refuses unmapped critical tags", f"{x.n_site_cols} site columns, units exact"], ["Site config", "ADVISORY refused until limits and approval are filled", "tested"],
                   ["Retrain", "Promote only if better, ≥10 % vs simple, guardrails pass", f"champion {x.champion}"], ["Monitor", "PSI, data quality, weekly MAE, false alerts → NO ADVICE", f"quality {x.dq} %, max PSI {x.psi} ({x.psi_feat}), {x.fa} false alerts/shift"],
                   ["Audit log", "Append-only, hash chain, 3 roles", "tamper detected in test"], ["M&V", "Normalised SFC, matched cells, 90 % CI", f"known −3 % recovered as {x.inj} % [{x.inj_lo}, {x.inj_hi}]; no effect: {x.aa} % [{x.aa_lo}, {x.aa_hi}]"]],
               7.3, 1.5, 5.5, [1.4, 2.6, 2.3], 9, 0.36, 4.6)
    deck.text(s, 0.55, 4.7, 6.6, 2.2, ["Container: non-root, read-only, no network for the app and jobs; gateway publishes 127.0.0.1:8501 only", f"M&V resolves only about ±{x.mde} % of fuel: a smaller real effect will not show in six weeks", "Docker image not built yet (needs network)"], 11)

    # 50 ------------------------------------------------------------------
    s = deck.slide("G  Pilot and deployment", f"Request: approve a {n.weeks}-week read-only pilot; stop if any stop condition fires", "Request, decision and stop condition.")
    deck.cards(s, [("Request", [f"Scope: one heater, read-only shadow, then supervised advice only if authorised", f"Duration: {n.weeks} weeks", f"Cost range (fictional): {n.one_opt}–{n.one_pess} million THB one-time, {n.run_opt}–{n.run_pess} million a year", "Owner: project sponsor (role)"]),
                   ("Decision at week 6", [f"GO = {n.n_targets} of {n.n_targets} targets met on measured data and 0 of {n.n_stops} stop conditions", "REVISE = safety and data targets met, effect or economics not shown", "STOP = any stop condition, or approval lapses"]),
                   ("Next steps", ["Approve preparation (weeks 1–2): approvals, tag walk-down, assay plan", "Site fills the tag map; OEM and EHS sign the limits", "Build the Docker image on a networked machine; run run_real_retrospective.ps1 on a historical export", "Decide where real data may be processed"])], 1.6, 4.4, 3, 12)
    deck.callout(s, 0.55, 6.15, 12.2, 0.75, "Recommendation: REVISE before any GO. No saving has been verified. Questions welcome.", BLUE, WHITE, 15, True)

    assert deck.n == TOTAL, deck.n
    from src.project_deck_notes import notes
    talk = notes(n, x, a)
    assert len(talk) == TOTAL, len(talk)
    for sl, t in zip(deck.prs.slides, talk):                       # full talk track replaces the short slide notes
        sl.notes_slide.notes_text_frame.text = t
    deck.save(OUT)
    L.table().round(4).to_csv(REP / "project_deck_number_map.csv", index=False)
    return deck, L


def main():
    deck, L = build()
    print(f"deck saved: {OUT} ({deck.n} slides); numbers logged: {len(L.rows)} -> reports/project_deck_number_map.csv")
    for w in deck.warnings:
        print("  fit warning:", w)


if __name__ == "__main__":
    main()
