"""Modul `Edit Content` din PDF Editor (faza 9, pasul 9.6): F-001, F-003, F-007…F-023,
F-100…F-110."""

from __future__ import annotations

import os

import pikepdf
import pytest
from PIL import Image
from test_pdf_content_edit import paragraph_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.gui.pdf_edit import next_size, resized
from app.gui.pdf_editor import LATER, RIBBON_TABS, PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    path = paragraph_pdf(tmp_path / "doc.pdf", [
        ["Cerere de finantare", "pentru proiectul de cercetare"],
        ["Bugetul total este de 1200 lei"],
    ])
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(path)
    yield w
    w.close()


def edit(window):
    window.actions["edit_content"].trigger()  # Ctrl+E
    return window.content_edit


def text(window):
    return window.current().document.extract_text(1)


def budget(controller):
    return next(b for b in controller.blocks() if "Bugetul" in b.text)


# --- F-001, F-003, F-007, F-100…F-103 ---------------------------------------------------------


def test_T_F001_edit_content_tab_starts_and_leaving_it_stops_editing(window):
    for key in ("picture", "add_text", "cut", "paste"):
        assert key not in LATER
    controller = edit(window)
    assert window.ribbon_tabs.currentIndex() == list(RIBBON_TABS).index("content")
    assert controller is not None and controller.page == 1 and len(controller.blocks()) == 2
    assert window.text_bar.isVisible()  # F-007
    window.actions["text_tools"].trigger()  # Ctrl+T
    assert not window.text_bar.isVisible()
    window.ribbon_tabs.setCurrentIndex(0)  # se iese comutand pe alt tab
    assert window.content_edit is None


def test_T_F003_page_that_cannot_be_prepared_gives_a_message(qtbot, ctx, tmp_path):
    pdf = pikepdf.new()
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
        Contents=pdf.make_stream(b"0 g 100 700 m 120 740 l 140 700 l f"))))
    path = tmp_path / "vector.pdf"
    pdf.save(path)
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.open_path(path)
    messages = []
    w.show_message = messages.append
    controller = edit(w)
    assert controller.page is None and messages  # ramane in vizualizare
    w.close()


def test_T_F100_F101_F102_F103_active_block_and_text_bar(window):
    controller = edit(window)
    assert not window.text_font.isEnabled() and not window.text_size.isEnabled()  # F-102
    block = budget(controller)
    controller.select_block(block.id)
    assert window.text_size.isEnabled() and window.text_size.value() == pytest.approx(12, abs=1)
    assert window.text_font.currentText()  # F-101: fontul blocului
    r = block.rect
    assert controller.handle_at(r.x, r.y) == "tl"  # F-103: manerele
    assert controller.handle_at(r.x + r.w / 2, r.y + r.h) == "b"
    assert controller.handle_at(r.x + r.w / 2, r.y + r.h / 2) is None


# --- F-008, F-009, F-104 ----------------------------------------------------------------------


def test_T_F008_F009_inline_editing(window):
    controller = edit(window)
    controller.select_block(budget(controller).id)
    inline = controller.start_inline()
    assert inline is not None and inline.toPlainText() == "Bugetul total este de 1200 lei"
    inline.setPlainText("Bugetul total este de 1500 lei")
    QTest.keyClick(inline, Qt.Key.Key_Escape)  # F-009: modificarile raman
    assert controller.inline is None
    flat = " ".join(text(window).split())  # reflow: randul se poate rupe
    assert "1500 lei" in flat and "1200" not in flat
    window.undo()
    assert "1200 lei" in text(window)
    assert any("1200" in b.text for b in window.content_edit.blocks())


# --- F-011…F-016, F-105…F-110 ---------------------------------------------------------------


def test_T_F011_add_text_block(window):
    controller = edit(window)
    window.actions["add_text"].trigger()
    assert controller.adding_text
    assert window.add_text_block(Rect(72, 400, 300, 30), "Bloc nou")
    assert "Bloc nou" in text(window)
    messages = []
    window.show_message = messages.append
    assert not window.add_text_block(Rect(500, 400, 300, 30), "prea lat") and messages


