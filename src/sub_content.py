"""Text content for the final submission set, built from src.sub_nums numbers. SYNTHETIC - NOT FOR PLANT OPERATION.
No company names, no person names other than the student author, no real plant values."""
from src.sub_nums import ORIGINAL

STUDENT, SID = "Raja Chairmapandi", "69900089BG"
COURSE = "2130511 AI Abstraction and Digital Technologies, Chula LGO"
TITLE = "Heater C AI Advisory: fuel-efficiency decision support for one biomass thermic-fluid heater"
SITE = "PET Resin Plant P (anonymized)"
STATUSES = ("CLOSED — VERIFIED", "CLOSED — DOCUMENTED", "OPEN — TECHNICAL", "OPEN — EXTERNAL DEPENDENCY", "PENDING — LIVE ASSESSMENT", "NOT APPLICABLE")
CV, CD, OT, OE, PL = STATUSES[:5]


def f0(v):
    return f"{v:,.0f}"


def f1(v):
    return f"{v:,.1f}"


def thb(v):
    return f"{v/1000:,.0f}k THB"


def gap_register(N):
    """CP01-CP24 plus extra gaps. Columns per the brief."""
    R = [
        ("CP01", "Repository and artifact integrity", "Pipeline stages generate..final rerun in this audit; full pytest run; 19 test files", "Docker image never built; earlier outputs carried pre-correction numbers",
         "Build needs network (rule 2); deliverables built before the audit", "Reran optimize, shadow, final; rebuilt the number map; added tests/test_audit_corrections.py and tests/test_submission.py",
         "src/pipeline.py, tests/", "High", "pytest -q (see sign-off); stage logs", CV),
        ("CP02", "Midterm-to-final continuity", "Brief states the midterm chose heater inefficiency (65–70 % vs 85 % design, 20–30 % extra fuel)",
         "Midterm deck not opened (company document); executive summary file not found", "Course and repository rule: company documents are not read by the AI tool",
         "Continuity paragraph uses only the figures given in the brief, labelled 'midterm operational estimate, disclosure to be confirmed'; same problem, same heater, fan/conveyor PdM kept out of scope",
         "Proposal p1, Slide 1", "High", "Read-through; disclosure check by the student", CD),
        ("CP03", "Business problem and numerical baseline", f"Synthetic SFC median {f1(N['baseline_sfc_median'])} kg/GJ; synthetic efficiency median {f1(N['eta_median'])} %",
         "Baseline evidence type had to be stated; design gap must not be called recoverable", "Earlier text mixed midterm and synthetic figures",
         "One paragraph: decision-maker, KPI (kg fuel per GJ useful heat), consequence (fictional fuel cost), labels SYNTHETIC vs midterm estimate; states only part of the gap is controllable",
         "Proposal p1, Slide 1", "High", "Number map lookup", CD),
        ("CP04", "Engineering calculation verification", "tests/test_energy_math.py, test_cleaning_engineering.py, test_combustion.py, test_synthetic_physics.py (HTF cp table, no water cp, kW = m·cp·ΔT, SFC, LHV, λ = 21/(21−O2))",
         "Fuel-to-PET normalisation not computable", "No PET production signal in the synthetic data", "Kept kg/GJ useful heat as KPI; PET normalisation listed as a site data item",
         "src/energy.py, src/combustion.py", "Medium", "Unit tests pass; dimensional checks in tests", CV),
        ("CP05", "Four-option comparison", "reports/06_options_comparison.md", "Comparison had to be redone after the corrected results", "Results changed in this audit",
         "New table: no change, process improvement, simple rule alert, AI; cost, data, evidence, risk, human role, reversibility, verdict", "Proposal p1, Slide 2", "High", "Read-through vs corrected numbers", CD),
        ("CP06", "AI incremental value", f"Forecast L MAE {f1(N['mae_L'])} vs P2 {f1(N['mae_P2'])} kg/h ({f1(N['gain_vs_P2'])} %)",
         "7.8 % is below the pilot's own 10 % threshold", "Forecast and decision quality were reported together", "Separated: forecast gain not operationally meaningful by the pilot rule (use the simple forecast unless real data show ≥10 %); decision quality judged on false alerts",
         "Proposal p2, Slide 3", "High", "Model comparison table", CD),
        ("CP07", "Synthetic-data integrity", "Seeds 42/77/101; chronological lot-aware split; 15 leakage tests; stress set; generator unchanged in this audit",
         "Generator and optimizer share the same combustion physics family (circularity)", "One author built both", "Stated: synthetic action results are an upper bound; real effect needs controlled tests",
         "reports/synthetic_data_card.md, reports/model_robustness.md", "Medium", "tests/test_model_leakage.py", CD),
        ("CP08", "Forecasting model validation", f"Selection on validation (critique fix K10); split-conformal 90 % interval, test coverage {f1(N['cov_L'])} %",
         "None new", "-", "Re-ran comparison; simpler linear model kept (boosting no better)", "src/train.py, reports/model_card.md", "Medium", "reports/model_comparison.csv", CV),
        ("CP09", "Action-effect and causal validity", "Ridge effect model + 200 lot bootstraps; causal-limits statement in reports/constraints_matrix.md",
         "Effects are associations", "Observational data; operators move FD with load", "No causal claim anywhere; approved controlled step tests listed as a precondition for any operational advice",
         "src/optimizer.py, src/compare.py", "High", "Text audit of the five main deliverables", CD),
        ("CP10", "Action-ranking and false-alert correction", f"Exact hit {ORIGINAL['ai_exact_pct']:.1f} % (AI) vs {N['rule_exact_pct']:.1f} % (rule)",
         "AI proposed large two-axis moves that the evaluation's action menu never contains, so exact hits were capped",
         "25-move grid larger than the generator's menu; no validation calibration of the menu or alert threshold",
         f"src/calibrate_menu.py: 8 variants on validation, rule fixed in advance; chosen {N['chosen_combo']} menu, min benefit {N['chosen_min_benefit']}; test scored once: exact hit {N['ai_exact_pct']:.1f} %, false alerts unchanged {N['ai_fa_pct']:.1f} %",
         "config/guardrail_limits.yaml, src/calibrate_menu.py", "High", "reports/menu_calibration.csv; tests/test_audit_corrections.py", CV),
        ("CP11", "Safety and guardrails", "21 NO_ADVICE reason codes; 23 gate tests (missing sensors, transient, OOD, uncertain LHV, stale data); AST test: no write path",
         "Real limits not signed", "No site config (rule 4)", "Unchanged: placeholder limits force NO_ADVICE in real mode", "src/guardrails.py", "High", "tests/test_advisory_gate.py", CV),
        ("CP12", "Data readiness", "Tag map template (40 site columns, 11 critical); data dictionary 106 columns; eligibility rules",
         f"Eligible coverage {f1(N['eligible_share_pct'])} % vs ≥60 % target; CO, air flow and per-lot LHV are the gaps", "CO often missing; lots without lab assay",
         "Coverage made a trial success criterion and a stop trigger; lab assay plan in weeks 1–2", "config/tag_map_template.yaml", "High", "Monitor eligible_pct", CD),
        ("CP13", "OT architecture and cybersecurity", "Read-only adapters; 127.0.0.1 binding; append-only hash-chained audit log; SECURITY_NOTES.md",
         "No authentication; container not built; retention not approved", "Needs site identity provider, network approval and DPO", "Listed as week-1–2 approvals in the trial", "SECURITY_NOTES.md, Dockerfile",
         "High", "Site OT/IT sign-off", OE),
        ("CP14", "Human oversight", "reports/07_RACI_and_safety_gate.md (12 roles, vetoes, escalation)", "Needed a one-paragraph version", "-",
         "Proposal p2 and Slide 4 name operator, shift lead, process engineer, EHS, OT/IT, lab and sponsor; reject/escalate path", "Proposal p2, Slide 4", "Medium", "Read-through", CD),
        ("CP15", "Financial business case", f"Workbook with live formulas; base net {f0(ORIGINAL['net_base'])} THB/yr (fictional inputs)",
         "Tariff and fuel price were placeholders", "No market anchor", "Tariff set from published Thai average tariff; fuel price anchored on a DEDE-cited figure; break-even recomputed; base case still negative",
         "src/economics.py", "High", "tests/test_audit_corrections.py; reports/economics_and_energy.xlsx", CV),
        ("CP16", "AI electricity and sustainability", f"{N['kwh_6w_base']:.1f} kWh per 6 weeks from measured run times × assumed watts", "PC power not metered", "No wattmeter",
         "Kept as OWN-ESTIMATE with a range; electrical kWh shown apart from thermal fuel kWh; no CO2 claim", "src/economics.py", "Low", "Formula check", CD),
        ("CP17", "Measurement and verification", f"A/A half-width ±{N['mv_hw_pct']:.2f} % (one retrospective split)", "No power analysis; six-week trial implied it could measure savings",
         "MDE never computed against duration", f"src/mv_power.py: MDE80 {N['mde80_21d']:.2f} % for 21-day windows, ≈{N['mde80_42d']:.1f} % for 42-day windows; 0.24 % needs ≈{f0(N['days_for_024'])} days per window. Trial objective changed: no saving claim",
         "src/mv_power.py, reports/mv/mv_power.md", "High", "tests/test_audit_corrections.py", CV),
        ("CP18", "Pilot scope, duration and cost", "docs/PILOT_SPEC.md six-week plan incl. supervised advice in week 5",
         "Supervised advice not justified by the corrected evidence; cost range mixed one-time items", "Plan written before the audit",
         f"Revised: 6 weeks, read-only shadow only; cost {thb(N['pilot_cost_opt'])}–{thb(N['pilot_cost_pess'])} (base {thb(N['pilot_cost_base'])}); analyser only if no usable CO",
         "Proposal p3, Slide 5", "High", "Formula in src/sub_nums.py", CD),
        ("CP19", "Success and stop conditions", "reports/pilot_scorecard.csv: 9 targets, 6 stops", "Needed synthetic baseline next to each target and a decision rule", "-",
         "One scorecard with baseline (synthetic), target, method, owner, rule; GO/REVISE/STOP defined", "Proposal p3", "High", "Read-through", CD),
        ("CP20", "Independent AI critique", "reports/ai_critique_log.md: 20 findings, 5 genuine errors fixed", "Fresh review needed", "-",
         "This audit found the action-menu mismatch (CP10) and the missing power analysis (CP17); both corrected; one error documented in the appendix", "Appendix A3", "Medium", "Before/after numbers", CD),
        ("CP21", "References and evidence provenance", "Two published method sources; number maps", "Market inputs had no source", "-",
         "Added published tariff/price/analyser sources; every number in the new set logged in submission/number_source_map_final.csv", "Appendix A2", "Medium", "tests/test_submission.py", CD),
        ("CP22", "Three-page proposal", "final/Heater_C_Final_Proposal.pdf (2 pages, pre-audit numbers)", "Needed exactly three pages with the six elements and corrected numbers", "-",
         "submission/Heater_C_Final_AI_Solution_Proposal.pdf", "src/sub_build.py", "High", "pypdf page count = 3; text check for six headings", CV),
        ("CP23", "Five-slide presentation", "final/Heater_C_Final_Deck.pptx (pre-audit)", "Rubric tags, corrected numbers, timing", "-",
         "submission/Heater_C_Final_Presentation.pptx, 5 slides, rubric tag and timing on each, notes = script", "src/sub_build.py", "High", "python-pptx count; PowerPoint render; script word count", CV),
        ("CP24", "Appendix and final compliance audit", "final/Appendix.pdf (pre-audit)", "Needed corrected evidence and the compliance matrix", "-",
         "submission/Heater_C_Final_Appendix.pdf and Heater_C_Final_Compliance_Report.pdf", "src/sub_build.py", "High", "tests/test_submission.py", CV),
        # extra gaps
        ("X01", "Midterm figures cleared for disclosure", "Figures given in the brief", "Not confirmed as approved for a public academic submission", "Operational observations",
         "Labelled; student to confirm with the company or remove before submission", "Proposal p1, Slide 1", "High", "Student confirmation", OE),
        ("X02", "AI false alerts above the rule", f"AI {N['ai_fa_pct']:.1f} % vs rule {N['rule_fa_pct']:.1f} %; {N['fa_per_shift']:.2f}/shift vs ≤1 target",
         "Not closed by the validation calibration", f"Validation rule false-alert rate ({N['val_rule_fa_pct']:.0f} %) was far above test, so the pre-set constraint was lenient",
         "Not re-tuned on test. Threshold to be recalibrated on real shadow data; supervised advice withheld", "config/guardrail_limits.yaml", "High", "Shadow false alerts per shift", OT),
        ("X03", "Eligible-window coverage below target", f"{f1(N['eligible_share_pct'])} % vs ≥60 %", "Few hours can receive advice", "CO missing, transients, unassayed lots",
         "Trial success criterion and stop trigger; CO availability checked in week 1", "src/guardrails.py", "High", "Monitor eligible_pct on site data", OE),
        ("X04", "Forecast gain below the pilot's 10 % rule", f"{f1(N['gain_vs_P2'])} %", "Pilot rule says choose simple", "-", "Decision recorded: simple forecast is the default; AI forecast only if real data show ≥10 %",
         "Proposal p2", "Medium", "Weekly MAE comparison", CD),
        ("X05", "Signed operating limits", "Placeholder envelopes", "No real limits", "Needs OEM/EHS", "Real mode forces NO_ADVICE until signed", "config/site_config", "High", "Signed site config", OE),
        ("X06", "Dashboard authentication and identity", "Role IDs typed by the user", "Not attributable", "No site identity provider", "Week-1–2 approval item", "src/dashboard", "Medium", "OT/IT review", OE),
        ("X07", "Container image not built", "Dockerfile, compose file", "Build untested", "Needs network approval", "Docker test skipped and reported", "Dockerfile", "Low", "docker build", OE),
        ("X08", "PC electricity not metered", "Assumed 35–100 W", "Estimate only", "No meter", "Plug-in meter reading in week 1", "src/economics.py", "Low", "Meter reading", OE),
        ("X09", "Fuel price and analyser cost not quoted", "Published anchors only", "No Thai PKS market quote; no installed CO quote", "Procurement data", "Ranges kept; quotes in week 1–2", "src/economics.py", "Medium", "Vendor quote", OE),
        ("X10", "Fuel per tonne PET", "-", "Not computable", "No production data", "Site data item", "-", "Low", "Historian export", OE),
        ("X11", "Earlier deliverables carry pre-audit numbers", "final/, the 50-slide deck and the student's own submission/*_Raja_* files", "Numbers differ (e.g. exact hit 9.0 %, −155k THB)", "Built before the audit",
         "final/ and the 50-slide deck rebuilt with corrected numbers (final/ text keeps the pre-audit week-5 supervised-advice plan); the student's own files are not overwritten; submit the Heater_C_Final_* set", "submission/", "High", "File list in the sign-off", CD),
        ("X12", "Pandas warning in the stale-data check", "FutureWarning on fillna of a float column", "Would break on a future pandas", "Type mismatch", "Cast to string before fill", "src/guardrails.py", "Low", "pytest warnings", CV),
        ("X13", "Live talk, discussion and classmate feedback", "Script and Q&A prepared", "Cannot be done in advance", "Live event", "Feedback framework prepared", "-", "High", "Course event, Google Form", PL),
    ]
    cols = ["ID", "Requirement", "Existing evidence", "Gap", "Root cause", "Correction", "Affected file/module", "Priority", "Verification method", "Status"]
    return cols, [list(r) for r in R]


