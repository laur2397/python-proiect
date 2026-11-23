"""Faza 15, pasul 15.1: nucleul Screenshot Reader (V-002…V-026)."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageFont
from test_automated_tasks import ScriptEngine

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.core.screenshot import (
    CAPTURE_MODES,
    MIN_SIZE,
    SEND_TARGETS,
    TIMED_DELAY_S,
    ScreenshotReader,
    rows_to_tsv,
)


class FakeGrabber:
    """Doua monitoare alaturate, 800×600 fiecare, cu text pe primul."""

    def __init__(self):
        self.desktop = Image.new("RGB", (1600, 600), "white")
        draw = ImageDraw.Draw(self.desktop)
        font = ImageFont.load_default(size=28)
        for row in range(4):
            draw.text((40, 40 + row * 40), "Cererea de plata nr. 12", fill="black", font=font)
        self.grabbed = []

    def screens(self):
        return [Rect(0, 0, 800, 600), Rect(800, 0, 800, 600)]

    def grab(self, rect):
        self.grabbed.append(rect)
        return self.desktop.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h))

    def window_rect(self, window_id):
        return Rect(20, 20, 400, 200)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def reader(ctx):
    slept = []
    r = ScreenshotReader(ctx, FakeGrabber(), engine=ScriptEngine(), sleep=slept.append)
    r.slept = slept
    return r


def test_T_V003_area_minimum_and_V026_repeat(reader):
    assert reader.last_region() is None  # V-026: butonul e gri
    with pytest.raises(ValueError):
        reader.repeat_last()
    with pytest.raises(ValueError):
        reader.capture_area(Rect(0, 0, MIN_SIZE - 1, 50))
    image = reader.capture_area(Rect(30, 30, 300, 100))
    assert (image.width_px, image.height_px) == (900, 300)  # marita de 3 ori pentru OCR
    assert reader.last_region() == Rect(30, 30, 300, 100)
    again = reader.repeat_last()
    assert again.path != image.path and reader._grabber.grabbed[-1] == Rect(30, 30, 300, 100)


def test_T_V004_V005_V025_window_screen_and_monitors(reader):
    assert reader.capture_window(7).width_px == 400 * 3
    whole = reader.capture_screen()
    assert reader.last_region() == Rect(0, 0, 1600, 600)  # V-025: ambele monitoare
    assert whole.width_px == 1600 * 3
    reader.capture_screen(display=1)
    assert reader.last_region() == Rect(800, 0, 800, 600)
    reader.capture_area(Rect(700, 10, 200, 50))  # zona peste doua monitoare
    assert reader._grabber.grabbed[-1] == Rect(700, 10, 200, 50)


def test_T_V006_timed_screen_fixed_five_seconds(reader):
    assert TIMED_DELAY_S == 5
    reader.capture_timed()
    assert reader.slept == [5]
    with pytest.raises(ValueError):
        reader.capture_timed(0)


def test_T_V010_V013_V015_text(reader, tmp_path):
    image = reader.capture_area(Rect(30, 30, 500, 200))
    text = reader.to_text(image, ["ron"])
    assert "captura_001" in text  # motorul fals citeste numele fisierului
    path = reader.text_to_file(image, ["ron"], tmp_path / "text.docx")
    from docx import Document

    assert "captura_001" in "\n".join(p.text for p in Document(path).paragraphs)
    with pytest.raises(ValueError):
        reader.text_to_file(image, ["ron"], tmp_path / "text.xyz")
    with pytest.raises(ValueError):
        reader.to_text(image, [])


def test_T_V011_V014_V016_table(reader, tmp_path):
    image = reader.capture_area(Rect(30, 30, 500, 200))
    rows = reader.to_table(image, ["ron"])
    assert rows and any("captura_001" in cell for row in rows for cell in row)
    assert rows_to_tsv([["a", "b"], ["c", "d\te"]]) == "a\tb\nc\td e"
    path = reader.table_to_file(image, ["ron"], tmp_path / "tabel.xlsx")
    from openpyxl import load_workbook

    values = [c.value for row in load_workbook(path).active.iter_rows() for c in row]
    assert any(v and "captura_001" in str(v) for v in values)
    with pytest.raises(ValueError):
        reader.table_to_file(image, ["ron"], tmp_path / "tabel.docx")


def test_T_V017_V019_image_files(reader, tmp_path):
    image = reader.capture_area(Rect(30, 30, 300, 100))
    png = reader.image_to_file(image, tmp_path / "zona.png")
    with Image.open(png) as img:
        assert img.size == (300, 100)  # marimea de pe ecran
    bmp = reader.image_for_email(image)
    with Image.open(bmp) as img:
        assert img.format == "BMP"  # V-019
    with pytest.raises(ValueError):
        reader.image_to_file(image, tmp_path / "zona.pdf")


def test_T_V002_V101_lists():
    assert CAPTURE_MODES == ("area", "window", "screen", "timed")
    assert len(SEND_TARGETS) == 10 and SEND_TARGETS[-2:] == ("image_ocr_editor",
                                                              "image_email")
