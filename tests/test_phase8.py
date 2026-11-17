"""Phase 8 pilot package (SYNTHETIC only): adapters + units, check_mapping, site config, guardrails with placeholders, registry promotion, drift -> NO_ADVICE,
audit tamper detection, M&V recovers a known effect, packaging and script checks."""
import copy
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src import audit, guardrails as gd, monitor, mv_report as mv, retrain, site_config as sc
from src.adapters import check_mapping as cm, tagmap as tm
from src.adapters.csv_export import CsvExportSource
from src.adapters.synthetic import SyntheticSource, to_site_export

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def raw():
    return pd.read_csv(ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv").iloc[:3000].reset_index(drop=True)


@pytest.fixture(scope="module")
def filled():
    return tm.synthetic_site_map()


# ------------------------------------------------------------------ adapters and units
def test_site_style_csv_round_trip_and_unit_conversions(raw, filled, tmp_path):
    export = to_site_export(raw, filled)
    f = tmp_path / "site_export.csv"
    export.to_csv(f, index=False)
    assert "SITE_DRAFT_PA" in export.columns and "draft_pa" not in export.columns            # site tag names
    assert np.allclose(export["SITE_DRAFT_PA"], raw["draft_pa"] / 9.80665)                    # site unit mmWC
    assert np.allclose(export["SITE_FUEL_RATE_MEASURED_KGH"], raw["fuel_rate_measured_kgh"] / 3600)    # kg/s
    assert np.allclose(export["SITE_Q_OUT_MW"], raw["Q_out_MW"] / 1.16222)                    # Mkcal/h
    res = CsvExportSource(f, filled).read()
    back = res.df
    assert np.allclose(back["draft_pa"], raw["draft_pa"]) and np.allclose(back["Q_out_MW"], raw["Q_out_MW"])          # mmWC->Pa, Mkcal/h->MW
    assert np.allclose(back["fuel_rate_measured_kgh"], raw["fuel_rate_measured_kgh"])                                  # kg/s->kg/h
    assert (back["heater_id"] == "HEATER_C_SYNTHETIC").all() and res.meta["unavailable_combustion"] == []
    assert np.allclose(SyntheticSource().read().df["draft_pa"].iloc[:3000], raw["draft_pa"])


def test_conversion_constants_are_the_project_ones():
    from src.adapters import conversions as cv
    assert cv.apply(pd.Series([1.0]), "mmwc_to_pa")[0] == pytest.approx(9.80665)
    assert cv.apply(pd.Series([1.0]), "mkcal_h_to_mw")[0] == pytest.approx(1.16222)
    assert cv.apply(pd.Series([1.0]), "kgs_to_kgh")[0] == pytest.approx(3600)
    assert cv.apply(pd.Series([2.0]), {"factor": 3, "offset": 1})[0] == pytest.approx(7)
    assert not cv.is_known("furlongs_per_fortnight")


def test_tag_map_template_covers_every_dictionary_column_and_forces_a_decision():
    t = tm.load()
    dic = pd.read_csv(ROOT / "reports" / "03_data_dictionary.csv")["column"].astype(str)
    assert set(dic) - {"timestamp_local"} <= set(t["columns"])
    site = {n: e for n, e in t["columns"].items() if e["source"] == "site"}
    assert site and all(e["available"] is None and e["site_tag"] == tm.PLACEHOLDER for e in site.values())
    assert all(e["available"] is False for e in t["columns"].values() if e["source"] == "generator_only")
    assert {"mmwc_to_pa", "mkcal_h_to_mw", "kgs_to_kgh"} <= {e["conversion"] for e in site.values()}


def test_check_mapping_refuses_unmapped_critical_tags_and_undecided_columns(filled):
    codes = {c for c, _ in cm.check(tm.load())}
    assert {"UNMAPPED_CRITICAL", "UNDECIDED"} <= codes                                    # the untouched template is refused
    assert cm.check(filled) == []
    bad = copy.deepcopy(filled)
    bad["columns"]["HTF_flow_m3h"]["site_tag"] = tm.PLACEHOLDER
    assert ("UNMAPPED_CRITICAL", "HTF_flow_m3h") in cm.check(bad)
    bad = copy.deepcopy(filled)
    bad["columns"]["draft_pa"]["available"] = False
    assert ("UNAVAILABLE_CRITICAL", "draft_pa") in cm.check(bad)
    bad = copy.deepcopy(filled)
    bad["columns"]["CO_ppm"]["conversion"] = "nonsense"
    assert ("UNKNOWN_CONVERSION", "CO_ppm") in cm.check(bad)
    bad = copy.deepcopy(filled)
    bad["columns"]["O2_pct_dry"]["site_tag"] = bad["columns"]["CO_ppm"]["site_tag"]
    assert ("DUPLICATE_TAG", "O2_pct_dry") in cm.check(bad)
    assert ("TAG_NOT_IN_EXPORT", "draft_pa") in cm.check(filled, header=["SITE_TIME"])


def test_check_mapping_cli_prints_names_only_and_exit_code(tmp_path, capsys):
    f = tmp_path / "x.csv"
    pd.DataFrame({"SITE_TIME": ["2026-01-01 00:00:00"], "SITE_HTF_FLOW_M3H": [123456.789]}).to_csv(f, index=False)
    assert cm.main(["--tag-map", str(ROOT / "config" / "tag_map_template.yaml"), "--path", str(f)]) == 2
    out = capsys.readouterr().out
    assert "REFUSED" in out and "123456" not in out                                       # no data values are printed


def test_unavailable_combustion_columns_force_diagnostic_only(raw, filled, tmp_path):
    from src import pipeline
    m = copy.deepcopy(filled)
    m["columns"]["CO_ppm"]["available"] = False
    m["columns"]["O2_pct_dry"]["available"] = False
    f = tmp_path / "e.csv"
    to_site_export(raw, filled).to_csv(f, index=False)
    res = CsvExportSource(f, m).read()
    assert set(res.meta["unavailable_combustion"]) == {"CO_ppm", "O2_pct_dry"} and (res.df["co_available"] == 0).all()
    site = sc.load_site(ROOT / "config" / "site_synthetic_demo.yaml")
    full, *_ = pipeline.clean_frame(res.df, site.cleaning_cfg())
    out = gd.evaluate(full, site.guardrail_config())
    assert (out["outcome"] != "ELIGIBLE").all() and (out["outcome"] == "DIAGNOSTIC_ONLY").sum() > 0
    full_ok, *_ = pipeline.clean_frame(CsvExportSource(f, filled).read().df, site.cleaning_cfg())
    assert (gd.evaluate(full_ok, site.guardrail_config())["outcome"] == "ELIGIBLE").sum() > 0     # with CO and O2 the same rows can be eligible


def test_adapters_have_no_plant_write_or_network_code():
    import ast
    banned = re.compile(r"opcua|asyncua|pymodbus|modbus|serial|requests|urllib|http|socket|paho|mqtt|sqlite3|psycopg|pyodbc|sqlalchemy|write_register|write_coil|write_tag|write_node|"
                        r"write_value|set_value|set_node|publish", re.I)
    for p in (ROOT / "src" / "adapters").glob("*.py"):
        names = set()
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):          # imports and identifiers only; docstrings and comments are ignored
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.FunctionDef):
                names.add(node.name)
        assert not [n for n in names if banned.search(n)], (p.name, [n for n in names if banned.search(n)])
    from src.adapters.base import ReadOnlySource
    assert {m for m in dir(ReadOnlySource) if not m.startswith("_")} == {"describe", "kind", "read"}      # no write/publish/connect methods


