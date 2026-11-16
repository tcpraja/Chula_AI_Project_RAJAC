"""Speaker notes and markdown documents for final/. All metrics come from src.final_nums (ledger-registered)."""
import re
from pathlib import Path

from src.final_pdf import critique_item, nums

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "final"
WPM = 135  # assumed speaking pace for timing (words per minute)


def words(t):
    return len(re.findall(r"\S+", t))


def speaker_notes(D, L):
    n = nums(D, L)
    return [
        # 1 organization / problem / baseline
        f"Good morning. I study one biomass thermic-fluid heater, Heater C, at an anonymized PET resin plant. The heater is reported to burn more fuel than its design benchmark, "
        f"and the people running it make different air and grate choices from shift to shift. The question I tested is small: can a tool spot avoidable fuel use and suggest a safe, small move, "
        f"better than a simple rule? Everything you will see is synthetic: a method check, not a result about the plant. "
        f"On the synthetic heater the baseline is a specific fuel consumption of {n.sfc_med} kilograms of fuel per gigajoule of useful heat, with a middle band of {n.sfc_p25} to {n.sfc_p75}. "
        f"Only {n.elig} percent of the rows were clean enough to give advice at all. The company's own baseline still has to be validated, with measured fuel mass and assayed heating value. "
        f"That is why this proposal asks for a read-only pilot, not for savings.",
        # 2 options / choice
        f"I compared four options. One, change nothing. Two, a process change: a written guide and more fuel heating-value tests. Three, simple automation: a rule that alerts when fuel use is high for the load, plus a small regression. "
        f"Four, an AI advisory that forecasts fuel and ranks small simulated moves of the fans and grate. The AI has to earn its place, so the choice is to run options two and three first and keep option four in shadow. "
        f"It would stay only if its forecast error is at least ten percent better than the simple regression on real data. The data would come from a read-only historian export plus laboratory results for each fuel lot. "
        f"It runs offline on a site computer, with no cloud and no connection that could write to the plant. For privacy, operators appear only as role identifiers, and notes carry no names. "
        f"Simplicity is a feature: operators must trust every part.",
        # 3 results
        f"Here is what the tests showed, on later fuel lots the models had never seen. The fuel forecast error in kilograms per hour was {n.mae_B} for a two-variable regression, {n.mae_P2} for simply repeating the current feed, "
        f"{n.mae_L} for a linear model with all features, and {n.mae_C0} for boosted trees. So machine learning added nothing over the linear model, and I chose the linear one. "
        f"For ranking simulated moves, the AI found the exact best move on {n.ai_hit} percent of actionable rows against {n.rule_hit} percent for the rule, "
        f"but it raised false alerts on {n.ai_fa} percent of rows against {n.rule_fa} percent. The AI is not clearly better. "
        f"One failure mattered: my first reference was too weak, which made the model look {n.L_vs_P} percent better. A critic review caught it. "
        f"With the fair reference the gain is {n.L_vs_P2} percent, and I now select models on validation rows only. This is honest evidence for a modest pilot, not for a rollout.",
        # 4 people & sustainability
        f"Operators stay in charge. The screen shows NO ADVICE by default and gives advice only when every safety check passes, with reason codes and an uncertainty interval. "
        f"The shift supervisor records each decision, the safety lead re-checks every advisory, and the energy manager measures the effect. Operators spend at most two minutes per review. "
        f"The main risk is an operator following a wrong suggestion. The control is that it is advisory only, the safety system and trips are untouched, and unsafe recommendations must be zero. "
        f"On energy, the AI itself needs about {n.kwh6_base} kilowatt-hours over six weeks: watts times measured seconds, with the watts assumed because I had no meter. "
        f"The synthetic fuel-energy change over a {n.win_h}-hour replay is {n.fuel_pt} thermal kilowatt-hours, roughly {n.ratio} times larger, but that is a generator illustration. "
        f"I make no carbon claim, because I have not defined a lifecycle boundary. Nothing here is a verified saving.",
        # 5 request & stop
        f"My request is a {n.weeks}-week, read-only pilot on one heater. Weeks one and two are approvals and data. Weeks three and four are shadow, with operators reviewing blind. Week five is supervised advice only if authorised. "
        f"Week six is measurement and a decision. The cost is a fictional placeholder range of {n.one_opt} to {n.one_pess} million baht one-time and {n.run_opt} to {n.run_pess} million a year to run; "
        f"on the simulated effect the base case does not pay back, so the owner, the project sponsor, decides again at week six. The go test is countable: all {n.n_targets} targets met on measured data and none of the {n.n_stops} stop conditions. "
        f"Stop conditions include any safety or operations incident linked to the pilot, any guardrail failure, critical data invalid for more than three days, and withdrawn approval. "
        f"If any one fires, we stop. I am asking you to approve preparation and a careful measurement, not savings.",
    ]


