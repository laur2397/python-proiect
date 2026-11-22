"""Tabul `Form Editor` din PDF Editor (faza 11, pasul 11.5): H-010…H-022,
H-030…H-036, H-101…H-110."""

from __future__ import annotations

import os

import pytest
from test_pdf_forms import form_pdf
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.model import FormFieldData, FormFieldType, Rect
from app.core.paths import AppPaths
from app.core.pdf.forms import FormEditor
from app.gui.pdf_editor import FORM_MODE_DISABLED, LATER, RIBBON_TABS, PdfEditorWindow
from app.gui.pdf_form_dialogs import ActionDialog, FieldPropertiesDialog


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
    w.resize(1100, 800)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(text_pdf(tmp_path / "cerere.pdf", [["Cerere de finantare"], ["Anexa"]]))
    w.enter_form_editor()
    yield w
    w.close()


@pytest.fixture
def messages(window):
    seen: list[str] = []
    window.show_message = seen.append
    return seen


def doc(window):
    return window.current().document


def design(window):
    return window.form_design


def at(window, page, x, y):
    """Punctul din fereastra vederii (viewport) pentru coordonatele de pagina."""
    view = window.current().view
    box = view.page_to_view(page, Rect(x, y, 0, 0))
    return box.topLeft() - view._offset()


def drag(window, page, start, end, modifiers=Qt.KeyboardModifier.NoModifier):
    d = design(window)
    d.press(at(window, page, *start), Qt.MouseButton.LeftButton, modifiers)
    d.move(at(window, page, *end), modifiers)
    d.release()


def names(window):
    return [f.field_name for f in FormEditor(doc(window)).fields()]


def add(window, kind, x=100, y=100):
    window.actions[{FormFieldType.TEXT: "text_field", FormFieldType.CHECKBOX: "check_box",
                    FormFieldType.RADIO: "radio_button", FormFieldType.DROPDOWN: "dropdown_list",
                    FormFieldType.LISTBOX: "list_box", FormFieldType.BUTTON: "button",
                    FormFieldType.SIGNATURE: "signature_field"}[kind]].trigger()
    drag(window, 1, (x, y), (x, y))


# --- H-010, B-207: tabul ---------------------------------------------------------------------


def test_T_H010_form_editor_disables_main_tools(window):
    assert window.form_editor_mode and design(window).active
    for key in RIBBON_TABS["forms"]:
        assert key not in LATER and window.actions[key].isEnabled()
    for key in FORM_MODE_DISABLED:
        assert not window.actions[key].isEnabled()
    window.ribbon_tabs.setCurrentIndex(0)
    assert not design(window).active and window.actions["add_note"].isEnabled()


# --- H-012, H-103, H-109: uneltele ------------------------------------------------------------


def test_T_H012_H103_H109_click_and_drag_create_fields(window):
    window.actions["text_field"].trigger()
    viewport = window.current().view.viewport()
    assert viewport.cursor().shape() == Qt.CursorShape.CrossCursor  # H-103
    drag(window, 1, (100, 100), (100, 100))  # clic: marimea implicita
    assert names(window) == ["TextField 1"]
    assert design(window).tool is None and not window.actions["text_field"].isChecked()
    window.actions["list_box"].trigger()
    drag(window, 1, (100, 200), (300, 280))  # tragere: dreptunghiul tras
    box = FormEditor(doc(window)).field("List Box 1")
    assert box.rect.w == pytest.approx(200, abs=1) and box.rect.h == pytest.approx(80, abs=1)
    for kind in (FormFieldType.CHECKBOX, FormFieldType.DROPDOWN, FormFieldType.BUTTON,
                 FormFieldType.SIGNATURE):
        add(window, kind, 100, 400 + 40 * len(names(window)))
    assert names(window) == ["TextField 1", "List Box 1", "Checkbox 1", "Drop-down List 1",
                             "Button 1", "Signature 1"]
    window.undo()  # fiecare camp e un pas de Undo
    assert "Signature 1" not in names(window)


