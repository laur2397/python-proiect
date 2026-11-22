"""Rescrierea unei pagini PDF pentru redactare si inlocuire (faza 7, pasul 7.2b):
C-015…C-018, C-025, C-026, G-020, G-021.

[DECIZIE AUTONOMA] (faza_7_pasi.md, decizia 11) Pagina atinsa se reconstruieste:
imaginea ei (randata la `REBUILD_DPI`, fara adnotari), cu zonele acoperite
(culoarea redactarii sau fondul detectat la inlocuire, C-018) si cu textul nou
desenat, plus un strat de text invizibil numai cu caracterele care raman.
Continutul vechi al paginii (fluxuri, fonturi, imagini) iese din pagina, deci
textul redactat nu mai exista in fisier, iar verificarea G-021 il cauta din nou.

INCOMPLET, marcat: pe un PDF cu text vectorial, inlocuirea face pagina imagine
cu strat de text; editarea reala a textului, cu fontul documentului, vine cu
editarea de continut (F-*, faza 9).
"""

from __future__ import annotations

import io
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
from PIL import Image, ImageDraw, ImageFont

from app.core.errors import RedactionVerificationError
from app.core.model import Rect
from app.core.pdf.text import (
    PageText,
    find_all,
    from_pdf_rect,
    page_geometry,
    read_page_text,
)

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

REBUILD_DPI = 300
"""Rezolutia imaginii unei pagini reconstruite."""

PADDING_PT = 0.75
"""Zona acoperita depaseste cu putin dreptunghiul textului, ca marginile literelor
sa nu ramana vizibile in imagine."""

UNIFORM_TOLERANCE = 24
"""C-018: abaterea maxima (0..255) a fondului din jurul unei zone ca sa fie uniform."""


@dataclass(frozen=True, slots=True)
class PageEdit:
    """O zona de pe pagina: se acopera cu `fill` (None = fondul detectat) si,
    optional, primeste textul `text` (inlocuire)."""

    rect: Rect
    fill: str | None = "#000000"
    text: str = ""


# --- geometria randarii ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Frame:
    """Legatura dintre coordonatele din `text.py` (MediaBox, sus-stanga) si
    pixelii imaginii paginii (CropBox, nerotita)."""

    media: tuple[float, float, float, float]
    crop: tuple[float, float, float, float]
    rotate: int
    scale: float

    def to_pixels(self, rect: Rect, pad: float = 0.0) -> tuple[int, int, int, int]:
        mx0, _my0, _mx1, my1 = self.media
        cx0, _cy0, _cx1, cy1 = self.crop
        x0 = (mx0 + rect.x - pad - cx0) * self.scale
        y0 = (cy1 - (my1 - rect.y + pad)) * self.scale
        x1 = x0 + (rect.w + 2 * pad) * self.scale
        y1 = y0 + (rect.h + 2 * pad) * self.scale
        return round(x0), round(y0), round(x1), round(y1)