def revalidation(N):
    o = ORIGINAL
    T = [
        ("Clean rows (data quality)", f0(N["rows_total"]), f0(N["rows_total"]), "0", "No change to cleaning", "data/clean/clean_report.json"),
        ("Eligible-window coverage", f"{N['eligible_share_pct']:.1f} %", f"{N['eligible_share_pct']:.1f} %", "0", "Guardrails unchanged; still below the 60 % target", "reports/final_numbers.csv"),
        ("Forecast MAE, model L (test)", f"{N['mae_L']:.1f} kg/h", f"{N['mae_L']:.1f} kg/h", "0", "Forecast not retrained; selection already on validation", "reports/model_comparison.csv"),
        ("Gain vs simple P2", f"{N['gain_vs_P2']:.1f} %", f"{N['gain_vs_P2']:.1f} %", "0", "Below the 10 % pilot rule", "same"),
        ("90 % interval coverage (test)", f"{N['cov_L']:.1f} %", f"{N['cov_L']:.1f} %", "0", "Conformal calibration unchanged", "same"),
        ("AI exact-action hit (actionable rows)", f"{o['ai_exact_pct']:.1f} %", f"{N['ai_exact_pct']:.1f} %", f"{N['ai_exact_pct']-o['ai_exact_pct']:+.1f} pp", "Menu fixed on validation; test scored once", "reports/menu_calibration.csv"),
        ("AI correct direction", f"{o['ai_direction_pct']:.1f} %", f"{N['ai_direction_pct']:.1f} %", f"{N['ai_direction_pct']-o['ai_direction_pct']:+.1f} pp", "Same cause", "reports/scenario_comparison.csv"),
        ("AI precision (exact)", f"{o['ai_precision_pct']:.1f} %", f"{N['ai_precision_pct']:.1f} %", f"{N['ai_precision_pct']-o['ai_precision_pct']:+.1f} pp", "Same alerts, better-named actions", "same"),
        ("Rule exact hit (default FD−4)", f"{o['rule_exact_pct']:.1f} %", f"{N['rule_exact_pct']:.1f} %", "0", "Comparator unchanged", "same"),
        ("AI false-alert rate", f"{o['ai_fa_pct']:.1f} %", f"{N['ai_fa_pct']:.1f} %", "0", "Not fixed: same rows alerted; stays OPEN", "same"),
        ("Rule false-alert rate", f"{o['rule_fa_pct']:.1f} %", f"{N['rule_fa_pct']:.1f} %", "0", "Comparator unchanged", "same"),
        ("Guardrail tests", "23 / 23", "23 / 23", "0", "Re-run", "tests/test_advisory_gate.py"),
        ("M&V A/A half-width (retrospective)", f"±{o['mv_hw_pct']:.2f} %", f"±{N['mv_hw_pct']:.2f} %", "0", "Same estimator", "reports/mv/mv_retrospective.json"),
        ("Minimum detectable effect, 80 % power", "not computed", f"{N['mde80_21d']:.2f} % (21 d) / ≈{N['mde80_42d']:.1f} % (42 d)", "new", "Power analysis added", "reports/mv/mv_power.json"),
        ("Simulated SFC effect, full realisation", f"{o['sim_full_pct']:.2f} %", f"{N['sim_pct_opti']:.2f} %", f"{N['sim_pct_opti']-o['sim_full_pct']:+.2f} pp", "Smaller two-axis moves", "reports/economics_summary.csv"),
        ("Simulated thermal fuel energy (253 h)", f"{f0(o['fuel_kwh_th'])} kWh", f"{f0(N['fuel_kwh_th'])} kWh", f"{N['fuel_kwh_th']-o['fuel_kwh_th']:+,.0f} kWh", "Same cause", "same"),
        ("FD fan electricity avoided (253 h)", f"{-o['fan_kwh']:.1f} kWh", f"{N['fan_kwh']:.1f} kWh", f"{N['fan_kwh']+o['fan_kwh']:+.1f} kWh", "Same cause", "same"),
        ("AI electricity, 6 weeks (base)", f"{N['kwh_6w_base']:.2f} kWh", f"{N['kwh_6w_base']:.2f} kWh", "0", "Run times unchanged", "same"),
        ("Electricity tariff (base)", f"{o['tariff_base']:.2f} THB/kWh (fictional)", f"{N['a_tariff_base']:.2f} THB/kWh (published)", f"{N['a_tariff_base']-o['tariff_base']:+.2f}", "Market anchor", "src/economics.py"),
        ("Fuel price (base)", f"{f0(o['price_base'])} THB/t (fictional)", f"{f0(N['a_price_base'])} THB/t (own estimate)", f"{N['a_price_base']-o['price_base']:+,.0f}", "Market anchor", "src/economics.py"),
        ("Net annual effect (base)", f"{f0(o['net_base'])} THB/yr", f"{f0(N['net_base'])} THB/yr", f"{N['net_base']-o['net_base']:+,.0f}", "Still negative: no payback", "reports/economics_summary.csv"),
        ("Break-even fuel saving (base)", f"{o['breakeven_base_pct']:.2f} %", f"{N['breakeven_base']:.2f} %", f"{N['breakeven_base']-o['breakeven_base_pct']:+.2f} pp", "Higher fuel price lowers break-even", "same"),
        ("Tests", f"{o['tests_passed']} passed, {o['tests_skipped']} skipped", "see sign-off", "+ new tests", "Audit tests added", "pytest"),
    ]
    return ["Metric", "Original", "Corrected", "Difference", "Explanation", "Evidence"], [list(t) for t in T]


