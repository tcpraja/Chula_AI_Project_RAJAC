"""Site configuration: mode, limits, approvals (CLAUDE.md rules 3 and 4).

MODE = SHADOW (read-only scoring, nothing shown to operators) or ADVISORY. ADVISORY is REFUSED unless every limit is filled (no
REQUIRES_OEM_APPROVAL left) and approver, approval date and MOC reference are set. Real modes show "ADVISORY ONLY — OPERATOR DECIDES".
Limits left as REQUIRES_OEM_APPROVAL make the guardrails answer NO_ADVICE for every row (LIMITS_NOT_APPROVED).
Run: python -m src.site_config --site config/site_template.yaml
"""
import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from src import guardrails as gd

ROOT = Path(__file__).resolve().parents[1]
MODES = ("SHADOW", "ADVISORY")
REAL_BANNER = "ADVISORY ONLY — OPERATOR DECIDES"
SHADOW_BANNER = "SHADOW MODE — READ-ONLY, NOT SHOWN TO OPERATORS · ADVISORY ONLY — OPERATOR DECIDES"
LIMIT_TO_CLEANING = {"draft_band_pa": "draft_band_pa", "o2_floor_pct": "o2_floor", "co_limit_ppm": "co_limit_ppm", "furnace_temp_limit_c": "furnace_temp_limit_c",
                     "htf_out_limit_c": "htf_out_limit_c", "eta_valid": "eta_valid", "flow_valid_m3h": "flow_valid_m3h", "stable_steps": "stable_steps"}


class SiteConfigError(ValueError):
    """The site configuration is not acceptable for the requested mode."""


@dataclass
class SiteConfig:
    raw: dict
    path: Path

    @property
    def mode(self):
        return str(os.environ.get("MODE") or self.raw.get("mode", "SHADOW")).upper()

    @property
    def heater_id(self):
        return self.raw.get("heater_id", "HEATER_C_SYNTHETIC")

    @property
    def tag_map_path(self):
        return self._p(self.raw.get("tag_map_path", "config/tag_map_template.yaml"))

    @property
    def property_table_path(self):
        return self._p(self.raw.get("property_table_path", "config/htf_properties.csv"))

    @property
    def limits(self):
        return dict(self.raw.get("limits", {}))

    def _p(self, p):
        """Relative paths: next to the site yaml, then its parent folder, then the repository root."""
        p = Path(p)
        if p.is_absolute():
            return p
        for base in (self.path.parent, self.path.parent.parent, ROOT):
            if (base / p).exists():
                return base / p
        return ROOT / p

    def unfilled_limits(self):
        return [k for k, v in self.limits.items() if v is None or v == gd.PLACEHOLDER or (isinstance(v, (list, tuple)) and (gd.PLACEHOLDER in v or None in v))]

    def missing_approval(self):
        a = self.raw.get("approval", {}) or {}
        return [k for k in ("approver", "date", "moc_reference") if not a.get(k)]

    def validate(self):
        """Raise SiteConfigError if the configured mode is not allowed. SHADOW is always allowed (advice is withheld by the guardrails)."""
        if self.mode not in MODES:
            raise SiteConfigError(f"MODE must be one of {MODES}, got '{self.mode}'")
        if self.mode == "ADVISORY":
            problems = []
            if self.unfilled_limits():
                problems.append(f"limits not filled: {self.unfilled_limits()}")
            if self.missing_approval():
                problems.append(f"approval fields missing: {self.missing_approval()}")
            if problems:
                raise SiteConfigError("ADVISORY refused: " + "; ".join(problems))
        return self

    def banner(self):
        return REAL_BANNER if self.mode == "ADVISORY" else SHADOW_BANNER

    def guardrail_config(self):
        """Config dict for guardrails.evaluate. Any limit the site did not list stays REQUIRES_OEM_APPROVAL (fail-safe)."""
        base = gd.load_limits(ROOT / "config" / "guardrail_limits.yaml")      # explicit path: avoids re-entering the site hook in guardrails.load_limits
        limits = {k: gd.PLACEHOLDER for k in base["limits"]}
        limits.update(self.limits)
        return {"provenance": "SITE_CONFIG:" + str(self.raw.get("site_id", "?")), "limits": limits, "optimizer": base["optimizer"]}

    def cleaning_cfg(self):
        from src.cleaning import load_cfg
        cfg = load_cfg()
        cfg["heater_id"] = self.heater_id
        for lk, ck in LIMIT_TO_CLEANING.items():
            v = self.limits.get(lk)
            if v is not None and v != gd.PLACEHOLDER and not (isinstance(v, (list, tuple)) and gd.PLACEHOLDER in v):
                cfg[ck] = v
        cfg.update(self.raw.get("cleaning_overrides") or {})
        return cfg


def load_site(path):
    p = Path(path)
    return SiteConfig(yaml.safe_load(p.read_text(encoding="utf-8")) or {}, p.resolve())


def from_env():
    """The site config named by HEATER_SITE (set by docker/compose), or None for the plain synthetic demo."""
    p = os.environ.get("HEATER_SITE")
    return load_site(p) if p and Path(p).exists() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True)
    a = ap.parse_args()
    s = load_site(a.site)
    try:
        s.validate()
    except SiteConfigError as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"site config OK: mode {s.mode}; banner: {s.banner()}; unfilled limits: {len(s.unfilled_limits())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
