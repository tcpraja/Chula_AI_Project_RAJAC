# Final audit sign-off — Heater C AI Advisory (SYNTHETIC, NOT FOR PLANT OPERATION)
Raja Chairmapandi, 69900089BG · 18 Nov 2026 · full register: reports/audit/gap_register.md and submission/Heater_C_Gap_Closure_Register.xlsx

1. **Gaps identified:** 37 (CP01–CP24 plus 13 extra).
2. **Extra gaps:** X01 midterm-figure disclosure · X02 AI false alerts above the rule · X03 eligible coverage below 60 % · X04 forecast gain below 10 % · X05 signed limits · X06 authentication · X07 container build · X08 PC power not metered · X09 no price or analyser quote · X10 no PET normalisation data · X11 earlier deliverables out of date · X12 pandas warning · X13 live talk and feedback.
3. **Closed — verified (11):** CP01, CP04, CP08, CP10, CP11, CP15, CP17, CP22, CP23, CP24, X12.
4. **Closed — documented (15):** CP02, CP03, CP05, CP06, CP07, CP09, CP12, CP14, CP16, CP18, CP19, CP20, CP21, X04, X11.
5. **Open — technical (1):** X02. The AI false-alert rate is 29.2 % against 15.3 % for the rule, about 2.0 per shift against a target of 1. It was not re-tuned on test data. It must be calibrated on real shadow data.
6. **Open — external dependency (9):** CP13, X01, X03, X05, X06, X07, X08, X09, X10. **Pending — live assessment (1):** X13.
7. **Files and modules:**
   - New: src/calibrate_menu.py, src/mv_power.py, src/sub_nums.py, src/sub_content.py, src/sub_build.py, tests/test_audit_corrections.py, tests/test_submission.py.
   - Changed: config/guardrail_limits.yaml (combo_max_step_pct 2), src/economics.py (market-anchored tariff, price and analyser notes), src/guardrails.py (dtype fix), tests/test_no_secrets.py (submission/ scanned).
   - Regenerated: reports/, final/, the 50-slide deck and its PDF.
8. **Tests:** 181 passed, 1 skipped (Docker build needs network), 0 failed (pytest; reports/audit/junit.xml).
9. **Original → corrected:**
   - AI exact move: 9.0 → 22.6 % (rule 8.6 %).
   - Direction: 17.4 → 26.8 %.
   - Precision: 18.9 → 47.6 %.
   - False alerts: 29.2 → 29.2 % (unchanged).
   - Forecast: unchanged (53.9 vs 58.5 kg/h, 7.8 %).
   - Minimum detectable effect at 80 % power is now computed: 1.64 % (21-day windows), about 1.0 % (42-day windows).
10. **Four-option recommendation:**
   - Process improvement: yes.
   - Rule alert: yes.
   - AI read-only shadow validation: yes, conditional.
   - Supervised advice: not now.
   - Deployment: no.
   - No further investment: the fallback if the shadow trial misses its targets.
11. **Economics:**
   - Base net is −150,243 THB/yr (was −154,779), with no payback in the base or pessimistic case.
   - Break-even is 0.34 % of fuel, against a simulated 0.10 % (base) or 0.20 % (full realisation).
   - Inputs: the tariff is PUBLISHED, the fuel price is OWN-ESTIMATE anchored on DEDE-cited data, and the rest are FICTIONAL or ASSUMED.
12. **Safety and sustainability:**
   - Safety: NO ADVICE by default; no write path (AST test); unsigned limits force NO ADVICE.
   - Electricity: 3.6 kWh of AI electricity per 6 weeks (range 1.4–9.1).
   - Simulated fuel effect: 6,412 kWh thermal per 253 h. This is an illustration only, and no CO2 claim is made.
13. **Pilot and request:**
   - Scope: 6 weeks, read-only shadow, Heater C only.
   - Cost: 78k–382k THB (base 183k), plus a CO analyser only if no usable CO signal exists.
   - Owner: the plant sponsor.
   - Decision: GO, REVISE or STOP at week 6. No saving will be claimed.
14. **Deliverables created in submission/:**
   - Heater_C_Final_AI_Solution_Proposal.pdf (3 pp)
   - Heater_C_Final_Presentation.pptx and .pdf (5 slides)
   - Heater_C_Final_Appendix.pdf (3 pp)
   - Heater_C_Gap_Closure_Register.xlsx
   - Heater_C_Model_Validation_Report.pdf
   - Heater_C_Business_Case_and_Energy.xlsx
   - Heater_C_Presentation_Script.docx
   - Heater_C_Final_Compliance_Report.pdf
   - number_source_map_final.csv
15. **Rubric:** the 75 content marks plus 5 for sources are covered by verified submission content. Presentation (10) and discussion and feedback (10) are pending the live assessment. No mark is guaranteed.
16. **Student actions:**
   - Confirm that the midterm figures may be disclosed, or remove them and rebuild with `python -m src.sub_build`.
   - Submit the Heater_C_Final_* set, not the older *_Raja_* files.
   - Rehearse to 6:00.
   - After the talk, take part in the discussion and submit the feedback form.

**Deliverable status:**
- Proposal and deck: ready, subject to the disclosure check in X01.
- Appendix, register, validation report, business case, script and compliance report: ready for submission.
