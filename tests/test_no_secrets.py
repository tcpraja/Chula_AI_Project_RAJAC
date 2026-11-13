"""Fail if any denylisted whole word appears in output folders (text content or file names)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRS = ["reports", "final", "models", "data/clean", "data/holdout", "data/stress", "data/raw_synthetic"]
TEXT_EXT = {".md", ".csv", ".txt", ".json", ".yaml", ".yml", ".py", ".html", ".svg", ".toml"}


def _patterns():
    lines = (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines()
    terms = [t.strip() for t in lines if t.strip() and not t.startswith("#")]
    return [(t, re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I)) for t in terms]


def test_no_denylisted_terms():
    pats = _patterns()
    assert pats, "denylist is empty"
    hits = []
    for d in OUTPUT_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            hits += [f"{p.relative_to(ROOT)} (name): {t}" for t, rx in pats if rx.search(p.name)]
            if p.suffix.lower() in TEXT_EXT:
                text = p.read_text(encoding="utf-8", errors="ignore")
                hits += [f"{p.relative_to(ROOT)}: {t}" for t, rx in pats if rx.search(text)]
    assert not hits, "denylisted terms found:\n" + "\n".join(hits)


def test_word_boundary_does_not_false_positive():
    rx = dict(_patterns())["IVL"]
    assert not rx.search("civil works") and rx.search("the IVL plant")
