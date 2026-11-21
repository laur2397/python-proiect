"""Exportul RTF (faza 6, pasul 6.4): Q-014, X-100..X-109.

Scris de noi din documentul intermediar (`docmodel.py`). Toate caracterele
non-ASCII se scriu ca `\\uN?`, deci diacriticele romanesti (ș, ț cu virgula)
ajung exact. Tabelele cu celule unite (`\\clmgf`/`\\clmrg`,
`\\clvmgf`/`\\clvmrg`), imaginile PNG (`\\pngblip`), antetele si subsolurile,
stilurile de titlu, rupturile de pagina si numerotarea randurilor.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from app.core.export.base import BaseExporter, ExportOptions, report
from app.core.export.docmodel import Document, Para, Picture, Run, Table, build_document
from app.core.model import (
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageData,
    ProgressCallback,
)

_ALIGN = {"left": r"\ql", "center": r"\qc", "right": r"\qr", "justify": r"\qj"}
MARGIN_TW = 720


def tw(pt: float) -> int:
    """Puncte in twips."""
    return round(pt * 20)


def escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append(r"\line ")
        elif ch == "\t":
            out.append(r"\tab ")
        elif ord(ch) < 128:
            out.append(ch)
        else:
            data = ch.encode("utf-16-be")
            for i in range(0, len(data), 2):
                unit = int.from_bytes(data[i:i + 2], "big")
                out.append(f"\\u{unit if unit < 32768 else unit - 65536}?")
    return "".join(out)


class _Tables:
    """Tabelele de fonturi, culori si stiluri ale documentului."""

    def __init__(self) -> None:
        self.fonts = ["Times New Roman"]
        self.colors: list[str] = []
        self.styles: list[str] = []

    def font(self, name: str | None) -> int:
        if not name:
            return 0
        if name not in self.fonts:
            self.fonts.append(name)
        return self.fonts.index(name)

    def color(self, hex_color: str) -> int:
        value = hex_color.lstrip("#").upper()
        if value not in self.colors:
            self.colors.append(value)
        return self.colors.index(value) + 1  # 0 = culoarea implicita

    def style(self, name: str) -> int:
        if name not in self.styles:
            self.styles.append(name)
        return self.styles.index(name) + 1

    def header(self) -> str:
        fonts = "".join(f"{{\\f{i}\\fnil {escape(n)};}}" for i, n in enumerate(self.fonts))
        colors = ";" + "".join(f"\\red{int(c[0:2], 16)}\\green{int(c[2:4], 16)}"
                               f"\\blue{int(c[4:6], 16)};" for c in self.colors)
        sheet = "{\\s0 Normal;}" + "".join(
            f"{{\\s{i + 1}{_heading_format(name)} {escape(name)};}}"
            for i, name in enumerate(self.styles))
        return f"{{\\fonttbl{fonts}}}\n{{\\colortbl{colors}}}\n{{\\stylesheet{sheet}}}\n"


def _heading_format(name: str) -> str:
    if name.startswith("Heading ") and name.split()[1].isdigit():
        level = int(name.split()[1])
        return f"\\b\\fs{max(20, 36 - 4 * (level - 1))}"
    return ""


def _run(run: Run, tables: _Tables) -> str:
    codes = []
    for flag, code in ((run.bold, r"\b"), (run.italic, r"\i"), (run.underline, r"\ul"),
                       (run.superscript, r"\super"), (run.subscript, r"\sub")):
        if flag:
            codes.append(code)
    if run.font:
        codes.append(f"\\f{tables.font(run.font)}")
    if run.size:
        codes.append(f"\\fs{round(run.size * 2)}")
    if run.color:
        codes.append(f"\\cf{tables.color(run.color)}")
    if run.highlight:  # X-109
        codes.append(f"\\chcbpat{tables.color(run.highlight)}")
    return "{" + "".join(codes) + " " + escape(run.text) + "}"


def _para(para: Para, tables: _Tables, in_table: bool = False) -> str:
    style_name = f"Heading {min(para.heading, 9)}" if para.heading else para.style
    codes = [r"\pard\plain"]
    if style_name:
        codes.append(f"\\s{tables.style(style_name)}{_heading_format(style_name)}")
    if in_table:
        codes.append(r"\intbl")
    if para.align in _ALIGN:
        codes.append(_ALIGN[para.align])
    if para.space_before:
        codes.append(f"\\sb{tw(para.space_before)}")
    if para.kind == "list_item" and para.level:
        codes.append(f"\\li{tw(18 * para.level)}")
    if para.direction == "rtl":
        codes.append(r"\rtlpar")
    body = "".join(_run(r, tables) for r in para.runs)
    return "".join(codes) + " " + body + ("" if in_table else "\\par\n")


def _table(table: Table, tables: _Tables) -> str:
    owner = {}
    for cell in table.cells:
        for r in range(cell.row, cell.row + cell.row_span):
            for c in range(cell.col, cell.col + cell.col_span):
                owner[(r, c)] = cell
    edges, x = [], 0.0
    for width in table.col_widths:
        x += width
        edges.append(tw(x))
    out = []
    for r in range(table.rows):
        row = [r"\trowd\trgaph108"]
        contents = []
        for c in range(table.cols):
            cell = owner.get((r, c))
            if cell is not None:
                if cell.col_span > 1:
                    row.append(r"\clmgf" if c == cell.col else r"\clmrg")
                if cell.row_span > 1:
                    row.append(r"\clvmgf" if r == cell.row else r"\clvmrg")
            row.append(r"\clbrdrt\brdrs\clbrdrl\brdrs\clbrdrb\brdrs\clbrdrr\brdrs")
            row.append(f"\\cellx{edges[c]}")
            first = cell is not None and (r, c) == (cell.row, cell.col)
            paras = cell.paras if first and cell is not None else []
            text = "\\par ".join(_para(p, tables, in_table=True) for p in paras)
            contents.append((text or r"\pard\intbl ") + r"\cell ")
        out.append("".join(row) + "\n" + "".join(contents) + "\\row\n")
    return "".join(out) + r"\pard" + "\n"


def _picture(picture: Picture) -> str:
    with Image.open(io.BytesIO(picture.data)) as img:
        w, h = img.size
    return (f"\\pard{{\\pict\\pngblip\\picw{w}\\pich{h}\\picwgoal{tw(picture.width)}"
            f"\\pichgoal{tw(picture.height)} {picture.data.hex()}}}\\par\n")


def write_rtf(document: Document, target: Path, *,
              progress: ProgressCallback | None = None) -> None:
    tables = _Tables()
    body = []
    for index, page in enumerate(document.pages):
        section = (f"\\paperw{tw(page.width)}\\paperh{tw(page.height)}"
                   f"\\margl{MARGIN_TW}\\margr{MARGIN_TW}\\margt{MARGIN_TW}\\margb{MARGIN_TW}")
        if document.line_numbers:
            section += r"\linemod1\linerestart"
        if index and document.page_breaks:
            body.append("\\sect\\sectd")
        body.append(section + "\n")
        for name, paras in (("header", page.header), ("footer", page.footer)):
            if paras:
                body.append(f"{{\\{name} " + "".join(_para(p, tables) for p in paras) + "}\n")
        for item in page.body:
            if isinstance(item, Para):
                body.append(_para(item, tables))
            elif isinstance(item, Table):
                body.append(_table(item, tables))
            elif isinstance(item, Picture):
                body.append(_picture(item))
        for note in page.footnotes:
            for run in note.runs:
                run.size = min(run.size or 8, 8)
            body.append(_para(note, tables))
        report(progress, index + 1, len(document.pages), "stage.exporting")
    info = f"{{\\info{{\\title {escape(document.title)}}}}}\n" if document.title else ""
    text = ("{\\rtf1\\ansi\\ansicpg1252\\deff0\\uc1\n" + tables.header() + info
            + "".join(body) + "}\n")
    Path(target).write_bytes(text.encode("ascii"))


# SPEC_05 Exporter. Q-014
class RtfExporter(BaseExporter):
    format = ExportFormat.RTF

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EDITABLE)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        target = Path(target)
        write_rtf(build_document(pages, options), target, progress=progress)
        return [target]
