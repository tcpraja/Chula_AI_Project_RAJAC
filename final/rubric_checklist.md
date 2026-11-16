# Rubric checklist: all 100 points scored with evidence (self-assessment, SYNTHETIC DATA)
Rubric from docs/SPEC.md C8. Scores are my own honest estimates, not a grade; "Before" is the first pass, "After" is after fixing the two weakest criteria (marked FIX).

| Criterion | Max | Before | After | Evidence (paths) | Gap that remains |
|---|---|---|---|---|---|
| Problem | 10 | 8 | 8 | final/Heater_C_Final_Proposal.pdf section 2; final/figs/f1_baseline.png; reports/00_scope_charter.md | Baseline is synthetic; the company baseline still requires validation (stated). |
| Options and data | 20 | 16 | 16 | proposal section 3; final/figs/f2_options.png; reports/06_options_comparison.md; reports/03_data_dictionary.csv; reports/privacy_PDPA.md | Options 1-2 untested; no real data; data access decision D3 open. |
| Test | 10 | 7 | 7 | proposal section 4; final/figs/f3_results.png; reports/model_comparison.csv; reports/scenario_comparison.csv; reports/ai_critique_log.md; tests/ | Synthetic only; AI not clearly better than the rule; one failure and fix shown. |
| People | 10 | 8 | 8 | proposal section 5; reports/operator_SOP_draft.md; reports/risk_register.md; reports/07_RACI_and_safety_gate.md | Operators and EHS not yet consulted. |
| Sustainability (FIX 1) | 10 | 6 | 7 | proposal section 5; Appendix A5 (energy boundary); reports/economics_and_energy.xlsx (sheet Model); reports/ai_runtime_measured.csv; final/figs/f4_energy.png | PC power still an unmetered OWN-ESTIMATE; no net environmental benefit shown (no lifecycle boundary). |
| Request and trial | 15 | 12 | 12 | proposal sections 1 and 6; reports/pilot_plan_6_weeks.md; reports/pilot_scorecard.csv; reports/executive_decision_gate.md; final/figs/f5_timeline.png | Cost figures are fictional placeholders; base case does not pay back. |
| Sources and AI | 5 | 4 | 4 | Appendix A3 and A4; final/source_and_AI_error_log.md; reports/ai_critique_log.md | Two published sources used lightly (method references). |
| Talk (FIX 2) | 10 | 6 | 7 | final/Heater_C_Final_Deck.pptx (5 slides, notes 150-170 words); final/6_min_speaker_notes.md (computed timing with slack, cue cards) | Not yet rehearsed with a timer; deck not viewed in PowerPoint here. |
| Discussion | 10 | 8 | 8 | final/panel_QA.md (10 hard questions with evidence paths) | Answers are written, not tested on a panel. |
| **Total** | **100** | **75** | **77** | | |

## The two weakest and what I changed
1. **Sustainability (6 of 10).** Weak because the energy story rested on one unmetered power guess and had no stated boundary. Fix: added an explicit energy boundary table (Appendix A5) separating what is counted (AI electricity, FD fan electricity, fuel thermal energy, each labelled) from what is not (fuel supply, biogenic carbon, ash, analyser), plus the ratio of fuel energy to AI energy, and kept the no-CO2-claim rule. Remaining gap: a plug-in power meter reading would replace the 60 W estimate.
2. **Talk (6 of 10).** Weak because the notes were close to the six-minute limit and had no glance aids. Fix: trimmed the notes to 150-170 words per slide (timing and slack are computed in final/6_min_speaker_notes.md), added one-line cue cards and a 30-second cut rule in final/6_min_speaker_notes.md. Remaining gap: nobody has timed a live rehearsal.

## Not scored because not checkable here
Visual quality of the PDFs and slides was not viewed in a rendering application in this environment (text extraction and geometry were checked by tests/test_final.py). Open the files before submission.
