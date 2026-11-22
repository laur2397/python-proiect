"""Semnele de carte, atasamentele, proprietatile si metadatele (faza 9, pasul
9.1): F-032…F-038, F-052, F-054…F-056."""

from __future__ import annotations

import pikepdf
import pytest
from test_pdf_search import text_pdf

from app.core.errors import NoWritePermissionError
from app.core.model import BookmarkData
from app.core.pdf.document import PdfDocument, pdf_date_iso


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root[:] = []
        pdf.save(path)
    with PdfDocument.open(path) as d:
        yield d


def tree(document):
    def walk(items):
        return [(b.title, b.target_page, walk(b.children)) if b.children
                else (b.title, b.target_page) for b in items]
    return walk(document.bookmarks())


def ids(document):
    out = {}

    def walk(items):
        for b in items:
            out[b.title] = b.id
            walk(b.children)
    walk(document.bookmarks())
    return out


# --- F-032…F-035 ---------------------------------------------------------------------------


def test_T_F032_new_bookmark_points_to_the_top_of_the_page(doc):
    bm = doc.add_bookmark(BookmarkData(None, "Cerere", target_page=2))
    [mark] = doc.bookmarks()
    assert (mark.title, mark.level, mark.target_page) == ("Cerere", 1, 2)
    assert mark.target_y == pytest.approx(0, abs=0.5)
    assert bm.id == mark.id and doc.is_modified
    with pytest.raises(ValueError):
        doc.add_bookmark(BookmarkData(None, "  ", target_page=1))


def test_T_F033_bookmark_on_a_selection_targets_its_position(doc):
    doc.add_bookmark(BookmarkData(None, "Bugetul total", target_page=3, target_y=200))
    [mark] = doc.bookmarks()
    assert mark.target_page == 3 and mark.target_y == pytest.approx(200, abs=0.5)


def test_T_F035_nesting_follows_the_previously_selected_bookmark(doc):
    first = doc.add_bookmark(BookmarkData(None, "Capitolul 1", target_page=1))  # radacina
    doc.add_bookmark(BookmarkData(None, "Sectiunea 1.1", target_page=1), first.id)
    section = ids(doc)["Sectiunea 1.1"]
    doc.add_bookmark(BookmarkData(None, "Sectiunea 1.2", target_page=2), after_id=section)
    doc.add_bookmark(BookmarkData(None, "Capitolul 2", target_page=3),
                     after_id=ids(doc)["Capitolul 1"])
    assert tree(doc) == [("Capitolul 1", 1, [("Sectiunea 1.1", 1), ("Sectiunea 1.2", 2)]),
                         ("Capitolul 2", 3)]


def test_T_F034_set_destination_keeps_the_place_in_the_tree(doc):
    parent = doc.add_bookmark(BookmarkData(None, "A", target_page=1))
    doc.add_bookmark(BookmarkData(None, "A1", target_page=1), parent.id)
    doc.set_bookmark_destination(ids(doc)["A"], 4, 100)
    [mark] = doc.bookmarks()
    assert mark.target_page == 4 and mark.target_y == pytest.approx(100, abs=0.5)
    assert [c.title for c in mark.children] == ["A1"]


# --- F-036…F-038 ---------------------------------------------------------------------------


def three(doc):
    for n, title in enumerate(("Unu", "Doi", "Trei"), start=1):
        doc.add_bookmark(BookmarkData(None, title, target_page=n))


def test_T_F036_reorder_and_levels_do_not_change_the_pages(doc):
    from app.core.pdf import outline

    three(doc)
    before = [doc.extract_text(n) for n in range(1, 6)]
    doc.move_bookmark(ids(doc)["Trei"], None, 0)
    assert [t[0] for t in tree(doc)] == ["Trei", "Unu", "Doi"]
    outline.indent(doc, ids(doc)["Doi"])  # `Move one level right`
    assert tree(doc) == [("Trei", 3), ("Unu", 1, [("Doi", 2)])]
    outline.outdent(doc, ids(doc)["Doi"])  # `Move one level left`
    assert tree(doc) == [("Trei", 3), ("Unu", 1), ("Doi", 2)]
    with pytest.raises(ValueError):
        outline.indent(doc, ids(doc)["Trei"])  # primul de pe nivel
    with pytest.raises(ValueError):
        outline.outdent(doc, ids(doc)["Unu"])
    outline.indent(doc, ids(doc)["Doi"])
    with pytest.raises(ValueError):  # nu in propriii descendenti
        doc.move_bookmark(ids(doc)["Unu"], ids(doc)["Doi"], 0)
    assert [doc.extract_text(n) for n in range(1, 6)] == before


def test_T_F037_rename_cannot_be_empty(doc):
    three(doc)
    doc.rename_bookmark(ids(doc)["Doi"], "Anexa 2")
    assert [t[0] for t in tree(doc)] == ["Unu", "Anexa 2", "Trei"]
    with pytest.raises(ValueError):
        doc.rename_bookmark(ids(doc)["Unu"], "")


