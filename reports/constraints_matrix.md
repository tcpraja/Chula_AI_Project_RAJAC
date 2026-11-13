# Constraints matrix (SYNTHETIC - NOT FOR PLANT OPERATION)
Test split rows: 3041; guardrail-eligible: 826; decisions: {'NO_ADVICE': 1518, 'DIAGNOSTIC_ONLY': 815, 'ADVICE': 708}. Limits are synthetic normalized envelopes (config/guardrail_limits.yaml, ASSUMED / NOT APPROVED); any REQUIRES_OEM_APPROVAL value forces NO_ADVICE.

| Reason code | Layer | Pass condition | Rows with code | Rows with only this code |
|---|---|---|---|---|
| NO_CO | 2 | CO available (co_available=1, CO measured) | 1422 | 815 |
| BAD_FLOW | 1 | HTF flow [500.0, 900.0] m3/h (+-2 %) | 33 | 0 |
| LOW_FUEL_CONF | 1 | belt-weighed fuel, lab LHV known, no feeder stop/totalizer reset | 412 | 0 |
| TRIP_ACTIVE | 2 | no interlock/trip alarm | 32 | 0 |
| FAN_DERATE | 2 | no fan derate | 69 | 0 |
| UNSAFE_DRAFT | 2 | draft in [-60.0, -10.0] Pa | 41 | 0 |
| HIGH_TEMP | 2 | furnace <= 1000.0 C, HTF out <= 300.0 C | 0 | 0 |
| STALE_DATA | 1 | no signal frozen > 2 samples | 0 | 0 |
| OOD | 1 | Mahalanobis^2 <= train 0.995 quantile (25.5) | 258 | 0 |
| ENERGY_BALANCE | 1 | [0.4, 0.9] efficiency, heat balance verified | 373 | 0 |
| TRANSIENT | 1 | STEADY, >= 12 contiguous steps, no sootblow/gap | 1400 | 369 |
| WIDE_INTERVAL | 2 (optimizer) | dSFC 90 % interval width <= 3.0 kg/GJ | 0 | 0 |
| PROPERTY_OOR | 1 | HTF temps inside property table | 0 | 0 |
| LIMITS_NOT_APPROVED | 2 | no limit equals REQUIRES_OEM_APPROVAL | 0 | 0 |
| LOW_O2 | 2 | O2 >= 5.0 % | 189 | 0 |
| HIGH_CO | 2 | CO <= 250.0 ppm | 151 | 0 |
| CMD_FEEDBACK | 1 | command vs feedback agree | 0 | 0 |
| NO_BENEFIT | 2 (optimizer) | pessimistic dSFC must be below 0 | 118 | 118 |

## Candidate constraints (per eligible row, 25-move FD x grate grid at fixed demand)
Move <= 4.0 % FD / 4.0 % grate; FD in [20.0, 100.0], grate in [0.0, 100.0]; predicted O2 >= floor + 0.3; predicted CO x 1.25 <= limit; predicted draft in band; candidate state not OOD.
Candidates dropped (sum over eligible rows x 25): {'LOW_O2_OR_CO_RISK': 1018, 'OOD': 252, 'DRAFT': 0, 'RANGE_OR_MOVE': 0}.
'Less excess O2' (O2 falls, floor and CO margin kept) is kept apart from 'low-O2 / CO risk' (dropped, never offered). Advice classes on test rows: {'NONE': 2333, 'LESS_EXCESS_O2': 465, 'MORE_AIR_COMPLETE_COMBUSTION': 168, 'GRATE_BALANCE': 75}.

## Models behind the checks (OWN-ESTIMATE, training split only)
Efficiency response ridge: train R2 0.467, residual SD 1.71 pp, 51 lots, 200 lot-bootstraps. O2 from FD: lambda proportional to FD at fixed demand (stoichiometric). Fan power: kW = k (FD/100)^3, correlation with data 0.9997.

## Causal-limits statement
Causal limits: the action-effect model is fitted to synthetic observational data with a generator-built exploration component; its delta-efficiency for a proposed move is an association, not an identified causal effect, and on real plant data confounding (operators move FD/grate in response to load, fuel and air demand) would bias it. All benefits are synthetic generator illustrations, never savings; every output requires human review; BMS/SIS/DCS remain the only control authorities.