def _box(values: Sequence[float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(v) for v in values)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _frame(page: pikepdf.Page, dpi: int) -> _Frame:
    media = _box(page.mediabox)
    crop = _box(page.obj.get("/CropBox", page.mediabox))
    crop = (max(crop[0], media[0]), max(crop[1], media[1]),
            min(crop[2], media[2]), min(crop[3], media[3]))
    rotate = int(page.obj.get("/Rotate", 0)) % 360
    return _Frame(media, crop, rotate, dpi / 72)


def _render(document: PdfDocument, number: int, frame: _Frame) -> Image.Image:
    """Pagina fara adnotari, nerotita (rotatia /Rotate se pastreaza in pagina)."""
    from app.core.pdf.document import PDFIUM_LOCK

    doc = document._require_open()
    with PDFIUM_LOCK:
        page = doc[number - 1]
        try:
            bitmap = page.render(scale=frame.scale, rotation=(360 - frame.rotate) % 360,
                                 may_draw_forms=False, draw_annots=False)
            return bitmap.to_pil().convert("RGB")
        finally:
            page.close()


# --- fondul si culorile ---------------------------------------------------------------


def _hex(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"culoare invalida: {color!r} (se asteapta #RRGGBB)")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _ring(image: Image.Image, box: tuple[int, int, int, int], width: int = 3
          ) -> list[tuple[int, int, int]]:
    """Pixelii de pe conturul din afara zonei (fondul din jurul textului)."""
    x0, y0, x1, y1 = box
    rgb = image.convert("RGB")
    points = [(x, y) for x in range(x0 - width, x1 + width)
              for y in (*range(y0 - width, y0), *range(y1, y1 + width))]
    points += [(x, y) for y in range(y0, y1)
               for x in (*range(x0 - width, x0), *range(x1, x1 + width))]
    return [rgb.getpixel(p) for p in points  # type: ignore[misc]
            if 0 <= p[0] < image.width and 0 <= p[1] < image.height]


def _median(pixels: Sequence[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not pixels:
        return 255, 255, 255
    r, g, b = (int(statistics.median(p[i] for p in pixels)) for i in range(3))
    return r, g, b


def _uniform(pixels: Sequence[tuple[int, int, int]]) -> bool:
    if not pixels:
        return True
    center = _median(pixels)
    far = sum(1 for p in pixels if max(abs(p[i] - center[i]) for i in range(3))
              > UNIFORM_TOLERANCE)
    return far <= 0.05 * len(pixels)


# C-018
def background_is_uniform(document: PdfDocument, number: int, rect: Rect) -> bool:
    """C-018: fondul din jurul zonei e uniform? Daca nu, apelantul avertizeaza
    inainte de inlocuire (textul vechi se acopera cu o singura culoare)."""
    page = document._pike().pages[number - 1]
    frame = _frame(page, REBUILD_DPI)
    image = _render(document, number, frame)
    return _uniform(_ring(image, frame.to_pixels(rect, PADDING_PT)))


# --- fontul textului nou --------------------------------------------------------------

_FONT_CANDIDATES = ("Arial.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
                    "NotoSans-Regular.ttf", "segoeui.ttf", "Helvetica.ttc", "Verdana.ttf")
_ROMANIAN = "ăâîșțĂÂÎȘȚ"


@lru_cache(maxsize=1)
def text_font_file() -> Path | None:
    """Un font de sistem fara serife care are diacriticele romanesti, pentru
    textul nou desenat la inlocuire. None = se foloseste fontul din Pillow."""
    from fontTools.ttLib import TTFont

    from app.core.fonts import _font_dirs

    for folder in _font_dirs():
        if not folder.is_dir():
            continue
        for name in _FONT_CANDIDATES:
            for path in folder.rglob(name):
                try:
                    with TTFont(str(path), fontNumber=0, lazy=True) as font:
                        cmap = font.getBestCmap() or {}
                except (OSError, ValueError, KeyError, AssertionError):  # font stricat
                    continue
                if all(ord(ch) in cmap for ch in _ROMANIAN):
                    return path
    return None


def _font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = text_font_file()
    if path is not None:
        return ImageFont.truetype(str(path), max(1, size_px))
    return ImageFont.load_default(max(1, size_px))


def _draw_text(image: Image.Image, box: tuple[int, int, int, int], text: str) -> float:
    """Textul nou, pe un rand, cat inaltimea zonei; intoarce latimea lui in pixeli."""
    x0, y0, x1, y1 = box
    height = max(1, y1 - y0)
    draw = ImageDraw.Draw(image)
    size = max(1, int(height * 0.8))
    font = _font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    limit = (x1 - x0) * 1.5
    if right - left > limit > 0:  # textul nou mult mai lung: se micsoreaza
        size = max(1, int(size * limit / (right - left)))
        font = _font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    y = y0 + (height - (bottom - top)) / 2 - top
    draw.text((x0 - left, y), text, font=font, fill=(0, 0, 0))
    return float(right - left)


# --- stratul de text invizibil --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Word:
    text: str
    rect: Rect


def _inside(box: Rect, rects: Sequence[Rect]) -> bool:
    cx, cy = box.x + box.w / 2, box.y + box.h / 2
    return any(r.x <= cx <= r.x + r.w and r.y <= cy <= r.y + r.h for r in rects)


def _kept_words(page: PageText, removed: Sequence[Rect]) -> list[_Word]:
    """Cuvintele care raman: caracterele al caror centru nu e in nicio zona."""
    words: list[_Word] = []
    chars: list[tuple[str, Rect]] = []

    def flush() -> None:
        if chars:
            x0 = min(r.x for _, r in chars)
            y0 = min(r.y for _, r in chars)
            x1 = max(r.x + r.w for _, r in chars)
            y1 = max(r.y + r.h for _, r in chars)
            words.append(_Word("".join(c for c, _ in chars), Rect(x0, y0, x1 - x0, y1 - y0)))
            chars.clear()

    for ch, box in zip(page.text, page.boxes, strict=True):
        if box is None or ch.isspace() or not box.w or not box.h or _inside(box, removed):
            flush()
            continue
        if chars and abs(chars[-1][1].y - box.y) > box.h * 0.5:
            flush()
        chars.append((ch, box))
    flush()
    return words


def _split_words(word: _Word) -> list[_Word]:
    """Textul nou impartit in cuvinte, cu latimea proportionala cu numarul de
    litere, ca stratul de text sa aiba spatiile intre cuvinte."""
    unit = word.rect.w / max(1, len(word.text))
    out: list[_Word] = []
    pos = 0
    for part in word.text.split():
        start = word.text.index(part, pos)
        out.append(_Word(part, Rect(word.rect.x + start * unit, word.rect.y,
                                    len(part) * unit, word.rect.h)))
        pos = start + len(part)
    return out


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _text_layer(words: Sequence[_Word], geometry: tuple[float, float, float],
                gid: dict[str, int]) -> str:
    left, bottom, height = geometry
    top = bottom + height
    ops: list[str] = []
    for word in words:
        r = word.rect
        if r.w <= 0 or r.h <= 0:
            continue
        x, y = left + r.x, top - r.y - r.h
        scale = 100.0 * r.w / (len(word.text) * r.h)
        codes = "".join(f"{gid[c]:04X}" for c in word.text)
        ops.append(f"/FR {_fmt(r.h)} Tf {_fmt(scale)} Tz 1 0 0 1 {_fmt(x)} "
                   f"{_fmt(y + 0.2 * r.h)} Tm <{codes}> Tj")
    return ("BT 3 Tr\n" + "\n".join(ops) + "\nET\n") if ops else ""


# --- reconstruirea paginii ------------------------------------------------------------


def _image_stream(pdf: pikepdf.Pdf, image: Image.Image) -> pikepdf.Stream:
    gray = image.convert("L")
    is_gray = gray.convert("RGB").tobytes() == image.tobytes()
    out = io.BytesIO()
    (gray if is_gray else image).save(out, "JPEG", quality=90, optimize=True)
    return pdf.make_stream(out.getvalue(), Type=pikepdf.Name.XObject,
                           Subtype=pikepdf.Name.Image, Width=image.width,
                           Height=image.height, BitsPerComponent=8,
                           ColorSpace=pikepdf.Name.DeviceGray if is_gray
                           else pikepdf.Name.DeviceRGB,
                           Filter=pikepdf.Name.DCTDecode)


def _intersects(a: Rect, b: Rect) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def rebuild_page(document: PdfDocument, number: int, edits: Sequence[PageEdit], *,
                 remove_annotations: bool) -> None:
    """Rescrie pagina `number` cu zonele `edits` acoperite. Cu
    `remove_annotations`, adnotarile care ating o zona dispar (redactare, G-020).
    Nu reincarca PDFium: apelantul face `document._changed()` dupa toate paginile."""
    from app.core.export.pdf import _font_object

    if not edits:
        return
    pdf = document._pike()
    page = pdf.pages[number - 1]
    frame = _frame(page, REBUILD_DPI)
    geometry = page_geometry(page)
    image = _render(document, number, frame)
    page_text = read_page_text(document._require_open(), number)
    draw = ImageDraw.Draw(image)
    words = _kept_words(page_text, [e.rect for e in edits])
    for edit in edits:
        box = frame.to_pixels(edit.rect, PADDING_PT)
        color = _hex(edit.fill) if edit.fill else _median(_ring(image, box))
        draw.rectangle(box, fill=color)
        if edit.text:
            width_pt = _draw_text(image, box, edit.text) / frame.scale
            words += _split_words(_Word(edit.text, Rect(edit.rect.x, edit.rect.y, width_pt,
                                                        edit.rect.h)))
    chars = sorted({c for w in words for c in w.text})
    gid = {c: i + 1 for i, c in enumerate(chars)}
    resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(ImR=_image_stream(pdf, image)))
    if chars:
        resources.Font = pikepdf.Dictionary(FR=_font_object(pdf, chars))
    cx0, cy0, cx1, cy1 = frame.crop
    body = (f"q {_fmt(cx1 - cx0)} 0 0 {_fmt(cy1 - cy0)} {_fmt(cx0)} {_fmt(cy0)} cm "
            f"/ImR Do Q\n" + _text_layer(words, geometry, gid))
    page.obj.Contents = pdf.make_stream(body.encode("ascii"))
    page.obj.Resources = resources
    if remove_annotations and "/Annots" in page.obj:
        rects = [e.rect for e in edits]
        kept = [a for a in page.obj.Annots
                if "/Rect" not in a
                or not any(_intersects(from_pdf_rect(geometry, a.Rect), r) for r in rects)]
        page.obj.Annots = pdf.make_indirect(pikepdf.Array(kept))


# --- verificarea (G-021) --------------------------------------------------------------


def verify_removed(document: PdfDocument, number: int, rects: Sequence[Rect],
                   words: Sequence[tuple[str, bool, bool]] = ()) -> None:
    """G-021: dupa redactare, pagina nu mai are niciun caracter in zonele
    redactate si nici textul cautat (`words`: text, majuscule, cuvant intreg).
    Altfel `RedactionVerificationError`."""
    page = read_page_text(document._require_open(), number)
    for ch, box in zip(page.text, page.boxes, strict=True):
        if box is not None and _inside(box, rects):
            raise RedactionVerificationError("textul redactat se gaseste inca in pagina",
                                             page_number=number, found_text=ch)
    for text, match_case, whole_word in words:
        if find_all(page.text, text, match_case=match_case, whole_word=whole_word):
            raise RedactionVerificationError("textul redactat se gaseste inca in pagina",
                                             page_number=number, found_text=text)
