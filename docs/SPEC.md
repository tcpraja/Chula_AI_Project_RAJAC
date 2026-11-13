## C1 Sources
Originals (midterm, requirements docx, P&ID, interlock doc, HMI screenshots) are NOT in the repo: list by filename,
"not read by AI tool — confidential". Equipment (qualitative): PKS travelling-grate furnace, FD+ID fans, dust
collection, economizer/air preheater, HTF loop to PET process, soot blowing, ash removal. HMI shows: HTF flow,
HTF inlet/outlet temp + setpoint, furnace and flue temps, draft (mmWC) + setpoint, O2 %, fan and grate command %,
feeder motors, biomass kg/s and kg/day, heat Mkcal/h and Mkcal/day, alarms, main-safety-status. Not on HMI: CO,
measured air flow, per-lot LHV, online moisture. Issues: fuel above design benchmark, operator-dependent air/grate,
infrequent LHV tests, aging fans, display totals that may not reconcile.
## C2 Candidate tags (verify on site; outputs use SYN_ aliases)
FT-1-1→SYN_FT_HTF HTF flow m3/h High | TE-1-5→SYN_TE_HTF_IN return °C High | TE-1-1→SYN_TE_HTF_OUT supply °C High |
TE-1-2(+SP)→SYN_TE_CTRL controlled temp Medium | TE-3-1/TE-3-2→SYN_TE_FURN furnace °C Medium | TE-3-3→SYN_TE_FLUE
Medium | DFT-1-1 (alias DT)→SYN_DRAFT draft mmWC→Pa (×9.80665) Medium | O2→SYN_O2 basis unknown Medium |
M4/M5→SYN_FD_CMD/SYN_ID_CMD command % Low (mapping unverified; command ≠ airflow) | M9→SYN_GRATE_CMD Low |
biomass kg/s, kg/day→SYN_FUEL_RATE/_DAY Low (window/reset unknown) | heat Mkcal/h, /day→SYN_Q_RATE/_DAY Low (method
unknown) | main safety status→SYN_SAFE_OK Low (source of truth = BMS/SIS).
Ambiguities: fan mapping; draft alias; O2 wet/dry; kg/s vs kg/day window; heat-output method; LHV per lot; no CO;
HTF grade/property table.
## C3 Formulas (as-fired LHV basis)
m_HTF=V/3600×rho(Tmean); Q_out=m_HTF×∫cp dT ≈ m×cp(Tmean)×(Tout−Tin); Q_in=m_fuel×LHV; eta=100×Q_out/Q_in
(startup/standby excluded, auxiliaries outside); SFC kg/GJ=1/(eta×LHV[GJ/kg]); 1 kcal=4.184 kJ; 1 Mkcal/h=1.16222 MW;
1 kg/s=86,400 kg/day only if sustained; scenario identity fuel_reduction=1−eta_base/eta_cand (not a result).
Worked (SYNTHETIC): 700 m3/h, rho 780, cp 2.60, ΔT 20.3 K → 151.7 kg/s, 8.0 MW; eta 0.675, LHV 15 MJ/kg →
11.85 MW in, 0.790 kg/s = 2,844 kg/h, SFC 98.8 kg/GJ; eta 0.675→0.700 → 3.57 %. ASME PTC 4 = method reference only.
## C4 HTF properties
config/htf_properties.csv (T_C, rho_kgm3, cp_kJkgK, source). No datasheet offline → generic linear table labeled
OWN-ESTIMATE("generic mineral-oil-type HTF, illustrative"), rho ≈ 780–820, cp ≈ 2.4–2.7, synthetic band only.
Outside range → PROPERTY_OOR → NO_ADVICE.
## C5 Synthetic envelope (ASSUMED / NOT APPROVED, config/synthetic_parameters.yaml + assumptions register)
Demand 6–11 MW; moisture 8–30 %wb; LHV 12–18 MJ/kg (falls with moisture); latent eta 0.62–0.72 centre 0.675;
HTF 500–900 m3/h; temps inside property table; O2 5–12 % dry; FD/ID/grate 0–100 %; draft normal band negative,
zero/positive = unsafe; CO available on 60 % of days.
## C6 Generator
Demand → lot moisture/LHV (lots 6–18 h, bed lag 10–20 min) → latent eta = f(moisture, fouling reset by sootblow,
excess-air deviation from a hidden optimum O2 depending on load+moisture, grate-air mismatch, fan derate, AR(1)) →
fuel = Q/(eta×LHV) → HTF temps → measured = truth + noise/bias/lag. Settings include a randomized exploration
component so effects are identifiable in synthetic data (state: not identifiable from observational plant data).
Events: startup, ramps, steady, sootblow, lot change, feeder stop, fan derate, poor air, frozen sensor, CO missing,
gaps, totalizer reset, high/low HTF flow, adverse draft, trips. 60 d × 288 = 17,280 normal rows (seed 42) + fault
rows; stress seed 77; display-reconciliation file where kg/s×86,400≠kg/day etc., one contradictory record → REJECT.
## C7 Guardrails
Layer 1 data: mode STEADY; HTF flow/temps valid and in table; fuel trusted; LHV known; not stale (>2 frozen samples)
or gap; not OOD; 0.4<eta<0.9. Layer 2 constraints: no trip/alarm; no fan derate; draft in synthetic band; temps in
synthetic limits; CO available and below limit for any air advice; O2 above floor; move ≤ max step; interval width ≤
threshold. No CO → DIAGNOSTIC_ONLY. Reason codes: NO_CO BAD_FLOW LOW_FUEL_CONF TRIP_ACTIVE FAN_DERATE UNSAFE_DRAFT
HIGH_TEMP STALE_DATA OOD ENERGY_BALANCE TRANSIENT WIDE_INTERVAL PROPERTY_OOR LIMITS_NOT_APPROVED.
## C8 Course
2130511 AI Abstraction and Digital Technologies, Chula LGO, individual. Raja Chairmapandi, 69900089BG. Due Thu 19 Nov
2026 23:59; talk 20 Nov, 6 min, 5 slides; optional revision 27 Nov. Proposal ≤3 pages: Request (4–5 lines: scope,
duration, cost range, owner, end decision); Problem & baseline (1 paragraph, labeled number); Options & choice (half page:
no change / process change / simple automation / AI; data source; where it runs; PDPA); Test results (1 paragraph incl.
what failed); People & sustainability (who checks, who is affected, one risk + control; AI energy = power × time; what
it saves); Trial plan (3–4 lines: measure + stop condition). Appendix: test evidence, two sources one line each, one AI
error. Slides: 1 org/problem/baseline 2 options/choice 3 results 4 people & sustainability 5 request & stop condition.
Rubric: problem 10, options/data 20, test 10, people 10, sustainability 10, request/trial 15, sources/AI 5, talk 10,
discussion 10. Style: answer first; baseline table "Measure | Result | Method"; refuse to guess unmeasurable money.
