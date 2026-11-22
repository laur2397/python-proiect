"""Setari comune pentru teste.

Ferestrele OCR Editor-ului intreaba la inchidere daca se salveaza proiectul
modificat (dialog modal). In teste nu raspunde nimeni, asa ca raspunsul
implicit e `discard`; testele care verifica intrebarea il inlocuiesc. La fel,
fisierele salvate nu se deschid in aplicatiile sistemului.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_modal_save_question(monkeypatch):
    try:
        from app.gui.main_window import MainWindow
    except ImportError:  # fara PySide6: testele de interfata se sar oricum
        yield
        return
    from app.gui.document_actions import DocumentActions

    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "discard")
    # nimic nu se deschide in aplicatiile sistemului si nu apar dialoguri modale
    monkeypatch.setattr(DocumentActions, "open_file", lambda self, path: None)
    monkeypatch.setattr(DocumentActions, "ask_continue", lambda self, warnings: True)
    monkeypatch.setattr(DocumentActions, "ask_password", lambda self: None)
    monkeypatch.setattr(DocumentActions, "choose_printer", lambda self: None)
    from PySide6.QtWidgets import QMessageBox

    from app.gui.pdf_editor import PdfEditorWindow

    # PDF Editor: aceleasi raspunsuri implicite, fara ferestre modale
    monkeypatch.setattr(PdfEditorWindow, "ask_save", lambda self, document: "discard")
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm", lambda self, text: True)
    monkeypatch.setattr(PdfEditorWindow, "ask_allow", lambda self, kind, target: True)
    monkeypatch.setattr(PdfEditorWindow, "ask_password", lambda self: None)
    monkeypatch.setattr(PdfEditorWindow, "ask_save_path", lambda self, document: None)
    monkeypatch.setattr(PdfEditorWindow, "open_external", lambda self, url: None)
    monkeypatch.setattr(PdfEditorWindow, "show_message", lambda self, text: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    yield