def options(N):
    return (["Option", "What it is", "Cost", "Data needed", "Evidence of benefit", "Main risk", "Human role", "Reversible", "Verdict"], [
        ["1 No change", "Keep today's operation", "0", "None", f"None; SFC stays at the baseline ({f1(N['baseline_sfc_median'])} kg/GJ, synthetic)", "Excess fuel continues unseen", "Operator as today", "-", "Not chosen"],
        ["2 Process improvement", "Lab LHV/moisture per fuel lot, O2 target SOP, fuel storage, training", "Low (lab tests, training time; ASSUMED)", "Lab assays", "Not quantified here; removes the biggest data gap", "Low", "Operator, lab", "Yes", "Do first"],
        ["3 Simple automation", "Rule alert when SFC > P75 of its load band", "Low (historian rule)", "Fuel, heat, load", f"Alerts {f0(N['rule_alerts'])}; false alerts {N['rule_fa_pct']:.1f} %; no action named", "Few actionable hints", "Operator decides", "Yes", "Adopt as comparator and fallback"],
        ["4 AI-assisted", "Forecast + ranked FD/grate options inside guardrails", f"Pilot {thb(N['pilot_cost_opt'])}–{thb(N['pilot_cost_pess'])}; base net {f0(N['net_base'])} THB/yr", "+ O2, CO, lots, commands",
         f"Exact action {N['ai_exact_pct']:.1f} % vs {N['rule_exact_pct']:.1f} %; false alerts {N['ai_fa_pct']:.1f} %", "Plausible but wrong advice", "Operator decides; EHS veto", "Yes (read-only)", "Shadow validation only"],
    ])


