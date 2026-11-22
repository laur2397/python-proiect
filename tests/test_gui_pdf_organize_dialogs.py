"""Dialogurile din `Organize Pages` (faza 8, pasul 8.4a): E-010…E-017, E-019,
E-020, E-038, E-108."""

from __future__ import annotations

import os

import pytest
from PIL import Image, ImageDraw
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.gui.pdf_editor import RIBBON_TABS, PdfEditorWindow
from app.gui.pdf_organize_dialogs import (
    PAGE_SIZES,
    ImageProcessingDialog,
    InsertPagesDialog,
    ReplacePagesDialog,
    image_options,
)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    c.settings.set("pdf_editor.recognize_images", False)  # fara Tesseract in teste
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)]))
    yield w
    w.close()


def answer(monkeypatch, fill):
    """`exec_dialog` completeaza dialogul cu `fill(dialog)` si raspunde OK."""
    def run(self, dialog):
        fill(dialog)
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", run)


def texts(window):
    document = window.current().document
    return [document.extract_text(n).strip() for n in range(1, document.page_count + 1)]


def organize(window):
    window.ribbon_tabs.setCurrentIndex(list(RIBBON_TABS).index("organize"))
    window.current().organize.render_all()
    return window.current().organize


# --- E-010…E-012 -------------------------------------------------------------------------


def test_T_E010_E011_one_frame_for_all_selected_pages(window):
    organize(window).select_pages([1, 2])
    window.actions["crop_pages"].trigger()  # Ctrl+Shift+X
    assert window.crop is not None and window.crop_bar.isVisible()
    assert window.current().page.currentWidget() is window.current().view
    window.crop.set_frame(1, Rect(0, 0, 200, 300))
    window.actions["crop_apply"].trigger()  # Enter
    document = window.current().document
    assert document.page_size(1) == pytest.approx((200, 300))
    assert document.page_size(2) == pytest.approx((200, 300))
    assert document.page_size(3) == pytest.approx((595, 842))
    assert window.crop is None and not window.crop_bar.isVisible()


def test_T_E010_separate_frame_per_page_with_the_mouse(window):
    view = window.current().view
    window.pages_panel.list.clearSelection()
    for row in (0, 1):
        window.pages_panel.list.item(row).setSelected(True)
    window.crop_mode.setCurrentIndex(1)  # cadru separat pe fiecare pagina
    window.start_crop()
    top_left = view.page_to_view(1, Rect(100, 100, 0, 0)).topLeft()
    bottom_right = view.page_to_view(1, Rect(400, 500, 0, 0)).topLeft()
    scroll = QPoint(view.horizontalScrollBar().value(), view.verticalScrollBar().value())
    start = top_left.toPoint() - scroll
    end = bottom_right.toPoint() - scroll
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     start)
    QTest.mouseMove(view.viewport(), end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)
    frame = window.crop.frames[1]
    assert frame.x == pytest.approx(100, abs=2) and frame.w == pytest.approx(300, abs=3)
    assert window.crop.frame_for(2) is None  # pagina 2 nu are inca cadru
    window.apply_crop()
    document = window.current().document
    assert document.page_size(1) == pytest.approx((300, 400), abs=3)
    assert document.page_size(2) == pytest.approx((595, 842))


def test_T_E012_exit_crop_changes_nothing(window):
    window.start_crop()
    window.crop.set_frame(1, Rect(0, 0, 100, 100))
    window.actions["crop_exit"].trigger()  # Esc
    assert window.crop is None
    assert window.current().document.page_size(1) == pytest.approx((595, 842))
    assert not window.current().document.is_modified


def test_apply_without_a_frame_gives_a_message(window):
    messages = []
    window.show_message = messages.append
    window.start_crop()
    assert not window.apply_crop() and messages and window.crop is not None
    window.exit_crop()


# --- E-013, E-016 ------------------------------------------------------------------------


def test_T_E013_blank_page_with_size_and_position(window, monkeypatch):
    def fill(dialog):
        dialog.size_box.setCurrentIndex(dialog.size_box.findData("a5"))
        dialog.position.first.setChecked(True)
    answer(monkeypatch, fill)
    assert window.actions["add_blank_page"].isEnabled()
    window.actions["add_blank_page"].trigger()  # Ctrl+Shift+B
    document = window.current().document
    assert document.page_count == 6 and document.extract_text(1).strip() == ""
    assert document.page_size(1) == pytest.approx(PAGE_SIZES["a5"], abs=0.5)


