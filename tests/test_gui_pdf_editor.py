"""Fereastra PDF Editor (faza 7, pasul 7.7b): B-002…B-043, B-200…B-209,
B-303…B-306, X-201, I-024."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pikepdf
import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.gui.pdf_editor import LATER, PANES, RIBBON_TABS, SHORTCUTS, PdfEditorWindow
from app.gui.pdf_view import ZOOM_MAX, ViewMode

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    yield w
    w.close()


@pytest.fixture
def pdf(tmp_path):
    return text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)])


# --- X-201 ----------------------------------------------------------------------------


def test_T_X201_1_shortcuts_follow_spec_09():
    """SPEC_09 A.2: fiecare scurtatura din PDF Editor e cea din tabel."""
    commands = {
        "New Task...": "new_task", "Open...": "open", "Save": "save",
        "Save as PDF Document...": "save_as", "Close Document": "close", "Print...": "print",
        "Options...": "options", "Exit": "exit", "Undo": "undo", "Redo": "redo",
        "Cut": "cut", "Copy": "copy", "Copy Area as Image": "copy",
        "Copy Area as Text": "copy_area_text", "Copy Area as Table": "copy_area_table",
        "Paste": "paste", "Delete": "delete", "Select All": "select_all",
        "Add Note": "add_note", "Highlight": "highlight", "Underline": "underline",
        "Strikethrough": "strikethrough", "Insert Text": "insert_text",
        "Search and Mark Up": "pane_search", "Recognize Document": "recognize_document",
        "Add Bookmark...": "add_bookmark", "Find...": "find", "Find Next": "find_next",
        "Add Blank Page": "add_blank_page", "Add Pages from PDF...": "add_pages_pdf",
        "Add Pages from File...": "add_pages_file",
        "Add Pages from Scanner...": "add_pages_scanner",
        "Rotate Pages Right": "rotate_right", "Rotate Pages Left": "rotate_left",
        "Correct Page Orientation": "correct_orientation", "Crop Pages": "crop_pages",
        "Replace Pages": "replace_pages", "Move Pages": "move_pages",
        "Delete Pages": "delete_pages", "Add Link...": "add_link",
        "Redaction Mode": "redaction_mode", "Erase Text and Pictures": "erase",
        "Show Navigation Pane": "navigation_pane", "Pages": "pane_pages",
        "Bookmarks": "pane_bookmarks", "Search": "pane_search",
        "Attachments": "pane_attachments", "Digital Signatures": "pane_signatures",
        "Show Comments Pane": "comments_pane", "Zoom In": "zoom_in", "Zoom Out": "zoom_out",
        "Best Fit": "best_fit", "Actual Size": "actual_size", "Fit to Width": "fit_width",
        "Go to Page Number...": "go_to_page", "Next Page": "next_page",
        "Previous Page": "previous_page", "First Page": "first_page",
        "Last Page": "last_page", "Back": "back", "Forward": "forward",
        "One-Page View": "one_page", "One-Page Scrolling": "one_page_scroll",
        "Two-Page View": "two_page", "Two-Page Scrolling": "two_page_scroll",
        "Full Screen": "full_screen", "Save Selected Pages": "save_pages", "Help": "help",
    }
    text = (ROOT / "docs" / "spec" / "SPEC_09_anexe_referinta.md").read_text(encoding="utf-8")
    section = text.split("### A.2 PDF Editor", 1)[1].split("### A.3", 1)[0]
    spec = {}
    for name, key in re.findall(r"\|\s*\**([^|*]+?)\**\s*\|\s*\**`([^`]+)`\**\s*\|", section):
        spec[name.strip()] = key.replace("Stanga", "Left").replace("Dreapta", "Right") \
            .replace("Jos", "Down").replace("Sus", "Up")
    assert set(commands) == set(spec)  # nicio comanda din tabel nu lipseste
    for command, action in commands.items():
        assert SHORTCUTS[action] == spec[command], command


def test_T_X201_2_shortcuts_are_set_on_the_actions(window):
    from PySide6.QtGui import QKeySequence

    for key, shortcut in SHORTCUTS.items():
        assert window.actions[key].shortcut() == QKeySequence(shortcut), key


def test_every_command_is_translated(window):
    assert [k for k, a in window.actions.items() if a.text().startswith("pdf.")] == []


# --- B-200…B-209, B-303…B-306 ---------------------------------------------------------


def test_T_B200_1_ribbon_tabs_and_hamburger(window):
    tabs = [window.ribbon_tabs.tabText(i) for i in range(window.ribbon_tabs.count())]
    assert tabs == ["Document", "Organizare pagini", "Editare conținut", "Securitate",
                    "Editor de formulare"]
    assert window.menuBar().actions() == []  # B-200: fara bara de meniu clasica
    menu = window.hamburger.menu()
    assert [a.text() for a in menu.actions()] == ["Fișier", "Editare", "Vizualizare",
                                                  "Document", "Instrumente", "Ajutor"]
    # V-001: `Tools > Screenshot Reader` si in PDF Editor
    window.ribbon_tabs.setCurrentIndex(3)
    assert window.ribbon_pages.currentWidget() is window.toolbars["security"]


def test_T_B203_1_document_tab_commands_in_order(window):
    bar = window.toolbars["document"]
    assert [a.objectName() for a in bar.actions()] == \
        [f"pdf_action_{k}" for k in RIBBON_TABS["document"]]


def test_T_B304_1_ribbon_collapses(window):
    window.collapse_button.setChecked(True)
    assert not window.ribbon_pages.isVisible() and window.ribbon_tabs.isVisible()
    window.collapse_button.setChecked(False)
    assert window.ribbon_pages.isVisible()


def test_later_commands_are_visible_but_disabled(window, pdf):
    window.open_path(pdf)
    for key, step in LATER.items():
        assert not window.actions[key].isEnabled(), key
        assert step in window.actions[key].toolTip()


def test_T_B305_1_comments_button_counts_and_toggles(window, pdf):
    window.open_path(pdf)
    assert window.actions["comments_pane"].text() == "Comentarii (1)"
    assert not window.comments_panel.isVisible()
    window.actions["comments_pane"].trigger()  # F7
    assert window.comments_panel.isVisible() and window.actions["comments_pane"].isChecked()
    assert len(window.comments_panel.cards) == 1


def test_T_B208_1_side_bar_and_navigation_pane(window, pdf):
    window.open_path(pdf)
    assert [a.objectName() for a in window.side_bar.actions()] == \
        [f"pdf_action_pane_{p}" for p in PANES]
    window.actions["pane_bookmarks"].trigger()
    assert window.nav_stack.currentWidget() is window.bookmarks_panel
    window.actions["navigation_pane"].trigger()  # F5
    assert not window.nav_stack.isVisible()
    window.actions["navigation_pane"].trigger()
    assert window.nav_stack.isVisible()


# --- B-002…B-018 prin fereastra -------------------------------------------------------


def test_T_B014_1_page_field(window, pdf):
    entry = window.open_path(pdf)
    assert window.page_total.text() == "/ 5"
    window.page_field.setText("4")
    window.page_field.returnPressed.emit()
    assert entry.view.current_page == 4 and window.page_field.property("invalid") is False
    window.page_field.setText("9")
    window.page_field.returnPressed.emit()
    assert window.page_field.property("invalid") is True  # camp rosu
    assert entry.view.current_page == 4


def test_T_B010_B016_bottom_bar_limits(window, pdf):
    entry = window.open_path(pdf)
    window.set_zoom(ZOOM_MAX)
    assert not window.actions["zoom_in"].isEnabled()
    assert window.zoom_combo.currentText() == f"{ZOOM_MAX}%"
    assert not window.actions["previous_page"].isEnabled()  # pagina 1
    window.actions["last_page"].trigger()
    assert entry.view.current_page == 5 and not window.actions["next_page"].isEnabled()
    window.zoom_combo.setEditText("150")
    window.zoom_combo.lineEdit().returnPressed.emit()
    assert entry.view.zoom == 150


def test_T_B006_2_odd_on_right_only_in_two_page_modes(window, pdf):
    entry = window.open_path(pdf)
    assert not window.actions["odd_on_right"].isEnabled()
    window.actions["two_page"].trigger()
    assert entry.view.mode is ViewMode.TWO_PAGE
    assert window.actions["odd_on_right"].isEnabled()
    window.actions["odd_on_right"].trigger()
    assert entry.view.odd_on_right


def test_T_B007_B009_full_screen(window, pdf):
    window.open_path(pdf)
    window.actions["full_screen"].trigger()
    assert window.isFullScreen() and not window.ribbon.isVisible()
    assert not window.bottom_bar.isVisible()
    texts = [a.text() for a in window.full_screen_menu().actions() if a.text()]
    assert "Notă" in texts and "Ieși din ecranul complet" in texts
    QTest.keyClick(window, Qt.Key.Key_Escape)  # B-007: Esc iese
    assert not window.isFullScreen() and window.ribbon.isVisible()


# --- B-043 ----------------------------------------------------------------------------


def test_T_B043_1_document_tabs_and_closing(window, pdf, tmp_path, monkeypatch):
    second = text_pdf(tmp_path / "anexa.pdf", [["Anexa"]])
    window.open_path(pdf)
    window.open_path(second)
    assert window.tabs.count() == 2 and window.tabs.tabText(1) == "anexa.pdf"
    assert window.page_total.text() == "/ 1"
    window.tabs.setCurrentIndex(0)
    assert window.page_total.text() == "/ 5"
    window.current().document.set_metadata(title="schimbat")
    monkeypatch.setattr(PdfEditorWindow, "ask_save", lambda self, d: "cancel")
    assert not window.close_document(0)  # I-023: Cancel pastreaza documentul
    assert window.tabs.count() == 2
    monkeypatch.setattr(PdfEditorWindow, "ask_save", lambda self, d: "discard")
    assert window.close_document(0)
    window.close_current()
    assert window.tabs.count() == 0 and window.center.currentWidget() is window.empty_page
    assert window.windowTitle() == "DocuLens PDF Editor"


def test_open_missing_or_protected_file(window, tmp_path):
    assert window.open_path(tmp_path / "lipsa.pdf") is None
    protected = tmp_path / "parola.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(protected, encryption=pikepdf.Encryption(user="x", owner="x", R=6))
    assert window.open_path(protected) is None  # fara parola (dialogul raspunde None)
    assert window.tabs.count() == 0


# --- B-037…B-039 ----------------------------------------------------------------------


def test_T_B037_B039_javascript_banner(window, pdf):
    with pikepdf.open(pdf, allow_overwriting_input=True) as doc:
        doc.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript,
                                                 JS=pikepdf.String("app.alert(1)"))
        doc.save(pdf)
    asked = []
    window.options_requested.connect(asked.append)
    entry = window.open_path(pdf)
    assert window.js_banner.isVisible()
    window.js_all_button.click()  # B-039: deschide Options
    assert asked == ["other"]
    window.js_document_button.click()  # B-038
    assert not window.js_banner.isVisible()
    assert window.policy.allows(entry.document)


# --- panourile ------------------------------------------------------------------------


def test_T_B021_B023_B024_panels(window, pdf):
    with pikepdf.open(pdf, allow_overwriting_input=True) as doc:
        doc.attachments["buget.xlsx"] = pikepdf.AttachedFileSpec(doc, b"x" * 2000,
                                                                 filename="buget.xlsx")
        doc.save(pdf)
    entry = window.open_path(pdf)
    assert not window.bookmarks_panel.is_empty()
    window.bookmarks_panel._activated(window.bookmarks_panel.tree.topLevelItem(0))
    assert entry.view.current_page == 5  # semnul de carte duce la ultima pagina
    assert window.attachments_panel.list.count() == 1
    assert "2.0 KB" in window.attachments_panel.list.item(0).text()
    assert window.signatures_panel.is_empty()
    window.pages_panel.render_all()
    assert window.pages_panel.list.item(0).data(Qt.ItemDataRole.UserRole + 1) is True


def test_T_B034_1_attachment_opens_only_when_allowed(window, pdf, monkeypatch):
    with pikepdf.open(pdf, allow_overwriting_input=True) as doc:
        doc.attachments["nota.txt"] = pikepdf.AttachedFileSpec(doc, b"salut",
                                                               filename="nota.txt")
        doc.save(pdf)
    window.open_path(pdf)
    opened = []
    monkeypatch.setattr(PdfEditorWindow, "open_external", lambda self, url: opened.append(url))
    monkeypatch.setattr(PdfEditorWindow, "ask_allow", lambda self, kind, target: False)
    window.open_attachment("nota.txt")
    assert opened == []
    monkeypatch.setattr(PdfEditorWindow, "ask_allow", lambda self, kind, target: True)
    window.open_attachment("nota.txt")
    assert Path(opened[0].toLocalFile()).read_bytes() == b"salut"


# --- B-028, B-032 ---------------------------------------------------------------------


def test_T_B028_1_background_recognition_starts_on_open(window, ctx, tmp_path, monkeypatch):
    from PIL import Image

    from app.core.pdf import background
    from app.core.pdf.document import PdfDocument

    scan = tmp_path / "scan.pdf"
    Image.new("L", (600, 800), 255).save(scan, "PDF", resolution=150)
    ctx.settings.set("image.background_recognition_pdf", True)
    monkeypatch.setattr(background.os, "cpu_count", lambda: 4)
    calls = []
    monkeypatch.setattr(PdfDocument, "recognize_in_background",
                        lambda self, **kw: calls.append(kw["pages"]) or [])
    window.open_path(scan)
    for _ in range(5):
        QApplication.processEvents()
    assert calls == [[1]]


def test_T_B032_1_recognize_document_asks_and_reloads(window, pdf, monkeypatch):
    from app.core.pdf.document import PdfDocument

    stored = []
    monkeypatch.setattr(PdfDocument, "recognize_and_store",
                        lambda self, **kw: stored.append(True) or [1])
    window.open_path(pdf)
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm", lambda self, text: False)
    window.actions["recognize_document"].trigger()
    assert stored == []
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm", lambda self, text: True)
    window.actions["recognize_document"].trigger()
    assert stored == [True]


# --- salvarea si siguranta ------------------------------------------------------------


def test_T_I001_I002_save_and_save_as(window, pdf, tmp_path, monkeypatch):
    entry = window.open_path(pdf)
    entry.document.set_metadata(title="Dosar nou")
    window._update_state()
    assert window.windowTitle().startswith("dosar.pdf*")
    assert window.save() and not entry.document.is_modified
    target = tmp_path / "copie.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, d: target)
    assert window.save_as()
    assert window.tabs.tabText(0) == "copie.pdf" and target.exists()


def test_T_I024_1_autosave_keeps_a_safety_copy(window, pdf):
    entry = window.open_path(pdf)
    entry.document.set_metadata(title="Nesalvat")
    window.autosave()
    assert entry.document._recovery_path is not None
    assert entry.document._recovery_path.exists()


def test_select_and_hand_tools(window, pdf):
    from app.gui.pdf_view import Tool

    entry = window.open_path(pdf)
    window.actions["hand"].trigger()
    assert entry.view.tool is Tool.HAND
    window.actions["select"].trigger()
    assert entry.view.tool is Tool.SELECT
    QTest.mouseClick(entry.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
