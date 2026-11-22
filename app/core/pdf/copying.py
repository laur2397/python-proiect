"""Copierea din PDF Editor (faza 7, pasul 7.3): C-040…C-049.

O zona marcata pe o singura pagina (C-040) se copiaza ca imagine (C-042), ca
text (C-043) sau ca tabel cu structura editabila (C-045…C-047). Textul vine
din stratul de text al paginii; pe o pagina fara text (scanare), din
recunoasterea zonei, intr-un proiect OCR temporar. Selectia directa de text
(C-044) poate trece peste mai multe pagini.

Nucleul nu atinge clipboard-ul: intoarce imaginea, textul sau tabelul (TSV si
HTML), iar interfata le pune in clipboard. Fisierul PDF nu se modifica (C-047).
"""

from __future__ import annotations

import html
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from app.core.layout.tables import TableAnalyzer, single_cell, structure_from_gray
from app.core.model import Rect, TableCellData, TableData
from app.core.pdf.text import PageText, read_page_text

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.pdf.document import PdfDocument

COPY_DPI = 300
"""Rezolutia imaginii copiate si a imaginii din care se recunoaste o zona."""

WARNING_COPY_MISMATCH = "warning.copy_mismatch"
"""C-049: textul copiat pare sa nu corespunda imaginii (strat de text slab sau
lipsa); interfata sugereaza verificarea limbilor OCR sau inlocuirea stratului."""

_SUSPECT_SHARE = 0.2
"""C-049: peste 20% caractere suspecte (inlocuire, zona privata, control)."""


# C-040
def check_area(document: PdfDocument, page: int, rect: Rect) -> None:
    """Zona trebuie sa fie pe o singura pagina: in interiorul ei si nevida."""
    total = document.page_count
    if not 1 <= page <= total:
        raise ValueError(f"pagina {page} nu exista (1..{total})")
    if rect.w <= 0 or rect.h <= 0:
        raise ValueError("zona de copiat e goala")
    pdf_page = document._pike().pages[page - 1]
    x0, y0, x1, y1 = (float(v) for v in pdf_page.mediabox)
    width, height = abs(x1 - x0), abs(y1 - y0)
    eps = 0.5
    if rect.x < -eps or rect.y < -eps or rect.x + rect.w > width + eps \
            or rect.y + rect.h > height + eps:
        raise ValueError("zona trebuie sa ramana in interiorul unei singure pagini (C-040)")


# --- imaginea (C-042) -----------------------------------------------------------------


def area_image(document: PdfDocument, page: int, rect: Rect, *, dpi: int = COPY_DPI
               ) -> Image.Image:
    """C-042: imaginea zonei, cu adnotarile vizibile, la `dpi`."""
    from app.core.pdf.redact import _frame, _render

    check_area(document, page, rect)
    frame = _frame(document._pike().pages[page - 1], dpi)
    image = _render(document, page, frame, annotations=True)
    return image.crop(frame.to_pixels(rect))


# --- textul (C-043, C-044, C-049) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class CopiedText:
    text: str
    from_ocr: bool = False
    """True cand textul vine din recunoasterea zonei (pagina fara strat de text)."""
    warning: str | None = None
    """C-049: cheia avertismentului, sau None."""


def _inside(box: Rect, rect: Rect) -> bool:
    cx, cy = box.x + box.w / 2, box.y + box.h / 2
    return rect.x <= cx <= rect.x + rect.w and rect.y <= cy <= rect.y + rect.h


def _collect(page: PageText, keep: Sequence[bool]) -> str:
    """Caracterele pastrate, cu spatiile si randurile dintre ele."""
    out: list[str] = []
    pending = ""
    for ch, kept, box in zip(page.text, keep, page.boxes, strict=True):
        if box is None or ch.isspace():
            if out:
                pending += ch
            continue
        if kept:
            if pending:
                out.append("\n" if ("\n" in pending or "\r" in pending) else " ")
            out.append(ch)
            pending = ""
        elif out:
            pending = pending or " "
    return "".join(out)


def _suspect(text: str) -> bool:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    bad = sum(1 for c in chars if c == "�" or "" <= c <= "" or ord(c) < 32)
    return bad / len(chars) > _SUSPECT_SHARE


def _has_ink(image: Image.Image) -> bool:
    gray = np.asarray(image.convert("L"))
    return bool(gray.size) and float((gray < 128).mean()) > 0.002


