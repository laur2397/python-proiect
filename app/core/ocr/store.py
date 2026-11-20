"""Salvarea si incarcarea textului recunoscut (text_block, text_line, word).

Pasul 4a. O pagina fara zone se recunoaste intreaga; pentru ea se creeaza o
zona de text pe toata pagina, ca textul sa aiba unde sta (SPEC_04: textul
apartine unei zone).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.model import BlockData, LineData, Rect, WordData

if TYPE_CHECKING:  # pragma: no cover
    from app.core.ocr.engine import RecognitionResult
    from app.core.project import OcrProject


# N-003, N-005, N-024: rezultatul se scrie pe pagina
def save_result(project: OcrProject, page_number: int, result: RecognitionResult) -> None:
    """Inlocuieste textul zonelor recunoscute si marcheaza pagina `recognized`.

    INCOMPLET, marcat: istoricul de undo nu pastreaza inca textul (pasul 4c);
    anularea recunoasterii revine la pagina fara text, dar refacerea ei nu
    readuce textul."""
    page = project.page(page_number)
    con = project._con
    with project._history("recognize", {"page": page_number}), con:
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
            for bi, block in enumerate(blocks):
                b = block.bbox
                bcur = con.execute(
                    "INSERT INTO text_block (area_id, order_index, block_type, bbox_x, bbox_y,"
                    " bbox_w, bbox_h) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (area_id, bi, block.block_type, b.x, b.y, b.w, b.h))
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
        con.execute(
            "UPDATE page SET status = 'recognized', avg_confidence = ?, uncertain_count = ?,"
            " recognized_at = ?, recognition_ms = ? WHERE id = ?",
            (result.avg_confidence, result.uncertain_count,
             datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), result.duration_ms, page.id))
    project._after_change()


def load_text(con: Any) -> dict[int, list[BlockData]]:
    """Textul tuturor zonelor din proiect, dupa id-ul zonei, in ordine."""
    blocks: dict[int, BlockData] = {}
    by_area: dict[int, list[BlockData]] = {}
    for bid, area_id, btype, x, y, w, h in con.execute(
        "SELECT id, area_id, block_type, bbox_x, bbox_y, bbox_w, bbox_h FROM text_block"
        " ORDER BY area_id, order_index"
    ):
        blocks[bid] = BlockData(bid, btype, bbox=Rect(x, y, w, h))
        by_area.setdefault(area_id, []).append(blocks[bid])
    lines: dict[int, LineData] = {}
    for lid, block_id, base, x, y, w, h, hyphen in con.execute(
        "SELECT id, block_id, baseline_y, bbox_x, bbox_y, bbox_w, bbox_h, ends_with_hyphen"
        " FROM text_line ORDER BY block_id, order_index"
    ):
        lines[lid] = LineData(lid, bbox=Rect(x, y, w, h), baseline_y=base,
                              ends_with_hyphen=bool(hyphen))
        blocks[block_id].lines.append(lines[lid])
    for (wid, line_id, text, conf, unc, verified, edited, redacted, original, lang,
         x, y, w, h) in con.execute(
        "SELECT id, line_id, text, confidence, is_uncertain, is_verified, is_edited,"
        " is_redacted, original_text, language_code, bbox_x, bbox_y, bbox_w, bbox_h"
        " FROM word ORDER BY line_id, order_index"
    ):
        lines[line_id].words.append(WordData(
            wid, text, conf, bbox=Rect(x, y, w, h), is_uncertain=bool(unc),
            is_verified=bool(verified), is_edited=bool(edited), is_redacted=bool(redacted),
            original_text=original, language_code=lang))
    return by_area
