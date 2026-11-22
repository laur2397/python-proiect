"""Completarea formularelor in PDF Editor (faza 11, pasul 11.4): H-001…H-007,
H-023, H-040…H-058, H-100, B-036…B-041."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_forms import form_pdf
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QComboBox, QLineEdit

from app.core.context import AppContext
from app.core.model import FormFieldData, FormFieldType, Rect
from app.core.paths import AppPaths
from app.core.pdf.forms import FormEditor
from app.gui.pdf_editor import PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(form_pdf(tmp_path / "formular.pdf"))
    yield w
    w.close()


@pytest.fixture
def messages(window):
    seen: list[str] = []
    window.show_message = seen.append
    return seen


def doc(window):
    return window.current().document


def field(window, name):
    return next(f for f in window.forms.fields() if f.field_name == name)


def click(window, name):
    data = field(window, name)
    r = data.rect
    window._page_clicked(data.page_number, r.x + r.w / 2, r.y + r.h / 2)
    return data


# --- H-001, H-002, H-100: banda si evidentierea -------------------------------------------------


def test_T_H001_H100_band_appears_for_forms(window, tmp_path):
    assert window.forms.band.isVisible()
    window.forms.highlight_box.setChecked(True)  # H-002
    assert window.forms.highlight
    window.forms.close_band()
    assert not window.forms.band.isVisible()
    window.open_path(text_pdf(tmp_path / "simplu.pdf", [["Fara campuri"]]))
    assert not window.forms.band.isVisible()


def test_T_H003_H005_form_data_menu(window):
    [document] = [m.menu() for m in window.hamburger.menu().actions()
                  if m.menu() is not None and m.menu().objectName() == "pdf_menu_document"]
    [menu] = [m for m in document.actions() if m.menu() is not None
              and m.menu().objectName() == "pdf_menu_form_data"]
    keys = [a.objectName() for a in menu.menu().actions()]
    assert keys == ["pdf_action_load_form_data", "pdf_action_save_form_data",
                    "pdf_action_reset_form"]


# --- completarea pe pagina ---------------------------------------------------------------------


def test_T_H030_text_field_edited_on_the_page(window):
    click(window, "cod")
    editor = window.forms.editor_widget
    assert isinstance(editor, QLineEdit) and editor.maxLength() == 5
    editor.setText("123")
    assert window.forms.commit_editor()
    assert window.forms.editor_widget is None
    assert FormEditor(doc(window)).value("cod") == "123"
    assert doc(window).is_modified


def test_T_H030_readonly_field_has_no_editor(window):
    click(window, "ro")
    assert window.forms.editor_widget is None


def test_T_H032_H033_checkbox_and_radio_by_click(window):
    click(window, "acord")
    assert FormEditor(doc(window)).value("acord") == "Da"
    click(window, "acord")
    assert FormEditor(doc(window)).value("acord") == "Off"
    click(window, "F")
    assert FormEditor(doc(window)).value("sex") == "F"


def test_T_H031_dropdown_editor(window):
    click(window, "judet")
    combo = window.forms.editor_widget
    assert isinstance(combo, QComboBox) and combo.count() == 2
    combo.setCurrentIndex(1)
    combo.activated.emit(1)
    assert FormEditor(doc(window)).value("judet") == "IS"


def test_T_H006_value_rejected_message(window, messages):
    click(window, "data")
    window.forms.editor_widget.setText("31.02.2026")
    assert not window.forms.commit_editor()
    assert messages and "data" in messages[0]


# --- H-003…H-005, H-023: datele, golirea, obligatoriile ------------------------------------------


def test_T_H003_H004_H005_data_and_reset(window, tmp_path, messages):
    form = FormEditor(doc(window))
    form.set_value("nume", "Ana Maria")
    out = tmp_path / "date.fdf"
    assert window.forms.save_data((out, "fdf")) == out
    assert window.forms.reset_form()
    assert form.value("nume") == "Ana"
    filled, ignored = window.forms.load_data(out)
    assert ignored == [] and filled >= 1
    assert form.value("nume") == "Ana Maria"
    assert len(messages) == 1  # raportul incarcarii


def test_T_H007_no_fields_hint(window, tmp_path, messages):
    window.open_path(text_pdf(tmp_path / "simplu.pdf", [["Fara campuri"]]))
    assert window.forms.load_data(tmp_path / "x.fdf") is None
    assert len(messages) == 1


def test_T_H023_required_fields_only_warn_on_save(window, tmp_path, messages, monkeypatch):
    out = tmp_path / "salvat.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path",
                        lambda self, document, suffix=".pdf": out)
    assert window.save_as()
    assert out.exists() and any("obligatoriu" in m for m in messages)


# --- H-040…H-058: butoane cu actiuni, JavaScript ---------------------------------------------------


def add_button(window, actions):
    form = FormEditor(doc(window))
    created = form.create_field(FormFieldData(None, "", FormFieldType.BUTTON, 1,
                                              Rect(420, 300, 90, 24), value="Mergi",
                                              actions=actions))
    window.forms.changed()
    return created


def test_T_H043_button_runs_navigation(window):
    add_button(window, [("click", "next_page", {})])
    click(window, "Button 1")
    assert window.current().view.current_page == 2


def test_T_H049_send_form_writes_an_eml(window, tmp_path, monkeypatch, messages):
    eml = tmp_path / "trimis.eml"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path",
                        lambda self, document, suffix=".pdf": eml)
    add_button(window, [("click", "send_form", {"to": "office@exemplu.ro", "format": "xfdf"})])
    click(window, "Button 1")
    text = eml.read_text(encoding="utf-8", errors="replace")
    assert "office@exemplu.ro" in text and "formular.xfdf" in text
    assert window.forms.send_form("https://portal.ro/primire", "pdf") is None  # offline


def test_T_H058_B038_javascript_after_enabling(window, messages):
    add_button(window, [("click", "run_javascript",
                         {"script": "this.getField('cod').value = 99; app.alert('Gata');"})])
    click(window, "Button 1")
    assert FormEditor(doc(window)).value("cod") is None  # dezactivat implicit (B-040)
    window.enable_javascript_for_document()
    click(window, "Button 1")
    assert FormEditor(doc(window)).value("cod") == "99" and "Gata" in messages


def test_T_B038_document_scripts_run_when_enabled(window, messages):
    pdf = doc(window)._pike()
    pdf.Root.Names = pikepdf.Dictionary(JavaScript=pikepdf.Dictionary(Names=pikepdf.Array([
        pikepdf.String("start"), pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert('Bun venit');"))])))
    doc(window)._changed()
    window.enable_javascript_for_document()
    assert messages == ["Bun venit"]
