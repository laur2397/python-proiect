"""Faza 6, pasul 6.1: baza exportului si exportul TXT (Q-001..Q-007, Q-018,
Q-023, Q-024, Q-051, X-123)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.context import AppContext
from app.core.errors import (
    IncompatibleLayoutError,
    NoTextFoundError,
    PagesNotRecognizedError,
    PdfAEncryptionConflictError,
)
from app.core.export.base import (
    IMAGE_FORMATS,
    PDF_FORMATS,
    ExportOptions,
    block_text,
    default_service,
    options_from_settings,
)
from app.core.export.txt import TxtExporter
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
from app.core.paths import AppPaths

# =============================================================================
# Q-001..Q-007: matricea
# =============================================================================


def test_T_Q001_2_every_combination_is_checked():
    """T-Q001.2: pentru cele 90 de combinatii, exact cele din Q-002..Q-006
    trec validarea; PDF/A si PDF/UA urmeaza PDF-ul; imaginile paginilor nu au
    mod de layout (Q-030)."""
    for mode in LayoutMode:
        for fmt in ExportFormat:
            options = ExportOptions(layout_mode=mode)
            base = ExportFormat.PDF if fmt in PDF_FORMATS else fmt
            ok = fmt in IMAGE_FORMATS or base in ExportFormat.allowed_for(mode)
            if ok:
                options.validate(fmt)
            else:
                with pytest.raises(IncompatibleLayoutError) as info:
                    options.validate(fmt)
                assert info.value.params["layout_mode"] == mode.value


def test_T_Q006_2_flexible_only_html_and_csv_only_plain():
    service = default_service()
    assert service.formats_for(LayoutMode.FLEXIBLE) == [ExportFormat.HTML]
    assert ExportFormat.CSV in service.formats_for(LayoutMode.PLAIN)
    assert ExportFormat.CSV not in service.formats_for(LayoutMode.FORMATTED)


def test_T_Q012_2_image_only_pdf_in_any_mode():
    """Q-012: PDF-ul doar-imagine nu depinde de mod."""
    ExportOptions(layout_mode=LayoutMode.PLAIN, searchable=False).validate(ExportFormat.PDF)


def test_T_I006_1_pdfa_with_a_password_is_refused():
    with pytest.raises(PdfAEncryptionConflictError):
        ExportOptions(layout_mode=LayoutMode.EXACT, password="x").validate(ExportFormat.PDFA)


# =============================================================================
# Documentul de test
# =============================================================================


def word(text, x=10):
    return WordData(None, text, 95.0, bbox=Rect(x, 10, 50, 20))


def block(*lines, kind="paragraph", level=None):
    return BlockData(None, kind, lines=[LineData(None, words=[word(t) for t in line.split()])
                                       for line in lines], list_level=level)


def page(number, *blocks, status=PageStatus.RECOGNIZED, table=None):
    p = PageData(number, number, Path("x.png"), Path("x.png"), 2480, 3508, 300, 300,
                 ColorMode.GRAY, status=status)
    for i, b in enumerate(blocks):
        p.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=Rect(0, 100 * i, 10, 10),
                                blocks=[b]))
    if table is not None:
        p.areas.append(table)
    return p


def table_area(cells):
    table = TableData(rows=2, cols=2, cells=[
        TableCellData(i, r, c, blocks=[block(text)]) for i, ((r, c), text)
        in enumerate(cells.items())])
    return AreaData(99, AreaType.TABLE, [], 9, bbox=Rect(0, 900, 10, 10), table=table)


SECRET = block("Cod secret")
SECRET.lines[0].words[0].is_redacted = True

DOC = [
    page(1, block("Antet comun", kind="header"),
         block("Cerere de finan-", "tare pentru proiect"),
         block("• Bugetul", kind="list_item", level=1),
         block("a) pe activitati", kind="list_item", level=2),
         table=table_area({(0, 0): "Județ", (0, 1): "Suma", (1, 0): "Brașov", (1, 1): "1250"})),
    page(2, block("Semnătura", "beneficiarului"), SECRET),
]


# =============================================================================
# Q-051, Q-023, Q-024
# =============================================================================


def test_T_Q051_1_warning_for_invalidated_pages():
    service = default_service()
    pages = [*DOC, page(3, block("nou"), status=PageStatus.ANALYZED)]
    warnings = service.check_before_export(pages, ExportOptions(), ExportFormat.TXT)
    assert len(warnings) == 1 and isinstance(warnings[0], PagesNotRecognizedError)
    assert warnings[0].params["page_numbers"] == [3]
    assert service.check_before_export(DOC, ExportOptions(), ExportFormat.TXT) == []
    no_tables = service.check_before_export([DOC[1]], ExportOptions(), ExportFormat.XLSX)
    assert isinstance(no_tables[0], NoTextFoundError)


def test_T_Q023_1_only_the_chosen_pages(tmp_path):
    service = default_service()
    options = ExportOptions(layout_mode=LayoutMode.PLAIN, page_range=(2,))
    (out,) = service.export(DOC, tmp_path / "p2.txt", ExportFormat.TXT, options)
    text = out.read_text(encoding="utf-8")
    assert "Semnătura beneficiarului" in text and "Cerere" not in text
    with pytest.raises(ValueError):
        service.export(DOC, tmp_path / "x.txt", ExportFormat.TXT,
                       ExportOptions(layout_mode=LayoutMode.PLAIN, page_range=(9,)))


def test_T_Q024_1_options_from_settings(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        ctx.settings.set("txt.layout", "formatted")
        ctx.settings.set("txt.encoding", "utf-16")
        ctx.settings.set("txt.page_break_char", True)
        options = options_from_settings(ctx.settings, ExportFormat.TXT)
        assert options.layout_mode is LayoutMode.FORMATTED and options.encoding == "utf-16"
        assert options.format_options["page_break_char"] is True
        assert options.keep_line_breaks is True  # txt.keep_line_breaks implicit
    finally:
        ctx.close()


# =============================================================================
# Q-018, X-123: TXT
# =============================================================================


def export_txt(tmp_path, **kw):
    fmt_options = {k: kw.pop(k) for k in ("page_break_char", "blank_line_paragraphs")
                   if k in kw}
    options = ExportOptions(**{"layout_mode": LayoutMode.PLAIN, **kw},
                            format_options=fmt_options)
    (out,) = default_service().export(DOC, tmp_path / "d.txt", ExportFormat.TXT, options)
    return out


def test_T_Q018_1_plain_text(tmp_path):
    text = export_txt(tmp_path).read_text(encoding="utf-8")
    assert "Antet comun" not in text  # X-103: antetele numai la cerere
    assert "Cerere de finantare pentru proiect" in text  # randuri unite, cratima refacuta
    assert "Județ\nSuma\nBrașov\n1250" in text  # plain: fiecare celula e un paragraf
    assert text.rstrip().endswith("••• secret")  # O-072: textul redactat


def test_T_Q018_2_formatted_text(tmp_path):
    text = export_txt(tmp_path, layout_mode=LayoutMode.FORMATTED,
                      keep_headers_footers=True).read_text(encoding="utf-8")
    assert text.startswith("Antet comun")
    assert "Județ\tSuma\nBrașov\t1250" in text  # randurile tabelului, cu tab
    assert "\n  a) pe activitati" in text  # lista de nivel 2, indentata


def test_T_X123_1_line_breaks_page_break_blank_lines(tmp_path):
    text = export_txt(tmp_path, keep_line_breaks=True, page_break_char=True,
                      blank_line_paragraphs=True).read_text(encoding="utf-8")
    assert "Cerere de finan-\ntare pentru proiect" in text
    assert text.count("\f") == 1
    assert "\n\n" in text.split("\f")[0]


def test_T_X123_2_encodings_keep_romanian_letters(tmp_path):
    """CLAUDE.md §6.4: UTF-16 cu BOM; pe 8 biti, ș/ț devin ş/ţ, nu `?`."""
    utf16 = export_txt(tmp_path, encoding="utf-16").read_bytes()
    assert utf16[:2] in (b"\xff\xfe", b"\xfe\xff") and "Brașov" in utf16.decode("utf-16")
    legacy = export_txt(tmp_path, encoding="windows-1250").read_bytes().decode("windows-1250")
    assert "Braşov" in legacy and "Judeţ" in legacy and "?" not in legacy


def test_T_O072_2_redacted_text_is_dots():
    assert block_text(SECRET, False) == "••• secret"


def test_T_Q001_3_txt_in_exact_mode_is_refused(tmp_path):
    with pytest.raises(IncompatibleLayoutError):
        default_service().export(DOC, tmp_path / "x.txt", ExportFormat.TXT,
                                 ExportOptions(layout_mode=LayoutMode.EXACT))
    exporter = TxtExporter()
    assert exporter.supported_layout_modes == {LayoutMode.FORMATTED, LayoutMode.PLAIN}
    assert exporter.default_options().layout_mode is LayoutMode.PLAIN


def test_T_Q100_2_separate_file_per_page(tmp_path):
    """Q-100 `Create a separate file`: cate un fisier pe pagina, numerotat."""
    from app.core.export.base import ExportOptions, default_service
    from app.core.model import (
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

    pages = []
    for n in (1, 2, 3):
        word = WordData(n, f"pagina{n}", 95.0, bbox=Rect(0, 0, 10, 10))
        page = PageData(n, n, tmp_path / "x.png", tmp_path / "x.png", 100, 100, 300, 300,
                        ColorMode.GRAY, status=PageStatus.RECOGNIZED)
        from app.core.model import AreaData, AreaType

        page.areas = [AreaData(n, AreaType.TEXT, [], 0, bbox=Rect(0, 0, 10, 10), blocks=[
            BlockData(n, lines=[LineData(n, words=[word])])])]
        pages.append(page)
    options = ExportOptions(layout_mode=LayoutMode.PLAIN, separate_file_per_page=True)
    written = default_service().export(pages, tmp_path / "doc.txt", ExportFormat.TXT, options)
    assert [p.name for p in written] == ["doc_001.txt", "doc_002.txt", "doc_003.txt"]
    assert "pagina2" in written[1].read_text(encoding="utf-8")
