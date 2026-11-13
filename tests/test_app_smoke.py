"""Phase 5 dashboard smoke tests (streamlit.testing.v1.AppTest, one per page) + what-if / operator-log / shadow contracts. SYNTHETIC."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import guardrails as gd, oplog, shadow, whatif
from src.dashboard import common

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"p1_live": "Live Performance", "p2_combustion": "Combustion Diagnostics", "p3_recs": "AI Recommendations",
         "p4_whatif": "What-if Simulator", "p5_decisions": "Operator Decisions", "p6_value": "Business Value"}
SCRIPT = "import sys\nsys.path.insert(0, r'{root}')\nfrom src.dashboard import common, {mod}\ncommon.setup()\n{mod}.render()\n"


@pytest.fixture(autouse=True)
def tmp_log(tmp_path, monkeypatch):
    monkeypatch.setenv("HEATER_OPLOG_DB", str(tmp_path / "op.db"))


def page(mod):
    return AppTest.from_string(SCRIPT.format(root=ROOT, mod=mod), default_timeout=180)


def texts(at):
    return " ".join([m.value for m in at.markdown] + [e.value for e in at.error] + [c.value for c in at.caption] + [s.value for s in at.success])


def advisory():
    return [json.loads(line) for line in (ROOT / "data" / "advisory" / "advisory_records_test.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("mod", list(PAGES))
def test_page_runs_without_exception_and_has_banner(mod):
    at = page(mod).run()
    assert not at.exception, [e.value for e in at.exception]
    assert common.BANNER in texts(at)
    assert "Asia/Bangkok" in texts(at)


def test_app_entrypoint_runs():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    assert common.BANNER in texts(at)


def test_recommendations_shows_no_advice_on_gated_row():
    gated = next(r for r in advisory() if r["decision"] == "NO_ADVICE" and r["reason_codes"])
    at = page("p3_recs").run()
    at.session_state["rec_ts"] = gated["timestamp"]
    at.run()
    assert not at.exception
    t = texts(at)
    assert "NO ADVICE" in t and "HUMAN REVIEW REQUIRED" in t and gated["reason_codes"][0] in t
    assert "Proposed (simulated)" not in t


def test_recommendations_shows_proposal_only_on_advice_row():
    adv = next(r for r in advisory() if r["decision"] == "ADVICE")
    at = page("p3_recs").run()
    at.session_state["rec_ts"] = adv["timestamp"]
    at.run()
    assert not at.exception and "ADVICE (simulated)" in texts(at) and len(at.dataframe) >= 1


def test_whatif_out_of_bounds_gives_error_and_no_output():
    at = page("p4_whatif").run()
    assert not at.exception and len(at.metric) > 0           # default (HOLD) evaluates
    key = next(n.key for n in at.number_input if n.key.startswith("wi_fd_"))
    at.number_input(key).set_value(500.0)
    at.run()
    assert not at.exception
    assert any("out of bounds" in e.value for e in at.error)
    assert len(at.metric) == 0


def test_whatif_matches_advisory_record_and_rejects_bad_moves():
    G = gd.load_limits()
    d = common.load_default()
    rec = next(r for r in advisory() if r["decision"] == "ADVICE")
    row = d[d["timestamp_local"] == rec["timestamp"]].iloc[0]
    p = rec["proposed_simulated_settings"]
    res = whatif.evaluate(row, p["FD_command_pct"], p["grate_command_pct"], common.effect_model(), G)
    assert res["SFC_option"] == pytest.approx(rec["predicted_SFC_option"], abs=0.002)
    assert res["dSFC_lo90"] == pytest.approx(rec["uncertainty"]["dSFC_lo90"], abs=0.002)
    for fd, g in ((200, 40), (60, -5), (float("nan"), 40), (row["FD_command_pct"] + 10, row["grate_command_pct"])):
        assert whatif.validate(row, fd, g, G)
        with pytest.raises(ValueError):
            whatif.evaluate(row, fd, g, common.effect_model(), G)


def test_oplog_roles_reasons_and_gate(tmp_path):
    db = tmp_path / "t.db"
    adv = {"timestamp": "2026-03-01 00:35:00+07:00", "decision": "ADVICE", "action": "FD-2", "model_version": "v"}
    gated = {**adv, "decision": "NO_ADVICE", "action": "NONE"}
    oplog.add("OP-A", "accept", "agree_with_reason_codes", "ok", adv, "synthetic", db)
    oplog.add("OP-B", "defer", "need_more_information", "", gated, "synthetic", db)
    for args in (("OP-C", "accept", "other_see_note", "", adv), ("OP-A", "accept", "", "", adv), ("OP-A", "accept", "other_see_note", "", gated),
                 ("OP-A", "approve", "other_see_note", "", adv), ("OP-A", "reject", "other_see_note", "x" * 201, adv)):
        with pytest.raises(ValueError):
            oplog.add(*args, "synthetic", db)
    log = oplog.read(db)
    assert len(log) == 2 and set(log["role_id"]) == {"OP-A", "OP-B"}
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):               # schema itself rejects other roles
        oplog.connect(db).execute("INSERT INTO decisions (logged_at,role_id,advisory_ts,advisory_decision,decision,reason_code,data_source)"
                                  " VALUES ('t','Somchai','t','ADVICE','accept','r','s')")


def test_operator_page_logs_a_decision():
    at = page("p5_decisions").run()
    assert not at.exception
    at.text_input[0].set_value("smoke test")
    submit = next(b for b in at.button if b.label == "Log decision")
    submit.click()
    at.run()
    assert not at.exception
    log = oplog.read()
    assert len(log) == 1 and log.at[0, "role_id"] == "OP-A" and log.at[0, "note"] == "smoke test"


def test_upload_schema_check_rejects_bad_file():
    d = common.load_default()
    assert common.schema_check(d) == []
    assert common.schema_check(d.drop(columns=["O2_pct_dry"])) and common.schema_check(d.head(3))


def test_shadow_file_exists_and_is_failsafe():
    s = pd.read_csv(ROOT / "reports" / "shadow_replay.csv")
    assert {"ai_decision", "reason_codes", "rule_P75_alert", "agreement"} <= set(s.columns)
    assert s["human_review_required"].all()
    assert not s[(s["ai_decision"] != "ADVICE") & s["action"].ne("NONE")].shape[0]
    assert s.loc[s["ai_decision"] == "NO_ADVICE", "reason_codes"].notna().all()


def test_shadow_replay_is_deterministic(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    shadow.run("test", a)
    shadow.run("test", b)
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    assert a.read_bytes() == (ROOT / "reports" / "shadow_replay.csv").read_bytes()
