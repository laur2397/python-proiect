"""Tabelele: structura, separatoarele, celulele unite.

Implementeaza `TableAnalyzer` din SPEC_05 sectiunea 6, pasul 3d din
docs/plan/faza_3_pasi.md (M-040..M-049). Operatiile pe `TableData` sunt pure;
salvarea in table_cell si table_separator e in AreaEditor (areas.py).

Modelul intern: o grila (pozitiile liniilor orizontale si verticale, in
pixelii paginii) si celulele ca dreptunghiuri in indicii grilei
(r0, c0, r1, c1), capatul exclusiv. O celula unita acopera mai multe casute.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from app.core.errors import CellsNotRectangularError, WrongAreaTypeError
from app.core.images.preprocess import otsu_threshold, to_array, to_gray
from app.core.model import (
    AreaData,
    PageData,
    PageWarning,
    Px,
    Rect,
    TableCellData,
    TableData,
)

WARNING_CODE = "TABLE_STRUCTURE_NOT_FOUND"
WARNING_KEY = "warning.table_structure"
"""M-049: structura nedetectabila: o celula si un avertisment, nu o eroare."""

AXES = ("horizontal", "vertical")


@dataclass
class _Grid:
    xs: list[int]
    ys: list[int]
    cells: list[tuple[int, int, int, int]]
    flags: dict[tuple[int, int, int, int], tuple[bool, bool]] = field(default_factory=dict)
    """(as_picture, is_header) pe celula."""


def _to_grid(table: TableData, bbox: Rect | None = None) -> _Grid:
    left = bbox.x if bbox else min((c.bbox.x for c in table.cells), default=0)
    top = bbox.y if bbox else min((c.bbox.y for c in table.cells), default=0)
    right = bbox.right if bbox else max((c.bbox.right for c in table.cells), default=0)
    bottom = bbox.bottom if bbox else max((c.bbox.bottom for c in table.cells), default=0)
    xs = [left, *sorted(table.v_separators), right]
    ys = [top, *sorted(table.h_separators), bottom]
    cells, flags = [], {}
    for c in table.cells:
        key = (c.row, c.col, c.row + c.row_span, c.col + c.col_span)
        cells.append(key)
        flags[key] = (c.as_picture, c.is_header)
    return _Grid(xs, ys, cells, flags)


def _to_table(g: _Grid) -> TableData:
    cells = []
    for r0, c0, r1, c1 in sorted(g.cells):
        pic, head = g.flags.get((r0, c0, r1, c1), (False, False))
        cells.append(TableCellData(
            id=None, row=r0, col=c0, row_span=r1 - r0, col_span=c1 - c0,
            bbox=Rect(g.xs[c0], g.ys[r0], g.xs[c1] - g.xs[c0], g.ys[r1] - g.ys[r0]),
            as_picture=pic, is_header=head))
    return TableData(rows=len(g.ys) - 1, cols=len(g.xs) - 1, cells=cells,
                     h_separators=g.ys[1:-1], v_separators=g.xs[1:-1])


def single_cell(bbox: Rect) -> TableData:
    """Tabelul 1x1 al unei zone."""
    return _to_table(_Grid([bbox.x, bbox.right], [bbox.y, bbox.bottom], [(0, 0, 1, 1)]))


def from_separators(bbox: Rect, h: Sequence[int], v: Sequence[int]) -> TableData:
    """Tabel cu toate casutele separate (fara celule unite)."""
    xs = [bbox.x, *sorted(set(v)), bbox.right]
    ys = [bbox.y, *sorted(set(h)), bbox.bottom]
    cells = [(r, c, r + 1, c + 1) for r in range(len(ys) - 1) for c in range(len(xs) - 1)]
    return _to_table(_Grid(xs, ys, cells))


def _merge_overlapping(cells: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Celulele care se suprapun devin una, pana nu mai ramane nicio suprapunere."""
    cells = list(dict.fromkeys(cells))
    changed = True
    while changed:
        changed = False
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                a, b = cells[i], cells[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    cells[i] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]),
                                max(a[3], b[3]))
                    del cells[j]
                    changed = True
                    break
            if changed:
                break
    return cells


