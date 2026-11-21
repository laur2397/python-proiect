"""Faza 6b, pasul 6b.3b: verificarea, simbolurile, legaturile, bara Text
Properties (O-003…O-011, O-050…O-056, O-102, O-106, O-109)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QTextCursor

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
from app.gui.dialogs import LinkDialog, SymbolDialog, VerifyDialog
from app.gui.main_window import MainWindow
from app.gui.text_panel import describe_mixed

PAGES = {
    1: [("Cerere", False, "ron"), ("finantere", True, "ron"), ("nr.", False, "ron")],
    2: [("Brasov", True, "ron"), ("日本", True, "jpn")],
}


class ScriptEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        words = [WordData(None, t, 40.0 if u else 95.0, bbox=Rect(10 + 90 * i, 10, 80, 20),
                          is_uncertain=u, language_code=lang)
                 for i, (t, u, lang) in enumerate(PAGES[page.page_number])]
        block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 400, 20))],
                          bbox=Rect(10, 10, 400, 20))
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=70.0,
                                 area_blocks={page.areas[0].id: [block]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (800, 400), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    p = OcrProject.create(context=ctx)
    p.add_images(paths, auto_process=AutoProcessMode.NONE)
    for n in (1, 2):
        AreaEditor(p).create(p.page(n), [(5, 5), (450, 5), (450, 40), (5, 40)], AreaType.TEXT)
    RecognitionService(p, engine=ScriptEngine()).recognize_pages()
    yield p
    p.close()


@pytest.fixture
def window(qtbot, ctx, project):
    w = MainWindow(ctx, project)
    qtbot.addWidget(w)
    w.resize(1400, 1000)
    w.show()
    yield w
    w.hide()


def words(project, n=1):
    return list(project.page(n).iter_words())


def select(panel, text):
    panel.view.setTextCursor(panel.view.document().find(text))


def put_cursor(panel, text, offset=1):
    found = panel.view.document().find(text)
    cursor = QTextCursor(panel.view.document())
    cursor.setPosition(found.selectionStart() + offset)
    panel.view.setTextCursor(cursor)


# =============================================================================
# Simbolurile (O-008, O-109)
# =============================================================================


def test_T_O008_1_subset_and_character_code(qtbot):
    dialog = SymbolDialog()
    qtbot.addWidget(dialog)
    subsets = [dialog.subset.itemText(i) for i in range(dialog.subset.count())]
    assert "Ș Ț cu virgulă" in subsets
    dialog.subset.setCurrentIndex(subsets.index("Ș Ț cu virgulă"))
    assert {dialog.table.item(0, c).text() for c in range(4)} == {"Ș", "ș", "Ț", "ț"}
    dialog.table.setCurrentCell(0, 1)
    assert dialog.symbol == "ș" and dialog.code.text() == "0219"
    assert dialog.choose("20AC") == "€"
    assert dialog.choose("U+021B") == "ț"
    assert dialog.choose("zz") == ""


def test_symbol_goes_into_the_word(window):
    panel = window.text_panel
    put_cursor(panel, "nr.", 2)
    panel.insert_symbol("º")
    assert "nrº." in [w.text for w in words(window.project)]


# =============================================================================
# Legaturile (O-050…O-056)
# =============================================================================


def test_T_O054_1_to_O056_1_link_dialog(qtbot, tmp_path):
    dialog = LinkDialog("Cerere")
    qtbot.addWidget(dialog)
    assert dialog.display.text() == "Cerere"  # O-053
    dialog.address.setText("exemplu.ro")
    dialog.protocol.setCurrentText("http://")
    assert dialog.url() == "http://exemplu.ro"  # O-054: protocol plus adresa
    assert not dialog.protocol.isHidden() and dialog.browse.isHidden()
    dialog.set_kind("file")
    assert not dialog.browse.isHidden() and dialog.protocol.isHidden()  # O-055
    dialog.address.setText(str(tmp_path / "act.pdf"))
    assert dialog.url().startswith("file://")
    dialog.set_kind("email")
    dialog.address.setText("ana@exemplu.ro")
    assert dialog.url() == "mailto:ana@exemplu.ro"  # O-056
    dialog.address.setText("nu-e-adresa")
    dialog.accept()
    assert dialog.error.text() == "Adresa nu este validă" and dialog.result() == 0


def test_links_in_the_text_panel(window):
    panel = window.text_panel
    opened = []
    panel.open_url.disconnect()
    panel.open_url.connect(opened.append)
    select(panel, "Cerere")
    panel.edit_link("web", "exemplu.ro", "Cerere")

    def cerere():
        return next(w for w in words(window.project) if w.text == "Cerere")

    link = panel.link_of(cerere())
    assert link.url == "https://exemplu.ro" and link.tooltip == "https://exemplu.ro"  # O-050
    put_cursor(panel, "Cerere")
    keys = [k for k, _ in panel.context_actions()]
    assert {"link", "open_link", "remove_link"} <= set(keys)
    panel.open_link()
    assert opened == ["https://exemplu.ro"]  # O-051
    select(panel, "Cerere")
    panel.edit_link("email", "ana@exemplu.ro", "Scrieti-ne")  # O-053: editarea
    link = panel.link_of(cerere())
    assert link.url == "mailto:ana@exemplu.ro" and link.text_to_display == "Scrieti-ne"
    put_cursor(panel, "Cerere")
    panel.remove_link()  # O-052: textul ramane
    assert panel.link_of(cerere()) is None


def test_T_O006_2_add_to_dictionary_from_the_context_menu(window):
    panel = window.text_panel
    put_cursor(panel, "finantere")
    assert "add_to_dictionary" in [k for k, _ in panel.context_actions()]
    panel.add_to_dictionary()
    word = next(w for w in words(window.project) if w.text == "finantere")
    assert word.in_dictionary and not word.is_uncertain


# =============================================================================
# Verificarea (O-003…O-011)
# =============================================================================


def test_T_O003_1_verify_walks_the_uncertain_words(window):
    dialog = window.verify()
    assert isinstance(dialog, VerifyDialog)
    assert dialog.edit.text() == "finantere" and dialog.context.text() == "Cerere finantere nr."
    assert window.text_panel.view.textCursor().selectedText() == "finantere"
    dialog.edit.setText("finanțare")
    dialog.buttons["replace"].click()  # O-005
    assert "finanțare" in [w.text for w in words(window.project)]
    assert dialog.edit.text() == "Brasov" and window.current == 2  # pagina urmatoare
    dialog.buttons["skip"].click()  # O-004: textul ramane
    assert next(w for w in words(window.project, 2) if w.text == "Brasov").is_verified
    assert dialog.edit.text() == "日本"
    dialog.buttons["add"].click()  # O-006
    assert dialog.finished_all and not dialog.buttons["skip"].isEnabled()
    assert dialog.status.text() == "Nu mai sunt cuvinte nesigure"
    dialog.close()
    assert window.verify() is None  # O-003: niciun cuvant nesigur → mesaj
    assert window.statusBar().currentMessage() == "Nu mai sunt cuvinte nesigure"


def test_T_O010_1_cjk_suggestions(window, qtbot):
    dialog = VerifyDialog(window.project)
    qtbot.addWidget(dialog)
    word = next(w for w in words(window.project, 2) if w.text == "日本")
    dialog._go(word)
    suggestions = [dialog.suggestions.item(i).text() for i in range(dialog.suggestions.count())]
    assert "曰本" in suggestions  # „日” arata ca „曰”
    dialog.suggestions.setCurrentRow(suggestions.index("曰本"))
    assert dialog.edit.text() == "曰本"


def test_T_O007_1_and_O009_1_font_and_options(window, qtbot):
    dialog = window.verify()
    dialog.effects["is_bold"].click()
    assert next(w for w in words(window.project) if w.text == "finantere").is_bold
    with qtbot.waitSignal(dialog.options_requested):
        dialog.buttons["options"].click()
    dialog.close()


def test_T_O011_1_mark_text_as_verified(window):
    assert window.actions["mark_verified"].shortcut().toString() == "Ctrl+T"
    assert window.actions["verify"].shortcut().toString() == "Ctrl+F7"
    window.actions["mark_verified"].trigger()
    assert window.project.page(1).status is PageStatus.VERIFIED


# =============================================================================
# Bara Text Properties (O-106) si selectia mixta (O-102)
# =============================================================================


def test_T_O102_1_mixed_selection_description():
    a = WordData(1, "a", 90, font_size=21.0, is_bold=False)
    b = WordData(2, "b", 90, font_size=21.0, is_bold=False)
    block_a = BlockData(10, style_name="Heading 1")
    block_b = BlockData(11, style_name="Normal")
    assert describe_mixed([a, b], [block_a, block_b]) == "Altul + 21 pt, Fără aldin"
    assert describe_mixed([a, b], [block_a, block_a]) is None
    c = WordData(3, "c", 90, font_size=12.0, is_bold=True)
    assert describe_mixed([a, c], [block_a, block_a]) == "Heading 1"


def test_mixed_selection_shows_in_the_style_combo(window):
    panel = window.text_panel
    select(panel, "Cerere")
    panel.actions["bold"].trigger()
    cursor = panel.view.document().find("Cerere")
    cursor.setPosition(cursor.selectionStart())
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
    panel.view.setTextCursor(cursor)
    assert panel.style_combo.currentText() == "Altul"


def test_T_O106_1_text_properties_bar(window):
    panel = window.text_panel
    for key in ("bold", "italic", "underline", "font_color", "superscript", "subscript",
                "small_caps", "all_caps", "alignment", "background", "scale", "spacing"):
        assert key in panel.props
    put_cursor(panel, "Cerere")
    assert panel.props["language"].text() == "ron"
    select(panel, "Cerere")
    panel.choose_color("#aa0000")
    assert next(w for w in words(window.project) if w.text == "Cerere").text_color.lower() == "#aa0000"
    put_cursor(panel, "Cerere")
    panel.props["alignment"].activated.emit(2)  # dreapta
    assert window.project.page(1).areas[0].blocks[0].alignment == "right"
