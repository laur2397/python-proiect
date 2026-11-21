"""Setari comune pentru teste.

Ferestrele OCR Editor-ului intreaba la inchidere daca se salveaza proiectul
modificat (dialog modal). In teste nu raspunde nimeni, asa ca raspunsul
implicit e `discard`; testele care verifica intrebarea il inlocuiesc.
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
    monkeypatch.setattr(MainWindow, "ask_save", lambda self: "discard")
    yield