def test_T_H013_radio_buttons_until_escape(window, messages):
    window.actions["radio_button"].trigger()
    drag(window, 1, (100, 100), (100, 100))
    drag(window, 1, (130, 100), (130, 100))
    assert design(window).tool == FormFieldType.RADIO  # continua pana la Esc
    design(window).key(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    fields = FormEditor(doc(window)).fields()
    assert {f.group_name for f in fields} == {"Radio Group 1"} and len(fields) == 2
    assert messages == []
    window.actions["radio_button"].trigger()
    drag(window, 1, (100, 300), (100, 300))
    design(window).key(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert len(messages) == 1 and "Radio Group 2" in messages[0]  # un singur buton


# --- H-014, H-017…H-021: selectia, mutarea, ghidajele, marimea, stergerea ----------------------


def test_T_H017_H018_H110_move_with_guides(window, messages):
    add(window, FormFieldType.TEXT, 100, 100)
    add(window, FormFieldType.TEXT, 300, 300)
    d = design(window)
    second = FormEditor(doc(window)).field("TextField 2")
    d.press(at(window, 1, 310, 310))
    d.move(at(window, 1, 110, 410))  # stanga ajunge la x = 100, ca primul camp
    assert ("x", 100.0) in d.guides  # H-018: ghidaj mov
    d.move(at(window, 1, 110, 410), Qt.KeyboardModifier.ControlModifier)
    assert d.guides == []  # H-110: `Ctrl` le ascunde
    d.release()
    moved = FormEditor(doc(window)).field("TextField 2")
    assert moved.rect.x == pytest.approx(second.rect.x - 200, abs=1)
    width, _height = doc(window).page_size(1)
    d.selected = [moved.id]
    assert not d.move_to({moved.id: Rect(width - 20, 100, moved.rect.w, moved.rect.h)})
    assert messages  # H-017: in afara paginii se refuza
    assert FormEditor(doc(window)).field("TextField 2").rect.x == pytest.approx(moved.rect.x)


def test_T_H017_ctrl_click_selects_several(window):
    add(window, FormFieldType.TEXT, 100, 100)
    add(window, FormFieldType.TEXT, 100, 200)
    d = design(window)
    d.press(at(window, 1, 110, 105))
    d.release()
    d.press(at(window, 1, 110, 205), Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier)
    d.release()
    assert len(d.selected) == 2
    window._delete_command()  # H-021
    assert names(window) == []


def test_T_H020_resize_from_the_handle(window):
    add(window, FormFieldType.TEXT, 100, 100)
    d = design(window)
    data = FormEditor(doc(window)).field("TextField 1")
    d.selected = [data.id]
    corner = (data.rect.x + data.rect.w, data.rect.y + data.rect.h)
    drag(window, 1, corner, (corner[0] + 50, corner[1] + 10))
    resized = FormEditor(doc(window)).field("TextField 1")
    assert resized.rect.w == pytest.approx(data.rect.w + 50, abs=1)
    assert resized.rect.h == pytest.approx(data.rect.h + 10, abs=1)


def test_T_H015_H016_copy_paste_and_linked_copy(window):
    add(window, FormFieldType.TEXT, 100, 100)
    d = design(window)
    d.selected = [FormEditor(doc(window)).field("TextField 1").id]
    window._on_selection("copy")  # Ctrl+C
    window.paste_block()  # Ctrl+V
    assert names(window) == ["TextField 1", "TextField 2"]
    d.selected = [FormEditor(doc(window)).field("TextField 1").id]
    linked = d.linked_copy()
    assert linked.field_name == "TextField 1" and linked.linked_to == "TextField 1"
    menu = d.context_menu()
    keys = [a.objectName() for a in menu.actions() if a.objectName()]
    assert keys == ["form_menu_properties", "form_menu_copy", "form_menu_paste",
                    "form_menu_linked_copy", "form_menu_delete", "form_menu_show_names",
                    "form_menu_reset"]


def test_T_H011_H002_show_names_and_highlight(window):
    window.actions["show_field_names"].trigger()
    assert not design(window).show_names
    window.actions["highlight_fields"].trigger()
    assert window.forms.highlight and window.forms.highlight_box.isChecked()


# --- H-014, H-030…H-036, H-104…H-106: dialogul de proprietati -------------------------------------


def test_T_H014_H030_properties_dialog_updates_the_field(window, monkeypatch):
    add(window, FormFieldType.TEXT, 100, 100)
    data = FormEditor(doc(window)).field("TextField 1")

    def fill(self, dialog):
        assert isinstance(dialog, FieldPropertiesDialog)
        assert not dialog.max_symbols.isEnabled()  # H-106: gri pana la bifa
        assert dialog.max_symbols.value() == 250
        dialog.max_enabled.setChecked(True)
        dialog.max_symbols.setValue(13)
        dialog.name.setText("cnp")
        dialog.required.setChecked(True)
        dialog.colors["fill"].set_color("#ffffe0")
        dialog.format.setCurrentIndex(1)  # Date
        dialog.date_view.setEditText("dd.mm.yyyy")
        dialog.default_style_button.click()  # `Set as Default Style`
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", fill)
    design(window).properties(data)
    updated = FormEditor(doc(window)).field("cnp")
    assert updated.max_symbols == 13 and updated.is_required
    assert updated.fill_color == "#FFFFE0" and updated.text_format == "date"
    assert window.settings.get("pdf_forms.default_style")["text"]["fill_color"] == "#FFFFE0"
    add(window, FormFieldType.TEXT, 100, 300)
    assert FormEditor(doc(window)).field("TextField 1").fill_color == "#FFFFE0"


def test_T_H030_H104_H105_dialog_geometry_units_and_lock(qtbot):
    data = FormFieldData(1, "a", FormFieldType.TEXT, 1, Rect(72, 72, 144, 36))
    dialog = FieldPropertiesDialog(data, page_size=(595, 842), units="in")
    qtbot.addWidget(dialog)
    assert dialog.x.value() == pytest.approx(1) and dialog.width.value() == pytest.approx(2)
    dialog.lock.setChecked(True)  # H-104
    dialog.width.setValue(4)
    assert dialog.height.value() == pytest.approx(1)
    dialog.units.setCurrentIndex(2)  # puncte
    assert dialog.width.value() == pytest.approx(288)
    result = dialog.field_data()
    assert result.rect == Rect(72, 72, 288, 72) and result.units == "pt"


def test_T_H031_H036_list_items(qtbot):
    data = FormFieldData(1, "lista", FormFieldType.LISTBOX, 1, Rect(0, 0, 100, 60),
                         items=[("Cluj", "CJ", False)])
    dialog = FieldPropertiesDialog(data, page_size=(595, 842))
    qtbot.addWidget(dialog)
    for text in ("Iași", "Timiș"):
        dialog.item_text.setText(text)
        dialog.add_item()
    dialog.items.setCurrentRow(2)
    dialog.move(-1)
    dialog.allow_multiple.setChecked(True)
    dialog.items.item(0).setSelected(True)
    dialog.set_default()
    dialog.unset_default()
    dialog.items.clearSelection()
    dialog.items.item(1).setSelected(True)
    dialog.set_default()
    result = dialog.field_data()
    assert result.items == [("Cluj", "CJ", False), ("Timiș", None, True), ("Iași", None, False)]
    assert result.allow_multiple


def test_T_H032_H033_H034_dialog_types(qtbot):
    radio = FormFieldData(1, "Da", FormFieldType.RADIO, 1, Rect(0, 0, 14, 14),
                          group_name="raspuns")
    dialog = FieldPropertiesDialog(radio, page_size=(595, 842), groups=["raspuns", "altul"],
                                   default_on=True)
    qtbot.addWidget(dialog)
    assert dialog.group.count() == 2 and dialog.default_on.isChecked()
    dialog.group.setEditText("nou")
    assert dialog.field_data().group_name == "nou" and dialog.field_data().value == "Yes"
    button = FormFieldData(2, "b", FormFieldType.BUTTON, 1, Rect(0, 0, 80, 20), value="OK")
    dialog = FieldPropertiesDialog(button, page_size=(595, 842),
                                   edit_action=lambda a: ("click", "print_form", {}))
    qtbot.addWidget(dialog)
    assert not dialog.required.isVisibleTo(dialog)  # H-022: fara Required la butoane
    dialog.button_text.setText("Tipărește")
    dialog.create_action()
    result = dialog.field_data()
    assert result.value == "Tipărește" and result.actions == [("click", "print_form", {})]


def test_T_H030_name_is_checked_before_closing(window, monkeypatch):
    add(window, FormFieldType.TEXT, 100, 100)
    add(window, FormFieldType.TEXT, 100, 200)
    data = FormEditor(doc(window)).field("TextField 2")
    seen = []

    def fill(self, dialog):
        dialog.name.setText("TextField 1")  # nume folosit deja
        dialog.accept()
        seen.append((dialog.result() != dialog.DialogCode.Accepted,
                     dialog.error.isVisibleTo(dialog)))
        return False
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", fill)
    assert design(window).properties(data) is None
    assert seen == [(True, True)] and names(window) == ["TextField 1", "TextField 2"]


# --- H-041, H-042, H-107, H-108: dialogul de actiune ----------------------------------------------


def test_T_H041_H107_H108_action_dialog(qtbot):
    dialog = ActionDialog(3)
    qtbot.addWidget(dialog)
    assert dialog.event.count() == 6  # H-040
    dialog.action.setCurrentIndex(dialog.action.findData("send_form"))
    assert dialog.params.currentIndex() == dialog.pages["send_form"]
    assert dialog.send_note.text() in ("Se trimit toate câmpurile formularului.",
                                       "All form fields will be sent.")  # H-107
    assert [dialog.send_format.itemData(i) for i in range(dialog.send_format.count())] == \
        ["pdf", "fdf", "xfdf", "html"]  # H-108
    dialog.send_to.setText("office@exemplu.ro")
    dialog.send_format.setCurrentIndex(2)
    assert dialog.action_data() == ("click", "send_form", {"to": "office@exemplu.ro",
                                                       "format": "xfdf"})
    edit = ActionDialog(3, ("on_blur", "go_to_page", {"page": 3}))  # H-042
    qtbot.addWidget(edit)
    assert edit.action_data() == ("on_blur", "go_to_page", {"page": 3})


def test_T_H044_action_parameters_are_validated(window, monkeypatch, messages):
    def fill(self, dialog):
        dialog.action.setCurrentIndex(dialog.action.findData("follow_link"))
        dialog.link.setText("exemplu.ro")
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", fill)
    assert design(window).edit_action(None) is None and messages


# --- H-101, H-102, H-022: desenarea -------------------------------------------------------------


def test_T_H101_H102_H022_fields_are_drawn_in_edit_mode(window, qtbot):
    form = FormEditor(doc(window))
    form.create_field(FormFieldData(None, "nume", FormFieldType.TEXT, 1,
                                    Rect(100, 100, 150, 20), is_required=True))
    form.create_field(FormFieldData(None, "", FormFieldType.SIGNATURE, 1,
                                    Rect(100, 300, 180, 50)))
    design(window).refresh()
    view = window.current().view
    image = view.viewport().grab().toImage()
    box = view.page_to_view(1, Rect(100, 300, 180, 50)).translated(-view._offset())
    label = image.pixelColor(int(box.left()) + 3, int(box.top()) + 3)
    assert label.red() > 200 and label.blue() < 100  # eticheta portocalie `Sign`
    name_box = view.page_to_view(1, Rect(100, 100, 150, 20)).translated(-view._offset())
    above = image.pixelColor(int(name_box.right()) - 2, int(name_box.top()) - 3)
    assert above.lightness() < 60  # eticheta neagra cu numele, dreapta-sus
    QApplication.processEvents()


def test_T_H010_fill_mode_is_off_in_form_editor(window):
    add(window, FormFieldType.TEXT, 100, 100)
    data = FormEditor(doc(window)).field("TextField 1")
    window._page_clicked(1, data.rect.x + 5, data.rect.y + 5)
    assert window.forms.editor_widget is None


def test_T_H001_existing_form_opens_in_form_editor(window, tmp_path):
    window.open_path(form_pdf(tmp_path / "formular.pdf"))
    window.enter_form_editor()
    assert "nume" in [f.field_name for f in design(window).fields()]
