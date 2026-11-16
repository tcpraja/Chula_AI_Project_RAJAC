# 6-minute talk: speaker notes (SYNTHETIC DATA; Raja Chairmapandi, 69900089BG)
Course talk is 6 minutes, 5 slides. Notes below are the exact speaker notes embedded in final/Heater_C_Final_Deck.pptx. Estimated time 5:43 at 135 words per minute, leaving about 16 seconds of slack (the pace is an assumption and I have not yet rehearsed with a timer).

| Slide | Words | Seconds at 135 wpm | Cumulative |
|---|---|---|---|
| 1 | 155 | 69 | 1:08 |
| 2 | 157 | 70 | 2:18 |
| 3 | 158 | 70 | 3:28 |
| 4 | 151 | 67 | 4:36 |
| 5 | 152 | 68 | 5:43 |

## Slide 1: Heater C may burn avoidable fuel, but the company baseline still has to be validated
Good morning. I study one biomass thermic-fluid heater, Heater C, at an anonymized PET resin plant. The heater is reported to burn more fuel than its design benchmark, and the people running it make different air and grate choices from shift to shift. The question I tested is small: can a tool spot avoidable fuel use and suggest a safe, small move, better than a simple rule? Everything you will see is synthetic: a method check, not a result about the plant. On the synthetic heater the baseline is a specific fuel consumption of 96.7 kilograms of fuel per gigajoule of useful heat, with a middle band of 90.0 to 102.6. Only 27 percent of the rows were clean enough to give advice at all. The company's own baseline still has to be validated, with measured fuel mass and assayed heating value. That is why this proposal asks for a read-only pilot, not for savings.
(155 words)

## Slide 2: Start with a rule and a regression; let AI earn its place
I compared four options. One, change nothing. Two, a process change: a written guide and more fuel heating-value tests. Three, simple automation: a rule that alerts when fuel use is high for the load, plus a small regression. Four, an AI advisory that forecasts fuel and ranks small simulated moves of the fans and grate. The AI has to earn its place, so the choice is to run options two and three first and keep option four in shadow. It would stay only if its forecast error is at least ten percent better than the simple regression on real data. The data would come from a read-only historian export plus laboratory results for each fuel lot. It runs offline on a site computer, with no cloud and no connection that could write to the plant. For privacy, operators appear only as role identifiers, and notes carry no names. Simplicity is a feature: operators must trust every part.
(157 words)

## Slide 3: A linear model matched boosted trees, and the AI ranking was not clearly better than a rule
Here is what the tests showed, on later fuel lots the models had never seen. The fuel forecast error in kilograms per hour was 106.4 for a two-variable regression, 58.5 for simply repeating the current feed, 53.9 for a linear model with all features, and 55.8 for boosted trees. So machine learning added nothing over the linear model, and I chose the linear one. For ranking simulated moves, the AI found the exact best move on 9.0 percent of actionable rows against 8.6 percent for the rule, but it raised false alerts on 29 percent of rows against 15 percent. The AI is not clearly better. One failure mattered: my first reference was too weak, which made the model look 23.9 percent better. A critic review caught it. With the fair reference the gain is 7.8 percent, and I now select models on validation rows only. This is honest evidence for a modest pilot, not for a rollout.
(158 words)

## Slide 4: Operators stay in charge, and the AI's own energy use is negligible
Operators stay in charge. The screen shows NO ADVICE by default and gives advice only when every safety check passes, with reason codes and an uncertainty interval. The shift supervisor records each decision, the safety lead re-checks every advisory, and the energy manager measures the effect. Operators spend at most two minutes per review. The main risk is an operator following a wrong suggestion. The control is that it is advisory only, the safety system and trips are untouched, and unsafe recommendations must be zero. On energy, the AI itself needs about 3.6 kilowatt-hours over six weeks: watts times measured seconds, with the watts assumed because I had no meter. The synthetic fuel-energy change over a 253-hour replay is 7,559 thermal kilowatt-hours, roughly 2,080 times larger, but that is a generator illustration. I make no carbon claim, because I have not defined a lifecycle boundary. Nothing here is a verified saving.
(151 words)

## Slide 5: Approve a six-week read-only pilot with a countable go/no-go and hard stops
My request is a 6-week, read-only pilot on one heater. Weeks one and two are approvals and data. Weeks three and four are shadow, with operators reviewing blind. Week five is supervised advice only if authorised. Week six is measurement and a decision. The cost is a fictional placeholder range of 0.43 to 1.58 million baht one-time and 0.08 to 0.43 million a year to run; on the simulated effect the base case does not pay back, so the owner, the project sponsor, decides again at week six. The go test is countable: all 9 targets met on measured data and none of the 6 stop conditions. Stop conditions include any safety or operations incident linked to the pilot, any guardrail failure, critical data invalid for more than three days, and withdrawn approval. If any one fires, we stop. I am asking you to approve preparation and a careful measurement, not savings.
(152 words)

## Cue cards (one line per slide to glance at)
1. baseline number, only a quarter of rows usable, validation needed
2. four options, AI must earn its place, offline and privacy
3. linear equals boosted, AI not clearly better, failure fixed
4. NO ADVICE default, one risk and control, AI kWh vs fuel illustration, no CO2 claim
5. six weeks, countable go, stop conditions, cost range, owner

## If you have 30 seconds left
Skip the second half of slide 4; keep the request and the stop conditions on slide 5.