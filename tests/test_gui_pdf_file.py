"""Salvarea, e-mailul, tiparirea si ajutorul din PDF Editor (faza 7, pasul 7.10):
I-002…I-006, I-020…I-022, D-053."""

from __future__ import annotations

import email
import io
import os

import pikepdf
import pytest
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtPrintSupport import QPrinter

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.gui import pdf_print
from app.gui.pdf_editor import PdfEditorWindow
from app.gui.pdf_print import PrintOptions, PrintSettings, print_document, sheets


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
    w.open_path(text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 6)]))
    yield w
    w.close()


def pdf_printer(path):
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setResolution(72)
    return printer


# --- I-002…I-006 ----------------------------------------------------------------------


def test_T_I002_I005_save_as_menu(window):
    texts = [a.text() for a in window.save_menu.actions() if a.text()]
    assert texts == ["Salvează ca document PDF...", "Document PDF căutabil...",
                     "Document PDF doar imagine...", "Salvează paginile selectate ca...",
                     "Document Word...", "Registru Excel...", "Prezentare PowerPoint...",
                     "Document HTML...", "Imagini TIFF...", "Imagini JPEG...",
                     "Imagini PNG...",  # I-013: celelalte formate
                     "Opțiuni..."]  # E-037: paginile selectate
    asked = []
    window.options_requested.connect(asked.append)
    window.save_menu.actions()[-1].trigger()  # I-005: optiunile PDF
    assert asked == ["format"]
    entries = [a.text() for a in window.recognize_menu.actions() if a.text()]
    assert entries[-3:-1] == \
        ["Recunoaște și verifică în OCR Editor", "Trimite paginile selectate în OCR Editor"]
    assert entries[-1] == "Repară textul copiat greșit (GlyphRecovery)"  # F-057


def test_T_I004_1_image_only_copy(window, tmp_path, monkeypatch):
    target = tmp_path / "imagine.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, d, suffix=".pdf": target)
    assert window.save_as_pdf(False)
    document = window.current().document
    assert document.path == target and not document.has_text_layer(1)
    assert window.tabs.tabText(0) == "imagine.pdf"


def test_T_I003_1_searchable_copy_goes_through_ocr(window, tmp_path, monkeypatch):
    seen = {}

    def save_as(self, path, *, options=None, **kw):
        seen["searchable"] = options.searchable
        seen["context"] = kw.get("context")

    target = tmp_path / "cautabil.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, d, suffix=".pdf": target)
    monkeypatch.setattr(PdfDocument, "save_as", save_as)
    assert window.save_as_pdf(True)
    assert seen["searchable"] is True and seen["context"] is window.context


def test_T_I006_1_save_selected_pages(window, tmp_path, monkeypatch):
    target = tmp_path / "pagini.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, d, suffix=".pdf": target)
    window.pages_panel.list.clearSelection()
    for row in (1, 3):
        window.pages_panel.list.item(row).setSelected(True)
    assert window.selected_pages() == [2, 4]
    window.actions["save_pages"].trigger()  # Ctrl+Alt+S
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 2
    assert window.current().document.path.name == "dosar.pdf"  # documentul ramane


# --- I-020, D-053 ---------------------------------------------------------------------


def test_T_I020_1_email_message_with_the_pdf(window, monkeypatch):
    monkeypatch.setattr(PdfEditorWindow, "ask_email", lambda self, d: ("Dosar", [1, 2]))
    message = window.email_current()
    parsed = email.message_from_bytes(message.read_bytes())
    [attachment] = [p for p in parsed.walk() if p.get_filename()]
    assert attachment.get_filename() == "Dosar.pdf"
    with pikepdf.open(io.BytesIO(attachment.get_payload(decode=True))) as pdf:
        assert len(pdf.pages) == 2


def test_T_D053_1_without_mail_client_the_message_can_be_saved(window, tmp_path,
                                                                monkeypatch):
    messages = []
    target = tmp_path / "mesaj.eml"
    monkeypatch.setattr(PdfEditorWindow, "ask_email", lambda self, d: ("Dosar", None))
    monkeypatch.setattr(PdfEditorWindow, "open_external", lambda self, url: False)
    monkeypatch.setattr(PdfEditorWindow, "show_message", lambda self, t: messages.append(t))
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path",
                        lambda self, d, suffix=".pdf": target if suffix == ".eml" else None)
    window.email_current()
    assert messages and target.exists()


# --- I-021, I-022 ---------------------------------------------------------------------


def test_T_I021_1_no_printer_gives_a_message(window, monkeypatch):
    messages = []
    monkeypatch.setattr(pdf_print, "printers_available", lambda: False)
    monkeypatch.setattr(PdfEditorWindow, "show_message", lambda self, t: messages.append(t))
    assert window.print_current() == 0
    assert messages and "imprimantă" in messages[0]


def test_T_I022_1_printing_through_the_window(window, tmp_path, monkeypatch):
    out = tmp_path / "tiparit.pdf"
    monkeypatch.setattr(pdf_print, "printers_available", lambda: True)
    monkeypatch.setattr(PdfEditorWindow, "choose_print",
                        lambda self, d: (pdf_printer(out), PrintSettings(pages=[1, 3])))
    assert window.actions["print"].isEnabled()
    assert window.print_current() == 2
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2


def test_T_I022_2_pages_per_sheet_and_manual_duplex(tmp_path, qtbot):
    path = text_pdf(tmp_path / "doc.pdf", [[f"Pagina {n}"] for n in range(1, 6)])
    assert sheets([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    with PdfDocument.open(path) as doc:
        assert print_document(doc, pdf_printer(tmp_path / "a.pdf"),
                              PrintSettings(per_sheet=2, grayscale=True)) == 3
        flips = []
        printed = print_document(doc, pdf_printer(tmp_path / "b.pdf"),
                                 PrintSettings(manual_duplex=True),
                                 flip=lambda: flips.append(True) or False)
        assert flips == [True] and printed == 3  # foile impare, apoi pauza refuzata
        printed = print_document(doc, pdf_printer(tmp_path / "c.pdf"),
                                 PrintSettings(manual_duplex=True, scaling="actual",
                                               annotations=False), flip=lambda: True)
        assert printed == 5


def test_T_I022_3_print_options_tab(qtbot):
    options = PrintOptions()
    qtbot.addWidget(options)
    options.annotations.setChecked(False)
    options.grayscale.setChecked(True)
    options.manual_duplex.setChecked(True)
    options.per_sheet.setCurrentIndex(2)
    options.scaling.setCurrentIndex(options.scaling.findData("shrink"))
    settings = options.settings([1, 2])
    assert (settings.pages, settings.annotations, settings.grayscale, settings.per_sheet,
            settings.scaling, settings.manual_duplex) == \
        ([1, 2], False, True, 4, "shrink", True)


# --- F1 -------------------------------------------------------------------------------


def test_help_shows_the_local_manual_or_its_path(window, monkeypatch, tmp_path):
    from app.gui import launcher

    messages = []
    monkeypatch.setattr(PdfEditorWindow, "show_message", lambda self, t: messages.append(t))
    monkeypatch.setattr(launcher, "MANUAL", tmp_path / "lipsa.html")
    assert not window.show_help() and messages
    manual = tmp_path / "manual.html"
    manual.write_text("<html></html>")
    monkeypatch.setattr(launcher, "MANUAL", manual)
    assert window.show_help()
