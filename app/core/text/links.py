"""Legaturile din textul recunoscut (faza 5, pasul 5.4): O-050..O-056, F-027.

[DECIZIE AUTONOMA] (faza_5_pasi.md, decizia 1) O legatura e o adnotare `link`
in project.db: adresa in `content`, textul afisat in `subject`, cuvintele
legate in `geometry` (`{"word_ids": [...]}`), dreptunghiul lor in `bbox_*`.

Tipurile din dialogul `Edit Hyperlink` (O-053..O-056): pagina web (protocol si
adresa), fisier local (`file://`), adresa de e-mail (`mailto:`). F-027:
legaturile cer prefixul.

INCOMPLET, marcat: la mutarea paginilor intre proiecte (J-065) legaturile nu se
copiaza (cuvintele primesc alte id-uri).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.model import PageData, Rect, WordData

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

WEB, FILE, EMAIL = "web", "file", "email"
WEB_PROTOCOLS = ("http://", "https://", "ftp://")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(slots=True)
class Link:
    id: int
    page_number: int
    url: str
    text_to_display: str
    word_ids: tuple[int, ...]
    bbox: Rect

    @property
    def kind(self) -> str:
        if self.url.startswith("mailto:"):
            return EMAIL
        if self.url.startswith("file://"):
            return FILE
        return WEB

    @property
    def tooltip(self) -> str:
        """O-050: adresa care apare la trecerea mouse-ului."""
        return self.url


# O-054..O-056, F-027
def make_url(kind: str, address: str, protocol: str = "https://") -> str:
    """Adresa completa, cu prefixul cerut de tip."""
    address = (address or "").strip()
    if not address:
        raise ValueError("adresa legaturii lipseste")
    if kind == WEB:
        if any(address.lower().startswith(p) for p in WEB_PROTOCOLS):
            return address
        if protocol not in WEB_PROTOCOLS:
            raise ValueError(f"protocol necunoscut: {protocol!r}; permise: {WEB_PROTOCOLS}")
        return protocol + address
    if kind == FILE:
        if address.startswith("file://"):
            return address
        return Path(address).absolute().as_uri()
    if kind == EMAIL:
        bare = address.removeprefix("mailto:")
        if not _EMAIL.fullmatch(bare):
            raise ValueError(f"adresa de e-mail nu e valida: {bare!r}")
        return "mailto:" + bare
    raise ValueError(f"tip de legatura necunoscut: {kind!r}")


class LinkEditor:
    def __init__(self, project: OcrProject) -> None:
        self._project = project

    def links(self, page: PageData) -> list[Link]:
        out = []
        for lid, url, text, geometry, x, y, w, h in self._project._con.execute(
                "SELECT id, content, subject, geometry, bbox_x, bbox_y, bbox_w, bbox_h"
                " FROM annotation WHERE page_id = ? AND annot_type = 'link' ORDER BY id",
                (page.id,)):
            out.append(Link(int(lid), page.page_number, url or "", text or "",
                            tuple(json.loads(geometry).get("word_ids", [])), Rect(x, y, w, h)))
        return out

    def link_at(self, page: PageData, word: WordData) -> Link | None:
        """O-050, O-051: legatura unui cuvant (tooltip, `Ctrl`+clic)."""
        return next((ln for ln in self.links(page) if word.id in ln.word_ids), None)

    # O-053..O-056
    def add(self, page: PageData, words: Sequence[WordData], kind: str, address: str, *,
            protocol: str = "https://", text_to_display: str | None = None) -> Link:
        ids = [w.id for w in words if w.id is not None]
        if not ids:
            raise ValueError("legatura are nevoie de cel putin un cuvant")
        url = make_url(kind, address, protocol)
        text = text_to_display if text_to_display is not None else " ".join(
            w.text for w in words)
        box = _union([w.bbox for w in words])
        project = self._project
        with project._history("add_link", {"page": page.page_number}), project._con:
            cur = project._con.execute(
                "INSERT INTO annotation (page_id, annot_type, content, subject, geometry,"
                " bbox_x, bbox_y, bbox_w, bbox_h) VALUES (?, 'link', ?, ?, ?, ?, ?, ?, ?)",
                (page.id, url, text, json.dumps({"word_ids": ids}), box.x, box.y, box.w,
                 box.h))
        project._after_change()
        return next(ln for ln in self.links(project.page(page.page_number))
                    if ln.id == cur.lastrowid)

    def edit(self, link: Link, *, kind: str | None = None, address: str | None = None,
             protocol: str = "https://", text_to_display: str | None = None) -> None:
        """O-053: `Edit Hyperlink`, cu `Text to display`."""
        url = make_url(kind or link.kind, address, protocol) if address is not None else link.url
        text = link.text_to_display if text_to_display is None else text_to_display
        project = self._project
        with project._history("edit_link", {"page": link.page_number}), project._con:
            project._con.execute(
                "UPDATE annotation SET content = ?, subject = ?,"
                " modified_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
                (url, text, link.id))
        project._after_change()

    def remove(self, link: Link) -> None:
        """O-052: `Remove Hyperlink`; textul ramane."""
        project = self._project
        with project._history("remove_link", {"page": link.page_number}), project._con:
            project._con.execute("DELETE FROM annotation WHERE id = ?", (link.id,))
        project._after_change()


def _union(rects: Sequence[Rect]) -> Rect:
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    return Rect(x0, y0, x1 - x0, y1 - y0)
