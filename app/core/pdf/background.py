"""Recunoasterea in fundal si stratul de text permanent (faza 7, pasul 7.6):
B-028…B-033.

- Recunoasterea in fundal (B-028) da paginilor fara text un strat de text
  **temporar**, numai in memorie: cautarea, copierea si marcajele il folosesc,
  dar nu se scrie niciodata in fisier (B-029). Un esec nu afiseaza nimic:
  pagina ramane cu textul ei, iar evenimentul se noteaza in jurnal.
- Pe un procesor cu un singur nucleu functia e dezactivata (B-030); se poate
  dezactiva si din `Options` (B-033, setarea `image.background_recognition_pdf`).
- `recognize_and_store` (B-032) scrie stratul de text permanent: textul
  invizibil se adauga peste continutul paginii, care ramane neatins.

INCOMPLET, marcat: din optiunile lui B-032 se folosesc limbile; corectia de
orientare si indreptarea (deskew) nu se aplica inca, pentru ca pozitiile
cuvintelor ar trebui intoarse in geometria paginii originale.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf
from PIL import Image

from app.core.applog import get_logger
from app.core.model import CancelToken, Progress, ProgressCallback, Rect
from app.core.pdf.text import PageText, page_geometry

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.pdf.document import PdfDocument

_log = get_logger("pdf.background")

OCR_DPI = 300
"""Rezolutia la care se randeaza o pagina pentru recunoastere."""

WARNING_CHECK_LANGUAGES = "warning.check_ocr_languages"
"""B-031: cand cautarea sau copierea nu merg, prima verificare e setul de limbi."""

SETTING = "image.background_recognition_pdf"
"""B-033: activarea recunoasterii in fundal (X-010)."""


# B-030
def available() -> bool:
    """Recunoasterea in fundal nu ruleaza pe un procesor cu un singur nucleu."""
    return (os.cpu_count() or 1) > 1


def enabled(settings: Any) -> bool:
    """B-028, B-030, B-033: activa implicit, daca procesorul permite."""
    return bool(settings.get(SETTING)) and available()


def pages_without_text(document: PdfDocument) -> list[int]:
    """B-028: paginile care nu au strat de text in fisier si nici unul temporar."""
    return [n for n in range(1, document.page_count + 1)
            if not document.has_text_layer(n) and n not in document._ocr_layer]


# --- recunoasterea unei imagini -------------------------------------------------------


def ocr_lines(image: Image.Image, *, context: AppContext | None = None, engine: Any = None,
              languages: Sequence[str] | None = None, dpi: int = OCR_DPI
              ) -> list[list[tuple[str, Rect]]]:
    """Randurile recunoscute in imagine, fiecare o lista de (cuvant, dreptunghi
    in pixelii imaginii), intr-un proiect OCR temporar."""
    from app.core.model import AutoProcessMode, _area_blocks
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject

    with tempfile.TemporaryDirectory(prefix="doculens-bg-") as tmp:
        source = Path(tmp) / "pagina.png"
        image.save(source, dpi=(dpi, dpi))
        project = OcrProject.create(context=context)
        try:
            if languages:
                settings = project.settings()
                settings.set("lang.mode", "manual")
                settings.set("lang.manual", list(languages))
            project.add_images([source], auto_process=AutoProcessMode.NONE)
            RecognitionService(project, engine=engine).recognize_pages()
            page = project.pages[0]
            lines: list[list[tuple[str, Rect]]] = []
            for area in page._ordered_areas():
                for block in _area_blocks(area):
                    for line in block.lines:
                        words = [(w.text, w.bbox) for w in line.words if w.text]
                        if words:
                            lines.append(words)
            return lines
        finally:
            project.close()


def _page_text(number: int, lines: Sequence[Sequence[tuple[str, Rect]]],
               page: pikepdf.Page, dpi: int) -> PageText:
    """Stratul temporar al paginii: textul si dreptunghiul fiecarui caracter, in
    coordonatele din `text.py` (puncte, sus-stanga MediaBox)."""
    from app.core.pdf.redact import _frame

    frame = _frame(page, dpi)
    mx0, _my0, _mx1, my1 = frame.media
    cx0, _cy0, _cx1, cy1 = frame.crop
    dx, dy = cx0 - mx0, my1 - cy1
    chars: list[str] = []
    boxes: list[Rect | None] = []
    for li, line in enumerate(lines):
        if li:
            chars.append("\n")
            boxes.append(None)
        for wi, (word, box) in enumerate(line):
            if wi:
                chars.append(" ")
                boxes.append(None)
            x, y = dx + box.x / frame.scale, dy + box.y / frame.scale
            w, h = box.w / frame.scale, box.h / frame.scale
            step = w / max(1, len(word))
            for ci, ch in enumerate(word):
                chars.append(ch)
                boxes.append(Rect(x + ci * step, y, step, h))
    left, bottom, height = page_geometry(page)
    return PageText(number, "".join(chars), tuple(boxes), height, bottom, left)


def _recognize_page(document: PdfDocument, number: int, *, context: AppContext | None,
                    engine: Any, languages: Sequence[str] | None) -> PageText:
    from app.core.pdf.redact import _frame, _render

    page = document._pike().pages[number - 1]
    image = _render(document, number, _frame(page, OCR_DPI))
    lines = ocr_lines(image, context=context, engine=engine, languages=languages)
    return _page_text(number, lines, page, OCR_DPI)


def _targets(document: PdfDocument, pages: Sequence[int] | None) -> list[int]:
    total = document.page_count
    chosen = list(pages) if pages is not None else list(range(1, total + 1))
    bad = [n for n in chosen if not 1 <= n <= total]
    if bad:
        raise ValueError(f"paginile {bad} nu exista (1..{total})")
    return chosen


# B-028, B-029
def recognize_in_background(document: PdfDocument, *, pages: Sequence[int] | None = None,
                            progress: ProgressCallback | None = None,
                            cancel: CancelToken | None = None,
                            context: AppContext | None = None, engine: Any = None,
                            languages: Sequence[str] | None = None) -> list[int]:
    """Strat de text temporar pentru paginile fara text (dintre cele date). Un
    esec pe o pagina se noteaza si se trece mai departe, fara exceptie (B-028).
    Intoarce paginile care au primit text."""
    if not available():
        _log.info("recunoasterea in fundal e dezactivata: un singur nucleu (B-030)")
        return []
    wanted = [n for n in _targets(document, pages)
              if not document.has_text_layer(n) and n not in document._ocr_layer]
    done: list[int] = []
    for i, number in enumerate(wanted):
        if cancel is not None and cancel():
            break
        if progress is not None:
            progress(Progress(i, len(wanted), "stage.recognizing", str(number)))
        try:
            layer = _recognize_page(document, number, context=context, engine=engine,
                                    languages=languages)
        except Exception as exc:  # noqa: BLE001 - B-028: fara mesaj intruziv
            _log.warning("recunoasterea in fundal a esuat pe pagina %d: %s", number, exc)
            continue
        if any(not ch.isspace() for ch in layer.text):
            document._ocr_layer[number] = layer
            done.append(number)
    if progress is not None:
        progress(Progress(len(wanted), len(wanted), "stage.recognizing", ""))
    return done


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _words(layer: PageText) -> list[tuple[str, Rect]]:
    words: list[tuple[str, Rect]] = []
    current: list[tuple[str, Rect]] = []
    for ch, box in [*zip(layer.text, layer.boxes, strict=True), (" ", None)]:
        if box is not None and not ch.isspace():
            current.append((ch, box))
            continue
        if current:
            x0 = min(b.x for _c, b in current)
            y0 = min(b.y for _c, b in current)
            x1 = max(b.x + b.w for _c, b in current)
            y1 = max(b.y + b.h for _c, b in current)
            words.append(("".join(c for c, _b in current), Rect(x0, y0, x1 - x0, y1 - y0)))
            current = []
    return words


def _store_layer(document: PdfDocument, number: int, layer: PageText) -> None:
    """Textul invizibil se adauga dupa continutul paginii; continutul vechi e
    inchis intre q/Q, ca starea lui grafica sa nu se scurga in text."""
    from app.core.export.pdf import _font_object

    pdf = document._pike()
    page = pdf.pages[number - 1]
    words = _words(layer)
    if not words:
        return
    chars = sorted({c for word, _r in words for c in word})
    gid = {c: i + 1 for i, c in enumerate(chars)}
    name = page.add_resource(_font_object(pdf, chars), pikepdf.Name.Font, prefix="FOCR")
    left, bottom, height = page_geometry(page)
    top = bottom + height
    ops = ["Q", "q", "BT", "3 Tr"]
    for word, r in words:
        if r.w <= 0 or r.h <= 0:
            continue
        scale = 100.0 * r.w / (len(word) * r.h)
        codes = "".join(f"{gid[c]:04X}" for c in word)
        ops.append(f"{name} {_fmt(r.h)} Tf {_fmt(scale)} Tz 1 0 0 1 {_fmt(left + r.x)} "
                   f"{_fmt(top - r.y - 0.8 * r.h)} Tm <{codes}> Tj")
    ops += ["ET", "Q"]
    page.contents_add(pdf.make_stream(b"q\n"), prepend=True)
    page.contents_add(pdf.make_stream(("\n".join(ops) + "\n").encode("ascii")))


# B-032, E-036
def recognize_and_store(document: PdfDocument, *, pages: Sequence[int] | None = None,
                        languages: Sequence[str] | None = None,
                        progress: ProgressCallback | None = None,
                        cancel: CancelToken | None = None,
                        context: AppContext | None = None, engine: Any = None) -> list[int]:
    """Strat de text permanent pentru paginile fara text: fisierul se modifica
    (interfata confirma intai, B-032). Paginile cu text in fisier se sar; un
    strat temporar existent se refoloseste, daca nu s-au cerut alte limbi.
    Intoarce paginile care au primit text."""
    wanted = [n for n in _targets(document, pages) if not document.has_text_layer(n)]
    stored: list[int] = []
    for i, number in enumerate(wanted):
        if cancel is not None and cancel():
            break
        if progress is not None:
            progress(Progress(i, len(wanted), "stage.recognizing", str(number)))
        layer = None if languages else document._ocr_layer.get(number)
        if layer is None:
            layer = _recognize_page(document, number, context=context, engine=engine,
                                    languages=languages)
        if any(not ch.isspace() for ch in layer.text):
            _store_layer(document, number, layer)
            stored.append(number)
    if stored:
        document._changed()
        for number in stored:
            document._ocr_layer.pop(number, None)
    return stored
