"""Build the final submission set in submission/ (new names; the student's own *_Raja_* files are never touched).
SYNTHETIC - NOT FOR PLANT OPERATION.

  Heater_C_Final_AI_Solution_Proposal.pdf   exactly 3 pages (each page shrink-fitted, verified with pypdf)
  Heater_C_Final_Presentation.pptx          exactly 5 slides, notes = six-minute script
  Heater_C_Final_Appendix.pdf               test table + screenshot, two sources, one AI error
  Heater_C_Gap_Closure_Register.xlsx        CP01-CP24 + extra gaps, revalidation, options, rubric, gates
  Heater_C_Model_Validation_Report.pdf      forecast, action ranking, calibration, guardrails, M&V power
  Heater_C_Business_Case_and_Energy.xlsx    economics workbook (live formulas) + market sources + pilot cost
  Heater_C_Presentation_Script.docx         script, Q&A, feedback framework (plain OOXML, no extra package)
  Heater_C_Final_Compliance_Report.pdf      quality gates 1-7, rubric matrix, sign-off
Run: python -m src.sub_build
"""
import datetime as dt
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src import sub_content as C
from src.final_pdf import footer, styles, table
from src.sub_nums import ORIGINAL, build, save_map

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"
AUD = ROOT / "reports" / "audit"
SHOTS = ROOT / "assets" / "screenshots"
NAMES = {"proposal": "Heater_C_Final_AI_Solution_Proposal.pdf", "deck": "Heater_C_Final_Presentation.pptx", "appendix": "Heater_C_Final_Appendix.pdf",
         "register": "Heater_C_Gap_Closure_Register.xlsx", "validation": "Heater_C_Model_Validation_Report.pdf", "business": "Heater_C_Business_Case_and_Energy.xlsx",
         "script": "Heater_C_Presentation_Script.docx", "compliance": "Heater_C_Final_Compliance_Report.pdf"}
NAVY, TEAL, RED, GREY = "#1f3b57", "#0f7c8c", "#b00020", "#555555"
W = A4[0] - 2.6 * cm
FRAME_H = A4[1] - 1.1 * cm - 1.5 * cm - 0.2 * cm
TODAY = "18 November 2026"


def thb(v):
    return C.thb(v)


def P(t, s):
    return Paragraph(t, s)


def boxed(flow, bg="#eef4f8", border=TEAL):
    t = Table([[flow]], colWidths=[W])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(border)), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def page(flows):
    return KeepInFrame(W, FRAME_H, flows, mode="shrink")


def doc(path, title):
    return SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.3 * cm, rightMargin=1.3 * cm, topMargin=1.1 * cm, bottomMargin=1.5 * cm, title=title, author=C.STUDENT)


def header(st, sub):
    return [P(C.TITLE, st["t"]), P(f"<b>{C.STUDENT}</b> · Student ID <b>{C.SID}</b> · {C.COURSE} · {sub} · {TODAY}", st["c"]),
            P(f"Organisation: {C.SITE}; asset: one biomass (palm-kernel shell) thermic-fluid heater, heater_id HEATER_C_SYNTHETIC. "
              "Evidence labels: <b>SYN</b> synthetic, computed by the prototype · <b>MEAS</b> measured in the prototype · <b>PUB</b> published, source in appendix · "
              "<b>EST</b> own estimate, method stated · <b>MID</b> midterm operational estimate, disclosure to be confirmed · <b>FIC</b> fictional planning input.", st["c"]), Spacer(1, 3)]


