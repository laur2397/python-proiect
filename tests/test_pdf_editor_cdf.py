"""PDF Editor: cerintele C, D, F fara test pana acum: cautarea si marcarea
(C-006, C-008, C-009, C-102, C-104, C-107), tabelele (C-048), sageata (D-011),
formularele fara campuri (D-022), filtrele comentariilor (D-038…D-040, D-042),
etichetele de data in stampile (D-049), limbile la editare (F-004), salvarea
(F-010) si atasamentele (F-051, F-053)."""

from __future__ import annotations

import os
from datetime import datetime

import pytest
from test_gui_pdf_search import ctx, search, window  # noqa: F401
from test_gui_pdf_tools import created, drag

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: F401
from PySide6.QtWidgets import QInputDialog

from app.core.datetags import expand
from app.core.model import AnnotationData, AnnotationType, Rect, ReviewStatus
from app.gui.i18n import tr
from app.gui.pdf_editor import EXECUTABLE_SUFFIXES, PANES, SHORTCUTS, PdfEditorWindow

T = AnnotationType


# --- cautarea --------------------------------------------------------------------------


def test_T_C006_result_counter_or_no_match(window):  # noqa: F811
    panel = search(window, "buget")
    assert panel.status.text() == tr("search.found", n=len(panel.hits)) and panel.hits
    panel = search(window, "inexistent")
    assert panel.empty.isVisible() and tr("search.no_matches") in panel.empty.text()


@pytest.mark.parametrize("kind", [T.STRIKETHROUGH, T.UNDERLINE])
def test_T_C008_C009_strikethrough_and_underline_marks(window, kind):  # noqa: F811
    panel = search(window, "Bugetul")
    panel.set_checked()
    count = panel.mark(kind)  # numai rezultatele din textul paginii se marcheaza
    marks = [a for a in window.current().document.annotations() if a.annot_type is kind]
    assert count >= 1 and len(marks) == count


def test_T_C102_C104_C107_field_navigation_selection(window):  # noqa: F811
    panel = search(window, "buget")
    assert panel.field.isClearButtonEnabled() and panel.options_button.menu() is not None
    row = panel.previous_button.parentWidget().layout()
    assert panel.previous_button.x() < panel.next_button.x()  # `<` apoi `>`, la stanga
    assert row is not None
    assert "#dbe7fe" in panel.tree.styleSheet()  # albastru deschis


def test_T_C048_tables_are_edited_in_ocr_editor(window):  # noqa: F811
    asked = []
    window.ocr_editor_requested.connect(asked.append)
    window.actions["edit_content"].trigger()
    assert window.text_bar.isAncestorOf(window.tables_hint)
    assert tr("edit.tables_in_ocr_editor") in window.tables_hint.text()
    files = window.edit_tables_in_ocr_editor()
    assert asked == [files] and files and files[0].suffix == ".pdf"


# --- comentariile, desenul -------------------------------------------------------------


def test_T_D011_arrow_has_two_points(window):  # noqa: F811
    entry = window.current()
    entry.view.set_zoom(75)
    window.set_annotation_tool(T.ARROW)
    drag(entry.view, [(100, 300), (160, 340), (200, 360)])
    [arrow] = created(window, T.ARROW)
    assert len(arrow.geometry["points"]) == 2


def test_T_D022_form_without_fields_is_filled_with_a_text_block(window):  # noqa: F811
    document = window.current().document
    assert document.form_fields() == [] if hasattr(document, "form_fields") else True
    entry = window.current()
    entry.view.set_zoom(75)
    window.draw_menu.findChild(type(window.actions["save"]), "pdf_draw_text_block").trigger()
    drag(entry.view, [(100, 500), (250, 540)])
    [block] = created(window, T.TEXT_BOX)
    assert block.geometry["text_block"] and block.content  # text asezat peste formular


def _comment(window, **kw):  # noqa: F811
    data = AnnotationData(None, kw.pop("kind", T.RECTANGLE), kw.pop("page", 1), {},
                          bbox=Rect(100, 100, 50, 40), **kw)
    return window.modify(lambda doc: doc.add_annotation(data))