def timing_table(notes):
    rows = ["| Slide | Words | Seconds at 135 wpm | Cumulative |", "|---|---|---|---|"]
    cum = 0.0
    for i, t in enumerate(notes, 1):
        s = words(t) / WPM * 60
        cum += s
        rows.append(f"| {i} | {words(t)} | {s:.0f} | {int(cum // 60)}:{int(cum % 60):02d} |")
    return "\n".join(rows), cum


def write_docs(D, L, admin, notes):
    n = nums(D, L)
    titles = ["Heater C may burn avoidable fuel, but the company baseline still has to be validated", "Start with a rule and a regression; let AI earn its place",
              "A linear model matched boosted trees, and the AI ranking was not clearly better than a rule", "Operators stay in charge, and the AI's own energy use is negligible",
              "Approve a six-week read-only pilot with a countable go/no-go and hard stops"]
    tbl, total = timing_table(notes)
    sn = ["# 6-minute talk: speaker notes (SYNTHETIC DATA; Raja Chairmapandi, 69900089BG)",
          f"Course talk is 6 minutes, 5 slides. Notes below are the exact speaker notes embedded in final/Heater_C_Final_Deck.pptx. Estimated time {int(total // 60)}:{int(total % 60):02d} at {WPM} words per minute, leaving about {int(360 - total)} seconds of slack (the pace is an assumption and I have not yet rehearsed with a timer).", "", tbl, ""]
    for i, (t, x) in enumerate(zip(titles, notes), 1):
        sn += [f"## Slide {i}: {t}", x, f"({words(x)} words)", ""]
    cues = ["baseline number, only a quarter of rows usable, validation needed", "four options, AI must earn its place, offline and privacy", "linear equals boosted, AI not clearly better, failure fixed",
            "NO ADVICE default, one risk and control, AI kWh vs fuel illustration, no CO2 claim", "six weeks, countable go, stop conditions, cost range, owner"]
    sn += ["## Cue cards (one line per slide to glance at)"] + [f"{i}. {c}" for i, c in enumerate(cues, 1)] + [""]
    sn += ["## If you have 30 seconds left", "Skip the second half of slide 4; keep the request and the stop conditions on slide 5."]
    (FIN / "6_min_speaker_notes.md").write_text("\n".join(sn), encoding="utf-8")

    qa = [("Safety: what stops this from hurting someone?",
           f"It cannot control anything: no write path to DCS/PLC/BMS/SIS exists in the code, and the screen always carries 'SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION'. Advice appears only when every guardrail passes; otherwise the output is NO ADVICE with reason codes "
           f"({n.noadv} of {n.test_rows} held-out rows were NO ADVICE, {n.diag} diagnostic only, {n.adv} advice). Limits in the code are arbitrary synthetic envelopes; a placeholder REQUIRES_OEM_APPROVAL forces NO ADVICE, and real limits come only from a signed site configuration. "
           "In the pilot the EHS lead re-checks every advisory (target 100 %, unsafe recommendations 0) and any incident stops the pilot. Evidence: tests/test_advisory_gate.py, reports/constraints_matrix.md, reports/operator_SOP_draft.md."),
          ("Data truth: how do you know the data are true?",
           f"I do not: they are synthetic. I never read real plant data. What the tool does is refuse to trust bad data: fuel, flow, LHV and heat-balance checks give UNVERIFIED PROXY or NO ADVICE, and only {n.elig} % of synthetic rows pass the checks (the pilot target is 60 %, so real data could fail it). "
           "The company baseline needs measured fuel mass, lot-assayed LHV and a defined stable window before any number is trusted. Evidence: reports/data_quality.md, reports/phase_2_packet.md."),
          ("Measurement: how will you know it worked?",
           f"By normalised SFC (kg fuel per GJ useful heat, lot- and load-matched) with a 90 % interval that must exclude zero, measured in week 6 from fuel mass and assayed LHV; shadow weeks 3-4 measure forecast error against the simple regression. "
           f"The simulated effect is small ({n.sim_opt} % of fuel at best), so a six-week window may be too short to show it; then the answer is 'not shown', not 'saved'. Evidence: reports/pilot_scorecard.csv (T8)."),
          ("Synthetic bias: synthetic data prove nothing, so why trust the results?",
           "They prove only that the method works when the truth is known and that the guardrails behave. The generator defines the truth, and its settings include a random exploration part that makes effects identifiable; real operators move settings in response to load and fuel, which would confound the effect model. "
           "So I report synthetic gains as generator illustrations and require a measured pilot before any claim. A stress run (seed 77) and ablations were used to check robustness. Evidence: reports/synthetic_data_card.md, reports/model_robustness.md, reports/phase_4_packet.md section 7."),
          ("Simplicity: why not just a rule?",
           f"I tested exactly that. Rule plus a default action finds the exact best move on {n.rule_hit} % of actionable rows against {n.ai_hit} % for the AI, with false alerts on {n.rule_fa} % against {n.ai_fa} %. A two-variable regression has forecast error {n.mae_B} kg/h; a linear model with more features {n.mae_L}. "
           "So the pilot baseline is the rule and regression; the AI stays in shadow unless it earns a gain of at least 10 %. Evidence: reports/scenario_comparison.csv, reports/model_comparison.csv."),
          ("O2/CO gaps: there is no CO, no air-flow measurement and O2 basis is unknown.",
           f"Correct. Without CO the system is DIAGNOSTIC ONLY and will not propose air changes ({n.diag} held-out rows). Fan values are commands, not air flow, and the screen says so. O2 below the floor or CO above the limit blocks advice. "
           "A CO analyser allowance is in the cost range, and O2 wet/dry basis is a walk-down item in week 2. Evidence: reports/constraints_matrix.md, reports/02_tag_inventory.csv."),
          ("Incremental ML value: what does ML add over regression?",
           f"On this data nothing for the forecast: boosted trees {n.mae_C0} kg/h against the linear model {n.mae_L}, which is {n.C0_vs_L} % worse, so I chose the linear model. The gain came from adding features such as the current feed, not from model complexity: "
           f"{n.L_vs_B} % better than the 2-variable regression and {n.L_vs_P2} % better than repeating the current feed. For ranking moves, the ridge effect model is also simple. ML earns a place only if the pilot shows at least 10 % lower error than the regression. Evidence: reports/model_card.md, reports/ai_critique_log.md."),
          ("Estimates: your numbers are estimates; how wrong could they be?",
           f"Each number is labelled. Run times are measured (train {n.t_train} s). PC power is an OWN-ESTIMATE of 60 W (35-100 W), unmetered. THB values are fictional placeholders. The 90 % intervals cover model-coefficient uncertainty only, not model error, so they are too narrow. "
           f"AI energy ranges {n.kwh6_opt}-{n.kwh6_pess} kWh over the pilot. The tornado chart shows which assumptions move the result. Evidence: reports/economics_and_energy.xlsx, reports/figs/p6_tornado.png, final/number_source_map.csv."),
          ("Cost: what does it cost and does it pay back?",
           f"Fictional placeholder range: one-time {n.one_opt}-{n.one_pess} million THB (engineering, CO analyser, pilot labour); running {n.run_opt}-{n.run_pess} million THB a year. Base case net is {n.net_base} thousand THB a year, so there is no payback; "
           f"only the optimistic case pays back ({n.pb_opt}). The fuel saving needed just to cover running cost is {n.be_base} % in the base case against a simulated {n.sim_base} %. I refuse to guess real money: replace the yellow cells with site values. Evidence: reports/economics_and_energy.xlsx."),
          ("Net environmental benefit: is it net positive?",
           f"Not shown. The AI's own electricity is negligible ({n.kwh6_base} kWh in {n.weeks} weeks), and a synthetic fuel-energy reduction of {n.fuel_pt} thermal kWh over a {n.win_h} h replay would matter only if real. I make no CO2 claim because no lifecycle boundary "
           f"(fuel supply, biogenic carbon, ash, CO analyser) has been defined. The FD fan electricity change is {n.fan_kwh} kWh (avoided) in the same replay. Net benefit needs a measured fuel change plus a stated boundary. Evidence: reports/energy_synthetic.json, reports/privacy_PDPA.md for data aspects.")]
    q = ["# Panel Q&A: 10 hard questions (SYNTHETIC DATA)", "Answers cite numbers from final/number_source_map.csv and files in this repository.", ""]
    for i, (a, b) in enumerate(qa, 1):
        q += [f"## Q{i}. {a}", b, ""]
    (FIN / "panel_QA.md").write_text("\n".join(q), encoding="utf-8")

    title, body = critique_item()
    crit = (ROOT / "reports" / "ai_critique_log.md").read_text(encoding="utf-8")
    genuine = re.findall(r"^(\d)\. \*\*(.+?)\*\*", crit.split("## Genuine errors found and fixed")[1].split("## Point-by-point")[0], re.M)
    lg = ["# Sources and AI error log (SYNTHETIC DATA; Raja Chairmapandi, 69900089BG)", "",
          "## Published sources (two, one line each)",
          "- ASME PTC 4, Fired Steam Generators: method reference only for useful heat, fuel input and efficiency (input-output basis); no compliance claim.",
          "- Angelopoulos and Bates (2021), A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification, arXiv:2107.07511: basis of the split-conformal 90 % forecast interval.", "",
          "## Project sources",
          "- docs/SPEC.md and docs/PILOT_SPEC.md (project-controlled). Course midterm, requirements document, P&ID, interlock document and HMI screenshots exist but were NOT read by the tool; only a qualitative summary in SPEC C1 was used (reports/01_source_evidence_matrix.csv).", "",
          "## Where AI was used",
          "Claude Code (an AI coding assistant) wrote the generator, pipeline, models, dashboard, tests and documents under my instructions in phases with written packets (reports/phase_*_packet.md). I set the rules (CLAUDE.md), reviewed each packet, and the final numbers come from code (final/number_source_map.csv). "
          "A separate critic agent attacked the modelling assumptions (reports/ai_critique_log.md). No AI or network call exists at runtime.", "",
          "## AI errors found and corrected",
          f"1. **{title}** {body}", ""]
    for num, t in genuine[1:]:
        lg.append(f"{int(num)}. **{t}** (see reports/ai_critique_log.md, 'Genuine errors found and fixed')")
    lg += ["", "### Errors found while building the dashboard and final set (this repository, Phases 5-7)",
           "| Error (by the AI assistant) | How found | Correction |", "|---|---|---|",
           "| Default page of the dashboard returned 'Page not found' because the default page was given a URL path | First headless screenshot of the running app | Removed the path from the default page (app.py) |",
           "| Metric values on the live screen were cut off ('2487 k...') | Same screenshot | CSS lets metric values wrap (src/dashboard/common.py) |",
           "| Business Value screen showed a gross THB figure that disagreed with the Phase 6 workbook (no realisation share, no running costs) | Cross-reading the screenshot against reports/economics_and_energy.xlsx | Added an explicit caption and renamed axes (src/dashboard/p6_value.py) |",
           "| Smoke test did not read success boxes, so a passing page looked like a failure | Test failure in Phase 5 | Test helper now reads st.success (tests/test_app_smoke.py) |",
           "| Phase 4 tests rewrote models/effect_model.joblib with different bytes, dirtying the repo on every run | git status after tests | Session fixture restores the committed bytes (tests/conftest.py) |", ""]
    (FIN / "source_and_AI_error_log.md").write_text("\n".join(lg), encoding="utf-8")
