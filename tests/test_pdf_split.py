"""Impartirea documentului (faza 8, pasul 8.2): E-024…E-031, E-110, E-111."""

from __future__ import annotations

import hashlib
import io
import os
import sys

import pikepdf
import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core.errors import NoWritePermissionError
from app.core.pdf.document import PdfDocument
from app.core.pdf.organize import ATTACHMENTS_FOLDER, PageOrganizer, SplitNaming


def bookmarked_pdf(path, pages=60, every=5, attachments=3):
    """`pages` pagini, un semn de carte de nivel 1 la fiecare `every` pagini (cu
    un copil), si `attachments` atasamente."""
    text_pdf(path, [[f"Pagina {n}"] for n in range(1, pages + 1)])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root[:] = []
            for i, start in enumerate(range(0, pages, every), start=1):
                item = pikepdf.OutlineItem(f"Capitol {i}", start)
                item.children.append(pikepdf.OutlineItem(f"Sectiune {i}.1", start))
                outline.root.append(item)
        for i in range(1, attachments + 1):
            pdf.attachments[f"anexa{i}.txt"] = pikepdf.AttachedFileSpec(
                pdf, f"continutul anexei {i}".encode(), filename=f"anexa{i}.txt")
        pdf.save(path)
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


# --- E-031 (prioritate 1) ----------------------------------------------------------------


def test_T_E031_split_by_bookmarks_drops_bookmarks_and_extracts_attachments(tmp_path):
    source = bookmarked_pdf(tmp_path / "dosar.pdf")
    out = tmp_path / "rezultat"
    with PdfDocument.open(source) as doc:
        originals = {name: sha(spec.get_file().read_bytes())
                     for name, spec in doc._pike().attachments.items()}
        files = PageOrganizer(doc).split(by="bookmarks", value=None, output_folder=out)
    assert len(files) == 12
    for path in files:
        with pikepdf.open(path) as part:
            assert len(part.pages) == 5
            assert "/Outlines" not in part.Root  # niciun semn de carte
            assert len(part.attachments) == 0
    extracted = {p.name: sha(p.read_bytes()) for p in (out / ATTACHMENTS_FOLDER).iterdir()}
    assert extracted == originals


# --- E-024…E-027, E-110 ------------------------------------------------------------------


def test_T_E026_split_by_page_count(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [[f"Pagina {n}"] for n in range(1, 6)])
    with PdfDocument.open(source) as doc:
        organizer = PageOrganizer(doc)
        assert organizer.plan_split("pages", 2).groups == [[1, 2], [3, 4], [5]]
        assert organizer.plan_split("pages", 10).file_count == 1  # E-110: contorul
        with pytest.raises(ValueError):
            organizer.plan_split("pages", 0)
        steps = []
        files = organizer.split(by="pages", value=2, output_folder=tmp_path / "out",
                                progress=steps.append)
    assert [f.name for f in files] == ["01_doc.pdf", "02_doc.pdf", "03_doc.pdf"]
    with PdfDocument.open(files[1]) as part:
        assert [part.extract_text(n).strip() for n in (1, 2)] == ["Pagina 3", "Pagina 4"]
    assert steps[-1].current == steps[-1].total == 3


def noise_page_pdf(path):
    """Trei pagini de text; a doua are si o imagine mare, greu de comprimat."""
    text_pdf(path, [["Pagina 1"], ["Pagina 2"], ["Pagina 3"]])
    image = Image.frombytes("RGB", (600, 600), os.urandom(600 * 600 * 3))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=95)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[1]
        page.obj.Resources.XObject = pikepdf.Dictionary(Im0=pikepdf.Stream(
            pdf, buf.getvalue(), Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
            Width=600, Height=600, ColorSpace=pikepdf.Name.DeviceRGB, BitsPerComponent=8,
            Filter=pikepdf.Name.DCTDecode))
        page.obj.Contents = pdf.make_stream(b"q 400 0 0 400 100 300 cm /Im0 Do Q")
        pdf.save(path)
    return path


