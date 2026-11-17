"""Unit conversions for tag maps: name -> (forward site->internal, inverse internal->site, site unit, internal unit).

Forward functions reuse src.units constants so the whole project shares one definition (1 mmWC = 9.80665 Pa,
1 Mkcal/h = 1.16222 MW, 1 kg/s = 3600 kg/h). A conversion may also be a mapping {factor: x, offset: y}: internal = site * factor + offset.
"""
import numpy as np
import pandas as pd

from src.units import MKCAL_H_TO_MW, PA_PER_MMWC

CONVERSIONS = {
    "identity": (lambda x: x, lambda x: x, "same", "same"),
    "mmwc_to_pa": (lambda x: x * PA_PER_MMWC, lambda x: x / PA_PER_MMWC, "mmWC", "Pa"),
    "kpa_to_pa": (lambda x: x * 1000.0, lambda x: x / 1000.0, "kPa", "Pa"),
    "mkcal_h_to_mw": (lambda x: x * MKCAL_H_TO_MW, lambda x: x / MKCAL_H_TO_MW, "Mkcal/h", "MW"),
    "kw_to_mw": (lambda x: x / 1000.0, lambda x: x * 1000.0, "kW", "MW"),
    "kgs_to_kgh": (lambda x: x * 3600.0, lambda x: x / 3600.0, "kg/s", "kg/h"),
    "kgday_to_kgh": (lambda x: x / 24.0, lambda x: x * 24.0, "kg/day", "kg/h"),
    "t_to_kg": (lambda x: x * 1000.0, lambda x: x / 1000.0, "t", "kg"),
    "m3s_to_m3h": (lambda x: x * 3600.0, lambda x: x / 3600.0, "m3/s", "m3/h"),
    "fraction_to_pct": (lambda x: x * 100.0, lambda x: x / 100.0, "fraction", "%"),
}


def resolve(spec):
    """spec: a name from CONVERSIONS or {factor, offset}. Returns (forward, inverse). Raises KeyError/ValueError for unknown specs."""
    if isinstance(spec, dict):
        f, o = float(spec.get("factor", 1.0)), float(spec.get("offset", 0.0))
        if f == 0:
            raise ValueError("factor must not be 0")
        return (lambda x: x * f + o), (lambda x: (x - o) / f)
    if spec not in CONVERSIONS:
        raise KeyError(f"unknown conversion '{spec}'")
    return CONVERSIONS[spec][0], CONVERSIONS[spec][1]


def apply(series, spec, inverse=False):
    fwd, inv = resolve(spec)
    return (inv if inverse else fwd)(pd.to_numeric(series, errors="coerce").astype(float))


def is_known(spec):
    try:
        resolve(spec)
        return True
    except (KeyError, ValueError):
        return False


__all__ = ["CONVERSIONS", "resolve", "apply", "is_known", "np"]
