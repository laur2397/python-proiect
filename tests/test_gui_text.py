"""Faza 6b, pasul 6b.3a: panoul Text (O-020, O-021, O-024, O-025, O-028,
O-029, O-060…O-064, O-100, O-101, O-103…O-105, J-417)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QToolBar

from app.core.context import AppContext
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    AutoProcessMode,
    BlockData,
    LineData,
    PageStatus,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.gui.main_window import MainWindow
from app.gui.text_panel import WORD_ID, collect_words

WORDS = [("Cerere", False), ("finanțare", True), ("nr.", False), ("4S21", True)]


class ScriptEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        words = [WordData(None, t, 40.0 if u else 95.0, bbox=Rect(10 + 90 * i, 10, 80, 20),
                          is_uncertain=u, language_code="ron",
                          char_confidences=tuple(30.0 if (u and k == 1) else 95.0
                                                 for k in range(len(t))))
                 for i, (t, u) in enumerate(WORDS)]
        block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 400, 20))],
                          bbox=Rect(10, 10, 400, 20))
        second = BlockData(None, lines=[LineData(None, words=[
            WordData(None, "Brașov", 95.0, bbox=Rect(10, 110, 80, 20), language_code="ron")],
            bbox=Rect(10, 110, 80, 20))], bbox=Rect(10, 110, 80, 20))
        areas = sorted(page.areas, key=lambda a: a.order_index)
        return RecognitionResult(page.page_number, blocks=[block, second], avg_confidence=70.0,
                                 area_blocks={areas[0].id: [block], areas[1].id: [second]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (800, 400), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    project = OcrProject.create(context=ctx)
    project.add_images(paths, auto_process=AutoProcessMode.NONE)
    ed = AreaEditor(project)
    ed.create(project.page(1), [(5, 5), (450, 5), (450, 40), (5, 40)], AreaType.TEXT)
    ed.create(project.page(1), [(5, 100), (450, 100), (450, 140), (5, 140)], AreaType.TEXT)
    RecognitionService(project, engine=ScriptEngine()).recognize_pages([1])
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.resize(1400, 1000)
    w.show()
    yield w
    w.hide()
    project.close()


def words(window):
    return list(window.project.page(window.current).iter_words())


def put_cursor(panel, text, offset=0):
    doc = panel.view.document()
    found = doc.find(text)
    assert not found.isNull(), text
    cursor = QTextCursor(doc)
    cursor.setPosition(found.selectionStart() + offset)
    panel.view.setTextCursor(cursor)


def select(panel, text):
    panel.view.setTextCursor(panel.view.document().find(text))


# =============================================================================
# Afisarea
# =============================================================================


def test_T_O103_1_unrecognized_page_is_empty_and_read_only(window):
    window.go_to_page(2)
    panel = window.text_panel
    assert panel.view.toPlainText() == "" and panel.view.isReadOnly()
    assert panel.view.placeholderText() == "Pagina nu e recunoscută"


def test_page_text_is_shown_with_romanian_letters(window):
    text = window.text_panel.view.toPlainText()
    assert "Cerere finanțare nr. 4S21" in text and "Brașov" in text


def test_T_O104_1_blocks_are_in_dotted_frames(window):
    from PySide6.QtGui import QTextFrameFormat

    frames = window.text_panel.view.document().rootFrame().childFrames()
    assert len(frames) == 2
    assert all(f.frameFormat().borderStyle() == QTextFrameFormat.BorderStyle.BorderStyle_Dotted
               for f in frames)


def test_T_O105_1_uncertain_characters_use_the_setting_color(window):
    panel = window.text_panel
    color = window.project.settings().get("areas.uncertain_color").lower()
    put_cursor(panel, "finanțare", 2)  # dupa „fi”: caracterul „i” e nesigur
    assert panel.view.textCursor().charFormat().background().color().name() == color
    put_cursor(panel, "finanțare", 4)
    assert panel.view.textCursor().charFormat().background().style() == Qt.BrushStyle.NoBrush  # sigur
    put_cursor(panel, "Cerere", 2)
    assert panel.view.textCursor().charFormat().background().style() == Qt.BrushStyle.NoBrush


def test_T_O028_1_nonprinting_characters(window):
    from PySide6.QtGui import QTextOption

    panel = window.text_panel
    panel.actions["nonprinting"].trigger()
    flags = panel.view.document().defaultTextOption().flags()
    assert flags & QTextOption.Flag.ShowTabsAndSpaces
    assert window.project.settings().get("areas.show_nonprinting") is True


def test_T_O029_1_plain_text_font_setting(window):
    window.project.settings().set("areas.plain_text_font", "Courier New")
    window.text_panel.render()
    assert window.text_panel.view.document().defaultFont().family() == "Courier New"


def test_T_J417_1_text_pane_has_its_own_zoom(window):
    panel = window.text_panel
    before = panel.view.document().defaultFont().pointSizeF()
    panel.zoom_combo.setCurrentIndex(panel.zoom_combo.findData(200))
    assert panel.zoom == 200 and window.image_view.zoom != 200
    assert panel.view.document().defaultFont().pointSizeF() == pytest.approx(before * 2)


def test_T_O100_1_and_O101_1_toolbars(window):
    panel = window.text_panel
    row1 = [a.objectName() for a in panel.findChild(QToolBar, "text_toolbar_1").actions()
            if a.objectName()]
    assert row1 == ["text_grow", "text_shrink", "text_symbol", "text_link", "text_find"]
    row2 = [a.objectName() for a in panel.findChild(QToolBar, "text_toolbar_2").actions()
            if a.objectName()]
    assert row2 == ["text_style_editor", "text_bold", "text_italic", "text_underline",
                    "text_superscript", "text_subscript", "text_align_left",
                    "text_align_center", "text_align_right", "text_align_justify",
                    "text_spacing", "text_list", "text_redaction"]


# =============================================================================
# Editarea (O-020)
# =============================================================================


def test_collect_words_attaches_typed_text_to_neighbours():
    chars = [("a", 1), ("b", 1), (" ", None), ("x", None), ("c", 2), (" ", None),
             ("z", None), ("\n", None)]
    assert collect_words(chars) == {1: "ab", 2: "xcz"}
    assert collect_words([("q", None), (" ", None), ("w", 5)]) == {5: "qw"}


def test_T_O020_1_typing_in_a_word_updates_the_project(window):
    panel = window.text_panel
    put_cursor(panel, "4S21", 1)
    cursor = panel.view.textCursor()
    cursor.deleteChar()  # „S” → „5”
    cursor.insertText("5")
    panel.view.setTextCursor(cursor)
    assert panel.commit() == 1
    word = next(w for w in words(window) if w.original_text == "4S21")
    assert word.text == "4521" and word.is_edited and not word.is_uncertain
    assert "4521" in panel.view.toPlainText()
    window.actions["undo"].trigger()
    assert "4S21" in [w.text for w in words(window)]


def test_edit_is_committed_after_a_pause(window, qtbot):
    panel = window.text_panel
    put_cursor(panel, "Cerere", 6)
    panel.view.textCursor().insertText("a")
    qtbot.waitUntil(lambda: "Cererea" in [w.text for w in words(window)], timeout=3000)


def test_typed_text_before_a_word_joins_it(window):
    panel = window.text_panel
    put_cursor(panel, "nr.", 0)
    panel.view.textCursor().insertText("(")
    panel.commit()
    assert "(nr." in [w.text for w in words(window)]


# =============================================================================
# Sincronizarea (O-021)
# =============================================================================


def test_T_O021_1_text_cursor_highlights_the_word_in_the_image(window):
    put_cursor(window.text_panel, "Brașov", 2)
    assert window.image_view.word_box == Rect(10, 110, 80, 20)


def test_T_O021_2_click_in_the_image_selects_the_word(window):
    window.image_view.clicked.emit(QPointF(200, 20))  # al treilea cuvant, „nr.”
    assert window.text_panel.view.textCursor().selectedText() == "nr."


# =============================================================================
# Formatarea, paragrafele, redactarea (O-022, O-101, O-070)
# =============================================================================


def test_bold_and_superscript_apply_to_the_selection(window):
    panel = window.text_panel
    select(panel, "Cerere")
    panel.actions["bold"].trigger()
    word = next(w for w in words(window) if w.text == "Cerere")
    assert word.is_bold
    put_cursor(panel, "Cerere", 2)
    assert panel.actions["bold"].isChecked()
    select(panel, "nr.")
    panel.actions["superscript"].trigger()
    select(panel, "nr.")
    panel.actions["subscript"].trigger()  # exponentul si indicele se exclud
    word = next(w for w in words(window) if w.text == "nr.")
    assert word.is_subscript and not word.is_superscript


def test_font_size_buttons(window):
    panel = window.text_panel
    select(panel, "Cerere")
    index = panel.size_combo.findData(14)
    panel.size_combo.setCurrentIndex(index)
    panel.size_combo.activated.emit(index)
    select(panel, "Cerere")
    panel.actions["grow"].trigger()
    assert next(w for w in words(window) if w.text == "Cerere").font_size == 15


def test_alignment_and_list(window):
    panel = window.text_panel
    put_cursor(panel, "Brașov", 1)
    panel.actions["align_center"].trigger()
    put_cursor(panel, "Brașov", 1)
    panel.actions["list"].trigger()
    block = window.project.page(1).areas[1].blocks[0]
    assert block.alignment == "center" and block.list_level == 1
    put_cursor(panel, "Brașov", 1)
    assert panel.actions["align_center"].isChecked() and panel.actions["list"].isChecked()


def test_style_combo_applies_a_style(window):
    panel = window.text_panel
    put_cursor(panel, "Brașov", 1)
    panel.style_combo.activated.emit(panel.style_combo.findData("Heading 2"))
    assert window.project.page(1).areas[1].blocks[0].style_name == "Heading 2"


def test_redaction_from_the_toolbar(window):
    panel = window.text_panel
    select(panel, "nr.")
    panel.actions["redaction"].trigger()
    assert next(w for w in words(window) if w.text == "nr.").is_redacted
    assert "•••" in panel.view.toPlainText()


# =============================================================================
# Cautarea si inlocuirea (O-024, O-025)
# =============================================================================


def test_find_and_replace(window):
    panel = window.text_panel
    panel.actions["find"].trigger()
    assert panel.find_bar.isVisibleTo(panel)
    panel.find_edit.setText("brasov")  # fara diacritice si majuscule
    assert panel.find_next().text == "Brașov"
    assert panel.view.textCursor().selectedText() == "Brașov"
    panel.replace_edit.setText("Sibiu")
    assert panel.replace_all() == 1
    assert "Sibiu" in [w.text for w in words(window)]
    panel.find_edit.setText("inexistent")
    messages = []
    panel.message.connect(messages.append)
    assert panel.find_next() is None and messages == ["Textul nu a fost găsit"]


# =============================================================================
# Tabelele (O-064) si starea paginii
# =============================================================================


def test_T_O064_1_table_tools_are_hidden_until_added_from_view(window):
    panel = window.text_panel
    assert not panel.table_bar.isVisibleTo(panel)
    window.actions["table_tools"].trigger()
    assert panel.table_bar.isVisibleTo(panel)


def test_page_status_follows_text_edits(window):
    from app.core.text.editor import TextEditor

    TextEditor(window.project).mark_verified(window.project.page(1))
    window.refresh()
    panel = window.text_panel
    put_cursor(panel, "Cerere", 6)
    panel.view.textCursor().insertText("a")
    panel.commit()
    assert window.project.page(1).status is PageStatus.RECOGNIZED  # nu mai e verificata


def test_word_ids_are_in_the_character_format(window):
    panel = window.text_panel
    put_cursor(panel, "Cerere", 1)
    wid = panel.view.textCursor().charFormat().property(WORD_ID)
    assert panel.words[int(wid)].text == "Cerere"
