# Phase 0 Packet — Scope, evidence, tags, assumptions
## 1 Implemented
Wrote scope charter (Heater C only; Level 1 vs Level 2; MVP question), source evidence matrix, tag inventory (25 tags), data dictionary (32 variables), assumptions register (13), generic PFD/data-flow figure, options comparison, RACI + safety gate, and a denylist scan test.
## 2 Files
reports/00_scope_charter.md, 01_source_evidence_matrix.csv, 02_tag_inventory.csv, 03_data_dictionary.csv, 04_assumptions_register.csv, 05_PFD_and_dataflow.png, 06_options_comparison.md, 07_RACI_and_safety_gate.md; src/make_pfd.py; tests/test_no_secrets.py.
## 3 Provenance & assumption IDs
Tags/envelope from docs/SPEC.md C2/C5 (ASSUMED). Assumptions A01–A13, all state=ASSUMED. Option costs in 06 are OWN-ESTIMATE placeholders, not measured.
## 4 Formulas + worked example
None computed in Phase 0. Only unit conversion: draft Pa = mmWC × 9.80665 (e.g. 10 mmWC = 98.07 Pa).
## 5 Evidence
pytest: 1 passed (denylist scan over reports/, final/, models/, data/*). Figure: reports/05_PFD_and_dataflow.png (checked visually, no plant values).
## 6 Checklist
- Heater C only, exclusions listed: PASS
- Level 1/Level 2 and MVP question stated: PASS
- Originals listed as not read: PASS (two filenames withheld; see 7)
- Tag table with confidence, observed/not_observed: PASS
- Data dictionary 12 groups, 4 classes: PASS
- Assumptions all ASSUMED with owners: PASS
- Denylist test passes: PASS
- Option costs verified by quotes: NEEDS DATA
- HTF property table / real limits: NEEDS DATA (Phase 1+, site)
## 7 Known faults/limits
- Two source filenames withheld because they or their content hit the denylist (SPEC C1 asks for filenames); alternative is to rename originals.
- 02 contains real candidate tag labels copied from SPEC C2 (as instructed); keep internal, publish SYN_ aliases only.
- SPEC C1 says originals are not in the repo; copies exist in the parent folder. Not opened by this tool.
## 8 Decision needed
APPROVE PHASE 0? Also: confirm tag labels may stay in 02, and whether option cost placeholders are acceptable.
