"""Fail if any denylisted term appears in output folders (text content or file names)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRS = ["reports", "final", "models", "data/clean", "data/holdout", "data/stress", "data/raw_synthetic"]
TEXT_EXT = {".md", ".csv", ".txt", ".json", ".yaml", ".yml", ".py", ".html", ".svg", ".toml"}


def _terms():
    lines = (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines()
    return [t.strip().lower() for t in lines if t.strip() and not t.startswith("#")]


def test_no_denylisted_terms():
    terms = _terms()
    assert terms, "denylist is empty"
    hits = []
    for d in OUTPUT_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            name = p.name.lower()
            hits += [f"{p.relative_to(ROOT)} (name): {t}" for t in terms if t in name]
            if p.suffix.lower() in TEXT_EXT:
                text = p.read_text(encoding="utf-8", errors="ignore").lower()
                hits += [f"{p.relative_to(ROOT)}: {t}" for t in terms if t in text]
    assert not hits, "denylisted terms found:\n" + "\n".join(hits)