def decision_ladder(N):
    return [("Process improvement", "SUPPORTED", "Cheap, reversible, fixes the lot-assay gap that blocks every other option."),
            ("Simple automation (rule alert)", "SUPPORTED", f"Fewer false alerts ({N['rule_fa_pct']:.1f} %) than AI; needed as the comparator."),
            ("AI shadow validation", "SUPPORTED, CONDITIONAL", "Read-only, 6 weeks, hard stop; tests whether real data reach the coverage and false-alert targets."),
            ("Supervised advisory", "NOT SUPPORTED NOW", f"AI false alerts {N['ai_fa_pct']:.1f} % vs rule {N['rule_fa_pct']:.1f} %; limits unsigned; effects are associations."),
            ("Larger deployment", "NOT SUPPORTED", f"Base case {f0(N['net_base'])} THB/yr; savings not measurable in a short trial."),
            ("No further investment", "FALLBACK", "The right answer if the shadow trial misses its targets or a stop condition fires.")]


def scorecard(N):
    return (["Criterion", "Synthetic result now", "Trial target", "Method", "Owner (role)", "Rule"], [
        ["Data quality / eligible windows", f"{N['eligible_share_pct']:.1f} %", "≥ 60 %", "Guardrail eligibility on site export", "OT/IT + process eng.", "Miss → REVISE"],
        ["Forecast vs simple regression", f"{N['gain_vs_P2']:.1f} % better", "≥ 10 % better", "Weekly MAE, frozen comparator", "Process eng.", "Miss → use simple"],
        ["Action quality (shadow, blind)", f"exact {N['ai_exact_pct']:.1f} %", "≥ rule + 10 pp, judged by engineer", "Engineer review sample", "Process eng.", "Miss → REVISE"],
        ["False alerts", f"{N['fa_per_shift']:.2f}/shift; {N['ai_fa_pct']:.1f} %", "≤ 1/shift and ≤ rule", "Operator 'no change needed' marks", "Shift lead", "> 3/shift 1 week → STOP"],
        ["Safety", "0 unsafe in replay", "0 unsafe; guardrail re-check 100 %", "EHS review of every record", "EHS lead", "Any → STOP"],
        ["Measurement feasibility", f"MDE80 {N['mde80_21d']:.1f} % at 21 days", "Report MDE; no saving claim", "A/A on site data", "Energy manager", "Plan next M&V or STOP"],
        ["Cost and schedule", "-", f"≤ {thb(N['pilot_cost_pess'])}; 6 weeks", "Time sheets", "Sponsor", "Overrun → REVISE"],
    ])