# ------------------------------------------------------------------ proposal (exactly 3 pages)
def proposal(N):
    st = styles(8.8)
    h = lambda t: P(t, st["h"])
    oc, orow = C.options(N)
    p1 = header(st, "Final AI solution proposal")
    p1 += [h("1 Management request"), boxed(P(
        f"I request approval for a <b>six-week, read-only AI shadow trial on Heater C only</b>. The trial makes no supervised advice and no control writes. "
        f"<b>Cost:</b> {thb(N['pilot_cost_opt'])}–{thb(N['pilot_cost_pess'])}, base {thb(N['pilot_cost_base'])} (EST: engineering days plus review hours). "
        f"A CO analyser ({thb(N['a_co_an_opt'])}–{thb(N['a_co_an_pess'])}, EST) is needed only if no usable CO signal exists. "
        "<b>Owner:</b> the plant sponsor is accountable and the process engineer runs the trial. "
        "I also request two low-cost process steps now: moisture and heating-value tests for every fuel lot, and a rule-based fuel-use alert. "
        "<b>End decision at week 6:</b> GO to a separately approved supervised-advice trial, REVISE, or STOP.", st["b"]))]
    p1 += [h("2 Problem and baseline"), P(
        "Heater C burns palm-kernel shell to heat the thermic fluid that the PET process depends on. The process engineer and shift lead cannot see in time when it uses more fuel than the load needs. "
        "Fuel moisture varies, heating value is tested only now and then, and combustion settings depend on the operator. "
        "<b>KPI:</b> specific fuel consumption (SFC), in kg of fuel per GJ of useful heat. "
        "<b>Midterm continuity:</b> the midterm chose this problem over granulator cutter trips. Its estimate (MID) was 65–70 % efficiency against 85 % design, implying 20–30 % extra fuel. "
        f"<b>Final baseline:</b> the final keeps the same heater and problem but tests on a synthetic copy. It has {C.f0(N['rows_total'])} five-minute rows over {N['days_total']:.0f} days and {C.f0(N['lots_total'])} fuel lots. "
        f"Its median efficiency is {C.f1(N['eta_median'])} % (P25–P75 {C.f1(N['eta_p25'])}–{C.f1(N['eta_p75'])} %) and its median SFC is {C.f1(N['baseline_sfc_median'])} kg/GJ (P25–P75 {C.f1(N['baseline_sfc_p25'])}–{C.f1(N['baseline_sfc_p75'])}) (SYN). "
        f"<b>Consequence:</b> on planning inputs, fuel costs about {N['fuel_cost_base']/1e6:.0f} M THB a year, so 1 % of fuel is worth about {N['fuel_cost_base']/1e8:.2f} M THB a year (FIC). "
        "The design gap is <b>not</b> assumed recoverable: part of it is fuel quality, fouling and equipment. "
        "Predictive maintenance of fans and conveyors stays out of scope.", st["b"])]
    p1 += [h("3 Options and choice"), table([oc] + orow, [2.1 * cm, 2.8 * cm, 2.4 * cm, 1.7 * cm, 3.0 * cm, 1.7 * cm, 1.6 * cm, 1.3 * cm, 1.8 * cm], st), Spacer(1, 3),
           P(f"<b>Choice and why.</b> AI is justified only for what a rule cannot do, which is to name a bounded fan or grate move. "
             f"On the held-out synthetic rows it names the generator's best move {N['ai_exact_pct']:.1f} % of the time, against {N['rule_exact_pct']:.1f} % for the rule. "
             f"However, it raises false alerts on {N['ai_fa_pct']:.1f} % of rows that need no change, against {N['rule_fa_pct']:.1f} % for the rule. "
             f"The forecast is only {C.f1(N['gain_vs_P2'])} % better than repeating the current feed, below my 10 % rule. "
             f"On planning inputs the base case does not pay back ({C.f0(N['net_base'])} THB a year). "
             "So the defensible choice is: process improvement and the rule alert now, and AI only in a read-only shadow trial. "
             "Supervised advice and deployment are not requested.", st["b"]),
           P("<b>Data, hosting and privacy.</b> The trial needs a read-only historian export. "
             "It uses fuel feed and belt weight, thermic-fluid flow and temperatures, flue O2 and CO, draft, FD/ID/grate commands, and lab assays per fuel lot. "
             "A tag walk-down in week 1 confirms which tags are available. "
             "The prototype runs offline on one site PC, bound to localhost: no cloud, no external AI service at runtime, and no write path to the DCS, PLC, BMS or SIS. "
             "Only synthetic data were used with external AI tools. Operator decision logs use role IDs, never names. "
             "Retention and lawful basis are set by the data protection officer (PDPA), and company data need company approval.", st["b"])]
    ev = [["Test (held-out, same rows for every method)", "AI", "Comparator", "Reading", "Label"],
          ["Next-interval fuel forecast, MAE kg/h", f"{C.f1(N['mae_L'])} (90 % CI {C.f1(N['mae_L_lo'])}–{C.f1(N['mae_L_hi'])})", f"{C.f1(N['mae_P2'])} repeat current feed", f"{C.f1(N['gain_vs_P2'])} % better; target 10 %: missed", "SYN"],
          ["90 % forecast interval coverage", f"{C.f1(N['cov_L'])} %", "nominal 90 %", "calibrated", "SYN"],
          ["Exact best move named (actionable rows)", f"{N['ai_exact_pct']:.1f} %", f"{N['rule_exact_pct']:.1f} % rule + default move", f"was {ORIGINAL['ai_exact_pct']:.1f} % before the menu fix", "SYN"],
          ["False alerts (rows needing no change)", f"{N['ai_fa_pct']:.1f} %", f"{N['rule_fa_pct']:.1f} % rule", "AI worse: failure", "SYN"],
          ["False alerts per 8-h shift", f"{N['fa_per_shift']:.2f}", "target ≤ 1", "failure", "SYN"],
          ["Rows eligible for advice", f"{N['eligible_share_pct']:.1f} %", "target ≥ 60 %", "failure", "SYN"],
          ["Smallest detectable SFC change, 80 % power", f"{N['mde80_21d']:.1f} % (21-day windows)", f"simulated effect {N['sim_pct_opti']:.2f} %", "saving not measurable", "SYN/EST"]]
    p2 = [h("4 Test results"), P(
        f"<b>Test.</b> The test replayed {C.f0(N['test_rows'])} held-out five-minute rows that no model saw during training or selection. "
        "Truth labels come from the generator and were used for scoring only. "
        f"<b>Results.</b> The linear forecast beat the simple reference by {C.f1(N['gain_vs_P2'])} %, and its 90 % interval covered {C.f1(N['cov_L'])} % of outcomes. "
        f"The guardrails returned NO ADVICE on {C.f0(N['shadow_no_advice'])} rows and DIAGNOSTIC ONLY on {C.f0(N['shadow_diag_only'])}, and allowed advice on {C.f0(N['shadow_advice'])}. "
        f"The AI named the exact best move on {N['ai_exact_pct']:.1f} % of actionable rows, against {N['rule_exact_pct']:.1f} % for the rule. "
        f"<b>Failure and correction.</b> Before this audit the figure was {ORIGINAL['ai_exact_pct']:.1f} %, because the optimiser offered large combined moves that are not in the action menu. "
        "I fixed the menu using validation data only, with a selection rule fixed in advance, and then scored the test set once. "
        f"The remaining failure is false alerts: {N['ai_fa_pct']:.1f} % against {N['rule_fa_pct']:.1f} %, or {N['fa_per_shift']:.1f} per shift against a target of 1. "
        f"Only {N['eligible_share_pct']:.1f} % of rows are eligible for advice. "
        f"<b>Implication.</b> The model is not ready to advise operators, and a fuel saving of about {N['sim_pct_opti']:.2f} % cannot be measured in weeks. "
        "All action effects are associations in synthetic data, not causal effects.", st["b"]),
        table(ev, [5.2 * cm, 3.7 * cm, 3.6 * cm, 3.6 * cm, 1.3 * cm], st), Spacer(1, 4)]
    p2 += [h("5 People and sustainability"), P(
        "<b>Affected people.</b> Heater operators and shift leads read and act. The process engineer owns the model and its review. "
        "Fuel QA runs the lot assays, EHS holds a veto on combustion-safety advice, OT/IT and cybersecurity own the read-only export, "
        "and the plant sponsor is accountable for go, revise or stop. "
        "<b>Human oversight.</b> The operator keeps full authority and makes every change in the existing DCS. "
        "The tool cannot write to any control system, and a rejection needs only a coded reason. "
        "The escalation path is operator → shift lead → EHS → sponsor. "
        "<b>Major risk and control.</b> The main risk is advice that looks plausible but cuts air too far, leading to CO, unburnt fuel or unstable draft. "
        "The control is a safety gate that defaults to NO ADVICE, with 21 reason codes, an O2 floor plus margin, a CO margin, a draft band, ±4 % moves and an out-of-distribution check. "
        "Unsigned limits force NO ADVICE, and in this trial everything is shadow only. "
        f"<b>Sustainability.</b> Measured run times multiplied by an assumed 35–100 W PC power give {N['kwh_6w_opti']:.1f}–{N['kwh_6w_pess']:.1f} kWh of electricity for six weeks, "
        f"base {N['kwh_6w_base']:.1f} kWh, or about {N['ai_kwh_cost_base']:.0f} THB at {N['a_tariff_base']:.2f} THB/kWh (EST, PUB tariff). "
        f"The simulated fuel effect over the 253-hour test window is {C.f0(N['fuel_kwh_th'])} kWh of thermal energy (90 % range {C.f0(N['fuel_kwh_lo'])}–{C.f0(N['fuel_kwh_hi'])}), "
        f"plus {N['fan_kwh']:.0f} kWh of FD-fan electricity avoided (SYN). These are illustrations, not savings. "
        "Electrical and thermal kWh are not added together, and no CO2 claim is made: the fuel is biogenic and emissions were not measured.", st["b"]),
        table([["Item", "Value", "Label"],
               ["AI electricity, six weeks", f"{N['kwh_6w_base']:.1f} kWh (range {N['kwh_6w_opti']:.1f}–{N['kwh_6w_pess']:.1f})", "EST from MEAS run times"],
               ["Simulated fuel effect, full realisation", f"{N['sim_pct_opti']:.2f} % of fuel; base (50 % realised) {N['sim_pct_base']:.2f} %", "SYN × EST"],
               ["Fuel saving needed to cover running cost", f"{N['breakeven_base']:.2f} % (range {N['breakeven_opti']:.2f}–{N['breakeven_pess']:.2f} %)", "FIC/PUB inputs"],
               ["Net annual effect, pessimistic / base / optimistic", f"{C.f0(N['net_pess'])} / {C.f0(N['net_base'])} / {C.f0(N['net_opti'])} THB/yr", "FIC sensitivity"]],
              [6.2 * cm, 8.0 * cm, 3.2 * cm], st)]
    sc, srows = C.scorecard(N)
    p3 = [h("6 Trial plan"), boxed(P(
        "<b>Weeks 1–2:</b> approvals (sponsor, OT/IT, EHS, OEM, MOC, data protection), tag walk-down, lab assay plan, historian export, electricity meter reading and vendor quotes. "
        "<b>Weeks 3–6:</b> read-only blind shadow. Operators and the process engineer judge each suggestion without acting on it, and the rule alert runs alongside as the comparator. "
        "<b>Success</b> is measured on site data against the scorecard below. "
        "<b>Stop</b> immediately on any condition in the stop list. No fuel saving will be claimed.", st["b"])),
        Spacer(1, 3), P("<b>Success criteria</b> (one scorecard; the synthetic result shows where the prototype stands today)", st["b"]),
        table([sc] + srows, [3.7 * cm, 2.9 * cm, 3.1 * cm, 3.4 * cm, 2.4 * cm, 2.9 * cm], st), Spacer(1, 3),
        P("<b>Stop conditions</b> (any one stops the trial): " + "; ".join(f"({i}) {s}" for i, s in enumerate(C.STOPS, 1)) + ".", st["b"]),
        P("<b>Cost range and accountable owner</b>", st["b"]),
        table([["Item", "Pessimistic", "Base", "Optimistic", "Basis"],
               ["Engineering and integration", thb(N["a_eng_d_pess"] * N["a_eng_rate_pess"]), thb(N["a_eng_d_base"] * N["a_eng_rate_base"]), thb(N["a_eng_d_opt"] * N["a_eng_rate_opt"]),
                f"{N['a_eng_d_opt']:.0f}–{N['a_eng_d_pess']:.0f} days × day rate (FIC)"],
               ["Review time, 6 weeks", thb(6 * N["a_rev_h_pess"] * N["a_rate_pess"]), thb(6 * N["a_rev_h_base"] * N["a_rate_base"]), thb(6 * N["a_rev_h_opt"] * N["a_rate_opt"]), "h/week × 6 × rate (FIC)"],
               ["<b>Trial total</b>", f"<b>{thb(N['pilot_cost_pess'])}</b>", f"<b>{thb(N['pilot_cost_base'])}</b>", f"<b>{thb(N['pilot_cost_opt'])}</b>", "EST"],
               ["CO analyser, only if no usable CO", thb(N["a_co_an_pess"]), thb(N["a_co_an_base"]), thb(N["a_co_an_opt"]), "EST; PUB equipment floors in appendix"],
               ["AI electricity", f"{N['kwh_6w_pess']:.1f} kWh", f"{N['kwh_6w_base']:.1f} kWh", f"{N['kwh_6w_opti']:.1f} kWh", "under 50 THB"]],
              [4.6 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 6.6 * cm], st),
        P("<b>Owner:</b> the plant sponsor is accountable. The process engineer is responsible day to day. EHS, OT/IT and the OEM hold vetoes. "
          "The data protection officer approves operator logs. These are roles only, not named people.", st["b"]),
        h("End decision and next gate"), boxed(P(
            "<b>GO</b> requires all scorecard targets met on site data and no stop condition. "
            "A GO leads to a new request for a supervised-advice trial with signed limits, MOC and hazard review, approved controlled step tests, "
            f"and an M&V design long enough to detect the expected effect (≥ {N['days_for_1pct']:.0f} days per window for 1 %). "
            "<b>REVISE</b> applies if any target is missed without a stop: recalibrate the alert threshold on shadow data, fix the data gaps, and repeat the shadow. "
            "<b>STOP</b> applies if any stop condition fires, or if coverage and false alerts both miss: keep process improvement and the rule alert, and end the AI work. "
            "<b>This trial will not prove</b> a fuel saving, a causal effect, or safety of closed-loop use, and none is requested.", st["b"]), bg="#fbf3e6", border="#c27c0e"),
        Spacer(1, 3), P("Every number on these pages is logged with its source file in submission/number_source_map_final.csv. Sources and the AI error are in the appendix.", st["c"])]
    path = SUB / NAMES["proposal"]
    doc(path, "Heater C Final AI Solution Proposal").build([page(p1), PageBreak(), page(p2), PageBreak(), page(p3)],
                                                          onFirstPage=footer("Heater C final proposal"), onLaterPages=footer("Heater C final proposal"))
    return path


