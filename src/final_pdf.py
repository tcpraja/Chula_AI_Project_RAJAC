"""ReportLab builders: final/Heater_C_Final_Proposal.pdf (<= 3 pages) and final/Appendix.pdf. All metrics come from src.final_nums."""
import re
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.final_nums import numbers

ROOT = Path(__file__).resolve().parents[1]
FIN, SHOTS = ROOT / "final", ROOT / "assets" / "screenshots"
BANNER = "SYNTHETIC DATA - all numbers computed in a synthetic prototype or marked ASSUMED/FICTIONAL - NOT FOR PLANT OPERATION"
_FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DJ", str(_FONTS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DJ-B", str(_FONTS / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ", boldItalic="DJ-B")
_N = {}


def nums(D, L):
    if id(L) not in _N:
        _N[id(L)] = numbers(D, L)
    return _N[id(L)]


def styles(base=7.6):
    b = ParagraphStyle("b", fontName="DJ", fontSize=base, leading=base * 1.28, spaceAfter=2.2)
    return {"b": b, "h": ParagraphStyle("h", parent=b, fontName="DJ-B", fontSize=base + 1.6, leading=base + 3, spaceBefore=4, spaceAfter=1.5, textColor=colors.HexColor("#1f3b57")),
            "t": ParagraphStyle("t", parent=b, fontName="DJ-B", fontSize=base + 5, leading=base + 7, spaceAfter=2),
            "c": ParagraphStyle("c", parent=b, fontSize=base - 0.8, leading=(base - 0.8) * 1.25, textColor=colors.HexColor("#444444")),
            "tc": ParagraphStyle("tc", parent=b, fontSize=base - 0.7, leading=(base - 0.7) * 1.22, spaceAfter=0)}


def table(rows, widths, st, head=True, fs=None):
    data = [[Paragraph(str(c), st["tc"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    ts = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]
    if head:
        ts.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe7ee")))
    t.setStyle(TableStyle(ts))
    return t


def footer(title):
    def draw(c, doc):
        c.saveState()
        c.setFont("DJ-B", 6.5)
        c.setFillColor(colors.HexColor("#b00020"))
        c.drawCentredString(A4[0] / 2, 0.95 * cm, BANNER)
        c.setFont("DJ", 6.5)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawCentredString(A4[0] / 2, 0.55 * cm, f"{title} - page {doc.page}")
        c.restoreState()
    return draw


def proposal(D, L, admin):
    from src.build_project_deck import extras
    n, st = nums(D, L), styles(9.3)
    x = extras(L, n)
    W = A4[0] - 3.0 * cm
    S = []
    S.append(Paragraph("Heater C AI Decision Support: final proposal for a six-week read-only pilot", st["t"]))
    S.append(Paragraph(f"<b>{admin['name']}</b> · ID {admin['id']} · {admin['course']} · Organization: PET Resin Plant P (anonymized) · Deadline {admin['due']}", st["b"]))
    S.append(Paragraph("<b>Answer first:</b> approve preparation and a read-only shadow pilot on one heater, but do <b>not</b> claim savings or buy a CO analyser yet. "
                       f"In synthetic tests a simple linear model forecasts fuel as well as a machine-learning model, and the AI option ranking is not clearly better than a plain rule. "
                       "Everything here is from a synthetic prototype; no real plant data were read.", st["b"]))
    S.append(Paragraph("1 Request", st["h"]))
    S.append(Paragraph(f"<b>Scope:</b> one biomass thermic-fluid heater (Heater C); the system advises, operators decide in the existing DCS, nothing is written to any plant system. "
                       f"<b>Duration:</b> {n.weeks} weeks (approvals and data; read-only shadow; supervised advice only if authorised; measurement). "
                       f"<b>Cost range</b> (OWN-ESTIMATE, fictional placeholders, not quotes): one-time {n.one_opt}-{n.one_pess} million THB (engineering, CO-analyser allowance, pilot labour), "
                       f"running {n.run_opt}-{n.run_pess} million THB per year. <b>Owner:</b> project sponsor (role). "
                       f"<b>End decision at week 6:</b> GO, REVISE or STOP against {n.n_targets} countable targets and {n.n_stops} stop conditions. No saving is estimated, because none can be measured yet.", st["b"]))
    S.append(Paragraph("2 Problem and baseline", st["h"]))
    S.append(Paragraph(f"The heater is reported to burn more palm-kernel-shell fuel than its design benchmark, with operator-dependent air and grate settings, infrequent fuel heating-value (LHV) tests and ageing fans "
                       f"(summarised from the course midterm; the original was not read by the tool). <b>Labelled number: specific fuel consumption (SFC) median {n.sfc_med} kg fuel per GJ useful heat "
                       f"(P25-P75 {n.sfc_p25}-{n.sfc_p75}), SYNTHETIC.</b> <b>The company's own baseline still requires validation</b>: measured fuel mass, lot-assayed LHV and a defined stable window; "
                       "until then the synthetic value only shows the method works.", st["b"]))
    S.append(table([["Measure", "Result", "Method"],
                    ["Baseline SFC (synthetic)", f"{n.sfc_med} kg/GJ, P25-P75 {n.sfc_p25}-{n.sfc_p75}", f"median over {n.sfc_n} eligible stable windows, training period, SYNTHETIC (company baseline: requires validation)"],
                    ["Eligible rows", f"{n.elig} % ELIGIBLE; a further {n.diag_share} % diagnostic only (no CO)", f"guardrail layers 1-2 on {n.rows_total} rows, {n.lots} fuel lots, {n.days} days; pilot target is 60 %, so this could fail"],
                    ["Data source for the pilot", "read-only historian export + lab LHV per lot", "needs signed site limits; the tool itself never reads real data"]],
                   [3.3 * cm, 4.6 * cm, W - 7.9 * cm], st))
    S.append(Paragraph("3 Options and choice", st["h"]))
    S.append(table([["Option", "What it is", "Synthetic evidence", "Verdict"],
                    ["1 No change", "keep current practice", "no answer to the fuel question", "baseline for comparison"],
                    ["2 Process change", "SOP, lot-matched air/grate guide, more LHV assays", "not tested here (needs plant)", "do alongside, low risk"],
                    ["3 Simple automation", "rule alert (trailing P75) + 2-variable regression", f"rule false alerts {n.rule_fa} %; regression MAE {n.mae_B} kg/h", "pilot baseline"],
                    ["4 AI advisory", "fuel forecast + ranked simulated moves, all gated", f"forecast MAE {n.mae_C0} kg/h (boosting) vs {n.mae_L} (linear); exact-action hit {n.ai_hit} % vs rule {n.rule_hit} %", "shadow only; keep only if MAE gain over regression is at least 10 % on real data"]],
                   [2.6 * cm, 4.4 * cm, W - 11.3 * cm, 4.3 * cm], st))
    S.append(Paragraph("<b>Choice:</b> start with options 2 and 3 and run option 4 in shadow; where it runs: offline on a site PC (no cloud, no network, no write path). "
                       "A pilot package is ready for a site run: read-only adapters with a tag-map check, a monitor that forces NO ADVICE on drift or bad data, a tamper-evident audit log and a container with no network. "
                       "<b>PDPA:</b> operators appear only as role IDs (OP-A, OP-B), notes carry no names, log kept for the pilot plus 90 days (proposal), site privacy contact to confirm.", st["b"]))
    S.append(Paragraph("4 Test results (SYNTHETIC, held-out later fuel lots)", st["h"]))
    S.append(Paragraph(f"<b>Simple vs AI.</b> Next-15-minute fuel forecast, mean absolute error (kg/h): repeat the current feed {n.mae_P2}; 2-variable regression {n.mae_B}; "
                       f"<b>linear model on all features {n.mae_L}</b> (95 % CI {n.ci_L}; 90 % interval covers {n.cov_L} % of rows); boosted trees (the AI option) {n.mae_C0}. "
                       f"Boosting is {n.C0_vs_L} % worse than the linear model, so the simple model was chosen. For ranking simulated operator moves, the AI picks the exact best move on {n.ai_hit} % of actionable rows against {n.rule_hit} % for rule plus default action, "
                       f"but raises false alerts on {n.ai_fa} % of rows against {n.rule_fa} %: <b>the AI is not clearly better than the rule</b>. "
                       f"<b>Failure and fix.</b> My first comparison used last fuel value as the reference, which made the linear model look {n.L_vs_P} % better; a critic review showed the models also saw the current feed, "
                       f"so I added the fair reference 'repeat current feed' and the gain fell to {n.L_vs_P2} %; selection was moved to validation rows only. "
                       f"<b>Energy.</b> Computing for the whole pilot uses about {n.kwh6_base} kWh (OWN-ESTIMATE: 60 W assumed, no meter, times measured run times: train {n.t_train} s, shadow {n.t_shadow} s), "
                       f"against a synthetic fuel-energy reduction of {n.fuel_pt} kWh thermal over a {n.win_h} h replay (90 % interval {n.fuel_hi}-{n.fuel_lo}; delta fuel kg x LHV / 3.6) - a generator illustration, not a saving. "
                       f"<b>Chemistry check.</b> A heat-loss balance from the fuel's combustion chemistry (assumed fuel analysis) puts the example row at {x.eta_chem} % against {x.eta_hb} % from the HTF heat balance; "
                       f"cutting excess air from {x.lam} times the stoichiometric air toward O2 {x.o2_opt} % is worth about {x.lev_o2} points, and the chemistry agrees in sign with the model ({x.d_chem} vs {x.d_ridge}).", st["b"]))
    S.append(Paragraph("5 People and sustainability", st["h"]))
    S.append(Paragraph(f"<b>Who checks:</b> shift supervisor (decisions), EHS lead (safety re-check of every advisory), process engineer (false alerts), energy manager (measurement). "
                       f"<b>Who is affected:</b> operators (review of at most 2 minutes), laboratory (more LHV assays), maintenance (CO analyser). "
                       f"<b>One risk and control:</b> an operator follows a wrong suggestion; control = advisory only, NO ADVICE by default, BMS/SIS/trips unchanged, EHS re-check pass 100 %, unsafe recommendations 0. "
                       f"<b>AI energy = power x time:</b> {n.kwh6_base} kWh in {n.weeks} weeks ({n.kwh_month} kWh per month; range {n.kwh6_opt}-{n.kwh6_pess} kWh over the pilot). "
                       f"<b>What it saves:</b> nothing is verified. At the simulated effect (about {n.sim_opt} % of fuel at best, {n.sim_base} % after the assumed realisation share) the base case does not cover running cost "
                       f"(needs {n.be_base} % fuel saving; net {n.net_base} thousand THB per year; payback: {n.pb_opt} only in the optimistic case). No CO2 claim: no lifecycle boundary is defined.", st["b"]))
    S.append(Paragraph("6 Trial plan", st["h"]))
    S.append(Paragraph(f"<b>Measure:</b> {n.n_targets} targets in the scorecard (e.g. {n.targets[0]}; {n.targets[1]}; {n.targets[2]}; {n.targets[3]}). "
                       f"<b>GO</b> = {n.n_targets} of {n.n_targets} targets met on measured data and 0 of {n.n_stops} stop conditions fired; <b>REVISE</b> = safety and data targets met but effect or economics not shown; "
                       f"<b>STOP</b> = any of: {n.stops}. A six-week trial can only resolve about ±{x.mde} % of fuel (own test on synthetic data), so a smaller effect would be reported as not shown, never as a saving.", st["b"]))
    doc = SimpleDocTemplate(str(FIN / "Heater_C_Final_Proposal.pdf"), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            title="Heater C Final Proposal", author=admin["name"])
    doc.build(S, onFirstPage=footer("Heater C final proposal"), onLaterPages=footer("Heater C final proposal"))


def critique_item():
    t = (ROOT / "reports" / "ai_critique_log.md").read_text(encoding="utf-8")
    m = re.search(r"^1\. \*\*(.+?)\*\* (.+)$", t, re.M)
    return m.group(1), re.sub(r"\*\*", "", m.group(2))


def appendix(D, L, admin):
    n, st = nums(D, L), styles(8.2)
    W = A4[0] - 3.0 * cm
    S = [Paragraph("Appendix: evidence for the Heater C proposal", st["t"]),
         Paragraph(f"{admin['name']} · {admin['id']} · PET Resin Plant P (anonymized) · SYNTHETIC DATA", st["b"]),
         Paragraph("A1 Dashboard screenshots (synthetic data, captured headlessly from the running app; the six screens in order)", st["h"])]
    names = ["1 Live Performance", "2 Combustion Diagnostics", "3 AI Recommendations (NO ADVICE row)", "4 What-if Simulator", "5 Operator Decisions", "6 Business Value"]
    cells = []
    for i in range(6):
        p = SHOTS / f"screen_{i + 1}.png"
        im = Image(str(p), width=W / 3 - 0.3 * cm, height=(W / 3 - 0.3 * cm) * 1.27) if p.exists() else Paragraph("(missing)", st["c"])
        cells.append([im, Paragraph(names[i], st["c"])])
    rows = [[cells[j][0] for j in range(i, i + 3)] for i in (0, 3)]
    caps = [[cells[j][1] for j in range(i, i + 3)] for i in (0, 3)]
    t = Table([rows[0], caps[0], rows[1], caps[1]], colWidths=[W / 3] * 3)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    S += [t, PageBreak()]
    S.append(Paragraph("A2 Test evidence", st["h"]))
    desc = {"test_advisory_gate.py": "guardrail gate: 1 accept + 12 NO ADVICE cases, record contract", "test_app_smoke.py": "6 dashboard pages (AppTest), banner, NO ADVICE row, what-if bounds, operator log, shadow determinism",
            "test_cleaning_engineering.py": "cleaning, heat balance, eligibility", "test_model_leakage.py": "no future/truth features, canary and truncation tests",
            "test_no_secrets.py": "denylisted real names absent from output folders", "test_synthetic_physics.py": "generator physics, units, HTF table",
            "test_energy_math.py": "independent kWh/MJ recomputation, workbook formulas, verbatim pilot targets/stops"}
    rows = [["Test file", "Tests", "Passed", "Checks"]]
    for f in sorted(desc):
        k = f"tests_{f}_n"
        if k in D.fn.index:
            rows.append([f, L.f(f"tests {f}", D.final(k)[0], "{:.0f}", D.final(k)[1]), L.f(f"passed {f}", D.final(f"tests_{f}_passed")[0], "{:.0f}", D.final(f"tests_{f}_passed")[1]), desc[f]])
    rows.append(["total (this run, excl. final-document tests)", n.tests_total, n.tests_passed, "all must pass before submission"])
    S.append(table(rows, [4.6 * cm, 1.3 * cm, 1.4 * cm, W - 7.3 * cm], st))
    S.append(Paragraph(f"Shadow replay of the {n.test_rows} held-out rows ({n.test_share} % of all rows): ADVICE {n.adv}, NO ADVICE {n.noadv}, DIAGNOSTIC ONLY {n.diag}; deterministic (identical file hash on repeat). "
                       f"Rule P75 vs AI where the rule is defined: both alert {n.both}, AI only {n.ai_only}, rule only {n.rule_only}.", st["b"]))
    S.append(Paragraph("A3 Two sources, one line each on how they were used", st["h"]))
    S.append(table([["Source", "Use"],
                    ["ASME PTC 4, Fired Steam Generators (performance test code)", "Method reference only for defining useful heat, fuel input and efficiency (input-output basis); no compliance claim, not reproduced."],
                    ["Angelopoulos and Bates (2021), A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification, arXiv:2107.07511", "Basis for the split-conformal 90 % forecast interval used in the model card."]],
                   [7.0 * cm, W - 7.0 * cm], st))
    S.append(Paragraph("A4 One AI error and its correction (from reports/ai_critique_log.md)", st["h"]))
    title, body = critique_item()
    S.append(Paragraph(f"<b>{title}</b> {body}", st["b"]))
    S.append(PageBreak())
    S.append(Paragraph("A5 Energy boundary (what is and is not counted; no CO2 claim)", st["h"]))
    S.append(table([["Inside the boundary", "Value", "Label"],
                    ["AI computing electricity, whole pilot", f"{n.kwh6_base} kWh (range {n.kwh6_opt}-{n.kwh6_pess})", "OWN-ESTIMATE: assumed watts x measured seconds"],
                    ["FD fan electricity change in the replay (negative = avoided)", f"-{n.fan_kwh} kWh", "SYNTHETIC, fan_power_kW_FD columns, fan law"],
                    ["Fuel thermal energy reduction in the replay", f"{n.fuel_pt} kWh (90 %: {n.fuel_hi}-{n.fuel_lo})", "SYNTHETIC, delta fuel kg x LHV / 3.6, coefficient uncertainty only"],
                    ["Ratio fuel kWh avoided to AI kWh (different carriers, not netted)", f"about {n.ratio} to 1", "computed; only meaningful if the synthetic effect were real"],
                    ["Outside the boundary", "fuel supply and transport, biogenic carbon accounting, ash handling, CO-analyser manufacture and power, site network", "not measured, so no CO2 or net-environment claim is made"]],
                   [6.2 * cm, 5.0 * cm, W - 11.2 * cm], st))
    S.append(Paragraph("A6 Synthetic method and formulas", st["h"]))
    S.append(Paragraph(f"Data are generated, not recorded: a demand series drives fuel lots (moisture, LHV, 6-18 h lots), latent efficiency (moisture, fouling, excess-air deviation, derates), fuel = Q / (eta x LHV), HTF temperatures, "
                       f"then measured values = truth + noise, bias, lag, with injected faults. Main run seed 42: {n.rows_total} rows (5 min, {n.days} days, {n.lots} lots); stress seed 77. Settings include a random exploration component, "
                       "so effects are identifiable in synthetic data but would not be identifiable from ordinary plant data. Splits are chronological and by lot; features use only past rows.", st["b"]))
    for line in ["Mass flow: m_HTF = V / 3600 x rho(T_mean)   (HTF property table, never water cp, no extrapolation)",
                 "Useful heat: Q_out = m_HTF x cp(T_mean) x (T_out - T_in)   [MW]",
                 "Fuel heat: Q_in = m_fuel x LHV_as-fired   ;   efficiency eta = 100 x Q_out / Q_in",
                 "Specific fuel consumption: SFC [kg/GJ] = 1 / (eta x LHV [GJ/kg]) = 1000 / (eta x LHV [MJ/kg])",
                 "Energy of fuel change: kWh = delta_fuel_kg x LHV [MJ/kg] / 3.6 ;  per advised 5-min row delta_fuel_kg = fuel_kg/h x (5/60) x dSFC/SFC",
                 "Fan electricity (proxy): kW_FD scales with FD^3, so delta = kW_FD x ((FD_new/FD)^3 - 1) x 5/60 h",
                 "AI electricity: kWh = W x s / 3.6e6 (watts assumed, seconds measured); 1 kWh = 3.6 MJ",
                 "Option score: J = dSFC + l1 x dFanPower + l2 x |move| + l3 x interval width; advice needs the 95th-percentile dSFC below 0 and every guardrail passed",
                 "Forecast interval: split conformal, 90 %, absolute residuals on validation rows"]:
        S.append(Paragraph("• " + line, st["b"]))
    spec = re.sub(r"\s+", " ", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
    worked = re.search(r"Worked \(SYNTHETIC\): (.*?) ASME", spec).group(1)
    S.append(Paragraph(f"Worked example (SYNTHETIC, quoted from docs/SPEC.md C3): {worked} "
                       f"Run times: generate {n.t_gen} s, train {n.t_train} s, shadow {n.t_shadow} s, dashboard start {n.t_dash} s (wall clock, MEASURED-IN-PROTOTYPE). "
                       "Limits are arbitrary synthetic envelopes (ASSUMED / NOT APPROVED); real limits only from a signed site configuration. Provenance labels: SYNTHETIC, MEASURED-IN-PROTOTYPE, PUBLISHED, OWN-ESTIMATE, ASSUMED.", st["b"]))
    doc = SimpleDocTemplate(str(FIN / "Appendix.pdf"), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.5 * cm, title="Heater C Appendix", author=admin["name"])
    doc.build(S, onFirstPage=footer("Appendix"), onLaterPages=footer("Appendix"))