# ------------------------------------------------------------------ site config
def test_site_template_is_shadow_only_until_limits_and_approval_are_complete(tmp_path):
    s = sc.load_site(ROOT / "config" / "site_template.yaml")
    assert s.mode == "SHADOW" and len(s.unfilled_limits()) == len(s.limits) == 13
    s.validate()                                                                           # SHADOW is allowed
    raw_cfg = copy.deepcopy(s.raw)
    raw_cfg["mode"] = "ADVISORY"
    with pytest.raises(sc.SiteConfigError, match="limits not filled"):
        sc.SiteConfig(raw_cfg, s.path).validate()
    full = yaml.safe_load((ROOT / "config" / "site_synthetic_demo.yaml").read_text(encoding="utf-8"))
    full["mode"] = "ADVISORY"
    full["approval"] = {"approver": None, "date": "2026-01-01", "moc_reference": "X"}
    with pytest.raises(sc.SiteConfigError, match="approval fields missing"):
        sc.SiteConfig(full, s.path).validate()
    full["approval"] = {"approver": "Plant manager (role)", "date": "2026-01-01", "moc_reference": "MOC-1"}
    ok = sc.SiteConfig(full, s.path).validate()
    assert ok.banner() == "ADVISORY ONLY — OPERATOR DECIDES"
    assert sc.SiteConfig({**full, "mode": "SHADOW"}, s.path).banner().startswith("SHADOW MODE")
    with pytest.raises(sc.SiteConfigError):
        sc.SiteConfig({**full, "mode": "AUTO"}, s.path).validate()


