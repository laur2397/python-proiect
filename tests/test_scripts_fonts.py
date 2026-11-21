"""Faza 4b, pasul 4b.4: scrieri speciale (P-070..P-075), limbile gotice
(P-076..P-079), limbile de interfata (P-107) si fonturile (P-120..P-128)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.core.context import AppContext
from app.core.fonts import (
    ARIAL_UNICODE,
    FREE_FONTS,
    FontMatcher,
    display_font,
    missing_fonts,
)
from app.core.images.preprocess import default_pipeline
from app.core.model import (
    AutoProcessMode,
    BlockData,
    LineData,
    PreprocessOp,
    Rect,
    WordData,
)
from app.core.ocr import languages
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject

# =============================================================================
# P-070..P-075: scrierile complexe
# =============================================================================


def test_T_P070_1_complex_scripts():
    assert languages.COMPLEX == {"ara", "heb", "yid", "tha", "chi_sim", "chi_tra", "jpn", "kor"}
    assert all(languages.is_rtl(c) for c in ("ara", "heb", "yid"))
    assert not languages.is_rtl("ron")


def test_T_P072_1_cjk_mixed_with_european_text():
    """T-P072.1: CJK cu text european: orientarea si impartirea se debifeaza."""
    advice = languages.cjk_advice(["jpn", "eng"])
    assert advice == {"image.correct_orientation": False, "image.split_facing_pages": False}
    assert languages.cjk_advice(["jpn"]) == {} and languages.cjk_advice(["ron", "eng"]) == {}


def spread() -> np.ndarray:
    """Doua pagini alaturate: stanga mai inchisa, dreapta mai deschisa."""
    img = np.full((200, 400), 255, np.uint8)
    img[20:180, 20:190] = 100
    img[20:180, 210:380] = 200
    return img


def test_T_P073_1_right_to_left_spread_starts_with_the_right_page():
    """T-P073.1: pentru araba, ebraica, idis, pagina din dreapta e prima."""
    split = default_pipeline().tool_for(PreprocessOp.SPLIT)
    (first, _), _ = split.apply(spread(), {"position": 200})
    (rtl_first, _), _ = split.apply(spread(), {"position": 200, "right_to_left": True})
    assert first.mean() < rtl_first.mean()  # stanga e mai inchisa
    from app.core.images.loader import LoadedImage
    from app.core.model import ColorMode
    from app.core.settings import PreprocessSettings

    described = LoadedImage(None, 400, 200, 300, 300, ColorMode.GRAY, None, False)
    settings = PreprocessSettings(split_facing_pages=True)
    chain = default_pipeline().recommended_chain(described, settings, is_photo=False,
                                                 right_to_left=True)
    assert (PreprocessOp.SPLIT, {"only_if_facing": True, "right_to_left": True}) in chain


class RtlEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        w = WordData(None, "שלום", 90.0, bbox=Rect(10, 10, 50, 20), language_code="heb")
        block = BlockData(None, lines=[LineData(None, words=[w], bbox=w.bbox)], bbox=w.bbox,
                          direction="rtl")
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=90.0,
                                 area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


def test_T_P075_1_text_direction_is_saved(tmp_path):
    """T-P075.1: directia blocului (rtl) se salveaza si se reincarca."""
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        ctx.settings.set("lang.mode", "manual")
        ctx.settings.set("lang.manual", ["heb"])
        Image.new("L", (400, 300), 255).save(tmp_path / "p.png", dpi=(300, 300))
        project = OcrProject.create(context=ctx)
        project.add_images([tmp_path / "p.png"], auto_process=AutoProcessMode.NONE)
        RecognitionService(project, engine=RtlEngine()).recognize_pages()
        project._reload_pages()
        (block,) = [b for a in project.page(1).areas for b in a.blocks]
        assert block.direction == "rtl"
        project.close()
    finally:
        ctx.close()


# =============================================================================
# P-076..P-079: limbile gotice
# =============================================================================


def test_T_P076_1_six_gothic_languages():
    assert len(languages.GOTHIC) == 6
    assert set(languages.GOTHIC.values()) == {"Old English", "Old French", "Old German",
                                              "Old Italian", "Old Spanish", "Latvian Gothic"}
    assert all(languages.get(c).models for c in languages.GOTHIC)
    assert languages.get("lav-goth").models == ("frk",)


def test_T_P079_1_gothic_only_alone():
    """T-P079.1: o limba gotica impreuna cu una moderna: avertisment."""
    assert languages.gothic_mixed(["frk", "deu"])
    assert not languages.gothic_mixed(["frk"]) and not languages.gothic_mixed(["deu"])


def test_T_P079_2_mixed_gothic_gives_a_page_warning(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        ctx.settings.set("lang.mode", "manual")
        ctx.settings.set("lang.manual", ["frk", "deu"])
        Image.new("L", (400, 300), 255).save(tmp_path / "p.png", dpi=(300, 300))
        project = OcrProject.create(context=ctx)
        project.add_images([tmp_path / "p.png"], auto_process=AutoProcessMode.NONE)
        RecognitionService(project, engine=RtlEngine()).recognize_pages()
        codes = [w.code for w in project.page(1).warnings]
        assert codes.count("GOTHIC_MIXED") == 1
        project.close()
    finally:
        ctx.close()


def test_T_P078_1_gothic_without_a_gothic_font():
    """T-P078.1: fara font gotic, textul se afiseaza in Arial, Times sau Courier."""
    assert display_font("frk", ["Times New Roman"]) == "Times New Roman"


# =============================================================================
# P-107: limbile de interfata
# =============================================================================


def test_T_P107_1_interface_languages():
    assert languages.UI_LANGUAGES[:2] == ("ro", "en")
    assert len(languages.UI_LANGUAGES) == 23  # cele 22 din original, plus romana


# =============================================================================
# P-120..P-128: fonturile
# =============================================================================


def test_T_P071_1_recommended_fonts_per_script():
    """T-P071.1 / P-124, P-125: fontul recomandat instalat se alege."""
    assert display_font("heb", ["David", "Arial"]) == "David"
    assert display_font("jpn", ["MingLiU"]) == "MingLiU"
    assert display_font("ara", [ARIAL_UNICODE, "Noto Sans Arabic"]) == ARIAL_UNICODE


def test_T_P126_1_free_font_without_microsoft_office():
    """T-P126.1: fara Arial Unicode MS (vine cu Office), fontul liber livrat."""
    assert display_font("ara", ["Noto Sans Arabic"]) == "Noto Sans Arabic"
    assert display_font("ron", ["Noto Sans"]) == "Noto Sans"
    assert set(FREE_FONTS) >= {"latin", "cyrillic", "arabic", "hebrew", "thai", "cjk"}


def test_T_P127_1_plain_text_font_setting_wins():
    assert display_font("ron", ["Liberation Serif", "Noto Sans"], "Liberation Serif") == (
        "Liberation Serif")


def test_T_P128_1_the_missing_font_is_named():
    """T-P128.1: proiectul vine de pe alt calculator; se spune ce font lipseste."""
    gone = missing_fonts(["jpn", "ron"], ["Noto Sans"], preferred="Calibri")
    assert gone["ron"] == ["Calibri"]
    assert gone["jpn"][0] == "Calibri" and "SimSun" in gone["jpn"]
    assert "Noto Sans CJK SC" in gone["jpn"]
    assert missing_fonts(["ron"], ["Noto Sans"]) == {}


def test_installed_fonts_list():
    assert FontMatcher(["Arial"]).installed_fonts() == ["Arial"]
    assert isinstance(FontMatcher().installed_fonts(), list)
