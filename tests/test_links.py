"""Faza 5, pasul 5.4: legaturile din text (O-050..O-056, F-027)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.model import AutoProcessMode, BlockData, LineData, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.service import RecognitionService
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.text.links import EMAIL, FILE, WEB, LinkEditor, make_url


class ScriptEngine:
    name = "fals"

    def recognize_page(self, page, settings, cancel=None):
        words = [WordData(None, t, 95.0, bbox=Rect(10 + 80 * i, 10, 70, 20),
                          language_code="ron")
                 for i, t in enumerate(("Vezi", "site-ul", "finantator", "aici"))]
        block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(10, 10, 330, 20))],
                          bbox=Rect(10, 10, 330, 20))
        area_id = page.areas[0].id if page.areas else None
        return RecognitionResult(page.page_number, blocks=[block], area_blocks={area_id: [block]})

    def recognize_area(self, page, area, settings, cancel=None):
        return RecognitionResult(page.page_number, area_blocks={area.id: []})


@pytest.fixture
def project(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    ctx.settings.set("lang.mode", "manual")
    ctx.settings.set("lang.manual", ["ron"])
    Image.new("L", (800, 400), 255).save(tmp_path / "p.png", dpi=(300, 300))
    p = OcrProject.create(context=ctx)
    p.add_images([tmp_path / "p.png"], auto_process=AutoProcessMode.NONE)
    RecognitionService(p, engine=ScriptEngine()).recognize_pages()
    yield p
    p.close()
    ctx.close()


def test_T_O054_O056_prefixes(tmp_path):
    """T-O054.1, T-O055.1, T-O056.1 / F-027: protocolul, `file://`, `mailto:`."""
    assert make_url(WEB, "fonduri.ro") == "https://fonduri.ro"
    assert make_url(WEB, "fonduri.ro", "http://") == "http://fonduri.ro"
    assert make_url(WEB, "ftp://arhiva.ro/x") == "ftp://arhiva.ro/x"
    assert make_url(FILE, str(tmp_path / "anexa.pdf")).startswith("file://")
    assert make_url(EMAIL, "ion@firma.ro") == "mailto:ion@firma.ro"
    assert make_url(EMAIL, "mailto:ion@firma.ro") == "mailto:ion@firma.ro"
    for kind, address in ((EMAIL, "fara-arond"), (WEB, ""), ("telefon", "0722")):
        with pytest.raises(ValueError):
            make_url(kind, address)
    with pytest.raises(ValueError):
        make_url(WEB, "fonduri.ro", "gopher://")


def test_T_O050_O053_add_edit_remove(project):
    """T-O050.1..T-O053.1: tooltip, deschiderea, editarea, stergerea."""
    links = LinkEditor(project)
    page = project.page(1)
    words = list(page.iter_words())
    link = links.add(page, words[1:3], WEB, "fonduri.ro")
    assert link.text_to_display == "site-ul finantator" and link.tooltip == "https://fonduri.ro"
    page = project.page(1)
    found = links.link_at(page, list(page.iter_words())[2])
    assert found is not None and found.url == "https://fonduri.ro"  # O-051: Ctrl+clic
    assert links.link_at(page, next(iter(page.iter_words()))) is None
    links.edit(found, kind=EMAIL, address="contact@fonduri.ro", text_to_display="scrieti-ne")
    (edited,) = links.links(project.page(1))
    assert (edited.url, edited.text_to_display, edited.kind) == (
        "mailto:contact@fonduri.ro", "scrieti-ne", EMAIL)
    links.remove(edited)  # O-052: textul ramane
    assert links.links(project.page(1)) == []
    assert "site-ul" in project.page(1).text
    project.undo()
    assert len(links.links(project.page(1))) == 1


def test_link_needs_words(project):
    with pytest.raises(ValueError):
        LinkEditor(project).add(project.page(1), [], WEB, "fonduri.ro")
