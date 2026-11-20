"""Teste pentru app/core/images/loader.py (faza 1, pasul 1a).

Toate imaginile se genereaza in test; niciun fisier mare in git.
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path

import pytest
from PIL import Image

from app.core.errors import (
    FileCorruptError,
    OperationCancelledError,
    UnsupportedFormatError,
)
from app.core.images.loader import (
    DEFAULT_DPI,
    MAX_PIXELS,
    PLANNED_EXTENSIONS,
    ImageLoader,
    LoadedImage,
)
from app.core.model import ColorMode, Progress

SPEC_09 = Path(__file__).resolve().parent.parent / "docs" / "spec" / "SPEC_09_anexe_referinta.md"


@pytest.fixture
def loader():
    return ImageLoader()


def _gray(size=(400, 300), value=200):
    return Image.new("L", size, value)


def _color(size=(400, 300)):
    img = Image.new("RGB", size, (255, 255, 255))
    img.paste((200, 30, 30), (0, 0, size[0] // 2, size[1] // 2))
    return img


def _save(img, path, **kw):
    img.save(path, **kw)
    return path


def _dcx(path, pages):
    """Pillow citeste DCX dar nu il scrie: il construim din pagini PCX."""
    blobs = []
    for img in pages:
        buf = io.BytesIO()
        img.save(buf, format="PCX")
        blobs.append(buf.getvalue())
    header_len = 4 + 4 * (len(blobs) + 1)
    offsets, pos = [], header_len
    for b in blobs:
        offsets.append(pos)
        pos += len(b)
    data = struct.pack("<I", 987654321) + b"".join(struct.pack("<I", o) for o in offsets)
    path.write_bytes(data + struct.pack("<I", 0) + b"".join(blobs))
    return path


# =============================================================================
# Formatele: SPEC_09 B.1, coloana „Intrare OCR Editor” (Y-100, Y-101)
# =============================================================================


def _ocr_editor_extensions_from_spec() -> set[str]:
    text = SPEC_09.read_text(encoding="utf-8")
    table = text[text.index("### B.1 Tabelul"):text.index("ANEXA G")]
    exts: set[str] = set()
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[2] == "da":
            exts |= set(re.findall(r"`(\.[a-z0-9]+)`", cells[1]))
    return exts


def test_T_Y100_1_formats_match_spec09_ocr_editor_column(loader):
    """T-Y100.1: exact formatele din SPEC_09 B.1 pentru OCR Editor, nici unul in plus."""
    spec = _ocr_editor_extensions_from_spec()
    assert ".jpg" in spec and ".dcx" in spec  # tabelul s-a citit
    assert loader.SUPPORTED_EXTENSIONS | PLANNED_EXTENSIONS == spec
    assert not (loader.SUPPORTED_EXTENSIONS & PLANNED_EXTENSIONS)


@pytest.mark.parametrize("ext", [".svg", ".docx", ".csv", ".epub", ".txt", ".webp", ""])
def test_T_Y101_1_formats_outside_ocr_editor_are_refused(loader, tmp_path, ext):
    """T-Y101.1: SVG si formatele editabile nu intra in OCR Editor (Y-104, Y-101)."""
    path = tmp_path / f"fisier{ext}"
    path.write_bytes(b"ceva")
    assert loader.can_load(path) is False
    with pytest.raises(UnsupportedFormatError) as info:
        loader.load(path)
    assert info.value.params["reason"] == "unsupported"


@pytest.mark.parametrize("ext", sorted(PLANNED_EXTENSIONS))
def test_planned_formats_say_not_implemented(loader, tmp_path, ext):
    path = tmp_path / f"doc{ext}"
    path.write_bytes(b"%PDF-1.7")
    assert loader.can_load(path) is False
    with pytest.raises(UnsupportedFormatError) as info:
        loader.load(path)
    assert info.value.params["reason"] == "not_implemented"


@pytest.mark.parametrize(
    ("name", "fmt", "kw"),
    [
        ("a.jpg", "JPEG", {}),
        ("a.jpeg", "JPEG", {}),
        ("a.jp2", "JPEG2000", {}),
        ("a.j2k", "JPEG2000", {"no_jp2": True}),
        ("a.jpc", "JPEG2000", {"no_jp2": True}),
        ("a.jpf", "JPEG2000", {}),
        ("a.jpx", "JPEG2000", {}),
        ("a.png", "PNG", {}),
        ("a.tif", "TIFF", {}),
        ("a.tiff", "TIFF", {}),
        ("a.bmp", "BMP", {}),
        ("a.dib", "BMP", {}),
        ("a.rle", "BMP", {}),
        ("a.gif", "GIF", {}),
        ("a.pcx", "PCX", {}),
    ],
)
def test_T_K001_1_each_raster_format_loads(loader, tmp_path, name, fmt, kw):
    """T-K001.1: fiecare format raster din B.1 se incarca, cu dimensiunile corecte."""
    path = _save(_color((120, 80)), tmp_path / name, format=fmt, **kw)
    assert loader.can_load(path)
    (img,) = loader.load(path)
    assert isinstance(img, LoadedImage)
    assert (img.width_px, img.height_px) == (120, 80)
    assert img.path == path and img.source_page == 1


def test_dcx_multipage(loader, tmp_path):
    path = _dcx(tmp_path / "fax.dcx", [_gray((50, 40)), _gray((60, 30))])
    assert loader.read_page_count(path) == 2
    sizes = [(i.width_px, i.height_px) for i in loader.load(path)]
    assert sizes == [(50, 40), (60, 30)]


def test_extension_is_case_insensitive(loader, tmp_path):
    path = _save(_gray(), tmp_path / "SCAN.PNG")
    assert loader.can_load(path)
    assert len(loader.load(path)) == 1


# =============================================================================
# Multipagina si intervale (J-050)
# =============================================================================


@pytest.fixture
def tiff3(tmp_path):
    frames = [_gray((100, 50)), _color((100, 50)), Image.new("1", (100, 50), 1)]
    path = tmp_path / "dosar.tif"
    frames[0].save(path, save_all=True, append_images=frames[1:], dpi=(200, 200))
    return path


def test_T_J050_1_multipage_one_image_per_page(loader, tiff3):
    """T-J050.1: un fisier multipagina da o imagine per pagina."""
    pages = loader.load(tiff3)
    assert [p.source_page for p in pages] == [1, 2, 3]
    assert [p.color_mode for p in pages] == [ColorMode.GRAY, ColorMode.COLOR, ColorMode.BW]
    assert loader.read_page_count(tiff3) == 3


def test_T_J050_2_page_range(loader, tiff3):
    """T-J050.2: interval de pagini pentru fisiere multipagina."""
    assert [p.source_page for p in loader.load(tiff3, pages=[3, 1])] == [3, 1]


@pytest.mark.parametrize("pages", [[0], [4], [1, 5], [-1]])
def test_page_range_outside_file(loader, tiff3, pages):
    with pytest.raises(ValueError):
        loader.load(tiff3, pages=pages)


def test_progress_and_cancel(loader, tiff3):
    seen: list[Progress] = []
    loader.load(tiff3, progress=seen.append)
    assert [(p.current, p.total) for p in seen] == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert seen[0].stage == "stage.loading_images" and seen[0].detail == "dosar.tif"

    calls = iter([False, True])
    with pytest.raises(OperationCancelledError) as info:
        loader.load(tiff3, cancel=lambda: next(calls))
    assert info.value.params["done"] == 1


# =============================================================================
# Metadate: dpi, culoare, fotografie (N-100, N-104, L-018)
# =============================================================================


def test_declared_dpi_is_read(loader, tmp_path):
    (img,) = loader.load(_save(_gray(), tmp_path / "a.png", dpi=(300, 300)))
    assert (img.dpi_x, img.dpi_y) == (300, 300)
    (img,) = loader.load(_save(_gray(), tmp_path / "b.tif", dpi=(400, 200)))
    assert (img.dpi_x, img.dpi_y) == (400, 200)


def test_missing_dpi_defaults_to_300(loader, tmp_path):
    (img,) = loader.load(_save(_gray(), tmp_path / "a.png"))
    assert (img.dpi_x, img.dpi_y) == (DEFAULT_DPI, DEFAULT_DPI) == (300, 300)


def test_jfif_aspect_ratio_is_not_a_resolution(loader, tmp_path):
    (img,) = loader.load(_save(_gray(), tmp_path / "a.jpg", dpi=(1, 1)))
    assert img.dpi_x == DEFAULT_DPI


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (lambda: Image.new("1", (40, 40), 1), ColorMode.BW),
        (lambda: Image.new("L", (40, 40), 90), ColorMode.GRAY),
        (lambda: Image.new("RGB", (40, 40), (90, 92, 89)), ColorMode.GRAY),  # gri salvat ca RGB
        (lambda: Image.new("L", (40, 40), 90).convert("P"), ColorMode.GRAY),  # paleta de gri
        (lambda: _color((40, 40)), ColorMode.COLOR),
        (lambda: _color((40, 40)).convert("P"), ColorMode.COLOR),
        (lambda: Image.new("CMYK", (40, 40), (0, 80, 80, 0)), ColorMode.COLOR),
    ],
)
def test_T_N104_1_color_mode(loader, tmp_path, make, expected):
    """T-N104.1: modul de culoare, inclusiv scanari gri salvate ca RGB sau paleta."""
    img = make()
    path = tmp_path / ("a.tif" if img.mode in ("CMYK", "1") else "a.png")
    (loaded,) = loader.load(_save(img, path))
    assert loaded.color_mode is expected


def _jpeg_with_exif(path, *, make=None, orientation=None, size=(300, 200)):
    img = _color(size)
    exif = Image.Exif()
    if make:
        exif[0x010F] = make
    if orientation:
        exif[0x0112] = orientation
    img.save(path, format="JPEG", exif=exif.tobytes(), dpi=(72, 72))
    return path


def test_T_L018_1_camera_photo_is_detected(loader, tmp_path):
    """T-L018.1: fotografie de pe telefon (EXIF cu producator) -> is_photo."""
    (img,) = loader.load(_jpeg_with_exif(tmp_path / "telefon.jpg", make="Telefon"))
    assert img.is_photo is True
    (scan,) = loader.load(_save(_gray(), tmp_path / "scan.png", dpi=(300, 300)))
    assert scan.is_photo is False


def test_jpeg_without_dpi_counts_as_photo(loader, tmp_path):
    (img,) = loader.load(_save(_color(), tmp_path / "a.jpg"))
    assert img.is_photo is True


def test_exif_rotation_swaps_reported_size(loader, tmp_path):
    (img,) = loader.load(_jpeg_with_exif(tmp_path / "r.jpg", orientation=6, size=(300, 200)))
    assert (img.width_px, img.height_px) == (200, 300)


# =============================================================================
# Fisiere stricate (A-010 / J-050: mesaj, nu cadere)
# =============================================================================


def test_garbage_is_corrupt(loader, tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x00nu e imagine" * 50)
    with pytest.raises(FileCorruptError):
        loader.load(path)


def test_truncated_image_is_caught_at_load(loader, tmp_path):
    path = _save(_color((800, 600)), tmp_path / "a.png")
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    with pytest.raises(FileCorruptError):
        loader.load(path)


def test_wrong_content_for_extension(loader, tmp_path):
    jpeg_as_png = _save(_color(), tmp_path / "foto.png", format="JPEG")
    assert len(loader.load(jpeg_as_png)) == 1  # tot o imagine acceptata
    ppm_as_png = _save(_color(), tmp_path / "x.png", format="PPM")
    with pytest.raises(UnsupportedFormatError) as info:
        loader.load(ppm_as_png)
    assert info.value.params["detected"] == "PPM"


def test_missing_file(loader, tmp_path):
    with pytest.raises(FileNotFoundError):
        loader.load(tmp_path / "lipsa.png")


def test_large_pages_are_allowed(loader):
    """SPEC_06 are o pagina A0 la 600 dpi (~560 milioane de pixeli)."""
    assert MAX_PIXELS >= 19866 * 28087
    assert Image.MAX_IMAGE_PIXELS >= MAX_PIXELS


# =============================================================================
# Miniaturi si pixeli
# =============================================================================


def test_thumbnail_is_png_within_size(loader, tiff3):
    data = loader.render_thumbnail(tiff3, 2, 40)
    assert data.startswith(b"\x89PNG")
    thumb = Image.open(io.BytesIO(data))
    assert max(thumb.size) <= 40 and thumb.size == (40, 20)


def test_thumbnail_of_cmyk_and_rotated_photo(loader, tmp_path):
    cmyk = _save(Image.new("CMYK", (100, 100), (0, 50, 50, 0)), tmp_path / "c.tif")
    assert Image.open(io.BytesIO(loader.render_thumbnail(cmyk, 1, 32))).mode in ("RGB", "RGBA")
    rot = _jpeg_with_exif(tmp_path / "r.jpg", orientation=6, size=(300, 200))
    thumb = Image.open(io.BytesIO(loader.render_thumbnail(rot, 1, 30)))
    assert thumb.size == (20, 30)  # in picioare, cum a fost facuta poza


def test_thumbnail_bad_arguments(loader, tiff3):
    with pytest.raises(ValueError):
        loader.render_thumbnail(tiff3, 9, 40)
    with pytest.raises(ValueError):
        loader.render_thumbnail(tiff3, 1, 0)


def test_open_pixels_returns_the_right_page_detached_from_file(loader, tiff3):
    second = loader.load(tiff3, pages=[2])[0]
    pixels = loader.open_pixels(second)
    assert pixels.size == (100, 50) and pixels.mode == "RGB"
    tiff3.unlink()  # imaginea nu mai depinde de fisier
    assert pixels.getpixel((0, 0)) == (200, 30, 30)
