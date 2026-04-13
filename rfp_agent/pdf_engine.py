"""
PDF Engine — parse a company template PDF to extract branding, then generate
a fully styled RFP PDF using reportlab.

Fixes applied vs previous version:
  - Functional TOC with dot-leaders (two-pass multiBuild)
  - Table cells wrapped in Paragraph → automatic word-wrap, no overflow
  - Column widths distributed by content-length ratio, min 8 % per column
  - Cover page fully drawn on canvas (title, date, decorative band)
  - Proper section spacing — headings keep with next paragraph
  - Blank lines produce a meaningful spacer, not a 4 pt stub
"""

import os
import re
import io
from datetime import date
from pathlib import Path

import fitz          # PyMuPDF
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfgen_canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable,
    KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

PAGE_W, PAGE_H = A4          # 595.27 × 841.89 pt
MARGIN_L = 2.2 * cm
MARGIN_R = 2.2 * cm
MARGIN_T = 3.6 * cm          # space for running header
MARGIN_B = 2.2 * cm
USABLE_W = PAGE_W - MARGIN_L - MARGIN_R

DEFAULT_PRIMARY   = (10,  60, 120)
DEFAULT_SECONDARY = (240, 245, 250)
DEFAULT_ACCENT    = (220, 100,   0)


# ─────────────────────────────────────────────────────────────────────────────
# Template parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_template(pdf_path: str) -> dict:
    """Extract brand colours, logo, company name from the first page of a PDF."""
    info = {
        "primary":      DEFAULT_PRIMARY,
        "secondary":    DEFAULT_SECONDARY,
        "accent":       DEFAULT_ACCENT,
        "logo_path":    None,
        "company_name": "",
    }
    try:
        doc  = fitz.open(pdf_path)
        page = doc[0]

        found = []
        for d in page.get_drawings():
            fill = d.get("fill")
            if fill and len(fill) >= 3:
                r, g, b = int(fill[0]*255), int(fill[1]*255), int(fill[2]*255)
                if not (r > 230 and g > 230 and b > 230) and \
                   not (r <  20 and g <  20 and b <  20):
                    found.append((r, g, b))
        if found:
            info["primary"] = found[0]
            if len(found) > 1:
                info["secondary"] = found[1]

        images = page.get_images(full=True)
        if images:
            xref     = images[0][0]
            base_img = doc.extract_image(xref)
            logo_path = str(Path(pdf_path).with_suffix("")) + "_logo.png"
            pil = PILImage.open(io.BytesIO(base_img["image"])).convert("RGBA")
            bbox = pil.getbbox()
            if bbox:
                pil = pil.crop(bbox)
            pil.save(logo_path, "PNG")
            info["logo_path"] = logo_path

        best = ("", 0)
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t, s = span.get("text", "").strip(), span.get("size", 0)
                    if len(t) > 3 and s > best[1]:
                        best = (t, s)
        info["company_name"] = best[0]
        doc.close()
    except Exception:
        pass
    return info


# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rl(rgb):
    return colors.Color(rgb[0]/255, rgb[1]/255, rgb[2]/255)

def _lighten(rgb, f=0.85):
    return tuple(int(c + (255-c)*f) for c in rgb)


# ─────────────────────────────────────────────────────────────────────────────
# Page callback — header, footer, and cover artwork
# ─────────────────────────────────────────────────────────────────────────────

