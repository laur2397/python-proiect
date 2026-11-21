"""Exportul ODT (faza 6, pasul 6.4): Q-014, X-100..X-109.

Scris de noi (OpenDocument 1.2: ZIP cu `mimetype` necomprimat primul,
`content.xml`, `styles.xml`, `meta.xml`, manifestul si imaginile), din
documentul intermediar (`docmodel.py`). Titlurile sunt `text:h` cu nivelul lor,
tabelele au celulele unite (`number-columns-spanned`) si acoperite
(`covered-table-cell`), imaginile sunt `draw:frame`.

[DECIZIE AUTONOMA] Pagina are marimea primei pagini a documentului; paginile
urmatoare incep cu o ruptura de pagina (X-105) fara alta marime.
"""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from app.core.export.base import BaseExporter, ExportOptions, report
from app.core.export.docmodel import Document, Para, Picture, Run, Table, build_document
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_NS = (' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
       ' xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
       ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
       ' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
       ' xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"'
       ' xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"'
       ' xmlns:xlink="http://www.w3.org/1999/xlink"'
       ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
       ' xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"'
       ' xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"'
       ' office:version="1.2"')
_ALIGN = {"left": "start", "center": "center", "right": "end", "justify": "justify"}
MIMETYPE = "application/vnd.oasis.opendocument.text"


def _pt(v: float) -> str:
    return f"{v:.2f}pt"


class _Styles:
    """Stilurile automate (paragrafe P1.., fragmente T1..), fara dubluri."""

    def __init__(self) -> None:
        self.paragraph: dict[str, str] = {}
        self.text: dict[str, str] = {}

    def para(self, props: str) -> str:
        if props not in self.paragraph:
            self.paragraph[props] = f"P{len(self.paragraph) + 1}"
        return self.paragraph[props]

    def run(self, props: str) -> str:
        if props not in self.text:
            self.text[props] = f"T{len(self.text) + 1}"
        return self.text[props]

    def xml(self) -> str:
        out = [f'<style:style style:name="{name}" style:family="paragraph">'
               f"<style:paragraph-properties {props}/></style:style>"
               for props, name in self.paragraph.items()]
        out += [f'<style:style style:name="{name}" style:family="text">'
                f"<style:text-properties {props}/></style:style>"
                for props, name in self.text.items()]
        return "".join(out)


def _run(run: Run, styles: _Styles) -> str:
    props = []
    if run.bold:
        props.append('fo:font-weight="bold"')
    if run.italic:
        props.append('fo:font-style="italic"')
    if run.underline:
        props.append('style:text-underline-style="solid"')
    if run.superscript:
        props.append('style:text-position="super 58%"')
    if run.subscript:
        props.append('style:text-position="sub 58%"')
    if run.font:
        props.append(f"fo:font-family={quoteattr(run.font)}")
    if run.size:
        props.append(f'fo:font-size="{_pt(run.size)}"')
    if run.color:
        props.append(f'fo:color="{run.color}"')
    if run.highlight:  # X-109
        props.append(f'fo:background-color="{run.highlight}"')
    text = escape(run.text).replace("\n", "<text:line-break/>").replace("\t", "<text:tab/>")
    if not props:
        return text
    return f'<text:span text:style-name="{styles.run(" ".join(props))}">{text}</text:span>'


def _para_style(para: Para, styles: _Styles, page_break: bool) -> str:
    props = []
    if para.align in _ALIGN:
        props.append(f'fo:text-align="{_ALIGN[para.align]}"')
    if para.space_before:
        props.append(f'fo:margin-top="{_pt(para.space_before)}"')
    if para.kind == "list_item" and para.level:
        props.append(f'fo:margin-left="{_pt(18 * para.level)}"')
    if para.direction == "rtl":
        props.append('style:writing-mode="rl-tb"')
    if page_break:
        props.append('fo:break-before="page"')
    return f' text:style-name="{styles.para(" ".join(props))}"' if props else ""


def _para(para: Para, styles: _Styles, page_break: bool = False, inner: str | None = None,
          ) -> str:
    style = _para_style(para, styles, page_break)
    body = inner if inner is not None else "".join(_run(r, styles) for r in para.runs)
    if para.heading:
        return f'<text:h text:outline-level="{min(para.heading, 10)}"{style}>{body}</text:h>'
    return f"<text:p{style}>{body}</text:p>"


