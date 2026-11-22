"""`Delete Objects and Data` (faza 10, pasul 10.1): G-022…G-024, G-111.

Fiecare functie scoate o categorie din PDF (vederea pikepdf a documentului) si
intoarce cate obiecte a sters. `to_image_only` (G-024, `Hidden text and
objects`) inlocuieste fiecare pagina cu imaginea ei: textul ascuns, obiectele
ascunse si tot textul dispar, documentul devine PDF imagine.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import pikepdf

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

LINK_LIKE = ("/Link", "/Widget", "/Screen", "/Movie", "/Sound", "/RichMedia", "/3D")
"""Adnotarile care tin de `Links, media, actions, scripts, and form data`."""
IMAGE_ONLY_DPI = 200


def _filter_annots(pdf: pikepdf.Pdf, drop: Any) -> int:
    removed = 0
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if annots is None:
            continue
        kept = [a for a in annots if not drop(a)]
        if len(kept) != len(annots):
            removed += len(annots) - len(kept)
            if kept:
                page.obj.Annots = pikepdf.Array(kept)
            else:
                del page.obj["/Annots"]
    return removed


def remove_comments(pdf: pikepdf.Pdf) -> int:
    """`Comments and markup`: toate adnotarile, in afara linkurilor si a
    campurilor (care au categoria lor) si a atasamentelor de fisier."""
    return _filter_annots(pdf, lambda a: a.get("/Subtype") not in (*LINK_LIKE,
                                                                   "/FileAttachment"))


def remove_links_actions_forms(pdf: pikepdf.Pdf) -> int:
    """`Links, media, actions, scripts, and form data`."""
    removed = _filter_annots(pdf, lambda a: a.get("/Subtype") in LINK_LIKE)
    root = pdf.Root
    for key in ("/AcroForm", "/OpenAction", "/AA"):
        if key in root:
            del root[key]
            removed += 1
    names = root.get("/Names")
    if names is not None and "/JavaScript" in names:
        del names["/JavaScript"]
        removed += 1
    for page in pdf.pages:
        if "/AA" in page.obj:
            del page.obj["/AA"]
            removed += 1
    return removed


def remove_bookmarks(pdf: pikepdf.Pdf) -> int:
    if "/Outlines" not in pdf.Root:
        return 0
    with pdf.open_outline() as outline:
        count = len(outline.root)
    del pdf.Root["/Outlines"]
    return count


def remove_attachments(pdf: pikepdf.Pdf) -> int:
    """Atasamentele documentului si adnotarile `/FileAttachment`."""
    count = len(pdf.attachments)
    names = pdf.Root.get("/Names")
    if names is not None and "/EmbeddedFiles" in names:
        del names["/EmbeddedFiles"]
    return count + _filter_annots(pdf, lambda a: a.get("/Subtype") == "/FileAttachment")


def remove_metadata(pdf: pikepdf.Pdf) -> int:
    """Dictionarul Info si metadatele XMP."""
    count = len(pdf.docinfo)
    for key in list(pdf.docinfo.keys()):
        del pdf.docinfo[key]
    if "/Metadata" in pdf.Root:
        del pdf.Root["/Metadata"]
        count += 1
    return count


def to_image_only(document: PdfDocument) -> int:
    """G-024: fiecare pagina devine imaginea ei, asa cum se vede (cu rotatia
    aplicata), fara strat de text."""
    from PIL import Image

    from app.core.pdf.redact import _image_stream

    pdf = document._pike()
    zoom = IMAGE_ONLY_DPI / 96
    for number, page in enumerate(pdf.pages, start=1):
        image = Image.open(io.BytesIO(document.render_page(number, zoom,
                                                           annotations=False)))
        width, height = image.width * 72 / IMAGE_ONLY_DPI, image.height * 72 / IMAGE_ONLY_DPI
        stream = _image_stream(pdf, image.convert("RGB"))
        for key in ("/Rotate", "/CropBox"):  # adnotarile au bifa lor (G-111)
            if key in page.obj:
                del page.obj[key]
        page.obj.MediaBox = pikepdf.Array([0, 0, width, height])
        page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=stream))
        page.obj.Contents = pdf.make_stream(
            f"q {width:.3f} 0 0 {height:.3f} 0 0 cm /Im0 Do Q".encode())
    return len(pdf.pages)
