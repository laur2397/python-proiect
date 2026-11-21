"""Teste pentru LayoutAnalyzer si analiza paginilor (faza 4, pasul 4.2)."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.layout.analyzer import LayoutAnalyzer
from app.core.layout.areas import AreaEditor
from app.core.model import AreaType, AutoProcessMode, ColorMode, PageData, PageStatus
from app.core.ocr.engine import find_tesseract
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import OcrSettings

T = AreaType
FONTS = ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
FONT = next((f for f in FONTS if Path(f).is_file()), None)
W, H = 1240, 1754  # A4 la 150 dpi


def font(size=17):
    return ImageFont.truetype(FONT, size) if FONT else ImageFont.load_default(size=size)


def layout_page(path: Path) -> Path:
    """Doua coloane de text, o fotografie, un tabel cu linii, text jos."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    for x in (75, 650):
        for i in range(14):
            d.text((x, 150 + i * 25), "Cerere de finantare pentru proiectul", fill="black",
                   font=font())
    photo = np.random.default_rng(0).integers(0, 255, (350, 500, 3), dtype=np.uint8)
    img.paste(Image.fromarray(photo), (75, 600))
    for r in range(5):
        d.line((650, 600 + r * 60, 1150, 600 + r * 60), fill="black", width=2)
    for c in range(4):
        d.line((650 + c * 166, 600, 650 + c * 166, 840), fill="black", width=2)
    for i in range(6):
        d.text((75, 1100 + i * 25), "Semnatura si stampila beneficiarului", fill="black",
               font=font())
    img.save(path, dpi=(150, 150))
    return path


def page_of(path: Path) -> PageData:
    with Image.open(path) as im:
        w, h = im.size
    return PageData(1, 1, path, path, w, h, 150, 150, ColorMode.COLOR)


# =============================================================================
# N-006: zonele gasite automat
# =============================================================================


def test_T_N006_1_zones_are_found(tmp_path):
    """T-N006.1: textul, imaginea si tabelul, numerotate pe coloane (M-022)."""
    zones = LayoutAnalyzer().analyze(page_of(layout_page(tmp_path / "p.png")), OcrSettings())
    kinds = [z.area_type for z in zones]
    assert kinds.count(T.TEXT) == 3 and kinds.count(T.PICTURE) == 1 and kinds.count(T.TABLE) == 1
    # coloana stanga (text, imagine, text de jos), apoi coloana dreapta (text, tabel)
    assert kinds == [T.TEXT, T.PICTURE, T.TEXT, T.TEXT, T.TABLE]
    picture = zones[1].bbox
    assert abs(picture.x - 75) <= 15 and abs(picture.w - 500) <= 30
    table = zones[4].bbox
    assert abs(table.x - 650) <= 15 and abs(table.right - 1150) <= 15


def test_blank_page_has_no_zones(tmp_path):
    path = tmp_path / "gol.png"
    Image.new("L", (W, H), 255).save(path)
    assert LayoutAnalyzer().analyze(page_of(path), OcrSettings()) == []


def test_template_zones_are_used_instead_of_detection(tmp_path):
    page = page_of(layout_page(tmp_path / "p.png"))
    from app.core.layout.areas import rect_polygon
    from app.core.model import AreaData, Rect
    tpl = [AreaData(None, T.TEXT, rect_polygon(Rect(10, 10, 100, 100)), 0,
                    bbox=Rect(10, 10, 100, 100))]
    zones = LayoutAnalyzer().analyze(page, OcrSettings(), template=tpl)
    assert [z.bbox for z in zones] == [Rect(10, 10, 100, 100)]


# =============================================================================
# N-006, N-007 in proiect
# =============================================================================


