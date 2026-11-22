"""Textul paginilor PDF si cautarea in document (faza 7, pasul 7.2a): C-002…C-006.

Coordonatele unui rezultat: puncte (1/72 inch), cu originea in coltul din
stanga-sus al paginii (MediaBox) si y in jos, ca la zonele din OCR Editor.
`to_pdf_rect` le intoarce in sistemul PDF (originea jos).

Cautarea compara literele dupa CLAUDE.md §6.4: varianta cu sedila si cea cu
virgula a lui ș/ț sunt aceeasi litera (ş = ș, ţ = ț), oricum ar fi scrise in
document sau in campul de cautare.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

import pikepdf
import pypdfium2 as pdfium

from app.core.model import Rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

SOURCE_TEXT = "text"
SOURCE_COMMENTS = "comments"
SOURCE_BOOKMARKS = "bookmarks"
SOURCE_METADATA = "metadata"
SOURCES = (SOURCE_TEXT, SOURCE_COMMENTS, SOURCE_BOOKMARKS, SOURCE_METADATA)
"""C-002: sursele dupa care se grupeaza rezultatele, in ordinea afisarii."""

CONTEXT_CHARS = 30
"""Cate caractere de o parte si de alta a rezultatului intra in context."""

_FOLD = str.maketrans({"ş": "ș", "ţ": "ț", "Ş": "Ș", "Ţ": "Ț"})


def fold(text: str, match_case: bool) -> str:
    """Forma de comparatie, cu aceeasi lungime ca textul: sedila → virgula si,
    fara `match_case`, litere mici (o litera care s-ar lungi ramane cum e)."""
    text = text.translate(_FOLD)
    if match_case:
        return text
    return "".join(low if len(low := ch.lower()) == 1 else ch for ch in text)


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


# C-002, C-003, C-004
def find_all(text: str, query: str, *, match_case: bool = False,
             whole_word: bool = False) -> list[tuple[int, int]]:
    """(inceput, lungime) pentru fiecare aparitie, fara suprapuneri.
    `whole_word` (C-003, `Exact Match`): numai cuvinte intregi."""
    if not query:
        raise ValueError("textul cautat trebuie sa aiba cel putin un caracter (C-002)")
    hay, needle = fold(text, match_case), fold(query, match_case)
    found: list[tuple[int, int]] = []
    start = 0
    while (i := hay.find(needle, start)) >= 0:
        end = i + len(needle)
        ok = not whole_word or (
            (i == 0 or not _is_word_char(hay[i - 1]))
            and (end == len(hay) or not _is_word_char(hay[end])))
        if ok:
            found.append((i, len(needle)))
            start = end
        else:
            start = i + 1
    return found


def find_pattern(text: str, pattern: str, *, match_case: bool = False
                 ) -> list[tuple[int, int]]:
    """Ca `find_all`, pentru o expresie regulata (listele de cuvinte cheie, C-028)."""
    flags = 0 if match_case else re.IGNORECASE
    regex = re.compile(fold(pattern, True), flags)
    return [(m.start(), m.end() - m.start())
            for m in regex.finditer(fold(text, True)) if m.end() > m.start()]


def context_of(text: str, start: int, length: int) -> str:
    """Rezultatul cu cateva cuvinte in jur, pe un singur rand."""
    left = max(0, start - CONTEXT_CHARS)
    right = min(len(text), start + length + CONTEXT_CHARS)
    snippet = " ".join(text[left:right].split())
    return ("…" if left else "") + snippet + ("…" if right < len(text) else "")


class SearchHit(tuple):
    """Un rezultat: tuplul din SPEC_05 `(pagina, dreptunghi, context)`, plus
    sursa (C-002), pozitia in textul paginii si dreptunghiurile pe randuri
    (pentru marcaje, C-007…C-009). Pagina 0 = rezultat fara pagina (metadate,
    semne de carte fara destinatie)."""

    source: str
    start: int
    length: int
    rects: tuple[Rect, ...]
    found: str

    def __new__(cls, page: int, rect: Rect, context: str, *, source: str = SOURCE_TEXT,
                start: int = -1, length: int = 0, rects: Sequence[Rect] = (),
                found: str = "") -> Self:
        self = super().__new__(cls, (page, rect, context))
        self.source = source
        self.start = start
        self.length = length
        self.rects = tuple(rects) or ((rect,) if rect.w and rect.h else ())
        self.found = found
        return self

    @property
    def page(self) -> int:
        return self[0]

    @property
    def rect(self) -> Rect:
        return self[1]

    @property
    def context(self) -> str:
        return self[2]


# --- textul unei pagini -----------------------------------------------------------------


@dataclass(frozen=True)
class PageText:
    """Textul unei pagini si dreptunghiul fiecarui caracter (None pentru
    spatii si sfarsituri de rand)."""

    number: int
    text: str
    boxes: tuple[Rect | None, ...]
    height: float
    """Inaltimea MediaBox, pentru intoarcerea in coordonate PDF."""
    bottom: float
    left: float

    def span_rects(self, start: int, length: int) -> list[Rect]:
        """Dreptunghiurile unui fragment, cate unul pe rand de text."""
        rows: list[list[Rect]] = []
        for box in self.boxes[start:start + length]:
            if box is None or not box.w or not box.h:
                continue
            row = rows[-1] if rows else None
            if row is not None and _same_line(row[-1], box):
                row.append(box)
            else:
                rows.append([box])
        return [union(row) for row in rows]


def _same_line(a: Rect, b: Rect) -> bool:
    overlap = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return overlap > 0.5 * min(a.h, b.h) and b.x >= a.x - 1


def union(rects: Sequence[Rect]) -> Rect:
    """Dreptunghiul care le cuprinde pe toate; gol pentru o lista goala."""
    if not rects:
        return Rect(0, 0, 0, 0)
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.x + r.w for r in rects)
    y1 = max(r.y + r.h for r in rects)
    return Rect(x0, y0, x1 - x0, y1 - y0)


def read_page_text(doc: pdfium.PdfDocument, number: int) -> PageText:
    """Textul paginii `number` (de la 1), cu dreptunghiurile caracterelor."""
    from app.core.pdf.document import PDFIUM_LOCK

    with PDFIUM_LOCK:
        page = doc[number - 1]
        try:
            left, bottom, _right, top = page.get_mediabox()
            textpage = page.get_textpage()
            try:
                chars: list[str] = []
                boxes: list[Rect | None] = []
                for i in range(textpage.count_chars()):
                    ch = textpage.get_text_range(i, 1)
                    if not ch:
                        continue
                    chars.append(ch[0])
                    if ch[0].isspace():
                        boxes.append(None)
                        continue
                    x0, y0, x1, y1 = textpage.get_charbox(i)
                    boxes.append(Rect(x0 - left, top - y1, x1 - x0, y1 - y0))
            finally:
                textpage.close()
        finally:
            page.close()
    return PageText(number, "".join(chars), tuple(boxes), float(top - bottom),
                    float(bottom), float(left))


def page_geometry(page: pikepdf.Page) -> tuple[float, float, float]:
    """(stanga, jos, inaltime) ale MediaBox-ului unei pagini pikepdf."""
    x0, y0, x1, y1 = (float(v) for v in page.mediabox)
    return min(x0, x1), min(y0, y1), abs(y1 - y0)


def to_pdf_rect(geometry: tuple[float, float, float], rect: Rect
                ) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in coordonatele PDF ale paginii (originea jos)."""
    left, bottom, height = geometry
    top = bottom + height
    return (left + rect.x, top - rect.y - rect.h, left + rect.x + rect.w, top - rect.y)


