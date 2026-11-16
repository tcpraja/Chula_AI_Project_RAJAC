# Privacy and PDPA note — Heater C advisory (DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL, and review by the site data-protection contact)
This is a working note, not legal advice. Thailand's Personal Data Protection Act B.E. 2562 (2019) is the reference; the site's data-protection officer or legal counsel must confirm.

## 1 Data inventory
| Data | Personal data? | Where | Control |
|---|---|---|---|
| Process data (temperatures, flows, fuel, O2, commands) | No, equipment data | Synthetic files in data/; site historian export in a pilot | Read-only export; kept on site systems |
| Synthetic operator action log (shift IDs OP-A/OP-B/OP-C) | No, generator output | data/raw_synthetic/operator_action_log.csv | Synthetic only |
| Operator decision log (role ID, decision, reason, note, timestamp) | Possibly: a role ID plus shift timing can identify a person; free-text notes may contain names | data/operator_log.db (git-ignored), CSV export | Role IDs only; the schema rejects other IDs; 200-character note with "no personal names" warning; no names in reports |
| Screenshots, reports | Only if they show notes or IDs | assets/, reports/ | Review before sharing |
| Camera, audio, location, biometrics | Not collected | n/a | n/a |

## 2 Principles applied
- Minimisation: role IDs (OP-A, OP-B) instead of names; no usernames, employee numbers or contact data.
- Purpose limitation: decision logs are used only to score the pilot (acceptance, review time, false alerts) and improve the advice; not for performance appraisal of individuals. This must be written into the pilot approval.
- Offline processing: the tool uses no network, cloud service or external API at runtime; no cross-border transfer by the tool. Any transfer (for example e-mailing an export) is outside the tool and needs its own check.
- Retention (proposal): decision log kept for the pilot plus 90 days for the report, then deleted or anonymised; the site decides.
- Security: local files, access limited to the pilot team; the dashboard binds to 127.0.0.1 only.
- Transparency: operators are told what is logged, by role ID, why, and who can read it, before week 3. Participation in the blind review needs supervisor approval; employee representatives can be consulted per site practice.

## 3 Open items for the site
1. Confirm whether a role ID plus shift time counts as personal data on site (assume yes until confirmed).
2. Name the data controller and the privacy contact; decide whether a record of processing and a short impact assessment are required.
3. Decide retention and who may export the CSV.
4. Confirm that supplier and company names stay out of public outputs (anonymised as "PET Resin Plant P").
5. Re-check this note if cameras, voice or any identifiable feedback form are added.
