"""Operator decision log (SQLite, local file only). Role IDs OP-A / OP-B only; no names. SYNTHETIC SIMULATION.

A logged decision is a record of what a human said about a simulated advisory; it never actuates anything.
Run: python -m src.oplog --help
"""
import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "operator_log.db"
ROLES = ("OP-A", "OP-B")
DECISIONS = ("accept", "reject", "defer")
REASONS = ("agree_with_reason_codes", "consistent_with_current_practice", "disagree_process_condition", "disagree_model_unconvincing",
           "data_looks_wrong", "need_more_information", "other_see_note")
NOTE_MAX = 200
COLS = ["id", "logged_at", "role_id", "advisory_ts", "advisory_decision", "advisory_action", "decision", "reason_code", "note",
        "model_version", "data_source"]
SCHEMA = """CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, logged_at TEXT NOT NULL,
  role_id TEXT NOT NULL CHECK (role_id IN ('OP-A','OP-B')),
  advisory_ts TEXT NOT NULL, advisory_decision TEXT NOT NULL, advisory_action TEXT,
  decision TEXT NOT NULL CHECK (decision IN ('accept','reject','defer')),
  reason_code TEXT NOT NULL, note TEXT, model_version TEXT, data_source TEXT NOT NULL)"""


def connect(path=None):
    p = Path(path or os.environ.get("HEATER_OPLOG_DB") or DB)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute(SCHEMA)
    return con


def validate(role, decision, reason, note, advisory_decision):
    """List of problems (empty = OK). 'accept' is allowed only on an ADVICE record; the reason is mandatory."""
    errs = []
    if role not in ROLES:
        errs.append(f"role must be one of {ROLES}")
    if decision not in DECISIONS:
        errs.append(f"decision must be one of {DECISIONS}")
    if reason not in REASONS:
        errs.append("a reason is required")
    if note is not None and len(note) > NOTE_MAX:
        errs.append(f"note longer than {NOTE_MAX} characters")
    if decision == "accept" and advisory_decision != "ADVICE":
        errs.append("cannot accept a NO ADVICE row")
    return errs


def add(role, decision, reason, note, rec, data_source, path=None):
    errs = validate(role, decision, reason, note, rec.get("decision"))
    if errs:
        raise ValueError("; ".join(errs))
    now = datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="seconds")
    with connect(path) as con:
        con.execute("INSERT INTO decisions (logged_at, role_id, advisory_ts, advisory_decision, advisory_action, decision, reason_code, note,"
                    " model_version, data_source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (now, role, rec["timestamp"], rec["decision"], rec.get("action"), decision, reason, (note or "").strip(),
                     rec.get("model_version"), data_source))


def read(path=None):
    con = connect(path)
    try:
        return pd.read_sql("SELECT * FROM decisions ORDER BY id DESC", con)
    finally:
        con.close()


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()


if __name__ == "__main__":
    main()