def from_pdf_rect(geometry: tuple[float, float, float], box: Sequence[float]) -> Rect:
    """Inversul lui `to_pdf_rect`, pentru un /Rect din fisier."""
    left, bottom, height = geometry
    x0, x1 = sorted(float(v) for v in (box[0], box[2]))
    y0, y1 = sorted(float(v) for v in (box[1], box[3]))
    return Rect(x0 - left, bottom + height - y1, x1 - x0, y1 - y0)


# --- cautarea -------------------------------------------------------------------------


def _match(text: str, query: str, match_case: bool, whole_word: bool, pattern: bool
           ) -> list[tuple[int, int]]:
    if pattern:
        return find_pattern(text, query, match_case=match_case)
    return find_all(text, query, match_case=match_case, whole_word=whole_word)


def _text_hits(document: PdfDocument, query: str, match_case: bool, whole_word: bool,
               pattern: bool) -> Iterator[SearchHit]:
    for number in range(1, document.page_count + 1):
        page = document.page_text(number)  # cu stratul temporar (B-028)
        for start, length in _match(page.text, query, match_case, whole_word, pattern):
            rects = page.span_rects(start, length)
            yield SearchHit(number, union(rects), context_of(page.text, start, length),
                            source=SOURCE_TEXT, start=start, length=length, rects=rects,
                            found=page.text[start:start + length])