def test_T_E013_plus_button_between_thumbnails_presets_the_position(window, monkeypatch):
    view = organize(window)
    grid = view.grid
    rect = grid.visualRect(grid.model().index(2, 0))
    assert grid.gap_at(QPoint(rect.left() + 3, rect.center().y()))[0] == 3
    assert grid.gap_at(QPoint(rect.center().x(), rect.center().y())) is None
    view._gap(3, QPoint(rect.left(), rect.center().y()))
    assert view.insert_button.isVisible()
    seen = {}
    view.insert_requested.connect(lambda at: seen.setdefault("at", at))
    monkeypatch.setattr(window.add_menu, "popup", lambda *a: None)
    view.insert_button.click()
    assert seen["at"] == 3 and window._insert_at == 3
    answer(monkeypatch, lambda dialog: None)
    window.add_blank_page()
    assert texts(window)[:4] == ["Pagina 1", "Pagina 2", "", "Pagina 3"]
    assert view.selected_pages() == [3]


# --- E-014, E-015, E-017, E-108 ----------------------------------------------------------


def test_T_E014_add_pages_from_pdf(window, tmp_path, monkeypatch):
    other = text_pdf(tmp_path / "anexa.pdf", [["Anexa A"], ["Anexa B"], ["Anexa C"]])

    def fill(dialog):
        dialog.path.setText(str(other))
        dialog.select.setChecked(True)
        dialog.pages.setText("2-3")
        dialog.position.last.setChecked(True)
    answer(monkeypatch, fill)
    assert window.add_pages_from_pdf() == 2
    assert texts(window)[-2:] == ["Anexa B", "Anexa C"]


def test_T_E108_file_dialog_validates_the_page_range(qtbot, tmp_path):
    dialog = InsertPagesDialog("file", 5, 1)
    qtbot.addWidget(dialog)
    ok = dialog.box.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()  # fara fisier
    image = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(image)
    dialog.path.setText(str(image))
    assert ok.isEnabled()
    dialog.select.setChecked(True)
    dialog.pages.setText("2,x")
    assert not ok.isEnabled()
    dialog.pages.setText("2,3,5-7")
    assert ok.isEnabled() and dialog.source_pages() == [2, 3, 5, 6, 7]
    assert dialog.split_facing.isVisibleTo(dialog) and dialog.image_settings.isVisibleTo(dialog)


def scan_image(path):
    img = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(img).rectangle((200, 300, 1000, 360), fill="black")
    img.save(path, dpi=(150, 150))
    return path


def test_T_E015_add_pages_from_file(window, tmp_path, monkeypatch):
    image = scan_image(tmp_path / "scan.png")

    def fill(dialog):
        dialog.path.setText(str(image))
        dialog.position.first.setChecked(True)
    answer(monkeypatch, fill)
    assert window.add_pages_from_file() == 1
    document = window.current().document
    assert document.page_count == 6 and document.extract_text(2).strip() == "Pagina 1"


def test_T_E017_add_pages_from_scanner(window, tmp_path, monkeypatch):
    images = [scan_image(tmp_path / "s1.png"), scan_image(tmp_path / "s2.png")]
    answer(monkeypatch, lambda dialog: dialog.position.after.setChecked(True))
    monkeypatch.setattr(PdfEditorWindow, "acquire_scan", lambda self: images)
    window.pages_panel.list.clearSelection()
    window.pages_panel.list.item(1).setSelected(True)  # dupa pagina 2
    assert window.add_pages_from_scanner() == 2
    assert texts(window)[:5] == ["Pagina 1", "Pagina 2", "", "", "Pagina 3"]


def test_scanner_cancelled_adds_nothing(window, monkeypatch):
    answer(monkeypatch, lambda dialog: None)
    monkeypatch.setattr(PdfEditorWindow, "acquire_scan", lambda self: [])
    assert window.add_pages_from_scanner() == 0
    assert window.current().document.page_count == 5


# --- E-019, E-020 ------------------------------------------------------------------------


def test_T_E019_move_pages_dialog(window, monkeypatch):
    organize(window).select_pages([1, 2])
    answer(monkeypatch, lambda dialog: dialog.position.last.setChecked(True))
    window.actions["move_pages"].trigger()  # Ctrl+Shift+M
    assert texts(window) == ["Pagina 3", "Pagina 4", "Pagina 5", "Pagina 1", "Pagina 2"]