def _make_page_cb(tmpl: dict, title: str):
    primary   = _rl(tmpl["primary"])
    accent    = _rl(tmpl["accent"])
    logo      = tmpl.get("logo_path")
    company   = tmpl.get("company_name", "")
    today_str = date.today().strftime("%B %d, %Y")

    def _draw(canv: pdfgen_canvas.Canvas, doc):
        canv.saveState()
        w, h = PAGE_W, PAGE_H

        if doc.page == 1:
            # ── Full cover ────────────────────────────────────────────────
            # Top band
            canv.setFillColor(primary)
            canv.rect(0, h - 100, w, 100, fill=1, stroke=0)

            # Logo in band
            if logo and os.path.exists(logo):
                try:
                    canv.drawImage(ImageReader(logo),
                                   x=28, y=h - 88,
                                   width=130, height=62,
                                   preserveAspectRatio=True, mask="auto")
                except Exception:
                    pass

            # Company name top-right
            canv.setFont("Helvetica-Bold", 13)
            canv.setFillColor(colors.white)
            canv.drawRightString(w - 28, h - 42, company or "")
            canv.setFont("Helvetica", 9)
            canv.drawRightString(w - 28, h - 60, "Request for Proposal")

            # Mid-page decorative band
            band_y = h * 0.42
            canv.setFillColor(primary)
            canv.rect(0, band_y, w, 6, fill=1, stroke=0)
            canv.setFillColor(_rl(tmpl["accent"]))
            canv.rect(0, band_y - 6, w, 6, fill=1, stroke=0)

            # Document title — centred above the band
            canv.setFont("Helvetica-Bold", 28)
            canv.setFillColor(primary)
            _draw_centered_text(canv, title.replace("_", " ").replace(".pdf", ""),
                                 w, band_y + 50, max_w=w - 80)

            # Subtitle
            canv.setFont("Helvetica", 13)
            canv.setFillColor(_rl(tmpl["accent"]))
            _draw_centered_text(canv, "Request for Proposal", w, band_y + 22)

            # Date box below band
            box_x, box_y = 28, band_y - 60
            canv.setStrokeColor(primary)
            canv.setFillColor(_rl(_lighten(tmpl["primary"], 0.92)))
            canv.roundRect(box_x, box_y, 200, 36, 4, fill=1, stroke=1)
            canv.setFont("Helvetica", 8)
            canv.setFillColor(_rl(tmpl["primary"]))
            canv.drawString(box_x + 10, box_y + 22, "DATE ISSUED")
            canv.setFont("Helvetica-Bold", 11)
            canv.drawString(box_x + 10, box_y + 8, today_str)

            # Bottom accent bar
            canv.setFillColor(accent)
            canv.rect(0, 0, w, 14, fill=1, stroke=0)
            canv.setFont("Helvetica", 7)
            canv.setFillColor(colors.white)
            canv.drawCentredString(w/2, 4, "CONFIDENTIAL — FOR AUTHORISED RECIPIENTS ONLY")

        else:
            # ── Running header ────────────────────────────────────────────
            canv.setFillColor(primary)
            canv.rect(0, h - 32, w, 32, fill=1, stroke=0)

            if logo and os.path.exists(logo):
                try:
                    canv.drawImage(ImageReader(logo),
                                   x=18, y=h - 28,
                                   width=64, height=24,
                                   preserveAspectRatio=True, mask="auto")
                except Exception:
                    pass

            canv.setFont("Helvetica-Bold", 9)
            canv.setFillColor(colors.white)
            canv.drawRightString(w - 18, h - 21, title.replace("_", " ").replace(".pdf",""))

            # ── Running footer ────────────────────────────────────────────
            canv.setFillColor(primary)
            canv.rect(0, 0, w, 22, fill=1, stroke=0)
            canv.setFont("Helvetica", 8)
            canv.setFillColor(colors.white)
            canv.drawString(18, 7, company or "Confidential")
            canv.drawRightString(w - 18, 7, f"Page {doc.page}")

        canv.restoreState()

    return _draw


def _draw_centered_text(canv, text, page_w, y, max_w=None):
    """Draw text centred on the page, shrinking font if too wide."""
    if max_w and canv.stringWidth(text) > max_w:
        # Truncate with ellipsis — simple approach for very long titles
        while canv.stringWidth(text + "…") > max_w and len(text) > 10:
            text = text[:-1]
        text += "…"
    canv.drawCentredString(page_w / 2, y, text)


# ─────────────────────────────────────────────────────────────────────────────
# Two-pass document template (required for functional TOC)
# ─────────────────────────────────────────────────────────────────────────────

