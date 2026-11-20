"""Geometria zonelor: reuniune, diferenta, suprapunere, puncte pe contur.

Pasul 3b (M-012..M-014, M-034, M-107). Fara dependente: shapely ar aduce GEOS,
care e LGPL (docs/plan/faza_3_pasi.md, decizia 2).

Doua metode, ambele exacte pentru ce le trebuie:
- poligoanele cu laturi orizontale si verticale (rectiliniare) se calculeaza
  pe o grila formata doar din coordonatele colturilor lor. Add / cut part
  adauga sau taie dreptunghiuri, deci raman rectiliniare;
- un poligon cu laturi oblice (dupa mutarea unui maner) se verifica dupa
  centrul fiecarui pixel. Doua zone care doar se ating nu au niciun centru de
  pixel comun, deci nu se suprapun.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.core.model import Point, Rect

PolygonPts = Sequence[tuple[int, int]]

MAX_SAMPLES = 16_000_000
"""Limita pentru verificarea pe pixeli (o pagina A0 la 300 dpi are ~140 de milioane)."""


def is_rectilinear(poly: PolygonPts) -> bool:
    n = len(poly)
    return all(poly[i][0] == poly[(i + 1) % n][0] or poly[i][1] == poly[(i + 1) % n][1]
               for i in range(n))


def area_of(poly: PolygonPts) -> float:
    """Aria (formula sireturilor), mereu pozitiva."""
    n = len(poly)
    s = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
            for i in range(n))
    return abs(s) / 2


def _inside(px: np.ndarray, py: np.ndarray, poly: PolygonPts) -> np.ndarray:
    """Testul razei (par-impar), vectorizat, pentru punctele (px, py)."""
    inside = np.zeros(px.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if y1 == y2:
            continue
        crosses = (y1 > py) != (y2 > py)
        x_at = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        inside ^= crosses & (px < x_at)
    return inside


def _grid(polys: Sequence[PolygonPts]) -> tuple[list[int], list[int]]:
    xs = sorted({p[0] for poly in polys for p in poly})
    ys = sorted({p[1] for poly in polys for p in poly})
    return xs, ys


def _cells(poly: PolygonPts, xs: list[int], ys: list[int]) -> np.ndarray:
    """Celulele grilei din interiorul poligonului (dupa centrul lor)."""
    cx = (np.array(xs[:-1]) + np.array(xs[1:])) / 2
    cy = (np.array(ys[:-1]) + np.array(ys[1:])) / 2
    gx, gy = np.meshgrid(cx, cy)
    return _inside(gx, gy, poly)


def bbox(poly: PolygonPts) -> Rect:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


# M-034: suprapunerea interioarelor; atingerea pe o latura nu conteaza
def polygons_overlap(a: PolygonPts, b: PolygonPts) -> bool:
    ra, rb = bbox(a), bbox(b)
    if not ra.intersects(rb):
        return False
    if is_rectilinear(a) and is_rectilinear(b):
        xs, ys = _grid([a, b])
        return bool((_cells(a, xs, ys) & _cells(b, xs, ys)).any())
    x0, y0 = max(ra.x, rb.x), max(ra.y, rb.y)
    x1, y1 = min(ra.right, rb.right), min(ra.bottom, rb.bottom)
    step = max(1, int(np.ceil(np.sqrt((x1 - x0) * (y1 - y0) / MAX_SAMPLES))))
    gx, gy = np.meshgrid(np.arange(x0, x1, step) + 0.5, np.arange(y0, y1, step) + 0.5)
    return bool((_inside(gx, gy, a) & _inside(gx, gy, b)).any())


def point_inside(point: Point, poly: PolygonPts) -> bool:
    return bool(_inside(np.array([point[0] + 0.0]), np.array([point[1] + 0.0]), poly)[0])


class ShapeError(ValueError):
    """Rezultatul n-ar mai fi o singura zona: doua bucati, o gaura sau nimic."""


def _trace(grid: np.ndarray, xs: list[int], ys: list[int]) -> list[tuple[int, int]]:
    """Conturul regiunii din grila, ca un singur poligon rectiliniar.
    ShapeError daca regiunea e goala, are mai multe bucati sau gauri."""
    if not grid.any():
        raise ShapeError("zona ar ramane goala")
    rows, cols = grid.shape
    padded = np.pad(grid, 1)
    edges: dict[tuple[int, int], tuple[int, int]] = {}
    count = 0
    # muchiile de contur, orientate (interiorul la dreapta, in coordonate cu y in jos)
    for r in range(rows):
        for c in range(cols):
            if not grid[r, c]:
                continue
            pr, pc = r + 1, c + 1
            if not padded[pr - 1, pc]:  # sus
                edges[(c, r)] = (c + 1, r)
                count += 1
            if not padded[pr, pc + 1]:  # dreapta
                edges[(c + 1, r)] = (c + 1, r + 1)
                count += 1
            if not padded[pr + 1, pc]:  # jos
                edges[(c + 1, r + 1)] = (c, r + 1)
                count += 1
            if not padded[pr, pc - 1]:  # stanga
                edges[(c, r + 1)] = (c, r)
                count += 1
    if len(edges) != count:
        raise ShapeError("zona ar avea colturi care se ating intr-un singur punct")
    start = next(iter(edges))
    loop = [start]
    cur = edges[start]
    while cur != start:
        loop.append(cur)
        cur = edges[cur]
    if len(loop) != len(edges):
        raise ShapeError("zona s-ar imparti in doua bucati sau ar avea o gaura")
    # pastreaza doar colturile (scoate punctele de pe aceeasi linie)
    pts = [(xs[c], ys[r]) for c, r in loop]
    corners = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        if (p0[0] == p1[0] == p2[0]) or (p0[1] == p1[1] == p2[1]):
            continue
        corners.append(p1)
    return corners


def _rect_pts(r: Rect) -> list[tuple[int, int]]:
    return [(r.x, r.y), (r.right, r.y), (r.right, r.bottom), (r.x, r.bottom)]


def _combine(poly: PolygonPts, rect: Rect, op: str) -> list[tuple[int, int]]:
    if not is_rectilinear(poly):
        raise ShapeError("add/cut part merge doar pe zone cu laturi orizontale si verticale")
    part = _rect_pts(rect)
    xs, ys = _grid([poly, part])
    a, b = _cells(poly, xs, ys), _cells(part, xs, ys)
    return _trace(a | b if op == "add" else a & ~b, xs, ys)


# M-013
def add_rect(poly: PolygonPts, rect: Rect) -> list[tuple[int, int]]:
    """Reuniunea zonei cu dreptunghiul. Dreptunghiul trebuie sa atinga zona."""
    return _combine(poly, rect, "add")


# M-014
def cut_rect(poly: PolygonPts, rect: Rect) -> list[tuple[int, int]]:
    """Zona fara dreptunghi (o scobitura). Nu poate despica zona si nu poate
    face o gaura in mijlocul ei."""
    return _combine(poly, rect, "cut")


# M-012
def insert_vertex(poly: PolygonPts, point: Point, tolerance: float = 3.0) -> list[tuple[int, int]]:
    """Adauga un maner pe contur, in punctul cel mai apropiat de `point` pe
    latura pe care a dat clic. ValueError daca punctul nu e pe contur."""
    px, py = point
    best, best_d = None, tolerance
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length2))
        qx, qy = x1 + t * dx, y1 + t * dy
        d = ((qx - px) ** 2 + (qy - py) ** 2) ** 0.5
        if d <= best_d:
            best, best_d = (i, (round(qx), round(qy))), d
    if best is None:
        raise ValueError(f"punctul {point} nu e pe conturul zonei")
    i, q = best
    pts = [tuple(p) for p in poly]
    if q in pts:
        return pts  # e deja un colt
    return pts[:i + 1] + [q] + pts[i + 1:]