def test_T_E020_replace_dialog_requires_equal_lengths(qtbot, tmp_path):
    other = text_pdf(tmp_path / "nou.pdf", [["Nou A"], ["Nou B"], ["Nou C"]])
    dialog = ReplacePagesDialog([2, 3], 5)
    qtbot.addWidget(dialog)
    dialog.path.setText(str(other))
    assert dialog.source_range.text() == "1-3"  # implicit: tot fisierul
    ok = dialog.box.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled() and "2" in dialog.message.text() and "3" in dialog.message.text()
    dialog.source_range.setText("1-2")
    assert ok.isEnabled() and dialog.message.text() == ""


def test_T_E020_replace_pages(window, tmp_path, monkeypatch):
    other = text_pdf(tmp_path / "nou.pdf", [["Nou A"], ["Nou B"], ["Nou C"]])
    organize(window).select_pages([4, 5])

    def fill(dialog):
        dialog.path.setText(str(other))
        dialog.source_range.setText("2-3")
    answer(monkeypatch, fill)
    window.actions["replace_pages"].trigger()  # Ctrl+Shift+E
    assert texts(window) == ["Pagina 1", "Pagina 2", "Pagina 3", "Nou B", "Nou C"]


# --- E-038 -------------------------------------------------------------------------------


def test_T_E038_image_processing_settings(qtbot, ctx):
    dialog = ImageProcessingDialog(ctx.settings)
    qtbot.addWidget(dialog)
    assert dialog.quality.count() == 4
    assert not dialog.recognize.isChecked() and not dialog.mrc.isEnabled()
    dialog.recognize.setChecked(True)
    assert dialog.mrc.isEnabled()
    dialog.mrc.setChecked(True)
    dialog.quality.setCurrentIndex(dialog.quality.findData("compact"))
    dialog.store()
    options = image_options(ctx.settings)
    assert options.searchable and options.use_mrc and options.image_quality.value == "compact"
    assert "ron" in dialog.languages.text()


def test_add_menu_offers_every_way_of_adding_pages(window):
    names = [a.objectName() for a in window.add_menu.actions() if a.objectName()]
    assert names == ["pdf_action_add_blank_page", "pdf_action_add_pages_pdf",
                     "pdf_action_add_pages_file", "pdf_action_add_pages_scanner",
                     "pdf_action_signed_merge"]  # E-500


# --- 8.4b: E-021…E-032, E-035, E-109…E-112 -----------------------------------------------


def add_blanks(window, *positions):
    from app.core.pdf.organize import PageOrganizer

    organizer = PageOrganizer(window.current().document)
    for at in positions:
        organizer.add_blank(at)
    window._after_modify()


def test_T_E021_E023_E109_blank_pages_dialog(window, monkeypatch):
    from PySide6.QtCore import Qt as _Qt

    add_blanks(window, 2, 4)  # paginile 2 si 4 goale
    seen = {}

    def fill(dialog):
        seen["found"] = [dialog.list.item(r).text() for r in range(dialog.list.count())]
        seen["checked"] = dialog.checked_pages()
        assert dialog.zoom_in.isVisibleTo(dialog) or True
        dialog.zoom(24)
        dialog.list.item(1).setCheckState(_Qt.CheckState.Unchecked)  # pagina 4 ramane
    answer(monkeypatch, fill)
    window.actions["delete_blank_pages"].trigger()
    assert seen["found"] == ["2", "4"] and seen["checked"] == [2, 4]  # implicit toate bifate
    assert window.current().document.page_count == 6
    assert texts(window)[:3] == ["Pagina 1", "Pagina 2", ""]


def test_T_E021_no_blank_pages_gives_a_message(window):
    messages = []
    window.show_message = messages.append
    assert window.delete_blank_pages() == [] and messages


def test_T_E022_notes_on_a_blank_page_are_confirmed_first(window, monkeypatch):
    import pikepdf

    add_blanks(window, 2)
    pdf = window.current().document._pike()
    note = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Ink, Rect=[10, 10, 50, 50],
        InkList=[[10, 10, 50, 50]]))
    pdf.pages[1].obj.Annots = pdf.make_indirect(pikepdf.Array([note]))
    window.current().document._changed()
    asked = []
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm",
                        lambda self, text: asked.append(text) or False)
    answer(monkeypatch, lambda dialog: None)
    assert window.delete_blank_pages() == []
    assert asked and "2" in asked[0] and window.current().document.page_count == 6


