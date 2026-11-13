# Phase 1 Packet — Synthetic generator, property table, units, data card
## 1 Implemented
Built the synthetic Heater C generator (demand, lots with bed lag, latent eta, HTF heat balance, measurements = truth + noise/bias/lag), operator shifts with 15 % randomized EXPLORATION, 15 fault cases, SPEC C7 eligibility labels, a generator-best-action label, HTF property table, unit helpers with display-record reconciliation, a 106-row data dictionary, figures and a data card. The earlier Phase 0 variable inventory moved to reports/03b_variable_inventory_phase0.csv.
## 2 Files
config/synthetic_parameters.yaml, config/htf_properties.csv; src/units.py, generate_synthetic.py, data_dictionary.py, p1_report.py; data/raw_synthetic/{synthetic_heater_c_5min,synthetic_truth,fault_cases,operator_action_log}.csv; data/stress/{stress_seed77*,display_reconciliation}.csv; reports/03_data_dictionary.csv, synthetic_data_card.md, figs/p1_{trend_24h,histograms,energy_balance_residuals}.png; tests/test_synthetic_physics.py, conftest.py.
## 3 Provenance & assumption IDs
All data SYNTHETIC. HTF table OWN-ESTIMATE (generic mineral-oil-type, 150–320 C, rho 820→780, cp 2.40→2.70). Effects are generator-defined: A12 (action effects), A15 (bed lag 10–20 min), A16 (noise), A17 (operator habits), A19 (ash), A20 (60-min window). Envelope A01–A10 from SPEC C5. Fan power = fan law, OWN-ESTIMATE.
## 4 Formulas + worked example
m=V/3600·rho(Tmean); Q_out=m·∫cp dT; Q_in=m_fuel·LHV; SFC kg/GJ=1/(eta·LHV[GJ/kg]); 1 Mkcal/h=1.16222 MW.
SPEC C3 example reproduced by `python -m src.units --selftest`: 151.7 kg/s, 8.00 MW, SFC 98.8 kg/GJ, eta 0.675→0.700 = 3.57 % fewer kg (identity, not a result).
## 5 Evidence
- Generator: main shape (18706, 52) = 17,280 normal + 1,426 fault-block rows; stress (10066, 52) = 8,640 normal + 1,426; 6,722 logged operator changes (main).
- Tests: 24 passed (22 physics + 2 denylist scan).
- Latent eta in STEADY: median 67.8 %, 5–95 % 64.8–69.7 %. Median SFC 93.1 kg/GJ. Truth balance residual 0.0003 % (limit 0.5 %).
- Eligibility (normal block): ELIGIBLE 27.1 %, DIAGNOSTIC_ONLY 16.9 %, NO_ADVICE 56.0 % (top reason LOW_FUEL_CONF: unassayed lots and volumetric periods).
- Display file: 30 records: 6 OK, 23 WINDOW_MISMATCH, 1 REJECT (injected contradictory).
- Figures: reports/figs/p1_trend_24h.png, p1_histograms.png, p1_energy_balance_residuals.png.
## 6 Checklist
- 17,280 normal rows, seed hash deterministic: PASS
- Truth balance ≤0.5 %: PASS
- cp≠4.186, no property extrapolation (NaN + PROPERTY_OOR): PASS
- Contradictory display record → REJECT: PASS
- Implausible heat/fuel flagged; bypass>0 → HEAT_BALANCE_CHECK: PASS
- Action log matches setting changes both ways: PASS
- Every column in data dictionary: PASS
- Realism vs real heater: NEEDS DATA (Level 2)
- Site-style seed 101 dataset: NOT GENERATED (config only)
## 7 Known faults/limits
- Gain headroom (mean 0.67 pp eta) is a generator choice; best action is dominated by FD reductions because operators run slightly high O2; ranking is easy by design.
- Eligibility is low (volumetric, 30 % unassayed lots, 60-min window); a Phase 2 baseline must handle it.
- Constant HTF setpoint, draft setpoint, pump status; startup uses a warm HTF loop.
- Added reason codes LOW_O2 and HIGH_CO (SPEC C7 lists conditions without codes).
- Latent eta floor/ceiling clips and clipped O2 deviation (−3.5/+6) are modelling shortcuts.
## 8 Decision needed
APPROVE PHASE 1? Also: keep ranking easy, or make Phase 2 stress (seed 77, shifted optimum) the main test of the AI vs simple regression?
