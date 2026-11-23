"""Compararea: cerintele R fara test pana acum: al doilea document (R-003),
alinierea cu ancore (R-031), zonele de afisare (R-040), zoom-ul (R-042),
conformitatea fisierului rezultat (R-066) si aspectul ferestrei (R-401…R-404,
R-406, R-408, R-412)."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_compare import built
from test_gui_compare import compared, ctx, pair, window  # noqa: F401
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.compare.engine import compare_sources
from app.core.model import CompareOptions, DiffType
from app.core.pdf.document import PdfDocument
from app.gui.compare_window import PANEL_WIDTH, SHORTCUTS
from app.gui.i18n import tr


def test_T_R003_second_document_four_ways(window, pair, monkeypatch):  # noqa: F811
    _left, right = pair
    monkeypatch.setattr(type(window), "ask_open_path", lambda self, index: right)
    assert window.ask_open(2)  # bara zonei 2, `File > Open Document...`, clic in zona
    assert window.areas[1].source is not None and window.areas[0].source is None
    window.areas[1].close_requested.emit()
    assert window.areas[1].source is None
    window.areas[1].recent_chosen.emit(right)  # recentele zonei 2
    assert window.areas[1].source is not None


def test_T_R031_long_documents_align_on_identical_paragraphs():
    def word(n: int) -> str:  # cuvinte diferite: cifrele nu deosebesc randurile (R-022)
        return "".join(chr(97 + (n * 7 + i * 3) % 26) for i in range(7))

    paragraphs = [("body", f"Articolul {word(n)} stabileste clauza {word(n + 50)}.")
                  for n in range(1, 41)]
    changed = list(paragraphs)
    changed.insert(20, ("body", "Articol nou introdus la mijloc."))
    changed[35] = ("body", f"Articolul {word(35)} stabileste clauza modificata.")
    result = compare_sources(built(paragraphs), built(changed), CompareOptions())
    assert [d.diff_type for d in result] == [DiffType.INSERTED, DiffType.REPLACED]
    assert result[1].text_right.startswith("modificata")  # restul ramane aliniat


def test_T_R040_two_display_areas(window):  # noqa: F811
    assert [a.index for a in window.areas] == [1, 2]
    assert window.areas[0].isVisible() and window.areas[1].isVisible()  # alaturate
    assert SHORTCUTS["area_1"] == "Alt+1" and SHORTCUTS["area_2"] == "Alt+2"


def test_T_R042_zoom_shortcuts(window):  # noqa: F811
    shortcuts = [k.toString() for k in window.actions["zoom_in"].shortcuts()]
    assert {"Ctrl++", "Ctrl+="} <= set(shortcuts)
    assert window.actions["zoom_out"].shortcut().toString() == "Ctrl+-"
    assert window.actions["fit_width"].shortcut().toString() == "Ctrl+0"


def test_T_R066_conformance_shown_in_document_properties(tmp_path):
    path = text_pdf(tmp_path / "rezultat.pdf", [["Raport de comparare"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            meta["pdfaid:part"] = "2"
            meta["pdfaid:conformance"] = "B"
        pdf.save(path)
    props = PdfDocument.open(path).properties()
    assert props["pdfa"] == "PDF/A-2b"


def test_T_R401_R402_R403_area_bars(window, pair):  # noqa: F811
    area = window.areas[0]
    area.set_recent([pair[1]])  # sageata cu documentele recente
    assert any(str(pair[1]) in (area.path.itemData(i) or area.path.itemText(i))
               for i in range(area.path.count()))
    assert tr("compare.loading") in area.loading.text()
    assert set(area.buttons) == {"previous_page", "next_page", "zoom_out", "fit_width",
                                 "zoom_in"}
    assert area.sync.isCheckable()
    window.load(1, pair[0])
    assert area.counter.text() == "1 / 2"


def test_T_R404_R406_panel_and_compare_button(window):  # noqa: F811
    assert 150 <= PANEL_WIDTH <= 190  # circa 170 px
    button = window.compare_button
    assert "background: #2f6df6" in button.styleSheet() and button.minimumHeight() >= 40


def test_T_R408_R412_differences_toolbar_and_selection(window, pair):  # noqa: F811
    assert window.save_button.text().startswith("W")
    assert window.save_button.menu() is not None  # `Save... ▾`
    names = {b.objectName() for b in window.findChildren(type(window.group_button))}
    assert {"compare_bar_next_difference", "compare_bar_previous_difference",
            "compare_bar_ignore", "compare_group_button"} <= names
    assert "#c9d3e6" in window.tree.styleSheet()
    assert compared(window, pair)
    QApplication.processEvents()
