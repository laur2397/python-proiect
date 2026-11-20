"""Teste pentru RecognitionService (faza 4, pasul 4.3).

Logica serviciului se testeaza cu un motor fals (rapid, fara Tesseract);
recunoasterea automata la adaugare, cu Tesseract real.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.context import AppContext
from app.core.errors import OperationCancelledError
from app.core.model import (
    AutoProcessMode,
    BlockData,
    LineData,
    PageStatus,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult, find_tesseract
from app.core.ocr.service import RecognitionService, default_workers
from app.core.paths import AppPaths
from app.core.project import OcrProject

FONTS = ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
FONT = next((f for f in FONTS if Path(f).is_file()), None)


class FakeEngine:
    """Motor fals: pe fiecare zona de text, cuvantul `pagina<N>`."""

    name = "fals"

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def recognize_page(self, page, settings, cancel=None):
        with self.lock:
            self.calls.append(page.page_number)
        word = WordData(None, f"pagina{page.page_number}", 91.0, bbox=Rect(10, 10, 50, 20),
                        language_code="ron")
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=word.bbox)],
                          bbox=word.bbox)
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=91.0,
                                 area_blocks={area_id: [block]})


def text_page(path, words="Cerere de finantare", dpi=300):
    img = Image.new("L", (1200, 600), 255)
    font = ImageFont.truetype(FONT, 40) if FONT else ImageFont.load_default(size=40)
    ImageDraw.Draw(img).text((80, 200), words, fill=0, font=font)
    img.save(path, dpi=(dpi, dpi))
    return path


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    p.add_images([text_page(tmp_path / f"p{i}.png") for i in range(3)],
                 auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


def svc(project, engine=None):
    return RecognitionService(project, engine=engine or FakeEngine())


# =============================================================================
# N-003, N-004
# =============================================================================


def test_T_N003_1_recognize_all_pages(project):
    """T-N003.1: toate paginile; textul ajunge pe pagini; analiza se face intai (N-004)."""
    engine = FakeEngine()
    assert svc(project, engine).recognize_pages() == [1, 2, 3]
    for n in (1, 2, 3):
        page = project.page(n)
        assert page.status is PageStatus.RECOGNIZED and f"pagina{n}" in page.text
        assert page.areas  # analiza a gasit zonele inainte de recunoastere


def test_T_N003_2_recognized_pages_are_skipped(project):
    """T-N003.2: paginile deja recunoscute nu se reproceseaza."""
    engine = FakeEngine()
    s = svc(project, engine)
    s.recognize_pages([1])
    engine.calls.clear()
    assert s.recognize_pages() == [2, 3]
    assert sorted(engine.calls) == [2, 3]
    engine.calls.clear()
    assert s.recognize_pages() == [] and engine.calls == []
    assert s.recognize_pages([1], skip_recognized=False) == [1]


def test_T_N022_1_progress(project):
    """T-N022.1: progresul si numarul de pagini procesate."""
    seen = []
    svc(project).recognize_pages(progress=seen.append)
    assert [(p.current, p.total) for p in seen] == [(1, 3), (2, 3), (3, 3)]
    assert seen[0].stage == "stage.recognizing"


def test_T_N028_1_cancel_after_current_page(project, ctx):
    """T-N028.1: anularea opreste dupa pagina curenta; paginile terminate raman."""
    ctx.settings.set("ocr.max_threads", 1)
    project.analyze_pages([1, 2, 3])  # anularea se verifica in timpul recunoasterii
    with pytest.raises(OperationCancelledError) as info:
        svc(project).recognize_pages(cancel=lambda: True)
    assert info.value.params["done"] == 1
    statuses = [project.page(n).status for n in (1, 2, 3)]
    assert statuses.count(PageStatus.RECOGNIZED) == 1


def test_T_N027_1_parallel_gives_the_same_result(project, ctx):
    """T-N027.1: mai multe fire, acelasi text pe fiecare pagina."""
    ctx.settings.set("ocr.max_threads", 3)
    svc(project).recognize_pages()
    assert [project.page(n).text for n in (1, 2, 3)] == ["pagina1", "pagina2", "pagina3"]
    assert default_workers(None) >= 1 and default_workers(4) == 4


def test_T_N023_1_low_resolution_warning(ctx, tmp_path):
    """T-N023.1: sub 250 dpi, avertisment pe pagina."""
    p = OcrProject.create(context=ctx)
    p.add_images([text_page(tmp_path / "jos.png", dpi=150)], auto_process=AutoProcessMode.NONE)
    svc(p).recognize_pages()
    (w,) = p.page(1).warnings
    assert w.code == "LOW_RESOLUTION" and w.message_key == "warning.low_resolution"
    p.close()


def test_T_J041_4_recognition_is_one_undo_step_with_text(project):
    """T-J041.4: recunoasterea intra in istoric cu tot cu text; redo il readuce."""
    svc(project).recognize_pages()
    assert project.undo_description() == "undo.recognize_pages"
    project.undo()
    assert project.page(1).text == "" and project.page(1).status is PageStatus.ANALYZED
    project.redo()
    assert project.page(2).text == "pagina2" and project.page(2).status is PageStatus.RECOGNIZED


def test_mark_uncertain(project):
    result = FakeEngine().recognize_page(project.page(1), None)
    s = svc(project)
    s.mark_uncertain(result, 95.0)
    assert result.uncertain_count == 1
    s.mark_uncertain(result, 50.0)
    assert result.uncertain_count == 0


# =============================================================================
# N-001: recunoasterea automata la adaugare (Tesseract real)
# =============================================================================

needs_ocr = pytest.mark.skipif(
    (find_tesseract() is None or FONT is None) and os.environ.get("DOCULENS_REQUIRE_OCR") != "1",
    reason="Tesseract sau fontul lipsesc")


@needs_ocr
def test_T_N001_1_pages_are_recognized_when_added(ctx, tmp_path):
    """T-N001.1: recunoasterea automata e activa implicit."""
    ctx.settings.set("lang.manual", ["ron"])
    ctx.settings.set("lang.mode", "manual")
    p = OcrProject.create(context=ctx)
    p.add_images([text_page(tmp_path / "a.png", "Județul Brașov")])
    page = p.page(1)
    assert page.status is PageStatus.RECOGNIZED
    assert "Brașov" in page.text
    p.close()


def test_analyze_mode_stops_before_recognition(ctx, tmp_path):
    """X-012 `analyze`: analiza se face, recunoasterea se porneste manual."""
    ctx.settings.set("image.auto_mode", "analyze")
    ctx.settings.set("image.correct_orientation", False)
    p = OcrProject.create(context=ctx)
    p.add_images([text_page(tmp_path / "a.png")])
    assert p.page(1).status is PageStatus.ANALYZED and p.page(1).areas
    p.close()
