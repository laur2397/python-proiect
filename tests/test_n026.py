"""N-026: modificarea zonelor sau a setarilor OCR duce statusul paginii inapoi
la `analyzed` (auditul din 23.11.2026, defectul 2). Cazul unei zone schimbate pe
o pagina fara text e si in `test_areas.py` (T-N026.1)."""

from __future__ import annotations

import pytest
from test_service import FakeEngine, text_page

from app.core.context import AppContext
from app.core.errors import PagesNotRecognizedError
from app.core.layout.areas import AreaEditor
from app.core.model import AreaType, AutoProcessMode, PageStatus
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    p.add_images([text_page(tmp_path / f"p{i}.png") for i in range(2)],
                 auto_process=AutoProcessMode.NONE)
    RecognitionService(p, engine=FakeEngine()).recognize_pages()
    assert {pg.status for pg in p.pages} == {PageStatus.RECOGNIZED}
    yield p
    p.close()


def statuses(project):
    return [p.status for p in project.pages]


def test_T_N026_2_moving_a_zone(project):
    page = project.page(1)
    AreaEditor(project).move(page, page.areas[0], 10, 10)
    assert statuses(project) == [PageStatus.ANALYZED, PageStatus.RECOGNIZED]


def test_T_N026_3_changing_the_zone_type(project):
    page = project.page(2)
    AreaEditor(project).change_type(page, page.areas[0], AreaType.PICTURE)
    assert statuses(project) == [PageStatus.RECOGNIZED, PageStatus.ANALYZED]


def test_T_N026_4_rotating_the_page(project):
    project.rotate_pages([1], 90)
    assert statuses(project)[0] == PageStatus.ANALYZED


def test_T_N026_5_changing_the_languages(project):
    project.languages = ["ron", "eng", "fra"]
    assert statuses(project) == [PageStatus.ANALYZED, PageStatus.ANALYZED]
    assert all(p.areas for p in project.pages)  # zonele raman


def test_T_N026_6_ocr_settings_of_the_project_and_global(project, ctx):
    settings = project.settings()
    settings.set("lang.manual", ["eng"])
    settings.set("lang.mode", "manual")
    assert statuses(project) == [PageStatus.ANALYZED, PageStatus.ANALYZED]
    RecognitionService(project, engine=FakeEngine()).recognize_pages()
    assert statuses(project) == [PageStatus.RECOGNIZED, PageStatus.RECOGNIZED]
    ctx.settings.set("ocr.max_threads", 2)  # numai viteza: nu invalideaza
    assert statuses(project) == [PageStatus.RECOGNIZED, PageStatus.RECOGNIZED]
    ctx.settings.set("ocr.quality", "fast")  # Options > OCR, global
    assert statuses(project) == [PageStatus.ANALYZED, PageStatus.ANALYZED]


def test_T_N026_7_export_warns_after_invalidation(project, tmp_path):
    from app.core.export.base import ExportOptions, default_service
    from app.core.model import ExportFormat

    project.languages = ["deu"]
    warnings = default_service().check_before_export(project.pages, ExportOptions(),
                                                     ExportFormat.DOCX)  # Q-051
    [stale] = [w for w in warnings if isinstance(w, PagesNotRecognizedError)]
    assert stale.params["page_numbers"] == [1, 2]
