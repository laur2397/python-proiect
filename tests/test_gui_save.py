"""Faza 6b, pasul 6b.6b: salvarea in formate, trimiterea, e-mailul, tiparirea
(Q-001, Q-022, Q-030, Q-040…Q-051, Q-100…Q-104)."""

from __future__ import annotations

import email
import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtPrintSupport import QPrinter

from app.core.context import AppContext
from app.core.errors import CoreError
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    BlockData,
    ExportFormat,
    LayoutMode,
    LineData,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.gui import zones
from app.gui.document_actions import DocumentActions, warning_text
from app.gui.main_window import MainWindow
from app.gui.save_dialog import EmailDialog, SaveDialog, allowed_formats


class ScriptEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        word = WordData(None, f"Cerere{page.page_number}", 95.0, bbox=Rect(100, 100, 300, 40))
        block = BlockData(None, lines=[LineData(None, words=[word],
                                                bbox=Rect(100, 100, 300, 40))],
                          bbox=Rect(100, 100, 300, 40))
        areas = {a.id: [block] for a in page.areas[:1]}
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks=areas)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    paths = []
    for n in (1, 2):
        img = Image.new("L", (600, 800), 255)
        img.paste(0, (100, 100, 400, 140))
        img.save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    w = MainWindow(ctx)
    w.ocr_engine = ScriptEngine()
    qtbot.addWidget(w)
    w.open_images(paths)
    w.recognize()
    yield w
    w.project.close()


@pytest.fixture
def opened(monkeypatch):
    files = []
    monkeypatch.setattr(DocumentActions, "open_file", lambda self, path: files.append(path))
    return files


def set_mode(window, mode):
    window.layout_combo.setCurrentIndex(window.layout_combo.findData(mode.value))


def test_T_Q100_1_save_dialog_fields(qtbot, tmp_path):
    dialog = SaveDialog(LayoutMode.EXACT, "Dosar", tmp_path, "docx")
    qtbot.addWidget(dialog)
    assert dialog.format_key == "docx" and dialog.target == tmp_path / "Dosar.docx"
    assert dialog.open_after.text() == "Deschide documentul după salvare"  # Q-101
    dialog.separate.setCurrentIndex(1)
    assert dialog.separate_files  # Q-022
    dialog.type.setCurrentIndex(dialog.type.findData("pdfa"))
    assert dialog.target.name == "Dosar.pdf"
    with qtbot.waitSignal(dialog.options_requested) as signal:  # Q-102
        dialog.options_button.click()
    assert signal.args == ["pdfa"]


def test_T_Q001_7_save_types_follow_the_layout_mode():
    assert allowed_formats(LayoutMode.FLEXIBLE) == ["pdf_image", "html"]
    exact = allowed_formats(LayoutMode.EXACT)
    assert "txt" not in exact and {"pdf", "pdfa", "pdfua", "docx"} <= set(exact)


def test_save_pdf_and_docx(window, tmp_path, opened):
    docs = window.documents
    set_mode(window, LayoutMode.EXACT)
    written = docs.save_document("pdf", target=tmp_path / "out" / "dosar.pdf",
                                 open_after=True)
    assert written == [tmp_path / "out" / "dosar.pdf"] and written[0].stat().st_size > 0
    assert opened == written  # Q-101
    assert window.statusBar().currentMessage() == "Fișiere salvate: 1"
    docx = docs.save_document("docx", target=tmp_path / "dosar.docx")
    assert docx[0].suffix == ".docx" and docs.last_format == "docx"


def test_T_Q022_2_one_file_per_page(window, tmp_path):
    set_mode(window, LayoutMode.PLAIN)
    written = window.documents.save_document("txt", target=tmp_path / "pagini.txt",
                                             separate=True)
    assert len(written) == 2


def test_format_not_allowed_by_mode_is_refused(window, tmp_path):
    set_mode(window, LayoutMode.FLEXIBLE)
    assert window.documents.save_document("docx", target=tmp_path / "x.docx") == []
    assert window.statusBar().currentMessage() != ""


def test_save_buttons_use_the_format_menu(window, monkeypatch):
    calls = []
    monkeypatch.setattr(DocumentActions, "save_document",
                        lambda self, key=None, **kw: calls.append(key))
    window.save_actions["docx"].trigger()
    window.save_button.click()
    assert calls == ["docx", None]


def test_T_Q051_2_warning_before_export(window, tmp_path, monkeypatch):
    AreaEditor(window.project).create(window.project.page(1),
                                      zones.rect_points(Rect(10, 500, 200, 100)),
                                      AreaType.TEXT)  # zona noua invalideaza pagina
    seen = []
    monkeypatch.setattr(DocumentActions, "ask_continue",
                        lambda self, warnings: seen.extend(warnings) or False)
    set_mode(window, LayoutMode.EXACT)
    assert window.documents.save_document("pdf", target=tmp_path / "x.pdf") == []
    assert seen and seen[0].startswith("Unele pagini nu sunt recunoscute")
    assert not (tmp_path / "x.pdf").exists()


