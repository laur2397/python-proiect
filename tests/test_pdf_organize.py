"""Operatiile pe paginile unui PDF (faza 8, pasul 8.1): E-004…E-022, E-035, E-036."""

from __future__ import annotations

import pikepdf
import pytest
from PIL import Image, ImageDraw
from test_pdf_search import text_pdf
from test_scanner import FakeScanner

from app.core.context import AppContext
from app.core.errors import LastPageError, PasswordRequiredError, WrongPasswordError
from app.core.images.scanner import ScanSettings
from app.core.model import Rect
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.organize import (
    WARN_IMAGES,
    WARN_NOTES,
    PageOrganizer,
    format_range,
    insertion_point,
    parse_range,
)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def five_pages(tmp_path, name="dosar.pdf"):
    return text_pdf(tmp_path / name, [[f"Pagina {n}"] for n in range(1, 6)])


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(five_pages(tmp_path)) as d:
        yield d


def texts(document):
    return [document.extract_text(n).strip() for n in range(1, document.page_count + 1)]


# --- E-004, E-016 ----------------------------------------------------------------------


def test_T_E004_page_range_text():
    assert parse_range("2,3,5-7", 10).pages == (2, 3, 5, 6, 7)
    assert parse_range(" 7 - 5 , 2 ", 10).pages == (2, 5, 6, 7)  # inversat, spatii
    assert parse_range("Even Pages", 5).pages == (2, 4)
    assert parse_range("odd pages", 5).pages == (1, 3, 5)
    assert parse_range("All Pages", 3).pages == (1, 2, 3)
    result = parse_range("4, 9-11", 10)
    assert result.pages == (4, 9, 10) and result.ignored == (11,)  # avertisment
    with pytest.raises(ValueError):
        parse_range("doi", 5)
    assert format_range([2, 5, 7, 8, 9, 3]) == "2, 3, 5, 7-9"


def test_T_E016_insertion_positions():
    assert insertion_point("first", 5) == 1
    assert insertion_point("last", 5) == 6
    assert insertion_point("after", 5, 3) == 4
    with pytest.raises(ValueError):
        insertion_point("after", 5, None)


# --- E-005…E-008 ------------------------------------------------------------------------


def test_T_E005_delete_pages_and_the_last_page(doc):
    organizer = PageOrganizer(doc)
    organizer.delete([2, 4])
    assert texts(doc) == ["Pagina 1", "Pagina 3", "Pagina 5"] and doc.is_modified
    with pytest.raises(LastPageError):
        organizer.delete([1, 2, 3])
    assert doc.page_count == 3


def test_delete_drops_bookmarks_to_deleted_pages(doc):
    assert doc.bookmarks()  # text_pdf: un semn de carte catre ultima pagina
    PageOrganizer(doc).delete([5])
    assert doc.bookmarks() == []


def test_T_E006_E007_rotate(doc):
    organizer = PageOrganizer(doc)
    organizer.rotate([1, 3], 90)
    organizer.rotate([3], -180)
    assert [doc.page_rotation(n) for n in (1, 2, 3)] == [90, 0, 270]
    with pytest.raises(ValueError):
        organizer.rotate([1], 45)


def test_T_E008_correct_orientation_leaves_pages_without_text(doc):
    seen = []

    def detect(image):
        seen.append(image.name)
        return 90 if image.name == "2.png" else 0  # pagina 3: fara text → 0

    assert PageOrganizer(doc).correct_orientation([2, 3], detect=detect) == {2: 90}
    assert len(seen) == 2
    assert doc.page_rotation(2) == 90 and doc.page_rotation(3) == 0


# --- E-010 ------------------------------------------------------------------------------


def test_T_E010_crop_one_frame_or_one_per_page(doc):
    organizer = PageOrganizer(doc)
    organizer.crop([1, 2], Rect(10, 20, 300, 400))
    assert doc.page_size(1) == pytest.approx((300, 400))
    with pikepdf.open(doc.path) as original:  # fisierul de pe disc ramane
        assert "/CropBox" not in original.pages[0].obj
    organizer.crop([3, 4], {3: Rect(0, 0, 100, 100), 4: Rect(0, 0, 200, 50)},
                   same_for_all=False)
    assert doc.page_size(3) == pytest.approx((100, 100))
    assert doc.page_size(4) == pytest.approx((200, 50))
    with pytest.raises(ValueError):
        organizer.crop([5], {4: Rect(0, 0, 10, 10)}, same_for_all=False)
    with pytest.raises(ValueError):
        organizer.crop([5], Rect(900, 900, 10, 10))


# --- E-013…E-017 -------------------------------------------------------------------------


def test_T_E013_blank_page(doc):
    PageOrganizer(doc).add_blank(3)
    assert doc.page_count == 6 and doc.extract_text(3).strip() == ""
    assert doc.page_size(3) == pytest.approx(doc.page_size(2))
    PageOrganizer(doc).add_blank(7, (300, 200))
    assert doc.page_size(7) == pytest.approx((300, 200))


