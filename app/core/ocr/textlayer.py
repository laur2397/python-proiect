"""Stratul de text al PDF-urilor: citire, evaluare, alegerea modului.

Pasul 4.4 din docs/plan/faza_4_pasi.md (N-008..N-012). Folosit de
RecognitionService.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from app.core.model import BlockData, LineData, PdfRecognitionMode, Rect, WordData
from app.core.pdf.document import PDFIUM_LOCK

TEXT_LAYER_MIN_QUALITY = 0.8
"""[DECIZIE] N-011: sub aceasta nota, stratul de text se ignora si pagina
trece pe OCR."""

SCANNED_IMAGE_SHARE = 0.8
"""N-009: o imagine care acopera cel putin 80% din pagina inseamna pagina
scanata (cautabila sau doar-imagine): mereu OCR."""

_WORD = re.compile(r"^[^\W\d_]{2,}[.,;:!?)]*$")


@dataclass(slots=True)
class PdfPageText:
    words: list[tuple[str, tuple[float, float, float, float]]]
    """(cuvant, (stanga, jos, dreapta, sus) in puncte)."""
    width_pt: float
    height_pt: float
    image_boxes: list[tuple[float, float, float, float]]
    """Imaginile din pagina, (stanga, jos, dreapta, sus) in puncte."""


def read_page(path: Path, page_number: int) -> PdfPageText | None:
    """Cuvintele stratului de text si imaginile unei pagini; None daca PDF-ul
    nu se poate deschide (de exemplu cere parola)."""
    try:
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(Path(path))
    except (pdfium.PdfiumError, FileNotFoundError, OSError):
        return None
    try:
        with PDFIUM_LOCK:
            page = doc[page_number - 1]
            width, height = page.get_size()
            textpage = page.get_textpage()
            words: list[tuple[str, tuple[float, float, float, float]]] = []
            current, box = "", None
            for i in range(textpage.count_chars()):
                ch = textpage.get_text_range(i, 1)
                if not ch or ch.isspace():
                    if current:
                        words.append((current, box))
                    current, box = "", None
                    continue
                left, bottom, right, top = textpage.get_charbox(i)
                current += ch
                box = (left, bottom, right, top) if box is None else (
                    min(box[0], left), min(box[1], bottom), max(box[2], right), max(box[3], top))
            if current:
                words.append((current, box))
            images = [obj.get_bounds() for obj in page.get_objects(
                filter=[pdfium_raw.FPDF_PAGEOBJ_IMAGE])]
            textpage.close()
            page.close()
        return PdfPageText(words, float(width), float(height), images)
    finally:
        with PDFIUM_LOCK:
            doc.close()


def is_scanned(text: PdfPageText) -> bool:
    """N-009: pagina e o imagine (cu sau fara text ascuns peste ea)."""
    area = text.width_pt * text.height_pt
    return any((r - le) * (t - b) >= SCANNED_IMAGE_SHARE * area
               for le, b, r, t in text.image_boxes)


# N-011
def evaluate(text: PdfPageText) -> float:
    """Nota stratului de text, 0..1: cuvinte reale, codificare corecta, text
    destul pe pagina. INCOMPLET, marcat: „cuvintele din dictionar” vin cu
    dictionarele (faza 4b); acum se numara cuvintele formate din litere."""
    if not text.words:
        return 0.0
    tokens = [w for w, _ in text.words]
    joined = "".join(tokens)
    bad = sum(1 for c in joined if c == "�" or (ord(c) < 32) or 0xE000 <= ord(c) <= 0xF8FF)
    encoding = 1.0 - bad / max(1, len(joined))
    wordlike = sum(1 for w in tokens if _WORD.match(w)) / len(tokens)
    amount = min(1.0, len(joined) / 100)
    return round(min(encoding, 1.0) * (0.7 * wordlike + 0.3) * (0.5 + 0.5 * amount), 3)


# N-008, N-009, N-010
def choose_mode(text: PdfPageText | None, requested: PdfRecognitionMode) -> PdfRecognitionMode:
    """TEXT_ONLY: se foloseste stratul de text; FORCE_OCR: se recunoaste.
    Paginile scanate si cele fara strat de text folosesc mereu OCR (N-009)."""
    if text is None or not text.words or is_scanned(text):
        return PdfRecognitionMode.FORCE_OCR
    if requested is PdfRecognitionMode.FORCE_OCR:
        return PdfRecognitionMode.FORCE_OCR
    if requested is PdfRecognitionMode.TEXT_ONLY:
        return PdfRecognitionMode.TEXT_ONLY
    return (PdfRecognitionMode.TEXT_ONLY if evaluate(text) >= TEXT_LAYER_MIN_QUALITY
            else PdfRecognitionMode.FORCE_OCR)


def to_blocks(text: PdfPageText, width_px: int, height_px: int,
              language: str | None) -> list[BlockData]:
    """Cuvintele stratului de text, in pixelii paginii, grupate pe randuri."""
    sx, sy = width_px / text.width_pt, height_px / text.height_pt
    lines: list[LineData] = []
    for word, (left, bottom, right, top) in text.words:
        box = Rect(round(left * sx), round((text.height_pt - top) * sy),
                   max(1, round((right - left) * sx)), max(1, round((top - bottom) * sy)))
        w = WordData(None, word, 100.0, bbox=box, language_code=language)
        line = lines[-1] if lines else None
        if line and abs((line.bbox.y + line.bbox.h / 2) - (box.y + box.h / 2)) < box.h / 2:
            line.words.append(w)
            x0, y0 = min(line.bbox.x, box.x), min(line.bbox.y, box.y)
            line.bbox = Rect(x0, y0, max(line.bbox.right, box.right) - x0,
                             max(line.bbox.bottom, box.bottom) - y0)
        else:
            lines.append(LineData(None, words=[w], bbox=box))
    if not lines:
        return []
    x0 = min(ln.bbox.x for ln in lines)
    y0 = min(ln.bbox.y for ln in lines)
    box = Rect(x0, y0, max(ln.bbox.right for ln in lines) - x0,
               max(ln.bbox.bottom for ln in lines) - y0)
    return [BlockData(None, lines=lines, bbox=box)]


def image_rects(text: PdfPageText, width_px: int, height_px: int) -> list[Rect]:
    """Imaginile paginii, in pixeli (pentru OCR pe documentele mixte, N-012)."""
    sx, sy = width_px / text.width_pt, height_px / text.height_pt
    out = []
    for left, bottom, right, top in text.image_boxes:
        x0, y0 = max(0, round(left * sx)), max(0, round((text.height_pt - top) * sy))
        x1, y1 = min(width_px, round(right * sx)), min(height_px, round((text.height_pt - bottom) * sy))
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            out.append(Rect(x0, y0, x1 - x0, y1 - y0))
    return out
