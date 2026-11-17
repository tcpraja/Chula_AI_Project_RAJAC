"""Tag map: site historian tag -> internal column, with unit, conversion, availability and criticality (SYNTHETIC template).

Every column of reports/03_data_dictionary.csv gets an entry: source = site (measured at the site), computed (derived by this tool) or
generator_only (synthetic truth/labels, never available at a site). Site columns carry available: true|false|null (null = the site
has not decided yet; check_mapping refuses it). Unavailable COMBUSTION columns (O2, CO, furnace/flue/stack temperature, economizer dP)
force DIAGNOSTIC_ONLY downstream (guardrails). No tag names in this repository are real; placeholders are '<SITE_TAG>'.
Run: python -m src.adapters.tagmap --write-template
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "config" / "tag_map_template.yaml"
PLACEHOLDER = "<SITE_TAG>"
DICTIONARY = ROOT / "reports" / "03_data_dictionary.csv"
# internal, group, critical, combustion, internal_unit, example site unit (None = same), conversion, default if unavailable, note
META = [
    ("operating_mode", "state", True, False, "-", None, "identity", None, "value_map site status -> STARTUP|STEADY|RAMP|STANDBY|TRIP|FEEDER_STOP"),
    ("fuel_lot", "fuel lot", True, False, "-", None, "identity", None, "lot / batch id; needed for lot-aware splits"),
    ("fuel_moisture_wb_pct", "fuel lot", False, False, "%wb", None, "identity", None, "lab result per lot"),
    ("fuel_LHV_asfired_MJkg", "fuel lot", False, False, "MJ/kg", None, "identity", None, "lab result per lot; absent = LHV unknown (never invented)"),
    ("fuel_rate_measured_kgh", "fuel rate", True, False, "kg/h", "kg/s", "kgs_to_kgh", None, "belt-weigher rate; kg/s on many displays"),
    ("fuel_totalizer_kg", "fuel rate", False, False, "kg", "t", "t_to_kg", None, "totalizer (resets are detected)"),
    ("HTF_flow_m3h", "HTF", True, False, "m3/h", None, "identity", None, "HTF volumetric flow"),
    ("HTF_Tin_C", "HTF", True, False, "degC", None, "identity", None, "HTF return temperature"),
    ("HTF_Tout_C", "HTF", True, False, "degC", None, "identity", None, "HTF supply temperature"),
    ("HTF_Tout_SP_C", "HTF", False, False, "degC", None, "identity", None, "HTF supply set point"),
    ("HTF_bypass_pct", "HTF", False, False, "%", None, "identity", None, "bypass opening; absent = heat balance UNVERIFIED"),
    ("HTF_pump_status", "HTF", False, False, "0/1", None, "identity", None, "pump running"),
    ("Q_out_MW", "energy", False, False, "MW", "Mkcal/h", "mkcal_h_to_mw", None, "reported (display) heat; used only for unit-slip checks"),
    ("Q_in_MW", "energy", False, False, "MW", "Mkcal/h", "mkcal_h_to_mw", None, "reported fuel heat (display)"),
    ("eta_direct_pct", "energy", False, False, "%", None, "identity", None, "reported efficiency (display)"),
    ("SFC_kg_GJ", "energy", False, False, "kg/GJ", None, "identity", None, "reported SFC (display)"),
    ("O2_pct_dry", "combustion", False, True, "% dry", None, "identity", None, "flue-gas O2; basis (wet/dry) must be confirmed"),
    ("CO_ppm", "combustion", False, True, "ppm", None, "identity", None, "flue-gas CO; absent = NO_CO"),
    ("furnace_temp_C", "combustion", False, True, "degC", None, "identity", None, "furnace temperature"),
    ("flue_temp_C", "combustion", False, True, "degC", None, "identity", None, "flue temperature"),
    ("stack_temp_C", "combustion", False, True, "degC", None, "identity", None, "stack temperature"),
    ("economizer_dP_pa", "combustion", False, True, "Pa", "mmWC", "mmwc_to_pa", None, "economizer differential pressure"),
    ("FD_command_pct", "fans/air", True, False, "%", None, "identity", None, "FD fan COMMAND, not airflow"),
    ("ID_command_pct", "fans/air", True, False, "%", None, "identity", None, "ID fan COMMAND, not airflow"),
    ("grate_command_pct", "grate", True, False, "%", None, "identity", None, "grate speed COMMAND"),
    ("fan_power_kW_FD", "fans/air", False, False, "kW", None, "identity", None, "FD motor power"),
    ("fan_power_kW_ID", "fans/air", False, False, "kW", None, "identity", None, "ID motor power"),
    ("feeder_speed_pct", "fuel rate", False, False, "%", None, "identity", None, "feeder speed"),
    ("draft_pa", "furnace/draft", True, False, "Pa", "mmWC", "mmwc_to_pa", None, "furnace draft; mmWC x 9.80665 = Pa; negative = normal"),
    ("draft_SP_pa", "furnace/draft", False, False, "Pa", "mmWC", "mmwc_to_pa", None, "draft set point"),
    ("interlock_active", "alarms/interlocks", True, False, "0/1", None, "identity", None, "any trip/interlock active (read-only status)"),
    ("alarm_code", "alarms/interlocks", False, False, "-", None, "identity", "", "active alarm code(s)"),
    ("fan_derated", "maintenance", False, False, "0/1", None, "identity", 0, "unknown derate is treated as 0; cmd-vs-power check still runs"),
    ("sootblow", "maintenance", False, False, "0/1", None, "identity", 0, "sootblowing active; unknown treated as 0"),
    ("fuel_mass_basis", "fuel rate", False, False, "-", None, "identity", "VOLUMETRIC", "WEIGH_BELT|VOLUMETRIC; unknown = VOLUMETRIC (conservative)"),
    ("fuel_ash_pct", "ash", False, False, "%", None, "identity", None, "lab ash"),
    ("unburnt_in_ash_pct", "ash", False, False, "%", None, "identity", None, "lab unburnt carbon"),
    ("ambient_temp_C", "ambient", False, False, "degC", None, "identity", None, "ambient temperature"),
    ("ambient_RH_pct", "ambient", False, False, "%", None, "identity", None, "ambient humidity"),
    ("fuel_price_index", "energy/cost", False, False, "index", None, "identity", None, "optional cost index"),
]
DERIVED = {"heater_id": "from the site config", "lhv_known": "1 where a lab LHV value exists", "co_available": "1 where CO is measured"}
CRITICAL_ANY_OF = [("fuel_rate_measured_kgh", "fuel_totalizer_kg")]      # at least one fuel signal must be mapped
META_BY = {m[0]: m for m in META}


def dictionary_columns():
    return pd.read_csv(DICTIONARY)["column"].astype(str).tolist() if DICTIONARY.exists() else []


def build_template():
    cols = {}
    for name in sorted(set(dictionary_columns()) | set(META_BY) | {"timestamp_local"} | set(DERIVED)):
        if name == "timestamp_local":
            continue
        if name in META_BY:
            _, grp, crit, comb, iu, su, conv, dflt, note = META_BY[name]
            e = {"source": "site", "site_tag": PLACEHOLDER, "available": None, "critical": crit, "combustion": comb, "group": grp,
                 "site_unit": su or iu, "internal_unit": iu, "conversion": conv, "note": note}
            if dflt is not None:
                e["default_if_unavailable"] = dflt
            if name == "operating_mode":
                e["value_map"] = {"<SITE_STATUS_TEXT>": "STEADY"}
        elif name in DERIVED:
            e = {"source": "computed", "note": f"derived by the adapter: {DERIVED[name]}"}
        else:
            e = {"source": "generator_only", "available": False, "note": "synthetic truth/label/log column or tool-derived value; never read from a site"}
        cols[name] = e
    return {"version": 1, "provenance": "TEMPLATE; no real tag names. The site fills site_tag/available/units; never taken from this repository",
            "time": {"site_tag": PLACEHOLDER, "format": None, "timezone": "Asia/Bangkok", "critical": True},
            "any_of_critical": [list(x) for x in CRITICAL_ANY_OF], "columns": cols}


def load(path=None):
    return yaml.safe_load(Path(path or TEMPLATE).read_text(encoding="utf-8"))


def is_placeholder(tag):
    return tag is None or str(tag).strip() == "" or "<" in str(tag)


def synthetic_site_map(prefix="SITE_"):
    """A fully filled map for tests/dry runs: invented site tags, mmWC / kg/s / Mkcal/h example units, every site column available."""
    m = build_template()
    m["time"]["site_tag"] = prefix + "TIME"
    for name, e in m["columns"].items():
        if e["source"] == "site":
            e["site_tag"] = prefix + name.upper()
            e["available"] = True
            if name == "operating_mode":
                e["value_map"] = {k: k for k in ("STARTUP", "STEADY", "RAMP", "STANDBY", "TRIP", "FEEDER_STOP")}
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-template", action="store_true")
    a = ap.parse_args()
    t = build_template()
    n_site = sum(1 for e in t["columns"].values() if e["source"] == "site")
    if a.write_template:
        header = "# Tag map template (SYNTHETIC placeholders). Generated by: python -m src.adapters.tagmap --write-template\n" \
                 "# Fill site_tag, available (true|false), and units per column. check_mapping refuses unmapped critical tags and undecided columns.\n"
        TEMPLATE.write_text(header + yaml.safe_dump(t, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"wrote {TEMPLATE} ({len(t['columns'])} columns, {n_site} site columns)")
    else:
        print(f"{len(t['columns'])} columns, {n_site} site columns")


if __name__ == "__main__":
    main()
