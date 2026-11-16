"""final/Heater_C_Final_Deck.pptx: exactly 5 slides, 16:9, action titles, one visual each, 'Synthetic data' watermark on slides 1-4, speaker notes.
No HMI or P&ID images are used (only figures generated from CSVs in final/figs)."""
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

from src.final_nums import numbers

ROOT = Path(__file__).resolve().parents[1]
FIN, FIGS = ROOT / "final", ROOT / "final" / "figs"
NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def build(D, L, notes):
    n = numbers(D, L)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    slides = [
        ("Heater C may burn avoidable fuel, but the company baseline still has to be validated", "f1_baseline.png",
         f"Synthetic baseline: median {n.sfc_med} kg fuel per GJ useful heat (P25-P75 {n.sfc_p25}-{n.sfc_p75}); only {n.elig} % of rows are clean enough for advice. Company baseline requires validation."),
        ("Start with a rule and a regression; let AI earn its place", "f2_options.png",
         "Choice: options 2 and 3 now, option 4 in shadow. Data: read-only historian export + lab LHV per lot. Runs offline; operators logged as role IDs only."),
        ("A linear model matched boosted trees, and the AI ranking was not clearly better than a rule", "f3_results.png",
         f"Held-out later lots. Linear {n.mae_L} vs boosted {n.mae_C0} kg/h; exact best move {n.ai_hit} % (AI) vs {n.rule_hit} % (rule); false alerts {n.ai_fa} % vs {n.rule_fa} %. Failure fixed: weak reference ({n.L_vs_P} % to {n.L_vs_P2} %)."),
        ("Operators stay in charge, and the AI's own energy use is negligible", "f4_energy.png",
         f"AI computing {n.kwh6_base} kWh over {n.weeks} weeks (OWN-ESTIMATE 60 W x measured time). Synthetic fuel-energy change is an illustration, not a saving. No CO2 claim."),
        ("Approve a six-week read-only pilot with a countable go/no-go and hard stops", "f5_timeline.png",
         f"GO = {n.n_targets} of {n.n_targets} targets met on measured data and 0 of {n.n_stops} stop conditions. Cost range (fictional): {n.one_opt}-{n.one_pess} million THB one-time. Owner: project sponsor."),
    ]
    for i, ((title, img, cap), note) in enumerate(zip(slides, notes), 1):
        s = prs.slides.add_slide(blank)
        tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(1.2))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.text = title
        tf.paragraphs[0].font.size, tf.paragraphs[0].font.bold = Pt(28), True
        tf.paragraphs[0].font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
        pic = s.shapes.add_picture(str(FIGS / img), Inches(0.9), Inches(1.7))
        scale = min(Inches(11.5) / pic.width, Inches(4.4) / pic.height)
        pic.width, pic.height = int(pic.width * scale), int(pic.height * scale)
        pic.left = int((prs.slide_width - pic.width) / 2)
        cb = s.shapes.add_textbox(Inches(0.6), Inches(6.2), Inches(12.1), Inches(0.8))
        cb.text_frame.word_wrap = True
        cb.text_frame.text = cap
        cb.text_frame.paragraphs[0].font.size = Pt(12)
        fb = s.shapes.add_textbox(Inches(0.6), Inches(7.05), Inches(12.1), Inches(0.3))
        fb.text_frame.text = f"Raja Chairmapandi · 69900089BG · PET Resin Plant P (anonymized) · {i}/5 · Synthetic data unless marked"
        fb.text_frame.paragraphs[0].font.size = Pt(9)
        fb.text_frame.paragraphs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)
        if i <= 4:
            wm = s.shapes.add_textbox(Inches(2.2), Inches(2.6), Inches(9), Inches(2))
            wm.name = "watermark Synthetic data"
            wm.rotation = -18
            wm.text_frame.text = "Synthetic data"
            r = wm.text_frame.paragraphs[0].runs[0]
            r.font.size, r.font.bold = Pt(80), True
            r.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            clr = r._r.find(f".//{{{NS}}}srgbClr")
            etree.SubElement(clr, f"{{{NS}}}alpha").set("val", "28000")
        s.notes_slide.notes_text_frame.text = note
    prs.save(str(FIN / "Heater_C_Final_Deck.pptx"))
