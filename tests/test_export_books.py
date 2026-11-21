"""Faza 6, pasul 6.6: HTML, EPUB, FB2 (Q-006, Q-019, Q-020, Q-021, X-124..X-126)."""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

import pytest
from PIL import Image

from app.core.errors import IncompatibleLayoutError
from app.core.export.base import ExportOptions, default_service
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


def block(text, y, style=None, kind="paragraph", bold=False):
    words = [WordData(None, t, 95.0, bbox=Rect(100 + 120 * i, y, 100, 50), is_bold=bold)
             for i, t in enumerate(text.split())]
    return BlockData(None, kind, style_name=style, lines=[LineData(None, words=words)],
                     bbox=Rect(100, y, 1000, 60))


@pytest.fixture
def pages(tmp_path):
    path = tmp_path / "p.png"
    Image.new("RGB", (2480, 3508), (250, 250, 250)).save(path, dpi=(300, 300))
    out = []
    for n, (title, sub) in enumerate((("Capitolul 1", "Secțiunea 1.1"),
                                      ("Capitolul 2", "Secțiunea 2.1")), start=1):
        p = PageData(n, n, path, path, 2480, 3508, 300, 300, ColorMode.COLOR,
                     status=PageStatus.RECOGNIZED)
        blocks = [block("Antet dosar", 50, kind="header"), block(title, 200, "Heading 1"),
                  block("Text din Brașov", 400, bold=n == 1), block(sub, 600, "Heading 2"),
                  block("Încă un paragraf", 800)]
        for i, b in enumerate(blocks):
            p.areas.append(AreaData(10 * n + i, AreaType.TEXT, [], i, bbox=b.bbox, blocks=[b]))
        p.areas.append(AreaData(10 * n + 9, AreaType.PICTURE, [], 9,
                                bbox=Rect(100, 1000, 300, 200)))
        out.append(p)
    return out


def export(pages, path, fmt, mode=LayoutMode.FORMATTED, **kw):
    return default_service().export(pages, path, fmt, ExportOptions(layout_mode=mode, **kw))


def test_T_Q019_1_html_formatted(pages, tmp_path):
    """T-Q019.1 / X-124: titluri, bold, imagini in folderul alaturat."""
    (out,) = export(pages, tmp_path / "d.html", ExportFormat.HTML)
    html = out.read_text(encoding="utf-8")
    import re

    assert re.search(r"<h1>(<span[^>]*>)?Capitolul 1(</span>)?</h1>", html)
    assert re.search(r"<h2>(<span[^>]*>)?Secțiunea 1.1(</span>)?</h2>", html)
    assert "<b>Text" in html and "Brașov" in html and "Antet dosar" not in html
    assert (tmp_path / "d_files" / "img1.png").is_file() and 'src="d_files/img1.png"' in html
    (out,) = export(pages, tmp_path / "h.html", ExportFormat.HTML, keep_headers_footers=True)
    assert "Antet dosar" in out.read_text(encoding="utf-8")


def test_T_Q006_3_html_flexible_positions(pages, tmp_path):
    """T-Q006.3: `Flexible layout` pune blocurile la pozitia lor."""
    (out,) = export(pages, tmp_path / "f.html", ExportFormat.HTML, LayoutMode.FLEXIBLE)
    html = out.read_text(encoding="utf-8")
    assert "left:32px;top:64px" in html  # 100, 200 px la 300 dpi
    assert html.count('class="page"') == 2


def test_T_X124_1_html_encoding(pages, tmp_path):
    (out,) = export(pages, tmp_path / "w.html", ExportFormat.HTML, encoding="windows-1250")
    text = out.read_bytes().decode("windows-1250")
    assert 'charset="windows-1250"' in text and "Braşov" in text and "Încă" in text


@pytest.mark.parametrize("split, files", [("h1", 2), ("h2", 4)])
def test_T_X125_1_book_split(pages, tmp_path, split, files):
    """T-X125.1: impartirea pe titluri, cu cuprins."""
    written = export(pages, tmp_path / "b.html", ExportFormat.HTML,
                     format_options={"book_split": split})
    assert len(written) == files + 1  # cuprinsul + partile
    toc = written[0].read_text(encoding="utf-8")
    assert "Capitolul 2" in toc and all(p.is_file() for p in written)


@pytest.mark.parametrize("version", ["3.0", "2.0"])
def test_T_Q020_1_epub(pages, tmp_path, version):
    """T-Q020.1 / X-126: structura EPUB, capitole la titlurile de nivel 1, coperta."""
    (out,) = export(pages, tmp_path / f"e{version}.epub", ExportFormat.EPUB,
                    format_options={"version": version, "first_page_cover": True})
    with zipfile.ZipFile(out) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        names = z.namelist()
        assert "META-INF/container.xml" in names and "OEBPS/cover.jpg" in names
        assert ("OEBPS/nav.xhtml" in names) == (version == "3.0")
        chapters = sorted(n for n in names if n.startswith("OEBPS/chapter"))
        assert len(chapters) == 2
        for name in [*chapters, "OEBPS/content.opf", "OEBPS/toc.ncx"]:
            ElementTree.fromstring(z.read(name))  # XML bine format
        assert "Brașov" in z.read(chapters[0]).decode("utf-8")
        assert f'version="{version}"' in z.read("OEBPS/content.opf").decode("utf-8")


def test_T_Q021_1_fb2(pages, tmp_path):
    """T-Q021.1: FictionBook valid, sectiuni, strong, imagini base64."""
    (out,) = export(pages, tmp_path / "d.fb2", ExportFormat.FB2,
                    format_options={"first_page_cover": True})
    root = ElementTree.fromstring(out.read_bytes())
    ns = "{http://www.gribuser.ru/xml/fictionbook/2.0}"
    assert len(root.find(f"{ns}body").findall(f"{ns}section")) == 2
    text = out.read_text(encoding="utf-8")
    assert "<strong>" in text and "Brașov" in text and "<binary" in text
    assert "<coverpage>" in text


def test_T_Q001_5_ebooks_and_html_modes(pages, tmp_path):
    for fmt in (ExportFormat.EPUB, ExportFormat.FB2):
        with pytest.raises(IncompatibleLayoutError):
            export(pages, tmp_path / f"x.{fmt.value}", fmt, LayoutMode.FLEXIBLE)
    with pytest.raises(IncompatibleLayoutError):
        export(pages, tmp_path / "x.html", ExportFormat.HTML, LayoutMode.EXACT)
