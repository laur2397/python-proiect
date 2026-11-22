"""Tabul `Security` din PDF Editor (faza 10, pasul 10.4): G-001…G-055, G-100…G-111."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_dossier import pkcs12
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialogButtonBox

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.gui.pdf_editor import LATER, PdfEditorWindow
from app.gui.pdf_security_ui import REASON_KEYS, DeleteObjectsDialog, SignDialog


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
    w.open_path(text_pdf(tmp_path / "dosar.pdf", [["Pagina 1", "Text secret"], ["Pagina 2"]]))
    yield w
    w.close()


def answer(monkeypatch, fill):
    def run(self, dialog):
        fill(dialog)
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", run)


def doc(window):
    return window.current().document


def test_security_commands_are_enabled():
    for key in ("signature", "password_security", "delete_objects", "watermark"):
        assert key not in LATER


# --- G-001…G-012 -------------------------------------------------------------------------------


def test_T_G001_G012_password_security_saved_over_the_document(window, monkeypatch):
    def fill(dialog):
        dialog.use_open.setChecked(True)
        dialog.open.setText("deschide")
        dialog.open_again.setText("deschide")
        dialog.use_permissions.setChecked(True)
        dialog.permissions.setText("permite")
        dialog.permissions_again.setText("permite")
        dialog.hide.setChecked(False)  # G-003
        assert dialog.open.echoMode() == dialog.open.EchoMode.Normal
    answer(monkeypatch, fill)
    again = {"security.again_open": "deschide", "security.again_permissions": "permite"}
    monkeypatch.setattr(PdfEditorWindow, "ask_password_again", lambda self, key: again[key])
    window.actions["password_security"].trigger()
    path = doc(window).path
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(path)
    with pikepdf.open(path, password="permite") as pdf:
        assert pdf.owner_password_matched


def test_T_G002_G004_mismatch_and_same_passwords_give_a_message(window, monkeypatch):
    messages = []
    window.show_message = messages.append

    def mismatch(dialog):
        dialog.use_open.setChecked(True)
        dialog.open.setText("a")
        dialog.open_again.setText("b")
    answer(monkeypatch, mismatch)
    assert not window.password_security()

    def same(dialog):
        for box, edits in ((dialog.use_open, (dialog.open, dialog.open_again)),
                           (dialog.use_permissions,
                            (dialog.permissions, dialog.permissions_again))):
            box.setChecked(True)
            for edit in edits:
                edit.setText("aceeasi")
    answer(monkeypatch, same)
    assert not window.password_security()
    assert len(messages) == 2


# --- G-020, G-100…G-103 -----------------------------------------------------------------------


def test_T_G020_G100_G101_G103_redaction_mode_with_colors(window, monkeypatch):
    window.actions["redact"].trigger()
    assert window.actions["redact"].isChecked() and window.redact_bar.isVisible()
    assert len(window.redact_buttons) == 8 and window.redact_buttons["#000000"].isChecked()
    window.redact_buttons["#e53935"].trigger()
    assert window.redact_color == "#e53935"
    monkeypatch.setattr(PdfEditorWindow, "ask_color", lambda self, current: "#123456")
    [more] = [a for a in window.redact_bar.actions() if a.objectName() == "redact_more_colors"]
    more.trigger()
    assert window.redact_color == "#123456"
    [hit] = doc(window).search("Text secret", in_comments=False, in_bookmarks=False,
                               in_metadata=False)
    rect = hit[1]
    window.picker.done(1, Rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4))
    assert "secret" not in doc(window).extract_text(1)
    assert window.picker is not None  # modul ramane activ
    window.actions["redact"].trigger()
    assert not window.redact_bar.isVisible()


# --- G-022…G-024, G-111 -----------------------------------------------------------------------


def test_T_G111_delete_objects_dialog(qtbot):
    dialog = DeleteObjectsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(dialog.boxes) == 6 and not dialog.warning.isVisible()
    dialog.boxes["hidden_text_and_objects"].setChecked(True)
    assert dialog.warning.isVisible()


def test_T_G022_G024_delete_objects_from_the_window(window, monkeypatch):
    def fill(dialog):
        dialog.boxes["comments_and_markup"].setChecked(True)
        dialog.boxes["hidden_text_and_objects"].setChecked(True)
    answer(monkeypatch, fill)
    counts = window.delete_objects()
    assert counts["comments"] == 1 and counts["pages"] == 2
    assert doc(window).extract_text(1).strip() == ""


# --- G-030…G-045, G-104…G-108 -----------------------------------------------------------------


def test_T_G031_G104_sign_dialog_without_certificate(window):
    dialog = SignDialog(window._signature_service(), window.settings, 1,
                        Rect(300, 600, 200, 60))
    assert not dialog.missing.isHidden()
    assert not dialog.box.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert dialog.reason.count() == len(REASON_KEYS) == 5  # G-104
    dialog.location.setText("Cluj")
    dialog.flags["location"].setChecked(True)
    assert "Cluj" in dialog.preview.text()  # G-105


def test_T_G030_G040_G042_G043_sign_from_the_window(window, monkeypatch, tmp_path):
    cert = pkcs12(tmp_path)
    monkeypatch.setattr(PdfEditorWindow, "ask_open_file", lambda self, title: cert)
    monkeypatch.setattr(PdfEditorWindow, "ask_password", lambda self: "parola")
    assert window.add_certificate()

    def fill(dialog):
        assert dialog.certificate.count() == 1
        dialog.reason.setCurrentIndex(0)
    answer(monkeypatch, fill)
    window.signature_menu.actions()[0].trigger()  # G-110: semnatura digitala
    window.picker.done(1, Rect(300, 600, 220, 70))
    [sig] = window._signature_service().validate_all(doc(window))
    assert sig["status"] == "valid"  # G-108
    assert window.signatures_panel.list.count() == 1
    window.show_message = lambda text: None
    text = window.signature_properties(sig["field_name"])  # G-042
    assert "Firma de test SRL" in text and "SHA-256" in text
    assert window.remove_signature(sig["field_name"])  # G-043
    assert doc(window).is_modified


# --- G-050…G-055 -------------------------------------------------------------------------------


def test_T_G050_G052_G054_text_signature_from_the_menu(window, monkeypatch):
    replies = iter(["Ana Popescu", "Ana"])
    monkeypatch.setattr(PdfEditorWindow, "ask_text",
                        lambda self, t, label, default="": next(replies))
    assert window.create_text_signature() == "Ana"
    window._fill_signature_menu()
    assert "Ana" in [a.text() for a in window.signature_menu.actions()]
    window.start_place_signature("Ana")
    window.picker.done(1, Rect(300, 600, 150, 40))
    stamps = [a for a in doc(window).annotations(1) if a.annot_type.value == "stamp"]
    assert len(stamps) == 1 and stamps[0].bbox.w == pytest.approx(150, abs=1)
    dialog = window.manage_signatures()
    dialog.buttons["delete"].click()  # G-055
    assert dialog.list.count() == 0