# SPEC_05 sect. 6. M-040..M-049
class TableAnalyzer:

    # --- M-045, M-046: separator nou -------------------------------------------------

    def add_separator(self, table: TableData, axis: str, position: Px) -> TableData:
        """Linie noua strict in interiorul tabelului. O celula unita prin care
        trece linia se taie in doua."""
        g = _to_grid(table)
        lines = g.ys if axis == "horizontal" else g.xs
        if axis not in AXES:
            raise ValueError(f"axa necunoscuta: {axis!r}; permise: {AXES}")
        if not lines[0] < position < lines[-1] or position in lines:
            raise ValueError(f"separatorul {position} nu e in interiorul tabelului "
                             f"sau exista deja")
        k = next(i for i, v in enumerate(lines) if v > position)  # noul index de linie
        lines.insert(k, position)
        new_cells, flags = [], {}
        for cell in g.cells:
            r0, c0, r1, c1 = cell
            if axis == "horizontal":
                r0, r1 = r0 + (r0 >= k), r1 + (r1 >= k)
                parts = [(r0, c0, k, c1), (k, c0, r1, c1)] if r0 < k < r1 else [(r0, c0, r1, c1)]
            else:
                c0, c1 = c0 + (c0 >= k), c1 + (c1 >= k)
                parts = [(r0, c0, r1, k), (r0, k, r1, c1)] if c0 < k < c1 else [(r0, c0, r1, c1)]
            for part in parts:
                new_cells.append(part)
                flags[part] = g.flags.get(cell, (False, False))
        g.cells, g.flags = new_cells, flags
        return _to_table(g)

    # --- M-047: stergerea unui separator ----------------------------------------------

    def remove_separator(self, table: TableData, axis: str, position: Px) -> TableData:
        """Randurile (sau coloanele) de o parte si de alta a liniei se unesc."""
        if axis not in AXES:
            raise ValueError(f"axa necunoscuta: {axis!r}; permise: {AXES}")
        g = _to_grid(table)
        lines = g.ys if axis == "horizontal" else g.xs
        if position not in lines[1:-1]:
            raise ValueError(f"nu exista separatorul {axis} la {position}")
        k = lines.index(position)
        del lines[k]

        # o celula care incepe pe linia stearsa incepe acum la linia de dinainte;
        # una care se termina pe ea se termina la linia de dupa (acum indicele k)
        def start(i: int) -> int:
            return i - 1 if i >= k else i

        def end(i: int) -> int:
            return i - 1 if i > k else i

        cells = []
        for r0, c0, r1, c1 in g.cells:
            if axis == "horizontal":
                cells.append((start(r0), c0, end(r1), c1))
            else:
                cells.append((r0, start(c0), r1, end(c1)))
        merged = _merge_overlapping(cells)
        g.flags = {c: (False, False) for c in merged}
        g.cells = merged
        return _to_table(g)

    # --- M-043, M-042, M-044 ----------------------------------------------------------

    def merge_cells(self, table: TableData, cells: Sequence[TableCellData]) -> TableData:
        """M-043: selectia trebuie sa fie dreptunghiulara."""
        g = _to_grid(table)
        chosen = [(c.row, c.col, c.row + c.row_span, c.col + c.col_span) for c in cells]
        if len(chosen) < 2 or any(c not in g.cells for c in chosen):
            raise ValueError("selectati cel putin doua celule ale tabelului")
        box = (min(c[0] for c in chosen), min(c[1] for c in chosen),
               max(c[2] for c in chosen), max(c[3] for c in chosen))
        covered = sum((c[2] - c[0]) * (c[3] - c[1]) for c in chosen)
        if covered != (box[2] - box[0]) * (box[3] - box[1]):
            raise CellsNotRectangularError("selectia de celule nu e dreptunghiulara")
        g.cells = [c for c in g.cells if c not in chosen] + [box]
        g.flags[box] = (False, any(g.flags.get(c, (False, False))[1] for c in chosen))
        return _to_table(g)

    def split_cells(self, table: TableData, cell: TableCellData) -> TableData:
        """M-042: numai celulele unite anterior se pot separa."""
        if cell.row_span == 1 and cell.col_span == 1:
            raise WrongAreaTypeError("numai celulele unite se pot separa (M-042)",
                                     operation="split_cells")
        g = _to_grid(table)
        key = (cell.row, cell.col, cell.row + cell.row_span, cell.col + cell.col_span)
        if key not in g.cells:
            raise ValueError("celula nu e in tabel")
        g.cells.remove(key)
        flag = g.flags.pop(key, (False, False))
        for r in range(key[0], key[2]):
            for c in range(key[1], key[3]):
                g.cells.append((r, c, r + 1, c + 1))
                g.flags[(r, c, r + 1, c + 1)] = flag
        return _to_table(g)

    def merge_rows(self, table: TableData, rows: Sequence[int]) -> TableData:
        """M-044: randurile consecutive selectate devin unul (liniile dintre ele
        dispar)."""
        chosen = sorted(set(rows))
        if len(chosen) < 2 or chosen != list(range(chosen[0], chosen[-1] + 1)):
            raise ValueError("selectati cel putin doua randuri consecutive")
        if chosen[0] < 0 or chosen[-1] >= table.rows:
            raise ValueError(f"randuri in afara tabelului (0..{table.rows - 1})")
        g = _to_grid(table)
        for r in reversed(chosen[1:]):
            table = self.remove_separator(table, "horizontal", g.ys[r])
        return table

    # --- M-048 -------------------------------------------------------------------------

    def set_as_picture(self, table: TableData, cells: Sequence[TableCellData],
                       as_picture: bool = True) -> TableData:
        """M-048: celulele care contin numai o imagine. Adaugare fata de SPEC_05."""
        g = _to_grid(table)
        for c in cells:
            key = (c.row, c.col, c.row + c.row_span, c.col + c.col_span)
            if key not in g.cells:
                raise ValueError("celula nu e in tabel")
            g.flags[key] = (as_picture, g.flags.get(key, (False, False))[1])
        return _to_table(g)

    # --- M-040, M-049: detectarea structurii ------------------------------------------

    def analyze_structure(self, area: AreaData, page: PageData) -> TableData:
        """Randuri, coloane si celule unite. Intai din liniile trase ale
        tabelului; fara linii, din spatiile goale. Structura nedetectabila: o
        singura celula si un PageWarning in `page.warnings` (M-049)."""
        bbox = area.bbox
        with Image.open(page.image_path) as src:
            gray = to_gray(to_array(src.crop((bbox.x, bbox.y, bbox.right, bbox.bottom))))
        ink = gray < otsu_threshold(gray) if gray.max() > gray.min() else np.zeros_like(gray, bool)
        result = _ruled(ink, bbox) or _whitespace(ink, bbox)
        if result is None:
            page.warnings.append(PageWarning("warning", WARNING_CODE, WARNING_KEY,
                                             {"area_id": area.id}))
            return single_cell(bbox)
        return result


