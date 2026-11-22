"""Copierea din PDF Editor (faza 7, pasul 7.3): C-040…C-049."""

from __future__ import annotations

import pikepdf
import pytest
from _pdftext import make_text_pdf
from PIL import Image
from test_pdf_search import TextEngine, text_pdf

from app.core.context import AppContext
from app.core.export.base import ExportOptions
from app.core.model import LayoutMode, Rect
from app.core.paths import AppPaths
from app.core.pdf import copying
from app.core.pdf.document import PdfDocument


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def path(tmp_path):
    return text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"],
        ["Anexa 2: buget detaliat", "Bugetare si BUGET"],
    ])


def table_pdf(path):
    """Un tabel 2x2 tras cu linii, cu text in celule (Helvetica 14)."""
    cells = [("Nume", 80, 570), ("Suma", 230, 570), ("Ana", 80, 520), ("1200", 230, 520)]
    ops = ["1 w 72 500 300 100 re S 222 500 m 222 600 l S 72 550 m 372 550 l S"]
    ops += [f"BT /F1 14 Tf {x} {y} Td ({t}) Tj ET" for t, x, y in cells]
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
        Contents=pdf.make_stream(" ".join(ops).encode()),
        Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)))))
    pdf.save(path)
    return path


TABLE_AREA = Rect(66, 236, 312, 112)
"""Tabelul din `table_pdf` (72..372 x 500..600 in PDF), cu o margine mica."""


# --- C-040 ----------------------------------------------------------------------------


def test_T_C040_1_area_must_stay_on_one_page(path):
    with PdfDocument.open(path) as doc:
        copying.check_area(doc, 1, Rect(10, 10, 100, 100))
        with pytest.raises(ValueError):
            copying.check_area(doc, 1, Rect(500, 800, 200, 100))  # iese din pagina
        with pytest.raises(ValueError):
            copying.check_area(doc, 1, Rect(10, 10, 0, 50))
        with pytest.raises(ValueError):
            copying.check_area(doc, 3, Rect(10, 10, 50, 50))


# --- C-042 ----------------------------------------------------------------------------


def test_T_C042_1_copy_as_image(path):
    with PdfDocument.open(path) as doc:
        hit = next(h for h in doc.search("Cerere") if h.source == "text")
        image = copying.area_image(doc, 1, hit.rect)
        assert abs(image.width - hit.rect.w * 300 / 72) <= 2
        assert abs(image.height - hit.rect.h * 300 / 72) <= 2
        assert image.convert("L").getextrema()[0] < 60  # textul se vede in imagine
        assert not doc.is_modified


# --- C-043, C-044 ---------------------------------------------------------------------


def test_T_C043_1_copy_as_text_from_text_layer(path):
    with PdfDocument.open(path) as doc:
        line = next(h for h in doc.search("Bugetul") if h.source == "text").rect
        copied = copying.area_text(doc, 1, Rect(60, line.y - 2, 400, line.h + 4))
        assert copied.text == "Bugetul total: 1200 lei"
        assert not copied.from_ocr and copied.warning is None
        both = copying.area_text(doc, 1, Rect(60, 50, 400, 120))
        assert both.text == "Cerere de finantare\nBugetul total: 1200 lei"
        part = copying.area_text(doc, 1, Rect(60, line.y - 2, 88, line.h + 4))
        assert part.text == "Bugetul"


def test_T_C043_2_copy_as_text_on_a_scan_uses_ocr(tmp_path, ctx):
    image = tmp_path / "scan.png"
    img = Image.new("L", (600, 800), 255)
    img.paste(0, (60, 60, 540, 100))
    img.save(image, dpi=(300, 300))
    options = ExportOptions(layout_mode=LayoutMode.EXACT, searchable=False)
    with PdfDocument.from_images([image], options=options, context=ctx) as doc:
        assert not doc.has_text_layer(1)
        copied = copying.area_text(doc, 1, Rect(0, 0, 144, 40), context=ctx,
                                   engine=TextEngine(["Cerere", "aprobata"]))
        assert copied.from_ocr
        assert copied.text == "Cerere aprobata"


def test_T_C044_1_text_selection_across_pages(path):
    with PdfDocument.open(path) as doc:
        start_hit = next(h for h in doc.search("total") if h.source == "text")
        start = copying.char_index_at(doc, 1, start_hit.rect.x + 1, start_hit.rect.y + 5)
        assert start == start_hit.start
        assert copying.char_index_at(doc, 1, 5, 5) is None
        end = next(h for h in doc.search("Anexa") if h.source == "text")
        text = copying.text_between(doc, (2, end.start + end.length - 1), (1, start))
        assert text == "total: 1200 lei\nAnexa"


# --- C-045…C-047 ----------------------------------------------------------------------


def test_T_C045_1_copy_as_table(tmp_path):
    path = table_pdf(tmp_path / "tabel.pdf")
    original = path.read_bytes()
    with PdfDocument.open(path) as doc:
        table = copying.area_table(doc, 1, TABLE_AREA)
        assert (table.table.rows, table.table.cols) == (2, 2)
        assert table.cell_texts() == [["Nume", "Suma"], ["Ana", "1200"]]
        assert table.to_tsv() == "Nume\tSuma\nAna\t1200"
        assert table.to_html() == ("<table><tr><td>Nume</td><td>Suma</td></tr>"
                                   "<tr><td>Ana</td><td>1200</td></tr></table>")
        assert not doc.is_modified
    assert path.read_bytes() == original  # C-047


def test_T_C046_1_edit_table_structure_before_copy(tmp_path):
    with PdfDocument.open(table_pdf(tmp_path / "tabel.pdf")) as doc:
        table = copying.area_table(doc, 1, TABLE_AREA)
        first_row = [c for c in table.table.cells if c.row == 0]
        table.merge_cells(first_row)
        assert table.cell_texts()[0] == ["Nume Suma", ""]
        assert 'colspan="2"' in table.to_html()
        table.split_cell(next(c for c in table.table.cells if c.row == 0))
        assert table.cell_texts()[0] == ["Nume", "Suma"]
        separator = table.table.v_separators[0]
        table.remove_separator("vertical", separator)
        assert table.table.cols == 1
        assert table.cell_texts() == [["Nume Suma"], ["Ana 1200"]]
        table.add_separator("vertical", separator)
        assert table.cell_texts() == [["Nume", "Suma"], ["Ana", "1200"]]


def test_T_C045_2_table_without_structure_is_one_cell(path):
    with PdfDocument.open(path) as doc:
        table = copying.area_table(doc, 1, Rect(60, 60, 98, 30))
        assert (table.table.rows, table.table.cols) == (1, 1)
        assert table.cell_texts() == [["Cerere de"]]


# --- C-049 ----------------------------------------------------------------------------


def test_T_C049_1_warning_when_text_does_not_match_the_image(tmp_path):
    dark = Image.new("L", (200, 100), 30)
    path = make_text_pdf(tmp_path / "img.pdf", ["Text"], image=dark,
                         image_box=(72, 300, 300, 150))
    with PdfDocument.open(path) as doc:
        copied = copying.area_text(doc, 1, Rect(100, 420, 100, 60))  # peste imagine, fara text
        assert copied.text == ""
        assert copied.warning == copying.WARNING_COPY_MISMATCH
        clean = copying.area_text(doc, 1, Rect(0, 0, 50, 30))  # colt alb, fara text
        assert clean.warning is None
