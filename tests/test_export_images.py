"""Faza 6, pasul 6.7: DjVu si imaginile paginilor (Q-022, Q-030..Q-032, X-127)."""

from __future__ import annotations

import shutil
import struct
import subprocess

import pytest
from PIL import Image

from app.core.export.base import ExportOptions, default_service, export_page_images
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    LayoutMode,
    LineData,
    PageData,
    PageStatus,
    Rect,
    WordData,
)


@pytest.fixture
def pages(tmp_path):
    out = []
    for n in (1, 2):
        path = tmp_path / f"p{n}.png"
        Image.new("L", (1240, 1754), 230).save(path, dpi=(150, 150))
        p = PageData(n, n, path, path, 1240, 1754, 150, 150, ColorMode.GRAY,
                     status=PageStatus.RECOGNIZED)
        lines = []
        for i, text in enumerate((f"Pagina {n} Brașov", "județul și orașul")):
            words = [WordData(None, t, 95.0, bbox=Rect(100 + 200 * j, 200 + 80 * i, 180, 40))
                     for j, t in enumerate(text.split())]
            lines.append(LineData(None, words=words))
        p.areas.append(AreaData(n, AreaType.TEXT, [], 0, bbox=Rect(100, 200, 800, 200),
                                blocks=[BlockData(None, lines=lines)]))
        out.append(p)
    return out


# =============================================================================
# Q-030..Q-032: imaginile paginilor
# =============================================================================


def test_T_Q031_1_single_tiff_for_all_pages(pages, tmp_path):
    (out,) = export_page_images(pages, tmp_path / "toate.tif", ExportFormat.TIFF,
                                multipage=True, compression="group4")
    with Image.open(out) as img:
        assert img.n_frames == 2 and img.mode == "1"
        assert img.info.get("compression") == "group4"


@pytest.mark.parametrize("compression, expected", [
    ("zip", "tiff_adobe_deflate"), ("lzw", "tiff_lzw"), ("packbits", "packbits"),
    ("jpeg", "jpeg")])
def test_T_Q032_1_tiff_compressions(pages, tmp_path, compression, expected):
    (out,) = export_page_images(pages[:1], tmp_path / "p.tif", ExportFormat.TIFF,
                                compression=compression)
    with Image.open(out) as img:
        assert img.info.get("compression") == expected


def test_T_Q030_1_one_file_per_page(pages, tmp_path):
    written = export_page_images(pages, tmp_path / "p.jpg", ExportFormat.JPEG, dpi=100)
    assert [w.name for w in written] == ["p_001.jpg", "p_002.jpg"]
    with Image.open(written[0]) as img:
        assert img.size == (827, 1169)  # 150 → 100 dpi
    (png,) = export_page_images(pages[:1], tmp_path / "u.png", ExportFormat.PNG, dpi=150)
    assert png.is_file()


def test_T_Q031_2_rules(pages, tmp_path):
    with pytest.raises(ValueError, match="TIFF"):
        export_page_images(pages, tmp_path / "x.png", ExportFormat.PNG, multipage=True)
    with pytest.raises(ValueError, match="JBIG2"):
        export_page_images(pages, tmp_path / "x.jb2", ExportFormat.JBIG2)
    with pytest.raises(ValueError):
        export_page_images(pages, tmp_path / "x.tif", ExportFormat.TIFF, compression="rar")


# =============================================================================
# Q-022, X-127: DjVu
# =============================================================================


def chunks(data: bytes) -> dict[bytes, bytes]:
    assert data[:8] == b"AT&TFORM" and data[12:16] == b"DJVU"
    assert struct.unpack(">I", data[8:12])[0] == len(data) - 12
    out, pos = {}, 16
    while pos < len(data):
        name, length = data[pos:pos + 4], struct.unpack(">I", data[pos + 4:pos + 8])[0]
        out[name] = data[pos + 8:pos + 8 + length]
        pos += 8 + length + (length % 2)
    return out


def decode_words(txta: bytes, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Inversul codificarii DjVuLibre: cuvintele si dreptunghiurile lor."""
    size = int.from_bytes(txta[:3], "big")
    text = txta[3:3 + size]
    pos = 3 + size + 1
    found = []

    def zone(parent, prev):
        nonlocal pos
        kind = txta[pos]
        x, y, w, h, start = (struct.unpack(">H", txta[pos + 1 + 2 * i:pos + 3 + 2 * i])[0]
                             - 0x8000 for i in range(5))
        length = int.from_bytes(txta[pos + 11:pos + 14], "big")
        count = int.from_bytes(txta[pos + 14:pos + 17], "big")
        pos += 17
        if prev is not None:
            if kind in (1, 4, 5):
                x += prev["xmin"]
                y = prev["ymin"] - y - h
            else:
                x += prev["xmax"]
                y += prev["ymin"]
            start += prev["start"] + prev["length"]
        elif parent is not None:
            x += parent["xmin"]
            y = parent["ymax"] - y - h
            start += parent["start"]
        me = {"xmin": x, "ymin": y, "xmax": x + w, "ymax": y + h, "start": start,
              "length": length}
        if kind == 6:
            found.append((text[start:start + length].decode("utf-8"),
                          (x, height - (y + h), w, h)))
        last = None
        for _ in range(count):
            last = zone(me, last)
        return me

    zone(None, None)
    return found


def test_T_Q022_1_djvu_with_hidden_text(pages, tmp_path):
    """T-Q022.1 / X-127: INFO, imaginea, stratul de text cu pozitiile cuvintelor."""
    written = default_service().export(pages, tmp_path / "d.djvu", ExportFormat.DJVU,
                                       ExportOptions(layout_mode=LayoutMode.EXACT))
    assert [w.name for w in written] == ["d_001.djvu", "d_002.djvu"]
    parts = chunks(written[0].read_bytes())
    assert set(parts) == {b"INFO", b"BGjp", b"TXTa"}
    assert struct.unpack(">HH", parts[b"INFO"][:4]) == (1240, 1754)
    assert struct.unpack("<H", parts[b"INFO"][6:8])[0] == 150
    words = decode_words(parts[b"TXTa"], 1754)
    assert words[0] == ("Pagina", (100, 200, 180, 40))
    assert ("Brașov", (500, 200, 180, 40)) in words and ("orașul", (500, 280, 180, 40)) in words


def test_T_X127_1_page_image_only(pages, tmp_path):
    (out,) = default_service().export(
        pages[:1], tmp_path / "i.djvu", ExportFormat.DJVU,
        ExportOptions(layout_mode=LayoutMode.EXACT, format_options={"save_mode": "image_only"}))
    assert b"TXTa" not in chunks(out.read_bytes())


@pytest.mark.skipif(shutil.which("djvutxt") is None, reason="DjVuLibre lipseste (CI Linux)")
def test_T_Q022_2_djvulibre_reads_the_text(pages, tmp_path):
    """T-Q022.2: un cititor DjVu real (DjVuLibre) citeste textul si imaginea."""
    (out,) = default_service().export(pages[:1], tmp_path / "r.djvu", ExportFormat.DJVU,
                                      ExportOptions(layout_mode=LayoutMode.EXACT))
    text = subprocess.run(["djvutxt", str(out)], capture_output=True, check=True).stdout
    decoded = text.decode("utf-8")
    assert "Brașov" in decoded and "orașul" in decoded
    subprocess.run(["ddjvu", "-format=pgm", str(out), str(tmp_path / "r.pgm")], check=True)