def test_mode_environment_variable_cannot_bypass_the_advisory_refusal(monkeypatch):
    s = sc.load_site(ROOT / "config" / "site_template.yaml")
    monkeypatch.setenv("MODE", "ADVISORY")
    with pytest.raises(sc.SiteConfigError):
        s.validate()


def test_placeholder_limits_force_no_advice_on_every_row():
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv").iloc[2000:2400]
    cfg = sc.load_site(ROOT / "config" / "site_template.yaml").guardrail_config()
    out = gd.evaluate(d, cfg)
    assert (out["outcome"] == "NO_ADVICE").all() and (out["reason_codes"] == "LIMITS_NOT_APPROVED").all()
    assert gd.unapproved(cfg)
    filled_cfg = sc.load_site(ROOT / "config" / "site_synthetic_demo.yaml").guardrail_config()
    assert not gd.unapproved(filled_cfg)


def test_partial_site_limits_stay_fail_safe():
    s = sc.load_site(ROOT / "config" / "site_synthetic_demo.yaml")
    part = sc.SiteConfig({**s.raw, "limits": {"o2_floor_pct": 5.0}}, s.path)
    assert part.guardrail_config()["limits"]["draft_band_pa"] == gd.PLACEHOLDER


# ------------------------------------------------------------------ registry and promotion
def test_promotion_rule():
    p = retrain.promotion_decision
    assert p(54.0, 50.0, 106.0, True)["decision"] == "PROMOTE"
    assert p(54.0, 54.0, 106.0, True)["decision"] == "KEEP_CHAMPION"                       # not better
    assert p(54.0, 50.0, 106.0, False)["decision"] == "KEEP_CHAMPION"                      # guardrail tests fail
    assert p(54.0, 50.0, 52.0, True)["decision"] == "KEEP_CHAMPION"                        # not 10 % better than the simple regression
    assert p(54.0, 50.0, 106.0, True, approver=None, require_approver=True)["decision"] == "KEEP_CHAMPION"
    assert p(54.0, 50.0, 106.0, True, approver="Process engineer (role)", require_approver=True)["decision"] == "PROMOTE"
    assert p(54.0, None, 106.0, True)["decision"] == "KEEP_CHAMPION"
    assert p(60.0, 59.0, 62.0, True)["simple_recommended"] is True                         # champion itself is not 10 % better than the simple model


def test_registry_promote_retires_previous_and_logs(tmp_path):
    reg_path, audit_db = tmp_path / "registry.json", tmp_path / "a.db"
    reg = retrain.init_registry(reg_path)
    first = reg["champion"]
    entry = retrain.new_entry("L-new", "abc", {"test_mae_kgh": 50.0}, "challenger", "Process engineer (role)")
    reg = retrain.promote(reg, entry, audit_path=audit_db)
    assert reg["champion"] == "L-new" and [e["status"] for e in reg["entries"]] == ["retired", "champion"] and reg["entries"][0]["version"] == first
    assert {"version", "data_sha256", "metrics", "approver"} <= set(reg["entries"][-1])
    retrain.save_registry(reg, reg_path)
    assert retrain.load_registry(reg_path)["champion"] == "L-new"
    assert audit.verify(audit_db)[0] and len(audit.read(audit_db)) == 1


