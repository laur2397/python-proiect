"""Exportul CSV (faza 6, pasul 6.5): Q-016, X-122.

CSV e numai format de iesire si numai in modul `plain` (Q-005). Optiunile X-122:
`Ignore text outside tables` (implicit da: numai randurile tabelelor),
caracterul #12 intre pagini, delimitatorul (`,` `;` tab) si codificarea (pe 8
biti, ș/ț se scriu cu sedila, ca la TXT).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from app.core.export.base import BaseExporter, ExportOptions, block_text, report
from app.core.export.txt import encode_text
from app.core.model import (
    AreaType,
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

DELIMITERS = {",": ",", ";": ";", "tab": "\t"}


def document_rows(pages: Sequence[PageData], options: ExportOptions,
                  ) -> list[list[list[str]] | None]:
    """Randurile fiecarei pagini; None intre pagini cand se cere #12."""
    outside = not options.format_options.get("ignore_text_outside_tables", True)
    page_break = bool(options.format_options.get("page_break_char", False))
    out: list[list[list[str]] | None] = []
    for index, page in enumerate(pages):
        if index and page_break:
            out.append(None)
        rows: list[list[str]] = []
        for area in page._ordered_areas():
            if area.area_type is AreaType.TABLE and area.table is not None:
                grid = [[""] * area.table.cols for _ in range(area.table.rows)]
                for cell in area.table.cells:
                    grid[cell.row][cell.col] = " ".join(
                        block_text(b, False) for b in cell.blocks)
                rows += grid
            elif outside:
                rows += [[block_text(b, False)] for b in area.blocks
                         if b.lines and b.block_type not in ("header", "footer")]
        out.append(rows)
    return out


# SPEC_05 Exporter. Q-016
class CsvExporter(BaseExporter):
    format = ExportFormat.CSV

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.PLAIN)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        delimiter = DELIMITERS.get(str(options.format_options.get("delimiter", ";")), ";")
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n")
        for done, rows in enumerate(document_rows(pages, options)):
            if rows is None:
                buffer.write("\f\r\n")
                continue
            writer.writerows(rows)
            report(progress, done + 1, len(pages), "stage.exporting")
        target = Path(target)
        target.write_bytes(encode_text(buffer.getvalue(), options.encoding))
        return [target]
