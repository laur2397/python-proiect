"""Faza 4, pasul 4.5.4: codurile de bare (M-056..M-060, X-066).

Codurile se genereaza cu zxing-cpp (si Postnet cu modelul propriu), se pun pe
o pagina alba la 300 dpi si se citesc din zona lor.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
import zxingcpp
from PIL import Image, ImageDraw

from app.core.context import AppContext
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaData,
    AreaType,
    AutoProcessMode,
    ColorMode,
    PageData,
    Rect,
)
from app.core.ocr import barcodes
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject

SAMPLES = {
    "code39": ("Code39", "DOSAR123"),
    "code93": ("Code93", "DOSAR123"),
    "code128": ("Code128", "Dosar-2026/14"),
    "ean8": ("EAN8", "9638507"),
    "ean13": ("EAN13", "590123412345"),
    "upca": ("UPCA", "03600029145"),
    "upce": ("UPCE", "0123456"),
    "pdf417": ("PDF417", "Cerere de finantare 14"),
    "qrcode": ("QRCode", "Cerere de finantare 14"),
}
EXPECTED = {"ean8": "96385074", "ean13": "5901234123457", "upca": "0036000291452",
            "upce": "0012345000065"}
BOX = Rect(300, 300, 1400, 900)


def barcode_image(fmt: str, text: str) -> Image.Image:
    code = zxingcpp.create_barcode(text, getattr(zxingcpp.BarcodeFormat, fmt))
    return Image.fromarray(np.asarray(code.to_image(scale=4))).convert("L")


def postnet_image(digits: str) -> Image.Image:
    pattern = barcodes.postnet_pattern(digits)
    img = Image.new("L", (40 + len(pattern) * 18, 120), 255)
    d = ImageDraw.Draw(img)
    for i, tall in enumerate(pattern):
        x = 20 + i * 18
        d.rectangle([x, 20 if tall else 62, x + 7, 100], fill=0)
    return img


def page_with(path: Path, code: Image.Image | None) -> Path:
    img = Image.new("L", (2480, 1600), 255)
    if code is not None:
        img.paste(code, (BOX.x + 50, BOX.y + 50))
    img.save(path, dpi=(300, 300))
    return path


def area(path: Path, kind: str = barcodes.AUTODETECT) -> tuple[PageData, AreaData]:
    page = PageData(1, 1, path, path, 2480, 1600, 300, 300, ColorMode.GRAY)
    return page, AreaData(1, AreaType.BARCODE, [], 0, bbox=BOX, barcode_type=kind)


# =============================================================================
# M-057: cele 11 tipuri autodetectate
# =============================================================================


@pytest.mark.parametrize("kind", sorted(SAMPLES))
def test_T_M057_1_autodetect_reads_the_type(tmp_path, kind):
    fmt, text = SAMPLES[kind]
    page, a = area(page_with(tmp_path / "c.png", barcode_image(fmt, text)))
    assert barcodes.read(page, a) == (kind, EXPECTED.get(kind, text))


def test_T_M057_2_postnet_has_its_own_decoder(tmp_path):
    """T-M057.2: Postnet (nu e in zxing-cpp), si rotit cu 90 si 180 de grade."""
    for angle in (0, 90, 180):
        code = postnet_image("12345").rotate(angle, expand=True, fillcolor=255)
        page, a = area(page_with(tmp_path / f"p{angle}.png", code))
        assert barcodes.read(page, a) == ("postnet", "12345"), angle
    page, a = area(page_with(tmp_path / "zip9.png", postnet_image("123456789")))
    assert barcodes.read(page, a) == ("postnet", "123456789")


def test_T_M057_3_ucc128_and_upca_are_told_apart():
    """T-M057.3: UCC-128 = Code 128 cu marcaj GS1; UPC-A = EAN-13 cu 0 in fata."""
    class Code:
        def __init__(self, fmt, text, sid):
            self.format, self.text, self.symbology_identifier = fmt, text, sid

    assert barcodes._classify(Code("BarcodeFormat.Code128", "0101234", "]C1")) == "ucc128"
    assert barcodes._classify(Code("BarcodeFormat.Code128", "ABC", "]C0")) == "code128"
    assert barcodes._classify(Code("BarcodeFormat.EAN13", "0036000291452", "]E0")) == "upca"
    assert barcodes._classify(Code("BarcodeFormat.EAN13", "5901234123457", "]E0")) == "ean13"


# =============================================================================
# M-058: celelalte tipuri numai alese manual
# =============================================================================


def test_T_M058_1_other_types_only_when_chosen(tmp_path):
    path = page_with(tmp_path / "dm.png", barcode_image("DataMatrix", "Dosar 14"))
    page, auto = area(path)
    assert barcodes.read(page, auto) is None  # nu e printre cele 11
    page, manual = area(path, "datamatrix")
    assert barcodes.read(page, manual) == ("datamatrix", "Dosar 14")


def test_T_M058_2_chosen_type_limits_the_search(tmp_path):
    path = page_with(tmp_path / "qr.png", barcode_image("QRCode", "Dosar 14"))
    page, a = area(path, "code128")
    assert barcodes.read(page, a) is None


# =============================================================================
# M-056, M-059, M-060, X-066: prin AreaEditor si RecognitionService
# =============================================================================


class NoTextEngine:
    """Motor fals pentru text; codurile le citeste barcodes.py, ca motorul real."""

    name = "fals"
    lock = threading.Lock()

    def recognize_page(self, page, settings, cancel=None):
        return RecognitionResult(page.page_number)

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})

    def read_barcode(self, page, area):
        return barcodes.read(page, area)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


def project_with_code(ctx, path):
    project = OcrProject.create(context=ctx)
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    AreaEditor(project).create(project.page(1), [(BOX.x, BOX.y), (BOX.right, BOX.y),
                                                 (BOX.right, BOX.bottom), (BOX.x, BOX.bottom)],
                               AreaType.BARCODE)
    return project


def barcode_area(project):
    (a,) = [x for x in project.page(1).areas if x.area_type is AreaType.BARCODE]
    return a


def test_T_M056_2_unknown_type_is_refused(ctx, tmp_path):
    project = project_with_code(ctx, page_with(tmp_path / "x.png", None))
    try:
        ed = AreaEditor(project)
        a = barcode_area(project)
        assert ed.set_properties(project.page(1), a, barcode_type="qrcode").barcode_type == (
            "qrcode")
        with pytest.raises(ValueError):
            ed.set_properties(project.page(1), a, barcode_type="cod-inventat")
    finally:
        project.close()


def test_T_M059_1_without_the_option_codes_stay_images(ctx, tmp_path):
    """T-M059.1: implicit (X-066 dezactivat), codul nu se citeste: ramane imagine."""
    project = project_with_code(ctx, page_with(tmp_path / "q.png",
                                               barcode_image("QRCode", "Dosar 14")))
    try:
        RecognitionService(project, engine=NoTextEngine()).recognize_pages()
        a = barcode_area(project)
        assert a.barcode_value is None and a.blocks == []
    finally:
        project.close()


def test_T_X066_1_with_the_option_the_value_becomes_text(ctx, tmp_path):
    """T-X066.1: cu optiunea activa, valoarea se salveaza si apare in textul paginii."""
    ctx.settings.set("ocr.barcodes_to_text", True)
    project = project_with_code(ctx, page_with(tmp_path / "q.png",
                                               barcode_image("Code128", "Dosar-2026/14")))
    try:
        RecognitionService(project, engine=NoTextEngine()).recognize_pages()
        a = barcode_area(project)
        assert a.area_type is AreaType.BARCODE and a.barcode_value == "Dosar-2026/14"
        assert "Dosar-2026/14" in project.page(1).text
    finally:
        project.close()


def test_T_M060_1_unreadable_code_stays_an_image(ctx, tmp_path):
    """T-M060.1: zgomot in zona de cod: fara valoare, fara text, fara eroare."""
    ctx.settings.set("ocr.barcodes_to_text", True)
    noise = Image.fromarray(np.random.default_rng(1).integers(0, 255, (400, 600),
                                                              dtype=np.uint8))
    project = project_with_code(ctx, page_with(tmp_path / "z.png", noise))
    try:
        RecognitionService(project, engine=NoTextEngine()).recognize_pages()
        a = barcode_area(project)
        assert a.area_type is AreaType.BARCODE and a.barcode_value is None and a.blocks == []
    finally:
        project.close()
