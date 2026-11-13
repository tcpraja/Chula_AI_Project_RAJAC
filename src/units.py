"""Unit conversions, HTF property table and display-record reconciliation (SYNTHETIC).

HTF properties come only from config/htf_properties.csv; never water cp; never extrapolated.
Run: python -m src.units --help
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KCAL_TO_KJ = 4.184
MKCAL_H_TO_MW = 1.16222
PA_PER_MMWC = 9.80665
WATER_CP = 4.186  # forbidden as an HTF value; kept only so tests can assert it is never used


class PropertyOutOfRange(ValueError):
    """Temperature outside the HTF property table (reason code PROPERTY_OOR)."""


def mmwc_to_pa(x):
    return np.asarray(x, dtype=float) * PA_PER_MMWC if np.ndim(x) else float(x) * PA_PER_MMWC


def kgs_to_kgday(kgs):
    """Valid only if the rate is sustained for 24 h."""
    return kgs * 86400.0


def kgday_to_kgs(kgday):
    return kgday / 86400.0


def mkcal_h_to_mw(x):
    return x * MKCAL_H_TO_MW


def mw_to_mkcal_h(x):
    return x / MKCAL_H_TO_MW


def sfc_kg_gj(eta_frac, lhv_mj_kg):
    """SFC kg/GJ = 1 / (eta x LHV[GJ/kg])."""
    return 1.0 / (eta_frac * lhv_mj_kg / 1000.0)


def fuel_reduction(eta_base, eta_cand):
    """Scenario identity 1 - eta_base/eta_cand (an identity, not a result)."""
    return 1.0 - eta_base / eta_cand


class HTFTable:
    """Piecewise-linear rho(T), cp(T); raises PropertyOutOfRange outside the table."""

    def __init__(self, path=None):
        df = pd.read_csv(path or ROOT / "config" / "htf_properties.csv")
        self.T = df["T_C"].to_numpy(float)
        self.rho_t = df["rho_kgm3"].to_numpy(float)
        self.cp_t = df["cp_kJkgK"].to_numpy(float)
        if np.any(np.diff(self.T) <= 0):
            raise ValueError("T_C must be strictly increasing")
        self.tmin, self.tmax = float(self.T[0]), float(self.T[-1])
        dT = np.diff(self.T)
        self._slope = np.diff(self.cp_t) / dT
        seg = 0.5 * (self.cp_t[1:] + self.cp_t[:-1]) * dT
        self._cum = np.concatenate([[0.0], np.cumsum(seg)])

    def in_range(self, T):
        T = np.asarray(T, float)
        return (T >= self.tmin) & (T <= self.tmax)

    def _check(self, T):
        if not np.all(self.in_range(T)):
            raise PropertyOutOfRange(f"T outside [{self.tmin}, {self.tmax}] C")

    def rho(self, T):
        self._check(T)
        return np.interp(T, self.T, self.rho_t)

    def cp(self, T):
        self._check(T)
        return np.interp(T, self.T, self.cp_t)

    def _cumint(self, T):
        """Integral of cp dT from tmin to T, kJ/kg."""
        T = np.asarray(T, float)
        k = np.clip(np.searchsorted(self.T, T, side="right") - 1, 0, len(self.T) - 2)
        d = T - self.T[k]
        return self._cum[k] + self.cp_t[k] * d + 0.5 * self._slope[k] * d * d

    def cp_integral(self, T1, T2):
        """Integral of cp dT between T1 and T2 (kJ/kg)."""
        self._check(T1)
        self._check(T2)
        return self._cumint(T2) - self._cumint(T1)

    def heat_mw(self, V_m3h, Tin, Tout):
        """Q = V/3600 x rho(Tmean) x integral cp dT, MW."""
        m = np.asarray(V_m3h, float) / 3600.0 * self.rho((np.asarray(Tin, float) + np.asarray(Tout, float)) / 2.0)
        return m * self.cp_integral(Tin, Tout) / 1000.0

    def solve_dT(self, V_m3h, Tin, Q_mw, iters=10):
        """Temperature rise (K), vectorized, so that heat_mw(V, Tin, Tin+dT) = Q (0 where Q <= 0)."""
        V, Tin, Q = np.broadcast_arrays(*(np.asarray(x, float) for x in (V_m3h, Tin, Q_mw)))
        dT = np.full(Q.shape, 20.0)
        for _ in range(iters):
            m = V / 3600.0 * self.rho(Tin + dT / 2.0)
            cpa = (self._cumint(Tin + dT) - self._cumint(Tin)) / np.maximum(dT, 1e-6)
            with np.errstate(divide="ignore", invalid="ignore"):
                dT = np.where(Q > 0, Q * 1000.0 / (m * cpa), 0.0)
            dT = np.where((Q > 0) & (dT < 1e-6), 1e-6, dT)
        return dT


def reconcile_display(kgs, kgday, mkcal_h, mw=None, mkcal_day=None):
    """Return (verdict, reasons) for an HMI-style display record.

    kg/s x 86400 = kg/day only if sustained -> 5-25 % gap is WINDOW_MISMATCH (not usable as proxy);
    > 50 % fuel gap or > 10 % heat unit gap is a contradictory record -> REJECT.
    """
    reasons = []
    implied = kgs * 86400.0
    rel_f = abs(kgday - implied) / implied if implied > 0 else (0.0 if kgday == 0 else np.inf)
    rel_h = 0.0
    if mw is not None and mkcal_h > 0:
        rel_h = abs(mw - mkcal_h * MKCAL_H_TO_MW) / (mkcal_h * MKCAL_H_TO_MW)
    rel_d = 0.0
    if mkcal_day is not None and mkcal_h > 0:
        rel_d = abs(mkcal_day - mkcal_h * 24.0) / (mkcal_h * 24.0)
    if rel_f > 0.5:
        reasons.append("FUEL_DAY_VS_RATE_CONTRADICTION")
    if rel_h > 0.10:
        reasons.append("HEAT_UNIT_CONTRADICTION")
    if reasons:
        return "REJECT", reasons
    if rel_f > 0.05:
        reasons.append("FUEL_WINDOW_MISMATCH")
    if rel_h > 0.02:
        reasons.append("HEAT_UNIT_MISMATCH")
    if rel_d > 0.25:
        reasons.append("HEAT_DAY_WINDOW_MISMATCH")
    return ("WINDOW_MISMATCH" if reasons else "OK"), reasons


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="print the SPEC C3 worked example")
    if not ap.parse_args().selftest:
        ap.print_help()
        return
    t = HTFTable()
    m = 700 / 3600 * 780
    print(f"mass flow {m:.1f} kg/s; Q_out {m * 2.60 * 20.3 / 1000:.2f} MW; "
          f"SFC {sfc_kg_gj(0.675, 15):.1f} kg/GJ; reduction {100 * fuel_reduction(0.675, 0.700):.2f} %; "
          f"table {t.tmin}-{t.tmax} C")


if __name__ == "__main__":
    main()
