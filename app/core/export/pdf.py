"""Exportul PDF (faza 6, pasul 6.2): Q-011, Q-012, Q-033, Q-104, I-030, I-031.

Fiecare pagina: imaginea ei (I-030) si, pentru PDF-ul cautabil (Q-011, I-031),
textul recunoscut ca strat invizibil (mod de afisare 3) la pozitia fiecarui
cuvant, cu textul editat (O-020). Textul redactat nu intra in strat si se
acopera cu un dreptunghi negru (O-072). PDF-ul doar-imagine (Q-012, Q-033) e
acelasi fara strat.

[DECIZIE AUTONOMA] (faza_6_pasi.md, decizia 4) Stratul de text foloseste un
font Type0 (Identity-H) cu un TrueType fara glife generat cu fontTools si
`ToUnicode`, ca textul sa se caute si sa se copieze cu diacriticele corecte.

`pdf.searchable_mode` (X-088): `text_under` si `text_over` scriu acelasi strat
invizibil (sub, respectiv peste imagine). **INCOMPLET, marcat:**
`text_and_pictures` (I-032, text vizibil fara imaginea paginii) vine in 6.3.
"""

from __future__ import annotations

import io
import re
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pikepdf
from PIL import Image, ImageOps

from app.core.export.base import BaseExporter, ExportOptions, check_cancel, report
from app.core.model import (
    CancelToken,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    PageData,
    ProgressCallback,
)

JPEG_QUALITY = {ImageQuality.BEST: 95, ImageQuality.BALANCED: 85, ImageQuality.COMPACT: 60,
                ImageQuality.CUSTOM: 85}
"""X-080: calitatea imaginilor (A-025)."""
WARNING_MRC_PRECISESCAN = "warning.mrc_precisescan"
"""Q-104: MRC impreuna cu PreciseScan pot face textul neclar."""
_HEADING = re.compile(r"^Heading (\d+)$")


def export_warnings(format_options: dict[str, Any]) -> list[str]:
    """Q-104: cheile avertismentelor pentru optiunile PDF alese."""
    if format_options.get("use_mrc") and format_options.get("smooth_characters"):
        return [WARNING_MRC_PRECISESCAN]
    return []


# --- fontul fara glife ----------------------------------------------------------------


