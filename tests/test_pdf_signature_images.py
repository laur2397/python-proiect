"""Semnaturile text si imagine (faza 10, pasul 10.3): G-050…G-055."""

from __future__ import annotations

import io
from dataclasses import replace

import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core.context import AppContext
from app.core.model import Rect
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.handsign import (
    SignatureImageLibrary,
    place_signature,
    prepare_image,
    rotate_placed,
)


@pytest.fixture
def library(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield SignatureImageLibrary(ctx.app_db)
    ctx.close()


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(text_pdf(tmp_path / "d.pdf", [["Pagina 1"], ["Pagina 2"]])) as d:
        yield d


def scan_of_signature():
    image = Image.new("RGB", (300, 120), "white")
    image.paste((20, 20, 120), (40, 50, 260, 70))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def stamps(doc, page):
    return [a for a in doc.annotations(page) if a.annot_type.value == "stamp"]


def test_T_G050_text_signature(library):
    signature = library.create_text("Ana", "Ana Popescu")
    assert signature.kind == "text" and signature.text == "Ana Popescu"
    image = Image.open(io.BytesIO(signature.image))
    assert image.mode == "RGBA" and image.width > image.height
    assert image.getpixel((1, 1))[3] == 0  # fond transparent
    with pytest.raises(ValueError):
        library.create_text("Ana", "alta")  # nume unic
    with pytest.raises(ValueError):
        library.create_text("Gol", "  ")


def test_T_G051_image_signature_with_transparent_background_and_resize(library):
    data = scan_of_signature()
    signature = library.create_image("Scanata", data, transparent=True, scale=0.5)
    image = Image.open(io.BytesIO(signature.image))
    assert image.size == (150, 60) and signature.transparent
    assert image.getpixel((2, 2))[3] == 0 and image.getpixel((75, 30))[3] == 255
    opaque = Image.open(io.BytesIO(prepare_image(data, transparent=False)))
    assert opaque.getpixel((2, 2))[3] == 255


def test_T_G052_G053_place_move_resize_rotate(library, doc):
    signature = library.create_text("Ana", "Ana Popescu")
    first = place_signature(doc, 1, signature, (300, 600))
    place_signature(doc, 1, signature, (100, 100))  # G-053: oricate semnaturi
    place_signature(doc, 2, signature, (100, 100))
    assert len(stamps(doc, 1)) == 2 and first.bbox.x == pytest.approx(300)
    doc.update_annotation(replace(first, bbox=Rect(200, 500, first.bbox.w * 2,
                                                   first.bbox.h * 2)))
    moved = next(a for a in doc.annotations(1) if a.id == first.id)
    assert moved.bbox.x == pytest.approx(200, abs=0.5)
    assert moved.bbox.w == pytest.approx(first.bbox.w * 2, abs=0.5)
    rotate_placed(doc, first.id, 90)
    rotated = next(a for a in doc.annotations(1) if a.id == first.id)
    assert rotated.bbox.w == pytest.approx(moved.bbox.h, abs=0.5)
    with pytest.raises(ValueError):
        rotate_placed(doc, first.id, 45)


def test_T_G054_G055_edit_save_and_delete(library, doc):
    library.create_text("Ana", "Ana Popescu")
    library.create_image("Scanata", scan_of_signature())
    edited = library.update("Ana", new_name="Ana P.", text="A. Popescu")
    assert edited.text == "A. Popescu"
    assert [s.name for s in library.signatures()] == ["Ana P.", "Scanata"]
    library.update("Scanata", transparent=True)
    assert library.get("Scanata").transparent
    library.delete("Ana P.")
    assert [s.name for s in library.signatures()] == ["Scanata"]
    placed = place_signature(doc, 1, library.get("Scanata"), (100, 100))
    doc.delete_annotations([placed.id])  # G-055: si pe pagina
    assert stamps(doc, 1) == []
    with pytest.raises(KeyError):
        library.delete("lipsa")
