"""Editarea continutului unei pagini PDF (faza 9, pasul 9.5): F-002…F-023.

Pagina se imparte in blocuri de text (randuri apropiate, aliniate) si imagini.
Sursa blocurilor (F-002):

- un PDF produs de alte aplicatii: obiectele text ale paginii;
- o scanare sau un PDF cautabil: stratul de text (existent sau recunoscut acum,
  B-028), peste imaginea paginii;
- un PDF al carui text e grafica vectoriala (contururi, fara obiecte text si fara
  imagine) nu se poate edita: `ContentNotEditableError`.

O modificare (F-008, F-012…F-016) scoate obiectele text din zona blocului cu
PDFium (`remove_obj`, `gen_content`) si deseneaza textul nou cu fontul
incorporat, cu reflow in latimea blocului. Pe o scanare, zona veche se acopera
cu culoarea fondului detectata in jurul ei (textul era in imagine). Fontul: cel
al blocului, daca e instalat ca TrueType; altfel cel mai apropiat dupa familie
(serif, fara serife, monospatiat), cu nota in jurnal (F-006). Un nume de font
incorporat in PDF dar neinstalat se afiseaza in paranteze patrate (F-005).

Imaginile (F-020…F-023) sunt obiectele imagine ale paginii, numerotate in
ordinea desenarii.
"""

from __future__ import annotations

import ctypes
import io
import math
import statistics
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.applog import get_logger
from app.core.errors import CoreError
from app.core.model import BlockData, LineData, Rect, WordData

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.pdf.document import PdfDocument

_log = get_logger("pdf.content")

ALIGNMENTS = ("left", "center", "right", "justify")
"""F-016, F-107."""
MIN_BLOCK_WIDTH = 10.0
"""SPEC_05 F-008: latimea minima a unui bloc, in puncte."""
DEFAULT_SIZE = 11.0
_LINE_GAP = 0.9
"""Doua randuri sunt in acelasi bloc daca distanta dintre ele e sub 0,9 x inaltimea."""


class ContentNotEditableError(CoreError):
    """F-002, F-003: pagina nu se poate pregati (text vectorial, fara text)."""

    code = "CONTENT_NOT_EDITABLE"


@dataclass
class TextBlock:
    """Un bloc de text si formatarea lui (F-015, F-016, F-107…F-110)."""

    id: int
    rect: Rect
    text: str
    source: str = "text"
    """`text` (obiecte text ale paginii), `ocr` (scanare) sau `new`."""
    font_name: str | None = None
    embedded: bool = False
    installed: bool = True
    font_size: float = DEFAULT_SIZE
    color: str = "#000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    alignment: str = "left"
    line_spacing: float = 1.2
    paragraph_spacing: float = 0.0
    direction: str = "ltr"

    @property
    def display_font(self) -> str | None:
        """F-005: `[Nume]` = font incorporat in PDF, dar neinstalat."""
        if self.font_name is None:
            return None
        return f"[{self.font_name}]" if self.embedded and not self.installed else self.font_name

    def as_block_data(self) -> BlockData:
        lines = [LineData(None, words=[WordData(None, w, 100.0) for w in text.split()])
                 for text in self.text.split("\n")]
        return BlockData(self.id, lines=lines, bbox=self.rect, alignment=self.alignment,
                         direction=self.direction)


@dataclass
class Picture:
    id: int
    rect: Rect


@dataclass
class PreparedPage:
    number: int
    kind: str
    """`text`, `scan` sau `blank`."""
    blocks: list[TextBlock] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)


# --- citirea paginii -------------------------------------------------------------------------


def _raw() -> Any:
    from pypdfium2 import raw

    return raw


def _objects(document: PdfDocument, number: int) -> list[Any]:
    return list(document._require_open()[number - 1].get_objects())


def _to_rect(document: PdfDocument, number: int, bounds: tuple[float, ...]) -> Rect:
    from app.core.pdf.text import from_pdf_rect, page_geometry

    return from_pdf_rect(page_geometry(document._pike().pages[number - 1]), list(bounds))


