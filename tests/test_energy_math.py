"""Phase 6: independent recomputation of kWh and unit conversions, live-formula check of the xlsx, verbatim pilot targets/stops. SYNTHETIC."""
import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import economics, energy_calc
from src.xl_eval import Book

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
squash = lambda s: re.sub(r"\s+", " ", s)


@pytest.fixture(scope="module")
def book():
    return Book(REP / "economics_and_energy.xlsx")


@pytest.fixture(scope="module")
def runtimes():
    return pd.read_csv(REP / "ai_runtime_measured.csv").set_index("step")["wall_s_mean"]


def test_unit_conversions():
    assert energy_calc.mj_to_kwh(3.6) == pytest.approx(1.0)
    assert energy_calc.mj_to_kwh(-27211.8) == pytest.approx(-27211.8 / 3.6)
    assert 1000 * 3600 / 1e6 == pytest.approx(3.6)                      # 1 kWh = 3.6 MJ
    assert 60 * 3600 / 3.6e6 == pytest.approx(0.06)                     # 60 W for 1 h = 0.06 kWh


def test_ai_electricity_kwh_recomputed_independently(book, runtimes):
    page = np.mean([runtimes[i] for i in runtimes.index if i.startswith("dashboard_render_")])
    for col, (p_busy, p_open, n_tr, n_sh, open_h) in {"D": (100, 30, 14, 84, 10), "E": (60, 20, 7, 42, 6), "F": (35, 15, 3, 6, 3)}.items():
        busy_s = runtimes["generate"] * 1 + runtimes["train"] * n_tr + runtimes["shadow"] * n_sh \
            + (runtimes["dashboard_start_to_healthy"] + page * 200) * 30
        kwh = busy_s * p_busy / 3.6e6 + open_h * 30 * p_open / 1000
        rows = {r[0].value: r[0].row for r in book.wb["Model"].iter_rows(min_row=2, max_col=1)}
        assert book.value("Model", f"{col}{rows['kwh_6w']}") == pytest.approx(kwh, rel=1e-9)
        assert book.value("Model", f"{col}{rows['kwh_month']}") == pytest.approx(kwh * 30 / 42, rel=1e-9)
        assert book.value("Model", f"{col}{rows['kwh_year']}") == pytest.approx(kwh * 365 / 42, rel=1e-9)


def test_fuel_energy_recomputed_independently(book):
    recs = pd.DataFrame([json.loads(line) for line in (ROOT / "data" / "advisory" / "advisory_records_test.jsonl").read_text(encoding="utf-8").splitlines()])
    adv = recs[recs["decision"] == "ADVICE"].copy()
    d = pd.read_csv(ROOT / "data" / "clean" / "clean_heater_c.csv").set_index("timestamp_local")
    adv = adv.join(d[["fuel_rate_aligned_kgh", "LHV_used_MJkg", "fan_power_kW_FD"]], on="timestamp")
    frac = adv["uncertainty"].map(lambda u: u["dSFC_kg_GJ_point"]) / adv["predicted_SFC_current"]
    dkg = adv["fuel_rate_aligned_kgh"] * (5 / 60) * frac
    kwh = (dkg * adv["LHV_used_MJkg"]).sum() / 3.6
    ratio = adv["proposed_simulated_settings"].map(lambda p: p["FD_command_pct"]) / adv["current_simulated_settings"].map(lambda p: p["FD_command_pct"])
    fan = (adv["fan_power_kW_FD"] * (ratio ** 3 - 1) * (5 / 60)).sum()
    out = json.loads((REP / "energy_synthetic.json").read_text(encoding="utf-8"))
    assert out["delta_fuel_kg"]["point"] == pytest.approx(dkg.sum(), rel=1e-9)
    assert out["delta_fuel_energy_kWh_thermal"]["point"] == pytest.approx(kwh, rel=1e-9)
    assert out["fan_FD_delta_kWh_electric"] == pytest.approx(fan, rel=1e-9)
    assert out["delta_fuel_energy_kWh_thermal"]["lo90"] < out["delta_fuel_energy_kWh_thermal"]["point"] < out["delta_fuel_energy_kWh_thermal"]["hi90"] < 0
    rows = {r[0].value: r[0].row for r in book.wb["Model"].iter_rows(min_row=2, max_col=1)}
    assert book.value("Model", f"E{rows['kwh_fuel_pt']}") == pytest.approx(kwh, rel=1e-9)