def glyphless_font(chars: Sequence[str]) -> bytes:
    """Un TrueType fara contururi, cu cate un glif (latime 1000) pentru fiecare
    caracter, in ordinea data: glif i+1 = chars[i]."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = [".notdef", *(f"g{i + 1}" for i in range(len(chars)))]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(ch): f"g{i + 1}" for i, ch in enumerate(chars)})
    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({name: empty for name in names})
    fb.setupHorizontalMetrics({name: (1000, 0) for name in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "DocuLensGlyphless", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    out = io.BytesIO()
    fb.save(out)
    return out.getvalue()


def _to_unicode(chars: Sequence[str]) -> bytes:
    entries = [f"<{i + 1:04X}> <{ch.encode('utf-16-be').hex().upper()}>"
               for i, ch in enumerate(chars)]
    body = []
    for start in range(0, len(entries), 100):
        chunk = entries[start:start + 100]
        body.append(f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar")
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            + "\n".join(body) + "\nendcmap\nCMapName currentdict /CMap defineresource pop\n"
            "end\nend\n").encode("ascii")


def _font_object(pdf: pikepdf.Pdf, chars: Sequence[str]) -> pikepdf.Object:
    font_file = pdf.make_stream(glyphless_font(chars))
    descriptor = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor, FontName=pikepdf.Name("/DocuLensGlyphless"),
        Flags=4, FontBBox=[0, -200, 1000, 800], ItalicAngle=0, Ascent=800, Descent=-200,
        CapHeight=700, StemV=80, FontFile2=font_file))
    cid_font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType2,
        BaseFont=pikepdf.Name("/DocuLensGlyphless"),
        CIDSystemInfo=pikepdf.Dictionary(Registry=pikepdf.String("Adobe"),
                                         Ordering=pikepdf.String("Identity"), Supplement=0),
        FontDescriptor=descriptor, DW=1000, CIDToGIDMap=pikepdf.Name.Identity))
    return pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        BaseFont=pikepdf.Name("/DocuLensGlyphless"), Encoding=pikepdf.Name("/Identity-H"),
        DescendantFonts=[cid_font], ToUnicode=pdf.make_stream(_to_unicode(chars))))


# --- imaginea paginii -----------------------------------------------------------------


def _image_object(pdf: pikepdf.Pdf, page: PageData, options: ExportOptions) -> pikepdf.Object:
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        img.load()
    if options.image_dpi and options.image_dpi < min(page.dpi_x, page.dpi_y):
        scale = options.image_dpi / min(page.dpi_x, page.dpi_y)
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    if img.mode == "1":  # alb-negru: fara pierderi, 1 bit
        return pdf.make_stream(zlib.compress(img.tobytes()), Type=pikepdf.Name.XObject,
                               Subtype=pikepdf.Name.Image, Width=img.width, Height=img.height,
                               BitsPerComponent=1, ColorSpace=pikepdf.Name.DeviceGray,
                               Filter=pikepdf.Name.FlateDecode)
    gray = img.mode in ("L", "LA", "I", "I;16", "F")
    img = img.convert("L" if gray else "RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY[ImageQuality(options.image_quality)],
             optimize=True)
    return pdf.make_stream(out.getvalue(), Type=pikepdf.Name.XObject,
                           Subtype=pikepdf.Name.Image, Width=img.width, Height=img.height,
                           BitsPerComponent=8,
                           ColorSpace=pikepdf.Name.DeviceGray if gray else pikepdf.Name.DeviceRGB,
                           Filter=pikepdf.Name.DCTDecode)


# --- pagina -----------------------------------------------------------------------------


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def page_words(page: PageData) -> list[Any]:
    from app.core.model import _area_blocks

    return [w for area in page._ordered_areas() for b in _area_blocks(area)
            for ln in b.lines for w in ln.words]


def _content(page: PageData, width_pt: float, height_pt: float, gid: dict[str, int],
             searchable: bool, text_over: bool) -> bytes:
    sx, sy = 72.0 / page.dpi_x, 72.0 / page.dpi_y
    image = f"q {_fmt(width_pt)} 0 0 {_fmt(height_pt)} 0 0 cm /Im0 Do Q\n"
    text, boxes = [], []
    for word in page_words(page):
        b = word.bbox
        x, w = b.x * sx, b.w * sx
        y, h = height_pt - (b.y + b.h) * sy, b.h * sy
        if word.is_redacted:  # O-072: dreptunghi negru, fara text
            boxes.append(f"{_fmt(x)} {_fmt(y)} {_fmt(w)} {_fmt(h)} re f")
            continue
        if not searchable or not word.text or w <= 0 or h <= 0:
            continue
        scale = 100.0 * w / (len(word.text) * h)
        codes = "".join(f"{gid[c]:04X}" for c in word.text)
        text.append(f"/F1 {_fmt(h)} Tf {_fmt(scale)} Tz 1 0 0 1 {_fmt(x)} "
                    f"{_fmt(y + 0.2 * h)} Tm <{codes}> Tj")
    layer = ("BT 3 Tr\n" + "\n".join(text) + "\nET\n") if text else ""
    black = ("q 0 g\n" + "\n".join(boxes) + "\nQ\n") if boxes else ""
    body = image + black + layer if text_over else layer + image + black
    return body.encode("ascii")


# --- semnele de carte si legaturile -------------------------------------------------------


def _bookmarks(pdf: pikepdf.Pdf, pages: Sequence[PageData]) -> None:
    """O-041, X-060: blocurile cu stil `Heading N` devin semne de carte."""
    from app.core.model import _area_blocks

    entries = []
    for index, page in enumerate(pages):
        for area in page._ordered_areas():
            for block in _area_blocks(area):
                match = _HEADING.match(block.style_name or "")
                if match and block.lines:
                    title = " ".join(w.text for ln in block.lines for w in ln.words
                                     if not w.is_redacted)
                    entries.append((int(match.group(1)), title, index))
    if not entries:
        return
    with pdf.open_outline() as outline:
        stack: list[tuple[int, pikepdf.OutlineItem]] = []
        for level, title, index in entries:
            item = pikepdf.OutlineItem(title, index)
            while stack and stack[-1][0] >= level:
                stack.pop()
            (stack[-1][1].children if stack else outline.root).append(item)
            stack.append((level, item))


def _links(pdf: pikepdf.Pdf, pdf_page: pikepdf.Page, page: PageData, height_pt: float,
           links: Sequence[Any]) -> None:
    """O-050..O-056: legaturile din text devin adnotari /Link cu /URI."""
    sx, sy = 72.0 / page.dpi_x, 72.0 / page.dpi_y
    annots = []
    for link in links:
        b = link.bbox
        rect = [b.x * sx, height_pt - b.bottom * sy, b.right * sx, height_pt - b.y * sy]
        annots.append(pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=rect, Border=[0, 0, 0],
            A=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String(link.url)))))
    if annots:
        pdf_page.obj.Annots = pdf.make_indirect(pikepdf.Array(annots))


# SPEC_05 Exporter. Q-011, Q-012
class PdfExporter(BaseExporter):
    format = ExportFormat.PDF

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EXACT)

    def build(self, pages: Sequence[PageData], options: ExportOptions, *,
              progress: ProgressCallback | None = None,
              cancel: CancelToken | None = None) -> pikepdf.Pdf:
        """Documentul PDF, nesalvat (PDF/A si PDF/UA il completeaza, 6.3)."""
        fmt = options.format_options
        text_over = fmt.get("searchable_mode") == "text_over"
        pdf = pikepdf.new()
        chars = sorted({c for p in pages for w in page_words(p) if not w.is_redacted
                        for c in w.text})
        gid = {c: i + 1 for i, c in enumerate(chars)}
        font = _font_object(pdf, chars) if options.searchable and chars else None
        links_by_page = fmt.get("links") or {}
        for done, page in enumerate(pages):
            check_cancel(cancel, done, len(pages))
            width_pt = page.width_px * 72.0 / page.dpi_x
            height_pt = page.height_px * 72.0 / page.dpi_y
            resources = pikepdf.Dictionary(
                XObject=pikepdf.Dictionary(Im0=_image_object(pdf, page, options)))
            if font is not None:
                resources.Font = pikepdf.Dictionary(F1=font)
            content = _content(page, width_pt, height_pt, gid, font is not None, text_over)
            pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
                Type=pikepdf.Name.Page, MediaBox=[0, 0, width_pt, height_pt],
                Resources=resources, Contents=pdf.make_stream(content))))
            _links(pdf, pdf.pages[-1], page, height_pt, links_by_page.get(page.page_number, ()))
            report(progress, done + 1, len(pages), "stage.exporting")
        if options.create_bookmarks_from_headings or fmt.get("bookmarks_from_headings"):
            _bookmarks(pdf, pages)
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["xmp:CreatorTool"] = "DocuLens"
            if "title" in options.metadata:
                meta["dc:title"] = options.metadata["title"]
            if "author" in options.metadata:
                meta["dc:creator"] = [options.metadata["author"]]
        return pdf

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        pdf = self.build(pages, options, progress=progress, cancel=cancel)
        target = Path(target)
        pdf.save(target)
        return [target]
