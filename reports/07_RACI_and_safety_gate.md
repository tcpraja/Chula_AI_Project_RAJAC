# 07 RACI and Safety Gate (roles only; no person names)
R = responsible, A = accountable, C = consulted, I = informed, V = veto right. Extra roles beyond the core eight: Maintenance, Fuel QA lab, Data protection officer (DPO), Cybersecurity.

| Activity | Operator | Shift lead | Process eng. | Energy mgr | EHS | OT/IT | OEM | Sponsor | Maint. | Fuel QA | DPO | Cyber |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Scope and charter | I | I | R | C | C | C | I | A | I | I | I | I |
| Tag walk-down and read-only export | C | C | R | I | C | A | C | I | C | I | C | V |
| Fuel lot LHV/moisture assay plan | I | C | C | A | I | I | I | I | I | R | I | I |
| Guardrail/limit definition (signed site config) | C | C | R | I | A/V | C | V | I | C | I | I | I |
| Shadow-mode review (blind) | R | A | C | I | I | I | I | I | I | I | I | I |
| Advisory use (supervised, operator decides in DCS) | R | A | C | I | V | C | C | I | I | I | I | C |
| Model version change / retrain | I | I | R | C | V | C | C | A | I | I | I | C |
| Personal-data handling and retention | I | C | I | I | I | R | I | A | I | I | V | C |
| Savings claim (M&V) | I | I | C | R | I | I | I | A | I | C | I | I |
| Go / revise / stop | C | C | C | C | V | C | C | A | C | I | C | C |

## Veto rights
- EHS: advice touching combustion safety, draft or interlock margins; any safety incident stops the pilot.
- OT/IT and Cybersecurity: any plant-network connection; any write path (none permitted).
- OEM: operating envelopes and any REQUIRES_OEM_APPROVAL limit.
- DPO: any use of personal data in logs or features.
- Shift lead and operator: may ignore any advice without justification; rejection reasons are logged.
- Sponsor: accountable for go/revise/stop, after the vetoes above are cleared.

## Safety gate (all required before Level 2 advisory; recorded on a gate sign-off sheet: date, role, decision, conditions)
1. Signed site config with real limits; otherwise NO_ADVICE.
2. Every recommendation shows "ADVISORY ONLY — OPERATOR DECIDES"; guardrails re-checked at display time.
3. No write access to DCS/PLC/BMS/SIS; no interlock bypass.
4. MOC approved; hazard review (HAZOP/LOPA or equivalent) confirms advice cannot defeat a protection layer.
5. OT cybersecurity check passed (zone/conduit review; read-only data diode or export).
6. Stop conditions per docs/PILOT_SPEC.md active; shadow-mode exit criterion agreed in writing.
7. Advice-override and incident log in place; escalation: operator → shift lead → EHS → sponsor.

## PDPA
Process data holds no personal data by design. Operator accept/reject logs with timestamps and shifts can identify individuals, so: pseudonymous role IDs, no names; purpose limited to the pilot; lawful basis and notice confirmed by the DPO; retention period set by the DPO (proposed: delete at pilot close unless extended); access limited to the pilot team; no export outside the site.
