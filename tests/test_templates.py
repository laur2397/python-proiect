"""Teste pentru sabloanele de zone (faza 3, pasul 3c)."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.errors import (
    FileCorruptError,
    TemplateSizeMismatchError,
    UnsupportedFormatError,
)
from app.core.layout.areas import TEMPLATE_FORMAT, AreaEditor
from app.core.layout.geometry import area_of
from app.core.model import AreaType, AutoProcessMode, Rect, TextFunction
from app.core.paths import AppPaths
from app.core.project import OcrProject

T = AreaType
# T-M032 la scara mica: conteaza doar dimensiunea si rezolutia
A4_300 = (620, 877, 75)
A4_600 = (1240, 1754, 150)  # aceeasi pagina, rezolutie dubla
LETTER_300 = (638, 825, 75)


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    p = OcrProject.create(context=ctx)
    paths = []
    for i, (w, h, dpi) in enumerate([A4_300, A4_300, A4_600, LETTER_300]):
        path = tmp_path / f"p{i}.png"
        Image.new("L", (w, h), 255).save(path, dpi=(dpi, dpi))
        paths.append(path)
    p.add_images(paths, auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


@pytest.fixture
def ed(project):
    return AreaEditor(project)


@pytest.fixture
def template(ed, project, tmp_path):
    """Sablon facut pe pagina 1 (A4 la 300 dpi): titlu, text in L, cod de bare."""
    pg = project.page(1)
    title = ed.create(pg, rect(20, 20, 580, 80), T.TEXT)
    ed.set_properties(project.page(1), title, text_function="header")
    body = ed.create(project.page(1), rect(20, 120, 400, 400), T.TEXT)
    ed.cut_part(project.page(1), body, Rect(320, 120, 100, 100))
    ed.set_language(project.page(1), [project.page(1).areas[1]], ["deu"])
    bc = ed.create(project.page(1), rect(450, 700, 150, 100), T.BARCODE)
    ed.set_properties(project.page(1), bc, barcode_type="qrcode")
    path = tmp_path / "sabloane" / "factura.blkx"
    ed.save_template(project.page(1), path, "Factura")
    return path


def summary(page):
    return [(a.area_type, a.bbox, a.text_function, a.language_codes, a.barcode_type)
            for a in page.areas]


# =============================================================================
# M-031: salvare
# =============================================================================


def test_T_M031_1_template_file(template, project):
    """T-M031.1: sablonul contine pozitiile, tipurile si proprietatile zonelor."""
    data = json.loads(template.read_text(encoding="utf-8"))
    assert data["format"] == TEMPLATE_FORMAT and data["name"] == "Factura"
    assert data["source"] == {"width": 620, "height": 877, "dpi_x": 75, "dpi_y": 75}
    assert [a["type"] for a in data["areas"]] == ["text", "text", "barcode"]
    assert data["areas"][0]["properties"]["text_function"] == "header"
    assert data["areas"][1]["properties"]["language_codes"] == ["deu"]
    assert data["areas"][2]["properties"]["barcode_type"] == "qrcode"
    assert not list(template.parent.glob(".*.tmp"))


def test_template_is_also_kept_in_the_library(ed, template, project, tmp_path):
    assert ed.library_templates() == ["Factura"]
    ed.save_template(project.page(1), tmp_path / "alt.blkx", "Factura")  # inlocuieste
    assert ed.library_templates() == ["Factura"]
    (count,) = project._ctx.app_db.execute("SELECT COUNT(*) FROM area_template_item").fetchone()
    assert count == 3


@pytest.mark.parametrize(("name", "fname"), [("", "a.blkx"), ("X", "a.blk"), ("X", "a.json")])
def test_save_needs_a_name_and_the_blkx_extension(ed, template, project, tmp_path, name, fname):
    with pytest.raises(ValueError):
        ed.save_template(project.page(1), tmp_path / fname, name)


def test_page_without_areas_cannot_be_saved(ed, project, tmp_path):
    with pytest.raises(ValueError):
        ed.save_template(project.page(2), tmp_path / "gol.blkx", "Gol")


# =============================================================================
# M-032: incarcare (T-M032)
# =============================================================================


def test_T_M032_1_same_size_page(ed, template, project):
    """T-M032.1: pe aceeasi dimensiune reuseste; zonele sunt identice."""
    ed.load_template([project.page(2)], template)
    assert summary(project.page(2)) == summary(project.page(1))
    assert area_of(project.page(2).areas[1].polygon) == area_of(project.page(1).areas[1].polygon)
    assert project.page(2).areas[0].text_function is TextFunction.HEADER


@pytest.mark.parametrize("n", [3, 4])
def test_T_M032_2_other_size_or_resolution_is_refused(ed, template, project, n):
    """T-M032.2: A4 la 600 dpi si Letter la 300 dpi ridica TemplateSizeMismatchError."""
    with pytest.raises(TemplateSizeMismatchError) as info:
        ed.load_template([project.page(n)], template)
    assert info.value.params["page"] == n
    assert project.page(n).areas == []


def test_T_M032_3_scale_true_scales_the_areas(ed, template, project):
    """T-M032.3: cu scale=True reuseste, iar zonele sunt scalate."""
    ed.load_template([project.page(3)], template, scale=True)  # de doua ori mai mare
    src, dst = project.page(1).areas, project.page(3).areas
    assert [a.bbox for a in dst] == [Rect(b.x * 2, b.y * 2, b.w * 2, b.h * 2)
                                     for b in (a.bbox for a in src)]
    ed.load_template([project.page(4)], template, scale=True)  # Letter: alte proportii
    for a in project.page(4).areas:
        assert a.bbox.right <= 638 and a.bbox.bottom <= 825


def test_mismatch_on_one_page_changes_no_page(ed, template, project):
    ed.create(project.page(2), rect(10, 10, 50, 50), T.PICTURE)
    with pytest.raises(TemplateSizeMismatchError):
        ed.load_template([project.page(2), project.page(3)], template)
    assert [a.area_type for a in project.page(2).areas] == [T.PICTURE]


def test_template_replaces_existing_areas_and_can_be_undone(ed, template, project):
    ed.create(project.page(2), rect(10, 10, 50, 50), T.PICTURE)
    ed.load_template([project.page(2)], template)
    assert len(project.page(2).areas) == 3
    assert project.undo_description() == "undo.load_area_template"
    project.undo()
    assert [a.area_type for a in project.page(2).areas] == [T.PICTURE]


def test_load_from_the_library(ed, template, project):
    ed.load_library_template([project.page(2)], "Factura")
    assert summary(project.page(2)) == summary(project.page(1))
    with pytest.raises(ValueError):
        ed.load_library_template([project.page(2)], "Nu exista")


def test_abbyy_and_broken_files(ed, project, tmp_path):
    blk = tmp_path / "vechi.blk"
    blk.write_bytes(b"\x00\x01ABBYY")
    with pytest.raises(UnsupportedFormatError):
        ed.load_template([project.page(1)], blk)
    binary = tmp_path / "abbyy.blkx"
    binary.write_bytes(b"\x00\xffbinary")
    with pytest.raises(UnsupportedFormatError):
        ed.load_template([project.page(1)], binary)
    other = tmp_path / "alt.blkx"
    other.write_text(json.dumps({"format": "altceva"}))
    with pytest.raises(UnsupportedFormatError):
        ed.load_template([project.page(1)], other)
    broken = tmp_path / "rupt.blkx"
    broken.write_text(json.dumps({"format": TEMPLATE_FORMAT, "source": {"width": 1}}))
    with pytest.raises(FileCorruptError):
        ed.load_template([project.page(1)], broken)


def test_template_survives_save_and_reopen(ctx, ed, template, project, tmp_path):
    ed.load_template([project.page(2)], template)
    project.save(tmp_path / "P")
    again = OcrProject.open(tmp_path / "P", context=ctx)
    assert summary(again.page(2)) == summary(project.page(1))
    again.close()