def test_economics_chain_recomputed(book):
    A = {r[0].value: r for r in book.wb["Assumptions"].iter_rows(min_row=2)}
    M = {r[0].value: r[0].row for r in book.wb["Model"].iter_rows(min_row=2, max_col=1)}
    for ci, col in ((3, "D"), (4, "E"), (5, "F")):
        g = lambda k: A[k][ci].value
        eff = g("dfuel_pt") / (g("fuel_kgh") * g("win_h"))
        fuel_cost = g("fuel_kgh") * g("hours") / 1000 * g("price")
        gross = -eff * g("real") * fuel_cost
        kwh_year = book.value("Model", f"{col}{M['kwh_year']}")
        running = g("fan_kwh") / g("win_h") * g("hours") * g("tariff") + kwh_year * g("tariff") + g("rev_h") * 52 * g("rate") + g("upkeep")
        one_time = g("eng_d") * g("eng_rate") + g("co_an") + g("rev_h") * 6 * g("rate")
        net = gross - running
        assert book.value("Model", f"{col}{M['net']}") == pytest.approx(net, rel=1e-9)
        pb = book.value("Model", f"{col}{M['payback']}")
        assert (pb == "NO PAYBACK") if net <= 0 else (pb == pytest.approx(one_time / net, rel=1e-9))


def test_workbook_every_value_cell_is_labeled_and_formulas_are_live(book):
    for name in ("Assumptions", "Model", "Tornado"):
        ws = book.wb[name]
        assert [c.value for c in ws[1]][:3] == ["ID", ws["B1"].value, "Unit"]
        for row in ws.iter_rows(min_row=2):
            vals = [c.value for c in row]
            assert vals[0] and vals[1] and vals[2] and vals[6], f"{name} row {row[0].row} lacks id/label/unit/provenance"
            for c in row[3:6]:
                assert c.value is not None
    for row in book.wb["Model"].iter_rows(min_row=2):
        assert all(str(c.value).startswith("=") for c in row[3:6])                       # live formulas
    for row in book.wb["Tornado"].iter_rows(min_row=2):
        assert all(str(c.value).startswith("=") for c in row[3:6])
    assert "No CO2 figure" in json.dumps([c.value for r in book.wb["README"].iter_rows() for c in r])


def test_model_formula_in_sheet_is_the_generated_one(book):
    m = economics.model_rows()
    a = economics.assumptions()
    A_row = {k: i for i, k in enumerate(a, 2)}
    f = "=" + economics.build_formula("net", "E", m, A_row, {})
    M = {r[0].value: r[0].row for r in book.wb["Model"].iter_rows(min_row=2, max_col=1)}
    assert book.wb["Model"][f"E{M['net']}"].value == f


def test_pilot_targets_and_stops_are_verbatim():
    spec = squash((ROOT / "docs" / "PILOT_SPEC.md").read_text(encoding="utf-8"))
    targets = re.search(r"Targets \(proposed\): (.*?)\. Stop:", spec).group(1)
    stops = re.search(r"Stop: (.*?)\.$", spec.strip()).group(1)
    gate = squash((REP / "executive_decision_gate.md").read_text(encoding="utf-8"))
    assert targets in gate and stops in gate
    sc = list(csv.DictReader(open(REP / "pilot_scorecard.csv", encoding="utf-8")))
    assert [r["target_verbatim_from_PILOT_SPEC"] for r in sc if r["type"] == "target"] == [t.strip() for t in targets.split(";")]
    assert [r["target_verbatim_from_PILOT_SPEC"] for r in sc if r["type"] == "stop"] == [t.strip() for t in stops.split(";")]
    assert all(r["actual"] == "" and r["owner_role"] and r["method"] for r in sc)


def test_sop_header_and_no_names():
    assert (REP / "operator_SOP_draft.md").read_text(encoding="utf-8").startswith("# DRAFT — REQUIRES SITE/OEM/EHS/MOC APPROVAL")
    for f in ("pilot_plan_6_weeks.md", "risk_register.md", "executive_decision_gate.md", "privacy_PDPA.md"):
        assert "REQUIRES SITE/OEM/EHS/MOC APPROVAL" in (REP / f).read_text(encoding="utf-8")
