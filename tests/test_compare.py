"""Compararea documentelor, nucleul (faza 12, pasii 12.1…12.3): R-002…R-008,
R-015, R-016, R-020…R-022, R-030…R-036, R-043, R-044, R-048, R-049, R-061…R-067."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import docx
import openpyxl
import pikepdf
import pytest
from pptx import Presentation
from test_pdf_background import LineEngine
from test_pdf_search import text_pdf

from app.core.compare import sources
from app.core.compare.engine import (
    GROUPS,
    DocumentComparer,
    compare_sources,
    grouped,
    ignore,
    ignore_identical,
    recent_comparisons,
)
from app.core.compare.report import (
    save_pdf_with_comments,
    save_report,
    save_track_changes,
)
from app.core.compare.sources import (
    SourceDocument,
    blocks_to_pdf,
    load_source,
    pdf_words,
)
from app.core.context import AppContext
from app.core.errors import NoTextFoundError, UnsupportedFormatError
from app.core.model import CompareOptions, DiffType
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument

CATALOG = json.loads((Path(__file__).resolve().parent.parent / "app/gui/i18n/ro.json")
                     .read_text(encoding="utf-8"))


def texts(key, **params):
    return CATALOG[key].format(**params)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def built(blocks, name="x.pdf"):
    document = PdfDocument._from_bytes(blocks_to_pdf(blocks), None)
    words, _ = pdf_words(document)
    return SourceDocument(Path(name), document, words, converted=True)


def diff(left, right, **options):
    return compare_sources(built(left), built(right), CompareOptions(**options))


def summary(differences):
    return [(d.diff_type.value, d.text_left, d.text_right) for d in differences]


# --- 12.1: sursele --------------------------------------------------------------------------------


def test_T_R008_compare_languages_are_a_declared_subset():
    from app.core.ocr import languages

    codes = sources.compare_languages()
    assert len(codes) == len(set(codes)) == 37  # P-101: declaram ce acoperim
    for code in codes:
        languages.get(code)
    for missing in ("chi_sim", "jpn", "tha"):
        assert missing not in codes  # fara spatii intre cuvinte


def test_T_R002_R005_editable_formats(tmp_path):
    word = docx.Document()
    word.sections[0].header.paragraphs[0].text = "Antet firmă"
    word.add_paragraph("Cerere de finanțare")
    table = word.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Suma", "100 lei"
    word.save(tmp_path / "a.docx")
    book = openpyxl.Workbook()
    book.active.append(["Buget", 1200])
    book.save(tmp_path / "a.xlsx")
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[1]).shapes.title.text = "Prezentare ș"
    deck.save(tmp_path / "a.pptx")
    with zipfile.ZipFile(tmp_path / "a.odt", "w") as odt:
        odt.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        odt.writestr("content.xml", (
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:'
            'xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            '<office:body><office:text><text:h>Titlu</text:h><text:p>Un<text:s/>paragraf'
            '</text:p></office:text></office:body></office:document-content>'))
    (tmp_path / "a.rtf").write_text(
        r"{\rtf1\ansi{\fonttbl{\f0 Arial;}}\f0 Cerere de \u537?ansa\par Al doilea r\'e2nd}",
        encoding="latin-1")
    (tmp_path / "a.html").write_text("<html><head><style>p{}</style></head><body><h1>Titlu"
                                     "</h1><p>Text &amp; paragraf</p></body></html>",
                                     encoding="utf-8")
    (tmp_path / "a.txt").write_text("Primul rând\fA doua pagină", encoding="utf-8")
    expected = {
        "a.docx": ["Antet", "firmă", "Cerere", "de", "finanțare", "Suma", "100", "lei"],
        "a.xlsx": ["Buget", "1200"], "a.pptx": ["Prezentare", "ș"],
        "a.odt": ["Titlu", "Un", "paragraf"],
        "a.rtf": ["Cerere", "de", "șansa", "Al", "doilea", "rând"],
        "a.html": ["Titlu", "Text", "&", "paragraf"],
        "a.txt": ["Primul", "rând", "A", "doua", "pagină"],
    }
    for name, words in expected.items():
        source = load_source(tmp_path / name)
        try:
            assert [w.text for w in source.words] == words, name
            assert source.converted and not source.recognized
        finally:
            source.close()
    txt = load_source(tmp_path / "a.txt")
    assert txt.document.page_count == 2
    txt.close()


def test_T_R002_unsupported_and_missing(tmp_path):
    for name in ("a.vsdx", "a.csv", "a.epub", "a.doc"):
        (tmp_path / name).write_bytes(b"x")
        assert not sources.can_compare(tmp_path / name)
        with pytest.raises(UnsupportedFormatError):
            load_source(tmp_path / name)
    with pytest.raises(FileNotFoundError):
        load_source(tmp_path / "lipsa.pdf")
    (tmp_path / "rupt.docx").write_bytes(b"nu e zip")
    with pytest.raises(UnsupportedFormatError):
        load_source(tmp_path / "rupt.docx")


def test_T_R020_text_from_pdf_by_default(tmp_path):
    path = text_pdf(tmp_path / "a.pdf", [["Contract de finantare"], ["Anexa 1"]])
    engine = LineEngine(["nu", "trebuie"])
    source = load_source(path, engine=engine)
    try:
        assert [w.text for w in source.words] == ["Contract", "de", "finantare", "Anexa", "1"]
        assert [w.page for w in source.words] == [1, 1, 1, 2, 2]
        assert engine.calls == 0 and not source.recognized
    finally:
        source.close()


def test_T_R007_R021_ocr_on_scans_and_on_request(tmp_path, ctx):
    from PIL import Image

    image = Image.new("L", (1200, 1600), 255)
    image.paste(0, (120, 120, 1080, 200))
    scan = tmp_path / "scan.pdf"
    image.save(scan, "PDF", resolution=300)
    source = load_source(scan, context=ctx, engine=LineEngine(["Cerere", "aprobata"]))
    try:
        assert [w.text for w in source.words] == ["Cerere", "aprobata"] and source.recognized
    finally:
        source.close()
    text = text_pdf(tmp_path / "t.pdf", [["Text din fisier"]])
    forced = load_source(text, mode="ocr", context=ctx, engine=LineEngine(["Recunoscut"]))
    try:
        assert [w.text for w in forced.words] == ["Recunoscut"]  # R-021 `Use OCR`
    finally:
        forced.close()
    with pytest.raises(NoTextFoundError):
        load_source(scan, context=ctx, engine=LineEngine([]))


def test_T_R020_auto_mode_recognizes_bad_text_layers():
    assert sources._looks_bad("§¤ ¶¶ ±± ×× ©®")
    assert not sources._looks_bad("Contractul de finanțare, nr. 12/2026.")


def test_T_R035_hyphenated_words_are_joined():
    box = built([("body", "x y")]).words[0].rect
    words = sources.join_hyphenated([
        sources.SourceWord("con-", 1, box, 0, [(1, box)]),
        sources.SourceWord("tractului", 1, box, 1, [(1, box)])])
    assert [w.text for w in words] == ["contractului"] and len(words[0].rects) == 2
    kept = sources.join_hyphenated([
        sources.SourceWord("Cluj-", 1, box, 0), sources.SourceWord("Napoca", 1, box, 1)])
    assert [w.text for w in kept] == ["Cluj-", "Napoca"]  # urmeaza majuscula
    same_line = sources.join_hyphenated([
        sources.SourceWord("bine-", 1, box, 0), sources.SourceWord("ales", 1, box, 0)])
    assert len(same_line) == 2  # nu e capat de rand


# --- 12.2: algoritmul -------------------------------------------------------------------------------


BASE = [("body", "Contractul de finanțare se încheie astăzi între părți."),
        ("body", "Valoarea totală este 1000 lei, plătibilă în două tranșe.")]


def test_T_R043_identical_documents_have_no_differences():
    assert diff(BASE, BASE) == []


def test_T_R033_minor_differences_are_always_ignored():
    other = [("body", "Contractul  de   finanţare se încheie astăzi între părţi."),
             ("body", "Valoarea totală este 1000 lei, plătibilă în două tranșe.")]
    assert diff(BASE, other) == []  # spatii, ș/ş, ț/ţ


def test_T_R030_R032_R044_types_and_both_versions():
    other = [("body", "Contractul de finanțare se încheie mâine între părți."),
             ("body", "Valoarea totală este 1000 lei."),
             ("body", "Clauză nouă adăugată.")]
    result = diff(BASE, other)
    assert summary(result) == [
        ("replaced", "astăzi", "mâine"),
        ("deleted", "plătibilă în două tranșe.", None),
        ("inserted", None, "Clauză nouă adăugată.")]
    assert result[0].page_left == result[0].page_right == 1
    assert result[0].bbox_left is not None and result[0].bbox_right is not None
    assert result[1].bbox_right is not None  # ancora in documentul fara text


def test_T_R015_R016_punctuation_and_one_letter_options():
    other = [("body", "Contractul de finantare se încheie astăzi între părți!"),
             ("body", "Valoarea totală este 1000 lei, plătibilă în două tranșe.")]
    assert diff(BASE, other) == []  # implicit: fara punctuatie, fara o litera
    assert summary(diff(BASE, other, find_one_letter=True)) == [
        ("replaced", "finanțare", "finantare")]
    assert summary(diff(BASE, other, find_punctuation=True)) == [
        ("replaced", "părți.", "părți!")]
    amounts = [("body", "Contractul de finanțare se încheie astăzi între părți."),
               ("body", "Valoarea totală este 1001 lei, plătibilă în două tranșe.")]
    assert summary(diff(BASE, amounts)) == [("replaced", "1000", "1001")]  # cifrele raman


def test_T_R022_R034_groups_body_headers_numbering():
    left = [("header", "Firma Exemplu SRL"), ("body", "Prima pagină."), ("page", ""),
            ("body", "1. Obiectul contractului"), ("body", "Text comun.")]
    right = [("header", "Firma Model SRL"), ("body", "Prima pagină modificată."), ("page", ""),
             ("body", "2. Obiectul contractului"), ("body", "Text comun.")]
    groups = grouped(diff(left, right))
    assert list(groups) == list(GROUPS)
    assert [d.text_right for d in groups["body"]] == ["modificată."]
    assert [d.text_right for d in groups["numbering"]] == ["2."]
    assert [(d.text_left, d.text_right) for d in groups["headers_footers"]] == [
        ("Exemplu", "Model"), ("Exemplu", "Model")]
    without = diff(left, right, ignore_headers_footers=True)
    assert all(d.group != "headers_footers" for d in without)
    off = diff(left, right, find_headers_footers=False)
    assert all(d.group != "headers_footers" for d in off)  # R-022 dezactivat


def test_T_R034_close_differences_are_merged_within_a_paragraph():
    left = [("body", "unu doi trei patru cinci sase")]
    right = [("body", "unu DOI trei PATRU cinci sase")]
    assert summary(diff(left, right)) == [("replaced", "doi trei patru", "DOI trei PATRU")]
    assert len(diff(left, right, group_distance_words=1)) == 2


def test_T_R036_long_documents_report_progress():
    long_left = [("body", f"Paragraful {i} are un text oarecare.") for i in range(400)]
    long_right = list(long_left)
    long_right[250] = ("body", "Paragraful 250 are alt text.")
    seen = []
    result = compare_sources(built(long_left), built(long_right), CompareOptions(),
                             progress=seen.append)
    assert summary(result) == [("replaced", "un text oarecare.", "alt text.")]
    assert seen and seen[-1].current == seen[-1].total


def test_T_R048_R049_ignore_and_ignore_identical():
    left = [("body", "Pretul este 10 lei. Taxa este 10 lei. Suma este 5 lei.")]
    right = [("body", "Pretul este 20 lei. Taxa este 20 lei. Suma este 6 lei.")]
    result = diff(left, right)
    assert [d.text_right for d in result] == ["20", "20", "6"]
    one = ignore(result, [2])
    assert [d.is_ignored for d in one] == [False, False, True]
    same = ignore_identical(result, 0)
    assert [d.is_ignored for d in same] == [True, True, False]
    assert sum(len(v) for v in grouped(same).values()) == 1


def test_T_R006_R017_comparer_and_recent_comparisons(ctx, tmp_path):
    left = text_pdf(tmp_path / "v1.pdf", [["Termen 30 zile"]])
    right = text_pdf(tmp_path / "v2.pdf", [["Termen 45 zile"]])
    comparer = DocumentComparer(context=ctx)
    assert comparer.can_compare(left) and ".docx" in comparer.SUPPORTED_FORMATS
    result = comparer.compare(left, right, CompareOptions(languages=("ron",)))
    assert summary(result) == [("replaced", "30", "45")]
    assert comparer.extract_text(left, CompareOptions())[0][1] == "Termen"
    [recent] = recent_comparisons(ctx.app_db)
    assert (recent.left, recent.right, recent.languages) == (left, right, ("ron",))
    assert recent.difference_count == 1 and not recent.missing
    right.unlink()
    assert recent_comparisons(ctx.app_db)[0].missing  # R-006: randul se marcheaza


# --- 12.3: salvarea ---------------------------------------------------------------------------------


@pytest.fixture
def pair():
    left = built([("body", "Termenul de plata este 30 de zile."), ("body", "Paragraf vechi.")])
    right = built([("body", "Termenul de plata este 45 de zile."),
                   ("body", "Clauza noua.")])
    differences = compare_sources(left, right, CompareOptions())
    yield left, right, differences
    left.close()
    right.close()


def test_T_R063_pdf_with_comments(pair, tmp_path):
    left, right, differences = pair
    out = save_pdf_with_comments(right, differences, tmp_path / "comentat.pdf", side=2,
                                 texts=texts)
    with pikepdf.open(out) as pdf:
        contents = [str(a.Contents) for a in pdf.pages[0].Annots]
    assert len(contents) == len(differences) == 2
    assert "Text modificat: „30” → „45”" in contents
    out_left = save_pdf_with_comments(left, ignore(differences, [1]), tmp_path / "s.pdf",
                                      side=1, texts=texts)
    with pikepdf.open(out_left) as pdf:
        assert len(pdf.pages[0].Annots) == 1  # R-067: ignorata nu apare


def test_T_R061_track_changes_docx(pair, tmp_path):
    left, right, differences = pair
    out = save_track_changes(right, differences, tmp_path / "doc2.docx", side=2,
                             author="DocuLens")
    with zipfile.ZipFile(out) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "<w:ins " in xml and "<w:del " in xml and "<w:delText" in xml
    assert "45" in xml and "30" in xml and 'w:author="DocuLens"' in xml
    assert docx.Document(str(out)).paragraphs[0].text.startswith("Termenul de plata este")
    save_track_changes(left, differences, tmp_path / "doc1.docx", side=1, author="DocuLens")
    assert (tmp_path / "doc1.docx").exists()  # R-061: cate un fisier per document


def test_T_R064_R414_comparison_report(pair, tmp_path):
    _left, _right, differences = pair
    out = save_report(ignore(differences, [1]), tmp_path / "Differences.docx",
                      left=Path("/acte/v1.pdf"), right=Path("/acte/v2.pdf"), texts=texts)
    [table] = docx.Document(str(out)).tables
    header = table.rows[0].cells
    assert header[0].text == "/acte/v1.pdf" and header[0].paragraphs[0].runs[-1].bold
    assert [[c.text for c in row.cells] for row in table.rows[1:]] == [
        ["[pagina 1] 30", "[pagina 1] 45"]]


def test_T_R065_only_pdf_and_docx(pair, tmp_path):
    _left, right, differences = pair
    with pytest.raises(UnsupportedFormatError):
        save_report(differences, tmp_path / "r.txt", left=Path("a"), right=Path("b"),
                    texts=texts)
    with pytest.raises(UnsupportedFormatError):
        save_pdf_with_comments(right, differences, tmp_path / "r.xlsx", side=2, texts=texts)
    assert DiffType.REPLACED in {d.diff_type for d in differences}
