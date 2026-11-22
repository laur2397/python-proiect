"""Panoul de cautare al PDF Editor-ului (faza 7, pasul 7.8a): C-001…C-011,
C-015…C-018, C-025…C-032, C-100…C-111."""

from __future__ import annotations

import os

import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

from app.core.context import AppContext
from app.core.model import AnnotationType
from app.core.paths import AppPaths
from app.core.pdf.keywords import Keyword
from app.gui.pdf_editor import PdfEditorWindow
from app.gui.pdf_search import SearchPanel


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [
        ["Cerere de finantare", "Bugetul total: 1200 lei"],
        ["Anexa 2: buget detaliat", "Bugetare si BUGET"],
    ])
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(path)
    yield w
    w.close()


def search(window, text, **options):
    panel = window.search_panel
    window.actions["find"].trigger()
    panel.exact_match.setChecked(options.get("exact", False))
    panel.match_case.setChecked(options.get("case", False))
    panel.field.setText(text)
    panel.field.returnPressed.emit()
    return panel


def groups(panel):
    return [panel.tree.topLevelItem(i).text(0) for i in range(panel.tree.topLevelItemCount())]


# --- C-001, C-100…C-111 ---------------------------------------------------------------


def test_T_C001_1_ctrl_f_opens_the_find_tab(window):
    panel = window.search_panel
    window.actions["find"].trigger()
    assert window.nav_stack.currentWidget() is panel and window.nav_stack.isVisible()
    assert panel.tab_bar.currentIndex() == 0
    assert [panel.tab_bar.tabText(i) for i in range(3)] == ["CAUTĂ", "ÎNLOCUIEȘTE",
                                                            "REDACTEAZĂ"]  # C-101
    window.actions["redaction_mode"].trigger()  # Ctrl+Shift+H
    assert panel.tab_bar.currentIndex() == 2 and panel.keyword_box.isVisible()
    assert panel.keyword_combo.lineEdit().placeholderText().startswith("Scrieți text")  # C-111
    panel.findChild(QToolButton, "search_close").click()
    assert not window.nav_stack.isVisible()


def test_T_C002_1_results_grouped_by_source_with_context(window):
    panel = search(window, "buget")
    assert groups(panel) == ["Textul documentului (4)", "Comentarii (1)",
                             "Semne de carte (1)"]
    first = panel.tree.topLevelItem(0).child(0)
    label = panel.tree.itemWidget(first, 0)
    assert isinstance(label, QLabel) and "background:#ffd84d" in label.text()  # C-105
    assert first.text(1) == "1"
    assert panel.status.text() == "Găsite: 6"  # C-109


def test_T_C003_C004_matching_options(window):
    panel = search(window, "buget", exact=True)
    assert panel.tree.topLevelItem(0).text(0) == "Textul documentului (2)"
    panel = search(window, "BUGET", case=True)
    assert groups(panel) == ["Textul documentului (1)"]


def test_T_C109_1_no_matches_message(window):
    panel = search(window, "inexistent")
    assert panel.status.text() == "Găsite: 0"
    assert panel.empty.isVisible() and not panel.tree.isVisible()


def test_T_C005_1_navigation_between_results(window):
    panel = search(window, "buget")  # pagina 1: Bugetul; pagina 2: buget, Bugetare, BUGET
    view = window.current().view
    assert panel.index == 0 and view.current_page == 1
    panel.next_button.click()
    assert panel.index == 1 and view.current_page == 2
    for _ in range(3):
        window.actions["find_next"].trigger()  # F3; dupa ultimul revine la primul
    assert panel.index == 4 % len(panel.hits)
    panel.previous_button.click()
    assert panel.index == 3 % len(panel.hits)


def test_T_C106_C103_checking_results(window):
    panel = search(window, "buget")
    assert not panel.replace_button.isEnabled() and not panel.redact_button.isEnabled()
    panel.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)  # parintele
    assert len(panel.checked_hits()) == 4
    assert panel.replace_button.isEnabled()
    panel.set_checked([0], checked=False)
    assert len(panel.checked_hits()) == 3


def test_T_C108_1_all_results_highlighted_in_the_page(window):
    panel = search(window, "buget", exact=True)
    view = window.current().view
    view.go_to_page(2)
    QApplication.processEvents()
    image = view.viewport().grab().toImage()
    offset = QPointF(view.horizontalScrollBar().value(), view.verticalScrollBar().value())
    tinted = 0
    for hit in [h for h in panel.hits if h.page == 2]:  # toate, nu doar cel curent
        box = view.page_to_view(hit.page, hit.rects[0]).translated(-offset)
        pixels = [image.pixelColor(x, y) for x in range(int(box.left()) + 1, int(box.right()))
                  for y in range(int(box.top()) + 1, int(box.bottom()))]
        if any(c.red() > 240 and c.green() > 220 and c.blue() < 200 for c in pixels):
            tinted += 1
    assert tinted == 2


