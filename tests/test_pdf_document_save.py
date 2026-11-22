"""PdfDocument: salvarea, textul, metadatele, salvarea automata (faza 7, pasul 7.1).

I-001…I-004, I-006, I-007, I-024, A-013.
"""

from __future__ import annotations

import io
import os

import pikepdf
import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.errors import FileLockedError, NoWritePermissionError
from app.core.export.base import ExportOptions
from app.core.model import BlockData, LayoutMode, LineData, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument


class WordEngine:
    """Motor OCR fals: fiecare pagina are un singur cuvant."""

    name = "fals"

    def recognize_area(self, page, area, settings, cancel=None):
        result = self.recognize_page(page, settings)
        return RecognitionResult(page.page_number, blocks=result.blocks, avg_confidence=95.0,
                                 area_blocks={area.id: result.blocks})

    def recognize_page(self, page, settings, cancel=None):
        word = WordData(None, "Finantare", 95.0, bbox=Rect(50, 50, 300, 40))
        block = BlockData(None, lines=[LineData(None, words=[word], bbox=Rect(50, 50, 300, 40))],
                          bbox=Rect(50, 50, 300, 40))
        return RecognitionResult(page.page_number, blocks=[block], avg_confidence=95.0,
                                 area_blocks={a.id: [block] for a in page.areas[:1]})


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(out, format="JPEG")
    return out.getvalue()


def make_pdf(path, *, pages=2, version="1.7", text=True, image=False, **save):
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    for n in range(1, pages + 1):
        ops = f"BT /F1 24 Tf 72 700 Td (Pagina {n}) Tj ET".encode() if text else b""
        resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
        if image:
            jpeg = pikepdf.Stream(pdf, _jpeg())
            jpeg.Type, jpeg.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
            jpeg.Width, jpeg.Height, jpeg.BitsPerComponent = 40, 30, 8
            jpeg.ColorSpace, jpeg.Filter = pikepdf.Name.DeviceRGB, pikepdf.Name.DCTDecode
            resources.XObject = pikepdf.Dictionary(Im1=jpeg)
            ops += b" q 40 0 0 30 72 72 cm /Im1 Do Q"
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page, MediaBox=[0, 0, 595, 842],
            Contents=pdf.make_stream(ops), Resources=resources))
        pdf.pages.append(page)
    pdf.docinfo["/Title"] = "Cerere de finantare"
    key = "min_version" if "encryption" in save else "force_version"  # force_version scoate criptarea
    pdf.save(path, **{key: version}, **save)
    return path


def image_pdf(path):
    """Un PDF doar-imagine: o pagina scanata, fara text."""
    img = Image.new("L", (600, 800), 255)
    img.paste(0, (50, 50, 350, 90))
    img.save(path, "PDF", resolution=300)
    return path


# --- I-001, I-007 ---------------------------------------------------------------------


