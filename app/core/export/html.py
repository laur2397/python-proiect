"""Exportul HTML (faza 6, pasul 6.6): Q-019, X-124, X-125.

Trei moduri (X-124): `formatted` si `plain` din documentul intermediar
(`docmodel.py`), si `flexible` (Q-006), care pune fiecare bloc si fiecare
imagine la pozitia lor pe pagina (pozitionare absoluta). `Keep pictures`,
`Keep line breaks`, `Keep text and background colors`, `Keep headers and
footers`, `Encoding` (pe 8 biti, caracterele lipsa devin `&#...;`).

`Book settings` (X-125): documentul se imparte in fisiere dupa titluri
(nivelul 1, nivelul 2, sau automat, in parti apropiate ca marime), cu un
cuprins care le leaga.

[DECIZIE AUTONOMA] Imaginile se scriu langa fisier, in folderul
`<nume>_files/`, ca la browserele care salveaza o pagina.

Randarea (`Renderer`, `render_sections`) e folosita si de EPUB.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from app.core.export.base import BaseExporter, ExportOptions, block_text, report
from app.core.export.docmodel import (
    Document,
    Para,
    Picture,
    Run,
    Table,
    _picture,
    _size_pt,
    build_document,
)
from app.core.model import (
    AreaType,
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_COMMA_TO_CEDILLA = str.maketrans("șȘțȚ", "şŞţŢ")
_EIGHT_BIT = ("windows-1250", "iso-8859-2")


def encode_html(text: str, encoding: str) -> bytes:
    if encoding.lower() in _EIGHT_BIT:
        text = text.translate(_COMMA_TO_CEDILLA)
    return text.encode(encoding, errors="xmlcharrefreplace")


@dataclass(slots=True)
class Renderer:
    """Fragmentele (X)HTML; `image` primeste PNG-ul si intoarce adresa lui."""

    image: Callable[[bytes], str]
    colors: bool = True
    fonts: bool = True
    xhtml: bool = False

    def run(self, run: Run) -> str:
        text = escape(run.text).replace("\n", "<br/>" if self.xhtml else "<br>")
        styles = []
        if self.fonts and run.font:
            styles.append(f"font-family:'{run.font}'")
        if self.fonts and run.size:
            styles.append(f"font-size:{run.size:g}pt")
        if self.colors and run.color:
            styles.append(f"color:{run.color}")
        if self.colors and run.highlight:
            styles.append(f"background-color:{run.highlight}")
        if run.underline:
            styles.append("text-decoration:underline")
        if run.bold:
            text = f"<b>{text}</b>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.superscript:
            text = f"<sup>{text}</sup>"
        if run.subscript:
            text = f"<sub>{text}</sub>"
        if styles:
            text = f"<span style={quoteattr(';'.join(styles))}>{text}</span>"
        return text

    def para(self, para: Para) -> str:
        body = "".join(self.run(r) for r in para.runs)
        attrs = ' dir="rtl"' if para.direction == "rtl" else ""
        if para.align:
            attrs += f' style="text-align:{para.align}"'
        if para.heading:
            level = min(para.heading, 6)
            return f"<h{level}{attrs}>{body}</h{level}>"
        if para.kind == "list_item":
            margin = 1.5 * (para.level or 1)
            return f'<p class="li" style="margin-left:{margin}em"{attrs}>{body}</p>'
        if para.kind == "footnote":
            return f'<p class="footnote"{attrs}>{body}</p>'
        return f"<p{attrs}>{body}</p>"

    def table(self, table: Table) -> str:
        rows: dict[int, list[str]] = {}
        for cell in table.cells:
            span = ""
            if cell.col_span > 1:
                span += f' colspan="{cell.col_span}"'
            if cell.row_span > 1:
                span += f' rowspan="{cell.row_span}"'
            content = "".join(self.para(p) for p in cell.paras)
            rows.setdefault(cell.row, []).append(f"<td{span}>{content}</td>")
        body = "".join(f"<tr>{''.join(cells)}</tr>" for _, cells in sorted(rows.items()))
        return f'<table border="1">{body}</table>'

    def picture(self, picture: Picture) -> str:
        close = "/" if self.xhtml else ""
        return (f'<p><img src={quoteattr(self.image(picture.data))} alt="" '
                f'width="{round(picture.width * 96 / 72)}"{close}></p>')

    def item(self, item: Para | Table | Picture) -> str:
        if isinstance(item, Para):
            return self.para(item)
        if isinstance(item, Table):
            return self.table(item)
        return self.picture(item)


@dataclass(slots=True)
class Section:
    title: str
    level: int
    parts: list[str] = field(default_factory=list)


def render_sections(document: Document, renderer: Renderer, split: str = "none",
                    ) -> list[Section]:
    """Documentul in sectiuni (X-125): `none` = una; `h1`/`h2` = la titlurile de
    acel nivel sau mai mari; `auto` = la titluri, in parti apropiate ca marime."""
    items: list[tuple[Para | Table | Picture, str]] = []
    for page in document.pages:
        items += [(p, renderer.para(p)) for p in page.header]
        items += [(it, renderer.item(it)) for it in page.body]
        items += [(p, renderer.para(p)) for p in page.footnotes]
        items += [(p, renderer.para(p)) for p in page.footer]
    limit = {"h1": 1, "h2": 2}.get(split)
    total = sum(len(html) for _, html in items) or 1
    headings = sum(1 for it, _ in items if isinstance(it, Para) and it.heading)
    target = total / max(2, headings)
    sections = [Section(document.title or "Document", 0)]
    size = 0
    for item, html in items:
        level = item.heading if isinstance(item, Para) else 0
        cut = (level <= limit) if limit else size >= target
        if level and split != "none" and sections[-1].parts and cut:
            sections.append(Section(item.text, level))  # type: ignore[union-attr]
            size = 0
        sections[-1].parts.append(html)
        size += len(html)
    return sections


_STYLE = ("body{font-family:serif;margin:2em}table{border-collapse:collapse}"
          "td{padding:2px 6px;vertical-align:top}p.footnote{font-size:smaller}"
          ".page{position:relative;margin:1em auto;border:1px solid #ccc}"
          ".page div,.page img{position:absolute;margin:0}")


def _page_html(title: str, body: str, encoding: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="ro"><head><meta charset="{encoding}">'
            f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
            f"<body>{body}</body></html>\n")


def _flexible(pages: Sequence[PageData], options: ExportOptions,
              image: Callable[[bytes], str]) -> str:
    """Q-006: blocurile si imaginile la pozitia lor (96 px pe inch)."""
    out = []
    for page in pages:
        sx, sy = 96.0 / page.dpi_x, 96.0 / page.dpi_y
        parts = []
        for area in page._ordered_areas():
            b = area.bbox
            if area.area_type in (AreaType.PICTURE, AreaType.BARCODE):
                if options.keep_pictures:
                    src = image(_picture(page, area).data)
                    parts.append(f'<img src={quoteattr(src)} alt="" style="left:'
                                 f'{b.x * sx:.0f}px;top:{b.y * sy:.0f}px;'
                                 f'width:{b.w * sx:.0f}px;height:{b.h * sy:.0f}px">')
                continue
            blocks = list(area.blocks)
            if area.table is not None:
                blocks += [bl for c in area.table.cells for bl in c.blocks]
            for block in blocks:
                if not block.lines or (block.block_type in ("header", "footer")
                                       and not options.keep_headers_footers):
                    continue
                bb = block.bbox if block.bbox.w else b
                heights = sorted(w.bbox.h for ln in block.lines for w in ln.words)
                size = _size_pt(heights[len(heights) // 2], page.dpi_y) if heights else 10
                text = escape(block_text(block, True)).replace("\n", "<br>")
                parts.append(f'<div style="left:{bb.x * sx:.0f}px;top:{bb.y * sy:.0f}px;'
                             f'width:{bb.w * sx:.0f}px;font-size:{size:g}pt">{text}</div>')
        out.append(f'<div class="page" style="width:{page.width_px * sx:.0f}px;'
                   f'height:{page.height_px * sy:.0f}px">{"".join(parts)}</div>')
    return "".join(out)


# SPEC_05 Exporter. Q-019
class HtmlExporter(BaseExporter):
    format = ExportFormat.HTML

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.FORMATTED)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        assets = target.parent / f"{target.stem}_files"
        count = [0]

        def image(data: bytes) -> str:
            assets.mkdir(exist_ok=True)
            count[0] += 1
            name = f"img{count[0]}.png"
            (assets / name).write_bytes(data)
            return f"{assets.name}/{name}"

        mode = LayoutMode(options.layout_mode)
        fmt = dict(options.format_options)
        encoding = options.encoding
        title = options.metadata.get("title") or target.stem
        if mode is LayoutMode.FLEXIBLE:
            body = _flexible(pages, options, image)
            target.write_bytes(encode_html(_page_html(title, body, encoding), encoding))
            report(progress, len(pages), len(pages), "stage.exporting")
            return [target]
        document = build_document(pages, options, headers_in=(
            LayoutMode.FORMATTED, LayoutMode.EDITABLE, LayoutMode.EXACT))
        renderer = Renderer(image, colors=bool(fmt.get("keep_colors", True)))
        sections = render_sections(document, renderer, str(fmt.get("book_split", "none")))
        written: list[Path] = []
        if len(sections) == 1:
            target.write_bytes(encode_html(_page_html(title, "".join(sections[0].parts),
                                                      encoding), encoding))
            written.append(target)
        else:  # X-125: cuprinsul si cate un fisier pe sectiune
            links = []
            for i, section in enumerate(sections, start=1):
                part = target.with_name(f"{target.stem}_{i:03d}{target.suffix}")
                nav = f'<p><a href="{target.name}">&#8593;</a></p>'
                part.write_bytes(encode_html(_page_html(
                    section.title, nav + "".join(section.parts), encoding), encoding))
                written.append(part)
                links.append(f'<li><a href="{part.name}">{escape(section.title)}</a></li>')
            toc = f"<h1>{escape(title)}</h1><ul>{''.join(links)}</ul>"
            target.write_bytes(encode_html(_page_html(title, toc, encoding), encoding))
            written.insert(0, target)
        report(progress, len(pages), len(pages), "stage.exporting")
        return written
