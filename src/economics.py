"""Build reports/economics_and_energy.xlsx (live formulas, every cell labeled), reports/figs/p6_tornado.png and reports/economics_calc.json.

Inputs: reports/ai_runtime_measured.csv (src.measure_runtime), reports/energy_synthetic.json (src.energy_calc).
All THB figures are FICTIONAL / ASSUMED ranges for sensitivity, never quotes or savings. The synthetic efficiency effect is a generator
illustration. No CO2 claim: no lifecycle boundary is defined. Run: python -m src.economics
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.xl_eval import Book

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
XLSX = REP / "economics_and_energy.xlsx"
FIG = REP / "figs" / "p6_tornado.png"
OUT = REP / "economics_calc.json"
SC = {"D": "Pessimistic", "E": "Base", "F": "Optimistic"}
A, M = "Assumptions", "Model"
BANNER = "SYNTHETIC / FICTIONAL ILLUSTRATION - NOT A SAVINGS CLAIM - NOT FOR PLANT OPERATION"
OWN = "OWN-ESTIMATE"


def assumptions():
    """key -> (label, unit, pess, base, opt, provenance, note). pess = worse for payback."""
    rt = pd.read_csv(REP / "ai_runtime_measured.csv").set_index("step")["wall_s_mean"]
    en = json.loads((REP / "energy_synthetic.json").read_text(encoding="utf-8"))
    page = float(rt[[i for i in rt.index if i.startswith("dashboard_render_")]].mean())
    f = lambda v: (v, v, v)
    S = "SYNTHETIC (src.energy_calc, held-out test replay)"
    Mm = "MEASURED-IN-PROTOTYPE (src.measure_runtime, wall clock, this PC)"
    return {
        # measured run times
        "t_gen": ("Wall time, generate stage (mean of 3)", "s", *f(float(rt["generate"])), Mm, "python -m src.pipeline --stage generate"),
        "t_train": ("Wall time, train stage (mean of 3)", "s", *f(float(rt["train"])), Mm, "python -m src.pipeline --stage train"),
        "t_shadow": ("Wall time, shadow replay of 3,041 rows (mean of 3)", "s", *f(float(rt["shadow"])), Mm, "upper bound for one daily shadow run"),
        "t_dash": ("Wall time, dashboard start to healthy", "s", *f(float(rt["dashboard_start_to_healthy"])), Mm, "1 run"),
        "t_page": ("Wall time, one dashboard page render (mean of 6 pages)", "s", *f(page), Mm, "AppTest, warm cache"),
        # synthetic energy
        "win_h": ("Held-out replay window length", "h", *f(en["window_hours"]), S, "3,041 rows x 5 min"),
        "fuel_kgh": ("Mean fuel flow in the replay window", "kg/h", *f(en["fuel_mean_kgh_all_rows"]), S, "fuel_rate_aligned_kgh"),
        "lhv": ("Mean as-fired LHV in the replay window", "MJ/kg", *f(en["lhv_mean_MJkg"]), S, "LHV_used_MJkg (mix of lab, band and envelope values)"),
        "dfuel_pt": ("Change in fuel over the window, point (negative = less fuel)", "kg", *f(en["delta_fuel_kg"]["point"]), S, "sum over 708 advised rows of fuel_kg x dSFC/SFC"),
        "dfuel_lo": ("Change in fuel over the window, 90 % lower bound", "kg", *f(en["delta_fuel_kg"]["lo90"]), S, "coefficient uncertainty only"),
        "dfuel_hi": ("Change in fuel over the window, 90 % upper bound", "kg", *f(en["delta_fuel_kg"]["hi90"]), S, "coefficient uncertainty only"),
        "dmj_pt": ("Change in fuel energy over the window, point", "MJ", *f(en["delta_fuel_energy_MJ"]["point"]), S, "sum of dFuel_kg x row LHV"),
        "dmj_lo": ("Change in fuel energy over the window, 90 % lower bound", "MJ", *f(en["delta_fuel_energy_MJ"]["lo90"]), S, ""),
        "dmj_hi": ("Change in fuel energy over the window, 90 % upper bound", "MJ", *f(en["delta_fuel_energy_MJ"]["hi90"]), S, ""),
        "fan_kwh": ("FD fan electricity change over the window (negative = avoided)", "kWh", *f(en["fan_FD_delta_kWh_electric"]), S,
                    "fan_power_kW_FD x ((FD_new/FD)^3 - 1) x 5/60 h per advised row (fan law, A-register proxy)"),
        "fan_kw": ("Mean FD + ID fan electric power in the window", "kW", *f(en["mean_fan_kW_FD_plus_ID_all_rows"]), S, "fan_power_kW_FD + fan_power_kW_ID columns"),
        # constants
        "mj_kwh": ("MJ per kWh", "MJ/kWh", *f(3.6), "PUBLISHED (SI definition: 1 kWh = 3.6 MJ)", "exact"),
        "days_6w": ("Working days in the 6-week pilot", "days", *f(30), "ASSUMED (6 weeks x 5 days)", ""),
        "renders_d": ("Dashboard page renders per working day", "count", *f(200), "ASSUMED", "interactive use"),
        "wk_6w": ("Weeks in the pilot", "weeks", *f(6), "PILOT_SPEC", "six-week pilot"),
        "d_6w": ("Calendar days in the pilot", "days", *f(42), "PILOT_SPEC", ""),
        "d_month": ("Days in a month used for monthly figures", "days", *f(30), "ASSUMED", ""),
        "d_year": ("Days in a year", "days", *f(365), "PUBLISHED (calendar)", ""),
        "n_gen": ("Generate runs in the 6 weeks", "runs", *f(1), "ASSUMED", "synthetic data only; a site pilot uses historian exports"),
        # tunable ASSUMED / OWN-ESTIMATE
        "p_busy": ("Average PC electric power while a job runs", "W", 100, 60, 35, OWN + " (no wattmeter)",
                   "24-thread machine; CPU package ~25-70 W + board/RAM/SSD/GPU/display ~10-30 W; replace by a plug-in meter reading"),
        "p_open": ("Average PC electric power while the dashboard sits open", "W", 30, 20, 15, OWN + " (no wattmeter)", "light interactive load"),
        "n_train": ("Training runs in the 6 weeks", "runs", 14, 7, 3, "ASSUMED", "weekly refit + initial"),
        "n_shadow": ("Shadow replay runs in the 6 weeks", "runs", 84, 42, 6, "ASSUMED", "daily (pessimistic: twice daily; optimistic: weekly)"),
        "open_h": ("Dashboard open hours per working day", "h/day", 10, 6, 3, "ASSUMED", ""),
        "tariff": ("Electricity price", "THB/kWh", 4.15, 3.98, 3.88,
                   "PUBLISHED (Thai ERC average tariff: 4.15 Jan-Apr 2025, 3.98 May-Aug 2025, 3.88 Jan-Apr 2026; Nation Thailand, Bangkok Post)",
                   "national average incl. Ft; a site tariff (TOU, demand charge) will differ; replace with the site bill"),
        "price": ("Fuel price (palm-kernel shell, delivered)", "THB/tonne", 2500, 3200, 4500,
                  "OWN-ESTIMATE from PUBLISHED anchors (3,200 THB/t oil-palm shell in arXiv 2406.00056 citing DEDE; FOB listings US$90-170/t at ~33 THB/US$)",
                  "no current Thai market quote found; replace with the site purchase price"),
        "hours": ("Heater operating hours per year", "h/yr", 6000, 7000, 8000, "ASSUMED", ""),
        "real": ("Share of the simulated fuel effect realised in practice", "fraction", 0.2, 0.5, 1.0, "ASSUMED",
                 "synthetic gains are generator illustrations; 0 would mean no effect at all"),
        "rev_h": ("Operator/engineer review time", "h/week", 6, 3, 1.5, "ASSUMED", "running cost after the pilot"),
        "rate": ("Loaded labour rate", "THB/h", 600, 450, 350, "ASSUMED (fictional)", ""),
        "eng_d": ("Engineering effort (integration, MOC, validation), one-time", "days", 40, 25, 15, "ASSUMED", ""),
        "eng_rate": ("Engineering day rate", "THB/day", 9000, 7000, 5000, "ASSUMED (fictional)", ""),
        "co_an": ("CO-analyser allowance, one-time, if no usable CO sensor", "THB", 1200000, 700000, 350000, OWN + " range (not a quote)",
                  "PUBLISHED equipment-only floors: in-situ zirconia O2 analyser from CAD 3,085 (Alpha Controls, Fuji ZKM-2); portable O2/CO analysers US$1,100-5,000 (listings). "
                  "Installed continuous CO adds tapping, wiring, controller and commissioning; get a vendor quote"),
        "upkeep": ("Software upkeep and re-validation", "THB/yr", 250000, 150000, 60000, "ASSUMED (fictional)", ""),
    }


# Model rows: key -> (label, unit, formula template, provenance, note). {x} = Assumptions ref in the same scenario column, [x] = Model row.
def model_rows():
    return [
        ("kwh_gen", "AI electricity, generate, 6 weeks", "kWh", "{t_gen}*{n_gen}*{p_busy}/({mj_kwh}*1000000)", "kWh = W x s / 3.6e6"),
        ("kwh_train", "AI electricity, train, 6 weeks", "kWh", "{t_train}*{n_train}*{p_busy}/({mj_kwh}*1000000)", "kWh = W x s / 3.6e6"),
        ("kwh_shadow", "AI electricity, shadow replay, 6 weeks", "kWh", "{t_shadow}*{n_shadow}*{p_busy}/({mj_kwh}*1000000)", "kWh = W x s / 3.6e6"),
        ("kwh_dash_busy", "AI electricity, dashboard start-up and page renders, 6 weeks", "kWh",
         "({t_dash}+{t_page}*{renders_d})*{days_6w}*{p_busy}/({mj_kwh}*1000000)", "start once per day + renders"),
        ("kwh_dash_open", "AI electricity, dashboard left open, 6 weeks", "kWh", "{open_h}*{days_6w}*{p_open}/1000", "kWh = W x h / 1000"),
        ("kwh_6w", "AI electricity, all steps, 6 weeks", "kWh", "[kwh_gen]+[kwh_train]+[kwh_shadow]+[kwh_dash_busy]+[kwh_dash_open]", "sum"),
        ("kwh_month", "AI electricity, monthly (same usage pattern)", "kWh/month", "[kwh_6w]*{d_month}/{d_6w}", "scaled by days"),
        ("kwh_year", "AI electricity, annual (pilot pattern persists)", "kWh/yr", "[kwh_6w]*{d_year}/{d_6w}", "scaled by days"),
        ("eff", "Simulated fuel change as a fraction of fuel burned in the window (negative = less fuel)", "fraction", "{dfuel_pt}/({fuel_kgh}*{win_h})", "SYNTHETIC illustration"),
        ("eff_lo", "same, 90 % lower bound", "fraction", "{dfuel_lo}/({fuel_kgh}*{win_h})", "coefficient uncertainty only"),
        ("eff_hi", "same, 90 % upper bound", "fraction", "{dfuel_hi}/({fuel_kgh}*{win_h})", "coefficient uncertainty only"),
        ("kwh_fuel_pt", "Fuel energy change over the window, point", "kWh thermal", "{dmj_pt}/{mj_kwh}", "kWh = MJ / 3.6"),
        ("kwh_fuel_lo", "Fuel energy change over the window, 90 % lower bound", "kWh thermal", "{dmj_lo}/{mj_kwh}", "kWh = MJ / 3.6"),
        ("kwh_fuel_hi", "Fuel energy change over the window, 90 % upper bound", "kWh thermal", "{dmj_hi}/{mj_kwh}", "kWh = MJ / 3.6"),
        ("kwh_fuel_yr", "Fuel energy change per year at the assumed hours, point", "kWh thermal/yr", "[kwh_fuel_pt]/{win_h}*{hours}", "scaled by operating hours"),
        ("kwh_fan_yr", "FD fan electricity change per year, point (negative = avoided)", "kWh/yr", "{fan_kwh}/{win_h}*{hours}", "scaled by operating hours"),
        ("fuel_t", "Fuel burned per year", "tonne/yr", "{fuel_kgh}*{hours}/1000", "kg/h x h / 1000"),
        ("fuel_cost", "Fuel cost per year (ASSUMED price)", "THB/yr", "[fuel_t]*{price}", "FICTIONAL"),
        ("gross", "Simulated fuel-cost change avoided, after the realisation share", "THB/yr", "-[eff]*{real}*[fuel_cost]", "FICTIONAL, not a saving"),
        ("fan_cost", "FD fan electricity cost change (negative = avoided)", "THB/yr", "[kwh_fan_yr]*{tariff}", "FICTIONAL"),
        ("model_cost", "Model (PC) electricity cost", "THB/yr", "[kwh_year]*{tariff}", "FICTIONAL"),
        ("labour", "Review labour", "THB/yr", "{rev_h}*52*{rate}", "h/week x 52 x rate"),
        ("upk", "Software upkeep", "THB/yr", "{upkeep}", "ASSUMED"),
        ("running", "Running cost per year", "THB/yr", "[fan_cost]+[model_cost]+[labour]+[upk]", "sum"),
        ("net", "Net annual effect (positive = benefit)", "THB/yr", "[gross]-[running]", "FICTIONAL sensitivity"),
        ("one_time", "One-time cost: engineering + CO analyser + 6-week pilot review labour", "THB",
         "{eng_d}*{eng_rate}+{co_an}+{rev_h}*{wk_6w}*{rate}", "FICTIONAL"),
        ("payback", "Simple payback", "years", 'IF([net]>0,[one_time]/[net],"NO PAYBACK")', "one-time / net annual"),
        ("breakeven", "Fuel saving needed just to cover running cost", "% of fuel", "[running]/[fuel_cost]*100", "compare with the simulated effect"),
        ("sim_pct", "Simulated fuel change x realisation share", "% of fuel", "-[eff]*{real}*100", "SYNTHETIC x ASSUMED"),
    ]


def build_formula(key, col, rows, A_row, M_row, override=None, depth=0):
    """Expand Model row `key` for scenario column `col` into one formula body (no '=') over Assumptions refs; override={param: col}."""
    override = override or {}
    tmpl = next(r[3] for r in rows if r[0] == key)
    out, i = "", 0
    while i < len(tmpl):
        c = tmpl[i]
        if c in "{[":
            j = tmpl.index("}" if c == "{" else "]", i)
            name = tmpl[i + 1:j]
            out += f"{A}!{override.get(name, col)}{A_row[name]}" if c == "{" else "(" + build_formula(name, col, rows, A_row, M_row, override, depth + 1) + ")"
            i = j + 1
        else:
            out += c
            i += 1
    return out


def build_xlsx(a, rows):
    wb = openpyxl.Workbook()
    hdr = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="444444")
    red = Font(bold=True, color="B00020")
    wrap = Alignment(wrap_text=True, vertical="top")
    ws = wb.active
    ws.title = "README"
    for i, t in enumerate([BANNER, "Sheets: Assumptions (all inputs; Pessimistic/Base/Optimistic), Model (live formulas, three scenarios), Tornado (one-at-a-time swings), Labels.",
                           "Every value row carries: ID, label, unit, provenance, note. Provenance values: SYNTHETIC | MEASURED-IN-PROTOTYPE | PUBLISHED | OWN-ESTIMATE | ASSUMED.",
                           "Pessimistic = worse for payback. Yellow cells are inputs you may edit; all other numbers are formulas.",
                           "THB values are fictional placeholders, not quotes. 'NO PAYBACK' means the net annual effect is zero or negative.",
                           "No CO2 figure is given: no lifecycle boundary (fuel supply, biogenic carbon, ash) is defined.",
                           "Units: 1 kWh = 3.6 MJ; kWh from watts: W x s / 3.6e6; fuel energy change = delta fuel kg x LHV MJ/kg."], 1):
        ws.cell(i, 1, t).font = red if i == 1 else Font()
    ws.column_dimensions["A"].width = 150

    wa = wb.create_sheet(A)
    wa.append(["ID", "Parameter", "Unit", "Pessimistic", "Base", "Optimistic", "Provenance", "Method / note"])
    A_row = {}
    for r, (k, (lab, unit, pe, ba, op, prov, note)) in enumerate(a.items(), 2):
        wa.append([k, lab, unit, pe, ba, op, prov, note])
        A_row[k] = r
        if "ASSUMED" in prov or OWN in prov:
            for c in "DEF":
                wa[f"{c}{r}"].fill = PatternFill("solid", fgColor="FFF3B0")
    wm = wb.create_sheet(M)
    wm.append(["ID", "Quantity", "Unit", "Pessimistic", "Base", "Optimistic", "Provenance", "Method / note"])
    M_row = {}
    for r, (k, lab, unit, tmpl, note) in enumerate(rows, 2):
        M_row[k] = r
    for r, (k, lab, unit, tmpl, note) in enumerate(rows, 2):
        prov = "SYNTHETIC x ASSUMED (formula)" if k in ("eff", "eff_lo", "eff_hi", "gross", "sim_pct", "kwh_fuel_pt", "kwh_fuel_lo", "kwh_fuel_hi", "kwh_fuel_yr", "kwh_fan_yr") \
            else "OWN-ESTIMATE (formula on measured times and assumed power)" if k.startswith("kwh_") else "ASSUMED / FICTIONAL (formula)"
        wm.append([k, lab, unit] + ["=" + build_formula(k, c, rows, A_row, M_row) for c in "DEF"] + [prov, note])
    # tornado
    wt = wb.create_sheet("Tornado")
    wt.append(["ID", "Parameter varied (others at Base)", "Unit", "Net annual effect at Pessimistic", "Net annual effect at Optimistic", "Swing (abs)",
               "Provenance", "Method / note"])
    tun = [k for k, v in a.items() if v[2] != v[4]]
    for r, k in enumerate(tun, 2):
        wt.append([k, a[k][0], a[k][1], "=" + build_formula("net", "E", rows, A_row, M_row, {k: "D"}), "=" + build_formula("net", "E", rows, A_row, M_row, {k: "F"}),
                   f"=ABS(E{r}-D{r})", "ASSUMED / FICTIONAL (formula)", "Model net annual effect with only this parameter moved"])
    for w in (wa, wm, wt):
        for c in w[1]:
            c.font, c.fill = hdr, fill
        for col, wd in zip("ABCDEFGH", (14, 62, 16, 16, 16, 16, 44, 70)):
            w.column_dimensions[col].width = wd
        for row in w.iter_rows(min_row=2):
            for c in row:
                c.alignment = wrap
        w.freeze_panes = "C2"
    for r in range(2, len(rows) + 2):
        for c in "DEF":
            wm[f"{c}{r}"].number_format = "#,##0.000" if wm[f"C{r}"].value in ("fraction", "kWh", "kWh/month", "years", "% of fuel") else "#,##0"
    wb.save(XLSX)
    return A_row, M_row, tun


def tornado_png(book, tun, a, rows, base):
    items = []
    for i, k in enumerate(tun, 2):
        items.append((a[k][0], float(book.value("Tornado", f"D{i}")), float(book.value("Tornado", f"E{i}"))))
    items.sort(key=lambda t: abs(t[2] - t[1]))
    fig, ax = plt.subplots(figsize=(10, 0.38 * len(items) + 2))
    for y, (lab, lo, hi) in enumerate(items):
        ax.barh(y, lo - base, left=base, color="#d1495b")
        ax.barh(y, hi - base, left=base, color="#1f6f8b")
    ax.set_yticks(range(len(items)), [t[0][:52] for t in items], fontsize=8)
    ax.axvline(base, color="k", lw=1)
    ax.axvline(0, color="#888", lw=0.8, ls="--")
    ax.set_xlabel("Net annual effect, THB/yr (FICTIONAL; positive = benefit)\nred = pessimistic value, blue = optimistic value; no bar = negligible, or one-time cost (affects payback, not annual net)", fontsize=8)
    ax.set_title(f"Tornado: one-at-a-time swings around Base ({base:,.0f} THB/yr)\n{BANNER}", fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    FIG.parent.mkdir(exist_ok=True)
    fig.savefig(FIG, dpi=130)
    plt.close(fig)


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    run()


def run():
    a, rows = assumptions(), model_rows()
    A_row, M_row, tun = build_xlsx(a, rows)
    b = Book(XLSX)
    res = {k: {SC[c]: b.value(M, f"{c}{M_row[k]}") for c in "DEF"} for k in M_row}
    base_net = float(res["net"]["Base"])
    tornado_png(b, tun, a, rows, base_net)
    res["tornado"] = {k: {"pess": b.value("Tornado", f"D{i}"), "opt": b.value("Tornado", f"E{i}")} for i, k in enumerate(tun, 2)}
    OUT.write_text(json.dumps({"label": BANNER, "model": res}, indent=1, default=str), encoding="utf-8")
    units = {r[0]: (r[2], r[4]) for r in rows}
    flat = [{"key": k, "scenario": sc, "value": v, "unit": units[k][0], "label": units[k][1] + " | " + BANNER}
            for k in M_row for sc, v in res[k].items()]
    en = json.loads((REP / "energy_synthetic.json").read_text(encoding="utf-8"))
    for k in ("window_hours", "advice_rows_used", "fuel_mean_kgh_all_rows", "lhv_mean_MJkg", "fan_FD_delta_kWh_electric", "fan_FD_increase_kWh_electric",
              "fan_FD_decrease_kWh_electric"):
        flat.append({"key": "energy_" + k, "scenario": "synthetic", "value": en[k], "unit": "see key", "label": "SYNTHETIC (src.energy_calc)"})
    for nm in ("delta_fuel_kg", "delta_fuel_energy_MJ", "delta_fuel_energy_kWh_thermal"):
        for sc, v in en[nm].items():
            flat.append({"key": "energy_" + nm, "scenario": sc, "value": v, "unit": nm.split("_")[-1], "label": "SYNTHETIC (src.energy_calc), coefficient uncertainty only"})
    pd.DataFrame(flat).to_csv(REP / "economics_summary.csv", index=False)
    for k in ("kwh_6w", "kwh_month", "kwh_year", "kwh_fuel_pt", "kwh_fuel_lo", "kwh_fuel_hi", "kwh_fan_yr", "gross", "running", "net", "one_time", "payback", "breakeven", "sim_pct"):
        print(f"{k:12s}", {s: (round(v, 3) if isinstance(v, float) else v) for s, v in res[k].items()})


if __name__ == "__main__":
    main()
