"""Synthetic Heater C generator (SYNTHETIC; no plant data). Pipeline per SPEC C6:
demand -> lot moisture/LHV -> latent eta -> fuel -> HTF temps -> measured = truth + noise/bias/lag.

Run: python -m src.generate_synthetic --seed 42 --days 60 --out data/raw_synthetic/synthetic_heater_c_5min.csv
"""
import argparse
import copy
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.signal import lfilter, lfilter_zi

from src.units import HTFTable, MKCAL_H_TO_MW, reconcile_display

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config" / "synthetic_parameters.yaml"
PROFILE_BY_SEED = {42: "main", 77: "stress", 101: "site_style"}
OPERATING = ("STEADY", "RAMP")

COLUMNS = [
    "timestamp_local", "heater_id", "operating_mode", "fuel_lot", "fuel_moisture_wb_pct", "fuel_LHV_asfired_MJkg",
    "lhv_known", "fuel_rate_true_kgh", "fuel_rate_measured_kgh", "fuel_totalizer_kg", "HTF_flow_m3h", "HTF_Tin_C",
    "HTF_Tout_C", "HTF_rho_kgm3", "HTF_cp_kJkgK", "Q_out_MW", "Q_in_MW", "eta_direct_pct", "SFC_kg_GJ", "O2_pct_dry",
    "CO_ppm", "co_available", "FD_command_pct", "ID_command_pct", "grate_command_pct", "furnace_temp_C", "flue_temp_C",
    "draft_pa", "fan_derated", "sootblow", "interlock_active", "quality_flag", "advice_eligibility",
    "true_synthetic_best_action", "scenario_id", "is_fault_injected", "HTF_Tout_SP_C", "HTF_bypass_pct",
    "HTF_pump_status", "ambient_temp_C", "ambient_RH_pct", "fan_power_kW_FD", "fan_power_kW_ID", "feeder_speed_pct",
    "fuel_mass_basis", "fuel_ash_pct", "unburnt_in_ash_pct", "stack_temp_C", "economizer_dP_pa", "draft_SP_pa",
    "alarm_code", "fuel_price_index",
]
TRUTH_COLUMNS = [
    "timestamp_local", "fuel_lot_idx", "moisture_true_wb_pct", "LHV_true_MJkg", "bed_tau_min", "Q_demand_MW",
    "fuel_feed_true_kgh", "fuel_burn_true_kgh", "Q_in_true_MW", "eta_true", "Q_out_true_MW", "HTF_flow_true_m3h",
    "HTF_Tin_true_C", "HTF_Tout_heater_true_C", "bypass_frac_true", "O2_true_pct_dry", "lambda_true",
    "O2_opt_true_pct", "grate_opt_true_pct", "fouling_index", "unburnt_true_pct", "CO_true_ppm", "draft_true_pa",
    "best_action_eta_gain_pp", "ash_true_pct",
]
LOG_COLUMNS = ["timestamp", "variable", "old", "new", "shift_id", "reason_code", "source"]
FAULT_COLUMNS = ["case_id", "fault_type", "case_start", "case_end", "injected_start", "injected_end", "injected_rows",
                 "description", "expected_detection"]

# fault type -> (offset_start, offset_end, description, expected_detection)
FAULT_SPEC = {
    "FEEDER_STOP": (40, 52, "Feeders stop for 1 h; bed burns down", "mode FEEDER_STOP; NO_ADVICE LOW_FUEL_CONF"),
    "FAN_DERATE": (20, 96, "Fans deliver 85 % of commanded air", "fan_derated=1; NO_ADVICE FAN_DERATE"),
    "POOR_AIR": (24, 72, "Operator trims air to a low O2 target and holds it", "low O2, high CO; NO_ADVICE LOW_O2/HIGH_CO"),
    "FROZEN_O2": (30, 42, "O2 analyser output frozen", "quality FROZEN_SENSOR; NO_ADVICE STALE_DATA"),
    "FROZEN_FLOW": (30, 40, "HTF flow transmitter frozen", "quality FROZEN_SENSOR; NO_ADVICE STALE_DATA"),
    "CO_MISSING": (16, 80, "CO analyser unavailable", "co_available=0; DIAGNOSTIC_ONLY NO_CO"),
    "DATA_GAP": (40, 52, "12 rows missing, then 2 rows missing", "quality GAP_AFTER; TRANSIENT after gap"),
    "TOTALIZER_RESET": (48, 49, "Fuel totalizer resets to zero", "quality TOTALIZER_RESET"),
    "HIGH_HTF_FLOW": (30, 66, "HTF flow 130 % of normal (above envelope)", "BAD_FLOW; NO_ADVICE"),
    "LOW_HTF_FLOW": (30, 66, "HTF flow 65 % of normal (below envelope)", "BAD_FLOW; NO_ADVICE"),
    "ADVERSE_DRAFT": (30, 60, "Operator error raises draft toward zero (alarm, no trip)", "UNSAFE_DRAFT; NO_ADVICE"),
    "TRIP": (30, 50, "Draft goes positive; interlock trips fuel for 10 steps", "TRIP_ACTIVE; mode TRIP"),
    "FUEL_SPIKE": (36, 39, "Measured fuel rate x4 for 3 steps", "quality FUEL_IMPLAUSIBLE"),
    "HEAT_IMPLAUSIBLE": (36, 70, "Tout spike +40 K (4 steps), then Tin bias -20 K (10 steps)", "quality HEAT_IMPLAUSIBLE"),
    "PROPERTY_OOR": (36, 39, "Tout reading 335 C, outside property table", "quality PROPERTY_OOR; cp/rho NaN"),
}