def _font_info(obj: Any) -> tuple[str | None, bool, float, str]:
    """(numele fontului, incorporat, marimea efectiva, culoarea) unui obiect text."""
    raw = _raw()
    name = None
    embedded = False
    font = raw.FPDFTextObj_GetFont(obj.raw)
    if font:
        buf = ctypes.create_string_buffer(256)
        if raw.FPDFFont_GetFamilyName(font, buf, 256):
            name = buf.value.decode("utf-8", "replace") or None
        embedded = bool(raw.FPDFFont_GetIsEmbedded(font))
    size = ctypes.c_float(0)
    raw.FPDFTextObj_GetFontSize(obj.raw, ctypes.byref(size))
    matrix = obj.get_matrix()
    scale = math.hypot(matrix.c, matrix.d) or 1.0
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    raw.FPDFPageObj_GetFillColor(obj.raw, *(ctypes.byref(v) for v in (r, g, b, a)))
    return name, embedded, float(size.value) * scale, f"#{r.value:02x}{g.value:02x}{b.value:02x}"


def _is_invisible_text(obj: Any) -> bool:
    raw = _raw()
    return raw.FPDFTextObj_GetTextRenderMode(obj.raw) == raw.FPDF_TEXTRENDERMODE_INVISIBLE


def _lines(document: PdfDocument, number: int) -> list[tuple[Rect, str]]:
    """Randurile de text ale paginii (dreptunghi, text), din stratul de text."""
    page = document.page_text(number)
    out: list[tuple[Rect, str]] = []
    current: list[tuple[str, Rect | None]] = []

    def flush() -> None:
        boxes = [b for _c, b in current if b is not None]
        text = "".join(c for c, _b in current).strip()
        if boxes and text:
            x0 = min(b.x for b in boxes)
            y0 = min(b.y for b in boxes)
            x1 = max(b.x + b.w for b in boxes)
            y1 = max(b.y + b.h for b in boxes)
            out.append((Rect(x0, y0, x1 - x0, y1 - y0), text))
        current.clear()

    for ch, box in zip(page.text, page.boxes, strict=False):
        if ch in "\r\n":
            flush()
            continue
        current.append((ch, box))
    flush()
    return out


def _group(lines: list[tuple[Rect, str]]) -> list[tuple[Rect, str]]:
    """Randurile apropiate si suprapuse pe orizontala devin un bloc."""
    blocks: list[list[tuple[Rect, str]]] = []
    for rect, text in sorted(lines, key=lambda item: (item[0].y, item[0].x)):
        if blocks:
            last_rect = blocks[-1][-1][0]
            gap = rect.y - (last_rect.y + last_rect.h)
            overlap = min(rect.x + rect.w, last_rect.x + last_rect.w) - max(rect.x, last_rect.x)
            similar = abs(rect.h - last_rect.h) <= 0.35 * max(rect.h, last_rect.h)
            if 0 <= gap <= _LINE_GAP * last_rect.h and overlap > 0 and similar:
                blocks[-1].append((rect, text))
                continue
        blocks.append([(rect, text)])
    out = []
    for group in blocks:
        x0 = min(r.x for r, _t in group)
        y0 = min(r.y for r, _t in group)
        x1 = max(r.x + r.w for r, _t in group)
        y1 = max(r.y + r.h for r, _t in group)
        out.append((Rect(x0, y0, x1 - x0, y1 - y0), "\n".join(t for _r, t in group)))
    return out


def _intersects(a: Rect, b: Rect) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def prepare(document: PdfDocument, number: int, *, context: AppContext | None = None,
            engine: Any = None) -> PreparedPage:
    """F-001…F-003: blocurile si imaginile paginii. Pe o scanare fara strat de
    text, pagina se recunoaste intai (stratul temporar, B-028)."""
    from app.core.fonts import font_file

    raw = _raw()
    document._check_pages([number])
    objects = _objects(document, number)
    texts = [o for o in objects if o.type == raw.FPDF_PAGEOBJ_TEXT]
    visible = [o for o in texts if not _is_invisible_text(o)]
    images = [o for o in objects if o.type == raw.FPDF_PAGEOBJ_IMAGE]
    paths = [o for o in objects if o.type == raw.FPDF_PAGEOBJ_PATH]
    pictures = [Picture(i, _to_rect(document, number, o.get_bounds()))
                for i, o in enumerate(images, start=1)]
    if visible:
        kind = "text"
    elif images:
        kind = "scan"
        if not document.page_text(number).text.strip():
            document.recognize_in_background(pages=[number], context=context, engine=engine)
    elif paths:
        raise ContentNotEditableError("textul paginii e grafica vectoriala", page=number)
    else:
        return PreparedPage(number, "blank", [], pictures)
    blocks = []
    page_width = document.page_size(number)[0]
    for i, (found, text) in enumerate(_group(_lines(document, number)), start=1):
        rows = text.count("\n") + 1
        # latimea blocului are o rezerva de 10%: fontul inlocuitor (F-006) poate fi
        # putin mai lat, iar un rand care incapea nu trebuie sa se rupa la mutare
        rect = Rect(found.x, found.y, min(found.w * 1.1 + 2, page_width - found.x), found.h)
        block = TextBlock(i, rect, text, source="text" if kind == "text" else "ocr",
                          font_size=max(1.0, round(rect.h / rows / 1.2, 1)))
        if kind == "text":
            inside = [o for o in visible
                      if _intersects(_to_rect(document, number, o.get_bounds()), rect)]
            if inside:
                name, embedded, size, color = _font_info(inside[0])
                block = replace(block, font_name=name, embedded=embedded,
                                font_size=round(size, 1) or block.font_size, color=color,
                                installed=name is not None and font_file(name) is not None)
        blocks.append(block)
    return PreparedPage(number, kind, blocks, pictures)


