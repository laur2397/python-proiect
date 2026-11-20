"""Teste pentru app/core/pdf/document.py si pentru PDF in ImageLoader (pasul 1b)."""

from __future__ import annotations

import io
import threading

import pypdfium2 as pdfium
import pytest
from _pdfgen import A4, BLACK, RED, make_pdf
from PIL import Image

from app.core.errors import (
    FileCorruptError,
    PasswordRequiredError,
    UnsupportedFormatError,
    WrongPasswordError,
)
from app.core.images.loader import OCR_DPI, ImageLoader
from app.core.model import ColorMode
from app.core.pdf import document as docmod
from app.core.pdf.document import SCREEN_DPI, PdfDocument, pixel_size

LANDSCAPE = (842.0, 595.0)


def _png(data: bytes) -> Image.Image:
    assert data.startswith(b"\x89PNG")
    return Image.open(io.BytesIO(data))


@pytest.fixture
def two_pages(tmp_path):
    return make_pdf(tmp_path / "dosar.pdf", [(*A4, BLACK), (*LANDSCAPE, RED)])


@pytest.fixture
def secret(tmp_path):
    return make_pdf(tmp_path / "secret.pdf", [(*A4, BLACK)], user_password="parola123")


class Asker:
    """Callback de parola care raspunde pe rand si numara intrebarile."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, path: str):
        self.calls += 1
        return self.answers.pop(0) if self.answers else None


# =============================================================================
# PdfDocument
# =============================================================================


def test_open_and_describe(two_pages):
    with PdfDocument.open(two_pages) as doc:
        assert doc.page_count == 2
        assert doc.pdf_version == "1.7"
        assert doc.is_encrypted is False and doc.is_modified is False
        assert doc.page_size(1) == A4
        assert doc.page_size(2) == LANDSCAPE


def test_T_B001_1_render_page_at_zoom(two_pages):
    """T-B001.1: o pagina se randeaza la cerere, la zoom-ul cerut."""
    with PdfDocument.open(two_pages) as doc:
        full = _png(doc.render_page(1, 1.0))
        assert full.size == pixel_size(*A4, SCREEN_DPI)
        double = _png(doc.render_page(1, 2.0))
        assert double.size[0] == pytest.approx(full.size[0] * 2, abs=2)
        # dreptunghiul negru e jos-stanga
        assert double.getpixel((10, double.size[1] - 10))[:3] == (0, 0, 0)
        assert double.getpixel((double.size[0] - 10, 10))[:3] == (255, 255, 255)


def test_T_B001_2_corrupt_page_fails_alone(two_pages, monkeypatch):
    """T-B001.2: o pagina stricata da eroare doar pentru ea; restul se randeaza."""
    real_render = pdfium.PdfPage.render

    def flaky(self, *a, **k):
        if self.get_size() == LANDSCAPE:
            raise pdfium.PdfiumError("pagina stricata")
        return real_render(self, *a, **k)

    monkeypatch.setattr(pdfium.PdfPage, "render", flaky)
    with PdfDocument.open(two_pages) as doc:
        with pytest.raises(FileCorruptError) as info:
            doc.render_page(2, 1.0)
        assert info.value.params["page"] == 2
        assert _png(doc.render_page(1, 0.5)).size[0] > 0


@pytest.mark.parametrize("zoom", [0, -1.0])
def test_render_rejects_bad_zoom(two_pages, zoom):
    with PdfDocument.open(two_pages) as doc, pytest.raises(ValueError):
        doc.render_page(1, zoom)


def test_render_refuses_absurd_zoom(two_pages):
    with PdfDocument.open(two_pages) as doc, pytest.raises(ValueError):
        doc.render_page(1, 500.0)


@pytest.mark.parametrize("number", [0, 3, -1])
def test_page_out_of_range(two_pages, number):
    with PdfDocument.open(two_pages) as doc:
        with pytest.raises(ValueError):
            doc.render_page(number, 1.0)
        with pytest.raises(ValueError):
            doc.page_size(number)


def test_closed_document_is_refused(two_pages):
    doc = PdfDocument.open(two_pages)
    doc.close()
    doc.close()  # a doua oara nu strica nimic
    with pytest.raises(ValueError):
        _ = doc.page_count


def test_annotations_flag_is_accepted(two_pages):
    with PdfDocument.open(two_pages) as doc:
        assert _png(doc.render_page(1, 0.5, annotations=False)).size[0] > 0


def test_garbage_and_missing_files(tmp_path):
    bad = tmp_path / "rau.pdf"
    bad.write_bytes(b"%PDF-1.4 nu e pdf" * 10)
    with pytest.raises(FileCorruptError):
        PdfDocument.open(bad)
    with pytest.raises(FileNotFoundError):
        PdfDocument.open(tmp_path / "lipsa.pdf")


def test_rendering_from_many_threads(two_pages):
    """PDFium nu e sigur intre fire: zavorul trebuie sa serializeze apelurile."""
    errors: list[BaseException] = []
    with PdfDocument.open(two_pages) as doc:

        def work():
            try:
                for _ in range(5):
                    doc.render_page(1 + threading.get_ident() % 2, 0.3)
            except BaseException as exc:  # noqa: BLE001 — colectam orice esec
                errors.append(exc)

        threads = [threading.Thread(target=work) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert errors == []


# =============================================================================
# Parole (A-011, J-052)
# =============================================================================


def test_T_J052_1_password_is_asked_only_when_needed(two_pages, secret):
    """T-J052.1: parola se cere la deschidere, doar pentru documentele protejate."""
    asker = Asker("parola123")
    PdfDocument.open(two_pages, password=asker).close()
    assert asker.calls == 0
    with PdfDocument.open(secret, password=asker) as doc:
        assert doc.is_encrypted is True
        assert _png(doc.render_page(1, 0.5)).getpixel((5, 300))[:3] == (0, 0, 0)
    assert asker.calls == 1


def test_no_password_given(secret):
    with pytest.raises(PasswordRequiredError):
        PdfDocument.open(secret)
    with pytest.raises(PasswordRequiredError):
        PdfDocument.open(secret, password=Asker())  # renunta din prima


def test_T_A011_1_three_attempts_then_wrong_password(secret):
    """T-A011.1: apelantul limiteaza la 3 incercari; dupa ele, WrongPasswordError."""
    asker = Asker("a", "b", "c")
    with pytest.raises(WrongPasswordError):
        PdfDocument.open(secret, password=asker)
    assert asker.calls == 4  # 3 parole gresite, apoi None = renuntare


def test_right_password_on_third_try(secret):
    asker = Asker("gresit", "tot gresit", "parola123")
    PdfDocument.open(secret, password=asker).close()
    assert asker.calls == 3


# =============================================================================
# Versiuni (Y-108)
# =============================================================================


def test_T_Y108_1_pdf_2_0_is_accepted(tmp_path):
    """T-Y108.1: PDF 2.0 si mai vechi se accepta."""
    path = make_pdf(tmp_path / "v20.pdf", [(*A4, None)], version="2.0")
    assert PdfDocument.open(path).pdf_version == "2.0"
    assert len(ImageLoader().load(path)) == 1


def test_pdf_newer_than_2_0_is_refused_by_loader(tmp_path):
    path = make_pdf(tmp_path / "v21.pdf", [(*A4, None)], version="2.1")
    with pytest.raises(UnsupportedFormatError) as info:
        ImageLoader().load(path)
    assert info.value.params["reason"] == "pdf_version"


# =============================================================================
# PDF in ImageLoader (J-050 cu PDF)
# =============================================================================


def test_T_J050_3_pdf_pages_become_ocr_images(two_pages):
    """T-J050.3: fiecare pagina PDF devine o imagine la rezolutia de OCR."""
    loader = ImageLoader()
    assert loader.can_load(two_pages)
    assert loader.read_page_count(two_pages) == 2
    first, second = loader.load(two_pages)
    assert (first.dpi_x, first.dpi_y) == (OCR_DPI, OCR_DPI) == (300, 300)
    assert (first.width_px, first.height_px) == (2480, 3509)  # A4 la 300 dpi, ca PDFium
    assert (second.width_px, second.height_px) == (3509, 2480)
    assert first.color_mode is ColorMode.GRAY  # negru pe alb
    assert second.color_mode is ColorMode.COLOR  # dreptunghi rosu
    assert [p.source_page for p in (first, second)] == [1, 2]
    assert not first.is_photo


def test_pdf_page_range_and_pixels(two_pages):
    loader = ImageLoader()
    (second,) = loader.load(two_pages, pages=[2])
    pixels = loader.open_pixels(second)
    assert pixels.size == (second.width_px, second.height_px)
    assert pixels.getpixel((20, pixels.size[1] - 20))[:3] == (255, 0, 0)


def test_pdf_thumbnail(two_pages):
    thumb = _png(ImageLoader().render_thumbnail(two_pages, 2, 64))
    assert max(thumb.size) <= 64 and thumb.size[0] > thumb.size[1]


def test_loader_remembers_password_for_pixels(secret):
    loader = ImageLoader()
    (page,) = loader.load(secret, password=Asker("parola123"))
    assert loader.open_pixels(page).getpixel((10, 3400))[:3] == (0, 0, 0)
    assert loader.read_page_count(secret) == 1  # fara sa mai intrebe
    # alta instanta nu stie parola
    with pytest.raises(PasswordRequiredError):
        ImageLoader().open_pixels(page)


def test_loader_reports_missing_password(secret):
    with pytest.raises(PasswordRequiredError):
        ImageLoader().load(secret)


@pytest.mark.parametrize("dpi", [72, 96, 150, 300, 600])
def test_described_size_equals_rendered_size(two_pages, dpi):
    """Zonele au coordonate in pixelii imaginii: descrierea si randarea coincid."""
    with PdfDocument.open(two_pages) as doc:
        img = docmod.render_pdf_page(doc._doc, two_pages, 1, dpi)
    assert img.size == pixel_size(*A4, dpi)


def test_pdf_lock_is_reentrant():
    with docmod.PDFIUM_LOCK, docmod.PDFIUM_LOCK:
        pass