# --- C-007…C-010 ----------------------------------------------------------------------


def test_T_C007_1_mark_checked_results(window):
    panel = search(window, "buget", exact=True)
    panel.set_checked()
    document = window.current().document
    before = len(document.annotations())
    assert panel.mark(AnnotationType.HIGHLIGHT) == 2
    assert len(document.annotations()) == before + 2
    assert document.is_modified and window.windowTitle().startswith("dosar.pdf*")
    assert window.actions["comments_pane"].text() == f"Comentarii ({before + 2})"


def test_T_C010_1_marking_color_becomes_the_default(window, ctx, monkeypatch):
    panel = window.search_panel
    monkeypatch.setattr(SearchPanel, "ask_color", lambda self, current: "#123456")
    panel.choose_color(AnnotationType.UNDERLINE)
    assert ctx.settings.get("pdf_editor.markup_color.underline") == "#123456"
    assert panel.color_for(AnnotationType.UNDERLINE) == "#123456"


# --- C-015…C-018 ----------------------------------------------------------------------


def test_T_C015_C016_replace_removes_results(window):
    panel = search(window, "1200")
    panel.tab_bar.setCurrentIndex(1)
    panel.replace_field.setText("1500")
    panel.set_checked([0])
    assert panel.replace() == 1
    document = window.current().document
    assert "1500" in document.extract_text(1) and "1200" not in document.extract_text(1)
    assert panel.hits == [] and panel.status.text() == "Găsite: 0"  # C-110
    assert panel.empty.isVisible()


def test_T_C018_1_uneven_background_asks_first(window, monkeypatch):
    from app.core.pdf import redact

    panel = search(window, "1200")
    panel.set_checked([0])
    monkeypatch.setattr(redact, "background_is_uniform", lambda *a: False)
    asked = []
    monkeypatch.setattr(SearchPanel, "ask_confirm",
                        lambda self, text: asked.append(text) or False)
    assert panel.replace() == 0
    assert asked and "1200" in window.current().document.extract_text(1)


# --- C-025, C-026 ---------------------------------------------------------------------


def test_T_C026_1_redact_checked_results(window):
    panel = search(window, "buget", exact=True)
    panel.tab_bar.setCurrentIndex(2)
    panel.set_checked()
    assert panel.redact() == 2
    document = window.current().document
    assert document.search("buget", whole_word=True, in_comments=False,
                           in_bookmarks=False, in_metadata=False) == []
    assert panel.hits == []


# --- C-027…C-032 ----------------------------------------------------------------------


def test_T_C027_C028_keyword_lists(window, monkeypatch):
    panel = search(window, "1200")
    monkeypatch.setattr(SearchPanel, "ask_list_name", lambda self: "Sume")
    panel.add_keyword_to_list()  # C-027
    panel.field.setText("lei")
    panel.add_keyword_to_list()
    assert [k.text for k in panel.store.keywords("Sume")] == ["1200", "lei"]
    assert panel.keyword_combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "1200, lei"  # C-031
    panel.close_keyword_list()  # C-032
    assert panel.active_list is None
    panel.find_using_list("Sume")  # C-028
    assert [h.found for h in panel.hits] == ["1200", "lei"]


def test_T_C029_C030_edit_list_and_find(window, monkeypatch):
    panel = window.search_panel
    panel.store.save("Dosar", [Keyword("Cerere")])

    def edit(self, dialog):
        dialog.word.setText("Anexa")
        dialog.add_current()
        dialog.list.setCurrentRow(0)
        dialog.remove_selected()
        dialog.find_after = True  # `Save and Find`
        return True

    monkeypatch.setattr(SearchPanel, "exec_dialog", edit)
    panel.active_list = "Dosar"
    panel.edit_keyword_list()
    assert [k.text for k in panel.store.keywords("Dosar")] == ["Anexa"]
    assert [h.found for h in panel.hits] == ["Anexa"]


def test_switching_documents_clears_results(window, tmp_path):
    panel = search(window, "buget")
    assert panel.hits
    window.open_path(text_pdf(tmp_path / "alt.pdf", [["Altceva"]]))
    assert panel.hits == []
