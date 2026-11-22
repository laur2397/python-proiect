"""Marcajele pe text in PDF (faza 7, pasul 7.2a): C-007…C-010.

Rezultatele cautarii se marcheaza cu adnotari PDF standard (`/Highlight`,
`/Underline`, `/StrikeOut`), cu `QuadPoints` pe fiecare rand si cu aspect
(`/AP`) generat aici, ca marcajul sa se vada la fel in orice cititor PDF
(faza_7_pasi.md, decizia 2). Textul PDF-ului nu se schimba (C-007).

Restul adnotarilor (note, forme, stampile, raspunsuri) vin in pasul 7.4.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.model import AnnotationType, Rect
from app.core.pdf.text import page_geometry, to_pdf_rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument
    from app.core.pdf.text import SearchHit

TEXT_MARKUPS = {
    AnnotationType.HIGHLIGHT: "/Highlight",
    AnnotationType.UNDERLINE: "/Underline",
    AnnotationType.STRIKETHROUGH: "/StrikeOut",
}
"""C-007, C-008, C-009: tipul de marcaj → subtipul adnotarii PDF."""


def pdf_date(moment: datetime | None = None) -> str:
    """Data in formatul PDF: D:AAAALLZZOOMMSSZ (UTC)."""
    moment = moment or datetime.now(UTC)
    return moment.astimezone(UTC).strftime("D:%Y%m%d%H%M%SZ")


def rgb(color: str) -> tuple[float, float, float]:
    """'#RRGGBB' → (r, g, b) intre 0 si 1."""
    value = color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"culoare invalida: {color!r} (se asteapta #RRGGBB)")
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"culoare invalida: {color!r}") from exc
    return r / 255, g / 255, b / 255


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _appearance(pdf: pikepdf.Pdf, kind: AnnotationType, boxes: Sequence[tuple[float, ...]],
                bbox: tuple[float, float, float, float], color: tuple[float, float, float]
                ) -> pikepdf.Stream:
    """Aspectul normal (/AP /N): dreptunghiuri pline in modul Multiply pentru
    evidentiere, o linie sub text sau prin mijlocul lui pentru celelalte."""
    r, g, b = (_num(c) for c in color)
    ops: list[str] = []
    resources = pikepdf.Dictionary()
    if kind is AnnotationType.HIGHLIGHT:
        resources.ExtGState = pikepdf.Dictionary(
            GS0=pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, BM=pikepdf.Name.Multiply))
        ops.append(f"/GS0 gs {r} {g} {b} rg")
        for x0, y0, x1, y1 in boxes:
            ops.append(f"{_num(x0)} {_num(y0)} {_num(x1 - x0)} {_num(y1 - y0)} re f")
    else:
        ops.append(f"{r} {g} {b} RG")
        for x0, y0, x1, y1 in boxes:
            height = y1 - y0
            width = max(0.5, height * 0.07)
            y = y0 + height * 0.1 if kind is AnnotationType.UNDERLINE else y0 + height * 0.45
            ops.append(f"{_num(width)} w {_num(x0)} {_num(y)} m {_num(x1)} {_num(y)} l S")
    stream = pdf.make_stream(" ".join(ops).encode("ascii"))
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = list(bbox)
    stream.Resources = resources
    return stream


# C-007…C-010
def add_text_markup(document: PdfDocument, page_number: int, rects: Sequence[Rect],
                    kind: AnnotationType, color: str, *, author: str | None = None,
                    contents: str | None = None) -> pikepdf.Dictionary:
    """O adnotare de marcaj pe dreptunghiurile date (un dreptunghi pe rand de
    text, in coordonatele din `text.py`). Nu reincarca PDFium: apelantul face
    asta o data, la sfarsit."""
    kind = AnnotationType(kind)
    if kind not in TEXT_MARKUPS:
        raise ValueError(f"nu e un marcaj pe text: {kind.value}")
    if not rects:
        raise ValueError("marcajul are nevoie de cel putin un dreptunghi")
    pdf = document._pike()
    page = pdf.pages[page_number - 1]
    geometry = page_geometry(page)
    boxes = [to_pdf_rect(geometry, r) for r in rects]
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))
    quads: list[float] = []
    for x0, y0, x1, y1 in boxes:  # ordinea uzuala: sus-stanga, sus-dreapta, jos-stanga, jos-dreapta
        quads += [x0, y1, x1, y1, x0, y0, x1, y0]
    color_rgb = rgb(color)
    now = pdf_date()
    annot = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name(TEXT_MARKUPS[kind]),
        Rect=list(bbox),
        QuadPoints=quads,
        C=list(color_rgb),
        F=4,  # se tipareste
        NM=pikepdf.String(uuid.uuid4().hex),
        M=pikepdf.String(now),
        CreationDate=pikepdf.String(now),
        P=page.obj,
    )
    if author:
        annot.T = pikepdf.String(author)
    if contents:
        annot.Contents = pikepdf.String(contents)
    annot.AP = pikepdf.Dictionary(N=_appearance(pdf, kind, boxes, bbox, color_rgb))
    indirect = pdf.make_indirect(annot)
    if "/Annots" not in page.obj:
        page.obj.Annots = pdf.make_indirect(pikepdf.Array())
    page.obj.Annots.append(indirect)
    return indirect


def mark_hits(document: PdfDocument, hits: Sequence[SearchHit], kind: AnnotationType,
              color: str, *, author: str | None = None) -> int:
    """C-007…C-009: cate o adnotare pentru fiecare rezultat din textul paginii.
    Rezultatele din comentarii, semne de carte si metadate nu au text in pagina
    si se sar. Intoarce numarul de adnotari create."""
    from app.core.pdf.text import SOURCE_TEXT

    count = 0
    for hit in hits:
        if hit.source != SOURCE_TEXT or hit.page < 1 or not hit.rects:
            continue
        add_text_markup(document, hit.page, hit.rects, kind, color, author=author)
        count += 1
    if count:
        document._changed()
    return count


def default_color(settings: Any, kind: AnnotationType) -> str:
    """C-010: culoarea implicita a unui marcaj, din setari."""
    return str(settings.get(f"pdf_editor.markup_color.{AnnotationType(kind).value}"))