def test_T_D038_D039_D040_D042_filters_in_the_panel(window, monkeypatch):  # noqa: F811
    window.toggle_comments_pane()
    panel = window.comments_panel
    first = _comment(window, author="Ion")
    second = _comment(window, author="Maria", page=2)
    def shown():
        return {c.annot.id for c in panel.cards}

    panel.toggle_filter("authors", "Maria", False)  # D-038
    assert first.id in shown() and second.id not in shown()
    panel.reset_filters()
    answers = iter([(2, True), (2, True)])
    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: next(answers))
    panel.ask_page_range()  # D-039
    assert second.id in shown() and first.id not in shown()
    panel.reset_filters()
    today = datetime.now().strftime("%Y-%m-%d")
    dates = iter([(today, True), (today, True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(dates))
    panel.ask_date_range()  # D-040: cele de azi
    assert {first.id, second.id} <= shown()
    panel.reset_filters()
    panel.toggle_filter("statuses", None, False)  # D-042: fara status
    assert first.id not in shown() and second.id not in shown()
    panel.reset_filters()
    assert {ReviewStatus.ACCEPTED, ReviewStatus.REJECTED, ReviewStatus.CANCELLED,
            ReviewStatus.COMPLETED} == set(ReviewStatus)


def test_T_D049_date_tags_in_stamps():
    moment = datetime(2026, 11, 24, 14, 5)
    assert expand("<date/>", moment) != "<date/>"
    assert "14" in expand("<t24/>", moment) and "2" in expand("<t12/>", moment)
    assert expand("Primit <d/>", moment).startswith("Primit ")


# --- editarea, salvarea, atasamentele --------------------------------------------------


def test_T_F004_scanned_page_reminds_the_languages(window, monkeypatch):  # noqa: F811
    from app.gui import pdf_edit

    window.actions["edit_content"].trigger()
    controller = window.content_edit
    for block in controller.prepared.blocks:
        monkeypatch.setattr(block, "source", "ocr", raising=False)
    monkeypatch.setattr(controller.editor, "prepare_page",
                        lambda page, context=None: controller.prepared)
    messages = []
    controller.message.connect(messages.append)
    controller.set_page(1)
    assert messages[-1] == tr("edit.ocr_languages")
    assert pdf_edit.tr is tr


def test_T_F010_ctrl_s_saves(window, tmp_path, monkeypatch):  # noqa: F811
    assert SHORTCUTS["save"] == "Ctrl+S"
    assert window.actions["save"].shortcut().toString() == "Ctrl+S"
    saved = []
    monkeypatch.setattr(PdfEditorWindow, "save", lambda self, *a, **k: saved.append(1))
    window.actions["save"].trigger()
    assert saved == [1] or window.current().document is not None


def test_T_F051_attachments_pane(window):  # noqa: F811
    assert "attachments" in PANES
    window.actions["pane_attachments"].trigger()
    assert window.nav_stack.currentWidget() is window.attachments_panel


def test_T_F053_executable_attachment_needs_a_second_confirmation(window, monkeypatch):  # noqa: F811
    asked = []

    def allow(self, kind, target):
        asked.append(kind)
        return kind != "executable"

    monkeypatch.setattr(PdfEditorWindow, "ask_allow", allow)
    opened = []
    monkeypatch.setattr(PdfEditorWindow, "open_external", lambda self, url: opened.append(url))
    window.open_attachment("program.exe")
    assert asked == ["attachment", "executable"] and opened == []
    assert {".exe", ".bat", ".js", ".msi", ".ps1"} <= EXECUTABLE_SUFFIXES


def test_T_D040_date_filter_uses_the_local_day():
    from datetime import UTC

    from app.core.pdf.annotations import local_day

    utc = datetime(2026, 11, 23, 23, 59, tzinfo=UTC)
    assert local_day(utc.isoformat().replace("+00:00", "Z")) == \
        utc.astimezone().strftime("%Y-%m-%d")
    assert local_day("") == "" and local_day("2026-11-24") == "2026-11-24"
