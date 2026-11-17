"""reports/Heater_C_Full_Project_Presentation.pptx: 50 slides, 16:9, notes, footer, visuals, no HMI/P&ID images, no denylisted names, sourced numbers. SYNTHETIC."""
import hashlib
import importlib.metadata as md
import re
from pathlib import Path

import pandas as pd
import pytest
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "reports" / "Heater_C_Full_Project_Presentation.pptx"


@pytest.fixture(scope="module")
def prs():
    return Presentation(DECK)


def text_of(slide):
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            out += [c.text for r in sh.table.rows for c in r.cells]
    return " ".join(out)


def test_fifty_slides_in_16_9_with_notes_and_footer(prs):
    assert len(prs.slides) == 50
    assert abs(prs.slide_width / prs.slide_height - 16 / 9) < 0.01
    for i, s in enumerate(prs.slides, 1):
        assert s.has_notes_slide and len(s.notes_slide.notes_text_frame.text.split()) >= 8, f"slide {i} notes"
        t = text_of(s)
        assert f"{i}/50" in t and "SYNTHETIC DATA" in t and "PET Resin Plant P (anonymized)" in t, f"slide {i} footer"


def test_every_slide_has_a_visual_element_and_a_real_title(prs):
    for i, s in enumerate(prs.slides, 1):
        kinds = {sh.shape_type for sh in s.shapes}
        has_visual = 13 in kinds or any(getattr(sh, "has_table", False) and sh.has_table for sh in s.shapes) or sum(1 for sh in s.shapes if sh.shape_type == 1) >= 4
        assert has_visual, f"slide {i} has no picture, table or card layout"
        title = next(sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text and sh.top > 0.4 * 914400 and sh.top < 0.7 * 914400)
        assert len(title.split()) >= 5, (i, title)


def test_no_hmi_or_pid_images_and_no_denylisted_names(prs):
    banned = {hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("HMI_1.jpg", "HMI_2.png") if (ROOT / f).exists()}
    terms = [t.strip() for t in (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    pats = [re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I) for t in terms]
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if sh.shape_type == 13:
                assert hashlib.sha256(sh.image.blob).hexdigest() not in banned, f"slide {i}"
        blob = text_of(s) + " " + s.notes_slide.notes_text_frame.text
        assert not [p.pattern for p in pats if p.search(blob)], f"slide {i}"


def test_deck_covers_the_requested_topics(prs):
    allt = " ".join(text_of(s) for s in prs.slides)
    for must in ("Tools used (1 of 2)", "Tools used (2 of 2)", "AI concepts used", "How to start the dashboard", "Inputs: every control", "run_dashboard.ps1", "http://localhost:8501",
                 "Conformal", "Combustion chemistry", "Optimize (1 of 2)", "Pilot package", "REVISE", "Stop:", "requires validation".lower()):
        assert must.lower() in allt.lower(), must
    for pkg in ("streamlit", "scikit-learn", "pandas"):
        assert md.version(pkg) in allt, pkg                                                  # versions come from the environment, not typed


def test_numbers_are_logged_with_existing_sources():
    m = pd.read_csv(ROOT / "reports" / "project_deck_number_map.csv")
    assert len(m) > 100 and m["source"].notna().all()
    for src in m["source"]:
        path = re.match(r"(?:computed from )?([\w./]+\.(?:csv|md|json|yaml|py))", str(src))
        assert path is None or (ROOT / path.group(1)).exists(), src


def test_pdf_copy_has_the_same_number_of_pages_when_present():
    pdf = ROOT / "reports" / "Heater_C_Full_Project_Presentation.pdf"
    if not pdf.exists():
        pytest.skip("PDF export needs PowerPoint; not present")
    from pypdf import PdfReader
    assert len(PdfReader(pdf).pages) == 50
