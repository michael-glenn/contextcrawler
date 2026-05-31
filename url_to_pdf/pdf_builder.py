"""Book-like PDF generation with reportlab."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from .extractor import Page

# ---------------------------------------------------------------------------
# Colours & fonts
# ---------------------------------------------------------------------------

BODY_FONT = "Times-Roman"
BOLD_FONT = "Times-Bold"
HEADING_COLOR = colors.HexColor("#1a1a2e")
ACCENT_COLOR = colors.HexColor("#16213e")
RULE_COLOR = colors.HexColor("#cccccc")

PAGE_W, PAGE_H = A4
MARGIN = 2.5 * cm

# ---------------------------------------------------------------------------
# Custom DocTemplate with page numbers and running headers
# ---------------------------------------------------------------------------


class BookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, title: str, **kwargs):
        super().__init__(filename, **kwargs)
        self.book_title = title
        self.current_chapter = ""
        self._toc_entries: list[tuple[int, str, int]] = []

        # Page frames
        body_frame = Frame(
            MARGIN, MARGIN + 1.2 * cm,
            PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN - 2.4 * cm,
            id="body",
        )
        cover_frame = Frame(
            MARGIN, MARGIN,
            PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
            id="cover",
        )

        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover_frame]),
            PageTemplate(
                id="Body",
                frames=[body_frame],
                onPage=self._draw_header_footer,
            ),
        ])

    def _draw_header_footer(self, canvas, doc):
        canvas.saveState()
        # Header rule
        canvas.setStrokeColor(RULE_COLOR)
        canvas.setLineWidth(0.5)
        y_header = PAGE_H - MARGIN + 0.3 * cm
        canvas.line(MARGIN, y_header, PAGE_W - MARGIN, y_header)

        # Running title (left) and chapter (right)
        canvas.setFont(BODY_FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(MARGIN, y_header + 0.15 * cm, self.book_title[:60])
        chap = self.current_chapter[:50]
        canvas.drawRightString(PAGE_W - MARGIN, y_header + 0.15 * cm, chap)

        # Footer rule
        y_footer = MARGIN - 0.5 * cm
        canvas.line(MARGIN, y_footer, PAGE_W - MARGIN, y_footer)

        # Page number
        canvas.setFont(BODY_FONT, 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(PAGE_W / 2, y_footer - 0.3 * cm, str(doc.page))

        canvas.restoreState()

    def afterFlowable(self, flowable):
        """Capture headings for TOC and update running chapter."""
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name == "ChapterTitle":
                text = _strip_tags(flowable.getPlainText())
                self.current_chapter = text
                self.notify("TOCEntry", (0, text, self.page))
            elif style_name == "SectionHeading":
                text = _strip_tags(flowable.getPlainText())
                self.notify("TOCEntry", (1, text, self.page))


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


# ---------------------------------------------------------------------------
# Style sheet
# ---------------------------------------------------------------------------


def _build_styles() -> dict:
    base = getSampleStyleSheet()

    styles = {}

    styles["CoverTitle"] = ParagraphStyle(
        "CoverTitle",
        fontName=BOLD_FONT,
        fontSize=28,
        leading=34,
        textColor=HEADING_COLOR,
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    styles["CoverSubtitle"] = ParagraphStyle(
        "CoverSubtitle",
        fontName=BODY_FONT,
        fontSize=13,
        leading=18,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    styles["ChapterTitle"] = ParagraphStyle(
        "ChapterTitle",
        fontName=BOLD_FONT,
        fontSize=18,
        leading=24,
        textColor=HEADING_COLOR,
        spaceBefore=6,
        spaceAfter=10,
        keepWithNext=True,
    )
    styles["SectionHeading"] = ParagraphStyle(
        "SectionHeading",
        fontName=BOLD_FONT,
        fontSize=12,
        leading=16,
        textColor=ACCENT_COLOR,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    styles["BodyText"] = ParagraphStyle(
        "BodyText",
        fontName=BODY_FONT,
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    styles["URLStyle"] = ParagraphStyle(
        "URLStyle",
        fontName="Courier",
        fontSize=8,
        leading=12,
        textColor=colors.grey,
        spaceAfter=12,
    )
    styles["TOCHeading"] = ParagraphStyle(
        "TOCHeading",
        fontName=BOLD_FONT,
        fontSize=16,
        leading=22,
        textColor=HEADING_COLOR,
        spaceAfter=14,
        spaceBefore=4,
    )
    styles["TOCEntry0"] = ParagraphStyle(
        "TOCEntry0",
        fontName=BOLD_FONT,
        fontSize=11,
        leading=16,
        leftIndent=0,
        spaceAfter=3,
    )
    styles["TOCEntry1"] = ParagraphStyle(
        "TOCEntry1",
        fontName=BODY_FONT,
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=2,
    )

    return styles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_pdf(pages: list[Page], output_path: str, start_url: str) -> None:
    """Render *pages* into a book-like PDF at *output_path*."""

    styles = _build_styles()

    # Derive a human title from the first page
    book_title = pages[0].title if pages else start_url

    doc = BookDocTemplate(
        output_path,
        title=book_title,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 1.2 * cm,
        bottomMargin=MARGIN + 1.2 * cm,
    )

    story: list = []

    # ------------------------------------------------------------------
    # Cover page
    # ------------------------------------------------------------------
    story.append(NextPageTemplate("Cover"))
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph(_esc(book_title), styles["CoverTitle"]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(_esc(start_url), styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(f"Generated {date.today().isoformat()}", styles["CoverSubtitle"])
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(f"{len(pages)} page(s) crawled", styles["CoverSubtitle"])
    )
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # Table of Contents
    # ------------------------------------------------------------------
    story.append(NextPageTemplate("Body"))
    story.append(Paragraph("Table of Contents", styles["TOCHeading"]))
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCEntry0"], styles["TOCEntry1"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # Chapters (one per crawled page)
    # ------------------------------------------------------------------
    for idx, page in enumerate(pages, start=1):
        chapter_label = f"Chapter {idx}"
        doc.current_chapter = page.title

        story.append(
            Paragraph(f"{chapter_label}: {_esc(page.title)}", styles["ChapterTitle"])
        )
        story.append(Paragraph(_esc(page.url), styles["URLStyle"]))

        # Body text — split on double newlines into paragraphs
        body = page.text.strip()
        if body:
            for para in re.split(r"\n{2,}", body):
                para = para.strip()
                if not para:
                    continue
                # Detect possible headings (short lines, no period at end)
                if len(para) < 80 and not para.endswith(".") and "\n" not in para:
                    story.append(Paragraph(_esc(para), styles["SectionHeading"]))
                else:
                    # Preserve single newlines as spaces
                    para = para.replace("\n", " ")
                    story.append(Paragraph(_esc(para), styles["BodyText"]))
        else:
            story.append(
                Paragraph("[No extractable text content]", styles["BodyText"])
            )

        # Mini-TOC of child links at the bottom of each chapter
        if page.child_links:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph("Links on this page:", styles["SectionHeading"]))
            for link in page.child_links[:30]:  # cap to keep PDF reasonable
                story.append(Paragraph(_esc(link), styles["URLStyle"]))

        story.append(PageBreak())

    doc.multiBuild(story)
    print(f"PDF written to: {output_path}")


def _esc(text: str) -> str:
    """Escape special XML/HTML characters for reportlab Paragraph."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