def test_T_E025_split_by_size_warns_before_about_files_over_the_limit(tmp_path):
    source = noise_page_pdf(tmp_path / "imagini.pdf")
    size = source.stat().st_size
    with PdfDocument.open(source) as doc:
        organizer = PageOrganizer(doc)
        with pytest.raises(ValueError):  # trebuie sa fie mai mica decat originalul
            organizer.plan_split("size", size)
        plan = organizer.plan_split("size", 20_000)
        assert plan.groups == [[1], [2], [3]]
        assert plan.oversize == [1]  # pagina cu imaginea depaseste, spus dinainte
        files = organizer.split(by="size", value=20_000, output_folder=tmp_path / "out")
    assert len(files) == 3 and files[1].stat().st_size > 20_000
    assert files[0].stat().st_size <= 20_000


def test_T_E027_bookmarks_option_needs_level_one_bookmarks(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [["A"], ["B"]])
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        del pdf.Root["/Outlines"]
        pdf.save(source)
    with PdfDocument.open(source) as doc, pytest.raises(ValueError):
        PageOrganizer(doc).plan_split("bookmarks")


def test_pages_before_the_first_bookmark_go_into_the_first_file(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [[f"P{n}"] for n in range(1, 6)])
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root[:] = [pikepdf.OutlineItem("Doi", 1), pikepdf.OutlineItem("Patru", 3)]
        pdf.save(source)
    with PdfDocument.open(source) as doc:
        plan = PageOrganizer(doc).plan_split("bookmarks")
    assert plan.groups == [[1, 2, 3], [4, 5]] and plan.titles == ["Doi", "Patru"]


# --- E-028, E-029, E-111 -----------------------------------------------------------------


def test_T_E028_numbering_before_or_after_with_digits(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [[f"Pagina {n}"] for n in range(1, 4)])
    with PdfDocument.open(source) as doc:
        plan = PageOrganizer(doc).plan_split("pages", 1)
    assert SplitNaming().file_names(plan, "doc") == ["01_doc.pdf", "02_doc.pdf", "03_doc.pdf"]
    assert SplitNaming(name="Dosar", numbering="after", digits=3).file_names(plan, "doc") == \
        ["Dosar_001.pdf", "Dosar_002.pdf", "Dosar_003.pdf"]
    with pytest.raises(ValueError):
        SplitNaming(digits=0).file_names(plan, "doc")


def test_T_E029_names_from_bookmarks(tmp_path):
    source = bookmarked_pdf(tmp_path / "dosar.pdf", pages=4, every=2, attachments=0)
    with PdfDocument.open(source) as doc:
        plan = PageOrganizer(doc).plan_split("bookmarks")
    assert SplitNaming().file_names(plan, "dosar") == ["01_Capitol 1.pdf", "02_Capitol 2.pdf"]
    assert SplitNaming(add_numeration=False).file_names(plan, "dosar") == \
        ["Capitol 1.pdf", "Capitol 2.pdf"]
    assert SplitNaming(use_bookmark_names=False, name="Anexa").file_names(plan, "dosar") == \
        ["01_Anexa.pdf", "02_Anexa.pdf"]


def test_bookmark_names_are_safe_and_existing_files_are_not_overwritten(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [["A"], ["B"]])
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root[:] = [pikepdf.OutlineItem("Cap: 1/2", 0),
                               pikepdf.OutlineItem("Cap: 1/2", 1)]
        pdf.save(source)
    out = tmp_path / "out"
    out.mkdir()
    (out / "Cap_ 1_2.pdf").write_bytes(b"vechi")
    with PdfDocument.open(source) as doc:
        files = PageOrganizer(doc).split(by="bookmarks", value=None, output_folder=out,
                                         naming=SplitNaming(add_numeration=False))
    assert len({f.name for f in files}) == 2
    assert all(f.name.startswith("Cap_ 1_2") for f in files)
    assert (out / "Cap_ 1_2.pdf").read_bytes() == b"vechi"


# --- E-030 -------------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="drepturile POSIX pe folder")
def test_T_E030_output_folder_must_be_writable(tmp_path):
    source = text_pdf(tmp_path / "doc.pdf", [["A"], ["B"]])
    locked = tmp_path / "blocat"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with PdfDocument.open(source) as doc, pytest.raises(NoWritePermissionError):
            PageOrganizer(doc).split(by="pages", value=1, output_folder=locked)
    finally:
        locked.chmod(0o700)
