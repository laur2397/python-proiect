"""Exportul Word (faza 6, pasul 6.4): Q-013, X-100..X-109.

Din documentul intermediar (`docmodel.py`), cu python-docx (MIT). Stilurile
`Heading N` devin stilurile de titlu ale lui Word; celelalte stiluri se pastreaza
cu numele lor (Q-013). Fara Microsoft Office (CLAUDE.md §6.3).

INCOMPLET, marcat: notele de subsol se scriu la sfarsitul paginii, cu litera
mai mica, nu ca note Word (python-docx nu le scrie).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import docx
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.core.export.base import BaseExporter, ExportOptions, report
from app.core.export.docmodel import Document, Para, Picture, Table, build_document
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
          "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
MARGIN_PT = 36


def _style(doc: Any, para: Para) -> str | None:
    if para.heading:
        return f"Heading {min(para.heading, 9)}"
    if para.kind == "list_item":
        return "List Paragraph"
    if para.style:
        if para.style not in [s.name for s in doc.styles]:
            doc.styles.add_style(para.style, 1)  # 1 = stil de paragraf
        return para.style
    return None


def _write_para(container: Any, doc: Any, para: Para) -> None:
    p = container.add_paragraph(style=_style(doc, para))
    fmt = p.paragraph_format
    if para.align in _ALIGN:
        p.alignment = _ALIGN[para.align]
    if para.space_before:
        fmt.space_before = Pt(para.space_before)
    if para.kind == "list_item" and para.level:
        fmt.left_indent = Pt(18 * para.level)
    if para.direction == "rtl":
        p._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
    for run in para.runs:
        for i, piece in enumerate(run.text.split("\n")):
            if i:
                p.add_run().add_break()
            if not piece:
                continue
            r = p.add_run(piece)
            r.bold = run.bold or None
            r.italic = run.italic or None
            r.underline = run.underline or None
            r.font.superscript = run.superscript or None
            r.font.subscript = run.subscript or None
            if run.font:
                r.font.name = run.font
            if run.size:
                r.font.size = Pt(run.size)
            if run.color:
                r.font.color.rgb = RGBColor.from_string(run.color.lstrip("#").upper())
            if run.highlight:  # X-109: caracterele nesigure, cu culoarea din X-166
                shading = OxmlElement("w:shd")
                shading.set(qn("w:val"), "clear")
                shading.set(qn("w:fill"), run.highlight.lstrip("#").upper())
                r._r.get_or_add_rPr().append(shading)


def _write_table(doc: Any, table: Table) -> None:
    t = doc.add_table(rows=table.rows, cols=table.cols)
    t.style = "Table Grid"
    for i, width in enumerate(table.col_widths):
        for cell in t.columns[i].cells:
            cell.width = Pt(width)
    for cell in table.cells:
        target = t.cell(cell.row, cell.col)
        if cell.row_span > 1 or cell.col_span > 1:
            target = target.merge(t.cell(cell.row + cell.row_span - 1,
                                         cell.col + cell.col_span - 1))
        first = target.paragraphs[0]
        for para in cell.paras:
            _write_para(target, doc, para)
        if cell.paras and not first.text:
            first._p.getparent().remove(first._p)


def _line_numbers(section: Any) -> None:
    """X-106: numerotarea randurilor (camp separat, nu text)."""
    numbering = OxmlElement("w:lnNumType")
    numbering.set(qn("w:countBy"), "1")
    numbering.set(qn("w:restart"), "newPage")
    section._sectPr.append(numbering)


def write_docx(document: Document, target: Path, *,
               progress: ProgressCallback | None = None) -> None:
    doc = docx.Document()
    if document.title:
        doc.core_properties.title = document.title
    for index, page in enumerate(document.pages):
        if index == 0:
            section = doc.sections[0]
        elif document.page_breaks:
            section = doc.add_section(WD_SECTION.NEW_PAGE)
        else:
            section = doc.sections[-1]
        section.page_width, section.page_height = Pt(page.width), Pt(page.height)
        for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(section, side, Pt(MARGIN_PT))
        if document.line_numbers and index == 0 or document.line_numbers and \
                document.page_breaks:
            _line_numbers(section)
        if page.header or page.footer:
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False
            for part, paras in ((section.header, page.header), (section.footer, page.footer)):
                for para in paras:
                    _write_para(part, doc, para)
        content_width = page.width - 2 * MARGIN_PT
        for item in page.body:
            if isinstance(item, Para):
                _write_para(doc, doc, item)
            elif isinstance(item, Table):
                _write_table(doc, item)
            elif isinstance(item, Picture):
                doc.add_picture(io.BytesIO(item.data), width=Pt(min(item.width, content_width)))
        for note in page.footnotes:
            for run in note.runs:
                run.size = min(run.size or 8, 8)
            _write_para(doc, doc, note)
        report(progress, index + 1, len(document.pages), "stage.exporting")
    doc.save(str(target))


# SPEC_05 Exporter. Q-013
class DocxExporter(BaseExporter):
    format = ExportFormat.DOCX

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EDITABLE)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        document = build_document(pages, options)
        fmt = dict(options.format_options)
        quality = picture_quality(fmt.get("image_quality"), fmt.get("image_custom_quality"))
        for page in document.pages:  # X-102: calitatea imaginilor pastrate
            for item in page.body:
                if isinstance(item, Picture):
                    item.data = encode_picture(item.data, quality)
        write_docx(document, target, progress=progress)
        return [target]


def picture_quality(choice: Any, custom: Any = None) -> int | None:
    """X-102: calitatea JPEG a imaginilor pastrate; None = PNG fara pierderi
    (`best`). `Custom...` foloseste valoarea aleasa (10…100)."""
    from app.core.export.pdf import JPEG_QUALITY
    from app.core.model import ImageQuality

    if choice is None:
        return JPEG_QUALITY[ImageQuality.BALANCED]
    quality = ImageQuality(choice)
    if quality is ImageQuality.BEST:
        return None
    if quality is ImageQuality.CUSTOM and custom:
        return max(10, min(100, int(custom)))
    return JPEG_QUALITY[quality]


def encode_picture(data: bytes, quality: int | None) -> bytes:
    """PNG-ul din modelul documentului, pastrat (None) sau recodat JPEG."""
    if quality is None:
        return data
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        out = io.BytesIO()
        image.convert("RGB" if image.mode not in ("L",) else "L").save(
            out, "JPEG", quality=quality)
    return out.getvalue()
