"""Exportul Excel (faza 6, pasul 6.5): Q-015, X-120.

Cu openpyxl (MIT). Tabelele recunoscute se scriu pe celule, cu celulele unite;
textul din afara tabelelor se scrie pe randuri (fara `Ignore text outside
tables`); imaginile (`Keep pictures`); antetele si subsolurile in antetul
foii; o foaie pentru fiecare pagina (`Create separate sheet for each page`).

`Convert numeric values to numbers`: „1250”, „1.250,50”, „-3,5” si „12%” devin
numere (formatul romanesc: punct pentru mii, virgula pentru zecimale).
Un document fara tabele produce avertismentul din Q-015 (ExportService).
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment, Font

from app.core.export.base import BaseExporter, ExportOptions, block_text, report
from app.core.export.docmodel import _picture
from app.core.model import (
    AreaType,
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_NUMBER = re.compile(r"^([+-]?)(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,(\d+))?(%?)$")
_DOT_DECIMAL = re.compile(r"^([+-]?)(\d+)\.(\d+)(%?)$")


def to_number(text: str) -> float | int | None:
    """X-120: numarul dintr-un text de celula, sau None."""
    value = text.strip().replace(" ", " ")
    match = _NUMBER.match(value) or _DOT_DECIMAL.match(value)
    if not match:
        return None
    sign, whole, fraction, percent = match.groups()
    whole = re.sub(r"[.\s]", "", whole) if match.re is _NUMBER else whole
    number: float | int = float(f"{whole}.{fraction}") if fraction else int(whole)
    if sign == "-":
        number = -number
    return number / 100 if percent else number


def _cell_value(text: str, numbers: bool) -> Any:
    number = to_number(text) if numbers else None
    return text if number is None else number


def write_xlsx(pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None) -> None:
    fmt = dict(options.format_options)
    formatted = LayoutMode(options.layout_mode) is LayoutMode.FORMATTED
    numbers = bool(fmt.get("numbers_as_numbers", True))
    outside = not fmt.get("ignore_text_outside_tables", False)
    per_page = bool(fmt.get("sheet_per_page", False))
    keep_pictures = options.keep_pictures and formatted
    wb = Workbook()
    ws = wb.active
    ws.title = "Pagina 1" if per_page else "Document"
    row = 1
    for index, page in enumerate(pages):
        if per_page and index:
            ws = wb.create_sheet(f"Pagina {index + 1}")
            row = 1
        headers = []
        for area in page._ordered_areas():
            if area.area_type is AreaType.TABLE and area.table is not None:
                for cell in area.table.cells:
                    text = "\n".join(block_text(b, options.keep_line_breaks)
                                     for b in cell.blocks)
                    target_cell = ws.cell(row + cell.row, 1 + cell.col,
                                          _cell_value(text, numbers))
                    target_cell.alignment = Alignment(wrap_text=True, vertical="top")
                    if cell.is_header and formatted:
                        target_cell.font = Font(bold=True)
                    if cell.row_span > 1 or cell.col_span > 1:
                        ws.merge_cells(start_row=row + cell.row, start_column=1 + cell.col,
                                       end_row=row + cell.row + cell.row_span - 1,
                                       end_column=cell.col + cell.col_span)
                row += area.table.rows + 1
            elif area.area_type in (AreaType.PICTURE, AreaType.BARCODE):
                if keep_pictures:
                    picture = _picture(page, area)
                    ws.add_image(XlImage(io.BytesIO(picture.data)), f"A{row}")
                    row += max(1, round(picture.height / 15)) + 1
            elif outside:
                for block in area.blocks:
                    if block.block_type in ("header", "footer"):
                        headers.append(block_text(block, False))
                        continue
                    text = block_text(block, options.keep_line_breaks)
                    if not text:
                        continue
                    cell = ws.cell(row, 1, _cell_value(text, numbers))
                    if formatted and block.block_type == "heading":
                        cell.font = Font(bold=True)
                    row += 1
        if options.keep_headers_footers and headers:
            ws.oddHeader.center.text = " ".join(headers)
        report(progress, index + 1, len(pages), "stage.exporting")
    wb.save(str(target))


# SPEC_05 Exporter. Q-015
class XlsxExporter(BaseExporter):
    format = ExportFormat.XLSX

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.FORMATTED)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        write_xlsx(pages, target, options, progress=progress)
        return [target]