class _RFPDoc(BaseDocTemplate):
    """BaseDocTemplate subclass that registers headings for TOC on each pass."""

    def __init__(self, filename, page_cb, **kw):
        super().__init__(filename, **kw)
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id="content", showBoundary=0,
        )
        self.addPageTemplates([
            PageTemplate(id="All", frames=[frame], onPage=page_cb)
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            sn   = flowable.style.name
            text = flowable.getPlainText()
            if sn == "RFP_H1":
                self.notify("TOCEntry", (0, text, self.page))
            elif sn == "RFP_H2":
                self.notify("TOCEntry", (1, text, self.page))


# ─────────────────────────────────────────────────────────────────────────────
# Style sheet
# ─────────────────────────────────────────────────────────────────────────────

def _make_styles(tmpl: dict) -> dict:
    primary = _rl(tmpl["primary"])
    accent  = _rl(tmpl["accent"])
    base    = getSampleStyleSheet()

    return {
        "h1": ParagraphStyle("RFP_H1", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=15, textColor=primary,
            spaceBefore=18, spaceAfter=4, leading=20, keepWithNext=1),

        "h2": ParagraphStyle("RFP_H2", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=12, textColor=primary,
            spaceBefore=14, spaceAfter=3, leading=16, keepWithNext=1),

        "h3": ParagraphStyle("RFP_H3", parent=base["Normal"],
            fontName="Helvetica-BoldOblique", fontSize=10, textColor=accent,
            spaceBefore=10, spaceAfter=2, leading=14, keepWithNext=1),

        "body": ParagraphStyle("RFP_Body", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=15,
            spaceAfter=6, alignment=TA_JUSTIFY),

        "bullet": ParagraphStyle("RFP_Bullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14,
            leftIndent=20, firstLineIndent=0, spaceAfter=3,
            alignment=TA_JUSTIFY),

        "bold_body": ParagraphStyle("RFP_Bold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=10, leading=15,
            spaceAfter=6, alignment=TA_JUSTIFY),

        "toc1": ParagraphStyle("TOC1", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=11, leading=22,
            leftIndent=0, textColor=primary),

        "toc2": ParagraphStyle("TOC2", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=20,
            leftIndent=18, textColor=colors.black),

        "toc_title": ParagraphStyle("TOC_Title", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=16, textColor=primary,
            spaceBefore=0, spaceAfter=10, alignment=TA_LEFT),

        "cell": ParagraphStyle("TblCell", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=13,
            wordWrap="CJK"),

        "cell_hdr": ParagraphStyle("TblHdr", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9, leading=13,
            textColor=colors.white, wordWrap="CJK"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → story
# ─────────────────────────────────────────────────────────────────────────────

def _inline(text: str) -> str:
    """Convert inline markdown to ReportLab XML."""
    # Escape bare & that aren't already entities
    text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|bull|nbsp);)", "&amp;", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`",       r"<font name='Courier'>\1</font>", text)
    return text


def _parse_table(lines: list, start: int):
    """Parse a markdown table. Returns (rows_as_strings, next_line_index)."""
    rows, i = [], start
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            break
        if re.match(r"^\|[-| :]+\|$", line):
            i += 1
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
        i += 1
    return rows, i


def _smart_col_widths(rows: list, available: float) -> list:
    """Distribute column widths proportionally by content length, min 8 %."""
    n = max(len(r) for r in rows)
    lens = [0] * n
    for row in rows:
        for j, cell in enumerate(row[:n]):
            lens[j] = max(lens[j], len(str(cell)))
    total = sum(lens) or n
    min_w = available * 0.08
    raw   = [max(min_w, (l / total) * available) for l in lens]
    scale = available / sum(raw)
    return [w * scale for w in raw]


def _build_story(content: str, tmpl: dict) -> list:
    s     = _make_styles(tmpl)
    pri   = _rl(tmpl["primary"])
    acc   = _rl(tmpl["accent"])
    sec   = _rl(_lighten(tmpl["primary"], 0.92))

    # ── Table of contents ──────────────────────────────────────────────────
    toc = TableOfContents()
    toc.levelStyles  = [s["toc1"], s["toc2"]]
    toc.dotsMinLevel = 0       # dot leaders at every level

    story = []

    # Cover page: the canvas callback draws all artwork on page 1.
    # A single PageBreak is enough — no spacer needed (and a full-frame spacer
    # would trigger "Flowable too large on page" in ReportLab).
    story.append(PageBreak())

    # TOC page
    story.append(Paragraph("Table of Contents", s["toc_title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=pri, spaceAfter=10))
    story.append(toc)
    story.append(PageBreak())

    # ── Parse markdown ─────────────────────────────────────────────────────
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        raw  = lines[i]
        line = raw.strip()

        # blank line → meaningful vertical gap
        if not line:
            story.append(Spacer(1, 8))
            i += 1
            continue

        # H1
        if line.startswith("# "):
            text = line[2:].strip()
            block = [
                Paragraph(text, s["h1"]),
                HRFlowable(width="100%", thickness=2, color=pri, spaceAfter=6),
            ]
            story.append(KeepTogether(block))
            i += 1
            continue

        # H2
        if line.startswith("## "):
            text = line[3:].strip()
            block = [
                Paragraph(text, s["h2"]),
                HRFlowable(width="60%", thickness=1, color=acc, spaceAfter=4),
            ]
            story.append(KeepTogether(block))
            i += 1
            continue

        # H3
        if line.startswith("### "):
            story.append(Paragraph(line[4:].strip(), s["h3"]))
            i += 1
            continue

        # Explicit page break (---)
        if re.match(r"^-{3,}$", line):
            story.append(PageBreak())
            i += 1
            continue

        # Markdown table
        if line.startswith("|"):
            rows, i = _parse_table(lines, i)
            if rows:
                col_n = max(len(r) for r in rows)
                rows  = [r + [""] * (col_n - len(r)) for r in rows]
                widths = _smart_col_widths(rows, USABLE_W)

                # Cap cell text so no single cell can exceed one page height.
                # ~600 chars at 9pt ≈ 40 lines ≈ safe upper bound per cell.
                MAX_CELL = 600
                capped_rows = []
                for row in rows:
                    capped_rows.append([
                        (str(c)[:MAX_CELL] + "…" if len(str(c)) > MAX_CELL else str(c))
                        for c in row
                    ])

                # Wrap every cell in a Paragraph for automatic word-wrap
                para_rows = []
                for ridx, row in enumerate(capped_rows):
                    st = s["cell_hdr"] if ridx == 0 else s["cell"]
                    para_rows.append([
                        Paragraph(_inline(cell), st)
                        for cell in row
                    ])

                # splitByRow=True (default) lets the table break across pages;
                # repeatRows=1 repeats the header row on continuation pages.
                tbl = Table(para_rows, colWidths=widths, repeatRows=1,
                            hAlign="LEFT", splitByRow=True)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1,  0), pri),
                    ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, sec]),
                    ("GRID",          (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ]))
                story.append(Spacer(1, 8))
                story.append(tbl)
                story.append(Spacer(1, 10))
            continue

        # Bullet
        if line.startswith(("- ", "• ", "* ")):
            story.append(Paragraph(f"• &nbsp; {_inline(line[2:])}", s["bullet"]))
            i += 1
            continue

        # Numbered list
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            story.append(
                Paragraph(f"<b>{m.group(1)}.</b> &nbsp; {_inline(m.group(2))}", s["bullet"])
            )
            i += 1
            continue

        # Stand-alone **bold** line
        if line.startswith("**") and line.endswith("**") and len(line) > 4:
            story.append(Paragraph(_inline(line), s["bold_body"]))
            i += 1
            continue

        # Normal body text
        story.append(Paragraph(_inline(line), s["body"]))
        i += 1

    return story


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_rfp_pdf(
    content: str,
    template_info: dict,
    output_path: str,
    title: str = "Request for Proposal",
) -> str:
    """
    Build a styled, TOC-equipped PDF from RFP markdown and extracted branding.
    Returns output_path on success.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    page_cb = _make_page_cb(template_info, title)

    doc = _RFPDoc(
        output_path,
        page_cb,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title=title,
        author=template_info.get("company_name", ""),
    )

    story = _build_story(content, template_info)

    # multiBuild does two passes: first pass collects page numbers for headings,
    # second pass renders the TOC with correct page references.
    try:
        doc.multiBuild(story)
    except Exception as first_err:
        # Fallback: rebuild without KeepTogether blocks and without TOC.
        # This handles "Flowable too large on page" on edge-case content.
        import logging
        logging.getLogger(__name__).warning(
            "multiBuild failed (%s) — retrying with simplified layout.", first_err
        )
        story2 = _build_story_simple(content, template_info)
        doc2 = _RFPDoc(
            output_path,
            page_cb,
            pagesize=A4,
            leftMargin=MARGIN_L,
            rightMargin=MARGIN_R,
            topMargin=MARGIN_T,
            bottomMargin=MARGIN_B,
            title=title,
            author=template_info.get("company_name", ""),
        )
        doc2.multiBuild(story2)

    return output_path


def _build_story_simple(content: str, tmpl: dict) -> list:
    """
    Minimal fallback story builder — no TOC, no KeepTogether, no tables.
    Renders every line as plain paragraphs so the PDF always succeeds.
    """
    s   = _make_styles(tmpl)
    pri = _rl(tmpl["primary"])

    story = [PageBreak()]   # cover page

    for raw in content.split("\n"):
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), s["h1"]))
            story.append(HRFlowable(width="100%", thickness=2, color=pri, spaceAfter=4))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), s["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:].strip(), s["h3"]))
        elif re.match(r"^-{3,}$", line):
            story.append(PageBreak())
        elif line.startswith("|"):
            # Render table rows as plain bullet lines instead of a Table flowable
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
            if cells and not re.match(r"^[-: ]+$", cells[0]):
                story.append(Paragraph("  |  ".join(_inline(c) for c in cells), s["bullet"]))
        elif line.startswith(("- ", "• ", "* ")):
            story.append(Paragraph(f"• &nbsp; {_inline(line[2:])}", s["bullet"]))
        elif re.match(r"^(\d+)\.\s+(.*)", line):
            m = re.match(r"^(\d+)\.\s+(.*)", line)
            story.append(Paragraph(f"<b>{m.group(1)}.</b> &nbsp; {_inline(m.group(2))}", s["bullet"]))
        else:
            story.append(Paragraph(_inline(line), s["body"]))

    return story
