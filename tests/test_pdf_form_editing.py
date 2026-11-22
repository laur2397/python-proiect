"""Formularele PDF, crearea si editarea campurilor (faza 11, pasul 11.2):
H-012…H-021, H-030…H-036, H-109."""

from __future__ import annotations

from dataclasses import replace

import pikepdf
import pytest
from test_pdf_forms import appearance_text, ink
from test_pdf_search import text_pdf

from app.core.errors import (
    DuplicateFieldNameError,
    InvalidFieldNameError,
    OrphanRadioButtonError,
    SignedFieldCopyError,
)
from app.core.model import FormFieldData, FormFieldType, Rect
from app.core.pdf.document import PdfDocument
from app.core.pdf.forms import FormEditor, from_units, style_of, to_units, with_style


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(text_pdf(tmp_path / "gol.pdf", [["Cerere"], ["Anexa"]])) as d:
        yield d


@pytest.fixture
def form(doc):
    return FormEditor(doc)


def new(kind, rect=(72, 100, 150, 20), page=1, **extra):
    return FormFieldData(None, extra.pop("field_name", ""), kind, page, Rect(*rect), **extra)


# --- H-030, H-109: numele ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["", "  ", ".nume", "nume.", "a..b"])
def test_T_H030_invalid_field_names(form, name):
    with pytest.raises(InvalidFieldNameError):
        form.validate_field_name(name)


def test_T_H030_H109_generated_and_unique_names(form):
    assert form.next_name(FormFieldType.TEXT) == "TextField 1"
    first = form.create_field(new(FormFieldType.TEXT))
    assert first.field_name == "TextField 1"
    assert form.create_field(new(FormFieldType.TEXT, (72, 140, 150, 20))).field_name == \
        "TextField 2"
    assert form.next_name(FormFieldType.CHECKBOX) == "Checkbox 1"
    assert form.next_name(FormFieldType.LISTBOX) == "List Box 1"
    assert form.next_name(FormFieldType.BUTTON) == "Button 1"
    with pytest.raises(DuplicateFieldNameError):
        form.create_field(new(FormFieldType.TEXT, field_name="TextField 1"))


def test_T_H030_hierarchical_names(form, doc):
    form.create_field(new(FormFieldType.TEXT, field_name="persoana.nume"))
    form.create_field(new(FormFieldType.TEXT, (72, 140, 150, 20), field_name="persoana.cnp"))
    names = [f.field_name for f in form.fields()]
    assert names == ["persoana.nume", "persoana.cnp"]
    assert len(doc._pike().Root.AcroForm.Fields) == 1  # un singur parinte `persoana`
    with pytest.raises(DuplicateFieldNameError):
        form.create_field(new(FormFieldType.TEXT, (72, 180, 150, 20), field_name="persoana"))
    with pytest.raises(DuplicateFieldNameError):
        form.create_field(new(FormFieldType.TEXT, (72, 180, 150, 20),
                              field_name="persoana.nume.x"))


# --- H-012, H-030…H-036: tipurile -----------------------------------------------------------


def test_T_H030_text_field_properties(form, doc, tmp_path):
    created = form.create_field(new(
        FormFieldType.TEXT, field_name="adresa", tooltip="Adresa completa",
        is_required=True, max_symbols=40, fill_color="#FFFFE0", border_color="#000080",
        border_width=2, font_size=11, text_color="#222222", is_multiline=True))
    assert created.id is not None and created.tooltip == "Adresa completa"
    assert created.is_required and created.max_symbols == 40 and created.is_multiline
    assert (created.fill_color, created.border_color, created.border_width) == \
        ("#FFFFE0", "#000080", 2)
    assert created.font_size == 11 and created.text_color == "#222222"
    assert created.rect == Rect(72, 100, 150, 20)
    form.set_value("adresa", "Str. Ștefan cel Mare 3")
    assert appearance_text(doc, "adresa") == "Str. Ștefan cel Mare 3"
    assert ink(doc, 1, created.rect) > 20
    out = tmp_path / "salvat.pdf"
    doc.save_as(out)
    with pikepdf.open(out) as pdf:
        [field] = pdf.Root.AcroForm.Fields
        assert field.FT == "/Tx" and int(field.Ff) & 2 and int(field.MaxLen) == 40


def test_T_H030_date_format(form):
    form.create_field(new(FormFieldType.TEXT, field_name="data", text_format="date",
                          date_format="dd.mm.yyyy"))
    assert form.field("data").text_format == "date"
    form.set_value("data", "2027-1-5")
    assert form.value("data") == "05.01.2027"
    data = form.field("data")
    form.update_field(replace(data, text_format="text"))
    assert form.field("data").text_format == "text"


