"""Documentul intermediar pentru formatele editabile (faza 6, pasul 6.4).

DOCX, RTF si ODT (si, in 6.6, HTML, EPUB, FB2) pornesc de la acelasi model,
construit o data dupa modul de layout (Q-002..Q-005) si optiunile X-100..X-109:

- `plain`: fara formatare; bold, italic, subliniat numai cu X-108; tabelele
  devin paragrafe, imaginile nu se pastreaza;
- `formatted`: fonturile, marimile, paragrafele, tabelele, imaginile; textul
  aliniat la stanga (Q-004);
- `editable`: in plus alinierea, rupturile de pagina (X-105), antetele si
  subsolurile (X-103), numerotarea randurilor (X-106), marimea hartiei (X-101);
- `exact`: in plus spatierea verticala dintre blocuri, care reproduce pozitiile.

[DECIZIE AUTONOMA] `exact` aproximeaza pozitiile prin spatierea dintre
paragrafe, nu prin casete de text plasate absolut; textul ramane in fluxul
documentului, deci se editeaza usor.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps

from app.core.export.base import ExportOptions, word_text
from app.core.model import AreaType, BlockData, LayoutMode, PageData

PAPER_SIZES_PT = {"a3": (842, 1191), "a4": (595.3, 841.9), "a5": (419.5, 595.3),
                  "letter": (612, 792), "legal": (612, 1008)}
"""X-101: marimile de hartie, in puncte (portret)."""


@dataclass(slots=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    superscript: bool = False
    subscript: bool = False
    color: str | None = None
    font: str | None = None
    size: float | None = None
    highlight: str | None = None


@dataclass(slots=True)
class Para:
    runs: list[Run]
    style: str | None = None
    """Numele stilului (Q-013: stilurile existente se pastreaza)."""
    kind: str = "paragraph"
    level: int | None = None
    heading: int = 0
    align: str | None = None
    space_before: float = 0.0
    direction: str = "ltr"

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass(slots=True)
class Cell:
    row: int
    col: int
    row_span: int
    col_span: int
    paras: list[Para]


@dataclass(slots=True)
class Table:
    rows: int
    cols: int
    cells: list[Cell]
    col_widths: list[float]


@dataclass(slots=True)
class Picture:
    data: bytes
    """PNG."""
    width: float
    height: float


@dataclass(slots=True)
class DocPage:
    width: float
    height: float
    body: list[Para | Table | Picture] = field(default_factory=list)
    header: list[Para] = field(default_factory=list)
    footer: list[Para] = field(default_factory=list)
    footnotes: list[Para] = field(default_factory=list)


@dataclass(slots=True)
class Document:
    pages: list[DocPage]
    mode: LayoutMode
    page_breaks: bool = True
    line_numbers: bool = False
    title: str = ""


def _size_pt(height_px: int, dpi: int) -> float:
    """Marimea fontului din inaltimea cuvantului (o aproximare a corpului)."""
    return max(4.0, min(96.0, round(height_px * 72.0 / dpi * 2) / 2))


def _paper(page: PageData, setting: str | None) -> tuple[float, float]:
    width = page.width_px * 72.0 / page.dpi_x
    height = page.height_px * 72.0 / page.dpi_y
    if setting in PAPER_SIZES_PT:
        w, h = PAPER_SIZES_PT[setting]
        return (h, w) if width > height else (w, h)  # orientarea paginii
    return width, height


def _runs(block: BlockData, page: PageData, options: ExportOptions, mode: LayoutMode,
          fmt: dict[str, Any]) -> list[Run]:
    plain = mode is LayoutMode.PLAIN
    styled = not plain or bool(fmt.get("keep_styles_in_plain", True))
    keep_colors = bool(fmt.get("keep_colors", True)) and not plain
    highlight = fmt.get("highlight_color") if fmt.get("highlight_low_confidence") else None
    runs: list[Run] = []
    for li, line in enumerate(block.lines):
        if li:
            text_break = "\n" if options.keep_line_breaks else " "
            if (not options.keep_line_breaks and runs and runs[-1].text.endswith("-")
                    and line.words and line.words[0].text[:1].islower()):
                runs[-1].text = runs[-1].text[:-1]  # R-035: cuvantul despartit se reface
                text_break = ""
            if text_break:
                runs.append(Run(text_break))
        for wi, word in enumerate(line.words):
            if wi:
                runs.append(Run(" "))
            runs.append(Run(
                word_text(word),
                bold=bool(word.is_bold) and styled, italic=bool(word.is_italic) and styled,
                underline=bool(word.is_underline) and styled,
                superscript=bool(word.is_superscript) and not plain,
                subscript=bool(word.is_subscript) and not plain,
                color=word.text_color if keep_colors else None,
                font=None if plain else word.font_name,
                size=None if plain else (word.font_size or _size_pt(word.bbox.h, page.dpi_y)),
                highlight=highlight if word.is_uncertain and not plain else None))
    return _merge(runs)


def _merge(runs: list[Run]) -> list[Run]:
    """Fragmentele vecine cu aceeasi formatare se unesc."""
    out: list[Run] = []
    for run in runs:
        if out and _same(out[-1], run):
            out[-1].text += run.text
        else:
            out.append(run)
    return out


def _same(a: Run, b: Run) -> bool:
    keys = ("bold", "italic", "underline", "superscript", "subscript", "color", "font",
            "highlight")
    if b.text.strip() == "":
        return True
    return all(getattr(a, k) == getattr(b, k) for k in keys) and a.size == b.size


def _para(block: BlockData, page: PageData, options: ExportOptions, mode: LayoutMode,
          fmt: dict[str, Any]) -> Para:
    match = re.match(r"^Heading (\d+)$", block.style_name or "")
    heading = int(match.group(1)) if match else (1 if block.block_type == "heading" else 0)
    plain = mode is LayoutMode.PLAIN
    return Para(_runs(block, page, options, mode, fmt),
                style=None if plain else block.style_name,
                kind=block.block_type, level=block.list_level,
                heading=0 if plain else heading,
                align=block.alignment if mode in (LayoutMode.EDITABLE, LayoutMode.EXACT)
                else None,
                direction=block.direction)


def _picture(page: PageData, area: Any) -> Picture:
    b = area.bbox
    with Image.open(page.image_path) as src:
        crop = ImageOps.exif_transpose(src).crop((b.x, b.y, b.right, b.bottom))
        out = io.BytesIO()
        crop.convert("RGB" if crop.mode not in ("1", "L") else crop.mode).save(out, "PNG")
    return Picture(out.getvalue(), b.w * 72.0 / page.dpi_x, b.h * 72.0 / page.dpi_y)


def _table(area: Any, page: PageData, options: ExportOptions, mode: LayoutMode,
           fmt: dict[str, Any]) -> Table:
    cells = [Cell(c.row, c.col, c.row_span, c.col_span,
                  [_para(b, page, options, mode, fmt) for b in c.blocks])
             for c in sorted(area.table.cells, key=lambda c: (c.row, c.col))]
    xs = [area.bbox.x, *area.table.v_separators, area.bbox.right]
    widths = [(xs[i + 1] - xs[i]) * 72.0 / page.dpi_x for i in range(len(xs) - 1)]
    if len(widths) != area.table.cols:
        widths = [area.bbox.w * 72.0 / page.dpi_x / area.table.cols] * area.table.cols
    return Table(area.table.rows, area.table.cols, cells, widths)


# Q-002..Q-005, X-100..X-109
def build_document(pages: Sequence[PageData], options: ExportOptions, *,
                   headers_in: Sequence[LayoutMode] = (LayoutMode.EDITABLE, LayoutMode.EXACT),
                   ) -> Document:
    """`headers_in`: modurile in care antetele si subsolurile se pastreaza cu
    `keep_headers_footers` (X-103: Word numai in editable; X-124: HTML si in
    formatted)."""
    mode = LayoutMode(options.layout_mode)
    fmt = dict(options.format_options)
    full = mode in (LayoutMode.EDITABLE, LayoutMode.EXACT)
    keep_pictures = options.keep_pictures and mode is not LayoutMode.PLAIN
    doc = Document([], mode,
                   page_breaks=bool(fmt.get("keep_page_breaks", True)) and full,
                   line_numbers=bool(fmt.get("keep_line_numbers")) and mode is LayoutMode.EDITABLE,
                   title=options.metadata.get("title", ""))
    for page in pages:
        width, height = _paper(page, fmt.get("paper_size"))
        out = DocPage(width, height)
        last_bottom = 0
        for area in page._ordered_areas():
            if area.area_type in (AreaType.PICTURE, AreaType.BARCODE):
                if keep_pictures:
                    out.body.append(_picture(page, area))
                    last_bottom = area.bbox.bottom
                continue
            if area.area_type is AreaType.TABLE and area.table is not None:
                table = _table(area, page, options, mode, fmt)
                if mode is LayoutMode.PLAIN:
                    out.body += [p for c in table.cells for p in c.paras]
                else:
                    out.body.append(table)
                last_bottom = area.bbox.bottom
                continue
            for block in area.blocks:
                if not block.lines:
                    continue
                para = _para(block, page, options, mode, fmt)
                if block.block_type in ("header", "footer"):
                    if options.keep_headers_footers and mode in headers_in:
                        target = out.header if block.block_type == "header" else out.footer
                        target.append(para)
                    continue
                if block.block_type == "footnote":
                    out.footnotes.append(para)
                    continue
                if mode is LayoutMode.EXACT:
                    gap = max(0, block.bbox.y - last_bottom) * 72.0 / page.dpi_y
                    para.space_before = round(min(gap, 400.0), 1)
                last_bottom = max(last_bottom, block.bbox.bottom)
                out.body.append(para)
        doc.pages.append(out)
    return doc