# ------------------------------------------------------------------ appendix
def appendix(N):
    st = styles(8.0)
    h = lambda t: P(t, st["h"])
    rc, rrows = C.revalidation(N)
    F = header(st, "Appendix to the final proposal")
    F += [h("A1 Test evidence"), P("Held-out test results (SYNTHETIC), with values before and after this audit. Selection used validation data only, and the test set was scored once.", st["b"]),
          table([rc] + rrows[:18], [4.6 * cm, 3.1 * cm, 3.5 * cm, 1.9 * cm, 3.4 * cm, 2.0 * cm], st), Spacer(1, 4)]
    F += [PageBreak()]
    shot = SHOTS / "screen_3.png"
    if shot.exists():
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(str(shot)).getSize()
        hh = 12.5 * cm
        ww = min(W, hh * iw / ih)
        F += [h("A1 (cont.) Dashboard screenshot"), Image(str(shot), width=ww, height=ww * ih / iw),
              P("Screenshot: the dashboard's advice page on a held-out synthetic row. It shows the gate result, the reason codes and the chemistry check (src.capture_screenshots).", st["c"])]
    F += [h("A2 Two sources and how each was used"),
          table([["Source", "How it was used"],
                 ["ASME PTC 4, Fired Steam Generators, performance test code (ASME).", "Method reference for the input-output efficiency, useful heat and fuel energy that define the SFC baseline and the heat balance. No compliance claim."],
                 ["Angelopoulos, A. N. and Bates, S. (2021). A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification. arXiv:2107.07511.",
                  f"Basis of the split-conformal 90 % forecast interval; the held-out coverage of {C.f1(N['cov_L'])} % checks it."]], [8.0 * cm, W - 8.0 * cm], st),
          Spacer(1, 3), P("<b>Market data used for planning inputs (PUBLISHED, accessed 18 Nov 2026)</b>", st["b"]),
          table([["Input", "Published figure", "Source", "Use"],
                 ["Electricity tariff", "4.15 (Jan–Apr 2025), 3.98 (May–Aug 2025), 3.88 THB/kWh (Jan–Apr 2026), national average incl. Ft",
                  "Nation Thailand (nationthailand.com/business/economy/40049646; /news/policy/40049419); Bangkok Post (bangkokpost.com/business/general/2930806)", "Tariff range in the business case"],
                 ["Palm-shell fuel price", "3,200 THB/t oil-palm shell (DEDE data cited); FOB listings US$90–170/t",
                  "arXiv:2406.00056 (bio-energy supply chain, DEDE data); tradekey.com listing", "Anchor for the 2,500–4,500 THB/t own estimate; no Thai market quote found"],
                 ["O2/CO analyser", "In-situ zirconia O2 from CAD 3,085 (equipment only); portable O2/CO US$1,100–5,000",
                  "alphacontrols.com (Fuji ZKM-2); levitt-safety.com and supplyhouse.com (Bacharach PCA 400)", "Floor for the CO-analyser allowance; installed cost needs a quote"]],
                [2.6 * cm, 5.0 * cm, 6.2 * cm, W - 13.8 * cm], st),
          PageBreak(), h("A3 One AI error, its correction and verification"),
          P("<b>Error (made by the AI coding assistant).</b> The first model card compared the forecast with persistence of the <i>last</i> fuel value. "
            "But the models also receive the current feeder speed, which is in effect the fuel being fed now. "
            "The comparison was therefore unfair, and it reported a gain of about 21 %.", st["b"]),
          P("<b>How I found it.</b> I asked what the simplest honest forecast would be with the same inputs, and added the reference 'repeat the current feed' (P2).", st["b"]),
          P(f"<b>Correction and verification.</b> On the held-out test set P2 scores {C.f1(N['mae_P2'])} kg/h. "
            f"Against that reference the first selected model was only about 4 % better. After the fix, selection on validation data chose the simpler linear model "
            f"({C.f1(N['mae_L'])} kg/h, {C.f1(N['gain_vs_P2'])} % better than P2), and boosting added nothing ({C.f1(N['mae_C0'])} kg/h). "
            "The fix is tested in tests/test_model_leakage.py and logged in reports/ai_critique_log.md.", st["b"]),
          P(f"<b>Second error, found in this final audit.</b> The optimiser could propose combined 4 % fan-and-grate moves that the evaluation's action menu never contains. "
            f"This capped the exact-move hit rate at {ORIGINAL['ai_exact_pct']:.1f} %. "
            f"The fix was a menu chosen on validation data by a rule fixed in advance (src/calibrate_menu.py). Scored once on test, the hit rate is {N['ai_exact_pct']:.1f} %. "
            f"The false-alert rate did not change ({N['ai_fa_pct']:.1f} %); it is reported as an open failure, not re-tuned on test data.", st["b"]),
          P("<b>AI use disclosure.</b> An AI coding assistant wrote code, tests and drafts under my instructions. I set the rules, reviewed every phase packet and own every number. "
            "No external AI service runs at runtime, and only synthetic data were given to AI tools.", st["b"]),
          h("A4 Measurement power (why the trial claims no saving)")]
    import pandas as pd
    pw = json.loads((ROOT / "reports" / "mv" / "mv_power.json").read_text(encoding="utf-8"))
    rows = [["Days per window", "Pairs", "90 % half-width", "MDE at 80 % power", "A/A false saving"]] + [
        [str(w["window_days"]), str(w["pairs"]), f"±{w['hw90_pct']:.2f} %", f"{w['mde80_pct']:.2f} %", f"{100*w['false_saving_share']:.0f} %"] for w in pw["windows"]]
    F += [table(rows, [3 * cm] * 5, st), P(f"Extrapolated (EST): 42-day windows ≈ {N['mde80_42d']:.1f} %; detecting {N['sim_pct_opti']:.2f}–0.24 % needs about {C.f0(N['days_for_024'])} days per window. "
                                           "Source: reports/mv/mv_power.md (synthetic A/A, no intervention).", st["c"])]
    path = SUB / NAMES["appendix"]
    doc(path, "Heater C Final Appendix").build(F, onFirstPage=footer("Heater C final appendix"), onLaterPages=footer("Heater C final appendix"))
    return path


