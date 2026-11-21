"""Exportul EPUB (faza 6, pasul 6.6): Q-020, X-126.

Scris de noi (faza_6_pasi.md, decizia 2: `ebooklib` e AGPL). EPUB 3 sau 2
(`EPUB Settings`): ZIP cu `mimetype` necomprimat primul, `container.xml`,
`content.opf`, cuprinsul (`nav.xhtml` pentru EPUB 3, `toc.ncx` pentru ambele),
capitolele XHTML impartite la titlurile de nivel 1, imaginile si, la cerere,
coperta din prima pagina (`Use the first page as the e-book cover`).
`Retain fonts and font sizes (EPUB only)`: fonturile si marimile raman in CSS.

INCOMPLET, marcat: `Embed fonts` (X-126) cere fisierele fonturilor; fonturile
libere intra in pachet la faza 16.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import Sequence
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

from app.core.export.base import BaseExporter, ExportOptions, report
from app.core.export.docmodel import build_document
from app.core.export.html import Renderer, render_sections
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_XHTML = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
          '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
          ' lang="ro" xml:lang="ro"><head><title>{title}</title>'
          '<link rel="stylesheet" type="text/css" href="style.css"/></head><body>{body}'
          "</body></html>")
_CSS = ("body{font-family:serif}table{border-collapse:collapse}td{border:1px solid #888;"
        "padding:2px 4px}p.footnote{font-size:smaller}")


def _cover(page: PageData) -> bytes:
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
        img.thumbnail((1600, 2400))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=85)
    return out.getvalue()


def _opf(version: str, identifier: str, title: str, chapters: Sequence[tuple[str, object]],
         images: Sequence[tuple[str, bytes]], cover: bool) -> str:
    epub3 = version.startswith("3")
    manifest = ['<item id="css" href="style.css" media-type="text/css"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
    if epub3:
        manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"'
                        ' properties="nav"/>')
    manifest += [f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>'
                 for i, (name, _) in enumerate(chapters, start=1)]
    manifest += [f'<item id="i{i}" href="{name}" media-type="image/png"/>'
                 for i, (name, _) in enumerate(images, start=1)]
    if cover:
        manifest.append('<item id="cover" href="cover.jpg" media-type="image/jpeg"'
                        + (' properties="cover-image"' if epub3 else "") + "/>")
    spine = "".join(f'<itemref idref="c{i}"/>' for i in range(1, len(chapters) + 1))
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = (f'<dc:identifier id="bookid">{identifier}</dc:identifier>'
            f"<dc:title>{escape(title)}</dc:title><dc:language>ro</dc:language>"
            + (f'<meta property="dcterms:modified">{modified}</meta>' if epub3 else "")
            + ('<meta name="cover" content="cover"/>' if cover else ""))
    return ('<?xml version="1.0" encoding="utf-8"?>'
            f'<package xmlns="http://www.idpf.org/2007/opf" version="{version}" '
            'unique-identifier="bookid"><metadata '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/">{meta}</metadata>'
            f"<manifest>{''.join(manifest)}</manifest>"
            f'<spine toc="ncx">{spine}</spine></package>')


# SPEC_05 Exporter. Q-020
class EpubExporter(BaseExporter):
    format = ExportFormat.EPUB

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.FORMATTED)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        fmt = dict(options.format_options)
        version = str(fmt.get("version", "3.0"))
        target = Path(target)
        title = options.metadata.get("title") or target.stem
        images: list[tuple[str, bytes]] = []

        def image(data: bytes) -> str:
            name = f"images/img{len(images) + 1}.png"
            images.append((name, data))
            return name

        values = {f.name: getattr(options, f.name) for f in fields(ExportOptions)}
        values["keep_pictures"] = bool(fmt.get("keep_pictures", options.keep_pictures))
        document = build_document(pages, ExportOptions(**values))
        document.title = title
        renderer = Renderer(image, fonts=bool(fmt.get("retain_fonts", True)), xhtml=True)
        sections = render_sections(document, renderer, "h1")
        chapters = [(f"chapter{i}.xhtml", s) for i, s in enumerate(sections, start=1)]
        cover = _cover(pages[0]) if fmt.get("first_page_cover") else None
        identifier = f"urn:uuid:{uuid.uuid4()}"
        points = "".join(
            f'<navPoint id="n{i}" playOrder="{i}"><navLabel><text>{escape(s.title)}</text>'
            f'</navLabel><content src="{name}"/></navPoint>'
            for i, (name, s) in enumerate(chapters, start=1))
        ncx = ('<?xml version="1.0" encoding="utf-8"?>'
               '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
               f'<meta name="dtb:uid" content="{identifier}"/></head><docTitle><text>'
               f"{escape(title)}</text></docTitle><navMap>{points}</navMap></ncx>")
        nav = _XHTML.format(title=escape(title), body='<nav epub:type="toc"><ol>' + "".join(
            f'<li><a href="{name}">{escape(s.title)}</a></li>' for name, s in chapters)
            + "</ol></nav>")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml",
                       '<?xml version="1.0"?><container version="1.0" '
                       'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="OEBPS/content.opf" '
                       'media-type="application/oebps-package+xml"/></rootfiles></container>')
            z.writestr("OEBPS/content.opf",
                       _opf(version, identifier, title, chapters, images, cover is not None))
            z.writestr("OEBPS/toc.ncx", ncx)
            z.writestr("OEBPS/style.css", _CSS)
            if version.startswith("3"):
                z.writestr("OEBPS/nav.xhtml", nav)
            for name, section in chapters:
                z.writestr(f"OEBPS/{name}", _XHTML.format(title=escape(section.title),
                                                          body="".join(section.parts)))
            for name, data in images:
                z.writestr(f"OEBPS/{name}", data)
            if cover is not None:
                z.writestr("OEBPS/cover.jpg", cover)
        report(progress, len(pages), len(pages), "stage.exporting")
        return [target]
