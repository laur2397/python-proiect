"""Cerintele critice fara test citat, gasite de auditul din 23.11.2026
(defectul 7): N-013, N-025, N-103, P-102, I-018. X-204 si I-032 au testele in
`test_x204.py` si `test_i032.py`."""

from __future__ import annotations

import os
import types

import pytest
from test_pdf_search import text_pdf

from app.core.context import AppContext
from app.core.model import OcrQuality
from app.core.paths import AppPaths
from app.core.settings import OcrSettings


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_N013_thorough_recognition_is_the_default_and_analyzes_blocks(ctx):
    """N-013: `Thorough recognition` (layout complex, fundaluri, tabele) e
    implicita si analizeaza blocurile paginii; `Fast` trateaza zona ca un bloc."""
    from app.core.ocr.engine import _config

    assert ctx.settings.get("ocr.quality") == "thorough"
    assert ctx.settings.ocr_settings().quality is OcrQuality.THOROUGH
    assert "--psm 3" in _config(OcrSettings(quality=OcrQuality.THOROUGH))
    assert "--psm 6" in _config(OcrSettings(quality=OcrQuality.FAST))


def test_T_N025_confidence_threshold_70_marks_uncertain_words(ctx):
    """N-025: pragul de incredere e alegerea noastra, 70; sub el cuvantul e nesigur."""
    from app.core.model import Rect
    from app.core.ocr.engine import TesseractEngine

    assert ctx.settings.get("ocr.confidence_threshold") == 70
    data = {"text": ["sigur", "nesigur"], "conf": [70, 69.9], "block_num": [1, 1],
            "par_num": [1, 1], "line_num": [1, 1], "left": [0, 60], "top": [0, 0],
            "width": [50, 50], "height": [20, 20]}
    engine = TesseractEngine.__new__(TesseractEngine)
    engine.keep_cedilla = False
    [block] = engine._blocks(data, Rect(0, 0, 200, 50), 70, "ron")
    assert [w.is_uncertain for w in block.lines[0].words] == [False, True]


def test_T_N103_more_than_three_languages_are_flagged():
    """N-103: cu cat mai multe limbi, cu atat mai lent; peste trei se semnaleaza."""
    from app.core.ocr.service import MANY_LANGUAGES, RecognitionService

    assert MANY_LANGUAGES == 3
    service = RecognitionService.__new__(RecognitionService)
    page = types.SimpleNamespace(dpi_x=300, dpi_y=300)
    three = service._warnings(page, OcrSettings(languages=("ron", "eng", "fra")))
    four = service._warnings(page, OcrSettings(languages=("ron", "eng", "fra", "deu")))
    assert not [w for w in three if w.code == "MANY_LANGUAGES"]
    [warning] = [w for w in four if w.code == "MANY_LANGUAGES"]
    assert warning.params["count"] == 4


def test_T_P102_every_language_declares_its_dictionary():
    """P-102, P-112: fiecare limba declara daca are dictionar (de el depinde
    verificarea ortografica). Originalul are 53; DocuLens declara ce acopera
    (P-101) — vezi `docs/plan/audit_2026-11-23_reparatii.md`, decizia 1."""
    from app.core.ocr import languages

    catalog = languages._CATALOG
    assert all(isinstance(lang.has_dictionary, bool) for lang in catalog.values())
    assert catalog["ron"].has_dictionary and catalog["ron-MD"].has_dictionary
    assert not catalog["digits"].has_dictionary  # limbile formale nu au dictionar
    assert languages.DICTIONARY_COUNT == sum(1 for lang in catalog.values()
                                             if lang.has_dictionary)


def test_T_I018_sending_to_ocr_editor_warns_what_is_lost(qtbot, ctx, tmp_path, monkeypatch):
    """I-018: atasamentele, semnele de carte, comentariile si adnotarile nu trec
    in OCR Editor; avertismentul apare inainte, iar `Nu` opreste trimiterea."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from app.gui.i18n import tr
    from app.gui.pdf_editor import PdfEditorWindow

    window = PdfEditorWindow(ctx)
    qtbot.addWidget(window)
    window.open_path(text_pdf(tmp_path / "a.pdf", [["Text"]]))
    asked = []
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm",
                        lambda self, text: asked.append(text) or False)
    assert window.send_to_ocr_editor() is None
    assert asked == [tr("pdf.send_ocr.lost")]
    monkeypatch.setattr(PdfEditorWindow, "ask_confirm", lambda self, text: True)
    sent = []
    window.ocr_editor_requested.connect(sent.append)
    path = window.send_to_ocr_editor()
    assert path is not None and sent == [[path]]
    window.close()
