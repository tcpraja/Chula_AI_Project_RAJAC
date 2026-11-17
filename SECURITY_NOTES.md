# SECURITY_NOTES: read-only design, ports, no OT write path (v0.9)
DRAFT, REQUIRES SITE/OEM/EHS/MOC APPROVAL. To be reviewed by site OT security. Built on SYNTHETIC data only.

## Data flow (one direction only)
```
 Historian / DCS  --(a person exports a CSV; no live link)-->  incoming/ (read-only mount)
                                                                    |
                                  [ container: no network ]         v
                       check_mapping -> ingest -> clean -> score (shadow) -> monitor
                                                                    |
                                                                    v
               data/  models/  reports/  audit_log.db   (site folder)  --> dashboard on 127.0.0.1:8501 (people only read it)
 Dashboard decisions (accept/reject/defer) -> operator log + audit log only.  NOTHING flows back to the DCS / PLC / BMS / SIS.
```
The operator carries any decision into the existing DCS by hand, inside normal operating procedures and signed limits.

## What the software does not contain (checked by tests)
No OPC UA, OPC DA, Modbus, serial/COM, MQTT, socket-client, HTTP-client or database-write code in `src/adapters/`; the only module that opens a socket is `src/ops/tcp_proxy.py`, which forwards the dashboard port to one fixed target. No LLM or external API call at runtime. No setpoint, tag-write or interlock-bypass function exists anywhere in the repository.

## Ports and networks
| Item | Value |
|---|---|
| Dashboard | TCP 8501, published on 127.0.0.1 only (the `gateway` service) |
| App container | internal Docker network `backend` (no outbound route); read-only root filesystem; all capabilities dropped; no-new-privileges; non-root uid 10001 |
| Ops jobs (shadow, monitor, retrain) | `network_mode: none` |
| Gateway | the only container with a published port; it runs only the fixed forwarder. Block its outbound traffic on the host firewall as well. |
| Inbound from plant networks | none required |
Build-time network use: the image build downloads the base image and pinned Python packages once, on a build machine, not on the plant network.

## Files and secrets
No credentials are needed or stored. `.streamlit/secrets.toml` is git-ignored and unused. Site data, the operator log and the audit log are local files in SITE_DIR: restrict folder access to the pilot team. Operator IDs are roles (OP-A, OP-B) and the audit roles are operator/engineer/admin; no personal names, no usernames of plant systems.

## Integrity
The audit log is append-only with a SHA-256 hash chain (`python -m src.audit --verify`). The model registry records a data hash for every model version. Limits come only from the signed site config; any limit left as REQUIRES_OEM_APPROVAL forces NO_ADVICE, and ADVISORY mode is refused until limits and approvals are complete.

## Residual risks to review
A person could copy a wrong export (the checker verifies tags and units, not truth); the gateway's outbound capability needs a host firewall rule; the dashboard has no login, so it relies on the 127.0.0.1 binding and workstation access control.