def test_T_I001_1_save_writes_changes_and_keeps_version(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf", version="1.7")
    with PdfDocument.open(path) as doc:
        doc.set_metadata(title="Dosar nou")
        assert doc.is_modified
        doc.save()
        assert not doc.is_modified
        assert doc.page_count == 2
        assert doc.extract_text(1).strip() == "Pagina 1"
    with pikepdf.open(path) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Dosar nou"
        assert pdf.pdf_version == "1.7"


def test_T_I001_2_version_is_never_lowered(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf", version="2.0")
    with PdfDocument.open(path) as doc:
        doc.set_metadata(author="Ana")
        doc.save()
        assert doc.pdf_version == "2.0"
    with pikepdf.open(path) as pdf:
        assert pdf.pdf_version == "2.0"


def test_T_I001_3_save_without_changes_does_not_touch_the_file(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf")
    before = path.read_bytes()
    os.utime(path, (1_000_000, 1_000_000))
    with PdfDocument.open(path) as doc:
        doc.save()
    assert path.read_bytes() == before
    assert path.stat().st_mtime == 1_000_000


def test_T_I001_4_locked_file_gives_error_and_keeps_document(tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "doc.pdf")
    before = path.read_bytes()

    def locked(src, dst):
        raise PermissionError(13, "in use")

    with PdfDocument.open(path) as doc:
        doc.set_metadata(title="Alt titlu")
        monkeypatch.setattr(os, "replace", locked)
        with pytest.raises(FileLockedError) as info:
            doc.save()
        monkeypatch.undo()
        assert info.value.code == "FILE_LOCKED"
        assert doc.is_modified
        assert doc.metadata()["title"] == "Alt titlu"
        assert doc.render_page(1, 0.5)[:8] == b"\x89PNG\r\n\x1a\n"
        doc.save()
    assert path.read_bytes() != before
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".doculens-")]


def test_T_I007_1_untouched_objects_are_copied_byte_for_byte(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf", image=True)
    with pikepdf.open(path) as pdf:
        image_before = pdf.pages[0].Resources.XObject.Im1.read_raw_bytes()
        content_before = pdf.pages[1].Contents.read_raw_bytes()
    with PdfDocument.open(path) as doc:
        doc.set_metadata(subject="Anexa 3")
        doc.save()
    with pikepdf.open(path) as pdf:
        assert pdf.pages[0].Resources.XObject.Im1.read_raw_bytes() == image_before
        assert pdf.pages[1].Contents.read_raw_bytes() == content_before


def test_T_I001_5_encrypted_document_stays_encrypted(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf",
                    encryption=pikepdf.Encryption(user="cheie", owner="cheie", R=6))
    with PdfDocument.open(path, password=lambda _p: "cheie") as doc:
        assert doc.is_encrypted
        doc.set_metadata(title="Protejat")
        doc.save()
        assert doc.metadata()["title"] == "Protejat"
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(path)
    with pikepdf.open(path, password="cheie") as pdf:
        assert str(pdf.docinfo["/Title"]) == "Protejat"


# --- I-002, I-006 ---------------------------------------------------------------------


def test_T_I002_1_save_as_copies_and_switches_to_the_new_file(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf")
    before = path.read_bytes()
    target = tmp_path / "mutat" / "copie.pdf"
    with PdfDocument.open(path) as doc:
        doc.set_metadata(title="Copie")
        doc.save_as(target)
        assert doc.path == target
        assert not doc.is_modified
    assert path.read_bytes() == before
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 2
        assert str(pdf.docinfo["/Title"]) == "Copie"


def test_T_I006_1_save_selected_pages(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf", pages=3)
    target = tmp_path / "pagini.pdf"
    with PdfDocument.open(path) as doc:
        doc.save_as(target, pages=[3, 1])
        assert doc.path == path
        assert doc.page_count == 3
    with PdfDocument.open(target) as part:
        assert part.page_count == 2
        assert part.extract_text(1).strip() == "Pagina 3"
        assert part.extract_text(2).strip() == "Pagina 1"
        assert part.metadata()["title"] == "Cerere de finantare"


def test_T_I006_2_invalid_page_selection(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf")
    with PdfDocument.open(path) as doc:
        with pytest.raises(ValueError):
            doc.save_as(tmp_path / "x.pdf", pages=[])
        with pytest.raises(ValueError):
            doc.save_as(tmp_path / "x.pdf", pages=[5])
    assert not (tmp_path / "x.pdf").exists()


# --- I-003, I-004 ---------------------------------------------------------------------


def test_T_I003_1_save_as_searchable_adds_text_layer(tmp_path, ctx):
    path = image_pdf(tmp_path / "scan.pdf")
    target = tmp_path / "cautabil.pdf"
    with PdfDocument.open(path) as doc:
        assert not doc.has_text_layer(1)
        doc.save_as(target, options=ExportOptions(layout_mode=LayoutMode.EXACT),
                    context=ctx, engine=WordEngine())
        assert doc.path == target
        assert doc.has_text_layer(1)
        assert "Finantare" in doc.extract_text(1)


def test_T_I004_1_save_as_image_only_has_no_text(tmp_path, ctx):
    path = make_pdf(tmp_path / "doc.pdf", pages=1)
    target = tmp_path / "imagine.pdf"
    with PdfDocument.open(path) as doc:
        assert doc.has_text_layer(1)
        doc.save_as(target, options=ExportOptions(layout_mode=LayoutMode.EXACT,
                                                  searchable=False), context=ctx)
        assert doc.page_count == 1
        assert not doc.has_text_layer(1)


# --- documente noi --------------------------------------------------------------------


def test_create_empty_document(tmp_path):
    with PdfDocument.create_empty() as doc:
        assert doc.path is None
        assert doc.page_count == 0
        with pytest.raises(ValueError):
            doc.save()
        doc.save_as(tmp_path / "gol.pdf")
        assert doc.path == tmp_path / "gol.pdf"
    with pikepdf.open(tmp_path / "gol.pdf") as pdf:
        assert len(pdf.pages) == 0


def test_T_A013_from_images_is_unsaved_pdf(tmp_path, ctx):
    files = []
    for n in (1, 2):
        Image.new("L", (600, 800), 255).save(tmp_path / f"p{n}.png", dpi=(300, 300))
        files.append(tmp_path / f"p{n}.png")
    with PdfDocument.from_images(files, options=ExportOptions(
            layout_mode=LayoutMode.EXACT, searchable=False), context=ctx) as doc:
        assert doc.path is None
        assert doc.is_modified
        assert doc.page_count == 2
        assert not doc.has_text_layer(1)
        doc.save_as(tmp_path / "nou.pdf")
        assert not doc.is_modified
    with pytest.raises(ValueError):
        PdfDocument.from_images([], options=ExportOptions())


# --- text, metadate, permisiuni -------------------------------------------------------


def test_extract_text_and_text_layer(tmp_path):
    with PdfDocument.open(make_pdf(tmp_path / "t.pdf")) as doc:
        assert doc.extract_text(2).strip() == "Pagina 2"
        assert doc.has_text_layer(2)
        with pytest.raises(ValueError):
            doc.extract_text(3)
    with PdfDocument.open(make_pdf(tmp_path / "f.pdf", text=False)) as doc:
        assert not doc.has_text_layer(1)


def test_metadata_read_change_and_clear(tmp_path):
    with PdfDocument.open(make_pdf(tmp_path / "m.pdf")) as doc:
        assert doc.metadata()["title"] == "Cerere de finantare"
        doc.set_metadata(author="Ștefan Țurcanu", keywords="")
        assert doc.metadata()["author"] == "Ștefan Țurcanu"
        doc.set_metadata(title="")
        assert "title" not in doc.metadata()
        with pytest.raises(ValueError):
            doc.set_metadata(culoare="rosu")


def test_permissions_and_protected_metadata(tmp_path):
    path = make_pdf(tmp_path / "p.pdf", encryption=pikepdf.Encryption(
        user="", owner="proprietar", R=6,
        allow=pikepdf.Permissions(modify_other=False, extract=False)))
    with PdfDocument.open(path) as doc:
        perms = doc.permissions
        assert perms["modify_other"] is False
        assert perms["extract"] is False
        assert perms["print_highres"] is True
        with pytest.raises(NoWritePermissionError):
            doc.set_metadata(title="Nu")
    with PdfDocument.open(make_pdf(tmp_path / "liber.pdf")) as doc:
        assert all(doc.permissions.values())


def test_is_tagged(tmp_path):
    path = make_pdf(tmp_path / "t.pdf")
    with PdfDocument.open(path) as doc:
        assert not doc.is_tagged
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        assert doc.is_tagged


# --- I-024 ----------------------------------------------------------------------------


def test_T_I024_1_autosave_only_when_needed(tmp_path, ctx):
    path = make_pdf(tmp_path / "doc.pdf")
    with PdfDocument.open(path) as doc:
        assert doc.autosave(ctx) is None  # nimic nesalvat
        doc.set_metadata(title="Nesalvat")
        copy = doc.autosave(ctx)
        assert copy is not None and copy.exists()
        assert copy.parent == ctx.paths.recovery_dir
        assert doc.autosave(ctx) == copy  # nimic nou de la ultima copie
        doc.set_metadata(title="Nesalvat 2")
        second = doc.autosave(ctx)
        assert second != copy and not copy.exists()
        doc.close()
        assert not second.exists()  # inchiderea normala nu lasa nimic


def test_T_I024_2_recovery_after_crash(tmp_path, ctx):
    path = make_pdf(tmp_path / "doc.pdf")
    doc = PdfDocument.open(path)
    doc.set_metadata(title="Nesalvat")
    copy = doc.autosave(ctx)
    with ctx.app_db:  # sesiunea care a scris copia „a cazut”
        ctx.app_db.execute("UPDATE recovery_entry SET session_id = 'cazuta-999999'")
    doc._recovery_path = None
    doc.close_views()

    assert PdfDocument.find_recovery(context=ctx) == [(copy, path)]
    with PdfDocument.recover(copy, context=ctx) as recovered:
        assert recovered.path == path
        assert recovered.is_modified
        assert recovered.metadata()["title"] == "Nesalvat"
        assert PdfDocument.find_recovery(context=ctx) == []
        recovered.save()
    with pikepdf.open(path) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Nesalvat"


def test_T_I024_3_save_forgets_the_safety_copy(tmp_path, ctx):
    path = make_pdf(tmp_path / "doc.pdf")
    with PdfDocument.open(path) as doc:
        doc.set_metadata(title="Salvat")
        copy = doc.autosave(ctx)
        doc.save()
        assert not copy.exists()
        assert PdfDocument.find_recovery(context=ctx) == []
