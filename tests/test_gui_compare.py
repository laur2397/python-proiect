"""Fereastra de comparare (faza 12, pasul 12.4): R-001…R-068, R-300, R-400…R-416."""

from __future__ import annotations

import os
import zipfile

import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.gui.compare_window import (
    MENUS,
    SHORTCUTS,
    AdvancedDialog,
    CompareWindow,
    SaveDialog,
)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx):
    w = CompareWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.show_message = lambda text: w.messages.append(text)
    w.messages = []
    yield w
    w.close()


@pytest.fixture
def pair(tmp_path):
    left = text_pdf(tmp_path / "v1.pdf", [["Termenul este 30 zile", "Pret 10 lei"],
                                          ["Anexa 1"]])
    right = text_pdf(tmp_path / "v2.pdf", [["Termenul este 45 zile", "Pret 10 lei"],
                                           ["Anexa 1", "Clauza noua"]])
    return left, right


def compared(window, pair):
    assert window.open_pair(*pair)
    return window.compare()


# --- R-001…R-010, R-300, R-400…R-405 ---------------------------------------------------------


def test_T_R300_menus_and_shortcuts(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles == ["Fișier", "Editare", "Vizualizare", "Comparare", "Ajutor"]
    assert set(MENUS) == {"file", "edit", "view", "compare", "help"}
    for key in ("compare", "next_difference", "previous_difference", "ignore", "select_all",
                "fit_width", "new", "close"):
        assert window.actions[key].shortcut().toString() != "", key
    assert SHORTCUTS["compare"] == "Ctrl+R" and SHORTCUTS["ignore"] == "Del"


def test_T_R002_R009_R010_R400_open_close_new(window, pair, tmp_path):
    left, right = pair
    assert not window.actions["compare"].isEnabled()
    assert window.load(1, left)
    assert window.areas[0].source is not None and window.areas[0].counter.text() == "1 / 2"
    assert window.load(2, right)
    assert window.windowTitle().startswith("v1.pdf / v2.pdf")  # R-400
    assert window.actions["compare"].isEnabled()
    window.close_document(1)  # R-009
    assert window.areas[0].source is None
    window.new_comparison()  # R-010
    assert all(a.source is None for a in window.areas)
    (tmp_path / "x.vsdx").write_bytes(b"x")
    assert not window.load(1, tmp_path / "x.vsdx") and window.messages  # format nesuportat


def test_T_R004_switching_areas(window, pair):
    window.open_pair(*pair)
    window.actions["area_1"].trigger()
    assert window.active == 1
    window.actions["switch_area"].trigger()
    assert window.active == 2


def test_T_R005_different_formats(window, pair, tmp_path):
    import docx

    document = docx.Document()
    document.add_paragraph("Termenul este 45 zile")
    document.add_paragraph("Pret 10 lei")
    document.save(tmp_path / "v2.docx")
    assert window.open_pair(pair[0], tmp_path / "v2.docx")
    texts = [(d.text_left, d.text_right) for d in window.compare()]
    assert ("30", "45") in texts


# --- R-017, R-034, R-043…R-046, R-405, R-407…R-413 ---------------------------------------------


def test_T_R017_R043_R405_R407_compare_and_list(window, pair):
    result = compared(window, pair)
    assert [(d.text_left, d.text_right) for d in result] == [("30", "45"),
                                                              (None, "Clauza noua")]
    assert window.panel.tabText(1) == "Diferențe (2)"
    assert window.band.isVisible() and window.band.text() == "Diferențe găsite: 2"
    top = window.tree.topLevelItem(0)
    assert top.text(0) == "Corpul textului (2)" and top.childCount() == 2  # R-409
    first = top.child(0)
    assert "Text modificat" in first.text(0) and "− 30" in first.text(0)  # R-410, R-411
    assert "+ 45" in first.text(0) and first.text(1) == "Pg. 1"


def test_T_R043_identical_documents(window, pair):
    window.open_pair(pair[0], pair[0])
    assert window.compare() == [] and window.band.text() == "Diferențe găsite: 0"


def test_T_R034_grouping_can_be_turned_off(window, pair):
    compared(window, pair)
    window.group_button.setChecked(False)
    assert window.tree.topLevelItemCount() == 2
    assert window.tree.topLevelItem(0).childCount() == 0


def test_T_R045_navigation(window, pair):
    result = compared(window, pair)
    assert window.current == result[0].order_index
    window.actions["next_difference"].trigger()
    assert window.current == result[1].order_index
    view = window.areas[1].view  # ambele zone sar la loc: diferenta se vede
    box = view.page_to_view(2, result[1].bbox_right).translated(-view._offset())
    assert view.viewport().rect().contains(box.toRect())
    window.actions["previous_difference"].trigger()
    assert window.current == result[0].order_index


def test_T_R046_synchronized_scrolling(window, pair):
    compared(window, pair)
    assert window.actions["synchronize"].isChecked()  # activa implicit
    left, right = (a.view.verticalScrollBar() for a in window.areas)
    left.setValue(left.maximum())
    assert right.value() == right.maximum()
    window.actions["synchronize"].trigger()
    left.setValue(0)
    assert right.value() == right.maximum()


def test_T_R041_split_horizontally(window):
    from PySide6.QtCore import Qt

    window.actions["split_horizontally"].trigger()
    assert window.splitter.orientation() == Qt.Orientation.Vertical


# --- R-047…R-050 -------------------------------------------------------------------------------


def test_T_R047_R048_R049_R050_copy_ignore_select(window, pair):
    result = compared(window, pair)
    window.go_to(result[0].order_index)
    assert window.copy_difference() == "30 → 45"
    assert QApplication.clipboard().text() == "30 → 45"
    window.select_all()
    assert len(window.selected_indices()) == 2  # R-050
    window.tree.clearSelection()
    window.go_to(result[0].order_index)
    assert window.ignore_selected() == 1  # R-048
    assert window.panel.tabText(1) == "Diferențe (1)"
    window.undo()
    assert window.panel.tabText(1) == "Diferențe (2)"
    window.redo()
    assert window.panel.tabText(1) == "Diferențe (1)"


def test_T_R049_ignore_identical(window, tmp_path):
    left = text_pdf(tmp_path / "a.pdf", [["Pret 10 lei", "Taxa 10 lei", "Suma 5 lei"]])
    right = text_pdf(tmp_path / "b.pdf", [["Pret 20 lei", "Taxa 20 lei", "Suma 6 lei"]])
    window.open_pair(left, right)
    window.compare()
    assert window.ignore_identical() == 2
    assert window.panel.tabText(1) == "Diferențe (1)"


# --- R-020…R-023 ----------------------------------------------------------------------------------


def test_T_R020_R023_advanced_options(window, monkeypatch, qtbot):
    dialog = AdvancedDialog(window.options)
    qtbot.addWidget(dialog)
    assert dialog.mode.currentData() == "text" and dialog.headers.isChecked()
    dialog.mode.setCurrentIndex(2)
    dialog.headers.setChecked(False)
    dialog.reset()  # R-023
    assert dialog.mode.currentData() == "text" and dialog.headers.isChecked()

    def run(self, d):
        d.mode.setCurrentIndex(d.mode.findData("ocr"))
        return True
    monkeypatch.setattr(CompareWindow, "exec_dialog", run)
    assert window.advanced() and window.options.pdf_mode == "ocr"


# --- R-060…R-068 ----------------------------------------------------------------------------------


def test_T_R060_R062_save_dialog(qtbot):
    dialog = SaveDialog("pdf_comments")
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.kind.currentData() == "pdf_comments"  # ultimul folosit
    assert not dialog.warning.isVisible()
    dialog.kind.setCurrentIndex(dialog.kind.findData("track_changes"))
    assert dialog.warning.isVisible()  # R-062: inainte de salvare


def test_T_R061_R063_R064_save_from_the_window(window, pair, tmp_path, monkeypatch):
    compared(window, pair)
    chosen = {"kind": "report", "which": 1}

    def run(self, dialog):
        dialog.kind.setCurrentIndex(dialog.kind.findData(chosen["kind"]))
        dialog.document.setCurrentIndex(dialog.document.findData(chosen["which"]))
        return True
    monkeypatch.setattr(CompareWindow, "exec_dialog", run)
    names = []

    def target(self, kind, suggested):
        names.append(suggested)
        return tmp_path / f"{len(names)}{'.pdf' if kind == 'pdf_comments' else '.docx'}"
    monkeypatch.setattr(CompareWindow, "ask_save_target", target)
    [report] = window.save()
    assert names == ["Diferențe"]  # R-415
    assert report.suffix == ".docx" and window.settings.get("compare.last_save") == "report"
    chosen.update(kind="track_changes", which=0)
    assert len(window.save()) == 2  # R-061: cate un fisier per document
    chosen.update(kind="pdf_comments", which=2)
    [pdf] = window.save()
    assert pdf.suffix == ".pdf"
    with zipfile.ZipFile(tmp_path / "2.docx") as archive:
        assert "<w:ins " in archive.read("word/document.xml").decode()


def test_T_R068_print(window, pair, monkeypatch):
    compared(window, pair)
    seen = []
    monkeypatch.setattr(CompareWindow, "choose_print", lambda self, d: seen.append(d) or None)
    assert window.print_result() == 0 and len(seen) == 1


# --- R-006, R-001 -----------------------------------------------------------------------------------


def test_T_R006_recent_comparisons_menu(window, pair):
    compared(window, pair)
    entries = [a.text() for a in window.recent_menu.actions()]
    assert entries == ["v1.pdf  ↔  v2.pdf"]
    pair[1].unlink()
    window._refresh_recent()
    action = window.recent_menu.actions()[0]
    assert "(fișier lipsă)" in action.text() and not action.isEnabled()


def test_T_R001_opened_from_the_application(ctx, qtbot, pair):
    from app.gui.application import Application

    app = Application(ctx)
    window = app.open_compare(pair[0], None)
    qtbot.addWidget(window)
    assert window.areas[0].source is not None and window.areas[1].source is None
    editor = app.pdf_editor
    qtbot.addWidget(editor)
    editor.open_path(pair[1])
    editor.actions["compare"].trigger()
    assert window.areas[0].source.path == pair[1]
    window.close()
