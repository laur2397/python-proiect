"""Iconitele DocuLens: desene proprii, linie simpla, pe o grila 24x24.

Nu se folosesc iconitele ABBYY si nici un set extern (CLAUDE.md §6.6, §9).
Fiecare iconita e un fragment SVG desenat de noi; culoarea se da la randare,
asa ca acelasi desen merge pe fond deschis, pe butonul accentuat sau gri.
"""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

INK = "#3b4453"
"""Culoarea obisnuita a iconitelor (gri inchis, ca textul secundar)."""

_PATHS: dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
            '<path d="M14 3v5h5"/>',
    "file_plus": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                 '<path d="M14 3v5h5M12 11v6M9 14h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5'
              'a2 2 0 0 1-2-2z"/>',
    "folder_open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v1"/>'
                   '<path d="M3 17l2.5-6.5A1.5 1.5 0 0 1 7 9.5h14l-3 8a1.5 1.5 0 0 1-1.4 1H5'
                   'a2 2 0 0 1-2-2z"/>',
    "scan": '<rect x="3" y="11" width="18" height="8" rx="2"/><path d="M6 11V5h12v6M7 15h4"/>',
    "up": '<path d="M6 15l6-6 6 6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "left": '<path d="M15 6l-6 6 6 6"/>',
    "right": '<path d="M9 6l6 6-6 6"/>',
    "recognize": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/>',
    "save": '<path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
            '<path d="M7 3v5h8V3M7 21v-7h10v7"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
    "columns": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
    "rows": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 12h18"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3'
            'M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "pencil": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/>',
    "cursor": '<path d="M5 3l14 8-6 2-2 6z"/>',
    "hand": '<path d="M8 13V5a1.5 1.5 0 0 1 3 0v6M11 10V4a1.5 1.5 0 0 1 3 0v6M14 10V5.5'
            'a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-1a6 6 0 0 1-5-3l-2-4a1.5 1.5 0 0 1 2.6'
            '-1.5L8 15"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "reorder": '<path d="M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4"/>',
    "grid": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M10 4v16"/>',
    "zoom_in": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M11 8v6M8 11h6"/>',
    "zoom_out": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M8 11h6"/>',
    "fit_width": '<path d="M3 12h18M6 9l-3 3 3 3M18 9l3 3-3 3"/>',
    "fit_height": '<path d="M12 3v18M9 6l3-3 3 3M9 18l3 3 3-3"/>',
    "fit_page": '<rect x="6" y="3" width="12" height="18" rx="1"/>',
    "rotate_left": '<path d="M4 4v6h6"/><path d="M4.5 10A8 8 0 1 1 6 17"/>',
    "rotate_right": '<path d="M20 4v6h-6"/><path d="M19.5 10A8 8 0 1 0 18 17"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "link": '<path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1"/>'
            '<path d="M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="5" cy="6" r="1"/>'
            '<circle cx="5" cy="12" r="1"/><circle cx="5" cy="18" r="1"/>',
    "align_left": '<path d="M4 6h16M4 10h10M4 14h16M4 18h10"/>',
    "align_center": '<path d="M4 6h16M7 10h10M4 14h16M7 18h10"/>',
    "align_right": '<path d="M4 6h16M10 10h10M4 14h16M10 18h10"/>',
    "align_justify": '<path d="M4 6h16M4 10h16M4 14h16M4 18h16"/>',
    "redact": '<rect x="4" y="9" width="16" height="6" rx="1" fill="currentColor"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
    "phone": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>',
    "compare": '<rect x="3" y="5" width="7" height="14" rx="1"/>'
               '<rect x="14" y="5" width="7" height="14" rx="1"/><path d="M10 12h4"/>',
    "image": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/>'
             '<path d="M21 16l-5-5-8 8"/>',
    "table": '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 10h18M3 14.5h18'
             'M9 5v14M15 5v14"/>',
    "text": '<path d="M5 6h14M12 6v13M9 19h6"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" '
           'cy="12" r="3"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 0 1 4.8 1c0 1.7-2.3'
            ' 2-2.3 3.5M12 17h.01"/>',
    "warning": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    "send": '<path d="M4 12l16-8-6 16-2-6z"/>',
    "print": '<path d="M7 9V3h10v6"/><rect x="4" y="9" width="16" height="8" rx="2"/>'
             '<path d="M7 14h10v7H7z"/>',
}

_LETTERS = {"bold": ("B", "bold", "normal"), "italic": ("I", "normal", "italic"),
            "underline": ("U", "normal", "normal"), "superscript": ("x²", "normal", "normal"),
            "subscript": ("x₂", "normal", "normal"), "symbol": ("Ω", "normal", "normal")}
"""Iconitele de formatare sunt litere (B, I, U), desenate tot de noi."""


def _svg(name: str, color: str) -> bytes:
    if name in _LETTERS:
        text, weight, style = _LETTERS[name]
        deco = ' text-decoration="underline"' if name == "underline" else ""
        body = (f'<text x="12" y="17.5" text-anchor="middle" font-family="Georgia, serif" '
                f'font-size="16" font-weight="{weight}" font-style="{style}"{deco} '
                f'fill="{color}" stroke="none">{text}</text>')
    else:
        body = _PATHS[name].replace("currentColor", color)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</svg>').encode()


def names() -> list[str]:
    return sorted([*_PATHS, *_LETTERS])


@cache
def icon(name: str, color: str = INK, size: int = 24) -> QIcon:
    """Iconita `name` in culoarea data; gri deschis cand comanda e dezactivata."""
    result = QIcon()
    for mode, tint in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, "#b3bac6")):
        for scale in (1, 2):
            pixmap = QPixmap(size * scale, size * scale)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            QSvgRenderer(QByteArray(_svg(name, tint))).render(
                painter, QRectF(0, 0, size * scale, size * scale))
            painter.end()
            pixmap.setDevicePixelRatio(scale)
            result.addPixmap(pixmap, mode)
    return result


@cache
def swatch(color: str, size: int = 12) -> QIcon:
    """Patratelul culorii unui tip de zona (uneltele de zona, ca in prototip)."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(2, 2, size * 2 - 4, size * 2 - 4), 4, 4)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
