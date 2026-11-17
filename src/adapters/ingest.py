"""Ingest: historian CSV export (or synthetic raw) -> internal raw CSV in the working folder, ready for `pipeline --stage clean`.

check_mapping runs first and refuses an unready map. Output path is printed; no data values are printed.
Run: python -m src.adapters.ingest --site site.yaml --path export.csv [--out data/raw_site/raw.csv]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from src import site_config
from src.adapters import tagmap as tm
from src.adapters.check_mapping import check
from src.adapters.csv_export import CsvExportSource

ROOT = Path(__file__).resolve().parents[2]


def ingest(site_path, export_path, out=None):
    site = site_config.load_site(site_path)
    tmap = tm.load(site.tag_map_path)
    issues = check(tmap, pd.read_csv(export_path, nrows=0).columns.tolist())
    if issues:
        raise SystemExit("REFUSED by check_mapping: " + ", ".join(f"{c}:{n}" for c, n in issues))
    res = CsvExportSource(export_path, tmap, heater_id=site.heater_id).read()
    out = Path(out or ROOT / "data" / "raw_site" / "raw.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    res.df.to_csv(out, index=False)
    return out, res.meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out, meta = ingest(a.site, a.path, a.out)
    print(f"raw written: {out}")
    print(f"unavailable combustion columns: {meta['unavailable_combustion'] or 'none'} (any listed => DIAGNOSTIC_ONLY)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
