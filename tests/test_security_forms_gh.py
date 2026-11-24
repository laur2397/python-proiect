"""Securitate si formulare: cerintele G si H fara test pana acum: semnatura
(G-034, G-038, G-106), textul redactat (G-102), formatul proprietatilor
documentului (G-109) si comenzile de fereastra ale butoanelor de formular
(H-051…H-056)."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image
from test_gui_pdf_forms import ctx, window  # noqa: F401
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.pdf.document import PdfDocument
from app.core.pdf.form_actions import ACTION_GROUPS
from app.core.pdf.security import SecurityService
from app.gui.i18n import tr
from app.gui.pdf_content import PropertiesDialog, file_size_text
from app.gui.pdf_editor import PdfEditorWindow


def test_T_G034_G038_G106_signature_fields_and_appearance_flags(qtbot, window):  # noqa: F811
    from app.core.model import Rect
    from app.gui.pdf_security_ui import SignDialog

    dialog = SignDialog(window._signature_service(), window.settings, 1, Rect(50, 50, 200, 60))
    qtbot.addWidget(dialog)
    dialog.location.setText("Brasov")
    dialog.contact.setText("0268 000 000")
    assert set(dialog.flags) == {"reason", "location", "contact", "date", "owner",
                                 "app_version", "labels", "borders"}  # G-106 (+ etichete)
    assert dialog.flags["borders"].isChecked()  # G-038: `Borders and background`
    options = dialog.options()
    assert (options.location, options.contact) == ("Brasov", "0268 000 000")  # G-034
    dialog.flags["borders"].setChecked(False)
    assert dialog.options().borders_and_background is False


def test_T_G102_redacted_text_is_a_filled_black_box(tmp_path):
    path = text_pdf(tmp_path / "d.pdf", [["Cerere de finantare 1200 lei"]])
    with PdfDocument.open(path) as doc:
        hit = next(h for h in doc.search("1200") if h.rects)
        SecurityService().redact_regions(doc, [(1, r) for r in hit.rects])
        image = Image.open(io.BytesIO(doc.render_page(1, 2.0))).convert("L")
        scale = 2 * 96 / 72
        box = hit.rect
        for fx in (0.2, 0.5, 0.8):
            for fy in (0.3, 0.7):
                x = round((box.x + box.w * fx) * scale)
                y = round((box.y + box.h * fy) * scale)
                assert image.getpixel((x, y)) < 40  # plin, nu numai chenar


def test_T_G109_document_properties_format(qtbot):
    assert file_size_text(54673) == tr("properties.size_value", n="53.39",
                                       unit=tr("properties.unit.kb"), bytes=54673)
    dialog = PropertiesDialog({"file_size": 54673, "page_size": (595.276, 841.89),
                               "tagged": False, "fast_web_view": False, "editable": True})
    qtbot.addWidget(dialog)
    assert dialog.values["page_size"].text() == tr("properties.page_size_cm", w="21.00",
                                                   h="29.70")
    assert dialog.values["tagged"].text() == tr("properties.no")
    assert dialog.values["fast_web_view"].text() == tr("properties.no")
    assert "54673" in dialog.values["file_size"].text()


@pytest.mark.parametrize("command, method", [
    ("save_form_as", "save_as"),  # H-051
    ("print_form", "print_current"),  # H-052
    ("close_document", "close_current"),  # H-053
    ("exit_application", "close"),  # H-054
    ("search_document", "open_search"),  # H-055
    ("document_properties", "show_properties"),  # H-056
])
def test_T_H051_H056_form_buttons_run_window_commands(window, monkeypatch, command,  # noqa: F811
                                                      method):
    assert command in ACTION_GROUPS["other"]
    called = []
    monkeypatch.setattr(window, method, lambda *a, **k: called.append(a))
    window.forms.run_command(command, {})
    assert len(called) == 1
    if command == "search_document":
        assert called == [("find",)]
    assert isinstance(window, PdfEditorWindow)
