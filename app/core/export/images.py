"""Imaginile paginilor (faza 6, pasul 6.7): Q-030, Q-031, Q-032.

`Save As > Page Images...` (Q-030): TIFF, JPEG, PNG. Un singur fisier pentru
toate paginile numai in TIFF, cu `Create a single file for all pages` (Q-031);
altfel cate un fisier pe pagina, `<nume>_001.<ext>`. Compresia TIFF (Q-032):
ZIP, JPEG, CCITT Group 4 (alb-negru), Packbits, LZW. Rezolutia ceruta.

INCOMPLET, marcat: JBIG2 (nu exista un codor liber in stiva); se refuza cu un
mesaj.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

from app.core.model import ExportFormat, PageData

TIFF_COMPRESSION = {"zip": "tiff_adobe_deflate", "jpeg": "jpeg", "group4": "group4",
                    "packbits": "packbits", "lzw": "tiff_lzw", None: "tiff_adobe_deflate"}
"""Q-032: compresiile TIFF (implicit ZIP, fara pierderi)."""
_SUFFIX = {ExportFormat.TIFF: ".tif", ExportFormat.JPEG: ".jpg", ExportFormat.PNG: ".png"}


def _load(page: PageData, dpi: int, fmt: ExportFormat, compression: str | None) -> Image.Image:
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        img.load()
    if dpi and dpi != page.dpi_x:
        scale = dpi / page.dpi_x
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    if fmt is ExportFormat.TIFF and compression == "group4" and img.mode != "1":
        img = img.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("1")
    if (fmt is ExportFormat.JPEG or compression == "jpeg") and img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    return img


# SPEC_05 ExportService.export_page_images. Q-030..Q-032
def export_page_images(pages: Sequence[PageData], target: Path, fmt: ExportFormat, *,
                       dpi: int = 300, multipage: bool = False,
                       compression: str | None = None) -> list[Path]:
    fmt = ExportFormat(fmt)
    if fmt is ExportFormat.JBIG2:
        raise ValueError("JBIG2 nu e inca disponibil (fara codor liber); alegeti TIFF G4")
    if fmt not in _SUFFIX:
        raise ValueError(f"{fmt.value} nu e un format de imagine de pagina")
    if multipage and fmt is not ExportFormat.TIFF:
        raise ValueError("un singur fisier pentru toate paginile cere TIFF (Q-031)")
    if compression not in TIFF_COMPRESSION:
        raise ValueError(f"compresie TIFF necunoscuta: {compression!r}")
    target = Path(target)
    images = [_load(p, dpi, fmt, compression) for p in pages]
    options: dict[str, object] = {"dpi": (dpi, dpi)}
    if fmt is ExportFormat.TIFF:
        options["compression"] = TIFF_COMPRESSION[compression]
    if fmt is ExportFormat.JPEG:
        options["quality"] = 90
    if multipage:
        images[0].save(target, save_all=True, append_images=images[1:], **options)
        return [target]
    if len(images) == 1:
        images[0].save(target, **options)
        return [target]
    written = []
    for page, img in zip(pages, images, strict=True):
        out = target.with_name(f"{target.stem}_{page.page_number:03d}{_SUFFIX[fmt]}")
        img.save(out, **options)
        written.append(out)
    return written
