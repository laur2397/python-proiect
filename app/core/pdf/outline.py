"""Editarea semnelor de carte (faza 9, pasul 9.1): F-032…F-038.

Semnele de carte se identifica prin `id`, pozitia in parcurgerea in adancime
(de la 1), ca in `navigation.bookmarks()`: dupa fiecare modificare id-urile se
recalculeaza, deci interfata reciteste arborele. Destinatia unui semn de carte e
`/XYZ` cu inaltimea dorita (inceputul paginii, implicit, F-032).

Mutarea si nivelurile (F-036) schimba doar arborele, nu aspectul documentului.
Stergerea unui parinte sterge si copiii (F-038).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.model import BookmarkData

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

MAX_LEVELS = 10
"""SPEC_05: cel mult 10 niveluri de semne de carte."""


@dataclass
class _Node:
    item: pikepdf.OutlineItem
    siblings: list[pikepdf.OutlineItem]
    """Lista din care face parte (radacina sau copiii parintelui)."""
    level: int
    parent: pikepdf.OutlineItem | None


def _index(root: list[pikepdf.OutlineItem]) -> dict[int, _Node]:
    nodes: dict[int, _Node] = {}
    counter = iter(range(1, 10_000_000))

    def walk(items: list[pikepdf.OutlineItem], level: int,
             parent: pikepdf.OutlineItem | None) -> None:
        for item in items:
            nodes[next(counter)] = _Node(item, items, level, parent)
            walk(item.children, level + 1, item)

    walk(root, 1, None)
    return nodes


def _depth(item: pikepdf.OutlineItem) -> int:
    return 1 + max((_depth(c) for c in item.children), default=0)


def _descendants(item: pikepdf.OutlineItem) -> list[pikepdf.OutlineItem]:
    out = []
    for child in item.children:
        out.append(child)
        out += _descendants(child)
    return out


def _item(pdf: pikepdf.Pdf, title: str, page: int, y: float | None) -> pikepdf.OutlineItem:
    """Semnul de carte catre pagina `page` (de la 1), la inaltimea `y` (puncte de
    la marginea de sus a paginii; None = inceputul paginii)."""
    from app.core.pdf.text import page_geometry

    if not 1 <= page <= len(pdf.pages):
        raise ValueError(f"pagina {page} nu exista (1..{len(pdf.pages)})")
    _left, bottom, height = page_geometry(pdf.pages[page - 1])
    top = bottom + height - (y or 0.0)
    return pikepdf.OutlineItem(title, page - 1, pikepdf.PageLocation.XYZ, top=top)


def _title(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValueError("numele semnului de carte nu poate fi gol (F-037)")
    return title


def _require(nodes: dict[int, _Node], bm_id: int) -> _Node:
    if bm_id not in nodes:
        raise KeyError(bm_id)
    return nodes[bm_id]


def _edit(document: PdfDocument, change: Any) -> Any:
    pdf = document._pike()
    with pdf.open_outline() as outline:
        result = change(pdf, outline.root, _index(outline.root))
    document._changed()
    return result


def _snapshot(document: PdfDocument) -> dict[int, _Node]:
    """Indexul arborelui, pentru calcule; nu se modifica nimic."""
    with document._pike().open_outline() as outline:
        return _index(outline.root)


def _id_of(nodes: dict[int, _Node], item: pikepdf.OutlineItem | None) -> int | None:
    if item is None:
        return None
    return next(i for i, n in nodes.items() if n.item is item)


# F-032, F-033, F-035
def add_bookmark(document: PdfDocument, bm: BookmarkData, parent_id: int | None = None, *,
                 after_id: int | None = None) -> int:
    """Semn de carte nou catre `bm.target_page` / `bm.target_y`. Imbricarea
    urmeaza semnul de carte selectat inainte (F-035): `after_id` = noul semn de
    carte vine imediat dupa el, la acelasi nivel; `parent_id` = ultimul copil al
    lui; fara ele, la sfarsitul radacinii (primul semn de carte ajunge acolo).
    Intoarce id-ul noului semn de carte."""
    title = _title(bm.title)
    if bm.target_page is None:
        raise ValueError("semnul de carte cere o pagina tinta")

    def change(pdf: pikepdf.Pdf, root: list, nodes: dict[int, _Node]) -> int:
        item = _item(pdf, title, bm.target_page, bm.target_y)
        if after_id is not None:
            node = _require(nodes, after_id)
            node.siblings.insert(node.siblings.index(node.item) + 1, item)
        elif parent_id is not None:
            node = _require(nodes, parent_id)
            if node.level >= MAX_LEVELS:
                raise ValueError(f"cel mult {MAX_LEVELS} niveluri")
            node.item.children.append(item)
        else:
            root.append(item)
        return _id_of(_index(root), item) or 0

    return int(_edit(document, change))


# F-036
def move_bookmark(document: PdfDocument, bm_id: int, parent_id: int | None, index: int
                  ) -> None:
    """Semnul de carte (cu copiii lui) devine copilul `index` al lui `parent_id`
    (None = radacina). Nu poate ajunge in propriii descendenti."""
    def change(pdf: pikepdf.Pdf, root: list, nodes: dict[int, _Node]) -> None:
        node = _require(nodes, bm_id)
        target = root
        if parent_id is not None:
            parent = _require(nodes, parent_id)
            if parent.item is node.item or parent.item in _descendants(node.item):
                raise ValueError("un semn de carte nu se muta in descendentii lui")
            if parent.level + _depth(node.item) > MAX_LEVELS:
                raise ValueError(f"cel mult {MAX_LEVELS} niveluri")
            target = parent.item.children
        node.siblings.remove(node.item)
        target.insert(max(0, min(index, len(target))), node.item)

    _edit(document, change)


def indent(document: PdfDocument, bm_id: int) -> None:
    """`Move one level right`: devine ultimul copil al fratelui dinaintea lui."""
    nodes = _snapshot(document)
    node = _require(nodes, bm_id)
    position = node.siblings.index(node.item)
    if position == 0:
        raise ValueError("primul semn de carte de pe nivel nu se poate muta la dreapta")
    previous = node.siblings[position - 1]
    move_bookmark(document, bm_id, _id_of(nodes, previous), len(previous.children))


def outdent(document: PdfDocument, bm_id: int) -> None:
    """`Move one level left`: devine fratele de dupa parintele lui."""
    nodes = _snapshot(document)
    node = _require(nodes, bm_id)
    if node.parent is None:
        raise ValueError("un semn de carte de pe primul nivel nu se poate muta la stanga")
    parent = nodes[_id_of(nodes, node.parent)]  # type: ignore[index]
    move_bookmark(document, bm_id, _id_of(nodes, parent.parent),
                  parent.siblings.index(parent.item) + 1)


# F-037
def rename_bookmark(document: PdfDocument, bm_id: int, title: str) -> None:
    title = _title(title)

    def change(pdf: pikepdf.Pdf, root: list, nodes: dict[int, _Node]) -> None:
        _require(nodes, bm_id).item.title = title

    _edit(document, change)


# F-034
def set_destination(document: PdfDocument, bm_id: int, page: int, y: float | None = None
                    ) -> None:
    """`Set Destination`: tinta noua, aceeasi pozitie in arbore."""
    def change(pdf: pikepdf.Pdf, root: list, nodes: dict[int, _Node]) -> None:
        node = _require(nodes, bm_id)
        fresh = _item(pdf, str(node.item.title), page, y)
        fresh.children[:] = list(node.item.children)
        fresh.is_closed = node.item.is_closed
        node.siblings[node.siblings.index(node.item)] = fresh

    _edit(document, change)


# F-038
def delete_bookmarks(document: PdfDocument, ids: Sequence[int]) -> int:
    """Sterge semnele de carte alese, cu copiii lor. Intoarce cate s-au sters
    (cu tot cu copii)."""
    def change(pdf: pikepdf.Pdf, root: list, nodes: dict[int, _Node]) -> int:
        removed = 0
        for node in [_require(nodes, i) for i in ids]:
            if node.item in node.siblings:
                removed += 1 + len(_descendants(node.item))
                node.siblings.remove(node.item)
        return removed

    return int(_edit(document, change))
