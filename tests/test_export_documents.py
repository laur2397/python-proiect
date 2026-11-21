"""Faza 6, pasul 6.4: DOCX, RTF, ODT (Q-013, Q-014, X-100..X-109)."""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

import docx
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
    TableCellData,
    TableData,
    WordData,
)


def words(text, y, **kw):
    return [WordData(None, t, 95.0, bbox=Rect(100 + 120 * i, y, 100, 50), **kw)
            for i, t in enumerate(text.split())]


def block(*lines, y=300, kind="paragraph", style=None, level=None):
    out = BlockData(None, kind, style_name=style, list_level=level,
                    bbox=Rect(100, y, 1000, 60 * len(lines)))
    for i, line in enumerate(lines):
        ws = line if isinstance(line, list) else words(line, y + 60 * i)
        out.lines.append(LineData(None, words=ws))
    return out


@pytest.fixture
def pages(tmp_path):
    path = tmp_path / "p.png"
    Image.new("RGB", (2480, 3508), (240, 240, 240)).save(path, dpi=(300, 300))
    p = PageData(1, 1, path, path, 2480, 3508, 300, 300, ColorMode.COLOR,
                 status=PageStatus.RECOGNIZED)
    bold = words("Brașov", 600, is_bold=True, text_color="#AA0000")
    unsure = words("finantere", 600, is_uncertain=True)
    secret = words("Cod", 660, is_redacted=True)
    blocks = [
        block("Antet comun", y=50, kind="header"),
        block("Cerere de finanțare", y=200, style="Heading 1"),
        block("Județul", bold + unsure, "proiect de investi-", "ții", y=400),
        block("• Bugetul proiectului", y=900, kind="list_item", level=1),
        block(secret + words("secret", 660), y=1000),
        block("1 Conform legii", y=3300, kind="footnote"),
    ]
    for i, b in enumerate(blocks):
        p.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=b.bbox, blocks=[b]))
    table = TableData(rows=2, cols=2, v_separators=[700], h_separators=[1300], cells=[
        TableCellData(10, 0, 0, col_span=2, bbox=Rect(100, 1200, 1200, 100),
                      blocks=[block("Total general", y=1210)]),
        TableCellData(11, 1, 0, bbox=Rect(100, 1300, 600, 100), blocks=[block("Sibiu", y=1310)]),
        TableCellData(12, 1, 1, bbox=Rect(700, 1300, 600, 100), blocks=[block("1250", y=1310)]),
    ])
    p.areas.append(AreaData(20, AreaType.TABLE, [], 6, bbox=Rect(100, 1200, 1200, 200),
                            table=table))
    p.areas.append(AreaData(21, AreaType.PICTURE, [], 7, bbox=Rect(100, 1600, 400, 300)))
    second = PageData(2, 2, path, path, 2480, 3508, 300, 300, ColorMode.COLOR,
                      status=PageStatus.RECOGNIZED)
    b2 = block("Pagina a doua", y=300)
    second.areas.append(AreaData(30, AreaType.TEXT, [], 0, bbox=b2.bbox, blocks=[b2]))
    return [p, second]


def export(pages, path, fmt, mode=LayoutMode.EDITABLE, **kw):
    options = ExportOptions(layout_mode=mode, **kw)
    (out,) = default_service().export(pages, path, fmt, options)
    return out


# =============================================================================
# Q-013: DOCX
# =============================================================================


def test_T_Q013_1_docx_editable(pages, tmp_path):
    """T-Q013.1: stilul de titlu, formatarea, tabelul unit, imaginea, rupturile."""
    out = export(pages, tmp_path / "e.docx", ExportFormat.DOCX, keep_headers_footers=True,
                 format_options={"keep_line_numbers": True, "highlight_low_confidence": True,
                                 "highlight_color": "#FFB000"})
    d = docx.Document(str(out))
    texts = [p.text for p in d.paragraphs]
    heading = next(p for p in d.paragraphs if p.text == "Cerere de finanțare")
    assert heading.style.name == "Heading 1"
    assert any("proiect de investiții" in t for t in texts)  # cratima refacuta
    assert any("••• secret" in t for t in texts)  # O-072
    run = next(r for p in d.paragraphs for r in p.runs if r.text.strip() == "Brașov")
    assert run.bold and str(run.font.color.rgb) == "AA0000"
    (table,) = d.tables
    assert table.cell(0, 0).text == "Total general" and table.cell(0, 1).text == "Total general"
    assert table.cell(1, 1).text == "1250"
    assert len(d.inline_shapes) == 1
    assert "Antet comun" in d.sections[0].header.paragraphs[-1].text  # X-103
    assert len(d.sections) == 2  # X-105: ruptura de pagina
    xml = d.element.xml
    assert "w:lnNumType" in xml and 'w:fill="FFB000"' in xml  # X-106, X-109


