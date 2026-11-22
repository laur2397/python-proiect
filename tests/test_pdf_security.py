"""Parole, permisiuni si stergerea datelor (faza 10, pasul 10.1): G-001…G-012,
G-022…G-024, G-100, G-101, G-111."""

from __future__ import annotations

import pikepdf
import pytest
from test_pdf_search import text_pdf

from app.core.errors import SamePasswordError, WrongPasswordError
from app.core.model import EncryptionLevel, PrintPermission
from app.core.pdf.document import PdfDocument
from app.core.pdf.security import REDACTION_COLORS, SecurityOptions, SecurityService


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [["Pagina 1"], ["Pagina 2"]])
    with PdfDocument.open(path) as d:
        yield d


# --- G-002…G-012 ----------------------------------------------------------------------------


def test_T_G002_G004_passwords_must_differ():
    with pytest.raises(SamePasswordError):
        SecurityOptions(open_password="abc", permissions_password="abc").validate()
    with pytest.raises(ValueError):
        SecurityOptions().validate()
    SecurityOptions(open_password="abc").validate()
    SecurityOptions(permissions_password="xyz").validate()


def test_T_G002_G005_open_password_and_permissions_password_both_open(doc, tmp_path):
    SecurityService().apply(doc, SecurityOptions(open_password="deschide",
                                                 permissions_password="permite"))
    target = tmp_path / "protejat.pdf"
    doc.save_as(target)
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(target)
    with pikepdf.open(target, password="deschide") as pdf:
        assert pdf.is_encrypted and not pdf.owner_password_matched
    with pikepdf.open(target, password="permite") as pdf:  # G-005
        assert pdf.owner_password_matched
    assert doc.is_encrypted and doc.path == target
    assert doc.extract_text(1).strip() == "Pagina 1"  # documentul ramane deschis
    with PdfDocument.open(target, password=lambda p: "permite") as again:
        assert again.page_count == 2


def test_T_G006_G007_G008_G009_permissions(doc, tmp_path):
    SecurityService().apply(doc, SecurityOptions(
        permissions_password="permite", print_permission=PrintPermission.LOW_RES,
        allow_editing=False, allow_copying=False, allow_screen_readers=True,
        allow_annotations=False, allow_form_filling=True, allow_assembly=False))
    target = tmp_path / "restrictii.pdf"
    doc.save_as(target)
    with pikepdf.open(target) as pdf:  # fara parola de deschidere
        allow = pdf.allow
        assert allow.print_lowres and not allow.print_highres
        assert not allow.modify_other and not allow.extract and allow.accessibility
        assert not allow.modify_annotation and allow.modify_form
        assert not allow.modify_assembly
    with PdfDocument.open(target) as again:
        assert again.permissions["modify_other"] is False


def test_T_G010_G011_encryption_level_and_metadata(doc, tmp_path):
    for level, revision in ((EncryptionLevel.AES_128, 4), (EncryptionLevel.AES_256, 6)):
        SecurityService().apply(doc, SecurityOptions(open_password="x", encryption=level,
                                                     encrypt_metadata=False))
        target = tmp_path / f"{level.value}.pdf"
        doc.save_as(target)
        with pikepdf.open(target, password="x") as pdf:
            assert pdf.encryption.R == revision and pdf.encryption.bits >= 128
            assert pdf.encryption.stream_method.name.startswith("aes")


def test_T_G012_save_over_the_open_document(doc):
    SecurityService().apply(doc, SecurityOptions(open_password="deschide"))
    assert doc.is_modified
    doc.save()
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(doc.path)
    doc.set_metadata(title="Dupa protectie")  # documentul se poate salva din nou
    doc.save()
    with pikepdf.open(doc.path, password="deschide") as pdf:
        assert str(pdf.docinfo["/Title"]) == "Dupa protectie"


def test_remove_protection_needs_the_permissions_password(doc):
    service = SecurityService()
    service.apply(doc, SecurityOptions(open_password="deschide",
                                       permissions_password="permite"))
    doc.save()
    with pytest.raises(WrongPasswordError):
        service.remove_protection(doc, "deschide")
    service.remove_protection(doc, "permite")
    doc.save()
    with pikepdf.open(doc.path) as pdf:
        assert not pdf.is_encrypted
    assert not doc.is_encrypted


# --- G-022…G-024, G-111 ---------------------------------------------------------------------


def rich_pdf(path):
    text_pdf(path, [["Pagina 1"], ["Pagina 2"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        link = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[0, 0, 10, 10],
            A=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String("https://a.ro"))))
        page.obj.Annots.append(link)
        pdf.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript,
                                                 JS=pikepdf.String("app.alert(1)"))
        pdf.attachments["buget.xlsx"] = pikepdf.AttachedFileSpec(pdf, b"x",
                                                                 filename="buget.xlsx")
        pdf.docinfo["/Author"] = "Ana Popescu"
        pdf.save(path)
    return path


def test_T_G022_G111_delete_selected_objects_and_data(tmp_path):
    with PdfDocument.open(rich_pdf(tmp_path / "bogat.pdf")) as doc:
        counts = SecurityService().delete_objects_and_data(
            doc, comments_and_markup=True, links_media_actions_scripts_form_data=True,
            bookmarks=True, attachments=True, metadata=True)
        assert counts["comments"] == 1 and counts["links"] >= 2
        assert counts["bookmarks"] == 1 and counts["attachments"] == 1
        assert doc.annotations() == [] and doc.links(1) == []
        assert doc.bookmarks() == [] and doc.attachments() == []
        assert doc.metadata() == {}
        assert "/OpenAction" not in doc._pike().Root
        assert doc.extract_text(1).strip() == "Pagina 1"  # continutul ramane


def test_T_G023_only_the_selected_categories(tmp_path):
    with PdfDocument.open(rich_pdf(tmp_path / "bogat.pdf")) as doc:
        SecurityService().delete_objects_and_data(doc, bookmarks=True)
        assert doc.bookmarks() == [] and len(doc.annotations()) == 1
        assert doc.attachments() and doc.metadata()["author"] == "Ana Popescu"


def test_T_G024_hidden_text_and_objects_makes_an_image_only_pdf(doc):
    from app.core.pdf.organize import PageOrganizer

    PageOrganizer(doc).rotate([2], 90)
    SecurityService().delete_objects_and_data(doc, hidden_text_and_objects=True)
    assert doc.extract_text(1).strip() == "" and doc.extract_text(2).strip() == ""
    assert doc.page_count == 2
    width, height = doc.page_size(2)
    assert width > height  # pagina rotita ramane asa cum se vedea
    assert doc.annotations(1)  # adnotarile au bifa lor


def test_T_G100_G101_redaction_colors_are_a_setting(tmp_path):
    from app.core.context import AppContext
    from app.core.paths import AppPaths

    assert len(REDACTION_COLORS) == 8 and REDACTION_COLORS[-1] == "#000000"
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        assert ctx.settings.get("pdf_editor.redaction_color") == "#000000"
        assert len(ctx.settings.get("pdf_editor.redaction_colors")) == 8
        ctx.settings.set("pdf_editor.redaction_colors", ["#000000", "#ffffff"])
        assert ctx.settings.get("pdf_editor.redaction_colors") == ["#000000", "#ffffff"]
    finally:
        ctx.close()
