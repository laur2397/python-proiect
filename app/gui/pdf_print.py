"""Tiparirea din PDF Editor (faza 7, pasul 7.10): I-021, I-022.

Dialogul de tiparire al sistemului alege imprimanta, numarul de copii, paginile
(toate, cele selectate sau un interval), hartia si orientarea (I-022). Tabul
propriu adauga ce nu are dialogul standard: comentariile si marcajele
(`Show Comments`), scalarea si paginile pe foaie, tiparirea manuala pe ambele
fete (`Manually print on both sides`) si alb-negru (`Black and white`).

Fara imprimanta instalata, fereastra afiseaza un mesaj (I-021). Paginile se
deseneaza din randarea PDFium la rezolutia imprimantei.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from app.gui.i18n import tr

PER_SHEET = (1, 2, 4)
"""Pagini pe foaie (I-022)."""
SCALINGS = ("fit", "actual", "shrink")
"""Scalarea: potrivire pe foaie, marimea reala, micsorare numai daca nu incape."""
MAX_DPI = 300
"""Rezolutia maxima de randare pentru tiparire."""


@dataclass
class PrintSettings:
    pages: list[int] | None = None
    """Paginile de tiparit, de la 1; None = toate."""
    annotations: bool = True
    grayscale: bool = False
    per_sheet: int = 1
    scaling: str = "fit"
    manual_duplex: bool = False


def sheets(pages: Sequence[int], per_sheet: int) -> list[list[int]]:
    """Paginile grupate pe foi."""
    if per_sheet not in PER_SHEET:
        raise ValueError(f"pagini pe foaie: {PER_SHEET}")
    return [list(pages[i:i + per_sheet]) for i in range(0, len(pages), per_sheet)]


def _cells(area: QRectF, per_sheet: int) -> list[QRectF]:
    """Celulele foii: 1 = toata foaia, 2 = una sub alta (alaturate pe o foaie
    culcata), 4 = 2 x 2."""
    if per_sheet == 1:
        return [area]
    if per_sheet == 2:
        if area.width() > area.height():
            half = area.width() / 2
            return [QRectF(area.left() + i * half, area.top(), half, area.height())
                    for i in range(2)]
        half = area.height() / 2
        return [QRectF(area.left(), area.top() + i * half, area.width(), half)
                for i in range(2)]
    w, h = area.width() / 2, area.height() / 2
    return [QRectF(area.left() + c * w, area.top() + r * h, w, h)
            for r in range(2) for c in range(2)]


def _target(cell: QRectF, image: QImage, page_pt: tuple[float, float], dpi: float,
            scaling: str) -> QRectF:
    actual_w, actual_h = page_pt[0] * dpi / 72, page_pt[1] * dpi / 72
    fit = min(cell.width() / image.width(), cell.height() / image.height())
    if scaling == "actual" or (scaling == "shrink" and actual_w <= cell.width()
                               and actual_h <= cell.height()):
        width, height = actual_w, actual_h
    else:
        width, height = image.width() * fit, image.height() * fit
    return QRectF(cell.left() + (cell.width() - width) / 2,
                  cell.top() + (cell.height() - height) / 2, width, height)


def print_document(document: Any, printer: Any, settings: PrintSettings, *,
                   flip: Callable[[], bool] | None = None) -> int:
    """Tipareste si intoarce numarul de foi. Cu `manual_duplex`, intai foile
    impare, apoi `flip()` (utilizatorul intoarce teancul) si foile pare, in
    ordine inversa."""
    pages = settings.pages or list(range(1, document.page_count + 1))
    groups = sheets(pages, settings.per_sheet)
    order: list[list[int] | None] = list(groups)
    if settings.manual_duplex and len(groups) > 1:
        order = [*groups[0::2], None, *reversed(groups[1::2])]
    dpi = min(MAX_DPI, printer.resolution())
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("imprimanta nu poate porni lucrarea")
    printed = 0
    try:
        area = QRectF(printer.pageRect(printer.Unit.DevicePixel))
        area.moveTo(0, 0)
        first = True
        for group in order:
            if group is None:  # pauza pentru intoarcerea foilor
                if flip is not None and not flip():
                    break
                continue
            if not first:
                printer.newPage()
            first = False
            for page, cell in zip(group, _cells(area, settings.per_sheet), strict=False):
                image = QImage.fromData(
                    document.render_page(page, dpi / 96, annotations=settings.annotations),
                    "PNG")
                if settings.grayscale:
                    image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                painter.drawImage(_target(cell, image, document.page_size(page), dpi,
                                          settings.scaling), image)
            printed += 1
    finally:
        painter.end()
    return printed


class PrintOptions(QWidget):
    """I-022: tabul propriu al dialogului de tiparire."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_print_options")
        self.setWindowTitle(tr("print.options"))
        self.annotations = QCheckBox(tr("print.comments"))
        self.annotations.setObjectName("print_comments")
        self.annotations.setChecked(True)
        self.grayscale = QCheckBox(tr("print.black_white"))
        self.grayscale.setObjectName("print_black_white")
        self.manual_duplex = QCheckBox(tr("print.both_sides"))
        self.manual_duplex.setObjectName("print_both_sides")
        self.per_sheet = QComboBox()
        self.per_sheet.setObjectName("print_per_sheet")
        for count in PER_SHEET:
            self.per_sheet.addItem(str(count), count)
        self.scaling = QComboBox()
        self.scaling.setObjectName("print_scaling")
        for key in SCALINGS:
            self.scaling.addItem(tr(f"print.scaling.{key}"), key)
        form = QFormLayout(self)
        form.addRow(self.annotations)
        form.addRow(tr("print.per_sheet"), self.per_sheet)
        form.addRow(tr("print.scaling"), self.scaling)
        form.addRow(self.manual_duplex)
        form.addRow(self.grayscale)

    def settings(self, pages: list[int] | None) -> PrintSettings:
        return PrintSettings(pages=pages, annotations=self.annotations.isChecked(),
                             grayscale=self.grayscale.isChecked(),
                             per_sheet=int(self.per_sheet.currentData()),
                             scaling=str(self.scaling.currentData()),
                             manual_duplex=self.manual_duplex.isChecked())


def printers_available() -> bool:
    """I-021: tiparirea cere o imprimanta instalata."""
    from PySide6.QtPrintSupport import QPrinterInfo

    return bool(QPrinterInfo.availablePrinters())
