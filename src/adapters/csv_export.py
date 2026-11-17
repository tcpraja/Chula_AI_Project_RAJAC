"""CsvExportSource: reads a historian CSV EXPORT file (never a live connection) and maps it to the internal raw schema.

Applies the tag map: site tag -> internal name, value maps, unit conversions (mmWC->Pa, Mkcal/h->MW, kg/s->kg/h ...), defaults for
unavailable optional columns, and the derived flags lhv_known, co_available, heater_id. Unavailable combustion columns are listed in
`site_unavailable`, which makes the guardrails answer DIAGNOSTIC_ONLY. Opens the file read-only; there is no write path.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.adapters import conversions as cv, tagmap as tm
from src.adapters.base import ReadOnlySource, SourceResult

RAW_COLUMNS = None  # filled lazily from the synthetic raw header so the output has every column cleaning expects


def internal_columns():
    p = Path(__file__).resolve().parents[2] / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv"
    if p.exists():
        return pd.read_csv(p, nrows=0).columns.tolist()
    return ["timestamp_local", "heater_id", *tm.META_BY, "lhv_known", "co_available"]


class CsvExportSource(ReadOnlySource):
    kind = "csv_export"

    def __init__(self, path, tag_map, heater_id="HEATER_C_SYNTHETIC", encoding="utf-8"):
        self.path = Path(path)
        self.map = tag_map if isinstance(tag_map, dict) else tm.load(tag_map)
        self.heater_id = heater_id
        self.encoding = encoding

    def read(self) -> SourceResult:
        with open(self.path, "rb") as fh:                      # read-only open, never write
            raw = pd.read_csv(fh, encoding=self.encoding, low_memory=False)
        cols = self.map["columns"]
        out = pd.DataFrame(index=raw.index)
        missing, unavailable = [], []
        t_tag = self.map["time"]["site_tag"]
        if t_tag not in raw.columns:
            raise KeyError("time tag not found in the export header")
        out["timestamp_local"] = pd.to_datetime(raw[t_tag], format=self.map["time"].get("format")).dt.strftime("%Y-%m-%d %H:%M:%S")
        for name, e in cols.items():
            if e.get("source") != "site":
                continue
            ok = e.get("available") is True and not tm.is_placeholder(e.get("site_tag"))
            if ok and e["site_tag"] not in raw.columns:
                missing.append(name)
                ok = False
            if not ok:
                unavailable.append(name)
                out[name] = e.get("default_if_unavailable", np.nan)
                continue
            s = raw[e["site_tag"]]
            if e.get("value_map"):
                s = s.astype(str).map(e["value_map"])
            elif e.get("internal_unit") not in ("-", "0/1") or e.get("conversion", "identity") != "identity":
                s = cv.apply(s, e.get("conversion", "identity"))
            out[name] = s
        out["heater_id"] = self.heater_id
        out["lhv_known"] = out["fuel_LHV_asfired_MJkg"].notna().astype(int)
        out["co_available"] = (out["CO_ppm"].notna() & ("CO_ppm" not in unavailable)).astype(int)
        comb = [n for n in unavailable if cols[n].get("combustion")]
        out["site_unavailable"] = ",".join(comb)
        for c in internal_columns():
            if c not in out.columns:
                out[c] = np.nan
        for c in ("fan_derated", "sootblow", "interlock_active"):
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
        return SourceResult(out, {"kind": self.kind, "rows": len(out), "unavailable": unavailable, "unavailable_combustion": comb, "missing_site_tags": missing})
