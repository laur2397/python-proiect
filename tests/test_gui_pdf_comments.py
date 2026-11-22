"""Panoul `Comments`, Undo/Redo si adnotarile din pagina (faza 7, pasul 7.9a):
D-008, D-024…D-044, D-100…D-106."""

from __future__ import annotations

import os

import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QToolButton

from app.core.context import AppContext
from app.core.model import AnnotationData, AnnotationType, Rect, ReviewStatus
from app.core.paths import AppPaths
from app.gui.pdf_comments import CommentsPanel
from app.gui.pdf_editor import PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    c.settings.set("pdf_editor.default_author", "Ana")
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [["Cerere de finantare"], ["Anexa"]])
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(path)
    w.toggle_comments_pane()
    yield w
    w.close()


def add(window, **kw):
    data = AnnotationData(None, kw.pop("kind", AnnotationType.RECTANGLE), kw.pop("page", 1),
                          kw.pop("geometry", {}), bbox=kw.pop("bbox", Rect(100, 100, 50, 40)),
                          **kw)
    return window.modify(lambda doc: doc.add_annotation(data))


def find(window, annot_id):
    return next(a for a in window.current().document.annotations() if a.id == annot_id)


# --- D-100…D-105 ----------------------------------------------------------------------


def test_T_D101_D104_panel_and_cards(window):
    p = window.comments_panel
    assert p.findChild(QToolButton, "comments_close") is not None  # D-101
    assert p.search.placeholderText() == "Filtrează după text"  # D-102
    assert p.sort_button.text() == "AZ ▾"  # D-103
    created = add(window, content="Lipsește semnătura", author="Ion")
    card = p.card(created.id)
    assert card.header.text().startswith("Azi ") and card.header.text().endswith("Pagina 1")
    assert (card.text.text(), card.author.text()) == ("Lipsește semnătura", "Ion")
    note = next(c for c in p.cards if c.annot.annot_type is AnnotationType.NOTE)
    assert note.text.placeholderText() == "Scrieți comentariul"  # D-104
    p.select(created.id)
    assert "background" in card.styleSheet()  # D-105


def test_T_D025_edit_comment_text_with_undo_and_redo(window):
    created = add(window)
    card = window.comments_panel.card(created.id)
    card.text.setText("Text nou")
    card.text.editingFinished.emit()
    assert find(window, created.id).content == "Text nou"
    assert window.actions["undo"].isEnabled()
    window.actions["undo"].trigger()  # Ctrl+Z
    assert find(window, created.id).content is None
    window.actions["redo"].trigger()  # Ctrl+Y
    assert find(window, created.id).content == "Text nou"


def test_T_D026_D027_replies(window):
    created = add(window, content="Intrebare")
    card = window.comments_panel.card(created.id)
    card.reply_link.click()
    assert card.reply_field.isVisibleTo(card)
    card.reply_field.setText("Raspuns")
    card.reply_field.returnPressed.emit()
    reply = find(window, created.id).replies[0]
    assert (reply.content, reply.author) == ("Raspuns", "Ana")  # autorul implicit (D-032)
    row = window.comments_panel.card(created.id).replies.itemAt(0).widget()
    assert "Ana: Raspuns" in row.text()
    window.comments_panel.delete([reply.id])  # D-027
    assert find(window, created.id).replies == []


def test_T_D028_delete_from_panel_and_page(window):
    created = add(window)
    window.comments_panel.delete([created.id])
    assert created.id not in [a.id for a in window.current().document.annotations()]
    second = add(window, bbox=Rect(200, 300, 60, 40))
    window._page_clicked(1, 220, 320)  # clic pe adnotare in pagina: selectata (D-106)
    assert window.selected_annotation == second.id
    assert window.actions["delete"].isEnabled()
    window.actions["delete"].trigger()  # Del
    assert second.id not in [a.id for a in window.current().document.annotations()]