# ------------------------------------------------------------------ deck (exactly 5 slides)
def deck(N):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Inches, Pt

    rgb = lambda h: RGBColor.from_string(h.lstrip("#"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    script = {s[0]: s for s in C.script(N)}
    rub = {1: "Problem & baseline · 10 marks · 60 s", 2: "Options, choice & data · 20 marks · 75 s", 3: "Test results · 10 marks · 90 s",
           4: "People & oversight 10 + Sustainability 10 · 60 s", 5: "Request & trial plan · 15 marks · 75 s"}

    def box(s, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE):
        sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        if fill:
            sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
        else:
            sh.fill.background()
        if line:
            sh.line.color.rgb = rgb(line); sh.line.width = Pt(0.75)
        else:
            sh.line.fill.background()
        sh.shadow.inherit = False
        return sh

    def text(s, x, y, w, h, paras, size=12, color="#1a1a1a", bold=False, align=PP_ALIGN.LEFT, fill=None, line=None, anchor_top=True):
        sh = box(s, x, y, w, h, fill, line)
        tf = sh.text_frame
        tf.word_wrap = True
        for m in ("margin_left", "margin_right"):
            setattr(tf, m, Inches(0.1))
        tf.margin_top = tf.margin_bottom = Inches(0.05)
        from pptx.enum.text import MSO_ANCHOR
        tf.vertical_anchor = MSO_ANCHOR.TOP if anchor_top else MSO_ANCHOR.MIDDLE
        if isinstance(paras, str):
            paras = [paras]
        for i, p_ in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            segs = p_ if isinstance(p_, list) else [(p_, bold)]
            for seg, b in segs:
                r = p.add_run(); r.text = seg; r.font.size = Pt(size); r.font.bold = b; r.font.color.rgb = rgb(color); r.font.name = "Calibri"
            p.space_after = Pt(3)
        return sh

    def frame(i, title, kicker):
        s = prs.slides.add_slide(blank)
        box(s, 0, 0, 13.333, 0.42, fill=NAVY)
        text(s, 0.35, 0.05, 8.5, 0.34, f"Heater C AI Advisory · {C.SITE}", 11, "#ffffff", True)
        text(s, 8.4, 0.05, 4.6, 0.34, f"Rubric: {rub[i]}", 10.5, "#cfe8ec", True, PP_ALIGN.RIGHT)
        text(s, 0.35, 0.55, 12.6, 0.75, title, 24, NAVY, True)
        text(s, 0.35, 1.25, 12.6, 0.42, kicker, 13, TEAL, False)
        box(s, 0, 7.08, 13.333, 0.42, fill="#f2f2f2")
        text(s, 0.35, 7.11, 10.6, 0.34, f"SYNTHETIC DATA — NOT FOR PLANT OPERATION · {C.STUDENT} {C.SID} · numbers: submission/number_source_map_final.csv", 9, RED, True)
        text(s, 11.9, 7.11, 1.1, 0.34, f"{i}/5", 10, GREY, True, PP_ALIGN.RIGHT)
        s.notes_slide.notes_text_frame.text = f"[{script[i][1]} s] {script[i][2]}\n\n{script[i][3]}"
        return s

    def table_(s, x, y, w, rows, widths, size=10.5, head=NAVY, rowh=0.36):
        t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(rowh * len(rows))).table
        for j, cw in enumerate(widths):
            t.columns[j].width = Inches(cw)
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                cell = t.cell(r, c)
                cell.text = str(v)
                cell.margin_left = cell.margin_right = Inches(0.05)
                cell.margin_top = cell.margin_bottom = Inches(0.02)
                for p in cell.text_frame.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(size); run.font.name = "Calibri"
                        run.font.bold = r == 0
                        run.font.color.rgb = rgb("#ffffff" if r == 0 else "#1a1a1a")
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(head if r == 0 else ("#f4f7f9" if r % 2 else "#ffffff"))
        return t

    def kpi(s, x, y, w, big, small, label, color=NAVY):
        box(s, x, y, w, 1.45, fill="#ffffff", line="#c9d6df")
        text(s, x + 0.05, y + 0.05, w - 0.1, 0.62, big, 26, color, True)
        text(s, x + 0.05, y + 0.66, w - 0.1, 0.45, small, 11, "#333333")
        text(s, x + 0.05, y + 1.1, w - 0.1, 0.3, label, 9, GREY, True)

    def chart(s, x, y, w, h, cats, series, title, fmt='0.0', colors_=(NAVY, TEAL), maxv=None):
        cd = CategoryChartData(); cd.categories = cats
        for name, vals in series:
            cd.add_series(name, vals)
        gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
        ch = gf.chart
        ch.has_title = True; ch.chart_title.text_frame.text = title
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12); ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
        ch.has_legend = len(series) > 1
        if ch.has_legend:
            ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False; ch.legend.font.size = Pt(10)
        ch.value_axis.has_major_gridlines = False; ch.value_axis.tick_labels.font.size = Pt(9)
        if maxv:
            ch.value_axis.maximum_scale = maxv
        ch.value_axis.minimum_scale = 0
        ch.category_axis.tick_labels.font.size = Pt(10)
        pl = ch.plots[0]; pl.gap_width = 60; pl.has_data_labels = True
        pl.data_labels.number_format = fmt; pl.data_labels.number_format_is_linked = False; pl.data_labels.font.size = Pt(10)
        pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        for k, se in enumerate(pl.series):
            se.format.fill.solid(); se.format.fill.fore_color.rgb = rgb(colors_[k % len(colors_)])
        return ch

    # slide 1
    s = frame(1, "Heater C uses more fuel than its load needs, and nobody sees it in time",
              "One biomass thermic-fluid heater feeding the PET process · KPI: kg fuel per GJ useful heat (SFC)")
    text(s, 0.35, 1.8, 6.1, 2.6, [[("Organisation: ", True), (f"{C.SITE}. Heater C burns palm-kernel shell and heats the thermic fluid for the PET lines.", False)],
                                 [("Problem: ", True), ("fuel moisture varies, heating value is tested only now and then, and air and grate settings depend on the operator. Excess fuel is not visible during the shift.", False)],
                                 [("Decision-maker: ", True), ("the plant sponsor (budget), with the process engineer and shift lead acting daily.", False)],
                                 [("Midterm continuity: ", True), ("same heater, same problem, chosen over cutter trips. Fan and conveyor maintenance stays out of scope.", False)]], 14)
    kpi(s, 6.8, 1.8, 3.0, "65–70 %", "efficiency vs 85 % design (midterm estimate)", "MID · disclosure to be confirmed", "#c27c0e")
    kpi(s, 10.0, 1.8, 3.0, f"{C.f1(N['eta_median'])} %", f"synthetic median efficiency (P25–P75 {C.f1(N['eta_p25'])}–{C.f1(N['eta_p75'])})", "SYN · prototype")
    kpi(s, 6.8, 3.45, 3.0, f"{C.f1(N['baseline_sfc_median'])}", f"kg/GJ synthetic median SFC (P25–P75 {C.f1(N['baseline_sfc_p25'])}–{C.f1(N['baseline_sfc_p75'])})", "SYN · 18,655 rows, 132 lots")
    kpi(s, 10.0, 3.45, 3.0, f"≈{N['fuel_cost_base']/1e8:.2f} M", "THB per year for each 1 % of fuel", "FIC planning inputs", TEAL)
    text(s, 0.35, 5.25, 12.6, 1.6, [[("Business consequence: ", True), ("fuel is the heater's main running cost, and an unstable heater puts HTF supply to the PET process at risk.", False)],
                                    [("What is not claimed: ", True), ("the design gap is not fully recoverable. Fuel quality, fouling and equipment set part of it, and no real plant value is used here.", False)],
                                    [("Evidence: ", True), ("midterm figure = operational estimate (MID); final figures = synthetic prototype (SYN); cost = fictional planning input (FIC).", False)]],
         14, fill="#eef4f8", line="#c9d6df")
    # slide 2
    s = frame(2, "Process improvement and a simple rule first; AI only in a read-only shadow trial",
              "Four options compared on cost, data, evidence, risk, human role and reversibility")
    oc, orow = C.options(N)
    rows = [["Option", "Cost", "Data needed", "Evidence (synthetic test)", "Main risk", "Verdict"]] + [[r[0], r[2], r[3], r[4], r[5], r[8]] for r in orow]
    table_(s, 0.35, 1.8, 12.6, rows, [2.0, 2.6, 1.9, 3.4, 1.4, 1.3], 10.5, rowh=0.62)
    text(s, 0.35, 5.05, 6.2, 1.85, [[("Why not AI advice now? ", True), (f"AI names a move better ({N['ai_exact_pct']:.1f} % vs {N['rule_exact_pct']:.1f} % exact), but it raises false alerts on {N['ai_fa_pct']:.1f} % of no-change rows against {N['rule_fa_pct']:.1f} % for the rule. "
                                                                         f"The forecast gain is {C.f1(N['gain_vs_P2'])} %, below the 10 % rule, and the base case is {C.f0(N['net_base'])} THB/yr.", False)]], 14, fill="#fbf3e6", line="#e2c38f")
    text(s, 6.75, 5.05, 6.2, 1.9, [[("Data: ", True), ("read-only historian export (fuel, HTF flow and temperatures, O2, CO, draft, commands) plus lab assays per lot.", False)],
                                   [("Hosting and privacy: ", True), ("one offline site PC, localhost only, no cloud and no runtime AI service. Role IDs, never names. PDPA retention is set by the data protection officer.", False)]],
         14, fill="#eef4f8", line="#c9d6df")
    # slide 3
    s = frame(3, "The prototype passed its safety tests but failed on false alerts and coverage",
              f"{C.f0(N['test_rows'])} held-out synthetic rows; the same rows for every method; selection on validation, test scored once")
    chart(s, 0.35, 1.8, 4.3, 3.9, ["Last value", "Repeat feed", "Linear (AI)", "Boosting"], [("MAE kg/h", (N["mae_P"], N["mae_P2"], N["mae_L"], N["mae_C0"]))],
          "Forecast error, MAE kg/h (lower is better)", colors_=(TEAL,))
    chart(s, 4.75, 1.8, 4.3, 3.9, ["Exact best move", "Correct direction", "False alerts"],
          [("AI", (N["ai_exact_pct"], N["ai_direction_pct"], N["ai_fa_pct"])), ("Rule", (N["rule_exact_pct"], N["rule_direction_pct"], N["rule_fa_pct"]))],
          "Action ranking, % of rows", maxv=40)
    text(s, 9.2, 1.8, 3.8, 3.9, [[("Passed", True)], f"• Guardrails: NO ADVICE on {C.f0(N['shadow_no_advice'])} rows, 0 unsafe advice", f"• 90 % interval covered {C.f1(N['cov_L'])} %",
                                 f"• Exact move {N['ai_exact_pct']:.1f} % vs {N['rule_exact_pct']:.1f} % (was {ORIGINAL['ai_exact_pct']:.1f} % before the menu fix)",
                                 [("Failed", True)], f"• False alerts {N['ai_fa_pct']:.1f} % vs {N['rule_fa_pct']:.1f} % ({N['fa_per_shift']:.1f}/shift; target 1)",
                                 f"• Forecast gain {C.f1(N['gain_vs_P2'])} % (target 10 %)", f"• Eligible rows {N['eligible_share_pct']:.1f} % (target 60 %)"], 13, fill="#ffffff", line="#c9d6df")
    text(s, 0.35, 5.85, 12.6, 1.1, [[("Implication: ", True), ("the AI is not ready to advise operators. ", False), ("Saving not measurable: ", True),
                                    (f"at 21-day windows the smallest detectable change is {N['mde80_21d']:.1f} %, while the simulated effect is {N['sim_pct_opti']:.2f} %. ", False),
                                    ("Limits: ", True), ("synthetic data, associational action effects (not causal), and the generator and optimiser share physics, so these results are an upper bound.", False)]],
         13, fill="#fbeaec", line="#e3a5ad")
    # slide 4
    s = frame(4, "Operators keep full authority; AI electricity is tiny next to the simulated fuel effect",
              "People, oversight, principal risk and control · AI electricity vs potential savings")
    table_(s, 0.35, 1.8, 6.4, [["Role", "Authority / duty"], ["Operator", "Decides; acts only in the existing DCS; may reject with a coded reason"],
                               ["Shift lead", "Reviews; first escalation"], ["Process engineer", "Owns the model, reviews shadow results"],
                               ["EHS / OEM", "Veto on combustion safety; sign limits"], ["OT/IT, cyber, DPO", "Read-only export; logs; PDPA"],
                               ["Plant sponsor", "Accountable for GO / REVISE / STOP"]], [1.8, 4.6], 12, rowh=0.4)
    text(s, 0.35, 4.75, 6.4, 2.15, [[("Principal risk: ", True), ("advice that looks plausible but cuts air too far, leading to CO, unburnt fuel or unstable draft.", False)],
                                    [("Control: ", True), ("the gate defaults to NO ADVICE (21 reason codes), with an O2 floor plus margin, a CO margin, a draft band and ±4 % moves. Unsigned limits mean no advice, there is no write path, and this trial is shadow only.", False)]],
         14, fill="#fbeaec", line="#e3a5ad")
    kpi(s, 7.0, 1.8, 2.9, f"{N['kwh_6w_base']:.1f} kWh", f"AI electricity in 6 weeks (range {N['kwh_6w_opti']:.1f}–{N['kwh_6w_pess']:.1f})", "EST: measured run time × assumed W")
    kpi(s, 10.05, 1.8, 2.9, f"{C.f0(N['fuel_kwh_th'])} kWh", "simulated fuel energy in a 253-hour window (thermal)", "SYN illustration, not a saving", TEAL)
    kpi(s, 7.0, 3.4, 2.9, f"{N['sim_pct_opti']:.2f} %", f"simulated SFC effect, full realisation (base {N['sim_pct_base']:.2f} %)", "SYN × EST")
    kpi(s, 10.05, 3.4, 2.9, f"{N['breakeven_base']:.2f} %", "fuel saving needed to pay running cost (base)", "FIC / PUB inputs", "#c27c0e")
    text(s, 7.0, 5.05, 5.95, 1.85, ["Electrical kWh (PC) and thermal kWh (fuel) are shown apart and never added together.",
                                    f"FD-fan electricity avoided in the window: {N['fan_kwh']:.0f} kWh (SYN).",
                                    "No CO2 claim: the fuel is biogenic and emissions were not measured."], 14, fill="#eef4f8", line="#c9d6df")
    # slide 5
    s = frame(5, f"Approve a 6-week read-only shadow trial, {N['pilot_cost_opt']/1000:,.0f}–{N['pilot_cost_pess']/1000:,.0f}k THB, owned by the sponsor",
              "Scope: Heater C only · no supervised advice · no control writes · decision at week 6")
    box(s, 0.35, 1.8, 3.6, 0.55, fill=TEAL); text(s, 0.35, 1.83, 3.6, 0.5, "Weeks 1–2 · approvals and data", 12, "#ffffff", True, PP_ALIGN.CENTER)
    box(s, 3.95, 1.8, 7.2, 0.55, fill=NAVY); text(s, 3.95, 1.83, 7.2, 0.5, "Weeks 3–6 · read-only blind shadow, with the rule alert as comparator", 12, "#ffffff", True, PP_ALIGN.CENTER)
    box(s, 11.15, 1.8, 1.8, 0.55, fill="#c27c0e"); text(s, 11.15, 1.83, 1.8, 0.5, "Week 6 · gate", 12, "#ffffff", True, PP_ALIGN.CENTER)
    sc, srows = C.scorecard(N)
    table_(s, 0.35, 2.55, 7.6, [["Success criterion", "Now (SYN)", "Target"]] + [[r[0], r[1], r[2]] for r in srows], [3.3, 2.1, 2.2], 10.5, rowh=0.42)
    text(s, 8.15, 2.55, 4.8, 2.55, [[("Stop if: ", True)]] + [f"• {x}" for x in C.STOPS], 11.5, fill="#fbeaec", line="#e3a5ad")
    text(s, 8.15, 5.2, 4.8, 1.7, [[("Cost: ", True), (f"{thb(N['pilot_cost_opt'])}–{thb(N['pilot_cost_pess'])} (base {thb(N['pilot_cost_base'])}, EST). A CO analyser is extra and only if needed.", False)],
                                  [("Owner: ", True), ("plant sponsor (accountable); process engineer (responsible).", False)]], 13, fill="#eef4f8", line="#c9d6df")
    text(s, 0.35, 6.05, 7.6, 0.85, [[("GO", True), (" = all targets met, no stop → new request for supervised advice. ", False), ("REVISE", True),
                                     (" = recalibrate and repeat. ", False), ("STOP", True), (" = keep the process fixes and the rule. No saving will be claimed.", False)]],
         13, fill="#fbf3e6", line="#e2c38f")
    path = SUB / NAMES["deck"]
    prs.save(path)
    return path