# C-043, C-049
def area_text(document: PdfDocument, page: int, rect: Rect, *,
              context: AppContext | None = None, engine: Any = None) -> CopiedText:
    """C-043: textul zonei. Din stratul de text, daca pagina are unul; altfel
    din recunoasterea zonei (C-044: recunoasterea furnizeaza textul lipsa).
    `warning` (C-049) cand textul pare stricat sau zona are continut dar textul
    lipseste."""
    check_area(document, page, rect)
    page_text = read_page_text(document._require_open(), page)
    if document.has_text_layer(page):
        keep = [box is not None and _inside(box, rect) for box in page_text.boxes]
        text = _collect(page_text, keep)
        warning = None
        if _suspect(text) or (not text and _has_ink(area_image(document, page, rect,
                                                                 dpi=72))):
            warning = WARNING_COPY_MISMATCH
        return CopiedText(text, False, warning)
    lines, _words = _ocr(area_image(document, page, rect), context, engine)
    text = "\n".join(lines)
    return CopiedText(text, True, WARNING_COPY_MISMATCH if _suspect(text) else None)


# C-044
def char_index_at(document: PdfDocument, page: int, x: float, y: float) -> int | None:
    """Indicele caracterului de sub mouse (puncte, sus-stanga), pentru selectia
    directa de text; None = mouse-ul nu e pe text (interfata verifica atunci
    recunoasterea in fundal, C-044)."""
    page_text = read_page_text(document._require_open(), page)
    for i, box in enumerate(page_text.boxes):
        if box is not None and box.x <= x <= box.x + box.w and box.y <= y <= box.y + box.h:
            return i
    return None


