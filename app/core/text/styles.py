"""Stilurile de text (faza 5, pasul 5.3): O-035..O-041, O-110, O-111.

`StyleManager` din SPEC_05, pe tabela `text_style` din app.db. Un bloc de text
foloseste un stil prin `text_block.style_name`. Stilurile `Heading 1`…`Heading
10` sunt livrate (`is_builtin`), cu rolul de titlu corespunzator (O-041,
O-110); titlurile detectate automat le primesc (O-111, `structure.py`).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import fields
from typing import Any

from app.core.model import BlockData, PageData, TextStyle

HEADING_STYLE = "Heading {}"
MAX_HEADING = 10

_COLUMNS = ("name", "font_name", "font_size", "horizontal_scale", "letter_spacing",
            "is_bold", "is_italic", "is_underline", "is_smallcaps", "text_color",
            "background_color", "heading_level", "is_builtin")
EDITABLE = ("name", "font_name", "font_size", "horizontal_scale", "letter_spacing",
            "is_bold", "is_italic", "is_underline", "is_smallcaps", "text_color",
            "background_color", "heading_level")
"""O-037, O-110: numele, fontul, marimea, spatierea, scara, B, I, Aa, rolul."""


def heading_name(level: int) -> str:
    return HEADING_STYLE.format(level)


# SPEC_05 sect. 8. O-021..O-026 (cerintele reale O-035..O-041)
class StyleManager:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._ensure_headings()

    def _ensure_headings(self) -> None:
        """O-111: stilurile `Heading N` livrate, cu rolul de titlu N."""
        with self._con:
            for level in range(1, MAX_HEADING + 1):
                self._con.execute(
                    "INSERT OR IGNORE INTO text_style (name, font_size, is_bold, heading_level,"
                    " is_builtin) VALUES (?, ?, 1, ?, 1)",
                    (heading_name(level), max(10.0, 24.0 - 2 * (level - 1)), level))

    def all(self) -> list[TextStyle]:
        return [self._style(row) for row in self._con.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM text_style ORDER BY is_builtin DESC, name")]

    def get(self, name: str) -> TextStyle:
        row = self._con.execute(f"SELECT {', '.join(_COLUMNS)} FROM text_style WHERE name = ?",
                                (name,)).fetchone()
        if row is None:
            raise ValueError(f"stilul {name!r} nu exista")
        return self._style(row)

    # O-038
    def create(self, name: str, /, **props: Any) -> TextStyle:
        """Nume unic, altfel `ValueError`."""
        name = (name or "").strip()
        if not name:
            raise ValueError("stilul are nevoie de un nume")
        if self._exists(name):
            raise ValueError(f"exista deja un stil {name!r}")
        with self._con:
            self._con.execute("INSERT INTO text_style (name) VALUES (?)", (name,))
        if props:
            return self.update(name, **props)
        return self.get(name)

    # O-036, O-037, O-110
    def update(self, name: str, /, **props: Any) -> TextStyle:
        """Schimba proprietatile din `Style Editor`."""
        current = self.get(name)
        unknown = set(props) - set(EDITABLE)
        if unknown:
            raise ValueError(f"proprietati necunoscute: {sorted(unknown)}")
        if "heading_level" in props and not 0 <= int(props["heading_level"]) <= MAX_HEADING:
            raise ValueError("heading_level: intre 0 (fara) si 10")
        if "font_size" in props and props["font_size"] is not None and not (
                1 <= float(props["font_size"]) <= 1638):
            raise ValueError("font_size: intre 1 si 1638")
        if "horizontal_scale" in props and float(props["horizontal_scale"]) <= 0:
            raise ValueError("horizontal_scale: mai mare decat 0")
        new_name = str(props.get("name", name)).strip()
        if current.is_builtin and new_name != name:
            raise ValueError("stilurile livrate nu se redenumesc")
        if new_name != name and self._exists(new_name):
            raise ValueError(f"exista deja un stil {new_name!r}")
        values = {k: (int(bool(v)) if k.startswith("is_") else v) for k, v in props.items()}
        values["name"] = new_name
        assignment = ", ".join(f"{k} = ?" for k in values)
        with self._con:
            self._con.execute(f"UPDATE text_style SET {assignment} WHERE name = ?",
                              (*values.values(), name))
        return self.get(new_name)

    # O-039
    def merge(self, styles: Sequence[TextStyle], into: str, project: Any = None) -> TextStyle:
        """`Merge Styles`: stilurile date dispar, iar blocurile care le foloseau
        (in proiectul dat) trec la `into`, care trebuie sa existe."""
        target = self.get(into)
        names = [s.name for s in styles if s.name != into]
        if project is not None and names:
            marks = ",".join("?" * len(names))
            with project._history("merge_styles", {"into": into}), project._con:
                project._con.execute(
                    f"UPDATE text_block SET style_name = ? WHERE style_name IN ({marks})",
                    (into, *names))
            project._after_change()
        with self._con:
            for name in names:
                if not self.get(name).is_builtin:
                    self._con.execute("DELETE FROM text_style WHERE name = ?", (name,))
        return target

    def delete(self, name: str) -> None:
        if self.get(name).is_builtin:
            raise ValueError("stilurile livrate nu se sterg")
        with self._con:
            self._con.execute("DELETE FROM text_style WHERE name = ?", (name,))

    # O-040: `Previous Fragment` / `Next Fragment`
    def fragments_using(self, pages: Sequence[PageData], style_name: str) -> list[BlockData]:
        from app.core.model import _area_blocks

        return [b for page in pages for area in page._ordered_areas()
                for b in _area_blocks(area) if b.style_name == style_name]

    def _exists(self, name: str) -> bool:
        return self._con.execute("SELECT 1 FROM text_style WHERE name = ?",
                                 (name,)).fetchone() is not None

    @staticmethod
    def _style(row: tuple[Any, ...]) -> TextStyle:
        data = dict(zip(_COLUMNS, row, strict=True))
        names = {f.name for f in fields(TextStyle)}
        out = {k: (bool(v) if k.startswith("is_") else v) for k, v in data.items() if k in names}
        out["horizontal_scale"] = float(out["horizontal_scale"] or 100.0)
        out["letter_spacing"] = float(out["letter_spacing"] or 0.0)
        return TextStyle(**out)