def test_T_H031_H036_lists(form):
    items = [("Cluj", "CJ", True), ("Iași", "IS", False)]
    drop = form.create_field(new(FormFieldType.DROPDOWN, field_name="judet", items=items,
                                 allow_custom=True))
    assert drop.items == items and drop.allow_custom and drop.value == "CJ"
    form.set_value("judet", "Brașov")  # `Allow non-list items`
    assert form.value("judet") == "Brașov"
    box = form.create_field(new(
        FormFieldType.LISTBOX, (72, 140, 150, 60), field_name="limbi",
        items=[("română", None, True), ("engleză", None, True), ("germană", None, False)],
        allow_multiple=True))
    assert box.allow_multiple and box.value == "română\nengleză"
    form.reset()
    assert form.value("judet") == "CJ"  # elementul implicit revine (H-031)


def test_T_H032_H033_checkbox_and_radio(form, doc):
    box = form.create_field(new(FormFieldType.CHECKBOX, (72, 100, 14, 14),
                                field_name="acord", value="Yes", check_color="#C00000"))
    assert box.value == "Yes" and box.check_color == "#C00000"  # `Enabled by Default`
    assert form.default_on(box)
    form.set_value("acord", "")
    form.reset()
    assert form.value("acord") == "Yes"
    a = form.create_field(new(FormFieldType.RADIO, (72, 140, 14, 14), field_name="Da",
                              group_name="raspuns", tooltip="Raspunsul"))
    b = form.create_field(new(FormFieldType.RADIO, (100, 140, 14, 14), field_name="Nu",
                              group_name="raspuns", value="Yes"))
    assert a.group_name == b.group_name == "raspuns" and a.tooltip == "Raspunsul"
    assert form.value("raspuns") == "Nu"
    form.set_value("Da", "")
    assert form.value("raspuns") == "Da"
    assert ink(doc, 1, a.rect) > 0
    with pytest.raises(DuplicateFieldNameError):
        form.create_field(new(FormFieldType.RADIO, (130, 140, 14, 14), field_name="Da",
                              group_name="raspuns"))


def test_T_H034_H035_button_and_signature(form, doc):
    button = form.create_field(new(FormFieldType.BUTTON, (300, 100, 80, 24),
                                   value="Trimite", fill_color="#DDDDDD"))
    assert button.field_name == "Button 1" and button.value == "Trimite"
    assert appearance_text(doc, "Button 1") == "Trimite"
    sig = form.create_field(new(FormFieldType.SIGNATURE, (300, 300, 200, 60),
                                is_required=True))
    assert sig.field_type == FormFieldType.SIGNATURE and sig.is_required  # H-035
    assert [f.field_name for f in form.incomplete_required()] == ["Signature 1"]


# --- H-013: grupurile radio ---------------------------------------------------------------


def test_T_H013_radio_group_needs_two_buttons(form):
    form.create_field(new(FormFieldType.RADIO, (72, 100, 14, 14), group_name="g"))
    [problem] = form.validate_document()
    assert isinstance(problem, OrphanRadioButtonError) and problem.params["group"] == "g"
    form.create_field(new(FormFieldType.RADIO, (100, 100, 14, 14), group_name="g"))
    assert form.validate_document() == []
    names = [f.field_name for f in form.fields()]
    assert names == ["Radio Button 1", "Radio Button 2"]


# --- H-014, H-017…H-020: proprietati, mutare, ghidaje, marime --------------------------------


def test_T_H017_H019_H020_move_and_resize_inside_the_page(form, doc):
    data = form.create_field(new(FormFieldType.TEXT, field_name="nume"))
    moved = form.move_field(data.id, 200, 300)
    assert (moved.rect.x, moved.rect.y) == (200, 300)
    width, _height = doc.page_size(1)
    with pytest.raises(ValueError):
        form.move_field(data.id, width - 10, 300)  # in afara paginii
    with pytest.raises(ValueError):
        form.update_field(replace(moved, page_number=2))
    with pytest.raises(ValueError):
        form.resize_field(data.id, 150, 0)  # inaltimea nu poate fi 0
    resized = form.resize_field(data.id, 220, 30)
    assert (resized.rect.w, resized.rect.h) == (220, 30)


def test_T_H018_alignment_guides(form):
    a = form.create_field(new(FormFieldType.TEXT, (72, 100, 150, 20)))
    b = form.create_field(new(FormFieldType.TEXT, (300, 200, 100, 20)))
    moving = replace(b, rect=Rect(72.5, 300, 100, 20))
    assert form.alignment_guides(moving, form.fields()) == [("x", 72.0)]
    moving = replace(b, rect=Rect(300, 120, 100, 20))  # sus = josul lui a
    assert ("y", 120.0) in form.alignment_guides(moving, [a])
    assert form.alignment_guides(replace(b, rect=Rect(400, 400, 50, 20)), [a]) == []


