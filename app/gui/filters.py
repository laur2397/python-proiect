"""Filtrele dialogurilor de deschidere, din tabelul formatelor (Y-100, Y-101):
fiecare modul ofera numai formatele pe care le accepta si pe care DocuLens le
citeste (`app.core.formats`)."""

from __future__ import annotations

from app.core.formats import extensions_for, pattern
from app.gui.i18n import tr


def open_filter(module: str) -> str:
    """`Toate formatele suportate (*.pdf *.png …);;Toate fisierele (*)`."""
    return f"{tr('filter.supported')} ({pattern(extensions_for(module))});;" \
           f"{tr('filter.all')} (*)"


def conversion_filter() -> str:
    """Conversia si OCR-ul din Lansator: formatele OCR Editor-ului (proiectul OCR)."""
    return open_filter("ocr_editor")
