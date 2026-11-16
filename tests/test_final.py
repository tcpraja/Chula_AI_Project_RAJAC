"""Phase 7 checks on final/: page counts, slide count and notes, denylist over PDF/PPTX text, no HMI/P&ID images, rubric totals. SYNTHETIC."""
import hashlib
import re
from pathlib import Path

import pandas as pd
import pytest
from pptx import Presentation
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
FIN = ROOT / "final"
words = lambda t: len(re.findall(r"\S+", t))


def pdf_text(name):
    return "\n".join(p.extract_text() for p in PdfReader(FIN / name).pages)


def test_proposal_at_most_three_pages_with_required_content():
    r = PdfReader(FIN / "Heater_C_Final_Proposal.pdf")
    assert 1 <= len(r.pages) <= 3
    t = re.sub(r"\s+", " ", pdf_text("Heater_C_Final_Proposal.pdf"))
    spec = re.sub(r"\s+", " ", (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8"))
    name, ident = re.search(r"individual\. ([^,]+), (\w+)\. Due", spec).groups()
    for must in (name, ident, "2130511 AI Abstraction and Digital Technologies", "PET Resin Plant P (anonymized)", "requires validation", "1 Request", "2 Problem and baseline",
                 "3 Options and choice", "4 Test results", "5 People and sustainability", "6 Trial plan", "Failure and fix", "kWh", "STOP", "SYNTHETIC"):
        assert must in t, must
    for stop in ("any safety/OT incident linked to pilot", "approval withdrawn/unavailable"):
        assert stop in t


def test_appendix_has_screenshots_tests_sources_error_and_method():
    r = PdfReader(FIN / "Appendix.pdf")
    t = pdf_text("Appendix.pdf")
    assert sum(len(p.images) for p in r.pages) >= 6
    for must in ("A2 Test evidence", "A3 Two sources", "A4 One AI error", "Energy boundary", "formulas", "ASME PTC 4", "arXiv:2107.07511"):
        assert must in t, must


def test_deck_five_slides_16_9_notes_watermark_one_visual_each():
    p = Presentation(FIN / "Heater_C_Final_Deck.pptx")
    assert len(p.slides) == 5
    assert abs(p.slide_width / p.slide_height - 16 / 9) < 0.01
    fig_hashes = {hashlib.sha256(f.read_bytes()).hexdigest() for f in (FIN / "figs").glob("*.png")}
    banned = {hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("HMI_1.jpg", "HMI_2.png") if (ROOT / f).exists()}
    for i, s in enumerate(p.slides, 1):
        pics = [sh for sh in s.shapes if sh.shape_type == 13]
        assert len(pics) == 1, f"slide {i} must have exactly one visual"
        h = hashlib.sha256(pics[0].image.blob).hexdigest()
        assert h in fig_hashes and h not in banned
        assert 150 <= words(s.notes_slide.notes_text_frame.text) <= 170, f"slide {i} notes words"
        wm = [sh for sh in s.shapes if "watermark" in sh.name.lower()]
        assert (len(wm) == 1 and wm[0].text_frame.text == "Synthetic data") if i <= 4 else not wm
        title = s.shapes[0].text_frame.text
        assert words(title) >= 6 and not title.endswith(":")
        assert all(sh.left >= 0 and sh.top >= 0 and sh.left + sh.width <= p.slide_width and sh.top + sh.height <= p.slide_height + 1 for sh in pics)


def test_no_denylisted_terms_in_pdf_pptx_and_filenames():
    terms = [t.strip() for t in (ROOT / "config" / "denylist.txt").read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    pats = [re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I) for t in terms]
    text = pdf_text("Heater_C_Final_Proposal.pdf") + pdf_text("Appendix.pdf")
    for s in Presentation(FIN / "Heater_C_Final_Deck.pptx").slides:
        text += " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) + s.notes_slide.notes_text_frame.text
    assert pats and not [rx.pattern for rx in pats if rx.search(text)]
    assert not [f.name for f in FIN.rglob("*") if any(rx.search(f.name) for rx in pats)]


def test_number_source_map_points_to_existing_files():
    m = pd.read_csv(FIN / "number_source_map.csv")
    assert len(m) > 60 and m["source"].notna().all()
    for src in m["source"]:
        path = re.match(r"(?:computed from )?([\w./]+\.(?:csv|md|json))", src)
        assert path is None or (ROOT / path.group(1)).exists(), src
    assert {"reports/model_comparison.csv", "reports/scenario_comparison.csv", "reports/economics_summary.csv", "reports/final_numbers.csv"} <= {
        re.match(r"(?:computed from )?([\w./]+\.csv)", s).group(1) for s in m["source"] if re.match(r"(?:computed from )?([\w./]+\.csv)", s)}


def test_panel_qa_ten_questions_and_topics():
    t = (FIN / "panel_QA.md").read_text(encoding="utf-8")
    qs = re.findall(r"^## Q\d+\. (.+)$", t, re.M)
    assert len(qs) == 10
    for topic in ("Safety", "Data truth", "Measurement", "Synthetic bias", "Simplicity", "O2/CO", "Incremental ML", "Estimates", "Cost", "environmental"):
        assert any(topic.lower() in q.lower() for q in qs), topic


def test_rubric_scores_sum_to_100_and_fixes_two_weakest():
    t = (FIN / "rubric_checklist.md").read_text(encoding="utf-8")
    rows = [r for r in re.findall(r"^\| ([^|]+) \| (\d+) \| (\d+) \| (\d+) \|", t, re.M)]
    assert sum(int(r[1]) for r in rows) == 100 and len(rows) == 9
    assert all(int(r[3]) <= int(r[1]) and int(r[3]) >= int(r[2]) for r in rows)
    assert sum(1 for r in rows if int(r[3]) > int(r[2])) == 2
    assert "(FIX" in t


def test_speaker_notes_and_error_log_exist():
    sn = (FIN / "6_min_speaker_notes.md").read_text(encoding="utf-8")
    assert sn.count("## Slide ") == 5 and "Cue cards" in sn
    log = (FIN / "source_and_AI_error_log.md").read_text(encoding="utf-8")
    assert "ASME PTC 4" in log and "AI errors found and corrected" in log and "Unfair reference" in log