def test_T_H014_H022_update_properties(form):
    data = form.create_field(new(FormFieldType.TEXT, field_name="nume"))
    updated = form.update_field(replace(data, is_required=True, is_readonly=True,
                                        tooltip="Numele", field_name="nume_complet"))
    assert updated.field_name == "nume_complet" and updated.is_required
    assert updated.is_readonly and updated.tooltip == "Numele"
    other = form.create_field(new(FormFieldType.TEXT, (72, 140, 150, 20)))
    with pytest.raises(DuplicateFieldNameError):
        form.update_field(replace(other, field_name="nume_complet"))


# --- H-015, H-016: copiile ------------------------------------------------------------------


def test_T_H015_copy_keeps_properties_except_name(form):
    data = form.create_field(new(FormFieldType.TEXT, field_name="TextField 3",
                                 fill_color="#EEEEEE", max_symbols=10, tooltip="Cod"))
    form.set_value("TextField 3", "abc")
    copy = form.copy_field("TextField 3")
    assert copy.field_name == "TextField 4" and copy.value is None
    assert (copy.fill_color, copy.max_symbols, copy.tooltip) == ("#EEEEEE", 10, "Cod")
    assert copy.rect.x == data.rect.x + 10
    assert form.copy_field("TextField 3", page=2, at=(50, 50)).page_number == 2
    assert form.copy_field("TextField 4").field_name == "TextField 6"
    form.create_field(new(FormFieldType.TEXT, (72, 300, 100, 20), field_name="nume"))
    assert form.copy_field("nume").field_name == "nume 1"


def test_T_H015_signed_signature_field_cannot_be_copied(form, doc):
    form.create_field(new(FormFieldType.SIGNATURE, (300, 300, 200, 60), field_name="sig"))
    assert form.copy_field("sig").field_name == "sig 1"  # goala: se copiaza
    for field in doc._pike().Root.AcroForm.Fields:
        if str(field.T) == "sig":
            field.V = doc._pike().make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Sig))
    with pytest.raises(SignedFieldCopyError):
        form.copy_field("sig")


def test_T_H016_linked_copy_and_unlinking_by_rename(form, doc):
    form.create_field(new(FormFieldType.TEXT, field_name="nume", fill_color="#FFFFCC"))
    form.set_value("nume", "Ana")
    copy = form.create_linked_copy("nume", page=2, at=(72, 72))
    assert copy.field_name == "nume" and copy.linked_to == "nume" and copy.value == "Ana"
    assert copy.fill_color == "#FFFFCC"
    form.set_value("nume", "Ioana")
    assert appearance_text(doc, "nume", page=2) == "Ioana"
    independent = form.update_field(replace(copy, field_name="nume_anexa"))
    assert independent.linked_to is None and independent.value == "Ioana"
    form.set_value("nume", "Maria")
    assert form.value("nume_anexa") == "Ioana"
    assert [f.field_name for f in form.fields()] == ["nume", "nume_anexa"]


# --- H-021: stergerea ---------------------------------------------------------------------


def test_T_H021_delete_fields_and_widgets(form, doc):
    form.create_field(new(FormFieldType.TEXT, field_name="a"))
    linked = form.create_linked_copy("a", page=2, at=(72, 72))
    form.create_field(new(FormFieldType.TEXT, (72, 140, 150, 20), field_name="b"))
    form.delete_widgets([linked.id])
    assert [f.field_name for f in form.fields()] == ["a", "b"]
    form.delete_fields(["a"])
    assert [f.field_name for f in form.fields()] == ["b"]
    form.create_field(new(FormFieldType.RADIO, (72, 200, 14, 14), field_name="x",
                          group_name="g"))
    form.create_field(new(FormFieldType.RADIO, (100, 200, 14, 14), field_name="y",
                          group_name="g"))
    form.delete_fields(["x"])  # numai butonul
    assert [f.field_name for f in form.fields()] == ["b", "y"]
    form.delete_fields(["b", "g"])
    assert form.fields() == []
    assert all(a.get("/Subtype") != "/Widget" for a in doc._pike().pages[0].Annots)
    assert len(doc._pike().Root.AcroForm.Fields) == 0


# --- unitatile si stilul implicit ------------------------------------------------------------


def test_T_H030_units_and_default_style():
    assert from_units(2.54, "cm") == pytest.approx(72)
    assert to_units(72, "in") == 1 and to_units(36, "pt") == 36
    styled = FormFieldData(None, "a", FormFieldType.TEXT, 1, Rect(0, 0, 50, 20),
                           fill_color="#FF0000", font_size=9)
    style = style_of(styled)
    plain = with_style(FormFieldData(None, "b", FormFieldType.TEXT, 1, Rect(0, 0, 50, 20)),
                       {**style, "field_name": "ignorat"})
    assert plain.fill_color == "#FF0000" and plain.font_size == 9 and plain.field_name == "b"
