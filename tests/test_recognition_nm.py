"""Recunoasterea (N) si zonele (M) fara test pana acum: pornirea manuala
(N-002), viteza si tipul de document (N-014…N-017, N-101, N-102), orientarea,
inclinarea si paginile alaturate (N-105…N-107), scrierile complexe, CJK si
gotice (N-108…N-110); tipurile si proprietatile zonelor (M-002, M-004, M-005,
M-025…M-027, M-055), desenul lor (M-103, M-109) si stergerea imaginilor
(M-112)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.export.base import ExportOptions
from app.core.export.docmodel import Picture, build_document
from app.core.images import preprocess
from app.core.images.preprocess import SplitTool, detect_skew, rotate_fill
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    AutoProcessMode,
    BlockData,
    LayoutMode,
    LineData,
    OcrQuality,
    Orientation,
    PageStatus,
    PreprocessOp,
    PrintType,
    Rect,
    WordData,
)
from app.core.ocr import engine as engine_mod
from app.core.ocr import languages
from app.core.ocr.engine import RecognitionResult, TesseractEngine, find_tesseract
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import OcrSettings, definition

ROOT = Path(__file__).resolve().parents[1]
FONTS = ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
FONT = next((f for f in FONTS if Path(f).is_file()), None)
needs_ocr = pytest.mark.skipif(
    find_tesseract() is None or FONT is None, reason="Tesseract sau fontul lipsesc")


class FakeEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        words = [WordData(None, "Cerere", 95.0, bbox=Rect(10, 10, 80, 20))]
        block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 80, 20))],
                          bbox=Rect(10, 10, 80, 20))
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    Image.new("L", (600, 400), 255).save(tmp_path / "p1.png", dpi=(300, 300))
    p = OcrProject.create(context=ctx)
    p.add_images([tmp_path / "p1.png"], auto_process=AutoProcessMode.NONE)
    AreaEditor(p).create(p.page(1), [(5, 5), (300, 5), (300, 60), (5, 60)], AreaType.TEXT)
    yield p
    p.close()


def recognized(project):
    RecognitionService(project, engine=FakeEngine()).recognize_pages()
    assert project.page(1).status is PageStatus.RECOGNIZED


# --- N-002 ----------------------------------------------------------------------------


def test_T_N002_when_recognition_must_be_started_manually(project, ctx):
    """Fara recunoastere automata paginile raman nerecunoscute; dupa zone noi,
    alte limbi, alte optiuni OCR sau alte fonturi, recunoasterea se reia manual."""
    assert project.page(1).status is not PageStatus.RECOGNIZED  # auto_process NONE
    recognized(project)
    AreaEditor(project).create(project.page(1), [(320, 100), (500, 100), (500, 200),
                                                 (320, 200)], AreaType.TEXT)
    assert project.page(1).status is not PageStatus.RECOGNIZED  # zona desenata (N-026)
    assert list(project.languages) != ["deu"]
    for change in (lambda: setattr(project, "languages", ["deu"]),
                   lambda: project.settings().set("ocr.detect_footnotes", False),
                   lambda: project.settings().set("ocr.export_fonts", ["Arial"])):
        recognized(project)
        change()
        assert project.page(1).status is PageStatus.ANALYZED


# --- N-014…N-017, N-101, N-102 --------------------------------------------------------


def test_T_N014_fast_recognition_treats_areas_as_one_block():
    assert "--psm 6" in engine_mod._config(OcrSettings(quality=OcrQuality.FAST))
    assert "--psm 3" in engine_mod._config(OcrSettings(quality=OcrQuality.THOROUGH))


def test_T_N015_N101_document_type_auto_by_default():
    assert definition("ocr.document_type").default == "auto"
    assert OcrSettings().print_type is PrintType.AUTO
    assert set(definition("ocr.document_type").allowed) == {"auto", "typewriter", "fax"}


def test_T_N016_typewriter_returns_to_auto_after_use(project):
    project.settings().set("ocr.document_type", "typewriter")
    recognized(project)
    assert project.settings().get("ocr.document_type") == "auto"
    assert project.page(1).status is PageStatus.RECOGNIZED  # textul ramane valabil
    project.settings().set("ocr.document_type", "fax")
    recognized(project)
    assert project.settings().get("ocr.document_type") == "fax"  # numai Typewriter


def test_T_N017_N101_fax_removes_noise():
    rng = np.random.default_rng(1)
    noisy = np.full((80, 80), 255, np.uint8)
    noisy[rng.random((80, 80)) < 0.05] = 0  # puncte izolate
    image = Image.fromarray(noisy)
    cleaned = np.asarray(engine_mod._prepare(image, PrintType.FAX, False))
    assert (cleaned < 128).sum() < (noisy < 128).sum() / 5
    same = np.asarray(engine_mod._prepare(image, PrintType.AUTO, False))
    assert (same == noisy).all()


def test_T_N102_thin_or_thick_print_has_brightness_and_gray_tools():
    assert PreprocessOp.BRIGHTNESS_CONTRAST in preprocess.default_pipeline().ops
    assert PreprocessOp.LEVELS in preprocess.default_pipeline().ops
    color = np.zeros((10, 10, 3), np.uint8)
    assert preprocess.to_gray(color).ndim == 2  # trecerea pe gri


# --- N-105…N-107 ----------------------------------------------------------------------


def _text_image(lines=20, size=(1240, 900)):
    img = Image.new("L", size, 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 28) if FONT else ImageFont.load_default()
    for i in range(lines):
        draw.text((60, 40 + i * 42), "Societatea isi desfasoara activitatea in domeniul",
                  fill=0, font=font)
    return img


@needs_ocr
def test_T_N105_orientation_detected_blank_page_unchanged():
    from app.core.layout.analyzer import osd_rotation

    assert osd_rotation(_text_image().rotate(180)) == 180
    assert osd_rotation(_text_image()) == 0
    assert osd_rotation(Image.new("L", (800, 1000), 255)) is None  # fara text: neschimbata


def test_T_N106_skew_detected_button_only_on_skewed_pages():
    from app.gui import image_panel

    straight = np.asarray(_text_image(), dtype=np.uint8)
    assert abs(detect_skew(straight)) < image_panel.SKEW_BUTTON_ANGLE
    skewed = rotate_fill(straight, 3.0)
    assert abs(detect_skew(skewed)) >= image_panel.SKEW_BUTTON_ANGLE


def _facing() -> np.ndarray:
    left = _text_image(lines=18, size=(700, 900))
    page = Image.new("L", (1500, 900), 255)
    page.paste(left, (0, 0))
    page.paste(left, (800, 0))
    return np.asarray(page, dtype=np.uint8)


def test_T_N107_facing_pages_split_but_not_when_upside_down(monkeypatch):
    from app.core.layout import analyzer

    tool = SplitTool()
    image = _facing()
    monkeypatch.setattr(analyzer, "osd_rotation", lambda img: 0)
    parts, meta = tool.apply(image, {"only_if_facing": True})
    assert meta["pages"] == 2 and len(parts) == 2
    monkeypatch.setattr(analyzer, "osd_rotation", lambda img: 180)
    parts, meta = tool.apply(image, {"only_if_facing": True})
    assert meta == {"pages": 1, "upside_down": True} and len(parts) == 1
    parts, meta = tool.apply(image, {})  # impartirea manuala ramane posibila
    assert meta["pages"] == 2


# --- N-108…N-110 ----------------------------------------------------------------------


def test_T_N108_complex_scripts_need_fonts():
    from app.core.fonts import missing_fonts

    assert {"ara", "heb", "yid", "tha", "chi_sim", "chi_tra", "jpn", "kor"} == \
        set(languages.COMPLEX)
    assert missing_fonts(["ara"], installed=["Times New Roman"])  # fontul lipseste
    assert not missing_fonts(["ron"], installed=["Noto Sans"])


def test_T_N109_mixed_cjk_and_european_disable_orientation_and_split():
    assert languages.cjk_advice(["jpn", "eng"]) == {"image.correct_orientation": False,
                                                   "image.split_facing_pages": False}
    assert languages.cjk_advice(["jpn"]) == {} and languages.cjk_advice(["ron"]) == {}


def test_T_N110_gothic_only_alone(project):
    assert languages.gothic_mixed(["frk", "deu"]) and not languages.gothic_mixed(["frk"])
    service = RecognitionService(project, engine=FakeEngine())
    warnings = service._warnings(project.page(1), OcrSettings(languages=("frk", "deu")))
    assert any(w.code == "GOTHIC_MIXED" for w in warnings)


# --- M --------------------------------------------------------------------------------


def test_T_M002_M004_M005_area_types_and_shortcuts():
    from app.gui.main_window import SHORTCUTS

    assert SHORTCUTS["area_type_text"] == "Ctrl+2"
    assert SHORTCUTS["area_type_picture"] == "Ctrl+4"
    assert SHORTCUTS["area_type_barcode"] == "Ctrl+5"
    assert engine_mod._TEXT_AREAS == (AreaType.TEXT, AreaType.RECOGNITION)  # numai textul


def test_T_M004_picture_area_is_not_recognized(project):
    page = project.page(1)
    AreaEditor(project).create(page, [(320, 100), (500, 100), (500, 300), (320, 300)],
                               AreaType.PICTURE)
    picture = next(a for a in project.page(1).areas if a.area_type is AreaType.PICTURE)
    with pytest.raises(ValueError):
        RecognitionService(project, engine=FakeEngine()).recognize_area_again(1, picture.id)


def test_T_M055_barcodes_off_by_default():
    assert definition("ocr.barcodes_to_text").default is False
    assert OcrSettings().convert_barcodes_to_text is False


def test_T_M025_rotated_box_maps_back():
    box = Rect(10, 20, 30, 40)  # in decupajul rotit cu 90 de grade (100 x 60 -> 60 x 100)
    back = engine_mod.unrotate_rect(box, 90, (100, 60))
    assert back == Rect(100 - 60, 10, 40, 30)
    for turn in (90, 180, 270):
        inside = engine_mod.unrotate_rect(Rect(0, 0, 5, 5), turn, (100, 60))
        assert 0 <= inside.x <= 100 and 0 <= inside.y <= 60
    assert engine_mod.unrotate_rect(box, 0, (100, 60)) == box


@needs_ocr
def test_T_M025_area_orientation_text_is_read_rotated(project, tmp_path):
    img = Image.new("L", (1400, 300), 255)
    ImageDraw.Draw(img).text((40, 100), "Cerere de finantare", fill=0,
                             font=ImageFont.truetype(FONT, 60))
    rotated = img.rotate(-90, expand=True)  # textul culcat in sensul acelor
    canvas = Image.new("L", (900, 1600), 255)
    canvas.paste(rotated, (100, 100))
    canvas.save(tmp_path / "rotit.png", dpi=(300, 300))
    project.add_images([tmp_path / "rotit.png"], auto_process=AutoProcessMode.NONE)
    page = project.page(2)
    area = AreaEditor(project).create(page, [(100, 100), (400, 100), (400, 1500),
                                             (100, 1500)], AreaType.TEXT)
    area.orientation = Orientation.DEG_90
    result = TesseractEngine().recognize_area(page, area, OcrSettings(languages=("ron",)))
    words = [w for b in result.blocks for line in b.lines for w in line.words]
    assert "Cerere" in " ".join(w.text for w in words)
    for w in words:  # casetele sunt in pagina, in zona
        assert 90 <= w.bbox.x and w.bbox.right <= 410 and 90 <= w.bbox.y <= 1510


def test_T_M026_M027_area_print_type_and_inversion(monkeypatch, project):
    seen = []
    monkeypatch.setattr(engine_mod, "_prepare", lambda image, kind, inverted: (
        seen.append((kind, inverted)), image)[1])
    monkeypatch.setattr(TesseractEngine, "_check_languages", lambda self, langs: None)
    monkeypatch.setattr(TesseractEngine, "_run", lambda self, *a, **k: [])
    engine = TesseractEngine.__new__(TesseractEngine)
    engine.cmd = Path("tesseract")
    engine.registry = None
    area = project.page(1).areas[0]
    area.print_type = PrintType.FAX
    area.is_inverted = True
    engine.recognize_area(project.page(1), area, OcrSettings(languages=("ron",)))
    assert seen[-1] == (PrintType.FAX, True)
    area.print_type = PrintType.AUTO  # zona pe Auto: tipul din Options
    engine.recognize_area(project.page(1), area,
                          OcrSettings(languages=("ron",), print_type=PrintType.TYPEWRITER))
    assert seen[-1][0] is PrintType.TYPEWRITER


def test_T_M103_M109_number_top_left_and_table_grid():
    source = (ROOT / "app" / "gui" / "image_panel.py").read_text(encoding="utf-8")
    assert "box = QRectF(area.bbox.x, area.bbox.y, side, side)" in source  # stanga-sus
    assert "cell.id in self.selected_cells" in source  # celula aleasa, evidentiata


def test_T_M109_selected_cell_follows_the_text(qtbot, ctx, project):
    from app.gui.main_window import MainWindow

    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    window.text_panel.cells[77] = (None, type("Cell", (), {"id": 5})())
    word = WordData(77, "x", 90.0, bbox=Rect(10, 10, 20, 10))
    window._word_selected(word)
    assert window.image_view.selected_cells == {5}


def test_T_M112_deleting_a_picture_area_removes_it_from_the_document(project):
    page = project.page(1)
    AreaEditor(project).create(page, [(320, 100), (500, 100), (500, 300), (320, 300)],
                               AreaType.PICTURE)
    options = ExportOptions(layout_mode=LayoutMode.EDITABLE)

    def pictures():
        doc = build_document([project.page(1)], options)
        return [i for p in doc.pages for i in p.body if isinstance(i, Picture)]

    assert len(pictures()) == 1
    picture = next(a for a in project.page(1).areas if a.area_type is AreaType.PICTURE)
    AreaEditor(project).delete(project.page(1), [picture])
    assert pictures() == []