STOPS = ["Any safety or OT incident linked to the pilot", "Any guardrail failure (unsafe state yields advice, or re-check differs)",
         "Critical data invalid > 3 consecutive days", "Forecast worse than the simple regression 2 weeks in a row",
         "False alerts > 3 per shift for 1 week", "Any approval withdrawn or unavailable"]


def qa(N):
    return [
        ("Why use AI rather than a rule-based system?", f"Only where it adds something the rule cannot: naming a bounded move. On synthetic data it names the exact best move on {N['ai_exact_pct']:.1f} % of actionable rows against {N['rule_exact_pct']:.1f} % for the rule, but it raises more false alerts ({N['ai_fa_pct']:.1f} % vs {N['rule_fa_pct']:.1f} %). So the rule stays as the fallback and the AI is only shadow-tested."),
        ("What evidence supports the baseline?", f"Two kinds, kept apart: the midterm operational estimate (65–70 % efficiency vs 85 % design), which still needs disclosure confirmation, and the synthetic baseline ({f1(N['baseline_sfc_median'])} kg/GJ median, {f1(N['eta_median'])} % efficiency), which is computed by code. Neither is a measured plant value."),
        ("Are the results based on real plant data?", "No. Every result is from synthetic data. No plant data, HMI, P&ID or interlock document was read by the AI tool."),
        ("Why did the AI action ranking perform poorly?", f"Before this audit it proposed large two-axis moves the evaluation menu never contains, which capped exact hits at {ORIGINAL['ai_exact_pct']:.1f} %. A validation-only menu fix raised it to {N['ai_exact_pct']:.1f} %. The effect model is still smooth and associational, so compound moves are often mis-ranked."),
        ("Why are AI false alerts higher?", f"The AI raises advice whenever the pessimistic predicted change is below zero ({f0(N['ai_alerts'])} alerts vs {f0(N['rule_alerts'])}). Validation suggested a stricter threshold was not needed because the rule's validation false-alert rate was {N['val_rule_fa_pct']:.0f} %. I did not re-tune on test; the threshold must be set on real shadow data."),
        ("What is the significance of the forecasting improvement?", f"Small. {f1(N['gain_vs_P2'])} % lower error than repeating the current feed, below the 10 % rule I set, so the simple forecast is the default."),
        ("What prevents unsafe operating recommendations?", "Guardrails run before the optimizer: 21 NO_ADVICE reason codes, O2 floor plus margin, CO margin, draft band, ±4 % move limit, out-of-distribution check. Unsigned limits force NO_ADVICE. There is no write path to the DCS; the operator decides."),
        ("What happens if operators reject the advice?", "Nothing changes in the plant. The rejection and a coded reason are logged; repeated rejections count as false alerts and can stop the trial."),
        ("Why is the financial base case negative?", f"The simulated effect ({N['sim_pct_base']:.2f} % of fuel, base) is below the break-even saving ({N['breakeven_base']:.2f} %) needed to pay running costs, so the base net is {f0(N['net_base'])} THB/yr. Inputs are fictional or market-anchored, not plant economics."),
        ("How will actual fuel savings be measured?", "Load- and moisture-normalised SFC, matched load × moisture cells, lot-cluster bootstrap 90 % interval; a saving is claimed only if the interval excludes zero."),
        ("Can the proposed trial detect the expected effect?", f"No. At 21-day windows the smallest detectable change at 80 % power is {N['mde80_21d']:.1f} %; the simulated effect is about {N['sim_pct_opti']:.2f} %. That is why the trial claims no saving."),
        ("What would cause the project to stop?", "Any of the six stop conditions on page 3, or missing the coverage and false-alert targets at week 6."),
        ("What company approvals are required?", "Sponsor, OT/IT and cybersecurity (read-only export), EHS and OEM (signed limits), MOC, data protection officer (operator logs), and clearance of the midterm figures for disclosure."),
        ("What did AI get wrong during development?", "It compared the forecast with the wrong simple reference, which inflated the gain from 4 % to 21 %. I found it by adding the 'repeat current feed' reference; the true gain is 7.8 % with the simpler linear model."),
        ("What is the management decision today?", f"Approve process improvement and the rule alert now, and a 6-week read-only AI shadow trial costing {thb(N['pilot_cost_opt'])}–{thb(N['pilot_cost_pess'])}, with GO/REVISE/STOP at week 6. Do not approve supervised advice or deployment."),
    ]