def test_T_Q104_1_mrc_warning_text():
    assert warning_text(CoreError("warning.mrc_precisescan")).startswith("Compresia MRC")


def test_T_Q030_1_save_page_images(window, tmp_path):
    written = window.save_page_images([1, 2], tmp_path / "pagini.png")
    assert len(written) == 2 and all(p.suffix == ".png" for p in written)
    assert window.pages_panel.actions["save"].isEnabled()
    assert window.image_panel.actions["save_page"].isEnabled()


def test_T_Q040_1_send_to_pdf_editor(window, opened):
    path = window.documents.send_to_pdf_editor()
    assert path.suffix == ".pdf" and opened == [path]
    assert window.statusBar().currentMessage().startswith("Atașamentele")  # Q-041


def test_T_Q046_1_and_Q048_1_send_to_applications(window, opened):
    word = window.documents.send_to_application(ExportFormat.DOCX)
    html = window.documents.send_to_application(ExportFormat.HTML)
    assert word.suffix == ".docx" and html.suffix == ".html" and opened == [word, html]


def test_T_Q047_1_clipboard(window):
    from PySide6.QtWidgets import QApplication

    text = window.documents.send_to_clipboard()
    assert "Cerere1" in text and "Cerere2" in text
    assert QApplication.clipboard().text() == text


def test_T_Q042_1_email_document_without_html(qtbot, window, opened):
    dialog = EmailDialog()
    qtbot.addWidget(dialog)
    keys = [dialog.type.itemData(i) for i in range(dialog.type.count())]
    assert "html" not in keys and "pdf" in keys
    assert [dialog.split.itemData(i) for i in range(dialog.split.count())] == [
        "all", "per_page", "blank_pages"]  # Q-043
    set_mode(window, LayoutMode.EXACT)
    eml = window.documents.email_document("pdf", "per_page")
    message = email.message_from_bytes(eml.read_bytes())
    assert len([p for p in message.walk() if p.get_filename()]) == 2
    assert opened == [eml]


def test_T_Q044_1_email_images_multipage(window):
    eml = window.documents.email_images("tiff", multipage=True)
    message = email.message_from_bytes(eml.read_bytes())
    names = [p.get_filename() for p in message.walk() if p.get_filename()]
    assert len(names) == 1 and names[0].endswith(".tif")


def test_T_Q045_1_kindle(window):
    assert window.documents.send_to_kindle("nu-e-kindle@exemplu.ro") is None
    assert window.statusBar().currentMessage() == "Datele trimiterii nu sunt valide"
    eml = window.documents.send_to_kindle("ana@kindle.com", name="Carte")
    message = email.message_from_bytes(eml.read_bytes())
    assert message["To"] == "ana@kindle.com"
    assert [p.get_filename() for p in message.walk() if p.get_filename()] == ["Carte.epub"]


def _pdf_printer(path):
    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    return printer


def test_T_Q049_1_print_text(window, tmp_path):
    import pypdfium2 as pdfium

    assert window.actions["print_text"].shortcut().toString() == "Ctrl+P"
    text = window.documents.text_document().toPlainText()
    assert "Cerere1" in text and "Cerere2" in text
    assert window.documents.print_text(_pdf_printer(tmp_path / "text.pdf"))
    # textul tiparit poate fi desenat ca contururi (Windows, fara fonturi reale),
    # deci se verifica foile: una pe pagina recunoscuta
    assert len(pdfium.PdfDocument(tmp_path / "text.pdf")) == 2
    assert not window.documents.print_text()  # nicio imprimanta aleasa: nimic


def test_T_Q050_1_print_images(window, tmp_path):
    import pypdfium2 as pdfium

    assert window.actions["print_image"].shortcut().toString() == "Ctrl+Alt+P"
    assert window.documents.print_images(_pdf_printer(tmp_path / "img.pdf"))
    assert len(pdfium.PdfDocument(tmp_path / "img.pdf")) == 2


def test_menus_and_shortcuts(window):
    assert window.actions["email_document"].shortcut().toString() == "Ctrl+M"
    assert window.actions["email_images"].shortcut().toString() == "Ctrl+Alt+M"
    send_to = [a.objectName() for a in window.menus["send_to"].actions()]
    assert send_to == ["send_pdf_editor", "send_word", "send_excel", "send_powerpoint",
                       "send_browser", "send_clipboard", "send_kindle"]
    assert window.menus["send_to"].menuAction() in window.menus["file"].actions()
