"""Linkurile adaugate de utilizator (faza 9, pasul 9.1): F-026…F-030."""

from __future__ import annotations

import pytest
from test_pdf_search import text_pdf

from app.core.model import Rect
from app.core.pdf.document import PdfDocument
from app.core.pdf.navigation import link_target, validate_link_target

AREA = Rect(72, 60, 200, 30)


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 4)])
    with PdfDocument.open(path) as d:
        yield d


def test_T_F026_link_to_a_page_and_to_a_precise_destination(doc):
    doc.add_link(1, AREA, {"kind": "page", "page": 3})
    doc.add_link(2, AREA, {"kind": "page", "page": 1, "y": 300})
    [first] = doc.links(1)
    assert first.target_page == 3 and first.rects[0] == pytest.approx(AREA)
    assert doc.links(2)[0].target_page == 1


def test_T_F027_prefixes_are_required(doc):
    for target in ({"kind": "email", "uri": "ana@exemplu.ro"},
                   {"kind": "file", "uri": "C:/dosar/anexa.pdf"},
                   {"kind": "url", "uri": "www.exemplu.ro"},
                   {"kind": "email", "uri": "mailto:"}):
        with pytest.raises(ValueError):
            validate_link_target(target)
    doc.add_link(1, AREA, {"kind": "email", "uri": "mailto:ana@exemplu.ro"})
    doc.add_link(1, Rect(72, 120, 100, 20), {"kind": "file", "uri": "file:///tmp/anexa.pdf"})
    doc.add_link(1, Rect(72, 160, 100, 20), {"kind": "url", "uri": "https://exemplu.ro"})
    assert [link.uri for link in doc.links(1)] == [
        "mailto:ana@exemplu.ro", "file:///tmp/anexa.pdf", "https://exemplu.ro"]


def test_T_F028_F029_edit_and_copy_a_link(doc):
    doc.add_link(1, AREA, {"kind": "url", "uri": "https://vechi.ro"})
    inside = Rect(AREA.x + 10, AREA.y + 10, 1, 1)
    assert link_target(doc, 1, inside) == {"kind": "url", "uri": "https://vechi.ro"}
    doc.update_link(1, inside, {"kind": "page", "page": 2})
    assert link_target(doc, 1, inside) == {"kind": "page", "page": 2, "y": None}
    assert len(doc.links(1)) == 1


def test_T_F030_remove_link(doc):
    doc.add_link(1, AREA, {"kind": "url", "uri": "https://a.ro"})
    doc.add_link(1, Rect(72, 200, 100, 20), {"kind": "url", "uri": "https://b.ro"})
    doc.delete_link(1, AREA)
    assert [link.uri for link in doc.links(1)] == ["https://b.ro"]
    with pytest.raises(KeyError):
        doc.delete_link(1, Rect(400, 700, 5, 5))


def test_links_survive_saving(doc, tmp_path):
    doc.add_link(1, AREA, {"kind": "page", "page": 2})
    target = tmp_path / "salvat.pdf"
    doc.save_as(target)
    with PdfDocument.open(target) as again:
        assert again.links(1)[0].target_page == 2
