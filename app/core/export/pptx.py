"""Exportul PowerPoint (faza 6, pasul 6.5): Q-017, X-121.

Cu python-pptx (MIT), numai in modul `exact` (Q-002): fiecare pagina devine un
diapozitiv de marimea ei; zonele de text sunt casete la pozitia lor, tabelele
sunt tabele PowerPoint (cu celulele unite), imaginile se pastreaza
(`Keep pictures`). `Keep line breaks` pastreaza randurile (fara ea, tot textul
unui bloc devine un rand); `Shrink text on overflow` micsoreaza textul care nu
incape; antetele si subsolurile numai cu `Keep headers and footers`.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

from app.core.export.base import BaseExporter, ExportOptions, block_text, report
from app.core.export.docmodel import _picture, _size_pt
from app.core.model import (
    AreaType,
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

EMU_PER_INCH = 914400


def _emu(px: int, dpi: int) -> Emu:
    return Emu(round(px * EMU_PER_INCH / dpi))


def write_pptx(pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None) -> None:
    fmt = dict(options.format_options)
    keep_breaks = bool(fmt.get("keep_line_breaks", options.keep_line_breaks))
    shrink = bool(fmt.get("shrink_on_overflow", True))
    keep_headers = options.keep_headers_footers or bool(fmt.get("keep_headers_footers"))
    deck = Presentation()
    first = pages[0]
    deck.slide_width = _emu(first.width_px, first.dpi_x)
    deck.slide_height = _emu(first.height_px, first.dpi_y)
    blank = deck.slide_layouts[6]
    for index, page in enumerate(pages):
        slide = deck.slides.add_slide(blank)
        for area in page._ordered_areas():
            b = area.bbox
            x, y = _emu(b.x, page.dpi_x), _emu(b.y, page.dpi_y)
            w, h = _emu(b.w, page.dpi_x), _emu(b.h, page.dpi_y)
            if area.area_type in (AreaType.PICTURE, AreaType.BARCODE):
                if options.keep_pictures:
                    slide.shapes.add_picture(io.BytesIO(_picture(page, area).data), x, y, w, h)
                continue
            if area.area_type is AreaType.TABLE and area.table is not None:
                table = slide.shapes.add_table(area.table.rows, area.table.cols, x, y, w,
                                               h).table
                for cell in area.table.cells:
                    target_cell = table.cell(cell.row, cell.col)
                    if cell.row_span > 1 or cell.col_span > 1:
                        target_cell.merge(table.cell(cell.row + cell.row_span - 1,
                                                     cell.col + cell.col_span - 1))
                    target_cell.text = "\n".join(block_text(bl, keep_breaks)
                                                 for bl in cell.blocks)
                continue
            blocks = [bl for bl in area.blocks if bl.lines and (
                keep_headers or bl.block_type not in ("header", "footer"))]
            if not blocks:
                continue
            frame = slide.shapes.add_textbox(x, y, w, h).text_frame
            frame.word_wrap = True
            if shrink:
                frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
            for i, block in enumerate(blocks):
                para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                para.text = block_text(block, keep_breaks)
                heights = sorted(wd.bbox.h for ln in block.lines for wd in ln.words)
                if heights:
                    size = Pt(_size_pt(heights[len(heights) // 2], page.dpi_y))
                    for run in para.runs:
                        run.font.size = size
        report(progress, index + 1, len(pages), "stage.exporting")
    deck.save(str(target))


# SPEC_05 Exporter. Q-017
class PptxExporter(BaseExporter):
    format = ExportFormat.PPTX

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EXACT, keep_line_breaks=True)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        write_pptx(pages, target, options, progress=progress)
        return [target]