# ------------------------------------------------------------------ registers / workbooks
def register(N):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    fills = {C.CV: "C8E6C9", C.CD: "DCEDC8", C.OT: "FFCDD2", C.OE: "FFE0B2", C.PL: "BBDEFB", C.STATUSES[5]: "EEEEEE"}

    def sheet(ws, cols, rows, widths):
        ws.append(cols)
        for r in rows:
            ws.append(r)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3B57")
        for row in ws.iter_rows(min_row=1):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "B2"

    ws = wb.active; ws.title = "Gap register"
    cols, rows = C.gap_register(N)
    sheet(ws, cols, rows, [7, 28, 40, 36, 30, 50, 28, 9, 30, 26])
    for r in range(2, ws.max_row + 1):
        st = ws.cell(r, 10).value
        ws.cell(r, 10).fill = PatternFill("solid", fgColor=fills.get(st, "FFFFFF"))
    ws2 = wb.create_sheet("Status summary")
    from collections import Counter
    cnt = Counter(r[9] for r in rows)
    sheet(ws2, ["Status", "Count", "IDs"], [[s, cnt.get(s, 0), ", ".join(r[0] for r in rows if r[9] == s)] for s in C.STATUSES] + [["Total", len(rows), ""]], [30, 8, 80])
    rc, rr = C.revalidation(N)
    sheet(wb.create_sheet("Revalidation"), rc, rr, [38, 24, 30, 14, 40, 32])
    oc, orow = C.options(N)
    sheet(wb.create_sheet("Options"), oc, orow, [20, 34, 26, 18, 36, 22, 18, 10, 24])
    sheet(wb.create_sheet("Decision ladder"), ["Path", "Evidence verdict", "Reason"], [list(x) for x in C.decision_ladder(N)], [30, 26, 90])
    rb = rubric(N)
    sheet(wb.create_sheet("Rubric matrix"), rb[0], rb[1], [30, 9, 60, 26, 50])
    path = SUB / NAMES["register"]
    wb.save(path)
    return path


