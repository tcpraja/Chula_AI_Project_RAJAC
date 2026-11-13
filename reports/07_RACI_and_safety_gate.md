# 07 RACI and Safety Gate (roles only; no person names)
R = responsible, A = accountable, C = consulted, I = informed, V = veto right.

| Activity | Operator | Shift lead | Process eng. | Energy mgr | EHS | OT/IT | OEM | Sponsor |
|---|---|---|---|---|---|---|---|---|
| Scope and charter | I | I | R | C | C | C | I | A |
| Tag walk-down and data export (read-only) | C | C | R | I | C | A/V | C | I |
| Guardrail and limit definition (signed site config) | C | C | R | I | A/V | C | V | I |
| Shadow-mode review (blind) | R | A | C | I | I | I | I | I |
| Advisory use (supervised, operator decides in DCS) | R | A | C | I | V | C | C | I |
| Savings claim (M&V) | I | I | C | R | I | I | I | A |
| Stop / go decision | C | C | C | C | V | C | C | A |

## Veto rights
- EHS: any advice touching combustion safety, draft, or interlock margins; any safety incident stops the pilot.
- OT/IT: any connection to plant network; any write path (none permitted).
- OEM: operating envelopes and any REQUIRES_OEM_APPROVAL limit.
- Shift lead and operator: may ignore any advice at any time without justification; rejection reasons are logged.
- Sponsor: accountable for go/revise/stop.

## Safety gate (all must be true before Level 2 advisory)
1. Signed site config with real limits; otherwise NO_ADVICE.
2. Every recommendation shows "ADVISORY ONLY — OPERATOR DECIDES"; guardrails re-checked at display time.
3. No write access to DCS/PLC/BMS/SIS; no bypass of any interlock.
4. MOC (management of change) raised and approved.
5. Stop conditions per docs/PILOT_SPEC.md active.

## PDPA
Process data contains no personal data by design; operator accept/reject logs use role or pseudonymous IDs, not names; purpose limited to the pilot; retention and deletion agreed with the data owner; access restricted to the pilot team.
