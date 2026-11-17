"""SyntheticSource: reads the generator's raw CSV in the internal schema (identity mapping). Also builds a site-style export for tests:
`to_site_export(raw, tag_map)` renames columns to site tags and converts INTERNAL -> SITE units (Pa->mmWC, MW->Mkcal/h, kg/h->kg/s),
so CsvExportSource can be checked by round trip. SYNTHETIC only."""
from pathlib import Path

import pandas as pd

from src.adapters import conversions as cv
from src.adapters.base import ReadOnlySource, SourceResult

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "data" / "raw_synthetic" / "synthetic_heater_c_5min.csv"


class SyntheticSource(ReadOnlySource):
    kind = "synthetic"

    def __init__(self, path=None):
        self.path = Path(path or DEFAULT)

    def read(self) -> SourceResult:
        with open(self.path, "rb") as fh:
            df = pd.read_csv(fh)
        df["site_unavailable"] = ""
        return SourceResult(df, {"kind": self.kind, "rows": len(df), "unavailable": [], "unavailable_combustion": [], "missing_site_tags": []})


def to_site_export(raw, tag_map, drop=()):
    """Internal-schema frame -> site-style export (site tag names, site units). `drop`: internal columns the 'site' does not export."""
    out = pd.DataFrame({tag_map["time"]["site_tag"]: raw["timestamp_local"].astype(str).str[:19]})
    for name, e in tag_map["columns"].items():
        if e.get("source") != "site" or name in drop or name not in raw.columns:
            continue
        s = raw[name]
        if e.get("value_map"):
            inv = {v: k for k, v in e["value_map"].items()}
            s = s.map(inv)
        elif e.get("internal_unit") not in ("-", "0/1") or e.get("conversion", "identity") != "identity":
            s = cv.apply(s, e.get("conversion", "identity"), inverse=True)
        out[e["site_tag"]] = s.to_numpy()
    return out
