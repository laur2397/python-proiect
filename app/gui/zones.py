"""Geometria interactiunii cu zonele, fara Qt (faza 6b, pasul 6b.2).

Numai calcule de interfata: ce tip deseneaza o combinatie de taste (M-009),
dreptunghiul tras in orice directie (M-106), manerele si redimensionarea
(M-011, M-104), parcurgerea cu `Tab` (M-010), modul `Reorder` (M-111),
culorile din setari (M-100, M-101, X-165). Regulile zonelor (dimensiunea
minima, suprapunerea, iesirea din imagine) raman in `AreaEditor`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.model import AreaType, Rect

# M-009: tragere cu modificator, fara unealta aleasa
_MODIFIER_TYPES = {
    (True, True, False): AreaType.TEXT,  # Ctrl+Shift
    (False, True, True): AreaType.PICTURE,  # Alt+Shift
    (True, False, True): AreaType.TABLE,  # Ctrl+Alt
    (True, True, True): AreaType.BACKGROUND_PICTURE,  # Ctrl+Shift+Alt
}

HANDLE_NAMES = ("top_left", "top", "top_right", "right", "bottom_right", "bottom",
                "bottom_left", "left")
"""M-104: manere la colturi si la mijlocul laturilor."""


# M-009
def type_for_modifiers(ctrl: bool, shift: bool, alt: bool) -> AreaType | None:
    return _MODIFIER_TYPES.get((bool(ctrl), bool(shift), bool(alt)))


# M-106: orice directie de tragere
def normalize(x0: float, y0: float, x1: float, y1: float) -> Rect:
    left, right = sorted((round(x0), round(x1)))
    top, bottom = sorted((round(y0), round(y1)))
    return Rect(left, top, right - left, bottom - top)


def clamp(rect: Rect, width: int, height: int) -> Rect:
    """Dreptunghiul tras peste marginea imaginii se taie la imagine."""
    left, top = max(0, rect.x), max(0, rect.y)
    right, bottom = min(width, rect.x + rect.w), min(height, rect.y + rect.h)
    return Rect(left, top, max(0, right - left), max(0, bottom - top))


def rect_points(rect: Rect) -> list[tuple[int, int]]:
    return [(rect.x, rect.y), (rect.x + rect.w, rect.y), (rect.x + rect.w, rect.y + rect.h),
            (rect.x, rect.y + rect.h)]


# M-104
def handles(rect: Rect) -> dict[str, tuple[float, float]]:
    cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
    r, b = rect.x + rect.w, rect.y + rect.h
    return {"top_left": (rect.x, rect.y), "top": (cx, rect.y), "top_right": (r, rect.y),
            "right": (r, cy), "bottom_right": (r, b), "bottom": (cx, b),
            "bottom_left": (rect.x, b), "left": (rect.x, cy)}


def hit_handle(rect: Rect, x: float, y: float, tolerance: float) -> str | None:
    for name, (hx, hy) in handles(rect).items():
        if abs(hx - x) <= tolerance and abs(hy - y) <= tolerance:
            return name
    return None


# M-011: tragerea unei laturi sau a unui colt
def resize(rect: Rect, handle: str, x: float, y: float) -> Rect:
    left, top, right, bottom = rect.x, rect.y, rect.x + rect.w, rect.y + rect.h
    if "left" in handle:
        left = x
    if "right" in handle:
        right = x
    if handle.startswith("top"):
        top = y
    if handle.startswith("bottom"):
        bottom = y
    return normalize(left, top, right, bottom)


# M-010
def next_index(count: int, current: int | None, *, backwards: bool = False) -> int | None:
    """`Tab` trece la zona urmatoare (`Shift+Tab` la cea anterioara), circular."""
    if count <= 0:
        return None
    if current is None:
        return count - 1 if backwards else 0
    return (current + (-1 if backwards else 1)) % count


# M-111
@dataclass
class ReorderSession:
    """Clic pe zone in ordinea dorita; numerele se recalculeaza la fiecare clic.

    `order` = toate zonele: cele apasate, in ordinea clicurilor, apoi restul in
    ordinea veche. Sesiunea e gata cand s-a facut clic pe toate."""

    original: Sequence[int]
    clicked: list[int] = field(default_factory=list)

    def click(self, area_id: int) -> list[int]:
        if area_id in self.original and area_id not in self.clicked:
            self.clicked.append(area_id)
        return self.order

    @property
    def order(self) -> list[int]:
        return [*self.clicked, *(a for a in self.original if a not in self.clicked)]

    @property
    def done(self) -> bool:
        return len(self.clicked) == len(self.original)


# M-100, M-101, X-165: culorile sunt setari, nu valori in cod
def area_style(settings: Any, area_type: AreaType) -> tuple[str, int]:
    kind = AreaType(area_type).value
    return settings.get(f"areas.color.{kind}"), int(settings.get(f"areas.border_width.{kind}"))