def test_T_F012_ctrl_click_and_delete(window):
    controller = edit(window)
    block = budget(controller)
    controller.marked.add(block.id)
    controller.select_block(block.id)
    window.actions["delete"].trigger()  # Del
    assert "Bugetul" not in text(window) and "Cerere de finantare" in text(window)


def test_T_F013_F014_resize_and_move(window):
    assert resized(Rect(10, 10, 100, 20), "r", -40, 0) == Rect(10, 10, 60, 20)
    assert resized(Rect(10, 10, 100, 20), "tl", 5, 5) == Rect(15, 15, 95, 15)
    controller = edit(window)
    block = budget(controller)
    controller.select_block(block.id)
    assert controller.move_active(50, 30)
    moved = budget(controller)
    assert moved.rect.x == pytest.approx(block.rect.x + 50, abs=1)
    assert controller.resize_active(Rect(moved.rect.x, moved.rect.y, 80, moved.rect.h))
    assert budget(controller).rect.h > moved.rect.h


def test_T_F105_F106_F107_F108_F109_F110_text_bar_controls(window, monkeypatch):
    assert next_size(12, 1) == 14 and next_size(12, -1) == 11
    controller = edit(window)
    controller.select_block(budget(controller).id)
    window.text_controls["bigger"].trigger()  # F-106
    assert budget(controller).font_size == 14
    window.text_controls["align_right"].trigger()  # F-107
    assert budget(controller).alignment == "right"
    window.text_controls["rtl"].trigger()  # F-108
    assert budget(controller).direction == "rtl"
    window.text_line_spacing.setValue(1.5)  # F-109
    window.text_line_spacing.editingFinished.emit()
    assert budget(controller).line_spacing == pytest.approx(1.5)
    monkeypatch.setattr(PdfEditorWindow, "ask_color", lambda self, current: "#cc0000")
    window.text_controls["color"].trigger()  # F-110
    assert budget(controller).color == "#cc0000"
    window.text_controls["bold"].trigger()
    assert budget(controller).bold
    window.text_size.setValue(20)  # F-105
    window.text_size.editingFinished.emit()
    assert budget(controller).font_size == 20


def test_cut_and_paste_a_block(window):
    controller = edit(window)
    controller.select_block(budget(controller).id)
    assert window.cut_block()
    assert QApplication.clipboard().text() == "Bugetul total este de 1200 lei"
    assert "Bugetul" not in text(window)
    controller.select_block(controller.blocks()[0].id)
    assert window.paste_block()
    assert "Bugetul total este de 1200 lei" in text(window)


# --- F-017, F-018, F-020…F-023 ---------------------------------------------------------------


def test_T_F020_F022_F023_pictures_from_the_window(window, monkeypatch, tmp_path):
    logo = tmp_path / "sigla.png"
    Image.new("RGB", (96, 48), "red").save(logo)
    controller = edit(window)
    monkeypatch.setattr(PdfEditorWindow, "ask_open_file", lambda self, title: logo)
    window.actions["picture"].trigger()  # F-020
    assert len(window.content_edit.prepared.pictures) == 1
    picture = window.content_edit.prepared.pictures[0]
    assert window.content_edit.picture_at(picture.rect.x + 1, picture.rect.y + 1) is not None
    menu = window.picture_menu(picture.id)
    assert [a.objectName() for a in menu.actions()] == ["picture_front", "picture_rotate",
                                                        "picture_delete"]
    assert window.picture_command("rotate", picture.id)  # F-021
    assert window.picture_command("delete", picture.id)  # F-023
    assert window.content_edit.prepared.pictures == []
    assert controller is not None


def test_T_F017_skew_button_only_on_skewed_pages(window):
    edit(window)
    assert not window.actions["correct_skew"].isVisible()


def test_T_F018_replace_text_layer_asks_first(window, monkeypatch):
    from app.core.pdf.editor import PdfContentEditor

    calls = []
    monkeypatch.setattr(PdfContentEditor, "replace_text_layer",
                        lambda self, page, **kw: calls.append((page, kw["deskew"])))
    edit(window)
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog",
                        lambda self, dialog: dialog.deskew.setChecked(True) or True)
    window.actions["text_layer"].trigger()
    assert calls == [(1, True)]
