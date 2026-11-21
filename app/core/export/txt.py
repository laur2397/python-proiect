"""Exportul TXT (faza 6, pasul 6.1): Q-018, X-123.

Modurile `formatted` si `plain` (Q-004, Q-005). Optiunile din X-123:
`Keep line breaks`, caracterul #12 intre pagini, linie goala intre
paragrafe, antetele si subsolurile, codificarea.

In `formatted`, randurile unui tabel se scriu cu celulele separate prin tab,
iar elementele de lista cu indentarea nivelului; in `plain`, fiecare bloc e un
paragraf.

Diacriticele (CLAUDE.md §6.4): codificarile pe 8 biti (windows-1250,
iso-8859-2) nu au ș si ț cu virgula; se scriu cu sedila (ş, ţ), nu ca `?`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.core.export.base import (
    BaseExporter,
    ExportOptions,
    block_text,
    check_cancel,
    page_blocks,
    report,
)
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

PAGE_BREAK = "\f"
"""X-123: `Insert page break character (#12) as page break`."""
_COMMA_TO_CEDILLA = str.maketrans("șȘțȚ", "şŞţŢ")
_EIGHT_BIT = ("windows-1250", "iso-8859-2")


def encode_text(text: str, encoding: str) -> bytes:
    """Textul in codificarea ceruta; UTF-16 cu BOM; pe 8 biti, ș/ț cu sedila."""
    if encoding.lower() in _EIGHT_BIT:
        text = text.translate(_COMMA_TO_CEDILLA)
    return text.encode(encoding, errors="replace")


def document_text(pages: Sequence[PageData], options: ExportOptions, *,
                  page_break: bool = False, blank_line: bool = False,
                  progress: ProgressCallback | None = None,
                  cancel: CancelToken | None = None) -> str:
    formatted = LayoutMode(options.layout_mode) is LayoutMode.FORMATTED
    separator = "\n\n" if blank_line else "\n"
    out_pages: list[str] = []
    for done, page in enumerate(pages):
        check_cancel(cancel, done, len(pages))
        paragraphs: list[str] = []
        row_cells: list[str] = []
        row_key = None
        for item in page_blocks(page, options):
            text = block_text(item.block, options.keep_line_breaks)
            if item.cell is not None and formatted:
                key = (item.area.id, item.cell.row)
                if row_key not in (None, key):
                    paragraphs.append("\t".join(row_cells))
                    row_cells = []
                row_key = key
                row_cells.append(text.replace("\n", " "))
                continue
            if row_cells:
                paragraphs.append("\t".join(row_cells))
                row_cells, row_key = [], None
            if formatted and item.block.block_type == "list_item":
                text = "  " * max(0, (item.block.list_level or 1) - 1) + text
            paragraphs.append(text)
        if row_cells:
            paragraphs.append("\t".join(row_cells))
        out_pages.append(separator.join(p for p in paragraphs if p))
        report(progress, done + 1, len(pages), "stage.exporting")
    return (PAGE_BREAK if page_break else separator).join(out_pages)


# SPEC_05 Exporter. Q-018
class TxtExporter(BaseExporter):
    format = ExportFormat.TXT

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.PLAIN, keep_line_breaks=True)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        opts = options.format_options
        text = document_text(pages, options, page_break=bool(opts.get("page_break_char")),
                             blank_line=bool(opts.get("blank_line_paragraphs")),
                             progress=progress, cancel=cancel)
        target = Path(target)
        target.write_bytes(encode_text(text, options.encoding))
        return [target]
