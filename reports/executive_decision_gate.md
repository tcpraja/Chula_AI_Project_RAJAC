# Executive decision gate — Heater C advisory pilot (DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL)
All figures: SYNTHETIC or FICTIONAL/ASSUMED unless marked MEASURED-IN-PROTOTYPE. No saving has been verified.

## Answer first
Recommendation: **REVISE before any GO.** A read-only shadow pilot is cheap and safe to plan, but the evidence so far does not justify a savings or payback claim. On the synthetic data the advisory beats a simple rule only marginally, and at the simulated effect size the running cost exceeds the benefit in the base case. Approve preparation (weeks 1–2: approvals, tag walk-down, assay plan) and decide again with measured data.

## Request (course format: scope, duration, cost range, owner, end decision)
- Scope: one heater (Heater C), read-only shadow, then supervised advisory only if authorised. No control, no write path.
- Duration: six weeks (weeks 1–2 approvals and data, 3–4 shadow, 5 supervised advisory if authorised, 6 measurement and decision).
- Cost range (FICTIONAL placeholders, THB): one-time 0.43 M (optimistic) / 0.88 M (base) / 1.58 M (pessimistic), containing engineering effort, a CO-analyser allowance (OWN-ESTIMATE range 0.35–1.2 M) and pilot review labour; running 0.08 / 0.21 / 0.43 M per year.
- Owner: Project sponsor (role). End decision: GO / REVISE / STOP at week 6.

## What the numbers say (reports/economics_and_energy.xlsx, sheet Model)
| Item | Pessimistic | Base | Optimistic | Label |
|---|---|---|---|---|
| Simulated fuel effect after realisation share | 0.05 % | 0.12 % | 0.24 % | SYNTHETIC × ASSUMED share (0.2 / 0.5 / 1.0) |
| Fuel saving needed just to cover running cost | 1.40 % | 0.43 % | 0.11 % | ASSUMED costs |
| Net annual effect, THB/yr | −416 k | −155 k | +93 k | FICTIONAL |
| Simple payback | NO PAYBACK | NO PAYBACK | 4.6 years | FICTIONAL |
Reading: payback appears only if nearly all of the simulated 0.24 % fuel effect is real and costs are at the low end. A measured result below about 0.4 % fuel would not cover running cost in the base case.
Energy (replay window of 253.4 h): simulated fuel energy change −7,559 kWh thermal (90 % interval −9,111 to −5,936; coefficient uncertainty only; Δfuel kg × LHV ÷ 3.6); FD fan electricity change −49.7 kWh (fan_power_kW_FD columns, fan law, negative = avoided). AI computing: about 3.6 kWh over six weeks (1.4–9.1), 2.6 kWh per month at an assumed 60 W (OWN-ESTIMATE, no wattmeter). No CO2 claim: no lifecycle boundary is defined.

## Evidence so far and what failed
- 107 tests pass; deterministic shadow replay (identical hash on repeat); dashboard runs.
- AI vs rule on the synthetic test split: exact-action hit 9.0 % vs 8.6 %; false-alert rate 29 % vs 15 % (Phase 4). The advisory is not clearly better than the rule.
- The effect model is associational; real data would be confounded. Synthetic gains are generator illustrations.

## Decisions needed
- D1 Approve preparation weeks 1–2 only, or stop here?
- D2 Replace ASSUMED economics (fuel price, hours, tariff, labour, CO analyser, upkeep) with site values?
- D3 Where may real data be processed, and by whom? This tool never reads real plant data; a site run needs a separate approved decision and a signed site limits config.
- D4 Accept the scorecard targets below, or change them?

## Targets (verbatim, docs/PILOT_SPEC.md — "proposed")
Targets (proposed): trusted eligible windows ≥60 %; guardrail re-check pass 100 %; unsafe recommendations 0; model MAE
≥10 % below simple regression else choose simple; acceptance ≥50 % with reasons; review ≤2 min; false alerts ≤1/shift;
normalized SFC 90 % CI excludes 0 to claim effect; no deterioration in HTF supply reliability.

## Stop conditions (verbatim, docs/PILOT_SPEC.md)
Stop: any safety/OT incident linked to pilot; any guardrail failure; critical data invalid >3 consecutive days; MAE worse
than simple regression 2 consecutive weeks; false alerts >3/shift for 1 week; approval withdrawn/unavailable.

## Gate rule at week 6
GO only if every target is met on measured data, no stop condition fired, and T8 shows a 90 % CI excluding 0. REVISE if safety and data targets pass but the effect is not shown or economics do not cover running cost. STOP if any stop condition fired or approvals lapse.