def _comment_hits(document: PdfDocument, query: str, match_case: bool, whole_word: bool,
                  pattern: bool) -> Iterator[SearchHit]:
    pdf = document._pike()
    for number, page in enumerate(pdf.pages, start=1):
        geometry = page_geometry(page)
        for annot in page.get("/Annots", None) or []:
            if annot.get("/Subtype") in (pikepdf.Name.Link, pikepdf.Name.Popup):
                continue
            text = str(annot.get("/Contents", "") or "")
            spans = _match(text, query, match_case, whole_word, pattern) if text else []
            if not spans:
                continue
            rect = from_pdf_rect(geometry, annot.Rect) if "/Rect" in annot else Rect(0, 0, 0, 0)
            for start, length in spans:
                yield SearchHit(number, rect, context_of(text, start, length),
                                source=SOURCE_COMMENTS, start=start, length=length,
                                found=text[start:start + length])


def outline_items(document: PdfDocument) -> list[tuple[str, int, int]]:
    """(titlu, nivel de la 1, pagina de la 1 sau 0) pentru semnele de carte."""
    pdf = document._pike()
    pages = {page.objgen: i for i, page in enumerate(pdf.pages, start=1)}
    out: list[tuple[str, int, int]] = []

    def walk(items: Sequence[Any], level: int) -> None:
        for item in items:
            out.append((str(item.title or ""), level, _dest_page(item, pages, pdf)))
            walk(item.children, level + 1)

    try:
        with pdf.open_outline() as outline:
            walk(outline.root, 1)
    except (pikepdf.PdfError, pikepdf.OutlineStructureError):
        return out
    return out


def _dest_page(item: Any, pages: dict[tuple[int, int], int], pdf: pikepdf.Pdf) -> int:
    dest = item.destination
    if dest is None and item.action is not None and item.action.get("/S") == "/GoTo":
        dest = item.action.get("/D")
    if isinstance(dest, (pikepdf.String, pikepdf.Name, str)):
        dest = _named_dest(pdf, str(dest).lstrip("/"))
    if isinstance(dest, pikepdf.Dictionary):
        dest = dest.get("/D")
    if isinstance(dest, (pikepdf.Array, list)) and len(dest):
        target = dest[0]
        if isinstance(target, int):
            return target + 1
        if isinstance(target, pikepdf.Object) and target.is_indirect:
            return pages.get(target.objgen, 0)
    return 0


def _named_dest(pdf: pikepdf.Pdf, name: str) -> Any:
    names = pdf.Root.get("/Names")
    if names is not None and "/Dests" in names:
        tree = pikepdf.NameTree(names.Dests)
        if name in tree:
            return tree[name]
    dests = pdf.Root.get("/Dests")
    if dests is not None and ("/" + name) in dests:
        return dests["/" + name]
    return None


def _bookmark_hits(document: PdfDocument, query: str, match_case: bool, whole_word: bool,
                   pattern: bool) -> Iterator[SearchHit]:
    for title, _level, page in outline_items(document):
        for start, length in _match(title, query, match_case, whole_word, pattern):
            yield SearchHit(page, Rect(0, 0, 0, 0), title, source=SOURCE_BOOKMARKS,
                            start=start, length=length, found=title[start:start + length])


def _metadata_hits(document: PdfDocument, query: str, match_case: bool, whole_word: bool,
                   pattern: bool) -> Iterator[SearchHit]:
    for key, value in document.metadata().items():
        for start, length in _match(value, query, match_case, whole_word, pattern):
            yield SearchHit(0, Rect(0, 0, 0, 0), f"{key}: {value}", source=SOURCE_METADATA,
                            start=start, length=length, found=value[start:start + length])


# C-002…C-006
def search_document(document: PdfDocument, query: str, *, match_case: bool = False,
                    whole_word: bool = False, in_comments: bool = True,
                    in_bookmarks: bool = True, in_metadata: bool = True,
                    pattern: bool = False) -> list[SearchHit]:
    """Toate rezultatele, in ordinea surselor din `SOURCES` si, in fiecare
    sursa, in ordinea paginilor. `pattern=True`: `query` e expresie regulata
    (o expresie gresita da `re.error` inainte de cautare)."""
    if not query:
        raise ValueError("textul cautat trebuie sa aiba cel putin un caracter (C-002)")
    if pattern:
        re.compile(query)
    hits = list(_text_hits(document, query, match_case, whole_word, pattern))
    if in_comments:
        hits += _comment_hits(document, query, match_case, whole_word, pattern)
    if in_bookmarks:
        hits += _bookmark_hits(document, query, match_case, whole_word, pattern)
    if in_metadata:
        hits += _metadata_hits(document, query, match_case, whole_word, pattern)
    return hits
