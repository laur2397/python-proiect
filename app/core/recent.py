"""Documentele recente (faza 6c, pasul 6c.1): A-102…A-105, A-111.

Tabela `recent_document` din app.db (SPEC_04): maximum 50 de intrari, taiate
de trigger. Un document deschis din nou urca primul; un fisier mutat sau sters
ramane in lista, marcat ca lipsa (A-102). Cautarea ignora diacriticele si
majusculele si se uita in nume si in cale (A-103).
"""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.core import db

KINDS = ("pdf", "ocr_project", "image", "office", "other")
"""Valorile `doc_kind` din SPEC_04."""


def _plain(text: str) -> str:
    """Fara diacritice si fara majuscule: „Brașov” → „brasov”."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch)).casefold()


@dataclass(frozen=True, slots=True)
class RecentDocument:
    path: Path
    display_name: str
    kind: str
    opened_at: str
    page_count: int | None = None
    last_page: int = 1

    @property
    def exists(self) -> bool:
        """A-102: fisierul mutat sau sters se marcheaza in lista."""
        return self.path.exists()


class RecentDocuments:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def add(self, path: Path, kind: str, *, display_name: str | None = None,
            page_count: int | None = None, last_page: int = 1) -> None:
        """Documentul deschis sau salvat urca primul in lista."""
        if kind not in KINDS:
            raise ValueError(f"tip de document necunoscut: {kind!r}; permise: {KINDS}")
        path = Path(path).resolve()
        name = display_name or path.name
        with self._con:  # sters si reinserat: id nou, deci primul si in aceeasi secunda
            self._con.execute("DELETE FROM recent_document WHERE path = ?", (str(path),))
            self._con.execute(
                "INSERT INTO recent_document (path, display_name, doc_kind, page_count,"
                " opened_at, last_page) VALUES (?, ?, ?, ?, ?, ?)",
                (str(path), name, kind, page_count, db._utc_now(), max(1, last_page)))

    def list(self, *, kind: str | None = None, query: str = "") -> list[RecentDocument]:
        """Cel mai recent primul; `query` cauta in nume si cale (A-103)."""
        sql = ("SELECT path, display_name, doc_kind, opened_at, page_count, last_page"
               " FROM recent_document")
        args: tuple[str, ...] = ()
        if kind is not None:
            sql += " WHERE doc_kind = ?"
            args = (kind,)
        rows = self._con.execute(sql + " ORDER BY opened_at DESC, id DESC", args).fetchall()
        docs = [RecentDocument(Path(p), n, k, t, c, lp) for p, n, k, t, c, lp in rows]
        needle = _plain(query.strip())
        if needle:
            docs = [d for d in docs if needle in _plain(d.display_name)
                    or needle in _plain(str(d.path))]
        return docs

    def last(self, kind: str) -> RecentDocument | None:
        """Cel mai recent document de un tip (X-001: ultimul proiect OCR)."""
        found = self.list(kind=kind)
        return found[0] if found else None

    def remove(self, path: Path) -> None:
        """A-104: intrarea dispare; fisierul nu se atinge."""
        with self._con:
            self._con.execute("DELETE FROM recent_document WHERE path = ?",
                              (str(Path(path).resolve()),))

    def clear(self) -> None:
        """A-105: lista goala (confirmarea o cere interfata)."""
        with self._con:
            self._con.execute("DELETE FROM recent_document")