def rubric(N):
    return (["Criterion", "Maximum", "Evidence", "Status", "Remaining correction"], [
        ["Problem and baseline", 10, "Proposal §2; Slide 1 (MID vs SYN labels)", "Submission content verified", "Student: confirm the midterm figures may be disclosed"],
        ["Options, choice and data", 20, "Proposal §3 table + choice + data/hosting/privacy; Slide 2", "Submission content verified", "-"],
        ["Test results", 10, "Proposal §4 + evidence table; Slide 3; Appendix A1, A4", "Submission content verified", "-"],
        ["People and oversight", 10, "Proposal §5; Slide 4 roles, risk, control", "Submission content verified", "-"],
        ["Sustainability", 10, "Proposal §5 table; Slide 4 kWh vs fuel", "Submission content verified", "Optional: meter the PC"],
        ["Request and trial plan", 15, "Proposal §1 and §6; Slide 5", "Submission content verified", "-"],
        ["Sources and AI use", 5, "Appendix A2 (two sources + market data), A3 (AI error, verified)", "Submission content verified", "-"],
        ["Presentation clarity and timing", 10, "Five slides; script ≈ 6 min at 140 wpm", "PENDING — LIVE ASSESSMENT", "Rehearse twice with a timer"],
        ["Discussion and committee feedback", 10, "15 prepared answers; feedback framework", "PENDING — LIVE ASSESSMENT", "Take part live; submit the Google Form feedback"]])


def business(N):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    src = ROOT / "reports" / "economics_and_energy.xlsx"
    wb = openpyxl.load_workbook(src)
    ws = wb.create_sheet("Market sources", 0)
    rows = [["Input", "Pessimistic", "Base", "Optimistic", "Unit", "Evidence label", "Source / note"],
            ["Electricity tariff", N["a_tariff_pess"], N["a_tariff_base"], N["a_tariff_opt"], "THB/kWh", "PUBLISHED", "Thai average tariff 2025–2026 (Nation Thailand 40049646, 40049419; Bangkok Post 2930806). Site TOU/demand tariff will differ."],
            ["Palm-kernel shell price", N["a_price_pess"], N["a_price_base"], N["a_price_opt"], "THB/t", "OWN-ESTIMATE", "Anchor 3,200 THB/t (arXiv:2406.00056 citing DEDE); FOB US$90–170/t listings. No Thai market quote found."],
            ["CO analyser allowance", N["a_co_an_pess"], N["a_co_an_base"], N["a_co_an_opt"], "THB", "OWN-ESTIMATE", "Equipment-only floors: in-situ zirconia O2 from CAD 3,085; portable O2/CO US$1,100–5,000. Installed cost needs a quote."],
            ["Operating hours", N["a_hours_pess"], N["a_hours_base"], N["a_hours_opt"], "h/yr", "ASSUMED", ""],
            ["Realisation share", N["a_real_pess"], N["a_real_base"], N["a_real_opt"], "fraction", "ASSUMED", "Synthetic effect × share"],
            [], ["Shadow-trial cost (no supervised advice)", N["pilot_cost_pess"], N["pilot_cost_base"], N["pilot_cost_opt"], "THB", "OWN-ESTIMATE", "eng days × day rate + 6 weeks × review h × rate"],
            ["Net annual effect if deployed", N["net_pess"], N["net_base"], N["net_opti"], "THB/yr", "FICTIONAL sensitivity", "From the Model sheet; base negative → no payback"],
            ["Break-even fuel saving", N["breakeven_pess"], N["breakeven_base"], N["breakeven_opti"], "% of fuel", "FICTIONAL sensitivity", "Compare with simulated effect"],
            ["Simulated effect", N["sim_pct_pess"], N["sim_pct_base"], N["sim_pct_opti"], "% of fuel", "SYNTHETIC × ASSUMED", "Generator illustration, not a saving"],
            ["AI electricity, 6 weeks", N["kwh_6w_pess"], N["kwh_6w_base"], N["kwh_6w_opti"], "kWh", "OWN-ESTIMATE", "Measured run time × assumed W"],
            [], ["SYNTHETIC / FICTIONAL ILLUSTRATION - NOT A SAVINGS CLAIM - NOT FOR PLANT OPERATION"]]
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3B57")
    for i, w in enumerate([34, 14, 14, 14, 10, 22, 90]):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    rc, rr = C.revalidation(N)
    ws2 = wb.create_sheet("Before-after", 1)
    for r in [rc] + rr:
        ws2.append(r)
    for i, w in enumerate([38, 24, 30, 14, 40, 32]):
        ws2.column_dimensions[chr(65 + i)].width = w
    path = SUB / NAMES["business"]
    wb.save(path)
    return path