def test_T_Q004_2_docx_formatted_and_plain(pages, tmp_path):
    formatted = docx.Document(str(export(pages, tmp_path / "f.docx", ExportFormat.DOCX,
                                         LayoutMode.FORMATTED, keep_headers_footers=True)))
    assert all("Antet" not in p.text for p in formatted.sections[0].header.paragraphs)
    assert len(formatted.sections) == 1 and len(formatted.tables) == 1
    plain = docx.Document(str(export(pages, tmp_path / "p.docx", ExportFormat.DOCX,
                                     LayoutMode.PLAIN)))
    assert plain.tables == [] and len(plain.inline_shapes) == 0
    assert any(p.text == "Sibiu" for p in plain.paragraphs)  # celulele devin paragrafe
    run = next(r for p in plain.paragraphs for r in p.runs if "Brașov" in r.text)
    assert run.bold and run.font.size is None  # X-108: bold pastrat, fara marimi


def test_T_Q002_3_docx_exact_keeps_vertical_spacing(pages, tmp_path):
    d = docx.Document(str(export(pages, tmp_path / "x.docx", ExportFormat.DOCX,
                                 LayoutMode.EXACT)))
    assert any(p.paragraph_format.space_before for p in d.paragraphs)


# =============================================================================
# Q-014: RTF si ODT
# =============================================================================


def test_T_Q014_1_rtf(pages, tmp_path):
    text = export(pages, tmp_path / "d.rtf", ExportFormat.RTF).read_text(encoding="ascii")
    assert text.startswith("{\\rtf1") and text.rstrip().endswith("}")
    assert "Bra\\u537?ov" in text  # ș cu virgula, U+0219
    assert "\\clmgf" in text and "\\clmrg" in text and "\\pngblip" in text
    assert "Heading 1" in text and "\\sect" in text
    plain = export(pages, tmp_path / "p.rtf", ExportFormat.RTF, LayoutMode.PLAIN)
    assert "\\pict" not in plain.read_text(encoding="ascii")


def test_T_Q014_2_odt(pages, tmp_path):
    out = export(pages, tmp_path / "d.odt", ExportFormat.ODT)
    with zipfile.ZipFile(out) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == b"application/vnd.oasis.opendocument.text"
        content = z.read("content.xml").decode("utf-8")
        for name in ("styles.xml", "meta.xml", "META-INF/manifest.xml", "content.xml"):
            ElementTree.fromstring(z.read(name))  # XML bine format
        assert any(n.startswith("Pictures/") for n in z.namelist())
    assert 'text:outline-level="1"' in content and "Brașov" in content
    assert "table:covered-table-cell" in content and 'number-columns-spanned="2"' in content
    assert 'fo:break-before="page"' in content


def test_T_Q001_4_editable_formats_refuse_flexible(pages, tmp_path):
    for fmt in (ExportFormat.DOCX, ExportFormat.RTF, ExportFormat.ODT):
        with pytest.raises(IncompatibleLayoutError):
            export(pages, tmp_path / f"x.{fmt.value}", fmt, LayoutMode.FLEXIBLE)


def test_T_X101_1_paper_size(pages, tmp_path):
    """X-101: marimea hartiei aleasa (A5)."""
    d = docx.Document(str(export(pages, tmp_path / "a5.docx", ExportFormat.DOCX,
                                 format_options={"paper_size": "a5"})))
    assert round(d.sections[0].page_width.pt) == 420
