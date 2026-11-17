"""Small toolkit for building the full-project presentation: slide layout helpers (with a text-fit estimator) and box-and-arrow diagrams.
Colours and fonts follow the corporate palette (blue 002E61, green 009933, red CC0033, greys), Arial; no company name or logo (CLAUDE.md rule 1).
"""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

BLUE, GREEN, RED = RGBColor(0x00, 0x2E, 0x61), RGBColor(0x00, 0x99, 0x33), RGBColor(0xCC, 0x00, 0x33)
G90, G60, G25, G10, WHITE = RGBColor(0x33, 0x33, 0x33), RGBColor(0x66, 0x66, 0x66), RGBColor(0xCC, 0xCC, 0xCC), RGBColor(0xF2, 0xF2, 0xF2), RGBColor(255, 255, 255)
HEX = {"blue": "#002E61", "green": "#009933", "red": "#CC0033", "g60": "#666666", "g25": "#CCCCCC", "g10": "#F2F2F2", "lblue": "#DCE6F2", "lgreen": "#E3F4E8", "lred": "#FBE3E8", "amber": "#FFF3CC"}
FONT = "Arial"
W, H = 13.333, 7.5


def est_lines(text, width_in, size_pt):
    cpl = max(8, int(width_in * 72 / (size_pt * 0.52)))
    return sum(max(1, math.ceil(len(p) / cpl)) for p in str(text).split("\n"))


