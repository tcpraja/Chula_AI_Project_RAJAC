"""Data dictionary for every generated column (provenance=SYNTHETIC).
Run: python -m src.data_dictionary [--out reports/03_data_dictionary.csv]
"""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
H = ["column", "group", "description", "unit", "type", "role", "how_generated", "use_in_model", "provenance", "dataset"]

# (column, group, description, unit, type, role, how_generated, use_in_model, dataset)
M = "main"
ROWS = [
    ("timestamp_local", "meta", "Local time (Asia/Bangkok, tz-naive), 5-min grid", "datetime", "datetime", "IDENTIFIER", "start + k x 5 min; rows removed only in DATA_GAP fault", "index only", "main|truth"),
    ("heater_id", "meta", "Anonymized heater id", "-", "str", "IDENTIFIER", "constant HEATER_C_SYNTHETIC", "no", M),
    ("operating_mode", "load", "STARTUP|STEADY|RAMP|STANDBY|TRIP|FEEDER_STOP", "-", "str", "FLAG", "state machine; RAMP if demand range over 30 min > 0.8 MW", "eligibility", M),
    ("fuel_lot", "fuel lot", "Lot id (6-18 h per lot)", "-", "str", "IDENTIFIER", "random lot durations", "split key only", M),
    ("fuel_moisture_wb_pct", "fuel lot", "Lab moisture, only when lhv_known=1", "%wb", "float", "FEATURE_CANDIDATE", "lot truth + lab noise; NaN if not assayed", "yes when lhv_known", M),
    ("fuel_LHV_asfired_MJkg", "fuel lot", "Lab as-fired LHV, only when lhv_known=1", "MJ/kg", "float", "FEATURE_CANDIDATE", "lot truth (falls with moisture) + lab noise", "yes when lhv_known", M),
    ("lhv_known", "fuel lot", "1 if lot has a lab assay", "bool", "int", "FLAG", "Bernoulli per lot (config)", "eligibility", M),
    ("fuel_rate_true_kgh", "fuel rate", "True feeder delivery rate", "kg/h", "float", "TRUTH_ONLY", "controller feed-forward x noise", "NO (truth leak)", M),
    ("fuel_rate_measured_kgh", "fuel rate", "Measured fuel rate (weigh belt or volumetric)", "kg/h", "float", "FEATURE_CANDIDATE", "truth x noise; volumetric adds lot density bias", "yes (lag>=1)", M),
    ("fuel_totalizer_kg", "fuel rate", "Cumulative measured fuel", "kg", "float", "FEATURE_CANDIDATE", "cumsum of measured rate; reset in fault F08", "reconciliation", M),
    ("HTF_flow_m3h", "HTF", "Measured HTF flow through heater branch", "m3/h", "float", "FEATURE_CANDIDATE", "truth x noise; frozen/high/low faults", "yes", M),
    ("HTF_Tin_C", "HTF", "Measured HTF return temperature", "degC", "float", "FEATURE_CANDIDATE", "truth + bias + noise", "yes", M),
    ("HTF_Tout_C", "HTF", "Measured HTF supply (header, after bypass mix) temperature", "degC", "float", "FEATURE_CANDIDATE", "truth mix + bias + noise; spike faults", "yes", M),
    ("HTF_rho_kgm3", "HTF", "Density at mean temperature from property table", "kg/m3", "float", "DERIVED", "table interpolation; NaN outside table", "yes", M),
    ("HTF_cp_kJkgK", "HTF", "Specific heat at mean temperature from property table", "kJ/kgK", "float", "DERIVED", "table interpolation; NaN outside table (never water cp)", "yes", M),
    ("Q_out_MW", "energy/cost", "Measured heat to HTF", "MW", "float", "DERIVED", "V/3600 x rho x integral cp dT / 1000", "yes", M),
    ("Q_in_MW", "energy/cost", "Fuel heat input from measured fuel and lab LHV", "MW", "float", "DERIVED", "rate/3600 x LHV; NaN when LHV unknown", "yes", M),
    ("eta_direct_pct", "energy/cost", "Direct efficiency", "%", "float", "DERIVED", "100 x Q_out / Q_in; NaN if LHV unknown", "target candidate (valid rows)", M),
    ("SFC_kg_GJ", "energy/cost", "Specific fuel consumption", "kg/GJ", "float", "TARGET_CANDIDATE", "rate/(3.6 x Q_out) = 1/(eta x LHV[GJ/kg])", "target", M),
    ("O2_pct_dry", "O2/CO", "Measured flue O2", "% dry", "float", "FEATURE_CANDIDATE", "truth filtered (lag) + noise", "yes", M),
    ("CO_ppm", "O2/CO", "Measured CO; NaN on days without analyser", "ppm", "float", "FEATURE_CANDIDATE", "truth x lognormal noise", "yes when co_available", M),
    ("co_available", "O2/CO", "CO analyser available (60 % of days)", "bool", "int", "FLAG", "Bernoulli per day; fault CO_MISSING", "eligibility", M),
    ("FD_command_pct", "fans/air", "Forced-draft fan command (operator setting)", "%", "float", "SETTING", "piecewise constant; changes logged", "action variable", M),
    ("ID_command_pct", "fans/air", "Induced-draft fan command (operator setting)", "%", "float", "SETTING", "piecewise constant; changes logged", "action variable", M),
    ("grate_command_pct", "grate", "Grate command (operator setting)", "%", "float", "SETTING", "piecewise constant; changes logged", "action variable", M),
    ("furnace_temp_C", "furnace/draft", "Furnace temperature", "degC", "float", "FEATURE_CANDIDATE", "load, O2, moisture function + noise", "yes", M),
    ("flue_temp_C", "furnace/draft", "Flue gas temperature before economizer", "degC", "float", "FEATURE_CANDIDATE", "load, O2, fouling function + noise", "yes", M),
    ("draft_pa", "furnace/draft", "Furnace draft (negative = safe)", "Pa", "float", "FEATURE_CANDIDATE", "fan-command balance + load term + noise", "yes", M),
    ("fan_derated", "fans/air", "Fans deliver 85 % of command (aging)", "bool", "int", "FLAG", "fault FAN_DERATE", "eligibility", M),
    ("sootblow", "maintenance", "Soot blowing active", "bool", "int", "FLAG", "triggered when fouling high; resets fouling", "eligibility", M),
    ("interlock_active", "alarms/interlocks", "Trip/interlock active", "bool", "int", "FLAG", "draft >= 0 trips fuel for 10 steps", "eligibility", M),
    ("quality_flag", "meta", "Data quality flags (OK or ;-joined)", "-", "str", "FLAG", "detectors on measured data", "filter", M),
    ("advice_eligibility", "meta", "ELIGIBLE | DIAGNOSTIC_ONLY:NO_CO | NO_ADVICE:<codes>", "-", "str", "LABEL", "SPEC C7 layers 1-2 on measured data, 12-step stable window", "gate", M),
    ("true_synthetic_best_action", "meta", "Generator-best feasible action (HOLD, FD+-2/4, GRATE+-2/4, combos)", "-", "str", "LABEL", "argmax eta gain over feasible set using hidden model", "evaluation only (NEVER input)", M),
    ("scenario_id", "meta", "Event label; FAULT_<type> for the 8 h fault-case blocks", "-", "str", "LABEL", "priority rules", "evaluation", M),
    ("is_fault_injected", "meta", "1 inside injected fault window", "bool", "int", "LABEL", "fault plan", "evaluation", M),
    ("HTF_Tout_SP_C", "HTF", "Supply temperature setpoint (constant)", "degC", "float", "FEATURE_CANDIDATE", "config", "yes", M),
    ("HTF_bypass_pct", "HTF", "Reported bypass valve opening; >0 means heat-balance check", "%", "float", "FLAG", "random 12-36 step episodes", "eligibility", M),
    ("HTF_pump_status", "HTF", "HTF pump running", "bool", "int", "FLAG", "constant 1 in this build", "no", M),
    ("ambient_temp_C", "ambient", "Ambient temperature", "degC", "float", "FEATURE_CANDIDATE", "daily sine + AR(1)", "yes", M),
    ("ambient_RH_pct", "ambient", "Ambient relative humidity", "%", "float", "FEATURE_CANDIDATE", "anti-correlated with temperature + noise", "yes", M),
    ("fan_power_kW_FD", "fans/air", "FD fan power (fan-law proxy)", "kW", "float", "DERIVED", "rated x (cmd/100)^3, OWN-ESTIMATE", "AI energy/cost only", M),
    ("fan_power_kW_ID", "fans/air", "ID fan power (fan-law proxy)", "kW", "float", "DERIVED", "rated x (cmd/100)^3, OWN-ESTIMATE", "AI energy/cost only", M),
    ("feeder_speed_pct", "fuel rate", "Feeder speed", "%", "float", "FEATURE_CANDIDATE", "true feed / capacity x 100 + noise", "yes", M),
    ("fuel_mass_basis", "fuel rate", "WEIGH_BELT or VOLUMETRIC fuel measurement", "-", "str", "FLAG", "belt except service episodes (all volumetric in stress)", "eligibility", M),
    ("fuel_ash_pct", "ash", "Lab ash content, sparse (one row per lot)", "%", "float", "FEATURE_CANDIDATE", "lot truth + lab noise at lot start + 3 h", "lot-level only", M),
    ("unburnt_in_ash_pct", "ash", "Lab unburnt in ash, sparse; rises at low O2 or high grate", "%", "float", "FEATURE_CANDIDATE", "mean of true unburnt over first 3 h + lab noise", "lot-level only", M),
    ("stack_temp_C", "furnace/draft", "Stack temperature after economizer", "degC", "float", "FEATURE_CANDIDATE", "flue minus recovery, shrinks with fouling", "yes", M),
    ("economizer_dP_pa", "maintenance", "Economizer differential pressure (fouling proxy)", "Pa", "float", "FEATURE_CANDIDATE", "rises with fouling, resets on sootblow", "yes", M),
    ("draft_SP_pa", "furnace/draft", "Draft setpoint (constant)", "Pa", "float", "FEATURE_CANDIDATE", "config", "yes", M),
    ("alarm_code", "alarms/interlocks", "Active alarm code or empty", "-", "str", "FLAG", "draft, O2, feeder, trip, temperature rules", "eligibility", M),
    ("fuel_price_index", "energy/cost", "Fuel price index (base 100)", "index", "float", "FEATURE_CANDIDATE", "daily random walk; no money claimed", "cost scenarios only", M),
    # truth file
    ("fuel_lot_idx", "truth", "Lot number", "-", "int", "TRUTH_ONLY", "lot generator", "NO", "truth"),
    ("moisture_true_wb_pct", "truth", "True lot moisture", "%wb", "float", "TRUTH_ONLY", "beta draw", "NO", "truth"),
    ("LHV_true_MJkg", "truth", "True lot as-fired LHV", "MJ/kg", "float", "TRUTH_ONLY", "falls with moisture", "NO", "truth"),
    ("bed_tau_min", "truth", "Bed lag time constant", "min", "float", "TRUTH_ONLY", "uniform 10-20", "NO", "truth"),
    ("Q_demand_MW", "truth", "Process heat demand", "MW", "float", "TRUTH_ONLY", "demand generator", "NO", "truth"),
    ("fuel_feed_true_kgh", "truth", "Feeder delivery", "kg/h", "float", "TRUTH_ONLY", "controller", "NO", "truth"),
    ("fuel_burn_true_kgh", "truth", "Bed burn rate (lagged feed)", "kg/h", "float", "TRUTH_ONLY", "first-order lag", "NO", "truth"),
    ("Q_in_true_MW", "truth", "True fuel heat released", "MW", "float", "TRUTH_ONLY", "burn x LHV", "NO", "truth"),
    ("eta_true", "truth", "Latent efficiency", "-", "float", "TRUTH_ONLY", "SPEC C6 function", "NO", "truth"),
    ("Q_out_true_MW", "truth", "True heat to HTF", "MW", "float", "TRUTH_ONLY", "eta x Q_in", "NO", "truth"),
    ("HTF_flow_true_m3h", "truth", "True heater-branch flow", "m3/h", "float", "TRUTH_ONLY", "flow generator", "NO", "truth"),
    ("HTF_Tin_true_C", "truth", "True return temperature", "degC", "float", "TRUTH_ONLY", "from setpoint and demand", "NO", "truth"),
    ("HTF_Tout_heater_true_C", "truth", "True heater outlet temperature", "degC", "float", "TRUTH_ONLY", "solves heat balance", "NO", "truth"),
    ("bypass_frac_true", "truth", "True bypass fraction", "-", "float", "TRUTH_ONLY", "episodes", "NO", "truth"),
    ("O2_true_pct_dry", "truth", "True flue O2", "% dry", "float", "TRUTH_ONLY", "21(1-1/lambda)", "NO", "truth"),
    ("lambda_true", "truth", "Air ratio", "-", "float", "TRUTH_ONLY", "FD effective / stoichiometric", "NO", "truth"),
    ("O2_opt_true_pct", "truth", "Hidden optimum O2", "% dry", "float", "TRUTH_ONLY", "function of load and moisture", "NO", "truth"),
    ("grate_opt_true_pct", "truth", "Hidden optimum grate command", "%", "float", "TRUTH_ONLY", "function of fuel heat and moisture", "NO", "truth"),
    ("fouling_index", "truth", "Fouling 0-1", "-", "float", "TRUTH_ONLY", "linear rise, reset by sootblow", "NO", "truth"),
    ("unburnt_true_pct", "truth", "True unburnt in ash", "%", "float", "TRUTH_ONLY", "rises at low O2 or high grate", "NO", "truth"),
    ("CO_true_ppm", "truth", "True CO", "ppm", "float", "TRUTH_ONLY", "exponential in low O2 + grate mismatch", "NO", "truth"),
    ("draft_true_pa", "truth", "True draft", "Pa", "float", "TRUTH_ONLY", "fan balance", "NO", "truth"),
    ("best_action_eta_gain_pp", "truth", "Efficiency gain of best feasible action", "% points", "float", "TRUTH_ONLY", "argmax over action set", "evaluation only", "truth"),
    ("ash_true_pct", "truth", "True lot ash", "%", "float", "TRUTH_ONLY", "uniform per lot", "NO", "truth"),
    # operator action log
    ("timestamp", "action log", "Time the setting changed (matches 5-min row)", "datetime", "datetime", "IDENTIFIER", "decision step", "join key", "action_log"),
    ("variable", "action log", "Setting changed", "-", "str", "IDENTIFIER", "FD/ID/grate command", "join key", "action_log"),
    ("old", "action log", "Setting before change", "%", "float", "SETTING", "state", "yes", "action_log"),
    ("new", "action log", "Setting after change", "%", "float", "SETTING", "state", "yes", "action_log"),
    ("shift_id", "action log", "OP-A 06-14, OP-B 14-22, OP-C 22-06", "-", "str", "IDENTIFIER", "clock", "behaviour grouping", "action_log"),
    ("reason_code", "action log", "O2_TRIM_*, DRAFT_TRIM, GRATE_MATCH, EXPLORATION_STEP, AIR_REDUCTION, TRIM_ERROR, FAULT_RESPONSE", "-", "str", "LABEL", "decision rule", "analysis", "action_log"),
    ("source", "action log", "OPERATOR or EXPLORATION (randomized, identifiability)", "-", "str", "LABEL", "exploration probability in config", "analysis", "action_log"),
    # fault cases
    ("case_id", "fault cases", "Fault case id", "-", "str", "IDENTIFIER", "plan", "evaluation", "fault_cases"),
    ("fault_type", "fault cases", "Fault type", "-", "str", "LABEL", "plan", "evaluation", "fault_cases"),
    ("case_start", "fault cases", "Case block start", "datetime", "str", "IDENTIFIER", "plan", "evaluation", "fault_cases"),
    ("case_end", "fault cases", "Case block end", "datetime", "str", "IDENTIFIER", "plan", "evaluation", "fault_cases"),
    ("injected_start", "fault cases", "Injection start", "datetime", "str", "IDENTIFIER", "plan", "evaluation", "fault_cases"),
    ("injected_end", "fault cases", "Injection end", "datetime", "str", "IDENTIFIER", "plan", "evaluation", "fault_cases"),
    ("injected_rows", "fault cases", "Rows present inside injection window", "count", "int", "LABEL", "plan", "evaluation", "fault_cases"),
    ("description", "fault cases", "What is injected", "-", "str", "LABEL", "plan", "evaluation", "fault_cases"),
    ("expected_detection", "fault cases", "Expected flag or reason code", "-", "str", "LABEL", "plan", "evaluation", "fault_cases"),
    # display reconciliation
    ("record_id", "display", "Display record id", "-", "str", "IDENTIFIER", "daily sample", "evaluation", "display_reconciliation"),
    ("date", "display", "Record date", "date", "str", "IDENTIFIER", "day", "evaluation", "display_reconciliation"),
    ("time", "display", "Record time", "time", "str", "IDENTIFIER", "random daytime step", "evaluation", "display_reconciliation"),
    ("kgs_disp", "display", "Displayed biomass rate", "kg/s", "float", "FEATURE_CANDIDATE", "measured rate/3600", "proxy only", "display_reconciliation"),
    ("kgday_disp", "display", "Displayed biomass daily total", "kg/day", "float", "FEATURE_CANDIDATE", "sum of measured rate over day", "proxy only", "display_reconciliation"),
    ("mkcal_h_disp", "display", "Displayed heat rate", "Mkcal/h", "float", "FEATURE_CANDIDATE", "Q_out/1.16222", "proxy only", "display_reconciliation"),
    ("mw_disp", "display", "Displayed heat rate in MW", "MW", "float", "FEATURE_CANDIDATE", "Q_out", "proxy only", "display_reconciliation"),
    ("mkcal_day_disp", "display", "Displayed daily heat", "Mkcal/day", "float", "FEATURE_CANDIDATE", "sum Q_out over day", "proxy only", "display_reconciliation"),
    ("injected_case", "display", "Injected display fault, if any", "-", "str", "LABEL", "fixed records R005 R011 R017", "evaluation", "display_reconciliation"),
    ("implied_kgday", "display", "kg/s x 86400", "kg/day", "float", "DERIVED", "identity valid only if sustained", "evaluation", "display_reconciliation"),
    ("rel_diff_fuel_pct", "display", "Gap between displayed and implied daily fuel", "%", "float", "DERIVED", "abs diff / implied", "evaluation", "display_reconciliation"),
    ("mw_from_mkcal_h", "display", "Mkcal/h x 1.16222", "MW", "float", "DERIVED", "unit conversion", "evaluation", "display_reconciliation"),
    ("verdict", "display", "OK | WINDOW_MISMATCH | REJECT", "-", "str", "LABEL", "units.reconcile_display", "evaluation", "display_reconciliation"),
    ("reasons", "display", "Reconciliation reason codes", "-", "str", "LABEL", "units.reconcile_display", "evaluation", "display_reconciliation"),
]


def build():
    df = pd.DataFrame([r[:8] + ("SYNTHETIC", r[8]) for r in ROWS], columns=H)
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports/03_data_dictionary.csv")
    a = ap.parse_args()
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    df = build()
    df.to_csv(out, index=False)
    print(f"wrote {out.name}: {len(df)} columns")


if __name__ == "__main__":
    main()
