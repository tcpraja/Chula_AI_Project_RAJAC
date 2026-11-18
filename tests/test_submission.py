"""Final submission set (submission/Heater_C_Final_*): page/slide counts, six elements, rubric tags, consistency, no denylisted names. SYNTHETIC."""
import re
from pathlib import Path

import pandas as pd
import pytest
from pptx import Presentation
from pypdf import PdfReader

from src import sub_content as C
from src.sub_build import NAMES

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"
pytestmark = pytest.mark.skipif(not (SUB / NAMES["proposal"]).exists(), reason="run python -m src.sub_build first")


def pdf_text(name):
    return " ".join(p.extract_text() for p in PdfReader(SUB / name).pages)


def deck_text(prs):
    out = []
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                out += [c.text for r in sh.table.rows for c in r.cells]
    return " ".join(out)


def test_proposal_is_exactly_three_pages_with_six_elements():
    assert len(PdfReader(SUB / NAMES["proposal"]).pages) == 3
    t = pdf_text(NAMES["proposal"])
    for h in ("1 Management request", "2 Problem and baseline", "3 Options and choice", "4 Test results", "5 People and sustainability", "6 Trial plan"):
        assert h in t, h
    assert C.SID in t and C.STUDENT in t


def test_deck_has_exactly_five_slides_in_the_required_order_with_notes():
    prs = Presentation(SUB / NAMES["deck"])
    assert len(prs.slides) == 5
    tags = ["Problem & baseline", "Options, choice & data", "Test results", "People & oversight", "Request & trial plan"]
    for i, (s, tag) in enumerate(zip(prs.slides, tags), 1):
        txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
        assert f"{i}/5" in txt and tag in txt and "SYNTHETIC DATA" in txt
        assert len(s.notes_slide.notes_text_frame.text.split()) > 60


def test_script_fits_six_minutes():
    words = sum(len(x[3].split()) for x in C.script(__import__("src.sub_nums", fromlist=["build"]).build()))
    assert 600 <= words <= 950                       # 360 s at 100-160 words per minute
    assert [x[1] for x in C.script(__import__("src.sub_nums", fromlist=["build"]).build())] == [60, 75, 90, 60, 75]


def test_appendix_has_test_evidence_two_sources_and_ai_error():
    t = pdf_text(NAMES["appendix"])
    for k in ("A1 Test evidence", "A2 Two sources", "A3 One AI error", "ASME PTC 4", "arXiv:2107.07511", "Correction and verification"):
        assert k in t, k


def test_key_numbers_match_between_proposal_and_deck():
    from src.sub_nums import build
    N = build()
    p = re.sub(r"\s+", " ", pdf_text(NAMES["proposal"]))
    d = re.sub(r"\s+", " ", deck_text(Presentation(SUB / NAMES["deck"])))
    for v in (f"{N['ai_exact_pct']:.1f} %", f"{N['ai_fa_pct']:.1f} %", f"{N['rule_fa_pct']:.1f} %", f"{N['eligible_share_pct']:.1f} %", C.thb(N["pilot_cost_pess"])):
        assert v in p and v in d, v


def test_no_denylisted_names_in_new_deliverables():
    terms = [t.strip() for t in (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    prs = Presentation(SUB / NAMES["deck"])
    blob = pdf_text(NAMES["proposal"]) + pdf_text(NAMES["appendix"]) + pdf_text(NAMES["compliance"]) + pdf_text(NAMES["validation"]) + deck_text(prs) + " ".join(
        s.notes_slide.notes_text_frame.text for s in prs.slides)
    assert not [t for t in terms if re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", blob, re.I)]


def test_gap_register_has_24_checkpoints_and_only_allowed_statuses():
    from openpyxl import load_workbook
    ws = load_workbook(SUB / NAMES["register"])["Gap register"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    ids = [r[0] for r in rows]
    assert [f"CP{i:02d}" for i in range(1, 25)] == [i for i in ids if i.startswith("CP")]
    assert all(r[9] in C.STATUSES for r in rows)


def test_number_map_sources_exist():
    m = pd.read_csv(SUB / "number_source_map_final.csv")
    assert len(m) > 80 and m["evidence_label"].notna().all()
    for s in m["source"]:
        g = re.match(r"([\w./]+\.(?:csv|json|py|yaml))", str(s))
        assert g is None or (ROOT / g.group(1)).exists(), s
