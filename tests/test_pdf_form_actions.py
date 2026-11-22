"""Actiunile campurilor si JavaScript-ul formularelor (faza 11, pasul 11.3):
H-006, H-034, H-040…H-058, B-038…B-041."""

from __future__ import annotations

from dataclasses import replace

import pikepdf
import pytest
from test_pdf_forms import appearance_text
from test_pdf_search import text_pdf

from app.core.model import FormFieldData, FormFieldType, Rect
from app.core.pdf.document import PdfDocument
from app.core.pdf.form_actions import (
    ACTION_TYPES,
    NAMED_ACTIONS,
    TRIGGER_EVENTS,
    FormScripts,
    document_scripts,
    submission,
    submit_target,
    validate_action,
)
from app.core.pdf.forms import FormEditor
from app.core.pdf.javascript import run_script


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(text_pdf(tmp_path / "f.pdf", [["Cerere"], ["Anexa"],
                                                         ["Final"]])) as d:
        yield d


@pytest.fixture
def form(doc):
    return FormEditor(doc)


def text_field(form, name, y=100, **extra):
    return form.create_field(FormFieldData(None, name, FormFieldType.TEXT, 1,
                                           Rect(72, y, 150, 20), **extra))


def button(form, actions, name="Button 1"):
    return form.create_field(FormFieldData(None, name, FormFieldType.BUTTON, 1,
                                           Rect(300, 100, 80, 24), value="OK",
                                           actions=actions))


def add_field_script(doc, name, key, code, *, calc_order=False):
    pdf = doc._pike()
    for field in pdf.Root.AcroForm.Fields:
        if str(field.T) == name:
            aa = field.get("/AA") or pikepdf.Dictionary()
            aa[key] = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String(code))
            field.AA = aa
            if calc_order:
                form = pdf.Root.AcroForm
                if "/CO" not in form:
                    form.CO = pikepdf.Array()
                form.CO.append(field)
    doc._changed()


# --- H-040…H-042: evenimentele si actiunile --------------------------------------------------


def test_T_H040_exactly_six_trigger_events(doc):
    assert TRIGGER_EVENTS == ("click", "drop", "mouse_enter", "mouse_exit", "on_focus",
                              "on_blur")
    with pytest.raises(ValueError):
        validate_action(doc, "double_click", "first_page")
    with pytest.raises(ValueError):
        validate_action(doc, "click", "dance")


def test_T_H041_H042_create_and_modify_actions(form, doc, tmp_path):
    created = button(form, [("click", "next_page", {}), ("click", "print_form", {}),
                            ("mouse_enter", "go_to_page", {"page": 3})])
    assert created.actions == [("click", "next_page", {}), ("click", "print_form", {}),
                               ("mouse_enter", "go_to_page", {"page": 3})]
    out = tmp_path / "cu_actiuni.pdf"
    doc.save_as(out)
    with pikepdf.open(out) as pdf:
        [widget] = [a for a in pdf.pages[0].Annots if a.get("/Subtype") == "/Widget"]
        assert widget.A.S == "/Named" and widget.A.N == "/NextPage"
        assert widget.A.Next.N == "/Print"  # mai multe actiuni: /Next
        assert widget.AA.E.S == "/GoTo"
    created = form.field("Button 1")  # dupa salvare, obiectele au alte numere
    modified = form.update_field(replace(created, actions=[("on_blur", "reset_form", {})]))
    assert modified.actions == [("on_blur", "reset_form", {})]
    scripts = FormScripts(form, enabled=False)
    scripts.set_actions(modified.id, [("drop", "fit_width", {})])
    assert form.field("Button 1").actions == [("drop", "fit_width", {})]


@pytest.mark.parametrize("action", sorted(NAMED_ACTIONS))
def test_T_H043_H045_H046_named_actions_round_trip(form, action):
    created = button(form, [("click", action, {})])
    assert created.actions == [("click", action, {})]


def test_T_H043_H057_all_action_types_are_known():
    assert len(ACTION_TYPES) == len(set(ACTION_TYPES)) == 31
    for needed in ("go_to_page", "open_file", "follow_link", "send_form", "reset_form",
                   "run_javascript", "scan_pages", "exit_application"):
        assert needed in ACTION_TYPES


def test_T_H044_H047_H048_H049_parameters_are_checked(doc):
    with pytest.raises(ValueError):
        validate_action(doc, "click", "go_to_page", {"page": 4})  # in interval (H-044)
    assert validate_action(doc, "click", "go_to_page", {"page": "2"}) == {"page": 2}
    with pytest.raises(ValueError):
        validate_action(doc, "click", "open_file", {"file": " "})
    with pytest.raises(ValueError):
        validate_action(doc, "click", "follow_link", {"url": "exemplu.ro"})  # fara prefix
    assert validate_action(doc, "click", "follow_link", {"url": "https://exemplu.ro"})
    with pytest.raises(ValueError):
        validate_action(doc, "click", "send_form", {"to": "nu-e-adresa", "format": "pdf"})
    with pytest.raises(ValueError):
        validate_action(doc, "click", "send_form", {"to": "a@b.ro", "format": "doc"})
    assert validate_action(doc, "click", "send_form", {"to": "a@b.ro", "format": "XFDF"}) \
        == {"to": "a@b.ro", "format": "xfdf"}