FEEDBACK = [("Problem", "Is there one specific problem with a number and a stated source?"),
            ("Options", "Were no change, process change and simple automation compared fairly with AI?"),
            ("Test", "Was there a real test with a comparator and at least one reported failure?"),
            ("People and sustainability", "Who decides, what is the main risk and control, and are kWh and savings both quantified?"),
            ("Request", "Is the ask specific: scope, time, cost, owner, success and stop?"),
            ("One strength, one question", "Write one concrete strength and one question you would ask as the approving manager.")]


def script(N):
    return [
        (1, 60, "What is the business problem?",
         f"I'm Raja, and this proposal is about Heater C at {SITE}. It's one biomass heater burning palm-kernel shell, and it supplies hot thermic fluid to the PET process. "
         f"In my midterm I chose heater inefficiency over cutter trips. The operational estimate was 65 to 70 percent efficiency against 85 percent design, and that figure is still waiting for disclosure clearance. "
         f"For this final I built a synthetic copy of the heater. Its median efficiency is {f1(N['eta_median'])} percent and its fuel use is {f1(N['baseline_sfc_median'])} kilograms per gigajoule of useful heat. "
         f"The consequence is fuel cost. On fictional inputs one percent of fuel is worth about {N['fuel_cost_base']/100/1e6:.1f} million baht a year. "
         "I am not claiming the whole design gap can be recovered. Part of it is fuel quality and equipment, and those are outside an operator's control."),
        (2, 75, "Why this option rather than a simpler alternative?",
         "I compared four options. Doing nothing keeps the waste invisible. Process improvement means testing every fuel lot for moisture and heating value, plus a clear oxygen target in the SOP. It's cheap, it's reversible, and it closes the biggest data gap. "
         f"Simple automation is a rule that alerts when fuel use is above its normal band. It gives {N['rule_fa_pct']:.0f} percent false alerts, but it can't say what to change. "
         f"AI adds one thing: it names a bounded fan or grate move. On synthetic data it names the right move {N['ai_exact_pct']:.0f} percent of the time against {N['rule_exact_pct']:.0f} percent for the rule. But it also raises almost twice the false alerts. "
         "So my choice is process improvement and the rule now, and AI only in a read-only shadow test. The data stays on a site PC, read-only from the historian, and no personal names are stored."),
        (3, 90, "What did the prototype prove, and what failed?",
         f"I tested on {f0(N['test_rows'])} held-out five-minute rows the model never saw. "
         f"For forecasting, the linear model's error is {f1(N['mae_L'])} kilograms per hour against {f1(N['mae_P2'])} for simply repeating the current feed. That's {f1(N['gain_vs_P2'])} percent better, which is below my own 10 percent rule, so the simple forecast stays the default. "
         f"For actions, the AI and the rule saw the same rows. The AI's exact-move hit rate is {N['ai_exact_pct']:.1f} percent against {N['rule_exact_pct']:.1f}. "
         f"That was {ORIGINAL['ai_exact_pct']:.1f} percent before this audit. The AI was proposing large combined moves that the test menu never contains. I fixed the menu using validation data only, and then scored the test set once. "
         f"The failure is false alerts: {N['ai_fa_pct']:.1f} percent against {N['rule_fa_pct']:.1f} for the rule, which is about {N['fa_per_shift']:.0f} per shift against a target of one. Only {N['eligible_share_pct']:.0f} percent of hours are even eligible for advice. "
         "The business implication is that the AI isn't ready to advise operators yet."),
        (4, 60, "Who is accountable, and what is the sustainability impact?",
         "The operator keeps full authority and makes every change in the existing control system. The tool can't write to it. The shift lead reviews, the process engineer owns the model, EHS has a veto on anything touching combustion safety, and the plant sponsor is accountable for the decision. "
         "The main risk is advice that looks plausible but lowers oxygen too far. The control is a safety gate that defaults to no advice, plus an oxygen floor, a CO margin and a four percent move limit. "
         f"On sustainability, running the AI uses about {N['kwh_6w_base']:.1f} kilowatt-hours of electricity in six weeks. The simulated fuel effect is {f0(N['fuel_kwh_th'])} kilowatt-hours of thermal energy in 253 hours. That's an illustration, not a saving, and I make no carbon claim."),
        (5, 75, "What decision is requested, and when should the project stop?",
         f"My request is to approve a six-week, read-only shadow trial on Heater C only, costing {thb(N['pilot_cost_opt'])} to {thb(N['pilot_cost_pess'])}, with a base of {thb(N['pilot_cost_base'])}. The plant sponsor owns it. "
         "Weeks one and two are approvals, the tag walk-down, the lab assay plan and the historian export. Weeks three to six are blind shadow review. "
         "Success means at least 60 percent eligible windows, at most one false alert per shift and no worse than the rule, zero unsafe records, and forecast error at least 10 percent below the simple model. "
         "It stops on any safety or OT incident, any guardrail failure, three days of bad data, a week above three false alerts per shift, or a lost approval. "
         f"The trial won't claim a fuel saving, because it can only detect about {N['mde80_21d']:.0f} percent. At week six the sponsor decides go, revise or stop."),
    ]
