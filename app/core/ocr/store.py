"""Salvarea si incarcarea textului recunoscut (text_block, text_line, word).

Pasul 4.1. O pagina fara zone se recunoaste intreaga; pentru ea se creeaza o
zona de text pe toata pagina, ca textul sa aiba unde sta (SPEC_04: textul
apartine unei zone).
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.model import BlockData, LineData, Rect, WordData

if TYPE_CHECKING:  # pragma: no cover
    from app.core.ocr.engine import RecognitionResult
    from app.core.project import OcrProject


# N-003, N-005, N-024: rezultatul se scrie pe pagina
def save_result(project: OcrProject, page_number: int, result: RecognitionResult, *,
                record: bool = True) -> None:
    """Inlocuieste textul zonelor recunoscute si marcheaza pagina `recognized`.

    `record=False`: apelantul inregistreaza el pasul de undo (mai multe pagini
    intr-un singur pas, RecognitionService)."""
    page = project.page(page_number)
    con = project._con
    history = project._history("recognize", {"page": page_number}) if record else nullcontext()
    with history, con:
        area_blocks = dict(result.area_blocks)
        if None in area_blocks:  # pagina intreaga, fara zone
            whole = [[0, 0], [page.width_px, 0], [page.width_px, page.height_px],
                     [0, page.height_px]]
            cur = con.execute(
                "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
                " bbox_h, polygon) VALUES (?, 0, 'text', 0, 0, ?, ?, ?)",
                (page.id, page.width_px, page.height_px, json.dumps(whole)))
            area_blocks[int(cur.lastrowid)] = area_blocks.pop(None)
        for area_id, blocks in area_blocks.items():
            con.execute("DELETE FROM text_block WHERE area_id = ?", (area_id,))
            insert_blocks(con, area_id, blocks)
        # M-057..M-060: valoarea citita (None = ilizibil, zona ramane imagine)
        barcode_areas = [aid for aid in area_blocks
                         if any(a.id == aid and a.area_type.value == "barcode"
                                for a in page.areas)]
        values = {area.id: value for area, _, value in result.barcodes}
        for aid in barcode_areas:
            con.execute("UPDATE area SET barcode_value = ? WHERE id = ?", (values.get(aid), aid))
        # M-003: textul celulelor de tabel. SPEC_04 numeroteaza blocurile pe
        # zona (UNIQUE area_id, order_index), deci celulele unui tabel se scriu
        # impreuna, in ordinea lor (rand, coloana).
        cells: dict[int, list[tuple[int, int, int]]] = {}
        for cell_id in result.cell_blocks:
            area_id, row, col = con.execute(
                "SELECT area_id, row_index, col_index FROM table_cell WHERE id = ?",
                (cell_id,)).fetchone()
            cells.setdefault(area_id, []).append((row, col, cell_id))
        for area_id, items in cells.items():
            con.execute("DELETE FROM text_block WHERE area_id = ?", (area_id,))
            start = 0
            for _, _, cell_id in sorted(items):
                blocks = result.cell_blocks[cell_id]
                insert_blocks(con, area_id, blocks, cell_id, start=start)
                start += len(blocks)
        con.execute(
            "UPDATE page SET status = 'recognized', avg_confidence = ?, uncertain_count = ?,"
            " recognized_at = ?, recognition_ms = ? WHERE id = ?",
            (result.avg_confidence, result.uncertain_count,
             datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), result.duration_ms, page.id))
        con.execute("DELETE FROM page_warning WHERE page_id = ?"
                    " AND code IN ('LOW_RESOLUTION', 'MANY_LANGUAGES', 'GOTHIC_MIXED')", (page.id,))
        con.executemany(
            "INSERT INTO page_warning (page_id, severity, code, message) VALUES (?, ?, ?, ?)",
            [(page.id, w.severity, w.code, w.message_key) for w in result.warnings])
    project._after_change()


# N-018..N-021: marcajele de structura, dupa detectia pe tot documentul
def save_structure(project: OcrProject, pages: list[Any]) -> None:
    """Scrie `block_type`, `list_level`, `style_name` pe blocuri si
    `text_function` pe zonele de text. In pasul de undo al apelantului."""
    con = project._con
    with con:
        for page in pages:
            for area in page.areas:
                if area.area_type.value == "text":
                    con.execute("UPDATE area SET text_function = ? WHERE id = ?",
                                (None if area.text_function is None
                                 else area.text_function.value, area.id))
                for block in area.blocks:
                    if block.id is not None:
                        con.execute(
                            "UPDATE text_block SET block_type = ?, list_level = ?,"
                            " style_name = ? WHERE id = ?",
                            (block.block_type, block.list_level, block.style_name, block.id))
    project._after_change()


def insert_blocks(con: Any, area_id: int, blocks: list[BlockData],
                  cell_id: int | None = None, *, start: int = 0) -> None:
    """Scrie blocurile unei zone (sau ale unei celule de tabel) cu randurile si
    cuvintele lor. In tranzactia apelantului."""
    for bi, block in enumerate(blocks):
        b = block.bbox
        bcur = con.execute(
            "INSERT INTO text_block (area_id, table_cell_id, order_index, block_type,"
            " style_name, list_level, direction, bbox_x, bbox_y, bbox_w, bbox_h)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (area_id, cell_id, start + bi, block.block_type, block.style_name,
             block.list_level, block.direction, b.x, b.y, b.w, b.h))
        for li, line in enumerate(block.lines):
            lb = line.bbox
            lcur = con.execute(
                "INSERT INTO text_line (block_id, order_index, baseline_y, bbox_x,"
                " bbox_y, bbox_w, bbox_h, ends_with_hyphen) VALUES (?,?,?,?,?,?,?,?)",
                (bcur.lastrowid, li, line.baseline_y, lb.x, lb.y, lb.w, lb.h,
                 int(line.ends_with_hyphen)))
            con.executemany(
                "INSERT INTO word (line_id, order_index, text, confidence, is_uncertain,"
                " language_code, bbox_x, bbox_y, bbox_w, bbox_h)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(lcur.lastrowid, wi, w.text, w.confidence, int(w.is_uncertain),
                  w.language_code, w.bbox.x, w.bbox.y, w.bbox.w, w.bbox.h)
                 for wi, w in enumerate(line.words)])


def load_text(con: Any) -> dict[int, list[BlockData]]:
    """Textul zonelor (fara celulele de tabel), dupa id-ul zonei, in ordine."""
    return _load(con)[0]


def load_cell_text(con: Any) -> dict[int, list[BlockData]]:
    """Textul celulelor de tabel (M-003), dupa id-ul celulei, in ordine."""
    return _load(con)[1]


def _load(con: Any) -> tuple[dict[int, list[BlockData]], dict[int, list[BlockData]]]:
    blocks: dict[int, BlockData] = {}
    by_area: dict[int, list[BlockData]] = {}
    by_cell: dict[int, list[BlockData]] = {}
    for bid, area_id, cell_id, btype, x, y, w, h, style, level, direction in con.execute(
        "SELECT id, area_id, table_cell_id, block_type, bbox_x, bbox_y, bbox_w, bbox_h,"
        " style_name, list_level, direction FROM text_block"
        " ORDER BY area_id, table_cell_id, order_index"
    ):
        blocks[bid] = BlockData(bid, btype, bbox=Rect(x, y, w, h), style_name=style,
                                list_level=level, direction=direction)
        target = by_area if cell_id is None else by_cell
        target.setdefault(area_id if cell_id is None else cell_id, []).append(blocks[bid])
    lines: dict[int, LineData] = {}
    for lid, block_id, base, x, y, w, h, hyphen in con.execute(
        "SELECT id, block_id, baseline_y, bbox_x, bbox_y, bbox_w, bbox_h, ends_with_hyphen"
        " FROM text_line ORDER BY block_id, order_index"
    ):
        lines[lid] = LineData(lid, bbox=Rect(x, y, w, h), baseline_y=base,
                              ends_with_hyphen=bool(hyphen))
        blocks[block_id].lines.append(lines[lid])
    def flag(v: Any) -> bool | None:
        return None if v is None else bool(v)

    for (wid, line_id, text, conf, unc, verified, edited, redacted, original, lang,
         x, y, w, h, in_dict, font, size, bold, italic, under, sup, sub, color) in con.execute(
        "SELECT id, line_id, text, confidence, is_uncertain, is_verified, is_edited,"
        " is_redacted, original_text, language_code, bbox_x, bbox_y, bbox_w, bbox_h,"
        " in_dictionary, font_name, font_size, is_bold, is_italic, is_underline,"
        " is_superscript, is_subscript, text_color FROM word ORDER BY line_id, order_index"
    ):
        lines[line_id].words.append(WordData(
            wid, text, conf, bbox=Rect(x, y, w, h), is_uncertain=bool(unc),
            is_verified=bool(verified), is_edited=bool(edited), is_redacted=bool(redacted),
            original_text=original, language_code=lang, in_dictionary=bool(in_dict),
            font_name=font, font_size=size, is_bold=flag(bold), is_italic=flag(italic),
            is_underline=flag(under), is_superscript=flag(sup), is_subscript=flag(sub),
            text_color=color))
    return by_area, by_cell
