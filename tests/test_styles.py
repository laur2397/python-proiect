"""Faza 5, pasul 5.3: stilurile (O-035..O-041, O-110, O-111)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.layout import structure
from app.core.layout.areas import AreaEditor
from app.core.model import (
    AreaType,
    AutoProcessMode,
    BlockData,
    LineData,
    Rect,
    WordData,
)
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.text.editor import TextEditor
from app.core.text.styles import StyleManager, heading_name


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("lang.mode", "manual")
    c.settings.set("lang.manual", ["ron"])
    yield c
    c.close()


@pytest.fixture
def styles(ctx):
    return StyleManager(ctx.app_db)


def test_T_O110_1_builtin_heading_styles(styles):
    """T-O110.1: `Heading 1`…`Heading 10`, cu rolul de titlu; nu se sterg."""
    names = {s.name for s in styles.all() if s.is_builtin}
    assert {heading_name(i) for i in range(1, 11)} <= names
    assert styles.get("Heading 3").heading_level == 3
    with pytest.raises(ValueError):
        styles.delete("Heading 1")
    with pytest.raises(ValueError):
        styles.update("Heading 1", name="Titlu")


def test_T_O037_1_create_and_edit(styles):
    """T-O037.1 / O-038: nume unic; numele, fontul, marimea, spatierea, scara."""
    s = styles.create("Corp dosar", font_name="Liberation Serif", font_size=11)
    assert (s.font_name, s.font_size, s.horizontal_scale) == ("Liberation Serif", 11, 100.0)
    with pytest.raises(ValueError, match="exista deja"):
        styles.create("Corp dosar")
    s = styles.update("Corp dosar", name="Corp", letter_spacing=0.5, horizontal_scale=95,
                      is_bold=True, heading_level=2)
    assert (s.name, s.letter_spacing, s.horizontal_scale, s.is_bold, s.heading_level) == (
        "Corp", 0.5, 95, True, 2)
    for bad in ({"heading_level": 11}, {"font_size": 0}, {"horizontal_scale": 0},
                {"culoare": "rosu"}):
        with pytest.raises(ValueError):
            styles.update("Corp", **bad)


class ScriptEngine:
    """Doua pagini: un titlu mare, un subtitlu mai mic, apoi text obisnuit."""

    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        result = RecognitionResult(page.page_number)
        for area, (text, size) in zip(sorted(page.areas, key=lambda a: a.bbox.y),
                                      [("Capitolul 1", 80), ("Bugetul", 56),
                                       ("Text obisnuit al cererii", 40)], strict=False):
            lines = []
            for i in range(1 if size > 40 else 4):
                top = area.bbox.y + i * size
                w = WordData(None, text, 95.0, bbox=Rect(area.bbox.x, top, 600, size),
                             language_code="ron")
                lines.append(LineData(None, words=[w], bbox=w.bbox))
            block = BlockData(None, lines=lines, bbox=area.bbox)
            result.blocks.append(block)
            result.area_blocks[area.id] = [block]
        return result

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


@pytest.fixture
def project(ctx, tmp_path):
    paths = []
    for n in (1, 2):
        Image.new("L", (2480, 3508), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        paths.append(tmp_path / f"p{n}.png")
    p = OcrProject.create(context=ctx)
    p.add_images(paths, auto_process=AutoProcessMode.NONE)
    ed = AreaEditor(p)
    for n in (1, 2):
        for y0, y1 in ((500, 600), (800, 880), (1200, 1400)):
            ed.create(p.page(n), [(200, y0), (2200, y0), (2200, y1), (200, y1)], AreaType.TEXT)
    RecognitionService(p, engine=ScriptEngine()).recognize_pages()
    yield p
    p.close()


def blocks(project, n):
    return [b for a in sorted(project.page(n).areas, key=lambda a: a.bbox.y) for b in a.blocks]


def test_T_O111_1_detected_headings_get_heading_styles(project):
    """T-O111.1: titlurile detectate primesc `Heading N` dupa marime."""
    for n in (1, 2):
        title, sub, body = blocks(project, n)
        assert (title.block_type, title.style_name) == ("heading", "Heading 1")
        assert (sub.block_type, sub.style_name) == ("heading", "Heading 2")
        assert (body.block_type, body.style_name) == ("paragraph", None)


def test_T_O035_1_apply_style_and_fragments(project, styles):
    """T-O035.1 / O-040: stilul aplicat; fragmentele care il folosesc."""
    styles.create("Important", is_bold=True)
    body1 = blocks(project, 1)[2]
    body2 = blocks(project, 2)[2]
    TextEditor(project).apply_style([body1, body2], styles.get("Important"))
    found = styles.fragments_using(project.pages, "Important")
    assert [b.id for b in found] == [body1.id, body2.id]
    assert len(styles.fragments_using(project.pages, "Heading 1")) == 2
    project.undo()
    assert styles.fragments_using(project.pages, "Important") == []


def test_T_O039_1_merge_styles(project, styles):
    """T-O039.1: blocurile trec la stilul ales, stilurile unite dispar."""
    a, b = styles.create("A"), styles.create("B")
    TextEditor(project).apply_style([blocks(project, 1)[2]], a)
    TextEditor(project).apply_style([blocks(project, 2)[2]], b)
    styles.merge([a, b], "B", project)
    assert len(styles.fragments_using(project.pages, "B")) == 2
    assert "A" not in [s.name for s in styles.all()]
    with pytest.raises(ValueError):
        styles.merge([b], "nu-exista")


def test_T_O041_1_plain_text_is_not_a_heading():
    """O-111 nu marcheaza textul obisnuit ca titlu (dimensiune egala)."""
    from pathlib import Path

    from app.core.model import AreaData, ColorMode, PageData

    page = PageData(1, 1, Path("x"), Path("x"), 2480, 3508, 300, 300, ColorMode.GRAY)
    for i in range(3):
        w = WordData(None, "text", 90.0, bbox=Rect(100, 500 + 100 * i, 300, 40))
        b = BlockData(None, lines=[LineData(None, words=[w], bbox=w.bbox)], bbox=w.bbox)
        page.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=w.bbox, blocks=[b]))
    structure.detect([page])
    assert all(a.blocks[0].block_type == "paragraph" for a in page.areas)