# --- scrierea ---------------------------------------------------------------------------------


def commit_pdfium(document: PdfDocument) -> None:
    """Dupa modificarile facute cu PDFium: vederea pikepdf se reface din ele."""
    from app.core.pdf.document import PDFIUM_LOCK

    buf = io.BytesIO()
    with PDFIUM_LOCK:
        document._require_open().save(buf)
    old = document._pdf
    document._pdf = pikepdf.open(io.BytesIO(buf.getvalue()))
    if old is not None:
        old.close()


def remove_area(document: PdfDocument, number: int, rect: Rect, *,
                invisible_only: bool = False) -> int:
    """Obiectele text din zona (pe o scanare, numai cele invizibile, ale stratului
    de text) dispar din pagina. Intoarce cate s-au scos."""
    raw = _raw()
    page = document._require_open()[number - 1]
    removed = 0
    for obj in list(page.get_objects()):
        if obj.type != raw.FPDF_PAGEOBJ_TEXT:
            continue
        if invisible_only and not _is_invisible_text(obj):
            continue
        if _intersects(_to_rect(document, number, obj.get_bounds()), rect):
            page.remove_obj(obj)
            removed += 1
    if removed:
        page.gen_content()
        commit_pdfium(document)
    return removed


def background_color(document: PdfDocument, number: int, rect: Rect) -> str:
    """Culoarea fondului in jurul zonei (mediana inelului), pentru acoperire."""
    from PIL import Image

    image = Image.open(io.BytesIO(document.render_page(number, 1.0, annotations=False)))
    image = image.convert("RGB")
    scale = image.width / document.page_size(number)[0]
    x0, y0 = int(rect.x * scale) - 3, int(rect.y * scale) - 3
    x1, y1 = int((rect.x + rect.w) * scale) + 3, int((rect.y + rect.h) * scale) + 3
    pixels = []
    for x in range(max(x0, 0), min(x1, image.width)):
        for y in (y0, y1):
            if 0 <= y < image.height:
                pixels.append(image.getpixel((x, y)))
    for y in range(max(y0, 0), min(y1, image.height)):
        for x in (x0, x1):
            if 0 <= x < image.width:
                pixels.append(image.getpixel((x, y)))
    if not pixels:
        return "#ffffff"
    r, g, b = (int(statistics.median(p[i] for p in pixels)) for i in range(3))
    return f"#{r:02x}{g:02x}{b:02x}"


def font_path(block: TextBlock) -> Path | None:
    """F-006: fontul instalat cel mai apropiat de cel al blocului."""
    from app.core.fonts import font_file

    if not block.font_name:
        return None
    exact = font_file(block.font_name, bold=block.bold, italic=block.italic)
    if exact is not None:
        return exact
    low = block.font_name.casefold()
    serif = any(k in low for k in ("times", "serif", "roman", "georgia", "garamond")) \
        and "sans" not in low
    family = "Courier New" if "courier" in low or "mono" in low else \
        "Times New Roman" if serif else "Arial"
    near = font_file(family, bold=block.bold, italic=block.italic)
    _log.info("fontul %s nu e instalat; se foloseste %s", block.font_name,
              near.name if near else "fontul implicit")
    return near


def layout_lines(block: TextBlock, font: Any) -> list[tuple[str, bool]]:
    """F-008, F-104: randurile dupa reflow in latimea blocului; al doilea element
    spune daca randul incheie un paragraf (pentru `justify` si spatiere)."""
    from app.core.pdf.embedded_font import wrap

    out: list[tuple[str, bool]] = []
    for paragraph in block.text.split("\n"):
        parts = wrap(font, paragraph, block.font_size, max(block.rect.w, 1)) or [""]
        out += [(part, i == len(parts) - 1) for i, part in enumerate(parts)]
    return out