def test_T_H047_H048_H049_actions_round_trip(form):
    actions = [("click", "open_file", {"file": "anexa.pdf"}),
               ("click", "follow_link", {"url": "mailto:office@exemplu.ro"}),
               ("click", "send_form", {"to": "office@exemplu.ro", "format": "xfdf"}),
               ("click", "run_javascript", {"script": "app.alert('ș');"})]
    assert button(form, actions).actions == actions


def test_T_H049_submit_target_and_files(form, tmp_path):
    assert submit_target("mailto:a@b.ro") == ("email", "a@b.ro")
    assert submit_target("a@b.ro") == ("email", "a@b.ro")
    assert submit_target("https://portal.ro/primire") == ("url", "https://portal.ro/primire")
    text_field(form, "nume")
    form.set_value("nume", "Ana")
    out = tmp_path / "trimis"
    out.mkdir()
    for fmt in ("pdf", "fdf", "xfdf", "html"):
        path = submission(form, fmt, out)
        assert path.suffix == "." + fmt and path.stat().st_size > 0
    with PdfDocument.open(out / "f.pdf") as sent:
        assert FormEditor(sent).value("nume") == "Ana"


def test_T_H034_unsupported_actions_are_kept(form, doc):
    button(form, [])
    pdf = doc._pike()
    widget = next(a for a in pdf.pages[0].Annots if a.get("/Subtype") == "/Widget")
    widget.A = pikepdf.Dictionary(S=pikepdf.Name.Hide, T=pikepdf.String("x"))
    doc._changed()
    [(event, kind, params)] = form.field("Button 1").actions
    assert (event, kind, params["subtype"]) == ("click", "unsupported", "/Hide")
    form.update_field(replace(form.field("Button 1"), tooltip="Ascunde"))
    assert form.field("Button 1").actions[0][1] == "unsupported"


# --- H-050…H-058: executia ------------------------------------------------------------------


def test_T_H050_H057_run_event_gives_window_commands(form):
    created = button(form, [("click", "reset_form", {}), ("click", "go_to_page", {"page": 2}),
                            ("on_focus", "full_screen", {})])
    scripts = FormScripts(form, enabled=False)
    assert scripts.run_event(created.id, "click").commands == [
        ("reset_form", {}), ("go_to_page", {"page": 2})]
    assert scripts.run_event(created.id, "on_focus").commands == [("full_screen", {})]
    assert scripts.run_event(created.id, "mouse_exit").commands == []


def test_T_H058_run_javascript_only_when_enabled(form):
    text_field(form, "total")
    created = button(form, [("click", "run_javascript", {
        "script": "this.getField('total').value = 42; app.alert('Gata'); this.print();"})])
    off = FormScripts(form, enabled=False).run_event(created.id, "click")
    assert off.commands == [] and form.value("total") is None
    on = FormScripts(form, enabled=True).run_event(created.id, "click")
    assert form.value("total") == "42"
    assert on.alerts == [("text", "Gata")] and on.commands == [("print_form", {})]


# --- H-006: verificarile de format, calculele -------------------------------------------------


def test_T_H006_format_checks_run_only_with_javascript(form, doc):
    text_field(form, "suma")
    add_field_script(doc, "suma", "/K", "AFNumber_Keystroke(2, 2, 0, 0, '', true);")
    add_field_script(doc, "suma", "/F", "AFNumber_Format(2, 2, 0, 0, ' lei', false);")
    on = FormScripts(form, enabled=True)
    rejected = on.commit("suma", "abc")
    assert not rejected.accepted and rejected.alerts == [("format", "suma")]
    assert form.value("suma") is None
    assert on.commit("suma", "1234.5").accepted
    assert form.value("suma") == "1234.5"
    assert appearance_text(doc, "suma") == "1.234,50 lei"  # formatul afisat
    off = FormScripts(form, enabled=False)
    assert off.commit("suma", "abc").accepted  # JS dezactivat: verificarea nu ruleaza
    assert form.value("suma") == "abc"


def test_T_H006_validation_and_calculation(form, doc):
    for i, name in enumerate(("a", "b", "total")):
        text_field(form, name, y=100 + 30 * i)
    add_field_script(doc, "a", "/V", "AFRange_Validate(true, 0, true, 100);")
    add_field_script(doc, "total", "/C", "AFSimple_Calculate('SUM', ['a', 'b']);",
                     calc_order=True)
    scripts = FormScripts(form, enabled=True)
    assert not scripts.commit("a", "150").accepted  # in afara intervalului
    assert scripts.commit("a", "40").accepted
    scripts.commit("b", "2,5")
    assert form.value("total") == "42.5"


def test_T_B038_document_scripts_define_functions(form, doc):
    text_field(form, "cod")
    pdf = doc._pike()
    pdf.Root.Names = pikepdf.Dictionary(JavaScript=pikepdf.Dictionary(Names=pikepdf.Array([
        pikepdf.String("util"), pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript,
            JS=pikepdf.String("function mare(s) { return String(s).toUpperCase(); }"))])))
    doc._changed()
    add_field_script(doc, "cod", "/K", "if (event.willCommit) event.value = mare(event.value);")
    assert document_scripts(doc) == ["function mare(s) { return String(s).toUpperCase(); }"]
    FormScripts(form, enabled=True).commit("cod", "ab12")
    assert form.value("cod") == "AB12"


# --- B-041: limita de timp ------------------------------------------------------------------


def test_T_B041_script_time_limit():
    result = run_script("while (true) {}", timeout=0.2)
    assert result.ran and result.timed_out
    assert run_script("event.value = 1 + 1;").value == "2"
    assert run_script("throw new Error('x');").error
