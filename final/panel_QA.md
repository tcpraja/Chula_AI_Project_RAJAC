# Panel Q&A: 10 hard questions (SYNTHETIC DATA)
Answers cite numbers from final/number_source_map.csv and files in this repository.

## Q1. Safety: what stops this from hurting someone?
It cannot control anything: no write path to DCS/PLC/BMS/SIS exists in the code, and the screen always carries 'SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION'. Advice appears only when every guardrail passes; otherwise the output is NO ADVICE with reason codes (1,518 of 3,041 held-out rows were NO ADVICE, 815 diagnostic only, 708 advice). Limits in the code are arbitrary synthetic envelopes; a placeholder REQUIRES_OEM_APPROVAL forces NO ADVICE, and real limits come only from a signed site configuration. In the pilot the EHS lead re-checks every advisory (target 100 %, unsafe recommendations 0) and any incident stops the pilot. Evidence: tests/test_advisory_gate.py, reports/constraints_matrix.md, reports/operator_SOP_draft.md.

## Q2. Data truth: how do you know the data are true?
I do not: they are synthetic. I never read real plant data. What the tool does is refuse to trust bad data: fuel, flow, LHV and heat-balance checks give UNVERIFIED PROXY or NO ADVICE, and only 27 % of synthetic rows pass the checks (the pilot target is 60 %, so real data could fail it). The company baseline needs measured fuel mass, lot-assayed LHV and a defined stable window before any number is trusted. Evidence: reports/data_quality.md, reports/phase_2_packet.md.

## Q3. Measurement: how will you know it worked?
By normalised SFC (kg fuel per GJ useful heat, lot- and load-matched) with a 90 % interval that must exclude zero, measured in week 6 from fuel mass and assayed LHV; shadow weeks 3-4 measure forecast error against the simple regression. The simulated effect is small (0.24 % of fuel at best), so a six-week window may be too short to show it; then the answer is 'not shown', not 'saved'. Evidence: reports/pilot_scorecard.csv (T8).

## Q4. Synthetic bias: synthetic data prove nothing, so why trust the results?
They prove only that the method works when the truth is known and that the guardrails behave. The generator defines the truth, and its settings include a random exploration part that makes effects identifiable; real operators move settings in response to load and fuel, which would confound the effect model. So I report synthetic gains as generator illustrations and require a measured pilot before any claim. A stress run (seed 77) and ablations were used to check robustness. Evidence: reports/synthetic_data_card.md, reports/model_robustness.md, reports/phase_4_packet.md section 7.

## Q5. Simplicity: why not just a rule?
I tested exactly that. Rule plus a default action finds the exact best move on 8.6 % of actionable rows against 9.0 % for the AI, with false alerts on 15 % against 29 %. A two-variable regression has forecast error 106.4 kg/h; a linear model with more features 53.9. So the pilot baseline is the rule and regression; the AI stays in shadow unless it earns a gain of at least 10 %. Evidence: reports/scenario_comparison.csv, reports/model_comparison.csv.

## Q6. O2/CO gaps: there is no CO, no air-flow measurement and O2 basis is unknown.
Correct. Without CO the system is DIAGNOSTIC ONLY and will not propose air changes (815 held-out rows). Fan values are commands, not air flow, and the screen says so. O2 below the floor or CO above the limit blocks advice. A CO analyser allowance is in the cost range, and O2 wet/dry basis is a walk-down item in week 2. Evidence: reports/constraints_matrix.md, reports/02_tag_inventory.csv.

## Q7. Incremental ML value: what does ML add over regression?
On this data nothing for the forecast: boosted trees 55.8 kg/h against the linear model 53.9, which is 3.4 % worse, so I chose the linear model. The gain came from adding features such as the current feed, not from model complexity: 49.3 % better than the 2-variable regression and 7.8 % better than repeating the current feed. For ranking moves, the ridge effect model is also simple. ML earns a place only if the pilot shows at least 10 % lower error than the regression. Evidence: reports/model_card.md, reports/ai_critique_log.md.

## Q8. Estimates: your numbers are estimates; how wrong could they be?
Each number is labelled. Run times are measured (train 18.5 s). PC power is an OWN-ESTIMATE of 60 W (35-100 W), unmetered. THB values are fictional placeholders. The 90 % intervals cover model-coefficient uncertainty only, not model error, so they are too narrow. AI energy ranges 1.4-9.1 kWh over the pilot. The tornado chart shows which assumptions move the result. Evidence: reports/economics_and_energy.xlsx, reports/figs/p6_tornado.png, final/number_source_map.csv.

## Q9. Cost: what does it cost and does it pay back?
Fictional placeholder range: one-time 0.43-1.58 million THB (engineering, CO analyser, pilot labour); running 0.08-0.43 million THB a year. Base case net is -155 thousand THB a year, so there is no payback; only the optimistic case pays back (4.6 years). The fuel saving needed just to cover running cost is 0.43 % in the base case against a simulated 0.12 %. I refuse to guess real money: replace the yellow cells with site values. Evidence: reports/economics_and_energy.xlsx.

## Q10. Net environmental benefit: is it net positive?
Not shown. The AI's own electricity is negligible (3.6 kWh in 6 weeks), and a synthetic fuel-energy reduction of 7,559 thermal kWh over a 253 h replay would matter only if real. I make no CO2 claim because no lifecycle boundary (fuel supply, biogenic carbon, ash, CO analyser) has been defined. The FD fan electricity change is 50 kWh (avoided) in the same replay. Net benefit needs a measured fuel change plus a stated boundary. Evidence: reports/energy_synthetic.json, reports/privacy_PDPA.md for data aspects.
