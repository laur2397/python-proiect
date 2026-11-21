"""Faza 6c, pasul 6c.1: conversia rapida din Lansator (A-013…A-073)."""

from __future__ import annotations

import pytest
from _pdftext import make_text_pdf
from PIL import Image

from app.core.context import AppContext
from app.core.convert import (
    OTHER_FORMATS,
    ConvertJob,
    ConvertSettings,
    FullTextSearch,
)
from app.core.model import (
    BlockData,
    ExportFormat,
    LayoutMode,
    LineData,
    Progress,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths


class ScriptEngine:
    """Motor fals: textul fiecarei pagini e numele fisierului-sursa."""

    name = "fals"

    def __init__(self):
        self.calls = 0

    def recognize_page(self, page, settings, cancel=None):
        self.calls += 1
        text = page.source_file.stem if page.source_file else f"pagina{page.page_number}"
        word = WordData(None, text, 95.0, bbox=Rect(50, 50, 300, 40))
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=Rect(50, 50, 300, 40))],
                          bbox=Rect(50, 50, 300, 40))
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def files(tmp_path):
    out = []
    for name in ("cerere", "anexa", "buget"):
        img = Image.new("L", (600, 800), 255)
        img.paste(0, (50, 50, 350, 90))
        img.save(tmp_path / f"{name}.png", dpi=(300, 300))
        out.append(tmp_path / f"{name}.png")
    return out


def pdf_text(path):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


def test_T_A013_1_one_pdf_per_file(ctx, files, tmp_path):
    result = ConvertJob(files, ConvertSettings(), context=ctx, engine=ScriptEngine()).run(
        tmp_path / "out")
    assert [p.name for p in result.written] == ["cerere.pdf", "anexa.pdf", "buget.pdf"]
    assert result.failed == [] and not result.cancelled
    assert "cerere" in pdf_text(result.written[0])[0]  # PDF cautabil


def test_T_A024_1_combine_in_list_order(ctx, files, tmp_path):
    settings = ConvertSettings(combine=True)
    result = ConvertJob(list(reversed(files)), settings, context=ctx,
                        engine=ScriptEngine()).run(tmp_path / "out", "Dosar finantare")
    assert [p.name for p in result.written] == ["Dosar finantare.pdf"]
    pages = pdf_text(result.written[0])
    assert len(pages) == 3
    assert "buget" in pages[0] and "anexa" in pages[1] and "cerere" in pages[2]


def test_combine_needs_two_files(ctx, files):
    with pytest.raises(ValueError):
        ConvertJob(files[:1], ConvertSettings(combine=True), context=ctx)
    with pytest.raises(ValueError):
        ConvertJob([], ConvertSettings(), context=ctx)


def test_T_A036_1_disabled_search_makes_an_image_only_pdf(ctx, files, tmp_path):
    engine = ScriptEngine()
    settings = ConvertSettings(full_text_search=FullTextSearch.DISABLED)
    result = ConvertJob(files[:1], settings, context=ctx, engine=engine).run(tmp_path)
    assert engine.calls == 0
    assert pdf_text(result.written[0])[0].strip() == ""


def test_T_A036_2_as_original_keeps_the_text_layer_without_ocr(ctx, tmp_path):
    source = make_text_pdf(tmp_path / "digital.pdf", ["Contract de finantare"])
    engine = ScriptEngine()
    settings = ConvertSettings(full_text_search=FullTextSearch.AS_ORIGINAL)
    result = ConvertJob([source], settings, context=ctx, engine=engine).run(tmp_path / "out")
    assert engine.calls == 0
    assert "Contract de finantare" in pdf_text(result.written[0])[0]


def test_T_A037_1_pdfa_2b_by_default(ctx, files, tmp_path):
    import pikepdf

    settings = ConvertSettings(pdfa=True)
    result = ConvertJob(files[:1], settings, context=ctx, engine=ScriptEngine()).run(tmp_path)
    with pikepdf.open(result.written[0]) as pdf:
        assert pdf.open_metadata().pdfa_status == "2B"


def test_T_A050_1_word_and_excel(ctx, files, tmp_path):
    word = ConvertJob(files[:1], ConvertSettings(target=ExportFormat.DOCX), context=ctx,
                      engine=ScriptEngine()).run(tmp_path / "w")
    assert word.written[0].suffix == ".docx"
    with pytest.raises(ValueError):  # A-060: Excel numai Formatted / Plain
        ConvertSettings(target=ExportFormat.XLSX, layout_mode=LayoutMode.EXACT).validate()
    excel = ConvertJob(files[:1], ConvertSettings(target=ExportFormat.XLSX,
                                                  sheet_per_page=True),
                       context=ctx, engine=ScriptEngine()).run(tmp_path / "x")
    assert excel.written[0].suffix == ".xlsx"


def test_T_A070_1_other_formats(ctx, files, tmp_path):
    assert [f.value for f in OTHER_FORMATS] == ["pptx", "odt", "html", "epub", "fb2", "rtf",
                                                 "txt", "csv", "djvu"]
    result = ConvertJob(files[:1], ConvertSettings(target=ExportFormat.TXT), context=ctx,
                        engine=ScriptEngine()).run(tmp_path)
    assert result.written[0].read_text(encoding="utf-8").strip() == "cerere"


def test_T_A028_1_a_bad_file_does_not_stop_the_batch(ctx, files, tmp_path):
    bad = tmp_path / "stricat.png"
    bad.write_bytes(b"nu e imagine")
    result = ConvertJob([files[0], bad, files[1]], ConvertSettings(), context=ctx,
                        engine=ScriptEngine()).run(tmp_path / "out")
    assert [p.name for p in result.written] == ["cerere.pdf", "anexa.pdf"]
    assert [f.name for f, _ in result.failed] == ["stricat.png"]


def test_progress_and_cancel(ctx, files, tmp_path):
    reports: list[Progress] = []

    def cancel():
        return any(r.current == 1 for r in reports)

    result = ConvertJob(files, ConvertSettings(), context=ctx, engine=ScriptEngine()).run(
        tmp_path / "out", progress=reports.append, cancel=cancel)
    assert result.cancelled and [p.name for p in result.written] == ["cerere.pdf"]
    assert reports[0].stage == "stage.converting" and reports[0].total == 3


def test_existing_files_are_not_overwritten(ctx, files, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "cerere.pdf").write_bytes(b"vechi")
    result = ConvertJob(files[:1], ConvertSettings(), context=ctx,
                        engine=ScriptEngine()).run(out)
    assert result.written[0].name == "cerere (2).pdf"
    assert (out / "cerere.pdf").read_bytes() == b"vechi"
