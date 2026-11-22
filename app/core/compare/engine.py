"""Algoritmul de comparare (faza 12, pasul 12.2): R-006, R-015, R-016,
R-022, R-030…R-036, R-048, R-049.

1. Cuvintele fiecarei surse (`sources.py`) se impart in corp si antete/subsoluri
   (R-022: randurile din marginea de sus si de jos care se repeta pe pagini).
2. Fiecare cuvant primeste o cheie de comparare, in care diferentele minore
   dispar (R-033): spatiile, fontul si formatarea nu exista in cheie; ligaturile,
   ghilimelele, liniutele si varianta cu sedila a lui ș si ț se unifica.
   Punctuatia intra in cheie numai cu R-015.
3. Alinierea (R-031): intai pe randuri intregi (ancorele: randurile identice),
   apoi, in zonele diferite, pe cuvinte; pe blocuri, cu progres (R-036).
4. Diferentele: inserat, sters, inlocuit (R-032); cele apropiate se unesc
   (`group_distance_words`); diferentele de o litera se pastreaza numai cu R-016;
   fiecare primeste grupul (R-034): `body`, `headers_footers`, `numbering`.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.compare.sources import (
    EDITABLE_EXTENSIONS,
    SourceDocument,
    SourceWord,
    can_compare,
    load_source,
)
from app.core.model import (
    CompareOptions,
    Difference,
    DiffType,
    Progress,
    ProgressCallback,
    Rect,
)

if TYPE_CHECKING:
    from app.core.context import AppContext

GROUPS = ("body", "headers_footers", "numbering")
"""R-034: cele trei grupuri fixe (`Body text`, `Headers and footers`, `Numbering`)."""
MARGIN_SHARE = 0.12
"""R-022: antetul si subsolul stau in 12% de sus, respectiv de jos, ale paginii."""
REPEAT_SHARE = 0.5
"""R-022: un rand din margine e antet daca apare pe cel putin jumatate din pagini."""
BLOCK_WORDS = 5000
"""R-036: cate cuvinte se aliniaza cuvant cu cuvant intr-un bloc."""

_TRANSLATE = str.maketrans({
    "ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț", "‘": "'", "’": "'", "‚": "'", "“": '"',
    "”": '"', "„": '"', "«": '"', "»": '"', "–": "-", "—": "-", "‐": "-", "‑": "-",
    "­": "", " ": " ", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
})
_PUNCT = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)
_LIST_MARKER = re.compile(r"^(\(?\d{1,3}[.)]|\(?[a-zA-Z][.)]|\(?[ivxlcdm]{1,6}[.)]|[•\-–*·▪◦])$",
                          re.IGNORECASE)

Op = tuple[str, list["_Token"], list["_Token"]]


@dataclass(slots=True)
class _Token:
    word: SourceWord
    key: str
    zone: str
    """`body` sau `headers_footers`."""


# --- cheile si zonele ------------------------------------------------------------------------


def normalize(text: str, *, punctuation: bool) -> str:
    """R-033: cheia de comparare a unui cuvant (fara diferentele minore)."""
    key = unicodedata.normalize("NFC", text).translate(_TRANSLATE)
    key = re.sub(r"\s+", "", key)
    if not punctuation:
        key = _PUNCT.sub("", key)
    return key


def _lines(words: Sequence[SourceWord]) -> list[list[SourceWord]]:
    lines: list[list[SourceWord]] = []
    for word in words:
        if lines and lines[-1][-1].page == word.page and lines[-1][-1].line == word.line:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def header_footer_lines(source: SourceDocument) -> set[tuple[int, int]]:
    """R-022: randurile (pagina, rand) din marginile paginii care se repeta pe
    cel putin jumatate din pagini (cifrele nu conteaza: numarul paginii difera)."""
    pages = source.document.page_count
    if pages < 2:
        return set()
    heights = {n: source.document.page_size(n)[1] for n in range(1, pages + 1)}
    seen: dict[str, set[int]] = {}
    found: list[tuple[str, tuple[int, int]]] = []
    for line in _lines(source.words):
        page = line[0].page
        top = min(w.rect.y for w in line)
        bottom = max(w.rect.y + w.rect.h for w in line)
        if top > heights[page] * MARGIN_SHARE and bottom < heights[page] * (1 - MARGIN_SHARE):
            continue
        text = re.sub(r"\d+", "#", " ".join(normalize(w.text, punctuation=False)
                                            for w in line))
        seen.setdefault(text, set()).add(page)
        found.append((text, (page, line[0].line)))
    needed = max(2, -(-pages // 2))
    return {key for text, key in found if len(seen[text]) >= needed}


def _tokens(source: SourceDocument, options: CompareOptions) -> list[_Token]:
    marginal = header_footer_lines(source) if options.find_headers_footers else set()
    out: list[_Token] = []
    for word in source.words:
        zone = "headers_footers" if (word.page, word.line) in marginal else "body"
        if zone == "headers_footers" and options.ignore_headers_footers:
            continue
        key = normalize(word.text, punctuation=options.find_punctuation)
        if key:
            out.append(_Token(word, key, zone))
    return out


# --- alinierea (R-031, R-036) -------------------------------------------------------------------


def _line_groups(tokens: Sequence[_Token]) -> list[list[_Token]]:
    groups: list[list[_Token]] = []
    for token in tokens:
        last = groups[-1][-1] if groups else None
        if last is not None and last.word.page == token.word.page and \
                last.word.line == token.word.line:
            groups[-1].append(token)
        else:
            groups.append([token])
    return groups


def _align(left: Sequence[_Token], right: Sequence[_Token], *,
           progress: Callable[[int, int], None] | None = None,
           cancel: Callable[[], bool] | None = None) -> list[Op]:
    """Operatiile (`equal`, `replace`, `delete`, `insert`) pe cuvinte: randurile
    identice sunt ancore, iar zonele dintre ele se aliniaza cuvant cu cuvant,
    pe blocuri (R-031, R-036)."""
    lines_left, lines_right = _line_groups(left), _line_groups(right)
    keys_left = [" ".join(t.key for t in line) for line in lines_left]
    keys_right = [" ".join(t.key for t in line) for line in lines_right]
    coarse = difflib.SequenceMatcher(None, keys_left, keys_right,
                                     autojunk=False).get_opcodes()
    out: list[Op] = []
    for step, (tag, i1, i2, j1, j2) in enumerate(coarse):
        if cancel is not None and cancel():
            break
        if progress is not None:
            progress(step, len(coarse))
        chunk_left = [t for line in lines_left[i1:i2] for t in line]
        chunk_right = [t for line in lines_right[j1:j2] for t in line]
        if tag == "equal":
            out.append(("equal", chunk_left, chunk_right))
            continue
        for start in range(0, max(len(chunk_left), len(chunk_right), 1), BLOCK_WORDS):
            part_left = chunk_left[start:start + BLOCK_WORDS]
            part_right = chunk_right[start:start + BLOCK_WORDS]
            fine = difflib.SequenceMatcher(None, [t.key for t in part_left],
                                           [t.key for t in part_right], autojunk=False)
            for op, a1, a2, b1, b2 in fine.get_opcodes():
                out.append((op, part_left[a1:a2], part_right[b1:b2]))
    return out


def _by_paragraph(tokens: list[_Token]) -> list[list[_Token]]:
    groups: list[list[_Token]] = []
    for token in tokens:
        if groups and groups[-1][-1].word.paragraph == token.word.paragraph:
            groups[-1].append(token)
        else:
            groups.append([token])
    return groups


def _relation(anchor: int, paragraph: int, step: int) -> str | None:
    """Paragraful fata de textul identic vecin: acelasi (`same`) sau cel imediat
    urmator/precedent (`next`)."""
    if paragraph == anchor:
        return "same"
    if paragraph == anchor + step:
        return "next"
    return None


def _paired(left: list[_Token], right: list[_Token], neighbour: Op | None, *,
            before: bool) -> bool:
    """Doua bucati (cate una din fiecare document) sunt acelasi paragraf daca stau
    la fel fata de textul identic vecin, in ambele documente."""
    if neighbour is None:
        return False
    step = 1 if before else -1
    anchor_left = (neighbour[1][-1] if before else neighbour[1][0]).word.paragraph
    anchor_right = (neighbour[2][-1] if before else neighbour[2][0]).word.paragraph
    side_left = _relation(anchor_left, (left[0] if before else left[-1]).word.paragraph, step)
    side_right = _relation(anchor_right, (right[0] if before else right[-1]).word.paragraph,
                           step)
    return side_left is not None and side_left == side_right


def _split_paragraphs(ops: list[Op]) -> list[Op]:
    """R-030: o inlocuire care trece peste paragrafe se imparte. Se pereche (ca
    inlocuire) numai bucata care sta la fel fata de textul identic de dinainte
    sau de dupa, in ambele documente; restul e sters, respectiv inserat."""
    out: list[Op] = []
    for i, (tag, left, right) in enumerate(ops):
        if tag != "replace":
            out.append((tag, left, right))
            continue
        before = ops[i - 1] if i and ops[i - 1][0] == "equal" else None
        after = ops[i + 1] if i + 1 < len(ops) and ops[i + 1][0] == "equal" else None
        groups_left, groups_right = _by_paragraph(left), _by_paragraph(right)
        if before is None and after is None:
            out.append((tag, left, right))
            continue
        head: list[Op] = []
        tail: list[Op] = []
        if groups_left and groups_right and _paired(groups_left[0], groups_right[0], before,
                                                   before=True):
            head.append(("replace", groups_left.pop(0), groups_right.pop(0)))
        if groups_left and groups_right and _paired(groups_left[-1], groups_right[-1], after,
                                                   before=False):
            tail.append(("replace", groups_left.pop(), groups_right.pop()))
        middle = [("delete", g, []) for g in groups_left] + \
            [("insert", [], g) for g in groups_right]
        out += head + middle + tail
    return out


def _close(a: Op, b: Op, gap: Op | None = None) -> bool:
    """Doua diferente din acelasi paragraf (R-034): in fiecare document,
    cuvintele lor si ale celor identice dintre ele nu trec intr-alt paragraf."""
    shared = False
    for side in (1, 2):
        tokens = [*a[side], *(gap[side] if gap else []), *b[side]]
        if len({t.word.paragraph for t in tokens}) > 1:
            return False
        shared = shared or bool(a[side] and b[side])
    return shared


def _merge(ops: list[Op], distance: int) -> list[Op]:
    """R-034: diferentele separate de mai putin de `distance` cuvinte identice,
    in acelasi paragraf, devin una singura."""
    merged: list[Op] = []
    for op in ops:
        if op[0] == "equal" or not merged:
            merged.append(op)
            continue
        if len(merged) >= 2 and merged[-1][0] == "equal" and merged[-2][0] != "equal" and \
                len(merged[-1][1]) < distance and _close(merged[-2], op, merged[-1]):
            gap = merged.pop()
            previous = merged.pop()
            merged.append(("replace", previous[1] + gap[1] + op[1],
                           previous[2] + gap[2] + op[2]))
            continue
        if merged[-1][0] != "equal" and _close(merged[-1], op):
            previous = merged.pop()
            merged.append(("replace", previous[1] + op[1], previous[2] + op[2]))
            continue
        merged.append(op)
    return merged


# --- diferentele (R-032, R-034, R-016) ------------------------------------------------------------


def _one_letter(left: str, right: str) -> bool:
    """R-016: textele difera printr-o singura litera (adaugata, stearsa, schimbata).
    Cifrele nu sunt litere: o suma schimbata ramane mereu diferenta."""
    if abs(len(left) - len(right)) > 1:
        return False
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    edits = [(left[i1:i2], right[j1:j2], max(i2 - i1, j2 - j1))
             for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    return sum(size for _a, _b, size in edits) == 1 and all(
        (a + b).isalpha() for a, b, _size in edits)


def _group(left: Sequence[_Token], right: Sequence[_Token]) -> str:
    tokens = [*left, *right]
    if any(t.zone == "headers_footers" for t in tokens):
        return "headers_footers"
    if tokens and all(_LIST_MARKER.match(t.word.text) for t in tokens):
        return "numbering"
    return "body"


def _rects(tokens: Sequence[_Token]) -> list[tuple[int, Rect]]:
    return [r for t in tokens for r in (t.word.rects or [(t.word.page, t.word.rect)])]


def _anchor(ops: list[Op], index: int, side: int) -> tuple[int | None, Rect | None]:
    """Locul din documentul in care diferenta nu are text: cuvantul dinainte (sau,
    la inceput, cel de dupa). Acolo se pune nota (R-063) si sare navigarea."""
    for step in (-1, 1):
        k = index + step
        while 0 <= k < len(ops):
            tokens = ops[k][side]
            if tokens:
                word = (tokens[-1] if step < 0 else tokens[0]).word
                return word.page, word.rect
            k += step
    return None, None


def build_differences(ops: list[Op], options: CompareOptions) -> list[Difference]:
    out: list[Difference] = []
    for index, (tag, left, right) in enumerate(ops):
        if tag == "equal" or not (left or right):
            continue
        if not options.find_one_letter and _one_letter("".join(t.key for t in left),
                                                       "".join(t.key for t in right)):
            continue
        kind = DiffType.REPLACED if left and right else (
            DiffType.DELETED if left else DiffType.INSERTED)
        rects_left, rects_right = _rects(left), _rects(right)
        page_left, box_left = (rects_left[0] if rects_left else _anchor(ops, index, 1))
        page_right, box_right = (rects_right[0] if rects_right else _anchor(ops, index, 2))
        out.append(Difference(
            len(out), kind, " ".join(t.word.text for t in left) or None,
            " ".join(t.word.text for t in right) or None, page_left, page_right,
            bbox_left=box_left, bbox_right=box_right, group=_group(left, right),
            rects_left=rects_left, rects_right=rects_right))
    return out


def compare_sources(left: SourceDocument, right: SourceDocument, options: CompareOptions, *,
                    progress: ProgressCallback | None = None,
                    cancel: Callable[[], bool] | None = None) -> list[Difference]:
    """R-030…R-036: diferentele dintre doua surse deja citite. Documente
    identice → lista goala (R-043)."""
    tokens_left, tokens_right = _tokens(left, options), _tokens(right, options)

    def report(done: int, total: int) -> None:
        if progress is not None:
            progress(Progress(done, max(total, 1), "stage.comparing", ""))

    ops: list[Op] = []
    for zone in ("body", "headers_footers"):
        zone_left = [t for t in tokens_left if t.zone == zone]
        zone_right = [t for t in tokens_right if t.zone == zone]
        if zone_left or zone_right:
            aligned = _split_paragraphs(_align(zone_left, zone_right, progress=report,
                                               cancel=cancel))
            ops += _merge(aligned, options.group_distance_words)
    differences = build_differences(ops, options)
    report(1, 1)
    return differences


# --- ignorarea (R-048, R-049) --------------------------------------------------------------


def ignore(differences: Sequence[Difference], indices: Sequence[int]) -> list[Difference]:
    """R-048: diferentele alese (`Ctrl` pentru mai multe) nu mai intra in raport."""
    chosen = set(indices)
    return [replace(d, is_ignored=True) if d.order_index in chosen else d
            for d in differences]


def ignore_identical(differences: Sequence[Difference], index: int) -> list[Difference]:
    """R-049: toate diferentele identice cu cea aleasa (acelasi tip, acelasi text
    vechi si nou), dintr-o singura comanda."""
    model = next(d for d in differences if d.order_index == index)
    same = [d.order_index for d in differences
            if (d.diff_type, d.text_left, d.text_right) ==
            (model.diff_type, model.text_left, model.text_right)]
    return ignore(differences, same)


def grouped(differences: Sequence[Difference], *, include_ignored: bool = False
            ) -> dict[str, list[Difference]]:
    """R-034: diferentele pe cele trei grupuri, in ordine."""
    out: dict[str, list[Difference]] = {g: [] for g in GROUPS}
    for d in differences:
        if include_ignored or not d.is_ignored:
            out.setdefault(d.group, []).append(d)
    return out


# --- comparatiile recente (R-006) --------------------------------------------------------------


def record_recent(con: sqlite3.Connection, left: Path, right: Path,
                  languages: Sequence[str], count: int | None) -> None:
    """R-006: perechea comparata ajunge prima in lista (cel mult 20, SPEC_04)."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with con:
        con.execute(
            "INSERT INTO recent_comparison (path_left, path_right, language_codes,"
            " difference_count, compared_at) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (path_left, path_right) DO UPDATE SET"
            " language_codes = excluded.language_codes,"
            " difference_count = excluded.difference_count,"
            " compared_at = excluded.compared_at",
            (str(left), str(right), json.dumps(list(languages)), count, now))