def _deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_cfg(profile="main", path=None):
    with open(path or CFG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    base = {k: v for k, v in cfg.items() if k != "profiles"}
    return _deep_merge(base, cfg["profiles"].get(profile, {}))


def frame_hash(df):
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()


def eta_fn(P, m, f, o2, o2opt, g, gopt, derate, soot, tamb):
    """Latent efficiency (before AR noise and startup factor). Generator-defined effects (A12)."""
    c = P["combustion"]
    e = c["eta_base"] + c["eta_moist_per_pct"] * (c["moist_ref"] - m) - c["foul_pen"] * f
    dev = np.clip(o2 - o2opt, -3.5, 6.0)
    e = e - np.where(dev > 0, c["over_air_k"], c["under_air_k"]) * dev ** 2
    e = e - c["grate_k"] * (g - gopt) ** 2 - c["derate_pen"] * derate - c["sootblow_pen"] * soot
    return e - c["amb_k"] * (tamb - 28.0)


def o2_opt_fn(P, m, qd):
    c = P["combustion"]
    return np.clip(c["o2_opt_base"] + c["o2_opt_moist"] * (m - 15.0) + c["o2_opt_load"] * (qd - 8.5),
                   c["o2_opt_min"], c["o2_opt_max"])


def g_opt_fn(P, qf, m):
    c = P["combustion"]
    return np.clip(c["g_opt_base"] + c["g_opt_per_mw"] * (qf - 12.0) + c["g_opt_moist"] * (m - 15.0), 5.0, 95.0)


def co_fn(P, o2, g, gopt, m):
    c = P["combustion"]
    co = (c["co_base_ppm"] + c["co_amp_ppm"] * np.exp(-c["co_decay"] * (np.minimum(o2, 14.0) - c["co_o2_ref"]))
          + 8.0 * np.maximum(0.0, np.abs(g - gopt) - 6.0) + 2.5 * np.maximum(0.0, m - 15.0))
    return np.clip(co, 5.0, 5000.0)


def draft_fn(P, id_e, fd_e, qf):
    g = P["gas"]
    return -g["draft_gain"] * (id_e - g["draft_fd_coupling"] * fd_e - g["draft_offset"]) + g["draft_load_gain"] * (qf - 12.0)


def fault_plan(P, n_norm):
    L = P["fault_case_steps"]
    out = []
    for k, t in enumerate(FAULT_SPEC):
        a, b, desc, exp = FAULT_SPEC[t]
        s = n_norm + k * L
        out.append(dict(case_id=f"F{k + 1:02d}", type=t, start=s, end=s + L, a=s + a, b=s + b, desc=desc, exp=exp))
    return out


def _episodes(rng, n_norm, per10d, days, length=(12, 36)):
    k = int(round(per10d * days / 10.0))
    eps = []
    for _ in range(k):
        ln = int(rng.integers(*length, endpoint=True))
        s = int(rng.integers(100, max(101, n_norm - ln - 100)))
        eps.append((s, s + ln))
    return eps


def generate(seed=42, days=60, profile=None, cfg_path=None):
    profile = profile or PROFILE_BY_SEED.get(seed, "main")
    P = load_cfg(profile, cfg_path)
    tab = HTFTable()
    r_dem, r_lot, r_op, r_sen, r_evt, r_misc = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(6)]
    step = P["step_min"]
    spd = 24 * 60 // step
    n_norm = days * spd
    cases = fault_plan(P, n_norm)
    n = n_norm + len(cases) * P["fault_case_steps"]
    ts = pd.date_range(P["start"], periods=n, freq=f"{step}min")
    hour = (ts.hour.values + ts.minute.values / 60.0)
    day = np.arange(n) // spd
    n_days = int(day.max()) + 1
    shift = np.where((hour >= 6) & (hour < 14), "OP-A", np.where((hour >= 14) & (hour < 22), "OP-B", "OP-C"))
    dm, fu, cb, fo, hf, gs, op, se, gr = (P[k] for k in
                                          ("demand", "fuel", "combustion", "fouling", "htf", "gas", "operators", "sensors", "guardrails"))
    sp_c = hf["sp_c"]

    # ---- demand (A01) and mode windows
    Qd = np.empty(n)
    i, level = 0, dm["base_mw"]
    while i < n:
        base = dm["base_mw"] + dm["daily_amp_mw"] * np.sin(2 * np.pi * (hour[i] - 10) / 24)
        tgt = float(np.clip(base + r_dem.normal(0, dm["level_sd_mw"]), dm["min_mw"] + 0.3, dm["max_mw"] - 0.3))
        ramp = int(r_dem.integers(*dm["ramp_steps"]))
        seg = int(r_dem.integers(*dm["seg_steps"]))
        m_ = min(ramp, n - i)
        Qd[i:i + m_] = np.linspace(level, tgt, ramp + 1)[1:m_ + 1]
        i += m_
        m_ = min(seg, n - i)
        Qd[i:i + m_] = tgt
        i += m_
        level = tgt
    phi = dm["ar_phi"]
    Qd = np.clip(Qd + lfilter([1.0], [1, -phi], r_dem.normal(0, dm["ar_sd_mw"] * np.sqrt(1 - phi ** 2), n)),
                 dm["min_mw"], dm["max_mw"])
    startup_frac = np.zeros(n)
    standby = np.zeros(n, bool)
    s0 = P["startup_steps"]
    startup_frac[:s0] = (np.arange(s0) + 1) / s0
    sb0 = int(0.55 * n_norm)
    standby[sb0:sb0 + P["standby_steps"]] = True
    r0 = sb0 + P["standby_steps"]
    startup_frac[r0:r0 + P["restart_steps"]] = (np.arange(P["restart_steps"]) + 1) / P["restart_steps"]
    Qd = np.where(standby, 0.0, np.where(startup_frac > 0, Qd * (0.25 + 0.75 * startup_frac), Qd))

    # ---- HTF flow, flow episodes, bypass episodes
    Vb = hf["flow_min"] + (np.clip(Qd, dm["min_mw"], dm["max_mw"]) - dm["min_mw"]) / (dm["max_mw"] - dm["min_mw"]) * (hf["flow_max"] - hf["flow_min"])
    V = np.clip(Vb * (1 + lfilter([1.0], [1, -0.8], r_evt.normal(0, hf["flow_noise_sd"] * 0.6, n))), hf["flow_min"], hf["flow_max"])
    flow_ep = np.full(n, "", dtype=object)
    for (a, b) in _episodes(r_evt, n_norm, hf["flow_episodes_per_10d"], days):
        V[a:b] = r_evt.uniform(860, 900, b - a)
        flow_ep[a:b] = "HIGH_FLOW"
    for (a, b) in _episodes(r_evt, n_norm, hf["flow_episodes_per_10d"], days):
        V[a:b] = r_evt.uniform(500, 540, b - a)
        flow_ep[a:b] = "LOW_FLOW"
    byp = np.zeros(n)
    for (a, b) in _episodes(r_evt, n_norm, hf["bypass_episodes_per_10d"], days):
        byp[a:b] = r_evt.uniform(*hf["bypass_range"])

    # ---- lots (A02, A03, A19)
    durs = []
    while sum(durs) < n:
        durs.append(int(r_lot.integers(*fu["lot_steps"], endpoint=True)))
    n_lot = len(durs)
    lot_idx = np.repeat(np.arange(n_lot), durs)[:n]
    lot_start = np.concatenate([[0], np.cumsum(durs)[:-1]])
    lot_m = fu["moisture_min"] + (fu["moisture_max"] - fu["moisture_min"]) * r_lot.beta(*fu["moisture_beta"], n_lot)
    lot_lhv = np.clip(fu["lhv_at_min_moisture"] - fu["lhv_slope_per_pct"] * (lot_m - fu["moisture_min"])
                      + r_lot.normal(0, fu["lhv_lot_sd"], n_lot), fu["lhv_min"], fu["lhv_max"])
    lot_tau = r_lot.uniform(*fu["bed_tau_min"], n_lot)
    lot_ash = r_lot.uniform(*fu["ash_range"], n_lot)
    lot_known = r_lot.random(n_lot) < fu["lhv_known_prob"]
    lot_vbias = np.clip(r_lot.normal(0, fu["volumetric_bias_sd"], n_lot), -0.2, 0.2)
    lab_lhv = lot_lhv + r_lot.normal(0, fu["lab_lhv_sd"], n_lot)
    lab_m = lot_m + r_lot.normal(0, fu["lab_moist_sd"], n_lot)
    price = np.clip(fu["price_index_base"] + np.cumsum(r_misc.normal(0, fu["price_step_sd"], n_days)), 85, 120)

    # ---- ambient and CO availability (A10)
    tamb = 28 + 4.5 * np.sin(2 * np.pi * (hour - 9) / 24) + np.repeat(r_misc.normal(0, 1.2, n_days), spd)[:n] \
        + lfilter([1.0], [1, -0.9], r_misc.normal(0, 0.3, n))
    rh = np.clip(80 - 2.4 * (tamb - 28) + r_misc.normal(0, 3, n), 35, 100)
    co_days = np.zeros(n_days, bool)
    co_days[r_misc.permutation(n_days)[:int(round(cb["co_avail_prob"] * n_days))]] = True
    co_avail = np.repeat(co_days, spd)[:n].copy()

    # ---- fuel mass basis
    vol = np.zeros(n, bool)
    if fu["volumetric_all"]:
        vol[:] = True
    else:
        for d0, d1 in fu["volumetric_episodes_days"]:
            if d0 < days:
                vol[d0 * spd:min(d1, days) * spd] = True

    # ---- fault arrays
    derate = np.zeros(n, bool); feeder_stop = np.zeros(n, bool); co_off = np.zeros(n, bool)
    frozen_o2, frozen_flow, drops, inj = [], [], np.zeros(n, bool), np.zeros(n, bool)
    suppress = np.zeros(n, bool)
    forced, tot_reset, fuel_spike, tout_spike, tin_bias, tout_oor = {}, [], [], [], [], []
    scen_fault = np.full(n, "", dtype=object)
    for c in cases:
        t, a, b = c["type"], c["a"], c["b"]
        scen_fault[c["start"]:c["end"]] = "FAULT_" + t
        inj[a:b] = True
        if t == "FEEDER_STOP": feeder_stop[a:b] = True
        elif t == "FAN_DERATE": derate[a:c["end"]] = True; inj[a:c["end"]] = True
        elif t == "POOR_AIR": forced.setdefault(a, []).append(("O2", 3.8, "AIR_REDUCTION")); suppress[a:b] = True
        elif t == "FROZEN_O2": frozen_o2.append((a, b))
        elif t == "FROZEN_FLOW": frozen_flow.append((a, b))
        elif t == "CO_MISSING": co_off[a:b] = True
        elif t == "DATA_GAP":
            drops[a:b] = True; drops[c["start"] + 70:c["start"] + 72] = True
            suppress[a - 2:b + 2] = True; suppress[c["start"] + 68:c["start"] + 74] = True
            inj[b] = True
        elif t == "TOTALIZER_RESET": tot_reset.append(a)
        elif t == "HIGH_HTF_FLOW": V[a:b] = V[a:b] * 1.3
        elif t == "LOW_HTF_FLOW": V[a:b] = V[a:b] * 0.65
        elif t == "ADVERSE_DRAFT": forced.setdefault(a, []).append(("ID_DELTA", 14.0, "TRIM_ERROR")); suppress[a:b] = True; forced.setdefault(b, []).append(("ID_RESTORE", 0.0, "FAULT_RESPONSE"))
        elif t == "TRIP": forced.setdefault(a, []).append(("ID_DELTA", 21.0, "TRIM_ERROR")); suppress[a:b] = True
        elif t == "FUEL_SPIKE": fuel_spike.append((a, b))
        elif t == "HEAT_IMPLAUSIBLE": tout_spike.append((a, a + 4)); tin_bias.append((a + 24, b))
        elif t == "PROPERTY_OOR": tout_oor.append((a, b))
    co_avail = co_avail & ~co_off
    Tin = sp_c - 20.0 * np.ones(n)
    for _ in range(3):
        Tin = sp_c - tab.solve_dT(V, Tin, Qd)

    # ---- sequential plant simulation
    ar = lfilter([1.0], [1, -cb["ar_phi"]], r_evt.normal(0, cb["ar_sd"] * np.sqrt(1 - cb["ar_phi"] ** 2), n))
    ctrl_noise = r_evt.normal(0, cb["controller_noise_sd"], n)
    draft_noise = r_evt.normal(0, gs["draft_noise_pa"], n)
    keys = ["F", "B", "Qf", "eta", "Qout", "O2", "lam", "o2opt", "gopt", "f", "draft", "FD", "ID", "GR", "soot", "su",
            "kd", "interlock"]
    S = {k: np.zeros(n) for k in keys}
    mode = np.empty(n, dtype=object)
    alarm = np.full(n, "", dtype=object)
    log = []
    FD, ID, GR = 55.0, 66.0, 40.0
    id_good = ID
    next_dec, q_last = 1, float(Qd[0])
    B_prev, eta_prev, lhv_ctrl, f, ar_i = 0.0, 0.55, 15.0, 0.1, 0
    trip_rem, soot_rem, restore = 0, 0, {}
    sb_bias = op["shift_bias"]
    for i in range(n):
        sh = shift[i]
        # --- mode
        if standby[i]:
            md = "STANDBY"
        elif trip_rem > 0:
            md = "TRIP"
        elif feeder_stop[i]:
            md = "FEEDER_STOP"
        elif startup_frac[i] > 0:
            md = "STARTUP"
        else:
            w = Qd[max(0, i - gr["ramp_window_steps"]):i + 1]
            md = "RAMP" if (w.max() - w.min()) > gr["ramp_mw"] else "STEADY"
        mode[i] = md
        # --- operator decisions (settings change only here)
        changes = {}
        if i in restore:
            changes["ID_command_pct"] = (restore.pop(i), "FAULT_RESPONSE", "OPERATOR")
        for kind, val, why in forced.get(i, []):
            qfx = max(Qd[i], 1.0) / 0.675
            if kind == "O2":
                lt = 21.0 / (21.0 - val)
                changes["FD_command_pct"] = (float(np.clip(cb["fd_stoich_per_mw"] * qfx * lt, 20, 100)), why, "OPERATOR")
            elif kind == "ID_DELTA":
                id_good = ID
                changes["ID_command_pct"] = (ID - val, why, "OPERATOR")
            elif kind == "ID_RESTORE":
                changes["ID_command_pct"] = (id_good, why, "OPERATOR")
        if (not changes and not suppress[i] and (i >= next_dec or abs(Qd[i] - q_last) > op["load_trigger_mw"]) and md not in ("STANDBY", "TRIP") and Qd[i] > 1.0):
            qfx = Qd[i] / 0.675
            expl = r_op.random() < op["explore_prob"]
            o2t = op["o2_target"] + sb_bias[sh]["o2"] + r_op.normal(0, op["o2_noise"])
            gt = cb["g_opt_base"] + cb["g_opt_per_mw"] * (qfx - 12) + sb_bias[sh]["grate"] + r_op.normal(0, op["grate_noise"])
            if expl:
                o2t += r_op.uniform(*op["explore_o2"])
                gt += r_op.uniform(*op["explore_grate"])
            lt = 21.0 / (21.0 - float(np.clip(o2t, 3.0, 12.0)))
            fd_new = float(np.clip(cb["fd_stoich_per_mw"] * qfx * lt, 20, 100))
            src = "EXPLORATION" if expl else "OPERATOR"
            if abs(fd_new - FD) >= op["deadband"]:
                changes["FD_command_pct"] = (fd_new, "EXPLORATION_STEP" if expl else ("O2_TRIM_HIGH" if fd_new > FD else "O2_TRIM_LOW"), src)
            fd_use = changes["FD_command_pct"][0] if "FD_command_pct" in changes else FD
            id_new = (gs["draft_fd_coupling"] * round(fd_use, 1) + gs["draft_offset"]
                      + (gs["draft_load_gain"] * (qfx - 12) - gr["draft_sp_pa"]) / gs["draft_gain"]
                      + r_op.normal(0, op["id_noise"]))
            if abs(id_new - ID) >= op["deadband"] or "FD_command_pct" in changes:
                changes["ID_command_pct"] = (float(np.clip(id_new, 20, 100)), "DRAFT_TRIM", "OPERATOR")
            if abs(gt - GR) >= op["deadband"]:
                changes["GR_command_pct"] = (float(np.clip(gt, 5, 95)), "EXPLORATION_STEP" if expl else "GRATE_MATCH", src)
            next_dec = i + int(r_op.integers(*op["decision_steps"], endpoint=True))
            q_last = Qd[i]
        for var, (new, why, src) in changes.items():
            new = round(float(np.clip(new, 0, 100)), 1)
            name = "grate_command_pct" if var == "GR_command_pct" else var
            old = {"FD_command_pct": FD, "ID_command_pct": ID, "grate_command_pct": GR}[name]
            if new != old:
                log.append((i, name, old, new, sh, why, src))
                if name == "FD_command_pct": FD = new
                elif name == "ID_command_pct": ID = new
                else: GR = new
        # --- fuel, bed lag
        lot = lot_idx[i]
        m, lhv = lot_m[lot], lot_lhv[lot]
        if md in ("STANDBY", "TRIP", "FEEDER_STOP"):
            F = 0.0
        else:
            F = float(np.clip(Qd[i] * 3600.0 / (max(eta_prev, 0.45) * lhv_ctrl) * (1 + ctrl_noise[i]), 0, fu["feeder_cap_kgh"]))
        lhv_ctrl += cb["lhv_ctrl_gain"] * (lhv - lhv_ctrl)
        B = B_prev + (1 - np.exp(-step / lot_tau[lot])) * (F - B_prev)
        Qf = B * lhv / 3600.0
        # --- air, O2
        kd = cb["derate_factor"] if derate[i] else 1.0
        FDe, IDe = FD * kd, ID * kd
        lam = max(FDe / (cb["fd_stoich_per_mw"] * Qf + 1e-9), 1.0005)
        O2 = min(21.0 * (1 - 1 / lam), 20.9)
        # --- fouling, sootblow
        if soot_rem == 0 and md in OPERATING and ((f >= fo["soot_trigger"] and r_evt.random() < fo["soot_prob"]) or f >= fo["forced_at"]):
            soot_rem = fo["soot_steps"]
            f = fo["reset_to"]
        soot = 1.0 if soot_rem > 0 else 0.0
        soot_rem = max(0, soot_rem - 1)
        f = min(1.0, f + fo["rate_per_step"] * (Qf / 12.0))
        # --- efficiency
        o2o = float(o2_opt_fn(P, m, Qd[i]))
        go = float(g_opt_fn(P, Qf, m))
        su = (0.65 + 0.35 * startup_frac[i]) if startup_frac[i] > 0 else 1.0
        o2e = O2 if md in OPERATING else o2o
        eta = float(np.clip(eta_fn(P, m, f, o2e, o2o, GR, go, float(derate[i]), soot, tamb[i]) + ar[i], cb["eta_min"], cb["eta_max"])) * su
        # --- draft, interlock
        dr = float(draft_fn(P, IDe, FDe, Qf)) + draft_noise[i]
        interlock = 1.0 if md == "TRIP" else 0.0
        if md == "TRIP":
            trip_rem -= 1
            alarm[i] = "ALM_TRIP_DRAFT"
            if trip_rem == 0:
                restore[i + 1] = id_good
        elif dr >= 0.0 and md not in ("STANDBY",):
            trip_rem = P["trip_steps"]
            alarm[i] = "ALM_DRAFT_LOW"
        elif md == "FEEDER_STOP":
            alarm[i] = "ALM_FEEDER_STOP"
        elif dr > gr["draft_band_pa"][1]:
            alarm[i] = "ALM_DRAFT_LOW"
        elif md in OPERATING and O2 < 4.0:
            alarm[i] = "ALM_O2_LOW"
        if md in OPERATING and gr["draft_band_pa"][0] <= dr <= gr["draft_band_pa"][1] and not suppress[i]:
            id_good = ID
        for k, v in zip(keys, [F, B, Qf, eta, eta * Qf, O2, lam, o2o, go, f, dr, FD, ID, GR, soot, su, kd, interlock]):
            S[k][i] = v
        B_prev, eta_prev = B, eta

    # ---- truth-side vector quantities
    m_arr, lhv_arr = lot_m[lot_idx], lot_lhv[lot_idx]
    Qf, Qout, O2, f_arr = S["Qf"], S["Qout"], S["O2"], S["f"]
    heat_up = np.clip(Qf / 6.0, 0, 1)
    dT_h = tab.solve_dT(V, Tin, Qout)
    Tout_h = Tin + dT_h
    Tout_mix = Tin + (1 - byp) * dT_h
    unb = np.maximum(0.5, cb["unburnt_base"] + cb["unburnt_low_o2"] * np.maximum(0, cb["unburnt_o2_ref"] - np.minimum(O2, 14))
                     + cb["unburnt_grate"] * np.maximum(0, S["GR"] - cb["unburnt_grate_ref"]) + r_misc.normal(0, 0.2, n))
    co_true = co_fn(P, O2, S["GR"], S["gopt"], m_arr)

    # ---- best synthetic action (generator ground truth, feasible set)
    acts = [(0, 0, "HOLD")] + [(d, 0, f"FD{d:+d}") for d in (-4, -2, 2, 4)] + [(0, d, f"GRATE{d:+d}") for d in (-4, -2, 2, 4)] \
        + [(a, b, f"FD{a:+d}&GRATE{b:+d}") for a in (-2, 2) for b in (-2, 2)]
    operating = np.isin(mode, OPERATING)
    fdst = cb["fd_stoich_per_mw"] * Qf + 1e-9
    base_e = eta_fn(P, m_arr, f_arr, S["O2"], S["o2opt"], S["GR"], S["gopt"], derate.astype(float), S["soot"], tamb)
    gain = np.full((len(acts), n), -np.inf)
    for j, (dfd, dg, _) in enumerate(acts):
        fdn, grn = np.clip(S["FD"] + dfd, 0, 100), np.clip(S["GR"] + dg, 0, 100)
        lam_n = np.maximum(fdn * S["kd"] / fdst, 1.0005)
        o2n = np.minimum(21 * (1 - 1 / lam_n), 20.9)
        dr_n = draft_fn(P, S["ID"] * S["kd"], fdn * S["kd"], Qf)
        e_n = eta_fn(P, m_arr, f_arr, o2n, S["o2opt"], grn, S["gopt"], derate.astype(float), S["soot"], tamb)
        feas = ((fdn >= 20) & (fdn <= 100) & (dr_n >= gr["draft_band_pa"][0]) & (dr_n <= gr["draft_band_pa"][1])
                & (o2n >= gr["o2_floor"]) & (co_fn(P, o2n, grn, S["gopt"], m_arr) <= gr["co_limit_ppm"]))
        gain[j] = np.where(feas, (e_n - base_e) * 100.0, -np.inf)
    gain[0] = 0.0
    jbest = gain.argmax(axis=0)
    gbest = gain.max(axis=0)
    labels = np.array([a[2] for a in acts], dtype=object)
    best_label = np.where(operating & (gbest >= gr["best_gain_min_pp"]), labels[jbest], np.where(operating, "HOLD", "NONE"))
    best_gain = np.where(operating, np.maximum(gbest, 0.0), np.nan)

    # ---- measurement stage (truth + noise/bias/lag)
    flow_m = V * (1 + r_sen.normal(0, se["flow_sd"], n))
    for a, b in frozen_flow:
        flow_m[a:b] = flow_m[a - 1]
    Tin_m = Tin + se["temp_bias"] + r_sen.normal(0, se["temp_sd"], n)
    Tout_m = Tout_mix + se["temp_bias"] + r_sen.normal(0, se["temp_sd"], n)
    for a, b in tout_spike: Tout_m[a:b] += 40.0
    for a, b in tin_bias: Tin_m[a:b] -= 20.0
    for a, b in tout_oor: Tout_m[a:b] = 335.0
    ok_t = tab.in_range(Tin_m) & tab.in_range(Tout_m) & tab.in_range((Tin_m + Tout_m) / 2)
    Tm = np.where(ok_t, (Tin_m + Tout_m) / 2, tab.tmin)
    rho_m = np.where(ok_t, tab.rho(Tm), np.nan)
    cp_m = np.where(ok_t, tab.cp(Tm), np.nan)
    Tin_s, Tout_s = np.where(ok_t, Tin_m, tab.tmin), np.where(ok_t, Tout_m, tab.tmin)
    Qout_m = np.where(ok_t, flow_m / 3600.0 * rho_m * tab.cp_integral(Tin_s, Tout_s) / 1000.0, np.nan)
    speed = np.maximum(0.0, S["F"] / fu["feeder_cap_kgh"] * 100.0 + r_sen.normal(0, 0.3, n))
    F_belt = S["F"] * (1 + r_sen.normal(0, fu["belt_noise_sd"], n))
    F_vol = speed * fu["feeder_cap_kgh"] / 100.0 * (1 + lot_vbias[lot_idx]) * (1 + r_sen.normal(0, fu["vol_noise_sd"], n))
    F_m = np.maximum(0.0, np.where(vol, F_vol, F_belt))
    for a, b in fuel_spike: F_m[a:b] *= 4.0
    tot = np.cumsum(F_m * step / 60.0)
    for r in tot_reset:
        tot[r:] -= tot[r - 1]
    b_, a_ = [1 - se["o2_lag"]], [1, -se["o2_lag"]]
    o2_m = lfilter(b_, a_, O2, zi=lfilter_zi(b_, a_) * O2[0])[0] + 0.05 + r_sen.normal(0, se["o2_sd"], n)
    for a, b in frozen_o2:
        o2_m[a:b] = o2_m[a - 1]
    co_m = np.where(co_avail, co_true * np.exp(r_sen.normal(0, se["co_sd_log"], n)), np.nan)
    furn = tamb + (780 + 22 * (Qf - 12) - 10 * (np.minimum(O2, 14) - 7.5) - 3.5 * (m_arr - 15) - tamb) * heat_up + r_sen.normal(0, 4, n)
    flue = tamb + (310 + 9 * (Qf - 12) + 7 * (np.minimum(O2, 14) - 7.5) + 30 * f_arr - tamb) * heat_up + r_sen.normal(0, 2, n)
    stack = flue - (110 - 35 * f_arr) * heat_up + r_sen.normal(0, 1.5, n)
    dp = (fo["dp_base_pa"] + fo["dp_gain_pa"] * f_arr + 8 * (Qf - 12)) * np.where(S["soot"] > 0, 0.8, 1.0) + r_sen.normal(0, 4, n)
    p_fd = gs["fan_fd_rated_kw"] * (S["FD"] / 100.0) ** gs["fan_exponent"] * (1 + r_sen.normal(0, 0.01, n))
    p_id = gs["fan_id_rated_kw"] * (S["ID"] / 100.0) ** gs["fan_exponent"] * (1 + r_sen.normal(0, 0.01, n))
    alarm = np.where((alarm == "") & (Tout_h > gr["htf_out_limit_c"]), "ALM_HTF_T_HIGH", alarm)
    alarm = np.where((alarm == "") & (furn > gr["furnace_temp_limit_c"]), "ALM_FURNACE_T_HIGH", alarm)

    # ---- lab-style sparse ash / unburnt, lab fuel properties
    ash_m = np.full(n, np.nan); unb_m = np.full(n, np.nan)
    for L_ in range(n_lot):
        a = int(lot_start[L_]); s_ = a + fu["lab_sample_step"]; e_ = a + durs[L_]
        if s_ < min(e_, n):
            ash_m[s_] = lot_ash[L_] + r_misc.normal(0, fu["lab_ash_sd"])
            unb_m[s_] = unb[a:s_ + 1].mean() + r_misc.normal(0, fu["lab_unburnt_sd"])
    kn = lot_known[lot_idx]
    Q_in_m = np.where(kn, F_m / 3600.0 * lab_lhv[lot_idx], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        eta_d = np.where(kn & (Q_in_m > 0.5), 100.0 * Qout_m / Q_in_m, np.nan)
    sfc = np.where((Qout_m > 0.5) & (F_m > 0), F_m / (Qout_m * 3.6), np.nan)

    # ---- scenario labels
    scen = np.full(n, "STEADY", dtype=object)
    scen[mode == "RAMP"] = "RAMP"
    for L_ in range(1, n_lot):
        scen[int(lot_start[L_]):int(lot_start[L_]) + 6] = "LOT_CHANGE"
    scen[flow_ep != ""] = flow_ep[flow_ep != ""]
    scen[byp > 0] = "BYPASS"
    scen[O2 < 5.0] = "POOR_AIR_LOW_O2"
    scen[O2 > 10.5] = "POOR_AIR_HIGH_O2"
    scen[S["soot"] > 0] = "SOOTBLOW"
    for md_ in ("STARTUP", "STANDBY", "FEEDER_STOP", "TRIP"):
        scen[mode == md_] = md_
    scen = np.where(scen_fault != "", scen_fault, scen)

    df = pd.DataFrame({
        "timestamp_local": ts.strftime("%Y-%m-%d %H:%M:%S"), "heater_id": P["heater_id"], "operating_mode": mode,
        "fuel_lot": [f"LOT-{k + 1:04d}" for k in lot_idx],
        "fuel_moisture_wb_pct": np.where(kn, lab_m[lot_idx], np.nan), "fuel_LHV_asfired_MJkg": np.where(kn, lab_lhv[lot_idx], np.nan),
        "lhv_known": kn.astype(int), "fuel_rate_true_kgh": S["F"], "fuel_rate_measured_kgh": F_m, "fuel_totalizer_kg": tot,
        "HTF_flow_m3h": flow_m, "HTF_Tin_C": Tin_m, "HTF_Tout_C": Tout_m, "HTF_rho_kgm3": rho_m, "HTF_cp_kJkgK": cp_m,
        "Q_out_MW": Qout_m, "Q_in_MW": Q_in_m, "eta_direct_pct": eta_d, "SFC_kg_GJ": sfc, "O2_pct_dry": o2_m, "CO_ppm": co_m,
        "co_available": co_avail.astype(int), "FD_command_pct": S["FD"], "ID_command_pct": S["ID"], "grate_command_pct": S["GR"],
        "furnace_temp_C": furn, "flue_temp_C": flue, "draft_pa": S["draft"], "fan_derated": derate.astype(int),
        "sootblow": S["soot"].astype(int), "interlock_active": S["interlock"].astype(int), "quality_flag": "OK",
        "advice_eligibility": "", "true_synthetic_best_action": best_label, "scenario_id": scen,
        "is_fault_injected": inj.astype(int), "HTF_Tout_SP_C": sp_c, "HTF_bypass_pct": byp * 100.0, "HTF_pump_status": 1,
        "ambient_temp_C": tamb, "ambient_RH_pct": rh, "fan_power_kW_FD": p_fd, "fan_power_kW_ID": p_id, "feeder_speed_pct": speed,
        "fuel_mass_basis": np.where(vol, "VOLUMETRIC", "WEIGH_BELT"), "fuel_ash_pct": ash_m, "unburnt_in_ash_pct": unb_m,
        "stack_temp_C": stack, "economizer_dP_pa": dp, "draft_SP_pa": gr["draft_sp_pa"], "alarm_code": alarm,
        "fuel_price_index": price[day],
    })
    truth = pd.DataFrame({
        "timestamp_local": df["timestamp_local"], "fuel_lot_idx": lot_idx + 1, "moisture_true_wb_pct": m_arr,
        "LHV_true_MJkg": lhv_arr, "bed_tau_min": lot_tau[lot_idx], "Q_demand_MW": Qd, "fuel_feed_true_kgh": S["F"],
        "fuel_burn_true_kgh": S["B"], "Q_in_true_MW": Qf, "eta_true": S["eta"], "Q_out_true_MW": Qout, "HTF_flow_true_m3h": V,
        "HTF_Tin_true_C": Tin, "HTF_Tout_heater_true_C": Tout_h, "bypass_frac_true": byp, "O2_true_pct_dry": O2,
        "lambda_true": S["lam"], "O2_opt_true_pct": S["o2opt"], "grate_opt_true_pct": S["gopt"], "fouling_index": f_arr,
        "unburnt_true_pct": unb, "CO_true_ppm": co_true, "draft_true_pa": S["draft"], "best_action_eta_gain_pp": best_gain,
        "ash_true_pct": lot_ash[lot_idx],
    })
    keep = ~drops
    df, truth = df[keep].reset_index(drop=True), truth[keep].reset_index(drop=True)
    df["quality_flag"] = assess_quality(df, P, tab)
    df["advice_eligibility"] = eligibility(df, P)
    lg = pd.DataFrame(log, columns=["i", "variable", "old", "new", "shift_id", "reason_code", "source"])
    lg.insert(0, "timestamp", ts[lg["i"].values].strftime("%Y-%m-%d %H:%M:%S"))
    lg = lg[LOG_COLUMNS]
    lg = lg[lg["timestamp"].isin(set(df["timestamp_local"]))].reset_index(drop=True)
    fc = []
    for c in cases:
        a, b = c["a"], c["b"]
        fc.append([c["case_id"], c["type"], ts[c["start"]], ts[c["end"] - 1], ts[a], ts[b - 1], int(((ts >= ts[a]) & (ts < ts[b]) & ~drops).sum()),
                   c["desc"], c["exp"]])
    fcd = pd.DataFrame(fc, columns=FAULT_COLUMNS)
    for col in ("case_start", "case_end", "injected_start", "injected_end"):
        fcd[col] = fcd[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return dict(main=df[COLUMNS], truth=truth[TRUTH_COLUMNS], log=lg, faults=fcd, profile=profile, P=P, n_norm=n_norm)


def assess_quality(df, P, tab):
    gr, hf = P["guardrails"], P["htf"]
    step = pd.Timedelta(minutes=P["step_min"])
    t = pd.to_datetime(df["timestamp_local"])
    flags = {}
    flags["GAP_AFTER"] = (t.diff() > step).to_numpy()
    fz = np.zeros(len(df), bool)
    for col in ("O2_pct_dry", "HTF_flow_m3h"):
        v = df[col]
        fz |= ((v == v.shift(1)) & (v == v.shift(2))).to_numpy()
    flags["FROZEN_SENSOR"] = fz
    flags["TOTALIZER_RESET"] = (df["fuel_totalizer_kg"].diff() < 0).to_numpy()
    implied = df["feeder_speed_pct"] * 50.0
    flags["FUEL_IMPLAUSIBLE"] = ((implied > 50) & ((df["fuel_rate_measured_kgh"] - implied).abs() / implied.clip(lower=1) > gr["fuel_speed_mismatch"])).to_numpy()
    op = df["operating_mode"].isin(OPERATING)
    dT = df["HTF_Tout_C"] - df["HTF_Tin_C"]
    flags["HEAT_IMPLAUSIBLE"] = ((df["Q_out_MW"] > gr["heat_max_mw"]) | (op & ((dT < gr["dT_valid"][0]) | (dT > gr["dT_valid"][1])))).to_numpy()
    flags["PROPERTY_OOR"] = df["HTF_rho_kgm3"].isna().to_numpy()
    flags["BAD_FLOW"] = (op & ((df["HTF_flow_m3h"] < hf["flow_min"] * 0.98) | (df["HTF_flow_m3h"] > hf["flow_max"] * 1.02))).to_numpy()
    eta = df["eta_direct_pct"]
    flags["HEAT_BALANCE_CHECK"] = ((df["HTF_bypass_pct"] > 0) | ((df["operating_mode"] == "STEADY") & eta.notna()
                                   & ((eta < 100 * gr["eta_valid"][0]) | (eta > 100 * gr["eta_valid"][1])))).to_numpy()
    out = np.full(len(df), "", dtype=object)
    for k, v in flags.items():
        out = np.where(v, np.where(out == "", k, out + ";" + k), out)
    return np.where(out == "", "OK", out)


def eligibility(df, P):
    gr = P["guardrails"]
    q = df["quality_flag"]
    has = lambda s: q.str.contains(s, regex=False).to_numpy()
    mode = df["operating_mode"].to_numpy()
    sootb = df["sootblow"].to_numpy() > 0
    codes = {
        "TRANSIENT": (mode != "STEADY") & ~np.isin(mode, ["TRIP", "FEEDER_STOP"]) | sootb | has("GAP_AFTER"),
        "LOW_FUEL_CONF": (df["fuel_mass_basis"] == "VOLUMETRIC").to_numpy() | (df["lhv_known"] == 0).to_numpy()
        | (mode == "FEEDER_STOP") | has("FUEL_IMPLAUSIBLE") | has("TOTALIZER_RESET"),
        "BAD_FLOW": has("BAD_FLOW"),
        "STALE_DATA": has("FROZEN_SENSOR"),
        "PROPERTY_OOR": has("PROPERTY_OOR"),
        "ENERGY_BALANCE": has("HEAT_BALANCE_CHECK") | has("HEAT_IMPLAUSIBLE"),
        "TRIP_ACTIVE": (df["interlock_active"] > 0).to_numpy() | (df["alarm_code"] != "").to_numpy() & ~df["alarm_code"].isin(["ALM_DRAFT_LOW", "ALM_O2_LOW"]).to_numpy(),
        "FAN_DERATE": (df["fan_derated"] > 0).to_numpy(),
        "UNSAFE_DRAFT": ((df["draft_pa"] < gr["draft_band_pa"][0]) | (df["draft_pa"] > gr["draft_band_pa"][1])).to_numpy(),
        "HIGH_TEMP": ((df["furnace_temp_C"] > gr["furnace_temp_limit_c"]) | (df["HTF_Tout_C"] > gr["htf_out_limit_c"])).to_numpy(),
        "LOW_O2": (df["O2_pct_dry"] < gr["o2_floor"]).to_numpy(),
        "HIGH_CO": (df["CO_ppm"] > gr["co_limit_ppm"]).to_numpy(),
    }
    blocking = np.zeros(len(df), bool)
    for v in codes.values():
        blocking |= v
    t = pd.to_datetime(df["timestamp_local"])
    contiguous = (t.diff() == pd.Timedelta(minutes=P["step_min"])).to_numpy()
    run = np.zeros(len(df), int)
    for i in range(len(df)):
        run[i] = 0 if blocking[i] else (run[i - 1] + 1 if i > 0 and contiguous[i] else 1)
    out = np.full(len(df), "ELIGIBLE", dtype=object)
    short = (~blocking) & (run < gr["stable_steps"])
    nocoal = (~blocking) & ~short & (df["co_available"] == 0).to_numpy()
    out[nocoal] = "DIAGNOSTIC_ONLY:NO_CO"
    for i in np.where(blocking | short)[0]:
        c = [k for k, v in codes.items() if v[i]] or ["TRANSIENT"]
        out[i] = "NO_ADVICE:" + ";".join(c)
    return out


def display_records(df, seed=42):
    """HMI-style daily display records derived from the data; three injected cases (see injected_case)."""
    rng = np.random.default_rng(seed + 1000)
    t = pd.to_datetime(df["timestamp_local"])
    d = df[~df["scenario_id"].str.startswith("FAULT_")].copy()
    d["date"] = t[d.index].dt.date
    rows = []
    for k, (date, g) in enumerate(d.groupby("date")):
        if len(g) < 288:
            continue
        r = g.iloc[int(rng.integers(96, 240))]
        kgs = round(r["fuel_rate_measured_kgh"] / 3600.0, 3)
        kgday = round(float(g["fuel_rate_measured_kgh"].sum() * 5 / 60), -1)
        mkh = round(r["Q_out_MW"] / MKCAL_H_TO_MW, 3)
        mw = round(r["Q_out_MW"], 2)
        mkd = round(float((g["Q_out_MW"].fillna(0) / MKCAL_H_TO_MW).sum() * 5 / 60), 2)
        rows.append(dict(record_id=f"R{k + 1:03d}", date=str(date), time=r["timestamp_local"][11:], kgs_disp=kgs, kgday_disp=kgday,
                         mkcal_h_disp=mkh, mw_disp=mw, mkcal_day_disp=mkd, injected_case=""))
    for rid, case in (("R005", "TOTALIZER_RESET_MIDDAY"), ("R011", "CONTRADICTORY"), ("R017", "UNIT_SLIP")):
        for r in rows:
            if r["record_id"] == rid:
                r["injected_case"] = case
                if case == "TOTALIZER_RESET_MIDDAY": r["kgday_disp"] = round(r["kgday_disp"] * 0.62, -1)
                elif case == "CONTRADICTORY": r["kgs_disp"], r["kgday_disp"] = 1.05, 21000.0
                else: r["mw_disp"] = round(r["mw_disp"] * 1.05, 2)
    for r in rows:
        v, why = reconcile_display(r["kgs_disp"], r["kgday_disp"], r["mkcal_h_disp"], r["mw_disp"], r["mkcal_day_disp"])
        implied = r["kgs_disp"] * 86400
        r.update(implied_kgday=round(implied, 1), rel_diff_fuel_pct=round(100 * abs(r["kgday_disp"] - implied) / implied, 2),
                 mw_from_mkcal_h=round(r["mkcal_h_disp"] * MKCAL_H_TO_MW, 3), verdict=v, reasons=";".join(why))
    return pd.DataFrame(rows)


def write_outputs(res, out, display_recon=None):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.name == "synthetic_heater_c_5min.csv":
        names = ("synthetic_truth.csv", "fault_cases.csv", "operator_action_log.csv")
    else:
        names = tuple(f"{out.stem}_{s}.csv" for s in ("truth", "fault_cases", "operator_action_log"))
    res["main"].round(4).to_csv(out, index=False)
    res["truth"].round(5).to_csv(out.parent / names[0], index=False)
    res["faults"].to_csv(out.parent / names[1], index=False)
    res["log"].to_csv(out.parent / names[2], index=False)
    if display_recon:
        Path(display_recon).parent.mkdir(parents=True, exist_ok=True)
        display_records(res["main"]).to_csv(display_recon, index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", default="data/raw_synthetic/synthetic_heater_c_5min.csv")
    ap.add_argument("--profile", default=None, help="main|stress|site_style (default by seed)")
    ap.add_argument("--display-recon", default=None, help="also write the display reconciliation CSV here")
    a = ap.parse_args()
    res = generate(a.seed, a.days, a.profile)
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    dr = None if not a.display_recon else (Path(a.display_recon) if Path(a.display_recon).is_absolute() else ROOT / a.display_recon)
    write_outputs(res, out, dr)
    df = res["main"]
    normal = int((~df["scenario_id"].str.startswith("FAULT_")).sum())
    print(f"profile={res['profile']} seed={a.seed} shape={df.shape} normal_rows={normal} fault_block_rows={len(df) - normal} "
          f"log_rows={len(res['log'])} sha256={frame_hash(df)[:16]}")


if __name__ == "__main__":
    main()
