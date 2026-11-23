"""Limbile si sabloanele: cerintele P fara test pana acum: limbile alese manual
(P-003, P-074), lista limbilor (P-007, P-111), asteriscul dictionarului (P-103),
limbajele formale in plus (P-106), scrierile gotice (P-077), romana (P-109),
interfata localizata (P-108), grupele de fonturi (P-121…P-123) si antrenarea
caracter cu caracter, cu `Back` (P-055, P-057)."""

from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.fonts import ARIAL_UNICODE, LUCIDA_GROUP, RECOMMENDED
from app.core.model import AutoProcessMode, BlockData, LineData, Rect, WordData
from app.core.ocr import languages
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.languages import LanguageRegistry
from app.core.ocr.patterns import PatternStore, glyph_boxes
from app.core.ocr.store import save_result
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui import i18n
from app.gui.i18n import tr


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_P003_P074_more_languages_opens_manual_selection(qtbot, ctx, monkeypatch):
    from app.gui.main_window import MainWindow

    project = OcrProject.create(context=ctx)
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    opened = []
    monkeypatch.setattr(MainWindow, "open_options", lambda self, tab="general": opened.append(tab))
    combo = window.language_combo
    last = combo.count() - 1
    assert combo.itemText(last) == tr("action.more_languages")
    window._language_chosen(last)  # `More languages...` -> `Specify OCR languages manually`
    assert opened == ["languages"]
    window._language_chosen(0)
    assert project.settings().get("lang.mode") == "manual"  # recunoasterea amestecata
    project.close()


def test_T_P007_P111_language_list_visible_in_product(qtbot, ctx):
    from app.gui.about_dialog import AboutDialog

    about = AboutDialog(ctx)
    qtbot.addWidget(about)
    text = about.show_license_info().text.toPlainText()
    assert tr("about.languages.natural", n=len(LanguageRegistry().by_category(
        languages.NATURAL))) in text


def test_T_P103_dictionary_languages_marked_with_asterisk(qtbot, ctx):
    from app.gui.about_dialog import LicenseInfoDialog

    dialog = LicenseInfoDialog()
    qtbot.addWidget(dialog)
    lines = dialog.text.toPlainText().splitlines()
    assert any(line.strip().endswith("*") for line in lines)
    assert tr("about.languages.dictionary_note") in lines


def test_T_P106_phonetic_and_chemical_formal_languages():
    formal = set(LanguageRegistry().by_category(languages.FORMAL))
    assert {"phonetic-en", "chem"} <= formal


def test_T_P077_gothic_scripts_documented():
    from pathlib import Path

    assert len(languages.GOTHIC) == 6  # o limba gotica per tip de text gotic
    source = Path(languages.__file__).read_text(encoding="utf-8")
    assert all(name in source for name in ("Textur/Textualis", "Fraktur", "Schwabacher"))


def test_T_P108_localized_interface_languages():
    assert {"ro", "en"} <= set(i18n.LANGUAGES)  # romana si engleza obligatorii
    assert {"ro", "en"} <= set(languages.UI_LANGUAGES)


def test_T_P109_romanian_and_romanian_moldavia():
    assert LanguageRegistry().is_builtin("ron-MD") and languages.get("ron-MD").models == (
        "ron",)


def test_T_P121_P122_P123_font_groups():
    for code in ("ara", "hye", "vie", "yid", "tha"):  # P-121: numai Arial Unicode MS
        assert RECOMMENDED[code] == (ARIAL_UNICODE,)
    assert LUCIDA_GROUP == (ARIAL_UNICODE, "Lucida Sans Unicode")  # P-122
    assert RECOMMENDED["tgk"] == (ARIAL_UNICODE, "Palatino Linotype")  # P-123


# --- antrenarea (P-055, P-057) ---------------------------------------------------------


def _word_page(tmp_path):
    img = Image.new("L", (600, 200), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=60)
    draw.text((40, 60), "ab", fill=0, font=font)
    draw.text((300, 60), "cde", fill=0, font=font)
    img.save(tmp_path / "p.png", dpi=(300, 300))
    return tmp_path / "p.png"


def test_T_P057_glyph_boxes_split_a_word():
    img = np.full((60, 200), 255, np.uint8)
    img[10:50, 10:30] = 0
    img[10:50, 50:70] = 0
    img[2:6, 55:65] = 0  # punctul literei: acelasi caracter
    boxes = glyph_boxes(img, Rect(0, 0, 200, 60))
    assert [(b.x, b.w) for b in boxes] == [(10, 20), (50, 20)]


def test_T_P055_P057_training_dialog_back_within_the_word(qtbot, ctx, tmp_path):
    from app.gui.editor_tools import PatternTrainingDialog

    project = OcrProject.create(context=ctx)
    project.add_images([_word_page(tmp_path)], auto_process=AutoProcessMode.NONE)
    words = [WordData(None, "ab", 90.0, bbox=Rect(30, 50, 120, 90)),
             WordData(None, "cde", 90.0, bbox=Rect(290, 50, 200, 90))]
    block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(30, 50, 460, 90))],
                      bbox=Rect(30, 50, 460, 90))
    save_result(project, 1, RecognitionResult(1, blocks=[block], avg_confidence=90.0,
                                              area_blocks={None: [block]}))
    store = PatternStore(ctx.app_db)
    store.create_set("Test")
    dialog = PatternTrainingDialog(ctx, project.page(1), "Test")
    qtbot.addWidget(dialog)
    assert [len(w) for w in dialog.words] == [2, 3]
    assert not dialog.buttons["back"].isEnabled()  # primul caracter al cuvantului
    dialog.character.setText("a")
    dialog.effects["bold"].setChecked(True)
    assert dialog.train()  # P-056: cu efectul bifat
    assert dialog.buttons["back"].isEnabled()
    dialog.back()  # P-057: caracterul anterior, in acelasi cuvant
    assert (dialog.word_index, dialog.char_index) == (0, 0)
    dialog.skip()
    dialog.skip()  # trece la al doilea cuvant
    assert (dialog.word_index, dialog.char_index) == (1, 0)
    assert not dialog.buttons["back"].isEnabled()  # nu se intoarce in cuvantul anterior
    (char,) = store.characters("Test")
    assert char.character == "a"
    project.close()


def test_T_P055_training_button_in_image_panel(qtbot, ctx, tmp_path):
    from app.gui.main_window import MainWindow

    project = OcrProject.create(context=ctx)
    project.add_images([_word_page(tmp_path)], auto_process=AutoProcessMode.NONE)
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    window.refresh()
    messages = []
    window.show_message = messages.append
    window.image_panel.actions["train_patterns"].trigger()
    assert messages == [tr("training.no_active_set")]  # fara sablon activ
    store = PatternStore(ctx.app_db)
    store.create_set("Activ")
    store.set_active("Activ")
    window.image_panel.actions["train_patterns"].trigger()
    assert window.training_dialog.set_name == "Activ"
    window.training_dialog.close()
    project.close()