def _table(table: Table, styles: _Styles, index: int) -> str:
    owner = {}
    for cell in table.cells:
        for r in range(cell.row, cell.row + cell.row_span):
            for c in range(cell.col, cell.col + cell.col_span):
                owner[(r, c)] = cell
    columns = "<table:table-column/>" * table.cols
    rows = []
    for r in range(table.rows):
        cells = []
        for c in range(table.cols):
            cell = owner.get((r, c))
            if cell is not None and (r, c) != (cell.row, cell.col):
                cells.append("<table:covered-table-cell/>")
                continue
            span = ""
            if cell is not None and cell.col_span > 1:
                span += f' table:number-columns-spanned="{cell.col_span}"'
            if cell is not None and cell.row_span > 1:
                span += f' table:number-rows-spanned="{cell.row_span}"'
            paras = "".join(_para(p, styles) for p in (cell.paras if cell else []))
            cells.append(f'<table:table-cell office:value-type="string"{span}>'
                         f"{paras or '<text:p/>'}</table:table-cell>")
        rows.append("<table:table-row>" + "".join(cells) + "</table:table-row>")
    return f'<table:table table:name="Tabel{index}">{columns}' + "".join(rows) + \
        "</table:table>"


def _frame(name: str, picture: Picture) -> str:
    return (f'<draw:frame text:anchor-type="as-char" svg:width="{_pt(picture.width)}" '
            f'svg:height="{_pt(picture.height)}"><draw:image xlink:href="{name}" '
            'xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/></draw:frame>')


def _manifest(pictures: Sequence[tuple[str, bytes]]) -> str:
    entries = [("/", MIMETYPE), ("content.xml", "text/xml"), ("styles.xml", "text/xml"),
               ("meta.xml", "text/xml"), *((n, "image/png") for n, _ in pictures)]
    return ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            + "".join(f'<manifest:file-entry manifest:full-path="{p}" '
                      f'manifest:media-type="{t}"'
                      + (' manifest:version="1.2"' if p == "/" else "") + "/>"
                      for p, t in entries)
            + "</manifest:manifest>")


def write_odt(document: Document, target: Path, *,
              progress: ProgressCallback | None = None) -> None:
    styles = _Styles()
    body: list[str] = []
    pictures: list[tuple[str, bytes]] = []
    tables = 0
    for index, page in enumerate(document.pages):
        page_break = index > 0 and document.page_breaks
        for item in page.body:
            if isinstance(item, Para):
                body.append(_para(item, styles, page_break))
            elif isinstance(item, Table):
                if page_break:
                    body.append(_para(Para([]), styles, True))
                tables += 1
                body.append(_table(item, styles, tables))
            elif isinstance(item, Picture):
                name = f"Pictures/img{len(pictures) + 1}.png"
                pictures.append((name, item.data))
                body.append(_para(Para([]), styles, page_break, inner=_frame(name, item)))
            page_break = False
        for note in page.footnotes:
            for run in note.runs:
                run.size = min(run.size or 8, 8)
            body.append(_para(note, styles))
        report(progress, index + 1, len(document.pages), "stage.exporting")
    first = document.pages[0] if document.pages else None
    header = "".join(_para(p, styles) for p in (first.header if first else []))
    footer = "".join(_para(p, styles) for p in (first.footer if first else []))
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               f"<office:document-content{_NS}><office:automatic-styles>{styles.xml()}"
               "</office:automatic-styles><office:body><office:text>" + "".join(body)
               + "</office:text></office:body></office:document-content>")
    width, height = (first.width, first.height) if first else (595.3, 841.9)
    numbering = ('<text:linenumbering-configuration text:number-lines="true" '
                 'text:increment="1" text:restart-on-page="true" style:num-format="1"/>'
                 if document.line_numbers else "")
    master = ('<style:master-page style:name="Standard" style:page-layout-name="pm1">'
              + (f"<style:header>{header}</style:header>" if header else "")
              + (f"<style:footer>{footer}</style:footer>" if footer else "")
              + "</style:master-page>")
    styles_xml = ('<?xml version="1.0" encoding="UTF-8"?>'
                  f"<office:document-styles{_NS}><office:styles>{numbering}</office:styles>"
                  '<office:automatic-styles><style:page-layout style:name="pm1">'
                  f'<style:page-layout-properties fo:page-width="{_pt(width)}" '
                  f'fo:page-height="{_pt(height)}" fo:margin="36pt"/></style:page-layout>'
                  f"</office:automatic-styles><office:master-styles>{master}"
                  "</office:master-styles></office:document-styles>")
    meta = ('<?xml version="1.0" encoding="UTF-8"?>'
            f"<office:document-meta{_NS}><office:meta><meta:generator>DocuLens"
            f"</meta:generator><dc:title>{escape(document.title)}</dc:title></office:meta>"
            "</office:document-meta>")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content)
        z.writestr("styles.xml", styles_xml)
        z.writestr("meta.xml", meta)
        z.writestr("META-INF/manifest.xml", _manifest(pictures))
        for name, data in pictures:
            z.writestr(name, data)


# SPEC_05 Exporter. Q-014
class OdtExporter(BaseExporter):
    format = ExportFormat.ODT

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EDITABLE)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        write_odt(build_document(pages, options), target, progress=progress)
        return [target]
