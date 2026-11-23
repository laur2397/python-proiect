"""SVG in PDF Editor (faza 16, Y-104; faza_16_pasi.md decizia 2): desenul se
converteste intr-un PDF nesalvat cu QtSvg (nucleul nu importa Qt, CLAUDE.md §4).
SVG-ul se deschide numai in PDF Editor si nu se salveaza ca SVG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QBuffer, QIODevice, QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgRenderer

from app.core.errors import UnsupportedFormatError

POINTS_PER_PX = 0.75
"""SVG are 96 px pe inch, PDF 72 de puncte."""


def svg_to_pdf_bytes(path: Path) -> bytes:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise UnsupportedFormatError("desenul SVG nu se poate citi", path=str(path))
    size = renderer.defaultSize()
    width = max(size.width(), 1) * POINTS_PER_PX
    height = max(size.height(), 1) * POINTS_PER_PX
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QPdfWriter(buffer)
    writer.setPageLayout(QPageLayout(QPageSize(QSizeF(width, height), QPageSize.Unit.Point),
                                     QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
    writer.setResolution(72)
    painter = QPainter(writer)
    renderer.render(painter)
    painter.end()
    buffer.close()
    return bytes(buffer.data())


def svg_document(path: Path) -> Any:
    """Un `PdfDocument` nesalvat cu desenul (ca `File > New`)."""
    from app.core.pdf.document import PdfDocument

    document = PdfDocument._from_bytes(svg_to_pdf_bytes(Path(path)), None)
    document.is_modified = True
    document._revision = 1
    return document
