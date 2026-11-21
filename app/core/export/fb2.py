"""Exportul FB2 (faza 6, pasul 6.6): Q-021, X-126.

FictionBook 2.0, scris de noi: `description` (titlul, limba, generatorul),
`body` cu sectiuni la titlurile de nivel 1, paragrafe cu `strong` si
`emphasis` (X-126: stilurile de font se pastreaza numai in EPUB; in FB2 raman
doar bold si italic), tabele si imagini (`binary` base64). Coperta din prima
pagina la cerere. Numai format de iesire.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape

from app.core.export.base import BaseExporter, ExportOptions, report
from app.core.export.docmodel import Para, Picture, Run, Table, build_document
from app.core.export.epub import _cover
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)


def _run(run: Run) -> str:
    text = escape(run.text.replace("\n", " "))
    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<emphasis>{text}</emphasis>"
    if run.superscript:
        text = f"<sup>{text}</sup>"
    if run.subscript:
        text = f"<sub>{text}</sub>"
    return text


def _para(para: Para) -> str:
    return "<p>" + "".join(_run(r) for r in para.runs) + "</p>"


def _table(table: Table) -> str:
    rows: dict[int, list[str]] = {}
    for cell in table.cells:
        span = (f' colspan="{cell.col_span}"' if cell.col_span > 1 else "") + (
            f' rowspan="{cell.row_span}"' if cell.row_span > 1 else "")
        text = " ".join("".join(_run(r) for r in p.runs) for p in cell.paras)
        rows.setdefault(cell.row, []).append(f"<td{span}>{text}</td>")
    return "<table>" + "".join(f"<tr>{''.join(c)}</tr>" for _, c in sorted(rows.items())) + \
        "</table>"


# SPEC_05 Exporter. Q-021
class Fb2Exporter(BaseExporter):
    format = ExportFormat.FB2

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.FORMATTED)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        fmt = dict(options.format_options)
        target = Path(target)
        title = options.metadata.get("title") or target.stem
        document = build_document(pages, options)
        binaries: list[tuple[str, str, bytes]] = []
        sections: list[tuple[str, list[str]]] = [("", [])]
        for page in document.pages:
            for item in [*page.body, *page.footnotes]:
                if isinstance(item, Para):
                    if item.heading == 1 and sections[-1][1]:
                        sections.append((item.text, []))
                    if item.heading:
                        if not sections[-1][0]:
                            sections[-1] = (item.text, sections[-1][1])
                        sections[-1][1].append(f"<subtitle>{escape(item.text)}</subtitle>")
                    else:
                        sections[-1][1].append(_para(item))
                elif isinstance(item, Table):
                    sections[-1][1].append(_table(item))
                elif isinstance(item, Picture):
                    ident = f"img{len(binaries) + 1}.png"
                    binaries.append((ident, "image/png", item.data))
                    sections[-1][1].append(f'<image l:href="#{ident}"/>')
        cover = ""
        if fmt.get("first_page_cover"):
            binaries.append(("cover.jpg", "image/jpeg", _cover(pages[0])))
            cover = '<coverpage><image l:href="#cover.jpg"/></coverpage>'
        body = "".join(
            "<section>" + (f"<title><p>{escape(name)}</p></title>" if name else "")
            + ("".join(parts) or "<p/>") + "</section>" for name, parts in sections)
        binary = "".join(
            f'<binary id="{ident}" content-type="{kind}">{base64.b64encode(data).decode()}'
            "</binary>" for ident, kind, data in binaries)
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" '
               'xmlns:l="http://www.w3.org/1999/xlink"><description><title-info>'
               "<genre>reference</genre><author><nickname>DocuLens</nickname></author>"
               f"<book-title>{escape(title)}</book-title>{cover}<lang>ro</lang></title-info>"
               "<document-info><author><nickname>DocuLens</nickname></author>"
               "<program-used>DocuLens</program-used><id>doculens</id><version>1.0</version>"
               f"</document-info></description><body>{body}</body>{binary}</FictionBook>\n")
        target.write_text(xml, encoding="utf-8")
        report(progress, len(pages), len(pages), "stage.exporting")
        return [target]
