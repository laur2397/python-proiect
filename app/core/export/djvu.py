"""Exportul DjVu (faza 6, pasul 6.7): Q-022, X-127.

Scris de noi (faza_6_pasi.md, decizia 3): fiecare pagina e un `FORM:DJVU` cu
`INFO`, imaginea ca `BGjp` (JPEG, decodata de orice cititor DjVu) si, pentru
`Text under the page image` (X-127), stratul de text ascuns `TXTa`: textul
UTF-8 si zonele pagina → paragraf → rand → cuvant, codificate ca in DjVuLibre
(coordonate relative, originea jos-stanga, pozitii in octeti UTF-8).

[DECIZIE AUTONOMA] Imaginea e JPEG (`BGjp`), nu IW44/JB2: fisierele sunt valide,
dar mai mari. **INCOMPLET, marcat:** documentul DjVu cu mai multe pagini cere
directorul `DIRM` comprimat BZZ; pana atunci fiecare pagina se scrie intr-un
fisier `<nume>_001.djvu`. `Multiple layers` (X-127) nu schimba nimic.
"""

from __future__ import annotations

import io
import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from app.core.export.base import BaseExporter, ExportOptions, report, word_text
from app.core.export.pdf import JPEG_QUALITY
from app.core.model import (
    CancelToken,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    PageData,
    ProgressCallback,
)

PAGE, PARAGRAPH, LINE, WORD = 1, 4, 5, 6


def _chunk(name: bytes, data: bytes) -> bytes:
    pad = b"\x00" if len(data) % 2 else b""
    return name + struct.pack(">I", len(data)) + data + pad


@dataclass(slots=True)
class Zone:
    kind: int
    xmin: int
    ymin: int
    xmax: int
    ymax: int
    start: int = 0
    length: int = 0
    children: list[Zone] = field(default_factory=list)

    def encode(self, parent: Zone | None = None, prev: Zone | None = None) -> bytes:
        """Ca `DjVuTXT::Zone::encode` din DjVuLibre."""
        x, y = self.xmin, self.ymin
        width, height = self.xmax - self.xmin, self.ymax - self.ymin
        start = self.start
        if prev is not None:
            if self.kind in (PAGE, PARAGRAPH, LINE):
                x -= prev.xmin
                y = prev.ymin - (y + height)
            else:
                x -= prev.xmax
                y -= prev.ymin
            start -= prev.start + prev.length
        elif parent is not None:
            x -= parent.xmin
            y = parent.ymax - (y + height)
            start -= parent.start
        out = bytes([self.kind])
        for v in (x, y, width, height, start):
            out += struct.pack(">H", (v + 0x8000) & 0xFFFF)
        out += self.length.to_bytes(3, "big") + len(self.children).to_bytes(3, "big")
        last = None
        for child in self.children:
            out += child.encode(self, last)
            last = child
        return out


def _fit(zone: Zone) -> None:
    zone.xmin = min(c.xmin for c in zone.children)
    zone.ymin = min(c.ymin for c in zone.children)
    zone.xmax = max(c.xmax for c in zone.children)
    zone.ymax = max(c.ymax for c in zone.children)


def text_chunk(page: PageData) -> bytes | None:
    """TXTa: textul paginii si zonele lui."""
    from app.core.model import _area_blocks

    height = page.height_px
    text = bytearray()
    root = Zone(PAGE, 0, 0, page.width_px, height)
    for area in page._ordered_areas():
        for block in _area_blocks(area):
            para = Zone(PARAGRAPH, 0, 0, 0, 0, start=len(text))
            for line in block.lines:
                words = [w for w in line.words if not w.is_redacted]
                if not words:
                    continue
                line_zone = Zone(LINE, 0, 0, 0, 0, start=len(text))
                for i, word in enumerate(words):
                    if i:
                        text += b" "
                    data = word_text(word).encode("utf-8")
                    b = word.bbox
                    line_zone.children.append(Zone(WORD, b.x, height - b.bottom, b.right,
                                                   height - b.y, start=len(text),
                                                   length=len(data)))
                    text += data
                text += b"\n"
                line_zone.length = len(text) - line_zone.start
                _fit(line_zone)
                para.children.append(line_zone)
            if para.children:
                para.length = len(text) - para.start
                _fit(para)
                root.children.append(para)
    if not root.children:
        return None
    root.length = len(text)
    return len(text).to_bytes(3, "big") + bytes(text) + b"\x01" + root.encode()


def page_djvu(page: PageData, *, quality: int, with_text: bool) -> bytes:
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        img.load()
    img = img.convert("L" if img.mode in ("1", "L", "LA", "I", "I;16") else "RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality)
    info = struct.pack(">HHBB", img.width, img.height, 26, 0) + struct.pack(
        "<H", page.dpi_x) + bytes([22, 1])
    body = b"DJVU" + _chunk(b"INFO", info) + _chunk(b"BGjp", out.getvalue())
    text = text_chunk(page) if with_text else None
    if text is not None:
        body += _chunk(b"TXTa", text)
    return b"AT&T" + b"FORM" + struct.pack(">I", len(body)) + body


# SPEC_05 Exporter. Q-022
class DjvuExporter(BaseExporter):
    format = ExportFormat.DJVU

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EXACT)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        fmt = dict(options.format_options)
        with_text = fmt.get("save_mode", "text_under") != "image_only" and options.searchable
        quality = JPEG_QUALITY[ImageQuality(fmt.get("image_quality", options.image_quality))]
        target = Path(target)
        written = []
        for done, page in enumerate(pages):
            out = target if len(pages) == 1 else target.with_name(
                f"{target.stem}_{page.page_number:03d}{target.suffix}")
            out.write_bytes(page_djvu(page, quality=quality, with_text=with_text))
            written.append(out)
            report(progress, done + 1, len(pages), "stage.exporting")
        return written
