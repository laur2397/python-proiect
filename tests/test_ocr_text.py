"""Teste fara Tesseract: normalizarea diacriticelor (P-008, decizia 4 din faza 4)."""

from __future__ import annotations

from app.core.ocr.engine import normalize_romanian


def test_T_P008_1_cedilla_becomes_comma():
    """T-P008.1: ş ţ Ş Ţ (sedila) devin ș ț Ș Ț (virgula)."""
    assert normalize_romanian("Ţara ştie: judeţul Şiret") == "Țara știe: județul Șiret"


def test_comma_forms_and_other_text_are_unchanged():
    text = "Șoseaua Țării, județul Iași — 12,5% ÎNVĂȚĂMÂNT"
    assert normalize_romanian(text) == text


def test_cedilla_can_be_kept_for_old_documents():
    assert normalize_romanian("ştiinţă", keep_cedilla=True) == "ştiinţă"
