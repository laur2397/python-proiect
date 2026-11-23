"""Scurtaturile de tastatura reatribuibile (auditul 23.11.2026, defectul 7):
X-204…X-207, SPEC_05 `ShortcutRegistry`, tabelul `keyboard_shortcut` (SPEC_04).

Comenzile se inregistreaza de fereastra care le are (numai OCR Editor, X-204),
cu scurtatura livrata. Utilizatorul le reatribuie din dialogul `Customize`; o
combinatie deja folosita nu se poate atribui din nou fara eliberare (X-207).
`display_name` e cheia de traducere a comenzii: textul il pune interfata.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors import ShortcutConflictError

Command = tuple[str, str, str, str | None]
"""(command_id, cheia de traducere, categoria, scurtatura livrata)."""


# X-204…X-207 (SPEC_05: ShortcutRegistry)
class ShortcutStore:
    """Scurtaturile din `keyboard_shortcut` (app.db)."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def register(self, commands: Sequence[Command]) -> None:
        """Comenzile ferestrei: cele noi primesc scurtatura livrata (daca e libera);
        la cele existente se actualizeaza numele, categoria si scurtatura livrata,
        iar alegerea utilizatorului ramane."""
        with self._con:
            for command_id, name, category, default in commands:
                row = self._con.execute(
                    "SELECT id FROM keyboard_shortcut WHERE command_id = ?", (command_id,)
                ).fetchone()
                if row is not None:
                    self._con.execute(
                        "UPDATE keyboard_shortcut SET display_name = ?, category = ?,"
                        " default_shortcut = ? WHERE id = ?", (name, category, default, row[0]))
                    continue
                free = default is None or self._owner(default) is None
                self._con.execute(
                    "INSERT INTO keyboard_shortcut (command_id, display_name, category,"
                    " shortcut, default_shortcut) VALUES (?, ?, ?, ?, ?)",
                    (command_id, name, category, default if free else None, default))

    def all(self) -> list[Mapping[str, Any]]:
        rows = self._con.execute(
            "SELECT command_id, display_name, category, shortcut, default_shortcut"
            " FROM keyboard_shortcut ORDER BY category, id").fetchall()
        return [{"command_id": c, "display_name": n, "category": k, "shortcut": s,
                 "default_shortcut": d} for c, n, k, s, d in rows]

    def shortcut(self, command_id: str) -> str | None:
        row = self._con.execute("SELECT shortcut FROM keyboard_shortcut WHERE command_id = ?",
                                (command_id,)).fetchone()
        if row is None:
            raise KeyError(command_id)
        return row[0]

    def _owner(self, shortcut: str) -> str | None:
        row = self._con.execute("SELECT command_id FROM keyboard_shortcut WHERE shortcut = ?",
                                (shortcut,)).fetchone()
        return row[0] if row else None

    def assign(self, command_id: str, shortcut: str | None) -> None:
        """X-205: combinatia noua a comenzii (None = nealocata). X-207: o combinatie
        folosita de alta comanda da `ShortcutConflictError`; intai se elibereaza."""
        self.shortcut(command_id)  # KeyError pentru o comanda necunoscuta
        shortcut = shortcut or None
        if shortcut is not None:
            owner = self._owner(shortcut)
            if owner is not None and owner != command_id:
                raise ShortcutConflictError("combinatia e deja folosita", shortcut=shortcut,
                                            command=owner)
        with self._con:
            self._con.execute("UPDATE keyboard_shortcut SET shortcut = ? WHERE command_id = ?",
                              (shortcut, command_id))

    def reset_defaults(self, category: str | None = None) -> None:
        """X-206: `Reset` (categoria aleasa) sau `Reset All` (`category` None).
        O scurtatura livrata ocupata intre timp de alta comanda ramane nealocata."""
        rows = self._con.execute(
            "SELECT command_id, default_shortcut FROM keyboard_shortcut"
            + (" WHERE category = ?" if category is not None else ""),
            (category,) if category is not None else ()).fetchall()
        with self._con:
            for command_id, _default in rows:
                self._con.execute(
                    "UPDATE keyboard_shortcut SET shortcut = NULL WHERE command_id = ?",
                    (command_id,))
            for command_id, default in rows:
                if default is not None and self._owner(default) is None:
                    self._con.execute(
                        "UPDATE keyboard_shortcut SET shortcut = ? WHERE command_id = ?",
                        (default, command_id))
