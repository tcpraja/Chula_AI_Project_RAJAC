"""Generate the SYNTHETIC site-style demo set used to exercise the Phase 8 adapters end to end (no real data, no real tags).

Writes under data/site_style/: internal_raw_seed101.csv (generator, site_style profile), site_export_synthetic.csv (invented tags and site units:
mmWC, kg/s, Mkcal/h), and config/tag_map_synthetic_site.yaml + config/site_synthetic_demo.yaml (a filled demo site config whose approval fields are
marked SYNTHETIC-TEST, not a real approval). Run: python -m src.site_demo
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

from src import generate_synthetic as gen
from src.adapters import synthetic as syn, tagmap as tm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "site_style"


def build(days=60, seed=101, out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    res = gen.generate(seed, days)
    raw = res["main"]
    raw.to_csv(out / "internal_raw_seed101.csv", index=False)
    tmap = tm.synthetic_site_map()
    export = syn.to_site_export(raw, tmap)
    export.to_csv(out / "site_export_synthetic.csv", index=False)
    (ROOT / "config" / "tag_map_synthetic_site.yaml").write_text(
        "# SYNTHETIC demo tag map: invented tags SITE_<NAME>, every site column available. Not a real site.\n" + yaml.safe_dump(tmap, sort_keys=False, allow_unicode=True), encoding="utf-8")
    limits = yaml.safe_load((ROOT / "config" / "guardrail_limits.yaml").read_text(encoding="utf-8"))["limits"]
    site = {"site_id": "SYNTHETIC_DEMO_SITE", "heater_id": "HEATER_C_SYNTHETIC", "mode": "SHADOW", "property_table_path": "config/htf_properties.csv",
            "tag_map_path": "config/tag_map_synthetic_site.yaml",
            "approval": {"approver": "SYNTHETIC-TEST (not a real approval)", "date": "2026-01-01", "moc_reference": "SYNTHETIC-TEST", "notes": "demo only"},
            "limits": limits, "cleaning_overrides": {},
            "mv": {"baseline_start": None, "baseline_end": None, "trial_start": None, "trial_end": None}}
    (ROOT / "config" / "site_synthetic_demo.yaml").write_text(
        "# SYNTHETIC demo site config: synthetic envelope limits, approval fields marked SYNTHETIC-TEST. Real sites start from config/site_template.yaml.\n"
        + yaml.safe_dump(site, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return raw, export


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=60)
    a = ap.parse_args()
    raw, export = build(a.days)
    print(f"internal raw {raw.shape}, site export {export.shape} (columns use invented SITE_ tags and site units)")


if __name__ == "__main__":
    main()
