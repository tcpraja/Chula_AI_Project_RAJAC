# Action-menu and alert-threshold calibration (CP10) - SYNTHETIC, NOT FOR PLANT OPERATION

Selection on the validation split only, with a rule fixed before the test split was scored: keep variants whose false-alert rate is no worse than the rule comparator's on validation, then take the highest exact-hit rate. Test scored once for the original and the chosen variant.

| split | two-axis menu | min benefit kg/GJ | alerts | exact hit | false alert | rule exact hit | rule false alert |
|---|---|---|---|---|---|---|---|
| val | full grid | 0.0 | 696 | 16.1 % | 33.0 % | 13.2 % | 43.4 % |
| val | full grid | 0.1 | 618 | 15.5 % | 18.4 % | 13.2 % | 43.4 % |
| val | full grid | 0.2 | 535 | 13.8 % | 9.7 % | 13.2 % | 43.4 % |
| val | full grid | 0.3 | 475 | 12.6 % | 5.2 % | 13.2 % | 43.4 % |
| val | <= 2 % | 0.0 | 696 | 30.1 % | 33.0 % | 13.2 % | 43.4 % |
| val | <= 2 % | 0.1 | 617 | 29.5 % | 18.4 % | 13.2 % | 43.4 % |
| val | <= 2 % | 0.2 | 525 | 27.2 % | 9.7 % | 13.2 % | 43.4 % |
| val | <= 2 % | 0.3 | 464 | 25.5 % | 4.9 % | 13.2 % | 43.4 % |
| test_original | full grid | 0.0 | 708 | 9.0 % | 29.2 % | 8.6 % | 15.3 % |
| test_chosen | <= 2 % | 0.0 | 708 | 22.6 % | 29.2 % | 8.6 % | 15.3 % |

Original: menu full grid, min benefit 0.0. Chosen: menu <= 2 %, min benefit 0.0.

Truth labels are generator outputs used for evaluation only. Exact hit = proposed action equals the generator's best action on actionable rows; false alert = advice on rows where the generator's best action is HOLD. Associations only, no causal claim.
