"""Formularele PDF, completarea (faza 11, pasul 11.1): H-001, H-003…H-005,
H-022…H-024, H-030…H-036."""

from __future__ import annotations

import pikepdf
import pytest
from test_pdf_search import text_pdf

from app.core.errors import FileCorruptError, UnsupportedFormatError
from app.core.model import FormFieldType
from app.core.pdf.document import PdfDocument
from app.core.pdf.forms import FormEditor, format_date


def _widget(pdf, page, rect, **extra):
    widget = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, Rect=rect, P=page.obj,
        **extra))
    if "/Annots" not in page.obj:
        page.obj.Annots = pdf.make_indirect(pikepdf.Array())
    page.obj.Annots.append(widget)
    return widget


def _states(pdf, on):
    return pikepdf.Dictionary(N=pikepdf.Dictionary({
        "/" + on: pdf.make_stream(b"0 0 1 rg 2 2 8 8 re f"), "/Off": pdf.make_stream(b" ")}))


def form_pdf(path):
    """Un formular ca de la alt program: campuri de toate tipurile, un camp
    ierarhic (`adresa.oras`) si o copie legata (`nume` pe doua pagini)."""
    text_pdf(path, [["Formular de inscriere"], ["Pagina 2"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        p1, p2 = pdf.pages[0], pdf.pages[1]
        fields = pikepdf.Array()

        def text(name, rect, page=p1, **extra):
            w = _widget(pdf, page, rect, FT=pikepdf.Name.Tx, T=pikepdf.String(name),
                        DA=pikepdf.String("/Helv 0 Tf 0 g"), **extra)
            fields.append(w)
            return w

        text("cod", [72, 700, 200, 720], MaxLen=5)
        text("ro", [72, 670, 200, 690], Ff=1, V=pikepdf.String("fix"))
        text("obligatoriu", [72, 640, 200, 660], Ff=2,
             TU=pikepdf.String("Camp obligatoriu"))
        date_js = pikepdf.Dictionary(S=pikepdf.Name.JavaScript,
                                     JS=pikepdf.String('AFDate_FormatEx("dd.mm.yyyy");'))
        text("data", [72, 610, 200, 630], AA=pikepdf.Dictionary(F=date_js))
        # campul `nume`, cu doua widgeturi (copie legata) si valoare implicita
        nume = pdf.make_indirect(pikepdf.Dictionary(
            FT=pikepdf.Name.Tx, T=pikepdf.String("nume"), DV=pikepdf.String("Ana"),
            DA=pikepdf.String("/Helv 10 Tf 0 0 1 rg"), Kids=pikepdf.Array()))
        for page, rect in ((p1, [72, 580, 250, 600]), (p2, [72, 700, 250, 720])):
            kid = _widget(pdf, page, rect, Parent=nume,
                          MK=pikepdf.Dictionary(BG=[1, 1, 0.8], BC=[0, 0, 0]))
            nume.Kids.append(kid)
        fields.append(nume)
        fields.append(_widget(pdf, p1, [72, 550, 86, 564], FT=pikepdf.Name.Btn,
                              T=pikepdf.String("acord"), AP=_states(pdf, "Da"),
                              AS=pikepdf.Name.Off))
        sex = pdf.make_indirect(pikepdf.Dictionary(
            FT=pikepdf.Name.Btn, T=pikepdf.String("sex"), Ff=1 << 15 | 1 << 14,
            TU=pikepdf.String("Sexul"), Kids=pikepdf.Array()))
        for on, x in (("M", 72), ("F", 100)):
            sex.Kids.append(_widget(pdf, p1, [x, 520, x + 14, 534], Parent=sex,
                                    AP=_states(pdf, on), AS=pikepdf.Name.Off))
        fields.append(sex)
        fields.append(_widget(
            pdf, p1, [72, 480, 200, 500], FT=pikepdf.Name.Ch, Ff=1 << 17,
            T=pikepdf.String("judet"), DV=pikepdf.String("CJ"),
            Opt=pikepdf.Array([pikepdf.Array([pikepdf.String("CJ"), pikepdf.String("Cluj")]),
                               pikepdf.Array([pikepdf.String("IS"), pikepdf.String("Iași")])]),
            DA=pikepdf.String("/Helv 9 Tf 0 g")))
        fields.append(_widget(
            pdf, p1, [72, 400, 200, 470], FT=pikepdf.Name.Ch, Ff=1 << 21,
            T=pikepdf.String("limbi"),
            Opt=pikepdf.Array([pikepdf.String(v) for v in ("română", "engleză", "franceză")]),
            DA=pikepdf.String("/Helv 9 Tf 0 g")))
        fields.append(_widget(pdf, p1, [300, 100, 500, 160], FT=pikepdf.Name.Sig,
                              T=pikepdf.String("semnatura")))
        fields.append(_widget(pdf, p1, [300, 700, 400, 720], FT=pikepdf.Name.Btn,
                              Ff=1 << 16, T=pikepdf.String("trimite"),
                              MK=pikepdf.Dictionary(CA=pikepdf.String("Trimite"))))
        adresa = pdf.make_indirect(pikepdf.Dictionary(T=pikepdf.String("adresa"),
                                                      Kids=pikepdf.Array()))
        oras = _widget(pdf, p1, [300, 600, 450, 620], FT=pikepdf.Name.Tx,
                       T=pikepdf.String("oras"), Parent=adresa)
        adresa.Kids.append(oras)
        fields.append(adresa)
        pdf.Root.AcroForm = pdf.make_indirect(pikepdf.Dictionary(
            Fields=fields, DA=pikepdf.String("/Helv 0 Tf 0 g"),
            DR=pikepdf.Dictionary(Font=pikepdf.Dictionary(Helv=pikepdf.Dictionary(
                Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica)))))
        pdf.save(path)
    return path


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(form_pdf(tmp_path / "formular.pdf")) as d:
        yield d


@pytest.fixture
def form(doc):
    return FormEditor(doc)


def by_name(form):
    return {f.field_name: f for f in form.fields()}


def appearance_text(doc, name, page=1):
    """Textul din aspectul (/AP) widgetului, prin ToUnicode-ul fontului lui."""
    import re

    for annot in doc._pike().pages[page - 1].Annots:
        field = annot if "/T" in annot else annot.get("/Parent")
        if field is None or str(field.T) != name:
            continue
        stream = annot.AP.N
        cmap = stream.Resources.Font.F1.ToUnicode.read_bytes().decode()
        glyphs = dict(re.findall(r"<([0-9A-F]{4})> <([0-9A-F]{4})>", cmap))
        codes = re.findall(r"<([0-9A-F]+)> Tj", stream.read_bytes().decode())
        return "\n".join("".join(chr(int(glyphs[c[i:i + 4]], 16))
                                 for i in range(0, len(c), 4)) for c in codes)
    raise KeyError(name)


def ink(doc, page, rect):
    """Pixelii intunecati din dreptunghiul campului, la randare."""
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(doc.render_page(page, 1.0))).convert("L")
    k = image.width / doc.page_size(page)[0]
    crop = image.crop((int(rect.x * k) + 3, int(rect.y * k) + 3,
                       int((rect.x + rect.w) * k) - 3, int((rect.y + rect.h) * k) - 3))
    return sum(1 for v in crop.tobytes() if v < 128)


# --- H-001: detectia, citirea -----------------------------------------------------------


def test_T_H001_form_is_detected_and_read(form, tmp_path):
    assert form.has_fields()
    with PdfDocument.open(text_pdf(tmp_path / "simplu.pdf", [["Fara campuri"]])) as plain:
        assert not FormEditor(plain).has_fields()
    fields = by_name(form)
    assert fields["cod"].field_type == FormFieldType.TEXT and fields["cod"].max_symbols == 5
    assert fields["ro"].is_readonly and fields["obligatoriu"].is_required
    assert fields["obligatoriu"].tooltip == "Camp obligatoriu"
    assert fields["acord"].field_type == FormFieldType.CHECKBOX
    assert fields["M"].field_type == FormFieldType.RADIO and fields["M"].group_name == "sex"
    assert fields["judet"].field_type == FormFieldType.DROPDOWN
    assert fields["judet"].items == [("Cluj", "CJ", True), ("Iași", "IS", False)]
    assert fields["limbi"].field_type == FormFieldType.LISTBOX and fields["limbi"].allow_multiple
    assert fields["semnatura"].field_type == FormFieldType.SIGNATURE
    assert fields["trimite"].field_type == FormFieldType.BUTTON
    assert "adresa.oras" in fields
    assert fields["data"].text_format == "date" and fields["data"].date_format == "dd.mm.yyyy"
    nume = [f for f in form.fields() if f.field_name == "nume"]
    assert [f.page_number for f in nume] == [1, 2] and nume[1].linked_to == "nume"
    assert nume[0].fill_color == "#FFFFCC" and nume[0].text_color == "#0000FF"
    assert nume[0].font_name == "Helvetica" and nume[0].font_size == 10
    assert fields["cod"].rect.y == pytest.approx(842 - 720)
    assert [f.field_name for f in form.fields(page=2)] == ["nume"]


# --- H-030…H-036: completarea ------------------------------------------------------------


def test_T_H030_text_values_with_limits_and_diacritics(form, doc):
    form.set_value("cod", "12345")
    with pytest.raises(ValueError):
        form.set_value("cod", "123456")  # Max Number of Symbols
    with pytest.raises(ValueError):
        form.set_value("ro", "alt")  # Read-Only
    form.set_value("nume", "Ștefan Țurcanu")
    assert form.value("nume") == "Ștefan Țurcanu"
    assert appearance_text(doc, "nume", page=2) == "Ștefan Țurcanu"  # copia legata (H-016)
    assert appearance_text(doc, "cod") == "12345"
    assert ink(doc, 2, form.fields(page=2)[0].rect) > 20


def test_T_H030_date_is_reduced_to_the_view_format():
    assert format_date("5/3/2026", "dd.mm.yyyy") == "05.03.2026"
    assert format_date("2026-11-22", "dd.mm.yyyy") == "22.11.2026"
    assert format_date("22 11 26", "d.m.yyyy") == "22.11.2026"
    assert format_date("11/22/2026", "mm/dd/yy") == "11/22/26"
    with pytest.raises(ValueError):
        format_date("31.02.2026", "dd.mm.yyyy")
    with pytest.raises(ValueError):
        format_date("maine", "dd.mm.yyyy")


def test_T_H030_date_field(form):
    form.set_value("data", "3-1-2027")
    assert form.value("data") == "03.01.2027"


def test_T_H032_H033_checkbox_and_radio(form, doc):
    form.set_value("acord", "da")
    assert form.value("acord") == "Da"
    widget = next(w for w in doc._pike().pages[0].Annots if w.get("/T") == "acord")
    assert widget.AS == "/Da"
    form.set_value("acord", "")
    assert form.value("acord") == "Off" and widget.AS == "/Off"
    form.set_value("F", "")  # butonul, dat prin nume
    assert form.value("sex") == "F" and form.value("M") == "Off"
    form.set_value("sex", "M")
    assert form.value("sex") == "M"
    with pytest.raises(ValueError):
        form.set_value("sex", "X")


def test_T_H031_H036_lists(form, doc):
    form.set_value("judet", "Iași")  # textul afisat sau valoarea
    assert form.value("judet") == "IS"
    assert appearance_text(doc, "judet") == "Iași"
    with pytest.raises(ValueError):
        form.set_value("judet", "Brașov")  # fara `Allow non-list items`
    form.set_value("limbi", "română\nfranceză")
    assert form.value("limbi") == "română\nfranceză"
    assert list(doc._pike().Root.AcroForm.Fields[8].I) == [0, 2]
    with pytest.raises(ValueError):
        form.set_value("trimite", "x")


# --- H-005: golirea ---------------------------------------------------------------------


def test_T_H005_reset_restores_defaults(form):
    form.set_value("cod", "123")
    form.set_value("judet", "IS")
    form.set_value("nume", "Ion")
    form.set_value("acord", "da")
    form.reset()
    assert form.value("cod") is None and form.value("acord") == "Off"
    assert form.value("judet") == "CJ"  # elementul implicit revine
    assert form.value("nume") == "Ana"


# --- H-022, H-023: campurile obligatorii --------------------------------------------------


def test_T_H022_H023_required_fields_only_warn(form, doc, tmp_path):
    assert [f.field_name for f in form.incomplete_required()] == ["obligatoriu"]
    doc.save_as(tmp_path / "salvat.pdf")  # salvarea nu e blocata
    form.set_value("obligatoriu", "gata")
    assert form.incomplete_required() == []


# --- H-024: salvarea pastreaza campurile ---------------------------------------------------


def test_T_H024_save_as_pdf_keeps_fields(form, doc, tmp_path):
    form.set_value("nume", "Maria")
    out = tmp_path / "completat.pdf"
    doc.save_as(out)
    with PdfDocument.open(out) as again:
        reopened = FormEditor(again)
        assert reopened.value("nume") == "Maria"
        assert len(reopened.fields()) == len(form.fields())


# --- H-003, H-004: datele de formular ------------------------------------------------------


@pytest.mark.parametrize("fmt", ["fdf", "xfdf"])
def test_T_H003_H004_save_and_load_form_data(form, tmp_path, fmt):
    form.set_value("nume", "Ștefan")
    form.set_value("acord", "da")
    form.set_value("sex", "F")
    form.set_value("limbi", "engleză\nfranceză")
    form.set_value("adresa.oras", "Cluj-Napoca")
    data = tmp_path / f"date.{fmt}"
    form.save_data(data, fmt)
    form.reset()
    filled, ignored = form.load_data(data)
    assert ignored == [] and filled >= 5
    assert form.value("nume") == "Ștefan" and form.value("acord") == "Da"
    assert form.value("sex") == "F" and form.value("limbi") == "engleză\nfranceză"
    assert form.value("adresa.oras") == "Cluj-Napoca"


def test_T_H003_unknown_fields_are_ignored_and_reported(form, tmp_path):
    xfdf = tmp_path / "strain.xfdf"
    xfdf.write_text('<?xml version="1.0"?><xfdf xmlns="http://ns.adobe.com/xfdf/">'
                    '<fields><field name="nume"><value>Ion</value></field>'
                    '<field name="lipsa"><value>x</value></field>'
                    '<field name="cod"><value>prea lung</value></field>'
                    '</fields></xfdf>', encoding="utf-8")
    assert form.load_data(xfdf) == (1, ["lipsa", "cod"])
    assert form.value("nume") == "Ion"
    fdf = tmp_path / "strain.fdf"
    fdf.write_bytes(b"%FDF-1.2\n1 0 obj\n<< /FDF << /Fields [ 2 0 R ] >> >>\nendobj\n"
                    b"2 0 obj\n<< /T (adresa) /Kids [ << /T (oras) /V <FEFF0218> >> ] >>\n"
                    b"endobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")
    assert form.load_data(fdf) == (1, [])
    assert form.value("adresa.oras") == "Ș"


def test_T_H003_bad_data_files(form, tmp_path):
    bad = tmp_path / "rau.xfdf"
    bad.write_text('<!DOCTYPE x [<!ENTITY a "b">]><xfdf/>', encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        form.load_data(bad)
    bad.write_text("<xfdf", encoding="utf-8")
    with pytest.raises(FileCorruptError):
        form.load_data(bad)
    bad.write_bytes(b"%FDF-1.2\nfara obiecte\n")
    with pytest.raises(FileCorruptError):
        form.load_data(bad)


def test_T_H004_html_form_data(form, tmp_path):
    form.set_value("nume", "Ana <Maria>")
    out = tmp_path / "date.html"
    form.save_data(out, "html")
    page = out.read_text(encoding="utf-8")
    assert "<th>nume</th><td>Ana &lt;Maria&gt;</td>" in page
    assert "semnatura" not in page and "trimite" not in page
    with pytest.raises(UnsupportedFormatError):
        form.save_data(tmp_path / "x.csv", "csv")