@dataclass(frozen=True, slots=True)
class RecentComparison:
    left: Path
    right: Path
    languages: tuple[str, ...]
    difference_count: int | None
    compared_at: str
    missing: bool
    """R-006: un fisier lipseste → randul se marcheaza."""


def recent_comparisons(con: sqlite3.Connection) -> list[RecentComparison]:
    rows = con.execute("SELECT path_left, path_right, language_codes, difference_count,"
                       " compared_at FROM recent_comparison ORDER BY compared_at DESC"
                       ).fetchall()
    out: list[RecentComparison] = []
    for left, right, languages, count, when in rows:
        try:
            codes = tuple(json.loads(languages))
        except (TypeError, ValueError):
            codes = ()
        out.append(RecentComparison(Path(left), Path(right), codes, count, when,
                                    not (Path(left).is_file() and Path(right).is_file())))
    return out


# --- contractul SPEC_05 --------------------------------------------------------------------------


def _raster_extensions() -> frozenset[str]:
    from app.core.images.loader import RASTER_EXTENSIONS

    return frozenset(RASTER_EXTENSIONS)


class DocumentComparer:
    """R-001…R-068 (SPEC_05: `DocumentComparer`)."""

    SUPPORTED_FORMATS: frozenset[str] = frozenset({".pdf", *EDITABLE_EXTENSIONS,
                                                   *_raster_extensions()})
    """R-002: PDF, formatele editabile si imaginile."""

    def __init__(self, *, context: AppContext | None = None, engine: Any = None,
                 texts: Callable[..., str] | None = None) -> None:
        self.context = context
        self.engine = engine
        self.texts = texts or (lambda key, **params: key)
        """Textele care ajung in fisierele salvate (traducerile, din interfata)."""

    def can_compare(self, path: Path) -> bool:
        return can_compare(path)

    def load(self, path: Path, options: CompareOptions, *,
             password: Callable[[str], str | None] | None = None,
             progress: ProgressCallback | None = None,
             cancel: Callable[[], bool] | None = None) -> SourceDocument:
        return load_source(path, mode=options.pdf_mode, languages=options.languages,
                           password=password, context=self.context, engine=self.engine,
                           progress=progress, cancel=cancel)

    def extract_text(self, path: Path, options: CompareOptions, *,
                     password: Callable[[str], str | None] | None = None,
                     progress: ProgressCallback | None = None) -> list[tuple[int, str, Rect]]:
        """R-007, R-020: (pagina, cuvant, pozitie); `NoTextFoundError` daca nici
        dupa OCR nu are text."""
        source = self.load(path, options, password=password, progress=progress)
        try:
            return [(w.page, w.text, w.rect) for w in source.words]
        finally:
            source.close()

    def compare(self, left: Path, right: Path, options: CompareOptions, *,
                password: Callable[[str], str | None] | None = None,
                progress: ProgressCallback | None = None,
                cancel: Callable[[], bool] | None = None) -> list[Difference]:
        """R-017, R-030…R-036; perechea intra in comparatiile recente (R-006)."""
        first = self.load(left, options, password=password, progress=progress, cancel=cancel)
        try:
            second = self.load(right, options, password=password, progress=progress,
                               cancel=cancel)
            try:
                result = compare_sources(first, second, options, progress=progress,
                                         cancel=cancel)
            finally:
                second.close()
        finally:
            first.close()
        if self.context is not None:
            record_recent(self.context.app_db, left, right, options.languages, len(result))
        return result

    # --- salvarea (R-060…R-067) ---

    def _source(self, document: SourceDocument | Path) -> SourceDocument:
        if isinstance(document, SourceDocument):
            return document
        return self.load(Path(document), CompareOptions())

    def save_as_pdf_with_comments(self, right: SourceDocument | Path,
                                  differences: Sequence[Difference], target: Path, *,
                                  side: int = 2, author: str | None = None) -> Path:
        """R-063: fiecare diferenta devine o adnotare pe documentul ales
        (implicit documentul 2, ca in SPEC_05)."""
        from app.core.compare.report import save_pdf_with_comments

        source = self._source(right)
        try:
            return save_pdf_with_comments(source, differences, target, side=side,
                                          texts=self.texts, author=author)
        finally:
            if source is not right:
                source.close()

    def save_as_track_changes(self, document: SourceDocument | Path,
                              differences: Sequence[Difference], target: Path, *,
                              side: int, author: str = "DocuLens") -> Path:
        """R-061: un fisier DOCX per document, cu modificarile ca revizii."""
        from app.core.compare.report import save_track_changes

        source = self._source(document)
        try:
            return save_track_changes(source, differences, target, side=side, author=author)
        finally:
            if source is not document:
                source.close()

    def save_as_word_table(self, differences: Sequence[Difference], target: Path, *,
                           left: Path, right: Path) -> Path:
        """R-064, R-414: tabelul Word cu diferentele."""
        from app.core.compare.report import save_report

        return save_report(differences, target, left=left, right=right, texts=self.texts)

    def save_report(self, differences: Sequence[Difference], target: Path, *,
                    left: Path, right: Path) -> Path:
        """R-064, R-067: acelasi raport; diferentele ignorate nu apar."""
        return self.save_as_word_table(differences, target, left=left, right=right)