class Deck:
    def __init__(self, total, footer):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.total, self.footer, self.n, self.warnings = total, footer, 0, []

    # ---------------------------------------------------------------- slide frame
    def slide(self, section, title, notes=""):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(0.14))
        bar.fill.solid()
        bar.fill.fore_color.rgb = BLUE
        bar.line.fill.background()
        acc = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(0.14), Inches(1.6), Inches(0.05))
        acc.fill.solid()
        acc.fill.fore_color.rgb = GREEN
        acc.line.fill.background()
        self.text(s, 0.55, 0.28, 9.5, 0.3, [section.upper()], 11, GREEN, bold=True, bullets=False)
        self.text(s, 0.55, 0.55, 12.2, 0.95, [title], 25 if len(title) < 70 else 22, BLUE, bold=True, bullets=False)
        if est_lines(title, 12.2, 25 if len(title) < 70 else 22) > 2:
            self.warnings.append(f"slide {self.n}: title may wrap to 3 lines")
        self.text(s, 0.55, 7.08, 12.2, 0.3, [f"{self.footer}  ·  {self.n}/{self.total}"], 9, G60, bullets=False)
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    # ---------------------------------------------------------------- text
    def text(self, s, x, y, w, h, paras, size=15, color=G90, bold=False, bullets=True, align=None, anchor=None, check=True):
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        if anchor:
            tf.vertical_anchor = anchor
        for i, p in enumerate(paras):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            sub = isinstance(p, tuple)                      # (text, level) for sub-bullets
            t, lvl = (p if sub else (p, 0))
            para.text = (("– " if lvl else "• ") if bullets else "") + t
            para.font.size, para.font.bold, para.font.name = Pt(size - (1 if lvl else 0)), bold, FONT
            para.font.color.rgb = color
            para.space_after = Pt(3)
            if lvl:
                para.level = 1
            if align:
                para.alignment = align
        if check:
            est = sum(est_lines(("– " if isinstance(p, tuple) else "• ") + (p[0] if isinstance(p, tuple) else p), w, size) for p in paras) * size * 1.27 / 72 + len(paras) * 0.045
            if est > h + 0.05:
                self.warnings.append(f"slide {self.n}: text box ~{est:.1f} in tall, room {h:.1f} in ('{str(paras[0])[:40]}')")
        return tb

    def callout(self, s, x, y, w, h, text, fill=G10, color=G90, size=13, bold=False, line=None):
        r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        r.adjustments[0] = 0.08
        r.fill.solid()
        r.fill.fore_color.rgb = fill
        if line is None:
            r.line.fill.background()
        else:
            r.line.color.rgb = line
            r.line.width = Pt(1)
        tf = r.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.12)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, t in enumerate(str(text).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = t
            p.font.size, p.font.bold, p.font.name = Pt(size), bold, FONT
            p.font.color.rgb = color
            p.alignment = PP_ALIGN.LEFT
        if est_lines(text, w - 0.3, size) * size * 1.27 / 72 > h:
            self.warnings.append(f"slide {self.n}: callout text may overflow ('{str(text)[:40]}')")
        return r

    def cards(self, s, items, y=1.75, h=3.6, cols=None, size=13):
        cols = cols or len(items)
        gap, w = 0.25, (12.2 - 0.25 * (cols - 1)) / cols
        body_h = h - 0.95
        best = 11
        for sz in range(18, 10, -1):                         # largest common font at which every card's body fits
            need = max(sum(est_lines("• " + t, w - 0.3, sz) for t in (body if isinstance(body, list) else [body])) * sz * 1.27 / 72
                       + len(body if isinstance(body, list) else [body]) * 0.045 for _, body in items)
            if need <= body_h:
                best = sz
                break
        size = best
        for i, (head, body) in enumerate(items):
            x = 0.55 + i * (w + gap)
            c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
            c.adjustments[0] = 0.05
            c.fill.solid()
            c.fill.fore_color.rgb = WHITE
            c.line.color.rgb = G25
            band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.09), Inches(h))
            band.fill.solid()
            band.fill.fore_color.rgb = [BLUE, GREEN, RED, G60][i % 4]
            band.line.fill.background()
            self.text(s, x + 0.2, y + 0.1, w - 0.3, 0.6, [head], size + 3, BLUE, bold=True, bullets=False)
            self.text(s, x + 0.2, y + 0.75, w - 0.3, h - 0.85, body if isinstance(body, list) else [body], size, G90)

    # ---------------------------------------------------------------- image
    def image(self, s, path, x, y, w, h, crop=None, border=True):
        p = Path(path)
        if crop:
            im = Image.open(p).convert("RGB").crop(crop)
            tmp = p.parent / "_deck_crops"
            tmp.mkdir(exist_ok=True)
            p = tmp / f"{p.stem}_{crop[0]}_{crop[1]}_{crop[2]}_{crop[3]}.png"
            im.save(p)
        iw, ih = Image.open(p).size
        sc = min(w / iw, h / ih)
        pw, ph = iw * sc, ih * sc
        pic = s.shapes.add_picture(str(p), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
        if border:
            pic.line.color.rgb = G25
            pic.line.width = Pt(0.75)
        return pic

    # ---------------------------------------------------------------- table
    def table(self, s, rows, x, y, w, col_w, size=11, row_h=0.34, max_h=5.2, head_fill=BLUE):
        nr, nc = len(rows), len(rows[0])
        tot = sum(col_w)
        widths = [w * c / tot for c in col_w]
        est = 0.0
        for r in rows:
            est += max(max(est_lines(c, widths[j] - 0.2, size) for j, c in enumerate(r)) * size * 1.25 / 72 + 0.12, row_h)
        if est > max_h:
            self.warnings.append(f"slide {self.n}: table ~{est:.1f} in tall, room {max_h:.1f} in")
        shape = s.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
        t = shape.table
        for j, cw in enumerate(widths):
            t.columns[j].width = Inches(cw)
        for i, r in enumerate(rows):
            t.rows[i].height = Inches(row_h)
            for j, val in enumerate(r):
                c = t.cell(i, j)
                c.text = str(val)
                c.margin_left = c.margin_right = Inches(0.07)
                c.margin_top = c.margin_bottom = Inches(0.03)
                c.vertical_anchor = MSO_ANCHOR.MIDDLE
                for p in c.text_frame.paragraphs:
                    p.font.size, p.font.name = Pt(size), FONT
                    p.font.bold = i == 0
                    p.font.color.rgb = WHITE if i == 0 else G90
                c.fill.solid()
                c.fill.fore_color.rgb = head_fill if i == 0 else (WHITE if i % 2 else G10)
        return shape

    def save(self, path):
        self.prs.save(str(path))


# ---------------------------------------------------------------------- diagrams
def diagram(path, nodes, edges, size=(11, 3.6), dpi=170, title=None, notes=None, fs=11):
    """nodes: {key: (x, y, w, h, label, colour)} in a 0..100 x 0..100 box; edges: [(a, b, label)]."""
    fig, ax = plt.subplots(figsize=size)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    for k, (x, y, w, h, label, col) in nodes.items():
        face = HEX.get(col, col)
        txt = "white" if col in ("blue", "green", "red", "g60") else "#222222"
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6", fc=face, ec="#9aa7b8" if txt != "white" else face, lw=1))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=fs, color=txt, wrap=True, linespacing=1.15)
    for a, b, lab in edges:
        xa, ya, wa, ha_, *_ = nodes[a]
        xb, yb, wb, hb, *_ = nodes[b]
        ca, cb = (xa + wa / 2, ya + ha_ / 2), (xb + wb / 2, yb + hb / 2)
        if abs(cb[0] - ca[0]) >= abs(cb[1] - ca[1]):
            p0 = (xa + wa if cb[0] > ca[0] else xa, ca[1])
            p1 = (xb if cb[0] > ca[0] else xb + wb, cb[1])
        else:
            p0 = (ca[0], ya + ha_ if cb[1] > ca[1] else ya)
            p1 = (cb[0], yb if cb[1] > ca[1] else yb + hb)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13, color="#555555", lw=1.4, shrinkA=1, shrinkB=1))
        if lab:
            ax.text((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + 3, lab, ha="center", va="bottom", fontsize=fs - 2, color="#555555")
    if title:
        ax.text(1, 98, title, fontsize=10, color="#002E61", fontweight="bold", va="top")
    if notes:
        ax.text(1, 1, notes, fontsize=fs - 1.5, color="#666666", va="bottom")
    fig.tight_layout(pad=0.3)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