def test_T_D030_D031_checkmark_and_status(window):
    created = add(window)
    p = window.comments_panel
    p.card(created.id).check.setChecked(True)
    p.set_status(created.id, ReviewStatus.ACCEPTED)
    annot = find(window, created.id)
    assert annot.is_checked and annot.review_status is ReviewStatus.ACCEPTED
    card = p.card(created.id)
    assert card.check.isChecked()
    assert card.findChild(QLabel, "comment_status").text() == "Acceptat"


def test_T_D032_properties_and_set_default(window, ctx, monkeypatch):
    created = add(window, author="Ion")
    window.comments_panel.set_status(created.id, ReviewStatus.COMPLETED)
    seen = {}

    def accept(self, dialog):
        seen["history"] = dialog.history.count()
        dialog.author.setText("Maria")
        dialog.set_default = True
        return True

    monkeypatch.setattr(CommentsPanel, "exec_dialog", accept)
    window.comments_panel.properties(find(window, created.id))
    assert seen["history"] == 1
    assert ctx.settings.get("pdf_editor.default_author") == "Maria"
    assert find(window, created.id).author == "Maria"


# --- D-033…D-044 ----------------------------------------------------------------------


def test_T_D033_D034_navigation_and_text_filter(window):
    p = window.comments_panel
    first = add(window, content="buget", author="Ion")
    second = add(window, page=2, content="anexa", author="Maria")
    pages = []
    p.page_requested.connect(pages.append)
    p.select(first.id)
    p.next_button.click()  # D-033
    assert p.selected_id != first.id and pages
    p.search.setText("maria")  # D-034: si in autori
    assert [c.annot.id for c in p.cards] == [second.id]


def test_T_D035_sorting(window):
    p = window.comments_panel
    add(window, author="Zoe")
    add(window, author="Alin")
    p.set_sort("author")
    authors = [c.annot.author for c in p.cards]
    assert authors == sorted(authors, key=lambda a: (a or "").casefold())


def test_T_D036_D043_filters(window):
    p = window.comments_panel
    rect = add(window, author="Ion")
    add(window, kind=AnnotationType.OVAL, author="Maria")
    total = len(p.cards)
    p.toggle_filter("types", AnnotationType.OVAL, False)  # D-037
    assert all(c.annot.annot_type is not AnnotationType.OVAL for c in p.cards)
    p.reset_filters()  # D-043
    assert len(p.cards) == total
    p.card(rect.id).check.setChecked(True)
    p.set_flag_filter(True)  # D-041
    assert [c.annot.id for c in p.cards] == [rect.id]
    p.reset_filters()
    p.hide_current()  # D-036
    assert p.cards == [] and p.empty.isVisibleTo(p)
    p.show_all()
    assert len(p.cards) == total
    p.fill_filter_menu()  # meniul se construieste fara erori
    assert p.filter_button.menu().actions()


def test_T_D044_hide_comment_text(window):
    created = add(window, content="text")
    p = window.comments_panel
    p.hide_text_action.setChecked(True)
    card = p.card(created.id)
    assert not card.text.isVisibleTo(card) and card.author.isVisibleTo(card)
    p.hide_text_action.setChecked(False)
    assert card.text.isVisibleTo(card)


# --- D-008, Undo ----------------------------------------------------------------------


def test_T_D008_double_click_opens_the_comment(window):
    created = add(window, bbox=Rect(200, 300, 60, 40))
    window.toggle_comments_pane()  # inchis
    assert not window.comments_panel.isVisibleTo(window)
    window.current().selection.double_clicked.emit(1, 220, 320)
    QApplication.processEvents()
    assert window.comments_panel.isVisibleTo(window)
    assert window.comments_panel.selected_id == created.id


def test_undo_covers_search_markup(window):
    search = window.search_panel
    window.actions["find"].trigger()
    search.field.setText("Cerere")
    search.field.returnPressed.emit()
    search.set_checked()
    search.mark(AnnotationType.HIGHLIGHT)
    document = window.current().document
    assert [a for a in document.annotations() if a.annot_type is AnnotationType.HIGHLIGHT]
    window.undo()
    assert not [a for a in document.annotations() if a.annot_type is AnnotationType.HIGHLIGHT]
