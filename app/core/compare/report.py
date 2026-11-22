"""Salvarea rezultatului compararii (faza 12, pasul 12.3): R-060…R-067,
R-414, R-415.

- `PDF with Comments` (R-063): documentul ales, cu fiecare diferenta ca adnotare
  (evidentiere pe textul lui; nota acolo unde textul lipseste din el).
- `DOCX in Track Changes Mode` (R-061): cate un fisier per document, cu textul
  lui si modificarile marcate ca revizii Word (`w:ins`, `w:del`). Fisierele sunt
  versiuni recunoscute (R-062): avertismentul il da interfata, inainte.
- `Comparison Report` (R-064, R-414): tabel cu doua coloane, antetul cu caile
  fisierelor (numele in bold), un rand pe diferenta, `[page N] text` in coloana
  documentului caruia ii apartine; celula goala = textul lipseste acolo.

Numai `.pdf` si `.docx` (R-065); diferentele ignorate nu apar (R-067). Textele
care ajung in fisiere vin din traduceri, prin `texts`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.errors import UnsupportedFormatError
from app.core.model import AnnotationData, AnnotationType, Difference, DiffType, Rect

if TYPE_CHECKING:
    from app.core.compare.sources import SourceDocument

Texts = Callable[..., str]

SAVE_FORMATS = (".pdf", ".docx")
"""R-065: doar acestea doua."""
SAVE_KINDS = ("track_changes", "pdf_comments", "report")
"""R-060: cele trei variante din dialogul `Save...`."""
HIGHLIGHT = {DiffType.INSERTED: "#7BC67E", DiffType.DELETED: "#EF7A7A",
             DiffType.REPLACED: "#C9B3F2", DiffType.FORMATTING: "#C9B3F2"}
"""Culorile evidentierii in PDF (R-063)."""


def _active(differences: Sequence[Difference]) -> list[Difference]:
    """R-067: diferentele ignorate nu apar."""
    return [d for d in differences if not d.is_ignored]


def _check(target: Path, suffix: str) -> Path:
    target = Path(target)
    if target.suffix.lower() != suffix:
        raise UnsupportedFormatError("rezultatul se salveaza numai ca PDF sau DOCX",
                                     path=str(target))
    return target


def _own(difference: Difference, side: int) -> tuple[list[tuple[int, Rect]], str | None,
                                                      str | None, int | None, Rect | None]:
    """(dreptunghiurile, textul propriu, textul celuilalt document, pagina,
    ancora) pentru documentul `side` (1 = stanga, 2 = dreapta)."""
    if side == 1:
        return (difference.rects_left, difference.text_left, difference.text_right,
                difference.page_left, difference.bbox_left)
    return (difference.rects_right, difference.text_right, difference.text_left,
            difference.page_right, difference.bbox_right)


def note_text(difference: Difference, side: int, texts: Texts) -> str:
    """Textul adnotarii: ce s-a schimbat fata de celalalt document."""
    _rects, own, other, _page, _anchor = _own(difference, side)
    if own and other:
        return texts("compare.note.edited", old=difference.text_left or "",
                     new=difference.text_right or "")
    if own:
        return texts("compare.note.added" if side == 2 else "compare.note.deleted", text=own)
    return texts("compare.note.deleted" if side == 2 else "compare.note.added",
                 text=other or "")


# --- PDF with Comments (R-063) --------------------------------------------------------------


def save_pdf_with_comments(source: SourceDocument, differences: Sequence[Difference],
                           target: Path, *, side: int, texts: Texts,
                           author: str | None = None) -> Path:
    """R-063: fiecare diferenta devine o adnotare pe documentul `side`."""
    from app.core.pdf.document import PdfDocument
    from app.core.pdf.markup import add_text_markup

    target = _check(target, ".pdf")
    source.document.export_copy(target)
    with PdfDocument.open(target) as copy:
        for difference in _active(differences):
            rects, _own_text, _other, page, anchor = _own(difference, side)
            contents = note_text(difference, side, texts)
            if rects:
                by_page: dict[int, list[Rect]] = {}
                for number, rect in rects:
                    by_page.setdefault(number, []).append(rect)
                for number, boxes in by_page.items():
                    add_text_markup(copy, number, boxes, AnnotationType.HIGHLIGHT,
                                    HIGHLIGHT[difference.diff_type], author=author,
                                    contents=contents)
                copy._changed()
            elif page is not None:
                width = copy.page_size(page)[0]
                x = min(anchor.x + anchor.w if anchor is not None else 20.0, width - 22)
                y = anchor.y if anchor is not None else 20.0
                copy.add_annotation(AnnotationData(
                    None, AnnotationType.NOTE, page, {"point": (x, y)},
                    bbox=Rect(x, y, 20, 20), author=author, content=contents))
        copy.save()
    return target


# --- DOCX in Track Changes Mode (R-061) ---------------------------------------------------------


def _key(page: int, rect: Rect) -> tuple[int, int, int]:
    return page, round(rect.x * 10), round(rect.y * 10)


def track_changes_plan(source: SourceDocument, differences: Sequence[Difference], side: int
                       ) -> tuple[set[int], dict[int, list[str]], list[str]]:
    """(cuvintele marcate ca inserate, textele sterse puse inaintea cuvantului i,
    textele sterse fara loc, puse la sfarsit), pentru documentul `side`."""
    index: dict[tuple[int, int, int], int] = {}
    for i, word in enumerate(source.words):
        for number, rect in word.rects or [(word.page, word.rect)]:
            index[_key(number, rect)] = i
    inserted: set[int] = set()
    deleted_before: dict[int, list[str]] = {}
    tail: list[str] = []
    for difference in _active(differences):
        rects, _own_text, other, page, anchor = _own(difference, side)
        mine = sorted({index[_key(n, r)] for n, r in rects if _key(n, r) in index})
        inserted.update(mine)
        if not other:
            continue
        if mine:
            deleted_before.setdefault(mine[0], []).append(other)
        elif anchor is not None and page is not None and _key(page, anchor) in index:
            after = index[_key(page, anchor)] + 1
            if after < len(source.words):
                deleted_before.setdefault(after, []).append(other)
            else:
                tail.append(other)
        else:
            tail.append(other)
    return inserted, deleted_before, tail


def save_track_changes(source: SourceDocument, differences: Sequence[Difference],
                       target: Path, *, side: int, author: str) -> Path:
    """R-061: textul documentului `side`, cu ce difera de celalalt ca revizii:
    textul lui propriu `w:ins`, textul celuilalt `w:del`."""
    import docx
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    target = _check(target, ".docx")
    inserted, deleted_before, tail = track_changes_plan(source, differences, side)
    document = docx.Document()
    body = document.element.body
    for old in list(body.iterchildren(qn("w:p"))):
        body.remove(old)
    when = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    state: dict[str, Any] = {"revision": 0, "paragraph": None, "current": None}
    plain: list[str] = []
    marked: list[str] = []

    def run(text: str, *, deleted: bool = False) -> Any:
        element = OxmlElement("w:r")
        t = OxmlElement("w:delText" if deleted else "w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = text
        element.append(t)
        return element

    def revision(kind: str, text: str) -> Any:
        state["revision"] += 1
        element = OxmlElement(kind)
        element.set(qn("w:id"), str(state["revision"]))
        element.set(qn("w:author"), author)
        element.set(qn("w:date"), when)
        element.append(run(text, deleted=kind == "w:del"))
        return element

    def new_paragraph() -> Any:
        element = OxmlElement("w:p")
        section = body.find(qn("w:sectPr"))
        if section is not None:
            section.addprevious(element)
        else:
            body.append(element)
        return element

    def flush() -> None:
        paragraph = state["paragraph"]
        if paragraph is None:
            return
        if plain:
            paragraph.append(run(" ".join(plain) + " "))
            plain.clear()
        if marked:
            paragraph.append(revision("w:ins", " ".join(marked) + " "))
            marked.clear()

    for i, word in enumerate(source.words):
        if state["paragraph"] is None or word.paragraph != state["current"]:
            flush()
            state["paragraph"], state["current"] = new_paragraph(), word.paragraph
        for text in deleted_before.get(i, []):
            flush()
            state["paragraph"].append(revision("w:del", text + " "))
        if i in inserted:
            if plain:
                flush()
            marked.append(word.text)
        else:
            if marked:
                flush()
            plain.append(word.text)
    flush()
    for text in tail:
        new_paragraph().append(revision("w:del", text))
    document.save(str(target))
    return target


# --- Comparison Report (R-064, R-414) -----------------------------------------------------------


def save_report(differences: Sequence[Difference], target: Path, *, left: Path, right: Path,
                texts: Texts) -> Path:
    """R-064, R-414: tabelul Word cu diferentele (fara cele ignorate, R-067)."""
    import docx

    target = _check(target, ".docx")
    document = docx.Document()
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    for cell, path in zip(table.rows[0].cells, (Path(left), Path(right)), strict=True):
        paragraph = cell.paragraphs[0]
        folder = str(path.parent)
        if folder not in ("", "."):
            paragraph.add_run(str(path)[:len(str(path)) - len(path.name)])
        paragraph.add_run(path.name).bold = True
    for difference in _active(differences):
        row = table.add_row().cells
        for cell, text, page in ((row[0], difference.text_left, difference.page_left),
                                 (row[1], difference.text_right, difference.page_right)):
            if text:
                cell.text = texts("compare.report.page", n=page or 1) + " " + text
    document.save(str(target))
    return target