def test_committed_registry_lists_the_current_champion():
    reg = json.loads((ROOT / "models" / "registry.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "models" / "metadata.json").read_text(encoding="utf-8"))
    assert reg["champion"].startswith(meta["selected"]) and reg["entries"][0]["data_sha256"] == meta["data_sha256"]


# ------------------------------------------------------------------ monitor and drift
def test_psi_detects_a_shift_and_ignores_noise():
    rng = np.random.default_rng(0)
    a, b = rng.normal(8.5, 1.0, 5000), rng.normal(8.5, 1.0, 2000)
    assert monitor.psi(a, b) < 0.05
    assert monitor.psi(a, rng.normal(10.5, 1.0, 2000)) > 0.25
    assert np.isnan(monitor.psi(a, b[:10]))                                                # too little data: no guess


def test_drift_and_data_failure_switch_to_no_advice(tmp_path, monkeypatch):
    cfg = monitor.load_cfg()
    rng = np.random.default_rng(1)
    ref = pd.DataFrame({f: rng.normal(10, 1, 4000) for f in cfg["psi_features"] if f != "fuel_moisture_wb_pct"})
    cur = ref.sample(1000, random_state=2).copy()
    cur["Q_out_MW"] = cur["Q_out_MW"] + 3.0                                                # a clear drift in load
    ref["fuel_lot"] = cur["fuel_lot"] = "L"
    ref["fuel_moisture_wb_pct"] = cur["fuel_moisture_wb_pct"] = np.nan
    t = monitor.drift_table(ref, cur, cfg).set_index("feature")
    assert t.loc["Q_out_MW", "status"] == "DRIFT" and t.loc["fuel_moisture_wb_pct", "status"] == "INSUFFICIENT_DATA"
    mode, reasons = monitor.decide_mode({"psi_max_value": float(t["psi"].max()), "psi_worst_feature": "Q_out_MW", "invalid_days_consecutive": 0, "weeks_worse_trailing": 0}, cfg)
    assert mode == "NO_ADVICE" and reasons[0].startswith("MODEL_DRIFT")
    assert monitor.decide_mode({"invalid_days_consecutive": 4}, cfg)[1][0].startswith("DATA_FAILURE")
    assert monitor.decide_mode({"invalid_days_consecutive": 3}, cfg)[0] == "NORMAL"          # stop only above 3 consecutive days
    assert monitor.decide_mode({"weeks_worse_trailing": 2}, cfg)[1][0].startswith("MAE_WORSE")
    assert monitor.decide_mode({"false_alerts_per_shift": 3.5}, cfg)[1][0].startswith("FALSE_ALERTS")
    assert monitor.decide_mode({"psi_max_value": 0.05, "invalid_days_consecutive": 0, "weeks_worse_trailing": 0, "false_alerts_per_shift": 1.0}, cfg)[0] == "NORMAL"
    # the forced mode reaches the guardrails and the dashboard gate
    mode_file = tmp_path / "mode.json"
    mode_file.write_text(json.dumps({"mode": "NO_ADVICE", "reasons": ["MODEL_DRIFT: x", "DATA_FAILURE: y"]}), encoding="utf-8")
    monkeypatch.delenv("HEATER_SITE", raising=False)
    monkeypatch.delenv("HEATER_ENFORCE_MONITOR", raising=False)
    assert monitor.enforced_codes(mode_file) == []                                         # not enforced in the plain synthetic demo
    monkeypatch.setenv("HEATER_ENFORCE_MONITOR", "1")
    codes = monitor.enforced_codes(mode_file)
    assert codes == ["MODEL_DRIFT", "DATA_FAILURE"]
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv").iloc[5000:5300]
    out = gd.evaluate(d, gd.load_limits(), force_codes=codes)
    assert (out["outcome"] == "NO_ADVICE").all() and out["reason_codes"].str.contains("MODEL_DRIFT").all()


def test_monitor_runs_on_synthetic_and_writes_the_files(tmp_path):
    m = monitor.run(tmp_path, quiet=True)
    for f in ("latest.json", "psi.csv", "weekly_mae.csv", "daily_quality.csv", "mode.json"):
        assert (tmp_path / f).exists(), f
    assert 90 < m["data_quality_pct"] <= 100 and 0 < m["eligible_pct"] < 100 and m["mode"] in ("NORMAL", "NO_ADVICE")
    psi = pd.read_csv(tmp_path / "psi.csv").set_index("feature")
    assert psi.loc["fuel_moisture_wb_pct", "level"] == "lot"                                # lot-level feature counted per lot, not per row


# ------------------------------------------------------------------ audit log
def test_audit_chain_verifies_and_blocks_edits(tmp_path):
    db = tmp_path / "audit.db"
    for i in range(3):
        audit.append("operator", "OP-A", "DECISION", {"advisory_ts": f"t{i}", "action": "FD-2"}, "accept:agree", None, db)
    audit.append("engineer", "ENG-1", "MODEL_PROMOTION", {"version": "v2"}, "PROMOTE", "metrics", db)
    ok, problems = audit.verify(db)
    assert ok and problems == [] and len(audit.read(db)) == 4
    con = audit.connect(db)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("UPDATE audit SET decision='reject' WHERE id=1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("DELETE FROM audit WHERE id=2")
    con.close()


def test_audit_tamper_is_detected_even_when_the_triggers_are_bypassed(tmp_path):
    db = tmp_path / "audit.db"
    for i in range(4):
        audit.append("operator", "OP-B", "DECISION", {"n": i}, f"defer:{i}", None, db)
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER audit_no_update")
    con.execute("UPDATE audit SET decision='accept:forged' WHERE id=2")                       # edit a decision
    con.commit()
    con.close()
    ok, problems = audit.verify(db)
    assert not ok and any("entry 2" in p and "hash" in p for p in problems)
    shutil.copy(db, tmp_path / "b.db")
    con = sqlite3.connect(tmp_path / "b.db")
    con.execute("DROP TRIGGER audit_no_delete")
    con.execute("DELETE FROM audit WHERE id=3")                                               # remove an entry
    con.commit()
    con.close()
    assert not audit.verify(tmp_path / "b.db")[0]


def test_audit_roles_are_enforced(tmp_path):
    db = tmp_path / "audit.db"
    with pytest.raises(audit.AuditError):
        audit.append("operator", "OP-A", "MODEL_PROMOTION", None, None, None, db)
    with pytest.raises(audit.AuditError):
        audit.append("engineer", "ENG-1", "USER_ROLE_CHANGE", None, None, None, db)
    with pytest.raises(audit.AuditError):
        audit.append("visitor", "X", "DECISION", None, None, None, db)
    audit.append("admin", "ADM-1", "USER_ROLE_CHANGE", None, "OP-C removed", None, db)
    assert audit.verify(db)[0]


def test_operator_decisions_are_copied_into_the_audit_log(tmp_path):
    from src import oplog
    rec = {"timestamp": "2026-03-01 00:35:00+07:00", "decision": "ADVICE", "action": "FD-2", "model_version": "v"}
    oplog.add("OP-A", "accept", "agree_with_reason_codes", "", rec, "synthetic")
    a = audit.read()
    assert len(a) == 1 and a.iloc[0]["role"] == "operator" and a.iloc[0]["actor_id"] == "OP-A" and "accept" in a.iloc[0]["decision"]
    assert audit.verify()[0]


# ------------------------------------------------------------------ M&V
@pytest.fixture(scope="module")
def prepared():
    return mv.prepare(pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv"))


def test_mv_recovers_a_known_effect_inside_its_interval_and_claims_nothing_for_zero(prepared):
    bm, tm_, how = mv.windows(prepared, "retrospective")
    null = mv.estimate(prepared, bm, tm_, n_boot=200)
    assert null["ok"] and null["ci90_lo"] < 0 < null["ci90_hi"] and not null["saving_reported"] and "NO SAVING CLAIMED" in null["verdict"]
    for true in (-0.03, -0.01):
        x = prepared.copy()
        x.loc[tm_, "sfc"] = x.loc[tm_, "sfc"] * (1 + true)
        r = mv.estimate(x, bm, tm_, n_boot=200)
        lo, hi = r["ci90_pct"]
        assert lo <= 100 * true <= hi, (true, lo, hi)                                      # known effect inside the 90 % CI
        assert abs(r["delta_pct"] - 100 * true) < 0.5
        assert r["saving_reported"] and "SAVING" in r["verdict"]
    worse = prepared.copy()
    worse.loc[tm_, "sfc"] = worse.loc[tm_, "sfc"] * 1.03
    assert mv.estimate(worse, bm, tm_, n_boot=100)["verdict"].startswith("SFC INCREASE")


def test_mv_trial_mode_refuses_to_guess_windows_and_writes_a_report(prepared, tmp_path):
    with pytest.raises(SystemExit, match="REFUSED"):
        mv.windows(prepared, "trial")
    bm, tm_, _ = mv.windows(prepared, "trial", cli={"baseline_start": "2026-02-28", "baseline_end": "2026-03-02", "trial_start": "2026-03-04", "trial_end": "2026-03-10"})
    assert bm.sum() > 0 and tm_.sum() > 0 and not (bm & tm_).any()
    md = mv.write_report(mv.estimate(prepared, prepared["t_local"] < "2026-02-10", prepared["t_local"] >= "2026-02-10", 100), "retrospective", "test", tmp_path, 3.6)
    assert md.exists() and "Fan penalty" in md.read_text(encoding="utf-8") and (tmp_path / "mv_retrospective.json").exists()


# ------------------------------------------------------------------ packaging
def test_dockerfile_is_slim_non_root_and_has_no_download_steps():
    t = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.11-slim", t, re.M) and re.search(r"^USER heater", t, re.M) and "useradd" in t and "--uid 10001" in t
    assert not re.search(r"curl |wget |ADD http|--privileged|sudo", t)
    assert "pip install -r requirements-runtime.txt" in t and "EXPOSE 8501" in t


def test_compose_has_no_outbound_path_for_the_app_and_jobs():
    c = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert c["networks"]["backend"]["internal"] is True
    assert c["services"]["app"]["networks"] == ["backend"] and c["services"]["app"]["read_only"] is True and c["services"]["app"]["cap_drop"] == ["ALL"]
    for job in ("shadow", "monitor", "retrain"):
        assert c["services"][job]["network_mode"] == "none" and c["services"][job]["profiles"] == ["ops"]
    assert c["services"]["gateway"]["ports"] == ["127.0.0.1:8501:8501"]
    assert all(":ro" in v for v in c["services"]["app"]["volumes"] if "/config" in v or "/incoming" in v)


def test_compose_file_validates_if_docker_is_installed():
    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    r = subprocess.run(["docker", "compose", "config", "-q"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0 and "compose" in r.stderr.lower() and "not a docker command" in r.stderr.lower():
        pytest.skip("docker compose plugin missing")
    assert r.returncode == 0, r.stderr[:300]


def test_docker_build_smoke_only_when_explicitly_enabled():
    """A build downloads the base image and packages (network), so it runs only with RUN_DOCKER_BUILD=1 and a docker daemon."""
    import os
    if os.environ.get("RUN_DOCKER_BUILD") != "1" or shutil.which("docker") is None:
        pytest.skip("set RUN_DOCKER_BUILD=1 to run (needs network for the base image and pinned packages)")
    r = subprocess.run(["docker", "build", "-t", "heater-c-advisory:smoke", "."], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]


def test_site_documents_exist_and_state_no_ot_write_path():
    for f in ("INSTALL_SITE.md", "OPERATIONS.md", "ROLLBACK.md", "SECURITY_NOTES.md"):
        t = (ROOT / f).read_text(encoding="utf-8")
        assert "REQUIRES SITE/OEM/EHS/MOC APPROVAL" in t, f
    sec = (ROOT / "SECURITY_NOTES.md").read_text(encoding="utf-8")
    assert "NOTHING flows back" in sec and "127.0.0.1" in sec and "8501" in sec and "no OPC" not in sec.lower().replace("no opc ua", "")
    assert "Stop: any safety/OT incident linked to pilot" in (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")


def test_real_data_scripts_print_paths_only_and_take_site_and_path_parameters():
    for f, must in (("run_real_retrospective.ps1", ["$Site", "$Path", "$OutDir", "check_mapping", "src.pipeline", "src.monitor", "src.mv_report", "retrospective"]),
                    ("run_real_live_shadow.ps1", ["$SiteDir", "MODE=SHADOW", "--network none", "docker run", "--read-only"]),
                    ("run_real_mv.ps1", ["$Site", "$Workspace", "--mode", "trial", "src.mv_report"])):
        t = (ROOT / f).read_text(encoding="utf-8")
        for m in must:
            assert m in t, (f, m)
        assert not re.search(r"Import-Csv|Get-Content\s+\$Path|Write-Host\s+\$\w*(data|row)", t, re.I), f      # data values are never read or echoed
        assert "RedirectStandardOutput" in t or "docker run" in t                                            # program output goes to log files
