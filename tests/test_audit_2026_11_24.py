"""Defectele gasite la auditul din 24.11.2026 (docs/audit/AUDIT_2026-11-24.md)."""

from __future__ import annotations

from test_text_editor import ctx, project, words  # noqa: F401

from app.core.ocr.dictionary import DictionaryService, _read_lines
from app.core.pdf.signing import _timestamp_failure
from app.core.text.editor import TextEditor

# --- §6.4: sedila si virgula -----------------------------------------------------------


def test_dictionary_words_with_cedilla_match_the_ocr_text(ctx):  # noqa: F811
    dic = DictionaryService(ctx.app_db)
    assert dic.add("ţara", "ron")  # dintr-un dictionar vechi, cu sedila
    assert dic.contains("țara", "ron")  # textul recunoscut are virgula
    assert not dic.add("țara", "ron")  # acelasi cuvant, nu un duplicat
    assert dic.words("ron") == {"țara"}


def test_windows_1250_dictionary_is_not_mojibake():
    data = "Braşov\nţară\nşcoală\n".encode("cp1250")
    assert _read_lines(data) == ["Braşov", "ţară", "şcoală"]
    latin = "café\nnaïve\n".encode("cp1252")  # P-023: Windows-1252 ramane implicit
    assert _read_lines(latin) == ["café", "naïve"]


def test_find_matches_cedilla_and_comma_forms(project):  # noqa: F811
    ed = TextEditor(project)
    ed.set_word_text(words(project, 2)[0], "Brașov")
    found = ed.find(project.pages, "Braşov", ignore_diacritics=False, match_case=True)
    assert [w.text for w in found] == ["Brașov"]


# --- semnarea (G-037) ------------------------------------------------------------------


def test_only_timestamp_failures_are_treated_as_timestamp_errors():
    assert _timestamp_failure(ConnectionError("serverul nu raspunde"))
    wrapped = RuntimeError("semnare")
    wrapped.__cause__ = TimeoutError()
    assert _timestamp_failure(wrapped)
    assert not _timestamp_failure(ValueError("aspect gresit"))  # nu se ascunde


# --- PdfDocument: redeschiderea dupa salvare -------------------------------------------


def test_failed_reload_closes_the_file(tmp_path, monkeypatch):
    import pikepdf

    from app.core.pdf import document as module
    from app.core.pdf.document import PdfDocument

    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(tmp_path / "a.pdf")
    doc = PdfDocument.open(tmp_path / "a.pdf")
    closed = []
    real_open = pikepdf.open

    def tracking_open(*a, **k):
        opened = real_open(*a, **k)
        original = opened.close

        def close():
            closed.append(1)
            original()

        opened.close = close
        return opened

    def broken(*a, **k):
        raise module.pdfium.PdfiumError("stricat")

    monkeypatch.setattr(module.pikepdf, "open", tracking_open)
    monkeypatch.setattr(module, "new_pdfium", broken)
    doc._reload_from(tmp_path / "a.pdf")
    assert closed == [1]  # fisierul nu ramane blocat
    assert doc.page_count == 1  # documentul din memorie ramane utilizabil
    doc.close()


# --- linkurile catre fisiere (F-027) ---------------------------------------------------


def test_launch_links_become_valid_file_uris():
    from app.core.pdf.navigation import file_uri

    assert file_uri(r"C:\Dosare\Cerere finanțare.pdf") == \
        "file:///C:/Dosare/Cerere%20finan%C8%9Bare.pdf"
    assert file_uri("/Users/x/a b.pdf") == "file:///Users/x/a%20b.pdf"
    assert file_uri(r"anexe\a.pdf") == "file:anexe/a.pdf"


# --- analiza: spatierea 1,5 ramane un paragraf (performanta si Word) --------------------


def test_one_and_a_half_spacing_stays_one_text_area(tmp_path, ctx):  # noqa: F811
    from PIL import Image, ImageDraw, ImageFont

    from app.core.layout.analyzer import LayoutAnalyzer
    from app.core.model import AreaType, AutoProcessMode
    from app.core.project import OcrProject

    img = Image.new("L", (1240, 1754), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=20)
    for i in range(12):  # litere de ~15 px, rand la 35 px: spatiere ~1,5
        draw.text((100, 200 + i * 35), "Beneficiarul isi asuma obligatiile din contract",
                  font=font, fill=0)
    img.save(tmp_path / "p.png", dpi=(150, 150))
    proj = OcrProject.create(context=ctx)
    try:
        proj.add_images([tmp_path / "p.png"], auto_process=AutoProcessMode.NONE)
        proj.analyze_pages([1], analyzer=LayoutAnalyzer())
        texts = [a for a in proj.page(1).areas if a.area_type is AreaType.TEXT]
        assert len(texts) == 1  # nu cate o zona pe rand (12 apeluri Tesseract)
    finally:
        proj.close()


# --- preprocesarea in paralel (N-027) --------------------------------------------------


def test_parallel_preprocessing_keeps_page_order(tmp_path, ctx):  # noqa: F811
    from PIL import Image

    from app.core.model import AutoProcessMode, PreprocessOp
    from app.core.project import OcrProject, _preprocess_workers

    assert _preprocess_workers(None, 3) <= 3 and _preprocess_workers(2, 10) == 2
    paths = []
    for n, width in enumerate((300, 400, 500, 600)):
        Image.new("L", (width, 200), 255).save(tmp_path / f"{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"{n}.png")
    proj = OcrProject.create(context=ctx)
    try:
        proj.add_images(paths, auto_process=AutoProcessMode.NONE)
        proj.preprocess_pages([1, 2, 3, 4], [(PreprocessOp.ROTATE, {"angle": 90})])
        assert [p.height_px for p in proj.pages] == [300, 400, 500, 600]  # rotite, in ordine
        assert all(proj.applied_operations(n) for n in (1, 2, 3, 4))
        proj.undo()  # un singur pas de undo (L-109)
        assert [p.width_px for p in proj.pages] == [300, 400, 500, 600]
    finally:
        proj.close()
