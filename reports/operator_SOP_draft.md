# DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL
# Operator SOP (draft) — Heater C advisory screen
Status: not approved, not in force, not for plant use. Written against the synthetic prototype to show the intended working method. Every site step must be rewritten and signed under the site MOC process.

## 1 Purpose and authority
The advisory screen is decision support. It never controls anything. The operator, shift supervisor, BMS, SIS, hardwired trips and DCS keep full authority. Nothing on the screen is an instruction.

## 2 Before the shift
1. Confirm the red banner is visible (SYNTHETIC SIMULATION — NOT FOR PLANT OPERATION in the prototype; ADVISORY ONLY — OPERATOR DECIDES after approval).
2. Confirm the data source and the time-zone label (Asia/Bangkok) and that the data are current, not frozen.
3. Confirm signed site limits are loaded. If the screen says limits are not approved, treat everything as NO ADVICE.

## 3 Reading a recommendation
| Screen shows | Meaning | Operator action |
|---|---|---|
| NO ADVICE (large, red) with reason codes | The system will not suggest anything now | Operate as usual; read the reason code; report repeated or odd codes to the process engineer |
| DIAGNOSTIC ONLY | CO or similar data missing; trends only | Use as information only |
| ADVICE (simulated option) with interval and checklist | A candidate small FD / grate change with uncertainty | Review the checklist; decide yourself; no obligation to act |
| Badge PROXY or UNAVAILABLE on a number | Estimated or not computable | Do not rely on it |

Always read: reason codes, interval width, constraint checklist (every line must pass), "human review required".

## 4 Making a decision (log it)
1. Enter your role ID (OP-A or OP-B), choose accept / reject / defer, choose a reason code, optionally add a short note. No names and no personal information in the note.
2. "Accept" means: I judge this reasonable and will consider it in the DCS myself. It applies nothing.
3. Target: review takes 2 minutes or less. If you cannot decide, defer.
4. Any change you make is made in the existing DCS, under normal operating procedures and signed limits.

## 5 Stop and escalate
Ignore the advice and call the shift supervisor if: any alarm, trip, interlock or fan derate is active; draft is outside the normal band; CO or O2 alarms; HTF temperature or flow looks abnormal; the screen shows stale data; or the advice contradicts your plant knowledge.
Report to EHS and OT at once any safety or OT incident, including a suspected link to the pilot (stop condition S1).

## 6 Never
Never treat the screen as a setpoint. Never bypass or reset an interlock because of it. Never enter personal names. Never use it while the banner or the data cannot be trusted.

## 7 Approvals still open before use
Site approval, OEM limits, EHS review, MOC record, operator training sign-off, privacy review.
