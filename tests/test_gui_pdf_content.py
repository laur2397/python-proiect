"""Interfata pentru semne de carte, linkuri, atasamente, proprietati, antete,
filigrane si `Erase` (faza 9, pasii 9.3, 9.4): F-024…F-055, Z-013."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.core.context import AppContext
from app.core.model import BookmarkData, Rect
from app.core.paths import AppPaths
from app.core.pdf.decorate import HeaderFooter, HeaderFooterStore
from app.gui.pdf_content import LinkEditorDialog
from app.gui.pdf_editor import LATER, PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}", "Al doilea rand"]
                                            for n in range(1, 4)])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root[:] = []
        pdf.save(path)
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(path)
    yield w
    w.close()


def answer(monkeypatch, fill):
    def run(self, dialog):
        fill(dialog)
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", run)


def reply(monkeypatch, *texts):
    values = iter(texts)
    monkeypatch.setattr(PdfEditorWindow, "ask_text",
                        lambda self, t, label, default="": next(values))


def doc(window):
    return window.current().document


def titles(window):
    return [b.title for b in doc(window).bookmarks()]


def test_commands_of_phase_9_are_enabled():
    for key in ("add_bookmark", "add_link", "erase", "header_footer", "watermark"):
        assert key not in LATER


# --- F-031…F-038 ---------------------------------------------------------------------------


def test_T_F032_F035_add_bookmarks_from_the_panel(window, monkeypatch):
    reply(monkeypatch, "Cerere", "Anexa")
    window.actions["add_bookmark"].trigger()  # Ctrl+D
    panel = window.bookmarks_panel
    assert titles(window) == ["Cerere"] and panel.current_id() == 1
    window._go_to(3)
    panel.actions["add"].trigger()  # dupa cel selectat, la acelasi nivel
    marks = doc(window).bookmarks()
    assert [(b.title, b.target_page) for b in marks] == [("Cerere", 1), ("Anexa", 3)]


def test_T_F036_F037_F038_panel_commands(window, monkeypatch):
    for n, title in enumerate(("Unu", "Doi", "Trei"), start=1):
        doc(window).add_bookmark(BookmarkData(None, title, target_page=n))
    window._after_modify()
    panel = window.bookmarks_panel
    panel.select_id(2)
    panel.actions["level_right"].trigger()
    assert [c.title for c in doc(window).bookmarks()[0].children] == ["Doi"]
    panel.select_id(2)
    panel.actions["level_left"].trigger()
    reply(monkeypatch, "Anexa 2")
    panel.select_id(2)
    panel.actions["rename"].trigger()
    assert titles(window) == ["Unu", "Anexa 2", "Trei"]
    panel.moved.emit(3, None, 0)  # tragerea in panou
    assert titles(window) == ["Trei", "Unu", "Anexa 2"]
    panel.select_id(1)
    panel.actions["delete"].trigger()
    assert titles(window) == ["Unu", "Anexa 2"]
    window.undo()
    assert titles(window) == ["Trei", "Unu", "Anexa 2"]


def test_T_F033_bookmark_from_a_text_selection(window):
    selection = window.current().selection
    selection.mode = "text"
    selection.text_start, selection.text_end = (2, 0), (2, 7)
    menu = selection._text_menu()
    assert "selection_add_bookmark" in [a.objectName() for a in menu.actions()]
    assert window.add_bookmark_from_selection() is not None
    mark = doc(window).bookmarks()[0]
    assert mark.title == "Pagina 2" and mark.target_page == 2
    assert mark.target_y is not None and mark.target_y > 0


def test_T_F034_set_destination_to_the_current_page(window):
    doc(window).add_bookmark(BookmarkData(None, "A", target_page=1))
    window._after_modify()
    window._go_to(3)
    window.bookmarks_panel.select_id(1)
    window.bookmarks_panel.actions["set_destination"].trigger()
    assert doc(window).bookmarks()[0].target_page == 3


# --- F-026…F-030 ---------------------------------------------------------------------------


def test_T_F027_link_editor_requires_prefixes(qtbot):
    dialog = LinkEditorDialog(3)
    qtbot.addWidget(dialog)
    ok = dialog.box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok.isEnabled()  # pagina 1, implicit
    dialog.to_other.setChecked(True)
    dialog.address.setText("ana@exemplu.ro")
    assert not ok.isEnabled() and dialog.message.text()
    dialog.address.setText("mailto:ana@exemplu.ro")
    assert ok.isEnabled() and dialog.target() == {"kind": "email",
                                                  "uri": "mailto:ana@exemplu.ro"}
    dialog.address.setText("C:/anexa.pdf")
    assert not ok.isEnabled()
    dialog.address.setText("file:///C:/anexa.pdf")
    assert dialog.target()["kind"] == "file"


def test_T_F026_add_link_by_drawing_an_area(window, monkeypatch):
    def fill(dialog):
        dialog.to_other.setChecked(True)
        dialog.address.setText("https://exemplu.ro")
    answer(monkeypatch, fill)
    window.actions["add_link"].trigger()  # Ctrl+L
    assert window.picker is not None
    window.picker.done(1, Rect(72, 300, 120, 20))
    assert window.picker is None
    assert [link.uri for link in doc(window).links(1)] == ["https://exemplu.ro"]


def test_T_F028_F029_F030_link_menu(window, monkeypatch):
    doc(window).add_link(1, Rect(72, 300, 120, 20), {"kind": "url", "uri": "https://a.ro"})
    window._after_modify()
    rect = window.link_at(1, 80, 310)
    assert rect is not None and window.link_at(1, 500, 700) is None
    menu = window.link_menu(1, rect)
    assert [a.objectName() for a in menu.actions()] == ["link_edit", "link_copy",
                                                        "link_remove"]
    assert window.copy_link(1, rect) == "https://a.ro"
    assert QApplication.clipboard().text() == "https://a.ro"

    def fill(dialog):
        dialog.to_page.setChecked(True)
        dialog.page.setValue(3)
    answer(monkeypatch, fill)
    assert window.edit_link(1, rect)
    assert doc(window).links(1)[0].target_page == 3
    assert window.remove_link(1, rect) and doc(window).links(1) == []


# --- F-052, F-054, F-055 ---------------------------------------------------------------------


def test_T_F052_attachment_operations(window, monkeypatch, tmp_path):
    source = tmp_path / "buget.xlsx"
    source.write_bytes(b"x" * 10)
    monkeypatch.setattr(PdfEditorWindow, "ask_open_file", lambda self, title: source)
    window.attachments_panel.add_action.trigger()
    assert [a[0] for a in doc(window).attachments()] == ["buget.xlsx"]
    reply(monkeypatch, "buget-final.xlsx")
    window.attachments_panel.list.setCurrentRow(0)
    window.attachments_panel.rename_action.trigger()
    assert [a[0] for a in doc(window).attachments()] == ["buget-final.xlsx"]
    window.attachments_panel.list.setCurrentRow(0)
    window.attachments_panel.delete_action.trigger()
    assert doc(window).attachments() == []


def test_T_F054_F055_document_properties_dialog(window, monkeypatch):
    seen = {}

    def fill(dialog):
        seen["pages"] = dialog.values["pages"].text()
        seen["size"] = dialog.values["page_size"].text()
        dialog.fields["author"].setText("Ana Popescu")
    answer(monkeypatch, fill)
    assert window.show_properties()
    assert seen == {"pages": "3", "size": "20.99 x 29.70 cm"}
    assert doc(window).metadata()["author"] == "Ana Popescu"


def test_T_F054_protected_document_fields_are_grey(qtbot, ctx, tmp_path, monkeypatch):
    path = tmp_path / "protejat.pdf"
    with pikepdf.open(text_pdf(tmp_path / "s.pdf", [["A"]])) as pdf:
        pdf.save(path, encryption=pikepdf.Encryption(
            owner="o", user="", allow=pikepdf.Permissions(modify_other=False)))
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.open_path(path)
    seen = {}
    answer(monkeypatch, lambda dialog: seen.setdefault(
        "enabled", [f.isEnabled() for f in dialog.fields.values()]))
    assert not w.show_properties()
    assert seen["enabled"] == [False] * 4
    w.close()


# --- F-039…F-044, Z-013 ----------------------------------------------------------------------


def test_T_F039_F040_header_dialog_with_bates_and_preview(window, ctx, monkeypatch):
    seen = {}

    def fill(dialog):
        dialog.position.setCurrentIndex(dialog.position.findData("bottom_right"))
        dialog.content.setText("Dosar ")
        dialog.insert_buttons["bates"].click()
        dialog.bates_start.setValue(7)
        dialog.bates_digits.setValue(3)
        seen["preview"] = dialog.preview.text()  # Z-013
    answer(monkeypatch, fill)
    window.actions["header_footer"].trigger()
    assert seen["preview"].endswith("Dosar 007")
    assert ["Dosar 00" + str(6 + n) in doc(window).extract_text(n) for n in (1, 2, 3)] == \
        [True] * 3
    assert ctx.settings.get("pdf_editor.bates_next") == 10  # `Continue from`

    def again(dialog):
        dialog.content.setText("{bates}")
        dialog.continue_from.setChecked(True)
        dialog.pages.apply_to.setCurrentIndex(dialog.pages.apply_to.findData("odd"))
    answer(monkeypatch, again)
    window.create_header_footer()
    assert "000010" in doc(window).extract_text(1) and "000011" in doc(window).extract_text(3)


def test_T_F043_save_and_add_requires_a_unique_name(window, ctx, monkeypatch):
    store = HeaderFooterStore(ctx.app_db)
    store.save("Dosar", HeaderFooter())
    reply(monkeypatch, "Dosar", "Dosar nou")
    messages = []
    window.show_message = messages.append

    def fill(dialog):
        dialog.content.setText("Antet {page}")
        dialog._save_clicked()
    answer(monkeypatch, fill)
    assert window.create_header_footer()
    assert store.names() == ["Dosar", "Dosar nou"] and len(messages) == 1
    assert store.load("Dosar nou").content == "Antet {page}"
    window._fill_header_menu()
    assert "Dosar nou" in [a.text() for a in window.header_menu.actions()]


def test_T_F044_manage_headers(window, ctx, monkeypatch):
    store = HeaderFooterStore(ctx.app_db)
    store.save("Dosar", HeaderFooter(content="{page}"))
    dialog = window.manage_headers()
    reply(monkeypatch, "Copie")
    dialog.buttons["copy"].click()
    assert store.names() == ["Copie", "Dosar"]
    answer(monkeypatch, lambda editor: editor.content.setText("Pag. {page}"))
    dialog.list.setCurrentRow(1)
    dialog.buttons["edit"].click()  # `Edit...`, apoi `Save`
    assert store.load("Dosar").content == "Pag. {page}"
    dialog.list.setCurrentRow(0)
    dialog.buttons["delete"].click()
    assert store.names() == ["Dosar"]


# --- F-045…F-050 -----------------------------------------------------------------------------


def test_T_F045_F049_watermarks_with_save_and_add(window, monkeypatch):
    rounds = iter([True, False])

    def fill(dialog):
        dialog.text.setText("CIORNA")
        dialog.transparency.setValue(50)
        assert dialog.transparency_slider.value() == 50
        dialog.rotation_slider.setValue(30)
        assert dialog.rotation.value() == 30
        if next(rounds):
            dialog._more_clicked()  # `Save and Add`
    answer(monkeypatch, fill)
    assert window.add_watermark() == 2
    assert "CIORNA" in doc(window).extract_text(1)
    seen = {}
    answer(monkeypatch, lambda dialog: seen.setdefault("wm", dialog.settings()))
    window.add_watermark()
    assert seen["wm"].opacity == pytest.approx(0.3) and seen["wm"].rotation == 45


def test_T_F050_delete_watermarks_from_the_menu(window, monkeypatch):
    answer(monkeypatch, lambda dialog: dialog.text.setText("CIORNA"))
    window.add_watermark()
    messages = []
    window.show_message = messages.append
    [action] = [a for a in window.watermark_menu.actions()
                if a.objectName() == "pdf_delete_watermarks"]
    action.trigger()
    assert "CIORNA" not in doc(window).extract_text(1) and messages


# --- F-024, F-025 ----------------------------------------------------------------------------


def test_T_F024_erase_tool(window):
    [hit] = doc(window).search("Pagina 2", in_comments=False, in_bookmarks=False,
                               in_metadata=False)
    rect = hit[1]
    window.actions["erase"].trigger()  # Ctrl+R
    window.picker.done(2, Rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4))
    assert "Pagina 2" not in doc(window).extract_text(2)
    assert "Al doilea rand" in doc(window).extract_text(2)
    window.undo()
    assert "Pagina 2" in doc(window).extract_text(2)
