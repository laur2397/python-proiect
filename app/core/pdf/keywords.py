"""Listele de cuvinte cheie pentru cautare si redactare (faza 7, pasul 7.2a):
C-027…C-032.

Listele se pastreaza in app.db, in tabelele `redaction_keyword_list` si
`redaction_keyword` din SPEC_04, ca sa fie disponibile in orice document.
Fiecare cuvant are optiunile lui: majuscule (C-004), cuvinte intregi (C-003)
si expresie regulata.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.pdf.text import SOURCES, SearchHit, search_document

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument


@dataclass(frozen=True, slots=True)
class Keyword:
    text: str
    match_case: bool = False
    whole_word: bool = False
    is_regex: bool = False

    def validate(self) -> None:
        if not self.text.strip():
            raise ValueError("cuvantul cheie e gol")
        if self.is_regex:
            re.compile(self.text)


class KeywordListStore:
    """Listele salvate. `con` e conexiunea la app.db (`AppContext.app_db`)."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def names(self) -> list[str]:
        rows = self._con.execute(
            "SELECT name FROM redaction_keyword_list ORDER BY name COLLATE NOCASE").fetchall()
        return [name for (name,) in rows]

    def _id(self, name: str) -> int | None:
        row = self._con.execute(
            "SELECT id FROM redaction_keyword_list WHERE name = ?", (name,)).fetchone()
        return None if row is None else int(row[0])

    def create(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("lista trebuie sa aiba un nume")
        if self._id(name) is not None:
            raise ValueError(f"exista deja o lista cu numele {name!r}")
        with self._con:
            self._con.execute("INSERT INTO redaction_keyword_list (name) VALUES (?)", (name,))

    def delete(self, name: str) -> None:
        with self._con:
            self._con.execute("DELETE FROM redaction_keyword_list WHERE name = ?", (name,))

    # C-031: cuvintele apar in tooltipul listei
    def keywords(self, name: str) -> list[Keyword]:
        list_id = self._id(name)
        if list_id is None:
            raise KeyError(name)
        rows = self._con.execute(
            "SELECT keyword, match_case, whole_word, is_regex FROM redaction_keyword"
            " WHERE list_id = ? ORDER BY id", (list_id,)).fetchall()
        return [Keyword(text, bool(mc), bool(ww), bool(rx)) for text, mc, ww, rx in rows]

    # C-027
    def add(self, name: str, keyword: Keyword | str) -> None:
        """Adauga un cuvant (textul curent din campul de cautare). Lista se
        creeaza daca nu exista; un cuvant deja prezent nu se dubleaza."""
        keyword = Keyword(keyword) if isinstance(keyword, str) else keyword
        keyword.validate()
        if self._id(name) is None:
            self.create(name)
        list_id = self._id(name)
        with self._con:
            self._con.execute(
                "INSERT OR IGNORE INTO redaction_keyword"
                " (list_id, keyword, match_case, whole_word, is_regex) VALUES (?, ?, ?, ?, ?)",
                (list_id, keyword.text, int(keyword.match_case), int(keyword.whole_word),
                 int(keyword.is_regex)))

    # C-029, C-030
    def save(self, name: str, keywords: Sequence[Keyword]) -> None:
        """`Edit Keyword List...`: lista primeste exact cuvintele date (adaugate,
        editate, sterse), intr-o singura tranzactie."""
        for keyword in keywords:
            keyword.validate()
        texts = [k.text for k in keywords]
        if len(set(texts)) != len(texts):
            raise ValueError("un cuvant apare de doua ori in lista")
        if self._id(name) is None:
            self.create(name)
        list_id = self._id(name)
        with self._con:
            self._con.execute("DELETE FROM redaction_keyword WHERE list_id = ?", (list_id,))
            self._con.executemany(
                "INSERT INTO redaction_keyword"
                " (list_id, keyword, match_case, whole_word, is_regex) VALUES (?, ?, ?, ?, ?)",
                [(list_id, k.text, int(k.match_case), int(k.whole_word), int(k.is_regex))
                 for k in keywords])


# C-028
def search_keywords(document: PdfDocument, keywords: Sequence[Keyword], *,
                    in_comments: bool = True, in_bookmarks: bool = True,
                    in_metadata: bool = True) -> list[SearchHit]:
    """Cautarea cu o lista: rezultatele tuturor cuvintelor, fara dubluri (acelasi
    fragment gasit de doua cuvinte apare o singura data), ordonate pe sursa,
    pagina si pozitie."""
    seen: set[tuple[str, int, int, int, str]] = set()
    hits: list[SearchHit] = []
    for keyword in keywords:
        keyword.validate()
        for hit in search_document(document, keyword.text, match_case=keyword.match_case,
                                   whole_word=keyword.whole_word, in_comments=in_comments,
                                   in_bookmarks=in_bookmarks, in_metadata=in_metadata,
                                   pattern=keyword.is_regex):
            key = (hit.source, hit.page, hit.start, hit.length, hit.context)
            if key not in seen:
                seen.add(key)
                hits.append(hit)
    hits.sort(key=lambda h: (SOURCES.index(h.source), h.page, h.start))
    return hits