@pytest.fixture
def project(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    p = OcrProject.create(context=ctx)
    p.add_images([layout_page(tmp_path / "a.png"), layout_page(tmp_path / "b.png")],
                 auto_process=AutoProcessMode.NONE)
    yield p
    p.close()
    ctx.close()


def test_T_N007_1_analyze_all_pages(project):
    """T-N007.1: toate paginile se analizeaza; statusul devine analyzed."""
    project.analyze_pages([1, 2])
    for n in (1, 2):
        page = project.page(n)
        assert len(page.areas) == 5 and page.status is PageStatus.ANALYZED
        assert [a.order_index for a in page.areas] == [0, 1, 2, 3, 4]
    assert project.undo_description() == "undo.analyze_pages"
    project.undo()
    assert project.page(1).areas == [] and project.page(1).status is PageStatus.IMPORTED


def test_user_zones_are_kept_and_gaps_filled(project):
    """SPEC_05: zonele facute de utilizator nu se suprascriu."""
    mine = AreaEditor(project).create(project.page(1), [(60, 140), (600, 140), (600, 520),
                                                        (60, 520)], T.TABLE)
    project.analyze_pages([1])
    areas = project.page(1).areas
    assert any(a.id == mine.id and a.area_type is T.TABLE for a in areas)
    assert len(areas) == 5  # coloana stanga de sus nu s-a mai adaugat ca text


# =============================================================================
# X-017: orientarea (cu Tesseract)
# =============================================================================

needs_ocr = pytest.mark.skipif(
    find_tesseract() is None and os.environ.get("DOCULENS_REQUIRE_OCR") != "1",
    reason="Tesseract nu e instalat")


@needs_ocr
def test_T_X017_1_orientation_is_detected_and_fixed(project, tmp_path):
    """T-X017.1: o pagina culcata se detecteaza; rotita, devine dreapta."""
    analyzer = LayoutAnalyzer()
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    for i in range(25):
        d.text((80, 100 + i * 45), "Societatea isi desfasoara activitatea in domeniul",
               fill=0, font=font(28))
    path = tmp_path / "culcat.png"
    img.rotate(90, expand=True).save(path, dpi=(150, 150))
    project.add_images([path], auto_process=AutoProcessMode.NONE)
    turn = analyzer.detect_orientation(project.page(3))
    assert turn in (90, 270)
    project.rotate_pages([3], turn)
    assert analyzer.detect_orientation(project.page(3)) == 0


@needs_ocr
def test_page_without_text_keeps_its_rotation(tmp_path):
    path = tmp_path / "gol.png"
    Image.new("L", (W, H), 255).save(path)
    page = page_of(path)
    page.rotation = 180
    assert LayoutAnalyzer().detect_orientation(page) == 180


# =============================================================================
# Defectele de la testul manual din 21.11.2026 (docs/plan/STARE.md)
# =============================================================================


def scan_page(path: Path, *, line_w=2, gray=0, skew=0.0, stamp=False, pen=False) -> Path:
    """O scanare A4 la 300 dpi: un paragraf, un tabel cu chenar (5 x 3),
    optional o stampila rotunda si o linie de pix."""
    img = Image.new("L", (2480, 3508), 255)
    d = ImageDraw.Draw(img)
    for i in range(8):
        d.text((200, 300 + i * 60), f"Text de paragraf pentru dosarul de finantare nr. {i}",
               fill=0, font=font(42))
    xs, ys = [200, 800, 1400, 2280], [1000 + 110 * i for i in range(6)]
    for x in xs:
        d.line([(x, ys[0]), (x, ys[-1])], fill=gray, width=line_w)
    for y in ys:
        d.line([(xs[0], y), (xs[-1], y)], fill=gray, width=line_w)
    for r in range(5):
        for c in range(3):
            d.text((xs[c] + 30, ys[r] + 30), f"celula {r}{c}", fill=0, font=font(42))
    if stamp:
        d.ellipse([1600, 2400, 2050, 2850], outline=0, width=8)
        d.ellipse([1660, 2460, 1990, 2790], outline=0, width=4)
        d.text((1700, 2600), "STAMPILA SRL", fill=0, font=font(34))
    if pen:
        d.line([(300, 2700), (700, 2650), (1100, 2720), (1300, 2680)], fill=0, width=5)
    if skew:
        img = img.rotate(skew, resample=Image.Resampling.BICUBIC, fillcolor=255)
    img.save(path, dpi=(300, 300))
    return path


def kinds(path: Path) -> list[str]:
    page = page_of(path)
    return sorted(a.area_type.value for a in LayoutAnalyzer().analyze(page, OcrSettings()))


@pytest.mark.parametrize("variant", [
    {"line_w": 1}, {"line_w": 1, "gray": 120}, {"line_w": 2, "gray": 150},
    {"skew": 0.3}, {"skew": 0.7}, {"skew": 1.5}, {"line_w": 1, "skew": 0.5},
])
def test_T_N006_2_bordered_table_on_a_clean_scan_is_found(tmp_path, variant):
    """T-N006.2: tabelul cu chenar subtire, gri sau usor inclinat devine o zona
    Tabel, iar liniile lui nu ajung in zonele de text."""
    found = kinds(scan_page(tmp_path / "s.png", **variant))
    assert found == ["table", "text"], (variant, found)


def test_T_N006_3_stamp_and_pen_line_are_pictures(tmp_path):
    """T-N006.3: o stampila rotunda si o linie de pix sunt zone Imagine, cate
    una fiecare, nu zone Text."""
    path = scan_page(tmp_path / "s.png", stamp=True, pen=True)
    page = page_of(path)
    areas = LayoutAnalyzer().analyze(page, OcrSettings())
    pictures = sorted((a.bbox for a in areas if a.area_type is AreaType.PICTURE),
                      key=lambda r: r.x)
    assert len(pictures) == 2 and sorted(a.area_type.value for a in areas).count("text") == 1
    pen, stamp = pictures
    assert pen.x <= 300 and pen.right >= 1300 and pen.h < 200
    assert stamp.x <= 1600 and stamp.right >= 2050 and stamp.y <= 2400 and stamp.bottom >= 2850


def test_T_M040_3_gray_lines_give_the_table_structure(tmp_path):
    """T-M040.3: liniile gri ale tabelului dau randurile si coloanele."""
    from app.core.layout.tables import TableAnalyzer
    from app.core.model import AreaData, Rect

    path = scan_page(tmp_path / "s.png", gray=150)
    page = page_of(path)
    box = Rect(190, 990, 2100, 570)
    table = TableAnalyzer().analyze_structure(AreaData(1, AreaType.TABLE, [], 0, bbox=box), page)
    assert (table.rows, table.cols) == (5, 3) and page.warnings == []