def test_T_E014_pages_from_pdf_with_position(doc, tmp_path):
    other = text_pdf(tmp_path / "anexa.pdf", [["Anexa A"], ["Anexa B"], ["Anexa C"]])
    count = PageOrganizer(doc).insert_from_pdf(other, source_pages=[3, 1],
                                               at=insertion_point("after", 5, 1))
    assert count == 2
    assert texts(doc)[:4] == ["Pagina 1", "Anexa C", "Anexa A", "Pagina 2"]


def test_T_E014_protected_pdf_asks_for_password(doc, tmp_path):
    source = tmp_path / "parola.pdf"
    with pikepdf.open(text_pdf(tmp_path / "plain.pdf", [["Secret"]])) as pdf:
        pdf.save(source, encryption=pikepdf.Encryption(owner="o", user="u"))
    organizer = PageOrganizer(doc)
    with pytest.raises(PasswordRequiredError):
        organizer.insert_from_pdf(source, at=1)
    answers = iter(["gresit", None])
    with pytest.raises(WrongPasswordError):
        organizer.insert_from_pdf(source, at=1, password=lambda p: next(answers))
    organizer.insert_from_pdf(source, at=1, password=lambda p: "u")
    assert texts(doc)[0] == "Secret"


def scan_image(path):
    img = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(img).rectangle((200, 300, 1000, 360), fill="black")
    img.save(path, dpi=(150, 150))
    return path


def test_T_E015_pages_from_file_go_through_image_processing(doc, tmp_path, ctx):
    image = scan_image(tmp_path / "scan.png")
    count = PageOrganizer(doc).insert_from_file(image, at=6, context=ctx)
    assert count == 1 and doc.page_count == 6
    assert doc.extract_text(6).strip() == ""  # fara recunoastere: doar imagine


def test_T_E017_pages_from_scanner(doc, tmp_path, ctx):
    (tmp_path / "scanner").mkdir()
    scanner = FakeScanner(tmp_path / "scanner", sheets=2)
    count = PageOrganizer(doc).insert_from_scanner(ScanSettings("adf", use_adf=True), 1,
                                                    service=scanner, context=ctx)
    assert count == 2 and doc.page_count == 7
    assert texts(doc)[2] == "Pagina 1"


# --- E-018…E-020 -------------------------------------------------------------------------


def test_T_E018_E019_move_pages(doc):
    organizer = PageOrganizer(doc)
    assert organizer.move([4, 5], 1) == [1, 2]  # inainte de prima
    assert texts(doc) == ["Pagina 4", "Pagina 5", "Pagina 1", "Pagina 2", "Pagina 3"]
    assert organizer.move([1], 6) == [5]  # dupa ultima
    assert texts(doc)[-1] == "Pagina 4"
    assert organizer.move([1], insertion_point("after", 5, 2)) == [2]
    assert texts(doc)[:3] == ["Pagina 1", "Pagina 5", "Pagina 2"]


def test_T_E020_replace_pages(doc, tmp_path):
    other = text_pdf(tmp_path / "nou.pdf", [["Nou A"], ["Nou B"], ["Nou C"]])
    organizer = PageOrganizer(doc)
    organizer.replace([2, 3], other, [1, 2])
    assert texts(doc) == ["Pagina 1", "Nou A", "Nou B", "Pagina 4", "Pagina 5"]
    with pytest.raises(ValueError) as err:
        organizer.replace([1, 2, 3], other, [1, 2])
    assert err.value.args[1:] == (3, 2)
    assert doc.page_count == 5


# --- E-021, E-022 ------------------------------------------------------------------------


def test_T_E021_find_blank_pages(doc):
    organizer = PageOrganizer(doc)
    organizer.add_blank(3)
    organizer.add_blank(7)
    assert organizer.find_blank() == [3, 7]
    assert organizer.find_blank(0.0) == list(range(1, 8))  # prag permisiv
    with pytest.raises(ValueError):
        organizer.find_blank(2)


def test_T_E022_content_warning_before_deleting_blank_pages(doc):
    organizer = PageOrganizer(doc)
    assert organizer.content_warnings([1, 2]) == {1: [WARN_NOTES]}
    pdf = doc._pike()
    resources = pdf.pages[1].obj.Resources
    resources.XObject = pikepdf.Dictionary()
    for name in ("/Im1", "/Im2"):
        resources.XObject[name] = pikepdf.Stream(
            pdf, b"\xff", Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
            Width=1, Height=1, ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=8)
    assert organizer.content_warnings([2]) == {2: [WARN_IMAGES]}


# --- E-035, E-036 ------------------------------------------------------------------------


def test_T_E036_new_document_from_selected_pages(doc):
    new = PageOrganizer(doc).extract_to_new_document([4, 2])
    try:
        assert new.path is None and new.is_modified
        assert texts(new) == ["Pagina 4", "Pagina 2"]
        assert doc.page_count == 5
    finally:
        new.close()


def test_T_E035_enhance_images_replaces_pages_in_place(doc, ctx):
    PageOrganizer(doc).enhance_images([2], context=ctx)
    assert doc.page_count == 5
    assert doc.extract_text(2).strip() == ""  # pagina e acum imagine
    assert doc.extract_text(3).strip() == "Pagina 3"