def text_height(block: TextBlock, lines: list[tuple[str, bool]]) -> float:
    step = block.font_size * block.line_spacing
    paragraphs = sum(1 for _t, last in lines if last) - 1
    return len(lines) * step + max(paragraphs, 0) * block.paragraph_spacing


def _positions(block: TextBlock, font: Any, text: str, last: bool, x0: float
               ) -> list[tuple[float, str]]:
    alignment = "right" if block.direction == "rtl" and block.alignment == "left" \
        else block.alignment
    width = font.width(text, block.font_size)
    words = text.split(" ")
    if alignment == "center":
        return [(x0 + (block.rect.w - width) / 2, text)]
    if alignment == "right":
        return [(x0 + block.rect.w - width, text)]
    if alignment == "justify" and not last and len(words) > 1:
        gap = (block.rect.w - sum(font.width(w, block.font_size) for w in words)) / \
            (len(words) - 1)
        out, x = [], x0
        for word in words:
            out.append((x, word))
            x += font.width(word, block.font_size) + gap
        return out
    return [(x0, text)]


def draw_block(document: PdfDocument, number: int, block: TextBlock, *,
               cover: str | None = None, cover_rect: Rect | None = None) -> Rect:
    """Deseneaza textul blocului (si, optional, un dreptunghi de acoperire sub
    el). Intoarce zona ocupata. Textul care ar trece de pagina → `ValueError`
    (F-011)."""
    from app.core.pdf.decorate import _num, _rgb
    from app.core.pdf.embedded_font import embed_text_font
    from app.core.pdf.text import page_geometry

    if block.alignment not in ALIGNMENTS:
        raise ValueError(f"aliniere necunoscuta: {block.alignment}")
    if not 1 <= block.font_size <= 1638:
        raise ValueError("dimensiunea fontului e intre 1 si 1638 pt (F-015)")
    pdf = document._pike()
    page = pdf.pages[number - 1]
    left, bottom, height = page_geometry(page)
    page_w, page_h = document.page_size(number)
    path = font_path(block)
    font = embed_text_font(pdf, [block.text], font_path=path)
    lines = layout_lines(block, font)
    area = Rect(block.rect.x, block.rect.y, block.rect.w,
                max(block.rect.h, text_height(block, lines)))
    if area.x < -0.5 or area.y < -0.5 or area.x + area.w > page_w + 0.5 or \
            area.y + area.h > page_h + 0.5:
        raise ValueError("textul trece peste marginile paginii (F-011)")
    ops: list[str] = ["q"]
    if cover is not None:
        target = cover_rect or block.rect
        r, g, b = _rgb(cover)
        ops.append(f"{_num(r)} {_num(g)} {_num(b)} rg {_num(left + target.x)} "
                   f"{_num(bottom + height - target.y - target.h)} {_num(target.w)} "
                   f"{_num(target.h)} re f")
    resource = page.add_resource(font.font, pikepdf.Name.Font, prefix="DLED")
    r, g, b = _rgb(block.color)
    ops.append(f"{_num(r)} {_num(g)} {_num(b)} rg {_num(r)} {_num(g)} {_num(b)} RG")
    real_bold = path is not None and "bold" in path.stem.casefold()
    y = bottom + height - block.rect.y - font.ascent / 1000 * block.font_size
    for text, last in lines:
        positions = _positions(block, font, text, last, left + block.rect.x)
        for x, part in positions:
            skew = 0.21 if block.italic else 0
            mode = f"2 Tr {_num(block.font_size * 0.03)} w " if block.bold and \
                not real_bold else ""
            ops.append(f"BT {mode}{resource} {_num(block.font_size)} Tf 1 0 {_num(skew)} 1 "
                       f"{_num(x)} {_num(y)} Tm {font.encode(part)} Tj ET")
        if block.underline and text:
            start = positions[0][0]
            line_y = y - block.font_size * 0.12
            width = font.width(text, block.font_size)
            ops.append(f"{_num(max(block.font_size * 0.05, 0.5))} w {_num(start)} "
                       f"{_num(line_y)} m {_num(start + width)} {_num(line_y)} l S")
        y -= block.font_size * block.line_spacing + (block.paragraph_spacing if last else 0)
    ops.append("Q")
    page.contents_add(pdf.make_stream(b"q"), prepend=True)
    page.contents_add(pdf.make_stream(b"Q"))
    page.contents_add(pdf.make_stream(" ".join(ops).encode("latin-1")))
    return area
