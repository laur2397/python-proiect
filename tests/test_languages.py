"""Teste cu Tesseract (faza 4, pasul 4.5.1): alegerea automata a limbii (P-001).

Avertismentul la multe limbi (P-009) nu depinde de motor: e in test_service.py.

Se sar daca Tesseract nu e instalat, in afara de CI, unde
DOCULENS_REQUIRE_OCR=1 face ca lipsa lui sa fie o eroare.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.model import AutoProcessMode
from app.core.ocr.engine import find_tesseract
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject

if find_tesseract() is None:
    if os.environ.get("DOCULENS_REQUIRE_OCR") == "1":
        raise RuntimeError("CI cere Tesseract, dar nu e instalat")
    pytest.skip("Tesseract nu e instalat", allow_module_level=True)

FONTS = [
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "C:/Windows/Fonts/times.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
FONT_PATH = next((f for f in FONTS if Path(f).is_file()), None)
if FONT_PATH is None:
    pytest.skip("niciun font cu diacritice romanesti", allow_module_level=True)

ROMANIAN = ["Subsemnatul Popescu Ștefan, domiciliat în municipiul Brașov,",
            "declar pe propria răspundere că informațiile din această",
            "cerere de finanțare sunt corecte și complete."]
ENGLISH = ["The applicant hereby declares that the information provided",
           "in this funding application is accurate and complete, and",
           "acknowledges that any false statement leads to rejection."]


def page_image(path: Path, lines: list[str]) -> Path:
    img = Image.new("L", (2480, 1200), 255)
    font = ImageFont.truetype(FONT_PATH, 48)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((150, 200 + i * 90), line, fill=0, font=font)
    img.save(path, dpi=(300, 300))
    return path


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def make_project(ctx, tmp_path, pages):
    p = OcrProject.create(context=ctx)
    p.add_images([page_image(tmp_path / f"p{i}.png", lines) for i, lines in enumerate(pages)],
                 auto_process=AutoProcessMode.NONE)
    return p


def test_T_P001_1_auto_mode_picks_the_page_language(ctx, tmp_path):
    """T-P001.1: din lista ron+eng se alege limba fiecarei pagini, iar pagina
    romaneasca isi pastreaza diacriticele (cu ambele limbi deodata le pierde)."""
    ctx.settings.set("lang.mode", "auto")
    ctx.settings.set("lang.auto_candidates", ["ron", "eng"])
    project = make_project(ctx, tmp_path, [ROMANIAN, ENGLISH])
    try:
        service = RecognitionService(project)
        project.analyze_pages([1, 2])
        settings = project.settings().ocr_settings()
        assert service.choose_language(project.page(1), settings) == "ron"
        assert service.choose_language(project.page(2), settings) == "eng"
        assert service.recognize_pages() == [1, 2]
        text = project.page(1).text
        for word in ("Ștefan", "Brașov", "răspundere", "informațiile", "finanțare"):
            assert word in text, (word, text)
        assert "applicant" in project.page(2).text
        # in modul automat se recunoaste cu o singura limba: fara P-009
        assert not [w for w in project.page(1).warnings if w.code == "MANY_LANGUAGES"]
    finally:
        project.close()


def test_T_P001_2_single_candidate_needs_no_probe(ctx, tmp_path):
    """T-P001.2: cu o singura limba in lista nu se face nicio mostra."""
    ctx.settings.set("lang.mode", "auto")
    ctx.settings.set("lang.auto_candidates", ["ron"])
    project = make_project(ctx, tmp_path, [ROMANIAN])
    try:
        service = RecognitionService(project)
        calls = []
        original = service.choose_language
        service.choose_language = lambda *a: calls.append(a) or original(*a)
        service.recognize_pages()
        assert calls == [] and "Ștefan" in project.page(1).text
    finally:
        project.close()