_LINE_SHARE = 0.6
"""[DECIZIE] O linie de tabel acopera cel putin 60% din latimea (inaltimea) tabelului."""

_EDGE_MARGIN = 0.03
"""Liniile din primele / ultimele 3% sunt chenarul tabelului, nu separatoare."""


def _line_positions(mask: np.ndarray, axis: int, length: int) -> list[int]:
    """Pozitiile liniilor lungi: proiectia unei deschideri morfologice cu un
    element lung pe directia liniei."""
    size = max(3, int(length * 0.25))
    structure = np.ones((1, size) if axis == 1 else (size, 1), dtype=bool)
    lines = ndi.binary_opening(mask, structure=structure)
    profile = lines.sum(axis=axis)
    hits = np.nonzero(profile >= _LINE_SHARE * length)[0]
    groups: list[list[int]] = []
    for i in hits:
        if groups and i - groups[-1][-1] <= 2:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [round(sum(g) / len(g)) for g in groups]


def _interior(positions: list[int], extent: int) -> list[int]:
    m = max(2, round(extent * _EDGE_MARGIN))
    return [p for p in positions if m < p < extent - m]


def _ruled(ink: np.ndarray, bbox: Rect) -> TableData | None:
    h, w = ink.shape
    hs = _interior(_line_positions(ink, 1, w), h)
    vs = _interior(_line_positions(ink, 0, h), w)
    if not hs and not vs:
        return None
    ys = [0, *hs, h]
    xs = [0, *vs, w]
    # celulele unite: lipseste bucata de linie dintre doua casute
    parent = {(r, c): (r, c) for r in range(len(ys) - 1) for c in range(len(xs) - 1)}

    def find(x: tuple[int, int]) -> tuple[int, int]:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: tuple[int, int], b: tuple[int, int]) -> None:
        parent[find(a)] = find(b)

    for ci, x in enumerate(xs[1:-1], start=1):
        band = ink[:, max(0, x - 2):x + 3].any(axis=1)
        for r in range(len(ys) - 1):
            seg = band[ys[r] + 3:ys[r + 1] - 3]
            if seg.size and seg.mean() < 0.5:
                union((r, ci - 1), (r, ci))
    for ri, y in enumerate(ys[1:-1], start=1):
        band = ink[max(0, y - 2):y + 3].any(axis=0)
        for c in range(len(xs) - 1):
            seg = band[xs[c] + 3:xs[c + 1] - 3]
            if seg.size and seg.mean() < 0.5:
                union((ri - 1, c), (ri, c))
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for key in parent:
        groups.setdefault(find(key), []).append(key)
    cells = []
    for members in groups.values():
        r0, c0 = min(m[0] for m in members), min(m[1] for m in members)
        r1, c1 = max(m[0] for m in members) + 1, max(m[1] for m in members) + 1
        if len(members) == (r1 - r0) * (c1 - c0):
            cells.append((r0, c0, r1, c1))
        else:  # unire nedreptunghiulara: casutele raman separate
            cells += [(r, c, r + 1, c + 1) for r, c in members]
    grid = _Grid([bbox.x + x for x in xs], [bbox.y + y for y in ys], cells)
    return _to_table(grid)


_GAP_SHARE = 0.015
"""[DECIZIE] Un spatiu gol intre coloane are cel putin 1,5% din latimea tabelului."""


def _gaps(profile: np.ndarray, min_gap: int) -> list[int]:
    """Mijloacele golurilor (zero cerneala) dintre zone cu cerneala."""
    filled = np.nonzero(profile > 0)[0]
    if filled.size == 0:
        return []
    centers, run_start = [], None
    for i in range(int(filled[0]), int(filled[-1]) + 1):
        empty = profile[i] == 0
        if empty and run_start is None:
            run_start = i
        elif not empty and run_start is not None:
            if i - run_start >= min_gap:
                centers.append((run_start + i - 1) // 2)
            run_start = None
    return centers


def _whitespace(ink: np.ndarray, bbox: Rect) -> TableData | None:
    w = ink.shape[1]
    vs = _gaps(ink.sum(axis=0), max(3, round(w * _GAP_SHARE)))
    hs = _gaps(ink.sum(axis=1), 3)
    if not vs and not hs:
        return None
    return from_separators(bbox, [bbox.y + y for y in hs], [bbox.x + x for x in vs])
