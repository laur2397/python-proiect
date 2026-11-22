"""Securitatea documentelor PDF: redactarea (faza 7, pasul 7.2b).

Din `SecurityService` (SPEC_05 sectiunea 10) sunt implementate aici numai
`redact_regions` (G-020, G-021) si `redact_by_keywords` (C-025, C-026), de
care are nevoie tabul `REDACT` al panoului de cautare. Restul clasei
(parolele si permisiunile G-001…G-009, stergerea datelor G-022, G-031) vine
cu faza 10 si nu e declarat aici.

CLAUDE.md §6.7: dupa fiecare redactare se extrage textul si se verifica
absenta lui; daca mai apare, operatia se anuleaza (documentul revine la starea
dinainte) si se ridica `RedactionVerificationError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.core.model import Rect
from app.core.pdf.redact import PageEdit, rebuild_page, verify_removed
from app.core.pdf.text import SOURCE_TEXT, SearchHit

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

DEFAULT_REDACTION_COLOR = "#000000"


def _group(regions: Sequence[tuple[int, Rect]], total: int) -> dict[int, list[Rect]]:
    pages: dict[int, list[Rect]] = {}
    for number, rect in regions:
        if not 1 <= number <= total:
            raise ValueError(f"pagina {number} nu exista (1..{total})")
        if rect.w <= 0 or rect.h <= 0:
            raise ValueError("zona de redactat e goala")
        pages.setdefault(number, []).append(rect)
    return pages


class SecurityService:
    """G-020, G-021, C-025, C-026 (restul in faza 10)."""

    # G-020, G-021
    def redact_regions(self, document: PdfDocument, regions: Sequence[tuple[int, Rect]],
                       color: str = DEFAULT_REDACTION_COLOR, *,
                       words: Sequence[tuple[str, bool, bool]] = ()) -> None:
        """Continutul zonelor dispare din pagina si din stratul de text; zonele
        se acopera cu `color`, iar adnotarile care le ating se sterg. Dupa
        operatie textul se extrage din nou: daca mai apare ceva in zone (sau
        unul din `words`: text, majuscule, cuvant intreg), documentul revine la
        starea dinainte si se ridica `RedactionVerificationError`.
        `words` e adaugat fata de SPEC_05, pentru verificarea dupa cuvinte."""
        pages = _group(regions, document.page_count)
        if not pages:
            return
        snapshot = document._snapshot()
        try:
            for number, rects in pages.items():
                rebuild_page(document, number, [PageEdit(r, color) for r in rects],
                             remove_annotations=True)
            document._changed()
            for number, rects in pages.items():
                verify_removed(document, number, rects, words)
        except BaseException:
            document._restore(snapshot)
            raise

    # C-025, C-026
    def redact_by_keywords(self, document: PdfDocument, keywords: Sequence[str], *,
                           match_case: bool = False, whole_word: bool = False,
                           color: str = DEFAULT_REDACTION_COLOR) -> int:
        """Redacteaza toate aparitiile cuvintelor in textul paginilor si intoarce
        cate au fost. Verificarea G-021 cauta din nou fiecare cuvant."""
        hits: list[SearchHit] = []
        for keyword in keywords:
            hits += document.search(keyword, match_case=match_case, whole_word=whole_word,
                                    in_comments=False, in_bookmarks=False, in_metadata=False)
        words = [(k, match_case, whole_word) for k in keywords]
        return self.redact_hits(document, hits, color, words=words)

    # C-026, C-011: rezultatele selectate in panou
    def redact_hits(self, document: PdfDocument, hits: Sequence[SearchHit],
                    color: str = DEFAULT_REDACTION_COLOR, *,
                    words: Sequence[tuple[str, bool, bool]] = ()) -> int:
        """Redacteaza rezultatele alese din lista; cele din comentarii, semne de
        carte si metadate nu au zona in pagina si se sar. Intoarce numarul de
        rezultate redactate (doua cuvinte care gasesc acelasi loc conteaza o data)."""
        regions: list[tuple[int, Rect]] = []
        seen: set[tuple[int, int, int]] = set()
        for hit in hits:
            key = (hit.page, hit.start, hit.length)
            if hit.source != SOURCE_TEXT or not hit.rects or key in seen:
                continue
            seen.add(key)
            regions += [(hit.page, r) for r in hit.rects]
        if regions:
            self.redact_regions(document, regions, color, words=words)
        return len(seen)