def text_between(document: PdfDocument, start: tuple[int, int], end: tuple[int, int]) -> str:
    """C-044: textul dintre doua pozitii (pagina, indice), inclusiv capetele;
    poate trece peste mai multe pagini (paginile se despart printr-un rand)."""
    if end < start:
        start, end = end, start
    doc = document._require_open()
    parts: list[str] = []
    for number in range(start[0], end[0] + 1):
        text = read_page_text(doc, number).text
        first = start[1] if number == start[0] else 0
        last = end[1] + 1 if number == end[0] else len(text)
        parts.append(text[first:last].replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(parts)


# --- recunoasterea unei zone ----------------------------------------------------------


def _ocr(image: Image.Image, context: AppContext | None, engine: Any
         ) -> tuple[list[str], list[tuple[str, Rect]]]:
    """Randurile si cuvintele (cu pozitia in pixelii imaginii) recunoscute
    intr-un proiect OCR temporar."""
    from app.core.export.base import block_lines
    from app.core.model import AutoProcessMode, _area_blocks
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject

    with tempfile.TemporaryDirectory(prefix="doculens-copy-") as tmp:
        source = Path(tmp) / "zona.png"
        image.save(source, dpi=(COPY_DPI, COPY_DPI))
        project = OcrProject.create(context=context)
        try:
            project.add_images([source], auto_process=AutoProcessMode.NONE)
            RecognitionService(project, engine=engine).recognize_pages()
            page = project.pages[0]
            lines: list[str] = []
            words: list[tuple[str, Rect]] = []
            for area in page._ordered_areas():
                for block in _area_blocks(area):
                    lines += [ln for ln in block_lines(block) if ln.strip()]
                    words += [(w.text, w.bbox) for ln in block.lines for w in ln.words
                              if w.text]
            return lines, words
        finally:
            project.close()


# --- tabelul (C-045…C-047) ------------------------------------------------------------


@dataclass
class AreaTable:
    """Tabelul unei zone copiate. Structura e in pixelii imaginii zonei
    (`COPY_DPI`); editarea (C-046) foloseste `TableAnalyzer`, ca in OCR Editor.
    Cuvintele raman legate de pozitia lor, deci dupa fiecare modificare de
    structura textul celulelor se recalculeaza."""

    image: Image.Image
    table: TableData
    words: list[tuple[str, Rect]] = field(default_factory=list)
    from_ocr: bool = False
    _analyzer: TableAnalyzer = field(default_factory=TableAnalyzer, repr=False)

    # C-046
    def add_separator(self, axis: str, position: int) -> None:
        self.table = self._analyzer.add_separator(self.table, axis, position)

    def remove_separator(self, axis: str, position: int) -> None:
        self.table = self._analyzer.remove_separator(self.table, axis, position)

    def merge_cells(self, cells: Sequence[TableCellData]) -> None:
        self.table = self._analyzer.merge_cells(self.table, cells)

    def split_cell(self, cell: TableCellData) -> None:
        self.table = self._analyzer.split_cells(self.table, cell)

    def cell_texts(self) -> list[list[str]]:
        """Textul pe randuri si coloane; o celula unita are textul in coltul
        din stanga-sus, iar casutele acoperite de ea sunt goale."""
        grid = [["" for _ in range(self.table.cols)] for _ in range(self.table.rows)]
        for cell in self.table.cells:
            inside = sorted(((t, b) for t, b in self.words if _inside(b, cell.bbox)),
                            key=lambda item: (item[1].y, item[1].x))
            lines: list[list[tuple[str, Rect]]] = []
            for text, box in inside:
                if lines and abs(box.y - lines[-1][0][1].y) <= box.h * 0.6:
                    lines[-1].append((text, box))
                else:
                    lines.append([(text, box)])
            grid[cell.row][cell.col] = "\n".join(
                " ".join(t for t, _ in sorted(ln, key=lambda item: item[1].x)) for ln in lines)
        return grid

    # C-047: formatele pentru clipboard
    def to_tsv(self) -> str:
        def clean(value: str) -> str:
            return value.replace("\t", " ").replace("\n", " ")

        return "\n".join("\t".join(clean(v) for v in row) for row in self.cell_texts())

    def to_html(self) -> str:
        texts = self.cell_texts()
        rows: list[str] = []
        for r in range(self.table.rows):
            cells = sorted((c for c in self.table.cells if c.row == r), key=lambda c: c.col)
            tds = []
            for c in cells:
                span = (f' rowspan="{c.row_span}"' if c.row_span > 1 else "") + \
                    (f' colspan="{c.col_span}"' if c.col_span > 1 else "")
                body = html.escape(texts[c.row][c.col]).replace("\n", "<br>")
                tds.append(f"<td{span}>{body}</td>")
            rows.append("<tr>" + "".join(tds) + "</tr>")
        return "<table>" + "".join(rows) + "</table>"


# C-045
def area_table(document: PdfDocument, page: int, rect: Rect, *,
               context: AppContext | None = None, engine: Any = None) -> AreaTable:
    """C-045: tabelul zonei: structura din imagine (linii trase sau spatii goale;
    nedetectabila → o singura celula), textul din stratul de text sau din
    recunoasterea zonei."""
    from app.core.images.preprocess import to_array, to_gray

    image = area_image(document, page, rect)
    gray = to_gray(to_array(image))
    bbox = _content_box(gray)
    part = gray[bbox.y:bbox.y + bbox.h, bbox.x:bbox.x + bbox.w]
    table = structure_from_gray(part, bbox, min_column_gap=MIN_COLUMN_GAP,
                                min_line=MIN_LINE) \
        or single_cell(bbox)
    if document.has_text_layer(page):
        words = _layer_words(read_page_text(document._require_open(), page), rect,
                             COPY_DPI / 72)
        return AreaTable(image, table, words, from_ocr=False)
    _lines, words = _ocr(image, context, engine)
    return AreaTable(image, table, words, from_ocr=True)


MIN_LINE = round(COPY_DPI * 30 / 72)
"""[DECIZIE AUTONOMA] O linie de tabel are cel putin 30 pt; zona unui singur rand
de text nu are linii verticale (tijele literelor sunt mai scurte)."""

MIN_COLUMN_GAP = round(COPY_DPI * 10 / 72)
"""[DECIZIE AUTONOMA] Fara linii trase, doua coloane ale tabelului copiat sunt
despartite de cel putin 10 pt de spatiu gol; spatiile dintre cuvinte (sub 6 pt
la textul obisnuit) nu despart coloane."""


def _content_box(gray: np.ndarray, pad: int = 2) -> Rect:
    """Dreptunghiul continutului din zona: marginile albe trase in plus de
    utilizator nu devin randuri sau coloane goale."""
    if not gray.size:
        return Rect(0, 0, 0, 0)
    paper = int(np.percentile(gray, 90))
    ink = gray < paper - 50
    rows, cols = np.nonzero(ink.any(axis=1))[0], np.nonzero(ink.any(axis=0))[0]
    height, width = gray.shape
    if not rows.size:
        return Rect(0, 0, width, height)
    x0, x1 = max(0, int(cols[0]) - pad), min(width, int(cols[-1]) + 1 + pad)
    y0, y1 = max(0, int(rows[0]) - pad), min(height, int(rows[-1]) + 1 + pad)
    return Rect(x0, y0, x1 - x0, y1 - y0)


def _layer_words(page: PageText, rect: Rect, scale: float) -> list[tuple[str, Rect]]:
    """Cuvintele stratului de text din zona, in pixelii imaginii zonei."""
    words: list[tuple[str, Rect]] = []
    chars: list[tuple[str, Rect]] = []

    def flush() -> None:
        if chars:
            x0 = min(b.x for _, b in chars)
            y0 = min(b.y for _, b in chars)
            x1 = max(b.x + b.w for _, b in chars)
            y1 = max(b.y + b.h for _, b in chars)
            words.append(("".join(c for c, _ in chars),
                          Rect((x0 - rect.x) * scale, (y0 - rect.y) * scale,
                               (x1 - x0) * scale, (y1 - y0) * scale)))
            chars.clear()

    for ch, box in zip(page.text, page.boxes, strict=True):
        if box is None or ch.isspace() or not _inside(box, rect):
            flush()
            continue
        if chars and (box.x - (chars[-1][1].x + chars[-1][1].w) > box.h * 0.6
                      or abs(box.y - chars[-1][1].y) > box.h * 0.5):
            flush()
        chars.append((ch, box))
    flush()
    return words
