"""Refuse a tag map that is not ready: unmapped critical tags, undecided columns, unknown conversions, duplicate site tags, tags missing
from the export header. Prints COLUMN NAMES and issue codes only, never data values. Exit code 2 = refused.

Run: python -m src.adapters.check_mapping --tag-map config/tag_map.yaml [--path export.csv] [--site site.yaml]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from src.adapters import conversions as cv, tagmap as tm


def check(tag_map, header=None):
    """Return a list of (code, column) issues; an empty list means the map is acceptable."""
    issues = []
    cols = tag_map.get("columns", {})
    site = {n: e for n, e in cols.items() if e.get("source") == "site"}
    if tm.is_placeholder(tag_map.get("time", {}).get("site_tag")):
        issues.append(("UNMAPPED_CRITICAL", "timestamp"))
    seen = {}
    for n, e in site.items():
        avail, tag = e.get("available"), e.get("site_tag")
        if avail is None:
            issues.append(("UNDECIDED", n))                      # every column must be marked available / unavailable
            continue
        if avail and tm.is_placeholder(tag):
            issues.append(("UNMAPPED_CRITICAL" if e.get("critical") else "UNMAPPED", n))
        if not avail and e.get("critical"):
            issues.append(("UNAVAILABLE_CRITICAL", n))
        if avail and not cv.is_known(e.get("conversion", "identity")):
            issues.append(("UNKNOWN_CONVERSION", n))
        if avail and not tm.is_placeholder(tag):
            if tag in seen:
                issues.append(("DUPLICATE_TAG", n))
            seen[tag] = n
    for grp in tag_map.get("any_of_critical", []):
        if not any(site.get(g, {}).get("available") is True and not tm.is_placeholder(site.get(g, {}).get("site_tag")) for g in grp):
            issues.append(("UNMAPPED_CRITICAL", "|".join(grp)))
    for n in tm.META_BY:
        if n not in site:
            issues.append(("MISSING_ENTRY", n))
    if header is not None:
        hdr = set(header)
        if tag_map.get("time", {}).get("site_tag") not in hdr and not tm.is_placeholder(tag_map.get("time", {}).get("site_tag")):
            issues.append(("TAG_NOT_IN_EXPORT", "timestamp"))
        for n, e in site.items():
            if e.get("available") and not tm.is_placeholder(e.get("site_tag")) and e["site_tag"] not in hdr:
                issues.append(("TAG_NOT_IN_EXPORT", n))
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag-map", default=None)
    ap.add_argument("--site", default=None, help="site yaml; its tag_map_path is used when --tag-map is absent")
    ap.add_argument("--path", default=None, help="historian CSV export (only its header row is read)")
    a = ap.parse_args(argv)
    path = a.tag_map
    if not path and a.site:
        from src import site_config
        path = site_config.load_site(a.site).tag_map_path
    header = pd.read_csv(a.path, nrows=0).columns.tolist() if a.path else None
    issues = check(tm.load(path), header)
    if issues:
        print(f"REFUSED: {len(issues)} mapping issue(s)")
        for code, col in issues:
            print(f"  {code}: {col}")
        return 2
    print("tag map OK (names checked only; no data values printed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
