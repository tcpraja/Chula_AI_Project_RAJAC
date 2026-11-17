"""Append-only audit log in SQLite with a SHA-256 hash chain: who (role + role id), when, what was recommended, what was decided.

Roles: operator | engineer | admin, each allowed only certain actions. UPDATE and DELETE are blocked by triggers, and verify() recomputes the whole
chain, so edits made by bypassing the triggers (or editing the file) are detected. The log records opinions and events; it never actuates anything.
Run: python -m src.audit --verify [--db path]
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "audit_log.db"
ROLES = ("operator", "engineer", "admin")
ACTIONS = {"operator": {"DECISION"}, "engineer": {"DECISION", "MODEL_PROMOTION", "MODEL_REJECTION", "MONITOR_MODE", "CONFIG_REVIEW"},
           "admin": {"DECISION", "MODEL_PROMOTION", "MODEL_REJECTION", "MONITOR_MODE", "CONFIG_REVIEW", "CONFIG_CHANGE", "USER_ROLE_CHANGE", "ROLLBACK"}}
GENESIS = "0" * 64
SCHEMA = """CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('operator','engineer','admin')),
  actor_id TEXT NOT NULL, action TEXT NOT NULL, recommendation TEXT, decision TEXT, detail TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;"""


class AuditError(ValueError):
    pass


def _path(path=None):
    return Path(path or os.environ.get("HEATER_AUDIT_DB") or DB)


def connect(path=None):
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript(SCHEMA)
    return con


def compute_hash(prev, ts, role, actor, action, recommendation, decision, detail):
    body = json.dumps([prev, ts, role, actor, action, recommendation, decision, detail], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append(role, actor_id, action, recommendation=None, decision=None, detail=None, path=None):
    """Add one entry. Raises AuditError if the role may not perform the action. Returns the new entry hash."""
    if role not in ROLES:
        raise AuditError(f"role must be one of {ROLES}")
    if action not in ACTIONS[role]:
        raise AuditError(f"role '{role}' may not log action '{action}'")
    rec = recommendation if recommendation is None or isinstance(recommendation, str) else json.dumps(recommendation, sort_keys=True, default=str)
    det = detail if detail is None or isinstance(detail, str) else json.dumps(detail, sort_keys=True, default=str)
    ts = datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="microseconds")
    con = connect(path)
    try:
        with con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            h = compute_hash(prev, ts, role, actor_id, action, rec, decision, det)
            con.execute("INSERT INTO audit (ts, role, actor_id, action, recommendation, decision, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?)",
                        (ts, role, actor_id, action, rec, decision, det, prev, h))
        return h
    finally:
        con.close()


def verify(path=None):
    """(ok, problems). Recomputes every hash and checks each prev_hash links to the entry before it."""
    con = connect(path)
    try:
        rows = con.execute("SELECT id, ts, role, actor_id, action, recommendation, decision, detail, prev_hash, hash FROM audit ORDER BY id").fetchall()
    finally:
        con.close()
    problems, prev = [], GENESIS
    for (i, ts, role, actor, action, rec, dec, det, ph, h) in rows:
        if ph != prev:
            problems.append(f"entry {i}: chain broken (prev_hash mismatch)")
        if compute_hash(ph, ts, role, actor, action, rec, dec, det) != h:
            problems.append(f"entry {i}: content does not match its hash")
        prev = h
    return (not problems), problems


def read(path=None, limit=None):
    import pandas as pd
    con = connect(path)
    try:
        q = "SELECT id, ts, role, actor_id, action, recommendation, decision, detail, hash FROM audit ORDER BY id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        return pd.read_sql(q, con)
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    ok, problems = verify(a.db)
    n = len(read(a.db))
    print(f"audit log: {n} entries; chain {'VERIFIED' if ok else 'BROKEN'}")
    for p in problems:
        print("  " + p)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
