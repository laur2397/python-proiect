"""Editarea si verificarea textului recunoscut (faza 5, pasul 5.1): O-001..O-012,
O-020.

`TextEditor` din SPEC_05. Fiecare modificare trece prin proiect: un pas de undo
si proiectul marcat ca modificat. Metodele primesc `WordData` (cu id) din
paginile proiectului; dupa o modificare, paginile se reincarca, deci apelantul
ia din nou cuvintele din `project.page(n)`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.model import PageData, PageStatus, WordData

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

_PUNCTUATION = ".,;:!?()[]{}\"'„”«»"

CJK_LOOKALIKES: tuple[str, ...] = (
    "未末", "己已巳", "土士", "人入八", "日曰", "千干于", "天夫", "刀力", "大太犬", "王玉主",
    "田由甲申", "木本未", "口囗", "白自", "斤斥", "免兔", "贝见", "侯候", "戍戌戊", "ロ口",
    "カ力", "エ工", "ニ二", "ハ八", "タ夕", "へヘ", "ー一", "기키", "이리",
)
"""O-010: grupuri de caractere CJK cu aspect asemanator.
[DECIZIE AUTONOMA] Lista e a noastra; originalul nu o publica."""


@dataclass(frozen=True, slots=True)
class VerifyOptions:
    """O-012 (X-160..X-162)."""

    check_uncertain: bool = True
    ignore_words_with_digits: bool = True
    check_compound_words: bool = True
    fix_punctuation_spaces: bool = True

    @classmethod
    def from_settings(cls, settings: Any) -> VerifyOptions:
        return cls(bool(settings.get("areas.check_uncertain")),
                   bool(settings.get("areas.ignore_words_with_digits")),
                   bool(settings.get("areas.check_compound_words")),
                   bool(settings.get("areas.fix_punctuation_spaces")))


def bare(text: str) -> str:
    """Cuvantul fara punctuatia de la capete (pentru dictionar)."""
    return text.strip(_PUNCTUATION)


def fix_punctuation_spaces(text: str) -> str:
    """O-012: fara spatiu inainte de , . ; : ! ? si dupa ( [ „."""
    text = re.sub(r"\s+([,.;:!?)\]”»])", r"\1", text)
    return re.sub(r"([(\[„«])\s+", r"\1", text)


# SPEC_05 sect. 8. O-001..O-029
class TextEditor:
    def __init__(self, project: OcrProject) -> None:
        self._project = project

    # --- O-020: editarea directa -----------------------------------------------------

    def set_word_text(self, word: WordData, text: str) -> None:
        """Pastreaza `original_text`, pune `is_edited`, scoate `is_verified`.
        Cuvantul scris de utilizator nu mai e nesigur. Modificarea ajunge si in
        stratul de text exportat (exportul citeste textul cuvintelor)."""
        word_id = self._id(word)
        if VerifyOptions.from_settings(self._project.settings()).fix_punctuation_spaces:
            text = fix_punctuation_spaces(text)
        project = self._project
        with project._history("edit_text", {"words": 1}), project._con:
            project._con.execute(
                "UPDATE word SET original_text = COALESCE(original_text, text), text = ?,"
                " is_edited = 1, is_verified = 0, is_uncertain = 0 WHERE id = ?",
                (text, word_id))
            self._page_back_to_recognized([word_id])
        project._after_change()

    # O-008: un simbol care nu e pe tastatura
    def insert_symbol(self, word: WordData, position: int, symbol: str) -> None:
        if not symbol:
            raise ValueError("simbolul lipseste")
        position = max(0, min(position, len(word.text)))
        self.set_word_text(word, word.text[:position] + symbol + word.text[position:])

    # --- O-001, O-002: cuvintele nesigure ----------------------------------------------

    def _candidates(self, pages: Sequence[PageData]) -> Iterator[WordData]:
        options = VerifyOptions.from_settings(self._project.settings())
        if not options.check_uncertain:
            return
        for page in pages:
            for word in page.iter_words():
                if not word.is_uncertain or word.is_verified or word.is_redacted:
                    continue
                core = bare(word.text)
                if options.ignore_words_with_digits and (
                        any(ch.isdigit() for ch in core)
                        or any(not ch.isalnum() and ch != "-" for ch in core)):
                    continue  # O-012: cuvinte cu cifre si caractere speciale
                if not options.check_compound_words and "-" in core:
                    continue  # O-012: cuvintele compuse nu se verifica
                yield word

    def next_uncertain(self, pages: Sequence[PageData],
                       after: WordData | None = None) -> WordData | None:
        """O-002 (SPEC_05: O-004). None cand nu mai urmeaza niciunul (mesaj)."""
        if after is None:
            return next(self._candidates(pages), None)
        return self._after_position(pages, after, forward=True)

    def previous_uncertain(self, pages: Sequence[PageData],
                           before: WordData | None = None) -> WordData | None:
        """O-002 (SPEC_05: O-005)."""
        if before is None:
            words = list(self._candidates(pages))
            return words[-1] if words else None
        return self._after_position(pages, before, forward=False)

    def _after_position(self, pages: Sequence[PageData], word: WordData,
                        forward: bool) -> WordData | None:
        """Urmatorul (anteriorul) nesigur fata de pozitia unui cuvant oarecare."""
        order = {w.id: i for i, w in enumerate(w for p in pages for w in p.iter_words())}
        if word.id not in order:
            return None
        where = order[word.id]
        candidates = list(self._candidates(pages))
        if forward:
            return next((w for w in candidates if order[w.id] > where), None)
        before = [w for w in candidates if order[w.id] < where]
        return before[-1] if before else None

    # --- O-003..O-007, O-011: dialogul de verificare -------------------------------------

    def skip(self, word: WordData) -> None:
        """O-004: scoate evidentierea fara sa schimbe textul."""
        self._update([self._id(word)], "is_verified = 1", "verify_skip")

    def add_to_dictionary(self, word: WordData, language: str | None = None) -> bool:
        """O-006: cuvantul intra in dictionarul limbii lui si nu mai e semnalat
        nicaieri in proiect. False daca era deja (P-041)."""
        from app.core.ocr.dictionary import DictionaryService

        text = bare(word.text)
        code = language or word.language_code or self._project.settings().ocr_settings(
            ).languages[0]
        added = DictionaryService(self._project._ctx.app_db,
                                  self._project.settings()).add(text, code)
        same = [w.id for p in self._project.pages for w in p.iter_words()
                if bare(w.text) == text and w.id is not None]
        self._update(same, "in_dictionary = 1, is_uncertain = 0", "add_to_dictionary")
        return added

    def suggestions(self, word: WordData, limit: int = 8) -> list[str]:
        """O-005, O-010: din dictionarul utilizatorului; pentru CJK, cuvintele
        cu caractere de aspect asemanator."""
        from app.core.ocr.dictionary import DictionaryService
        from app.core.ocr.languages import CJK

        code = word.language_code or self._project.settings().ocr_settings().languages[0]
        if code in CJK:
            return cjk_variants(word.text, limit)
        return DictionaryService(self._project._ctx.app_db,
                                 self._project.settings()).suggest(bare(word.text), code, limit)

    def mark_verified(self, page: PageData) -> None:
        """O-011 (`Ctrl+T`): pagina devine `VERIFIED`, cuvintele ei verificate."""
        project = self._project
        with project._history("mark_verified", {"page": page.page_number}), project._con:
            project._con.execute(
                "UPDATE word SET is_verified = 1 WHERE line_id IN (SELECT l.id FROM text_line l"
                " JOIN text_block b ON b.id = l.block_id JOIN area a ON a.id = b.area_id"
                " WHERE a.page_id = ?)", (page.id,))
            project._con.execute("UPDATE page SET status = ? WHERE id = ?",
                                 (PageStatus.VERIFIED.value, page.id))
        project._after_change()

    # --- ajutoare ------------------------------------------------------------------------

    @staticmethod
    def _id(word: WordData) -> int:
        if word.id is None:
            raise ValueError("cuvantul nu e salvat in proiect")
        return word.id

    def _update(self, ids: Sequence[int], assignment: str, op: str) -> None:
        if not ids:
            return
        project = self._project
        marks = ",".join("?" * len(ids))
        with project._history(op, {"words": len(ids)}), project._con:
            project._con.execute(f"UPDATE word SET {assignment} WHERE id IN ({marks})",
                                 tuple(ids))
        project._after_change()

    def _page_back_to_recognized(self, word_ids: Sequence[int]) -> None:
        """O pagina verificata in care se schimba textul nu mai e verificata."""
        marks = ",".join("?" * len(word_ids))
        self._project._con.execute(
            f"UPDATE page SET status = 'recognized' WHERE status = 'verified' AND id IN ("
            f"SELECT a.page_id FROM word w JOIN text_line l ON l.id = w.line_id"
            f" JOIN text_block b ON b.id = l.block_id JOIN area a ON a.id = b.area_id"
            f" WHERE w.id IN ({marks}))", tuple(word_ids))


def cjk_variants(text: str, limit: int = 8) -> list[str]:
    """O-010: textul cu cate un caracter inlocuit de unul cu aspect asemanator."""
    out: list[str] = []
    for i, ch in enumerate(text):
        for group in CJK_LOOKALIKES:
            if ch in group:
                out += [text[:i] + other + text[i + 1:] for other in group if other != ch]
    return list(dict.fromkeys(out))[:limit]