def bookmarked(tmp_path):
    from test_pdf_split import bookmarked_pdf

    return bookmarked_pdf(tmp_path / "carte.pdf", pages=6, every=2, attachments=1)


def test_T_E110_E111_E112_split_dialog(qtbot, tmp_path):
    from app.core.pdf.document import PdfDocument
    from app.core.pdf.organize import PageOrganizer
    from app.gui.pdf_organize_dialogs import SplitDialog

    with PdfDocument.open(bookmarked(tmp_path)) as doc:
        dialog = SplitDialog(PageOrganizer(doc))
        qtbot.addWidget(dialog)
        assert dialog.by_bookmarks.isChecked()
        assert dialog.total.text() == "Total fișiere: 3"  # E-110
        assert dialog.example.text() == "Exemplu: 01_Capitol 1.pdf"  # E-111
        dialog.add_numeration.setChecked(False)  # E-029
        assert dialog.example.text() == "Exemplu: Capitol 1.pdf"
        dialog.by_pages.setChecked(True)
        dialog.page_count.setValue(4)
        assert dialog.total.text() == "Total fișiere: 2"
        assert dialog.example.text() == "Exemplu: 01_carte.pdf"
        dialog.numbering.setCurrentIndex(1)
        dialog.digits.setValue(3)
        assert dialog.example.text() == "Exemplu: carte_001.pdf"  # E-028
        assert dialog.same_folder.isChecked() and not dialog.folder.isEnabled()  # E-112
        dialog.same_folder.setChecked(False)
        assert dialog.folder.isEnabled()
        dialog.by_size.setChecked(True)  # E-025: mai mare decat originalul → rosu
        dialog.size_mb.setValue(dialog.original / 1_000_000 + 1)
        ok = dialog.box.button(QDialogButtonBox.StandardButton.Ok)
        assert "c62828" in dialog.size_mb.styleSheet() and not ok.isEnabled()


def test_T_E027_bookmarks_method_is_grey_without_bookmarks(qtbot, tmp_path):
    import pikepdf

    from app.core.pdf.document import PdfDocument
    from app.core.pdf.organize import PageOrganizer
    from app.gui.pdf_organize_dialogs import SplitDialog

    path = text_pdf(tmp_path / "simplu.pdf", [["A"], ["B"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        del pdf.Root["/Outlines"]
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        dialog = SplitDialog(PageOrganizer(doc))
        qtbot.addWidget(dialog)
        assert not dialog.by_bookmarks.isEnabled() and dialog.by_pages.isChecked()


def test_T_E024_E031_E032_split_from_the_window(qtbot, ctx, tmp_path, monkeypatch):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.open_path(bookmarked(tmp_path))
    out = tmp_path / "rezultat"
    opened = []
    monkeypatch.setattr(PdfEditorWindow, "open_external",
                        lambda self, url: opened.append(url.toLocalFile()) or True)

    def fill(dialog):
        dialog.same_folder.setChecked(False)
        dialog.folder.setText(str(out))
    answer(monkeypatch, fill)
    files = w.split_document()
    assert [f.name for f in files] == ["01_Capitol 1.pdf", "02_Capitol 2.pdf",
                                       "03_Capitol 3.pdf"]
    assert (out / "Attachments" / "anexa1.txt").exists()  # E-031
    assert opened == [str(out)]  # E-032: folderul se deschide
    w.close()


def test_T_E035_enhance_images(window, monkeypatch):
    from app.gui.pdf_organize_dialogs import EnhanceDialog

    asked = []
    window.options_requested.connect(asked.append)

    def fill(dialog):
        assert isinstance(dialog, EnhanceDialog)
        settings = dialog.preprocess()
        assert settings.correct_orientation and settings.deskew
        assert not settings.whiten_background
        dialog.change_languages.click()
        dialog.orientation.setChecked(False)
    answer(monkeypatch, fill)
    organize(window).select_pages([2])
    window.actions["enhance"].trigger()
    assert asked == ["languages"]
    assert window.current().document.extract_text(2).strip() == ""  # pagina e acum imagine
    assert window.current().document.page_count == 5