def test_T_F038_deleting_a_parent_deletes_its_children(doc):
    three(doc)
    doc.add_bookmark(BookmarkData(None, "Unu.1", target_page=1), ids(doc)["Unu"])
    assert doc.delete_bookmarks([ids(doc)["Unu"], ids(doc)["Trei"]]) == 3
    assert tree(doc) == [("Doi", 2)]


def test_bookmarks_survive_saving(doc, tmp_path):
    three(doc)
    target = tmp_path / "salvat.pdf"
    doc.save_as(target)
    with PdfDocument.open(target) as again:
        assert [b.title for b in again.bookmarks()] == ["Unu", "Doi", "Trei"]


# --- F-052 -----------------------------------------------------------------------------------


def test_T_F052_attachment_add_rename_delete(doc, tmp_path):
    source = tmp_path / "buget.xlsx"
    source.write_bytes(b"x" * 100)
    assert doc.add_attachment(source, "Bugetul") == "buget.xlsx"
    assert doc.add_attachment(source) == "buget (2).xlsx"
    doc.rename_attachment("buget (2).xlsx", "buget-final.xlsx")
    assert [a[0] for a in doc.attachments()] == ["buget-final.xlsx", "buget.xlsx"]
    with pytest.raises(ValueError):
        doc.rename_attachment("buget.xlsx", "buget-final.xlsx")
    doc.delete_attachment("buget.xlsx")
    out = tmp_path / "iesire.xlsx"
    doc.extract_attachment("buget-final.xlsx", out)
    assert out.read_bytes() == b"x" * 100 and len(doc.attachments()) == 1
    with pytest.raises(KeyError):
        doc.delete_attachment("lipsa")


# --- F-054, F-055 ----------------------------------------------------------------------------


def test_T_F054_F055_document_properties(doc):
    doc.set_metadata(author="Ana Popescu", keywords="finantare, buget")
    props = doc.properties()
    assert props["title"] == "Dosar de finantare" and props["author"] == "Ana Popescu"
    assert props["editable"] is True
    assert props["file_name"] == "dosar.pdf" and props["pages"] == 5
    assert props["page_size"] == pytest.approx((595, 842))
    assert props["file_size"] > 0 and props["pdf_version"]
    assert props["tagged"] is False and props["fast_web_view"] is False
    assert props["pdfa"] is None and props["pdfua"] is None


def test_T_F054_protected_file_is_read_only(tmp_path):
    path = tmp_path / "protejat.pdf"
    with pikepdf.open(text_pdf(tmp_path / "s.pdf", [["A"]])) as pdf:
        pdf.save(path, encryption=pikepdf.Encryption(
            owner="proprietar", user="", allow=pikepdf.Permissions(modify_other=False)))
    with PdfDocument.open(path) as doc:
        assert doc.properties()["editable"] is False
        with pytest.raises(NoWritePermissionError):
            doc.set_metadata(title="Nou")


def test_pdf_dates_for_the_properties_dialog():
    assert pdf_date_iso("D:20260122143000+02'00'") == "2026-01-22T14:30:00+02:00"
    assert pdf_date_iso("D:20260122") == "2026-01-22T00:00:00"
    assert pdf_date_iso(None) is None


# --- F-056 -----------------------------------------------------------------------------------


def test_T_F056_metadata_survives_conversion(tmp_path):
    from app.core.context import AppContext
    from app.core.convert import ConvertJob, ConvertSettings, FullTextSearch
    from app.core.model import ExportFormat
    from app.core.paths import AppPaths

    source = text_pdf(tmp_path / "sursa.pdf", [["Pagina 1"]])
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Author"] = "Ana Popescu"
        pdf.docinfo["/Subject"] = "Cerere"
        pdf.save(source)
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        settings = ConvertSettings(target=ExportFormat.PDF,
                                   full_text_search=FullTextSearch.DISABLED)
        result = ConvertJob([source], settings, context=ctx).run(tmp_path / "out")
    finally:
        ctx.close()
    [written] = result.written
    with pikepdf.open(written) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Dosar de finantare"
        assert str(pdf.docinfo["/Author"]) == "Ana Popescu"
        assert str(pdf.docinfo["/Subject"]) == "Cerere"


def test_T_F056_explicit_options_win_and_empty_means_deleted(tmp_path):
    from app.core.export.base import ExportOptions, with_source_metadata
    from app.core.model import ColorMode, PageData

    source = text_pdf(tmp_path / "sursa.pdf", [["Pagina 1"]])
    page = PageData(1, 1, tmp_path / "x.png", tmp_path / "x.png", 10, 10, 300, 300,
                    ColorMode.GRAY, source_file=source)
    options = with_source_metadata(ExportOptions(metadata={"title": "", "author": "Eu"}),
                                   [page])
    assert options.metadata["title"] == "" and options.metadata["author"] == "Eu"