def script_docx(N):
    def para(t, bold=False, size=22):
        runs = []
        for seg, b in (t if isinstance(t, list) else [(t, bold)]):
            rp = f"<w:rPr>{'<w:b/>' if b else ''}<w:sz w:val=\"{size}\"/></w:rPr>"
            runs.append(f"<w:r>{rp}<w:t xml:space=\"preserve\">{escape(seg)}</w:t></w:r>")
        return f"<w:p>{''.join(runs)}</w:p>"

    def tbl(rows):
        out = ["<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/><w:tblBorders>" +
               "".join(f"<w:{e} w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"999999\"/>" for e in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders></w:tblPr>"]
        for i, r in enumerate(rows):
            out.append("<w:tr>" + "".join(f"<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>{para(str(c), i == 0, 20)}</w:tc>" for c in r) + "</w:tr>")
        return "".join(out) + "</w:tbl>"

    S = C.script(N)
    words = sum(len(x[3].split()) for x in S)
    body = [para(f"Heater C AI Advisory — six-minute presentation script ({C.STUDENT}, {C.SID})", True, 32),
            para(f"{C.COURSE}. Five slides, 360 seconds, about {words} words (≈ {words/6:.0f} words per minute). SYNTHETIC DATA — NOT FOR PLANT OPERATION.", False, 20),
            tbl([["Slide", "Time", "Main message"]] + [[str(a), f"{b} s", c] for a, b, c, _ in S])]
    for a, b, c, t in S:
        body += [para(f"Slide {a} · {b} seconds · {c}", True, 26), para(t)]
    body += [para("Committee questions and answers", True, 30)]
    for i, (q, a) in enumerate(C.qa(N), 1):
        body += [para(f"{i}. {q}", True), para(a)]
    body += [para("Framework for written feedback on classmates' presentations (Google Form)", True, 30)]
    body += [para([(f"{k}: ", True), (v, False)]) for k, v in C.FEEDBACK]
    body += [para("Status: the live discussion and the feedback form are still to be done at the event; nothing here claims they are complete.", False, 20)]
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>"
           + "".join(body) + "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\" w:header=\"0\" w:footer=\"0\" w:gutter=\"0\"/></w:sectPr></w:body></w:document>")
    ct = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
          "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/>"
          "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>")
    rels = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>")
    path = SUB / NAMES["script"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("word/document.xml", xml)
    return path, words


# ------------------------------------------------------------------ validation and compliance reports
def validation_report(N):
    import pandas as pd
    st = styles(8.2)
    h = lambda t: P(t, st["h"])
    F = header(st, "Model validation report (supporting document)")
    mc = pd.read_csv(ROOT / "reports" / "model_comparison.csv")
    m = mc[(mc["population"] == "eligible_test") & (mc["segment"] == "ALL")][["model", "MAE", "RMSE", "coverage", "halfwidth"]]
    F += [h("1 Data and split"), P(f"{C.f0(N['raw_rows'])} raw synthetic rows; {C.f0(N['rows_total'])} after cleaning; {C.f0(N['lots_total'])} fuel lots; chronological, lot-aware train/validation/test split. "
                                   f"Test = {C.f0(N['test_rows'])} rows. Seeds 42 (main), 77 (stress), 101 (site style). Generator not changed in this audit.", st["b"]),
          h("2 Forecasting (next-interval fuel, held-out test)"),
          table([["Model", "MAE kg/h", "RMSE kg/h", "90 % coverage", "Half-width"]] + [[r.model, f"{r.MAE:.1f}", f"{r.RMSE:.1f}", "-" if pd.isna(r.coverage) else f"{100*r.coverage if r.coverage <= 1 else r.coverage:.1f} %",
                                                                                   "-" if pd.isna(r.halfwidth) else f"{r.halfwidth:.1f}"] for r in m.itertuples()],
                [3 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm], st),
          P(f"Selection on validation (critique fix K10). Linear model L chosen; gain vs repeat-current-feed {C.f1(N['gain_vs_P2'])} % is below the pilot's 10 % rule, so the simple forecast is the default.", st["b"]),
          h("3 Action ranking (AI vs rule, held-out test)")]
    sc = pd.read_csv(ROOT / "reports" / "scenario_comparison.csv")
    F += [table([["Method", "Subset", "Alerts", "Exact hit", "Direction", "False alert", "Precision"]] + [
        [r.method, r.subset, str(r.alerts), "-" if pd.isna(r.hit_rate_exact) else f"{100*r.hit_rate_exact:.1f} %", "-" if pd.isna(r.hit_rate_direction) else f"{100*r.hit_rate_direction:.1f} %",
         f"{100*r.false_alert_rate:.1f} %", "-" if pd.isna(r.precision_exact) else f"{100*r.precision_exact:.1f} %"] for r in sc.itertuples()], [4.5 * cm, 3.6 * cm, 1.4 * cm, 1.9 * cm, 1.9 * cm, 2 * cm, 1.9 * cm], st),
          h("4 Menu and threshold calibration (validation only, test scored once)")]
    cal = pd.read_csv(ROOT / "reports" / "menu_calibration.csv")
    F += [table([["Split", "Two-axis menu", "Min benefit", "Alerts", "Exact hit", "False alert", "Rule exact", "Rule FA"]] + [
        [r.split, "full grid" if pd.isna(r.combo_max_step_pct) else f"≤{int(r.combo_max_step_pct)} %", f"{r.min_benefit_sfc_kg_gj}", str(r.alerts), f"{100*r.hit_rate_exact:.1f} %",
         f"{100*r.false_alert_rate:.1f} %", f"{100*r.rule_hit_rate_exact:.1f} %", f"{100*r.rule_false_alert_rate:.1f} %"] for r in cal.itertuples()], [2.4 * cm] + [2.0 * cm] * 7, st),
          P(f"Pre-set rule: keep variants with validation false alerts ≤ the rule's, then highest exact hit. All variants passed because the rule's validation false-alert rate was {N['val_rule_fa_pct']:.0f} % "
            f"(test: {N['rule_fa_pct']:.1f} %); the constraint was lenient. The false-alert gap is therefore OPEN and must be calibrated on real shadow data; it was not tuned on test.", st["b"]),
          h("5 Guardrails"), P("21 reason codes; 23 gate tests cover missing sensors, stale or frozen data, transients, uncertain fuel properties, out-of-distribution states, unsigned limits; "
                               "an AST test confirms no DCS/PLC/OPC/Modbus write code. Placeholder limits force NO ADVICE in real mode.", st["b"]),
          h("6 Measurement and verification power")]
    pw = json.loads((ROOT / "reports" / "mv" / "mv_power.json").read_text(encoding="utf-8"))
    F += [table([["Days per window", "Pairs", "90 % half-width", "MDE 80 %", "A/A SD", "False saving"]] + [
        [str(w["window_days"]), str(w["pairs"]), f"±{w['hw90_pct']:.2f} %", f"{w['mde80_pct']:.2f} %", f"{w['aa_sd_pct']:.2f} %", f"{100*w['false_saving_share']:.0f} %"] for w in pw["windows"]],
        [2.8 * cm] * 6, st),
        P(f"Fit half-width = {pw['fit_hw90_pct']['a']:.2f} × days^{pw['fit_hw90_pct']['b']:.2f}. 42-day windows ≈ {N['mde80_42d']:.2f} %; 0.24 % needs ≈ {C.f0(N['days_for_024'])} days per window (extrapolated).", st["b"]),
        h("7 Original vs corrected")]
    rc, rr = C.revalidation(N)
    F += [table([rc] + rr, [4.6 * cm, 3.1 * cm, 3.5 * cm, 1.9 * cm, 3.4 * cm, 2.0 * cm], st),
          h("8 Limits"), P("Synthetic data only; action effects are associations; generator and optimiser share the combustion physics family, so action results are an upper bound; "
                           "bootstrap intervals cover coefficient uncertainty, not model misspecification; no causal or real-plant savings claim.", st["b"])]
    path = SUB / NAMES["validation"]
    doc(path, "Heater C Model Validation Report").build(F, onFirstPage=footer("Heater C model validation"), onLaterPages=footer("Heater C model validation"))
    return path


def verify(N, words):
    from pptx import Presentation
    from pypdf import PdfReader
    V = {}
    V["proposal_pages"] = len(PdfReader(SUB / NAMES["proposal"]).pages)
    V["appendix_pages"] = len(PdfReader(SUB / NAMES["appendix"]).pages)
    prs = Presentation(SUB / NAMES["deck"])
    V["slides"] = len(prs.slides)
    deck_text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame) + " " + " ".join(
        c.text for s in prs.slides for sh in s.shapes if getattr(sh, "has_table", False) and sh.has_table for r in sh.table.rows for c in r.cells)
    ptxt = " ".join(p.extract_text() for p in PdfReader(SUB / NAMES["proposal"]).pages)
    atxt = " ".join(p.extract_text() for p in PdfReader(SUB / NAMES["appendix"]).pages)
    V["proposal_sections"] = all(s in ptxt for s in ("1 Management request", "2 Problem and baseline", "3 Options and choice", "4 Test results", "5 People and sustainability", "6 Trial plan"))
    V["student_id_everywhere"] = all(C.SID in t for t in (ptxt, atxt, deck_text))
    notes = " ".join(s.notes_slide.notes_text_frame.text for s in prs.slides)
    keys = {"exact hit": f"{N['ai_exact_pct']:.1f} %", "rule exact": f"{N['rule_exact_pct']:.1f} %", "AI false alerts": f"{N['ai_fa_pct']:.1f} %",
            "rule false alerts": f"{N['rule_fa_pct']:.1f} %", "forecast gain": f"{C.f1(N['gain_vs_P2'])} %", "pilot cost low": thb(N["pilot_cost_opt"]), "pilot cost high": thb(N["pilot_cost_pess"]),
            "AI kWh": f"{N['kwh_6w_base']:.1f} kWh", "eligible": f"{N['eligible_share_pct']:.1f} %"}
    norm = lambda t: re.sub(r"\s+", " ", t)
    V["consistency"] = {k: {"proposal": v in norm(ptxt), "deck": v in norm(deck_text)} for k, v in keys.items()}
    V["consistency_ok"] = all(x["proposal"] and x["deck"] for x in V["consistency"].values())
    terms = [t.strip() for t in (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    blob = ptxt + atxt + deck_text + notes
    V["denylist_hits"] = [t for t in terms if re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", blob, re.I)]
    V["script_words"] = words
    V["script_minutes_at_140wpm"] = round(words / 140, 2)
    pdfd = SUB / "Heater_C_Final_Presentation.pdf"
    V["deck_pdf_pages"] = len(PdfReader(pdfd).pages) if pdfd.exists() else None
    junit = AUD / "junit.xml"
    if junit.exists():
        t = junit.read_text(encoding="utf-8")
        m = re.search(r'<testsuite[^>]*errors="(\d+)"[^>]*failures="(\d+)"[^>]*skipped="(\d+)"[^>]*tests="(\d+)"', t)
        if m:
            e, f_, s_, n = map(int, m.groups())
            V["pytest"] = {"tests": n, "failures": f_, "errors": e, "skipped": s_, "passed": n - f_ - e - s_}
    V["files"] = {k: (SUB / v).exists() for k, v in NAMES.items()}
    AUD.mkdir(parents=True, exist_ok=True)
    (AUD / "verification.json").write_text(json.dumps(V, indent=2), encoding="utf-8")
    return V


def compliance(N, V):
    st = styles(8.0)
    h = lambda t: P(t, st["h"])
    cols, rows = C.gap_register(N)
    from collections import Counter
    cnt = Counter(r[9] for r in rows)
    ok = lambda b: "PASS" if b else "FAIL"
    pt = V.get("pytest", {})
    tests_txt = f"{pt.get('passed', '?')} passed, {pt.get('failures', '?')} failed, {pt.get('skipped', '?')} skipped" if pt else "not recorded"
    F = header(st, "Final compliance report (supporting document)")
    F += [h("Quality gates"), table([["Gate", "Check", "Result", "Evidence"],
        ["1 Academic", "Proposal pages = 3", ok(V["proposal_pages"] == 3), f"pypdf: {V['proposal_pages']}"],
        ["1 Academic", "Slides = 5", ok(V["slides"] == 5), f"python-pptx: {V['slides']}; PDF render pages: {V['deck_pdf_pages']}"],
        ["1 Academic", "Six proposal elements present", ok(V["proposal_sections"]), "headings 1–6 found in the PDF text"],
        ["1 Academic", "Six-minute script", ok(4.5 <= V["script_minutes_at_140wpm"] <= 6.5), f"{V['script_words']} words ≈ {V['script_minutes_at_140wpm']} min at 140 wpm; live timing pending"],
        ["1 Academic", "Name and ID on every deliverable", ok(V["student_id_everywhere"]), "text search"],
        ["1 Academic", "Two sources with usage; one AI error", "PASS", "Appendix A2, A3"],
        ["2 Technical", "Pipeline reproducible; tests", ok(pt.get("failures", 1) == 0 and pt.get("errors", 1) == 0), tests_txt],
        ["2 Technical", "No test-set tuning", "PASS", "src/calibrate_menu.py selects on validation; test scored once"],
        ["2 Technical", "No unsupported causal claim", "PASS", "causal-limits statement; text uses 'association'"],
        ["3 Business", "Baseline, four options, owner, success, stop", "PASS", "Proposal §1–3, §6"],
        ["3 Business", "No invented positive ROI", "PASS", f"base net {C.f0(N['net_base'])} THB/yr reported"],
        ["4 Safety & confidentiality", "No denylisted names in deliverables", ok(not V["denylist_hits"]), f"hits: {V['denylist_hits'] or 'none'}"],
        ["4 Safety & confidentiality", "No control write path; human authority", "PASS", "AST test; RACI"],
        ["4 Safety & confidentiality", "Midterm figures cleared for disclosure", "OPEN — EXTERNAL DEPENDENCY", "student to confirm"],
        ["5 Sustainability", "kWh electricity vs thermal shown apart; no CO2 claim", "PASS", "Proposal §5; Slide 4"],
        ["6 Consistency", "Key numbers identical in proposal and deck", ok(V["consistency_ok"]), ", ".join(k for k, v in V["consistency"].items() if not (v["proposal"] and v["deck"])) or "all 9 keys match"],
        ["7 Rubric", "Matrix below", "see table", "live parts pending"]], [3.0 * cm, 6.2 * cm, 3.2 * cm, W - 12.4 * cm], st)]
    rb = rubric(N)
    F += [h("Rubric compliance (no mark is guaranteed)"), table([rb[0]] + [[str(c) for c in r] for r in rb[1]], [3.6 * cm, 1.5 * cm, 5.6 * cm, 3.4 * cm, W - 14.1 * cm], st)]
    F += [h("Gap register summary"), table([["Status", "Count", "IDs"]] + [[s, str(cnt.get(s, 0)), ", ".join(r[0] for r in rows if r[9] == s)] for s in C.STATUSES], [5 * cm, 1.5 * cm, W - 6.5 * cm], st),
          P(f"Full register: submission/{NAMES['register']} ({len(rows)} items: 24 checkpoints + {len(rows) - 24} extra gaps).", st["c"])]
    status = lambda k: "Ready for submission" if V["files"].get(k) else "Not ready: file missing"
    dl = [["Deliverable", "Status", "Verified by"],
          [NAMES["proposal"], "Ready subject to specified verification" if V["proposal_pages"] == 3 else "Not ready", "3 pages; six headings; numbers consistent. Verify: midterm-figure disclosure (X01)"],
          [NAMES["deck"], "Ready subject to specified verification" if V["slides"] == 5 else "Not ready", "5 slides; rubric tag and timing per slide; PowerPoint render. Verify: same midterm-figure check; rehearse timing"],
          [NAMES["appendix"], status("appendix"), f"{V['appendix_pages']} pages: test table + screenshot, two sources, AI error"],
          [NAMES["register"], status("register"), "openpyxl"], [NAMES["validation"], status("validation"), "built from report CSV/JSON"],
          [NAMES["business"], status("business"), "economics workbook + market sources"], [NAMES["script"], status("script"), f"{V['script_words']} words; Q&A; feedback framework"],
          [NAMES["compliance"], "Ready for submission", "this file"]]
    F += [h("Deliverable status"), table(dl, [6.4 * cm, 4.2 * cm, W - 10.6 * cm], st)]
    F += [h("Items requiring student action before submission"), P(
        "1 Confirm that the midterm figures (65–70 % efficiency, 85 % design, 20–30 % extra fuel) may be disclosed; otherwise delete them from the proposal and Slide 1 and rebuild. "
        "2 Your own files in submission/ (*_Raja_69900089BG*) carry pre-audit numbers, and final/ (numbers refreshed) still describes the pre-audit plan with supervised advice in week 5; submit the Heater_C_Final_* set instead. "
        "3 Open the deck in PowerPoint once and rehearse twice with a timer (target 6:00). "
        "4 Optional: install python-docx only if a styled script is needed (the plain .docx opens in Word). "
        "5 After the talk: take part in the discussion and submit the Google Form feedback.", st["b"])]
    path = SUB / NAMES["compliance"]
    doc(path, "Heater C Final Compliance Report").build(F, onFirstPage=footer("Heater C compliance"), onLaterPages=footer("Heater C compliance"))
    return path


def write_register_md(N):
    cols, rows = C.gap_register(N)
    L = ["# Gap-closure register (CP01–CP24 + extra gaps) - SYNTHETIC, NOT FOR PLANT OPERATION", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    L += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    rc, rr = C.revalidation(N)
    L += ["", "## Original vs corrected", "", "| " + " | ".join(rc) + " |", "|" + "---|" * len(rc)] + ["| " + " | ".join(r) + " |" for r in rr]
    (AUD / "gap_register.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def run():
    SUB.mkdir(exist_ok=True)
    AUD.mkdir(parents=True, exist_ok=True)
    N = build()
    save_map(N)
    out = [proposal(N), appendix(N), deck(N), register(N), business(N), validation_report(N)]
    sp, words = script_docx(N)
    out.append(sp)
    write_register_md(N)
    V = verify(N, words)
    out.append(compliance(N, V))
    V = verify(N, words)
    for p in out:
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size:,} bytes")
    print(json.dumps({k: V[k] for k in ("proposal_pages", "appendix_pages", "slides", "proposal_sections", "student_id_everywhere", "consistency_ok", "denylist_hits", "script_words", "deck_pdf_pages")}, ensure_ascii=False))
    return V


if __name__ == "__main__":
    run()
