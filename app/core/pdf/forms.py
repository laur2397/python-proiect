"""Formularele PDF (faza 11): H-001…H-058.

Formularul ramane in PDF (`/AcroForm`), ca semnele de carte si linkurile din
fazele 7–9 (`docs/plan/faza_11_pasi.md`, decizia 1). Fiecare widget de pe pagina
e un `FormFieldData`: copiile legate (H-016) sunt widgeturi ale aceluiasi camp,
iar butoanele radio (H-033) sunt widgeturile campului-grup, cu numele butonului
= starea lor „pornit”.

Aspectul (`/AP`) il scrie DocuLens la fiecare valoare noua, cu fontul campului
incorporat ca subset (diacriticele romanesti se vad in orice cititor); `/DA`
ramane cu un font standard, ca alte programe sa poata regenera aspectul
(decizia 2). Bifele si butoanele radio care au deja aspect isi pastreaza
desenul; li se schimba numai starea (`/AS`).

Pasul 11.1: citirea, completarea, golirea, datele de formular (FDF, XFDF, HTML).
Pasul 11.2: crearea, modificarea, copierea, mutarea si stergerea campurilor.
"""

from __future__ import annotations

import html
import io
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.errors import (
    CoreError,
    DuplicateFieldNameError,
    FileCorruptError,
    InvalidFieldNameError,
    OrphanRadioButtonError,
    SignedFieldCopyError,
    UnsupportedFormatError,
)
from app.core.model import FormFieldData, FormFieldType, Rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument
    from app.core.pdf.embedded_font import TextFont

# --- indicatorii de camp (PDF 32000-1, 12.7.3.1, 12.7.4) ---------------------------------

FF_READONLY = 1
FF_REQUIRED = 1 << 1
FF_MULTILINE = 1 << 12
FF_NO_TOGGLE_OFF = 1 << 14
FF_RADIO = 1 << 15
FF_PUSHBUTTON = 1 << 16
FF_COMBO = 1 << 17
FF_EDIT = 1 << 18
FF_MULTISELECT = 1 << 21

OFF = "Off"
"""Starea „oprit” a unei bife sau a unui buton radio."""
DEFAULT_FONT_SIZE = 10.0
AUTO_FONT_MAX = 12.0
PADDING = 2.0
DEFAULT_DATE_FORMAT = "dd.mm.yyyy"
XFDF_NS = "http://ns.adobe.com/xfdf/"
DATA_FORMATS = ("fdf", "xfdf", "html")
"""H-004: formatele datelor de formular salvate."""

_EMPTY_WORDS = {"", "off", "0", "false", "no", "nu"}
_DA_FONT = re.compile(r"/([^\s/]+)\s+([\d.]+)\s+Tf")
_DA_RGB = re.compile(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg")
_DA_GRAY = re.compile(r"(?<![\d.])([\d.]+)\s+g\b")
_DATE_SCRIPT = re.compile(r"AFDate_(?:Format|Keystroke)Ex\(\s*[\"']([^\"']+)[\"']")
_DATE_TOKEN = re.compile(r"yyyy|yy|mm|m|dd|d")


# --- tipuri interne -----------------------------------------------------------------


@dataclass
class _Field:
    """Un camp terminal din arborele `/AcroForm`, cu widgeturile lui."""

    name: str
    obj: pikepdf.Object
    widgets: list[tuple[int, pikepdf.Object]] = field(default_factory=list)
    """(pagina, widget)."""

    def get(self, key: str) -> Any:
        return _inherited(self.obj, key)

    @property
    def flags(self) -> int:
        value = self.get("/Ff")
        return int(value) if value is not None else 0

    @property
    def kind(self) -> FormFieldType | None:
        ft = self.get("/FT")
        flags = self.flags
        if ft == "/Tx":
            return FormFieldType.TEXT
        if ft == "/Btn":
            if flags & FF_PUSHBUTTON:
                return FormFieldType.BUTTON
            return FormFieldType.RADIO if flags & FF_RADIO else FormFieldType.CHECKBOX
        if ft == "/Ch":
            return FormFieldType.DROPDOWN if flags & FF_COMBO else FormFieldType.LISTBOX
        if ft == "/Sig":
            return FormFieldType.SIGNATURE
        return None


def _inherited(obj: pikepdf.Object, key: str) -> Any:
    seen: set[tuple[int, int]] = set()
    node: Any = obj
    while isinstance(node, pikepdf.Dictionary):
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        if parent is None or not parent.is_indirect or parent.objgen in seen:
            return None
        seen.add(parent.objgen)
        node = parent
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, pikepdf.Name):
        return str(value)[1:]
    if isinstance(value, pikepdf.Array):
        return "\n".join(_text(v) for v in value)
    return str(value)


def _widget_pages(pdf: pikepdf.Pdf) -> dict[tuple[int, int], int]:
    pages: dict[tuple[int, int], int] = {}
    for number, page in enumerate(pdf.pages, start=1):
        for annot in page.obj.get("/Annots", None) or []:
            if isinstance(annot, pikepdf.Dictionary) and annot.is_indirect:
                pages.setdefault(annot.objgen, number)
    return pages


def _walk(pdf: pikepdf.Pdf) -> list[_Field]:
    """Campurile terminale, in ordinea din document."""
    form = pdf.Root.get("/AcroForm")
    if not isinstance(form, pikepdf.Dictionary):
        return []
    pages = _widget_pages(pdf)
    out: list[_Field] = []
    seen: set[tuple[int, int]] = set()
    stack: list[tuple[Any, str]] = [(f, "") for f in reversed(list(form.get("/Fields", [])))]
    while stack:
        node, prefix = stack.pop()
        if not isinstance(node, pikepdf.Dictionary):
            continue
        if node.is_indirect:
            if node.objgen in seen:
                continue
            seen.add(node.objgen)
        partial = _text(node.get("/T")) if "/T" in node else ""
        name = f"{prefix}.{partial}" if prefix and partial else prefix or partial
        kids = [k for k in node.get("/Kids", []) if isinstance(k, pikepdf.Dictionary)]
        named = [k for k in kids if "/T" in k]
        if named:
            stack.extend((k, name) for k in reversed(named))
            continue
        widgets = kids or [node]
        item = _Field(name, node)
        for widget in widgets:
            page = pages.get(widget.objgen) if widget.is_indirect else None
            if page is None and "/P" in widget:
                page = next((i for i, p in enumerate(pdf.pages, start=1)
                             if p.obj.objgen == widget.P.objgen), None)
            if page is not None:
                item.widgets.append((page, widget))
        if item.kind is not None:
            out.append(item)
    return out


def _on_state(widget: pikepdf.Object) -> str | None:
    """Numele starii „pornit” a unei bife sau a unui buton radio."""
    ap = widget.get("/AP")
    normal = ap.get("/N") if isinstance(ap, pikepdf.Dictionary) else None
    if isinstance(normal, pikepdf.Dictionary):
        for key in normal:
            if key != "/" + OFF:
                return key[1:]
    return None


def _color(value: Any) -> str | None:
    from app.core.pdf.annotations import _color_hex

    if not isinstance(value, pikepdf.Array) or len(value) == 0:
        return None
    if len(value) == 4:  # CMYK
        c, m, y, k = (float(v) for v in value)
        rgb = [(1 - min(1.0, v + k)) for v in (c, m, y)]
        return _color_hex(rgb)
    return _color_hex(value)


def _parse_da(da: str) -> tuple[str | None, float | None, str | None]:
    """(resursa de font, marimea, culoarea) dintr-un sir /DA."""
    from app.core.pdf.annotations import _color_hex

    font = _DA_FONT.search(da)
    color: str | None = None
    rgb = _DA_RGB.search(da)
    if rgb:
        color = _color_hex([float(v) for v in rgb.groups()])
    else:
        gray = _DA_GRAY.search(da)
        if gray:
            color = _color_hex([float(gray.group(1))])
    if font is None:
        return None, None, color
    return font.group(1), float(font.group(2)), color


def _font_base_name(pdf: pikepdf.Pdf, resource: str | None) -> str | None:
    if resource is None:
        return None
    form = pdf.Root.get("/AcroForm")
    dr = form.get("/DR") if isinstance(form, pikepdf.Dictionary) else None
    fonts = dr.get("/Font") if isinstance(dr, pikepdf.Dictionary) else None
    font = fonts.get("/" + resource) if isinstance(fonts, pikepdf.Dictionary) else None
    if isinstance(font, pikepdf.Dictionary) and "/BaseFont" in font:
        base = str(font.BaseFont)[1:]
        return base.split("+", 1)[1] if "+" in base[:7] else base
    return {"Helv": "Helvetica", "TiRo": "Times-Roman", "Cour": "Courier"}.get(resource,
                                                                              resource)


def _date_format(item: _Field) -> str | None:
    aa = item.obj.get("/AA")
    if not isinstance(aa, pikepdf.Dictionary):
        return None
    for key in ("/F", "/K"):
        action = aa.get(key)
        if isinstance(action, pikepdf.Dictionary) and "/JS" in action:
            script = action.JS
            code = script.read_bytes().decode("latin-1") if isinstance(
                script, pikepdf.Stream) else str(script)
            match = _DATE_SCRIPT.search(code)
            if match:
                return match.group(1)
    return None


def _items(item: _Field) -> list[tuple[str, str | None, bool]]:
    defaults = set(_text(item.get("/DV")).split("\n")) - {""}
    out: list[tuple[str, str | None, bool]] = []
    for entry in item.get("/Opt") or []:
        if isinstance(entry, pikepdf.Array) and len(entry) >= 2:
            value, text = _text(entry[0]), _text(entry[1])
            out.append((text, value, value in defaults))
        else:
            text = _text(entry)
            out.append((text, None, text in defaults))
    return out


def _to_data(pdf: pikepdf.Pdf, item: _Field, page: int, widget: pikepdf.Object,
             index: int) -> FormFieldData:
    from app.core.pdf.text import from_pdf_rect, page_geometry

    kind = item.kind
    assert kind is not None
    flags = item.flags
    rect = from_pdf_rect(page_geometry(pdf.pages[page - 1]), list(widget.get("/Rect")))
    da = _text(widget.get("/DA") or item.get("/DA") or
               (pdf.Root.AcroForm.get("/DA") if "/AcroForm" in pdf.Root else None))
    resource, size, da_color = _parse_da(da)
    mk = widget.get("/MK")
    mk = mk if isinstance(mk, pikepdf.Dictionary) else pikepdf.Dictionary()
    bs = widget.get("/BS")
    border_color = _color(mk.get("/BC"))
    width: float | None = None
    if isinstance(bs, pikepdf.Dictionary) and "/W" in bs:
        width = float(bs.W)
    elif border_color is not None:
        width = 1.0
    name, group = item.name, None
    value: str | None = _text(item.get("/V")) or None
    if kind == FormFieldType.RADIO:
        group = item.name
        name = _on_state(widget) or f"{item.name}.{index + 1}"
    elif kind == FormFieldType.CHECKBOX:
        on = _on_state(widget) or "Yes"
        value = on if value == on else OFF
    elif kind == FormFieldType.SIGNATURE:
        value = "signed" if item.get("/V") is not None else None
    elif kind == FormFieldType.BUTTON:
        value = _text(mk.get("/CA")) or None  # `Button Text` (decizia 4)
    date_format = _date_format(item) if kind == FormFieldType.TEXT else None
    tooltip = _text(item.get("/TU")) or None
    check = kind in (FormFieldType.CHECKBOX, FormFieldType.RADIO)
    return FormFieldData(
        id=widget.objgen[0], field_name=name, field_type=kind, page_number=page, rect=rect,
        tooltip=tooltip, is_required=bool(flags & FF_REQUIRED),
        is_readonly=bool(flags & FF_READONLY), fill_color=_color(mk.get("/BG")),
        border_color=border_color, border_width=width,
        font_name=None if check else _font_base_name(pdf, resource),
        font_size=None if check else (size or None),
        text_color=None if check else da_color, check_color=da_color if check else None,
        text_format=("date" if date_format else "text") if kind == FormFieldType.TEXT
        else None,
        date_format=date_format, is_multiline=bool(flags & FF_MULTILINE),
        max_symbols=int(item.get("/MaxLen")) if item.get("/MaxLen") is not None else None,
        group_name=group, allow_custom=bool(flags & FF_EDIT),
        allow_multiple=bool(flags & FF_MULTISELECT),
        linked_to=item.name if index and kind != FormFieldType.RADIO else None,
        items=_items(item) if kind in (FormFieldType.DROPDOWN, FormFieldType.LISTBOX) else [],
        value=value,
    )


# --- datele (H-030) -------------------------------------------------------------------


def format_date(value: str, view: str) -> str:
    """H-030: data tastata in orice forma, redusa la formatul din `View`
    (`dd.mm.yyyy`, `mm/dd/yy`, `yyyy-mm-dd`...). Un an de patru cifre la inceput
    inseamna an-luna-zi; altfel ordinea e cea din `View`. Numele lunilor (`mmm`)
    nu se folosesc: formatele sunt numerice (INCOMPLET, marcat)."""
    numbers = re.findall(r"\d+", value)
    if len(numbers) != 3:
        raise ValueError(f"data {value!r} nu se poate citi")
    order: list[str] = []
    for token in _DATE_TOKEN.findall(view.lower()):
        if token[0] not in order:
            order.append(token[0])
    if len(numbers[0]) == 4:
        order = ["y", "m", "d"]
    elif sorted(order) != ["d", "m", "y"]:
        order = ["d", "m", "y"]
    parts = dict(zip(order, (int(n) for n in numbers), strict=True))
    year = parts["y"]
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        moment = date(year, parts["m"], parts["d"])
    except ValueError as exc:
        raise ValueError(f"data {value!r} nu exista") from exc
    tokens = {"yyyy": f"{moment.year:04d}", "yy": f"{moment.year % 100:02d}",
              "mm": f"{moment.month:02d}", "m": str(moment.month),
              "dd": f"{moment.day:02d}", "d": str(moment.day)}
    return _DATE_TOKEN.sub(lambda m: tokens[m.group(0)], view.lower())


# --- aspectul (decizia 2) ---------------------------------------------------------------


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _rgb_op(color: str, op: str) -> str:
    from app.core.pdf.markup import rgb

    return " ".join(_num(c) for c in rgb(color)) + " " + op


def _box(data: FormFieldData, w: float, h: float, *, round_: bool = False) -> str:
    from app.core.pdf.annotations import _ellipse

    ops: list[str] = []
    bw = data.border_width if data.border_width is not None else (
        1.0 if data.border_color else 0.0)
    if data.fill_color:
        shape = _ellipse(0, 0, w, h) if round_ else f"0 0 {_num(w)} {_num(h)} re"
        ops.append(f"{_rgb_op(data.fill_color, 'rg')} {shape} f")
    if data.border_color and bw > 0:
        half = bw / 2
        shape = _ellipse(half, half, w - half, h - half) if round_ else \
            f"{_num(half)} {_num(half)} {_num(w - bw)} {_num(h - bw)} re"
        ops.append(f"{_num(bw)} w {_rgb_op(data.border_color, 'RG')} {shape} S")
    return " ".join(ops)


def _stream(pdf: pikepdf.Pdf, w: float, h: float, ops: str,
            font: TextFont | None = None) -> pikepdf.Stream:
    resources = pikepdf.Dictionary()
    if font is not None:
        resources.Font = pikepdf.Dictionary(F1=font.font)
    stream = pdf.make_stream(ops.encode("ascii"))
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = [0, 0, w, h]
    stream.Resources = resources
    return stream


def _font_for(pdf: pikepdf.Pdf, data: FormFieldData, texts: Sequence[str]) -> TextFont:
    from app.core.fonts import font_file
    from app.core.pdf.embedded_font import embed_text_font

    path = font_file(data.font_name) if data.font_name else None
    return embed_text_font(pdf, [t for t in texts if t] or [" "], font_path=path)


def _font_size(data: FormFieldData, h: float) -> float:
    if data.font_size:
        return float(data.font_size)
    return max(4.0, min(AUTO_FONT_MAX, (h - 2 * PADDING) * 0.75))


def _text_ops(font: TextFont, data: FormFieldData, lines: Sequence[str], w: float,
              h: float, size: float, *, quadding: int = 0, top: bool = False,
              selected: Sequence[int] = ()) -> str:
    """Randurile de text in caseta campului, decupate la marginea interioara."""
    leading = size * (font.ascent - font.descent) / 1000
    ops = [(f"/Tx BMC q {_num(PADDING / 2)} {_num(PADDING / 2)} {_num(w - PADDING)} "
            f"{_num(h - PADDING)} re W n")]
    if top or len(lines) > 1:
        y0 = h - PADDING - size * font.ascent / 1000
    else:
        y0 = (h - leading) / 2 - size * font.descent / 1000
    for index in selected:
        y = y0 - index * leading + size * font.descent / 1000
        ops.append(f"0.6 0.75 0.95 rg {_num(PADDING / 2)} {_num(y)} {_num(w - PADDING)} "
                   f"{_num(leading)} re f")
    ops.append(f"BT /F1 {_num(size)} Tf {_rgb_op(data.text_color or '#000000', 'rg')}")
    for i, line in enumerate(lines):
        width = font.width(line, size)
        x = PADDING if quadding == 0 else (w - width) / 2 if quadding == 1 else \
            w - PADDING - width
        ops.append(f"1 0 0 1 {_num(x)} {_num(y0 - i * leading)} Tm {font.encode(line)} Tj")
    ops.append("ET Q EMC")
    return " ".join(ops)


def _check_ops(data: FormFieldData, w: float, h: float, kind: FormFieldType) -> str:
    from app.core.pdf.annotations import _ellipse

    color = data.check_color or "#000000"
    if kind == FormFieldType.RADIO:
        r = min(w, h) * 0.25
        cx, cy = w / 2, h / 2
        return f"{_rgb_op(color, 'rg')} {_ellipse(cx - r, cy - r, cx + r, cy + r)} f"
    lw = max(1.0, min(w, h) * 0.1)
    return (f"q {_num(lw)} w 1 J 1 j {_rgb_op(color, 'RG')} {_num(w * 0.22)} {_num(h * 0.52)} m "
            f"{_num(w * 0.42)} {_num(h * 0.27)} l {_num(w * 0.8)} {_num(h * 0.78)} l S Q")


def _display_value(item: _Field, data: FormFieldData) -> list[str]:
    value = _text(item.get("/V"))
    if data.field_type == FormFieldType.DROPDOWN:
        for text, export, _default in data.items:
            if export is not None and export == value:
                return [text]
        return [value]
    if data.field_type == FormFieldType.TEXT and data.is_multiline:
        return value.split("\n")
    return [value.replace("\n", " ")]


def _write_appearance(pdf: pikepdf.Pdf, item: _Field, widget: pikepdf.Object,
                      data: FormFieldData, *, redraw: bool = False) -> None:
    """Aspectul unui widget dupa valoarea curenta a campului. Bifele si butoanele
    radio cu aspect existent se redeseneaza numai cu `redraw`."""
    from app.core.pdf.embedded_font import wrap

    x0, y0, x1, y1 = (float(v) for v in widget.Rect)
    w, h = abs(x1 - x0), abs(y1 - y0)
    kind = data.field_type
    quadding = int(_inherited(widget, "/Q") or 0)
    if kind in (FormFieldType.CHECKBOX, FormFieldType.RADIO):
        on = _on_state(widget) or ("Yes" if kind == FormFieldType.CHECKBOX
                                   else data.field_name)
        ap = widget.get("/AP")
        normal = ap.get("/N") if isinstance(ap, pikepdf.Dictionary) else None
        if redraw or not isinstance(normal, pikepdf.Dictionary) or "/" + on not in normal:
            round_ = kind == FormFieldType.RADIO
            box = _box(data, w, h, round_=round_)
            states = pikepdf.Dictionary()
            states["/" + on] = _stream(pdf, w, h, box + " " + _check_ops(data, w, h, kind))
            states["/" + OFF] = _stream(pdf, w, h, box or " ")
            widget.AP = pikepdf.Dictionary(N=states)
        value = _text(item.get("/V"))
        widget.AS = pikepdf.Name("/" + (on if value == on else OFF))
        return
    box = _box(data, w, h)
    font: TextFont | None = None
    text = ""
    if kind == FormFieldType.BUTTON:
        mk = widget.get("/MK")
        caption = _text(mk.get("/CA")) if isinstance(mk, pikepdf.Dictionary) else ""
        if caption:
            font = _font_for(pdf, data, [caption])
            text = _text_ops(font, data, [caption], w, h, _font_size(data, h), quadding=1)
    elif kind == FormFieldType.LISTBOX:
        labels = [t for t, _v, _d in data.items]
        chosen = set(_text(item.get("/V")).split("\n")) - {""}
        selected = [i for i, (t, v, _d) in enumerate(data.items) if (v or t) in chosen]
        if labels:
            font = _font_for(pdf, data, labels)
            size = data.font_size or DEFAULT_FONT_SIZE
            text = _text_ops(font, data, labels, w, h, size, top=True, selected=selected)
    elif kind in (FormFieldType.TEXT, FormFieldType.DROPDOWN):
        lines = _display_value(item, data)
        if any(lines):
            font = _font_for(pdf, data, lines)
            if data.is_multiline:
                size = data.font_size or DEFAULT_FONT_SIZE
                lines = [part for line in lines
                         for part in (wrap(font, line, size, w - 2 * PADDING) or [""])]
                text = _text_ops(font, data, lines, w, h, size, quadding=quadding, top=True)
            else:
                text = _text_ops(font, data, lines, w, h, _font_size(data, h),
                                 quadding=quadding)
    ops = " ".join(part for part in (box, text) if part) or " "
    widget.AP = pikepdf.Dictionary(N=_stream(pdf, w, h, ops, font))


# --- FDF -------------------------------------------------------------------------------


def _open_fdf(data: bytes) -> tuple[pikepdf.Pdf, pikepdf.Object]:
    """Dictionarul /FDF dintr-un fisier FDF. FDF-ul nu are arbore de pagini, deci
    se citeste ca PDF cu un catalog si un tabel xref adaugate."""
    roots = re.findall(rb"/Root\s+(\d+)\s+(\d+)\s+R", data)
    cut = data.rfind(b"trailer")
    if not roots or cut < 0 or b"\n" not in data[:cut]:
        raise FileCorruptError("fisierul FDF nu are trailer")
    number, generation = roots[-1]
    body = data[:cut].split(b"\n", 1)[1]
    out = bytearray(b"%PDF-1.7\n")
    base = len(out)
    offsets = {int(m.group(1)): base + m.start(1)
               for m in re.finditer(rb"(?m)^[ \t]*(\d+)\s+(\d+)\s+obj\b", body)}
    if not offsets:
        raise FileCorruptError("fisierul FDF nu are obiecte")
    out += body + b"\n"
    top = max(offsets) + 1
    offsets[top] = len(out)
    out += b"%d 0 obj << /Type /Catalog /Pages %d 0 R /FDFRoot %s %s R >> endobj\n" % (
        top, top + 1, number, generation)
    offsets[top + 1] = len(out)
    out += b"%d 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n" % (top + 1)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (top + 2)
    for i in range(1, top + 2):
        out += (b"%010d 00000 n \n" % offsets[i]) if i in offsets else \
            b"0000000000 65535 f \n"
    out += b"trailer << /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        top + 2, top, xref)
    try:
        pdf = pikepdf.open(io.BytesIO(bytes(out)))
        root = pdf.Root.FDFRoot.FDF
    except (pikepdf.PdfError, AttributeError, KeyError) as exc:
        raise FileCorruptError("fisierul FDF nu se poate citi") from exc
    return pdf, root


def _fdf_values(fields: Any, prefix: str = "") -> Iterator[tuple[str, str]]:
    for entry in fields or []:
        if not isinstance(entry, pikepdf.Dictionary):
            continue
        partial = _text(entry.get("/T"))
        name = f"{prefix}.{partial}" if prefix and partial else prefix or partial
        if "/V" in entry:
            yield name, _text(entry.V)
        yield from _fdf_values(entry.get("/Kids"), name)


def _xfdf_values(node: ET.Element, prefix: str = "") -> Iterator[tuple[str, str]]:
    for child in node:
        if child.tag.rsplit("}", 1)[-1] != "field":
            continue
        partial = child.get("name", "")
        name = f"{prefix}.{partial}" if prefix and partial else prefix or partial
        values = [v.text or "" for v in child if v.tag.rsplit("}", 1)[-1] == "value"]
        if values:
            yield name, "\n".join(values)
        yield from _xfdf_values(child, name)


def _pdf_literal(value: str) -> str:
    return bytes(pikepdf.String(value).unparse()).decode("latin-1")


def _list_indices(item: _Field, value: Any) -> pikepdf.Array:
    exports = [(v if v is not None else t) for t, v, _d in _items(item)]
    chosen = _text(value).split("\n")
    return pikepdf.Array(sorted(exports.index(c) for c in chosen if c in exports))


# --- crearea si modificarea (pasul 11.2) ------------------------------------------------

AUTO_NAMES = {
    FormFieldType.TEXT: "TextField", FormFieldType.CHECKBOX: "Checkbox",
    FormFieldType.RADIO: "Radio Button", FormFieldType.DROPDOWN: "Drop-down List",
    FormFieldType.LISTBOX: "List Box", FormFieldType.BUTTON: "Button",
    FormFieldType.SIGNATURE: "Signature",
}
"""H-109: numele generate, `TextField 3`, `Checkbox 1`, `List Box 1`, `Button 1`.
Sunt date scrise in PDF, ca in original, nu text de interfata."""
RADIO_GROUP_NAME = "Radio Group"
MIN_SIZE = 8.0
"""H-020 (si SPEC_04): latimea si inaltimea minime, in puncte."""
PASTE_OFFSET = 10.0
"""H-015, H-016: copia apare deplasata cu atat, in puncte."""
GUIDE_TOLERANCE = 1.0
"""H-018: marginile la mai putin de atat (puncte) sunt „identice”."""
UNITS = {"pt": 1.0, "cm": 72 / 2.54, "in": 72.0}
"""H-030: unitatile din tabul `General`, in puncte."""
STYLE_KEYS = ("fill_color", "border_color", "border_width", "font_name", "font_size",
              "text_color", "check_color")
"""`Set as Default Style`: proprietatile din tabul `Appearance`."""

_MANAGED_FLAGS = (FF_READONLY | FF_REQUIRED | FF_MULTILINE | FF_NO_TOGGLE_OFF | FF_RADIO
                  | FF_PUSHBUTTON | FF_COMBO | FF_EDIT | FF_MULTISELECT)
_FIELD_KEYS = ("/FT", "/Ff", "/V", "/DV", "/TU", "/TM", "/MaxLen", "/Opt", "/I", "/Q")
_FIELD_AA = ("/K", "/F", "/V", "/C")
"""Declansatorii de camp din /AA; restul (mouse, focus) sunt ai widgetului."""


def to_units(points: float, unit: str) -> float:
    """H-030: puncte → unitatea aleasa."""
    return points / UNITS[unit]


def from_units(value: float, unit: str) -> float:
    """H-030: unitatea aleasa → puncte."""
    return value * UNITS[unit]


def style_of(data: FormFieldData) -> dict[str, Any]:
    """`Set as Default Style`: stilul unui camp, de pastrat in setari."""
    return {key: getattr(data, key) for key in STYLE_KEYS}


def with_style(data: FormFieldData, style: dict[str, Any]) -> FormFieldData:
    """Campul nou, cu stilul implicit pastrat (cheile necunoscute se ignora)."""
    return replace(data, **{k: v for k, v in style.items() if k in STYLE_KEYS})


def _is_on(value: str | None) -> bool:
    return value is not None and value.strip().lower() not in _EMPTY_WORDS


def _check_name(name: str) -> None:
    if not name or not name.strip() or name.startswith(".") or name.endswith(".") \
            or ".." in name:
        raise InvalidFieldNameError("numele campului nu e valid", name=name)


def _acroform(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
    form = pdf.Root.get("/AcroForm")
    if not isinstance(form, pikepdf.Dictionary):
        form = pdf.make_indirect(pikepdf.Dictionary())
        pdf.Root.AcroForm = form
    if "/Fields" not in form:
        form.Fields = pikepdf.Array()
    if "/DA" not in form:
        form.DA = pikepdf.String("/Helv 0 Tf 0 g")
    if "/DR" not in form:
        form.DR = pikepdf.Dictionary()
    if "/Font" not in form.DR:
        form.DR.Font = pikepdf.Dictionary()
    if "/Helv" not in form.DR.Font:
        form.DR.Font.Helv = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica, Encoding=pikepdf.Name.WinAnsiEncoding))
    if "/ZaDb" not in form.DR.Font:
        form.DR.Font.ZaDb = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.ZapfDingbats))
    return form


def _font_resource(pdf: pikepdf.Pdf, font_name: str | None) -> str:
    """Resursa de font din /DR pentru /DA; fontul nu se incorporeaza aici (aspectul
    are fontul lui), e doar referinta pentru alte programe."""
    form = _acroform(pdf)
    if not font_name or font_name in ("Helvetica", "Helv"):
        return "Helv"
    resource = re.sub(r"[^A-Za-z0-9]", "", font_name) or "F"
    fonts = form.DR.Font
    if "/" + resource not in fonts:
        fonts["/" + resource] = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.TrueType,
            BaseFont=pikepdf.Name("/" + font_name), Encoding=pikepdf.Name.WinAnsiEncoding))
    return resource


def _color_array(color: str | None) -> pikepdf.Array | None:
    from app.core.pdf.markup import rgb

    return pikepdf.Array([round(c, 4) for c in rgb(color)]) if color else None


def _siblings(form: pikepdf.Dictionary, node: pikepdf.Object) -> pikepdf.Array:
    parent = node.get("/Parent")
    return parent.Kids if isinstance(parent, pikepdf.Dictionary) else form.Fields


def _detach(form: pikepdf.Dictionary, node: pikepdf.Object) -> None:
    """Scoate nodul din arbore si curata parintii ramasi fara copii."""
    while True:
        siblings = _siblings(form, node)
        for i in range(len(siblings) - 1, -1, -1):
            if siblings[i].is_indirect and siblings[i].objgen == node.objgen:
                del siblings[i]
        parent = node.get("/Parent")
        if "/Parent" in node:
            del node["/Parent"]
        if not isinstance(parent, pikepdf.Dictionary) or len(parent.Kids) or \
                "/FT" in parent:
            return
        node = parent


def _attach(pdf: pikepdf.Pdf, form: pikepdf.Dictionary, name: str,
            node: pikepdf.Object) -> None:
    """Pune nodul in arbore sub numele complet `a.b.c`, cu parintii lipsa."""
    parts = name.split(".")
    siblings, parent = form.Fields, None
    for part in parts[:-1]:
        found = next((k for k in siblings if isinstance(k, pikepdf.Dictionary)
                      and _text(k.get("/T")) == part), None)
        if found is None:
            found = pdf.make_indirect(pikepdf.Dictionary(T=pikepdf.String(part),
                                                         Kids=pikepdf.Array()))
            if parent is not None:
                found.Parent = parent
            siblings.append(found)
        elif "/FT" in found or "/Kids" not in found or \
                any("/T" not in k for k in found.Kids):
            raise DuplicateFieldNameError("numele e deja al unui camp", name=name)
        parent, siblings = found, found.Kids
    node.T = pikepdf.String(parts[-1])
    if parent is not None:
        node.Parent = parent
    siblings.append(node)


def _set(obj: pikepdf.Object, key: str, value: Any) -> None:
    if value is None:
        if key in obj:
            del obj[key]
    else:
        obj[key] = value


def _write_field(pdf: pikepdf.Pdf, node: pikepdf.Object, data: FormFieldData) -> None:
    """Proprietatile de camp (H-030…H-036) in dictionarul campului."""
    kind = data.field_type
    flags = int(node.get("/Ff", 0)) & ~_MANAGED_FLAGS
    flags |= (FF_READONLY if data.is_readonly else 0)
    if kind != FormFieldType.BUTTON:
        flags |= FF_REQUIRED if data.is_required else 0
    ft = {FormFieldType.TEXT: "/Tx", FormFieldType.CHECKBOX: "/Btn",
          FormFieldType.RADIO: "/Btn", FormFieldType.BUTTON: "/Btn",
          FormFieldType.DROPDOWN: "/Ch", FormFieldType.LISTBOX: "/Ch",
          FormFieldType.SIGNATURE: "/Sig"}[kind]
    node.FT = pikepdf.Name(ft)
    if kind == FormFieldType.TEXT and data.is_multiline:
        flags |= FF_MULTILINE
    if kind == FormFieldType.RADIO:
        flags |= FF_RADIO | FF_NO_TOGGLE_OFF
    if kind == FormFieldType.BUTTON:
        flags |= FF_PUSHBUTTON
    if kind == FormFieldType.DROPDOWN:
        flags |= FF_COMBO | (FF_EDIT if data.allow_custom else 0)
    if kind == FormFieldType.LISTBOX and data.allow_multiple:
        flags |= FF_MULTISELECT
    node.Ff = flags
    if kind != FormFieldType.RADIO:  # tooltipul grupului il scrie apelantul
        _set(node, "/TU", pikepdf.String(data.tooltip) if data.tooltip else None)
    _set(node, "/MaxLen", data.max_symbols if kind == FormFieldType.TEXT
         and data.max_symbols else None)
    if kind in (FormFieldType.DROPDOWN, FormFieldType.LISTBOX):
        opt = pikepdf.Array()
        defaults: list[str] = []
        for text, value, is_default in data.items:
            if value is not None and value != text:
                opt.append(pikepdf.Array([pikepdf.String(value), pikepdf.String(text)]))
            else:
                opt.append(pikepdf.String(text))
            if is_default:
                defaults.append(value if value is not None else text)
        node.Opt = opt
        if len(defaults) > 1 and data.allow_multiple:
            node.DV = pikepdf.Array([pikepdf.String(v) for v in defaults])
        else:
            _set(node, "/DV", pikepdf.String(defaults[0]) if defaults else None)
    if kind == FormFieldType.TEXT:
        aa = node.get("/AA")
        aa = aa if isinstance(aa, pikepdf.Dictionary) else pikepdf.Dictionary()
        for key in ("/F", "/K"):
            action = aa.get(key)
            if isinstance(action, pikepdf.Dictionary) and _DATE_SCRIPT.search(
                    _text(action.get("/JS"))):
                del aa[key]
        if data.text_format == "date":
            view = data.date_format or DEFAULT_DATE_FORMAT
            for key, fn in (("/F", "AFDate_FormatEx"), ("/K", "AFDate_KeystrokeEx")):
                aa[key] = pikepdf.Dictionary(S=pikepdf.Name.JavaScript,
                                             JS=pikepdf.String(f'{fn}("{view}");'))
        _set(node, "/AA", aa if len(aa) else None)


def _write_widget(pdf: pikepdf.Pdf, page: pikepdf.Page, widget: pikepdf.Object,
                  data: FormFieldData) -> None:
    """Pozitia si aspectul (tabul `Appearance`) in dictionarul widgetului."""
    from app.core.pdf.text import page_geometry, to_pdf_rect

    widget.Type = pikepdf.Name.Annot
    widget.Subtype = pikepdf.Name.Widget
    widget.Rect = pikepdf.Array(list(to_pdf_rect(page_geometry(page), data.rect)))
    widget.P = page.obj
    widget.F = 4  # se tipareste
    mk = widget.get("/MK")
    mk = mk if isinstance(mk, pikepdf.Dictionary) else pikepdf.Dictionary()
    _set(mk, "/BG", _color_array(data.fill_color))
    _set(mk, "/BC", _color_array(data.border_color))
    if data.field_type == FormFieldType.BUTTON:
        _set(mk, "/CA", pikepdf.String(data.value) if data.value else None)
    widget.MK = mk
    width = data.border_width if data.border_width is not None else (
        1.0 if data.border_color else 0.0)
    widget.BS = pikepdf.Dictionary(W=width, S=pikepdf.Name.S)
    check = data.field_type in (FormFieldType.CHECKBOX, FormFieldType.RADIO)
    resource = "ZaDb" if check else _font_resource(pdf, data.font_name)
    if check:
        _acroform(pdf)
    color = data.check_color if check else data.text_color
    widget.DA = pikepdf.String(f"/{resource} {_num(data.font_size or 0)} Tf "
                               + _rgb_op(color or "#000000", "rg"))


def _page_check(document: PdfDocument, data: FormFieldData) -> None:
    """H-017, H-020: campul ramane in pagina lui si are cel putin 8×8 puncte."""
    total = document.page_count
    if not 1 <= data.page_number <= total:
        raise ValueError(f"pagina {data.page_number} nu exista (1..{total})")
    from app.core.pdf.text import page_geometry

    _left, _bottom, height = page_geometry(document._pike().pages[data.page_number - 1])
    box = document._pike().pages[data.page_number - 1].mediabox
    width = abs(float(box[2]) - float(box[0]))
    r = data.rect
    if r.w < MIN_SIZE or r.h < MIN_SIZE:
        raise ValueError(f"campul are cel putin {MIN_SIZE:g}×{MIN_SIZE:g} puncte")
    if r.x < -0.01 or r.y < -0.01 or r.x + r.w > width + 0.01 or r.y + r.h > height + 0.01:
        raise ValueError("campul nu poate iesi din pagina lui")


def _find_widget(pdf: pikepdf.Pdf, widget_id: int
                 ) -> tuple[_Field, int, pikepdf.Object, int]:
    for item in _walk(pdf):
        for index, (page, widget) in enumerate(item.widgets):
            if widget.objgen[0] == widget_id:
                return item, page, widget, index
    raise KeyError(widget_id)


def _split_widget(pdf: pikepdf.Pdf, form: pikepdf.Dictionary, item: _Field
                  ) -> pikepdf.Object:
    """Un camp cu un singur widget (acelasi dictionar) devine camp-parinte cu
    widgetul ca fiu, ca sa poata primi copii legate (H-016)."""
    node = item.obj
    if "/Kids" in node:
        return node
    parent = pdf.make_indirect(pikepdf.Dictionary(Kids=pikepdf.Array([node])))
    for key in _FIELD_KEYS + ("/T", "/Parent"):
        if key in node:
            parent[key] = node[key]
            del node[key]
    if "/DA" in node:
        parent.DA = node.DA
    aa = node.get("/AA")
    if isinstance(aa, pikepdf.Dictionary):
        moved = pikepdf.Dictionary({k: aa[k] for k in _FIELD_AA if k in aa})
        for key in _FIELD_AA:
            if key in aa:
                del aa[key]
        if len(moved):
            parent.AA = moved
        if not len(aa):
            del node["/AA"]
    siblings = _siblings(form, parent)
    for i, sibling in enumerate(siblings):
        if sibling.is_indirect and sibling.objgen == node.objgen:
            siblings[i] = parent
    node.Parent = parent
    return parent


def _unlink_widget(pdf: pikepdf.Pdf, form: pikepdf.Dictionary, item: _Field,
                   widget: pikepdf.Object) -> pikepdf.Object:
    """H-016: widgetul iese din campul comun si devine camp independent, cu
    proprietatile si valoarea campului."""
    parent = item.obj
    for i in range(len(parent.Kids) - 1, -1, -1):
        if parent.Kids[i].objgen == widget.objgen:
            del parent.Kids[i]
    del widget["/Parent"]
    for key in _FIELD_KEYS:
        value = _inherited(parent, key)
        if value is not None:
            widget[key] = value
    aa = parent.get("/AA")
    if isinstance(aa, pikepdf.Dictionary):
        own = widget.get("/AA") or pikepdf.Dictionary()
        for key in _FIELD_AA:
            if key in aa:
                own[key] = aa[key]
        if len(own):
            widget.AA = own
    return widget


def _copy_name(name: str, taken: set[str]) -> str:
    """H-015: numele copiei se incrementeaza (`TextField 3` → `TextField 4`,
    `nume` → `nume 1`)."""
    match = re.match(r"^(.*?)(\d+)$", name)
    base, n = (match.group(1), int(match.group(2))) if match else (name + " ", 0)
    while True:
        n += 1
        candidate = f"{base}{n}"
        if candidate not in taken:
            return candidate


# --- FormEditor -----------------------------------------------------------------------


# H-001…H-058 (SPEC_05: FormEditor)
class FormEditor:
    """Campurile de formular ale unui `PdfDocument`."""

    def __init__(self, document: PdfDocument) -> None:
        self.document = document

    # --- citirea (H-001) ---

    def _fields(self) -> list[_Field]:
        return _walk(self.document._pike())

    def fields(self, page: int | None = None) -> list[FormFieldData]:
        pdf = self.document._pike()
        out: list[FormFieldData] = []
        for item in _walk(pdf):
            for index, (number, widget) in enumerate(item.widgets):
                if page is None or number == page:
                    out.append(_to_data(pdf, item, number, widget, index))
        return out

    def has_fields(self) -> bool:
        """H-001: documentul are campuri interactive."""
        return any(item.widgets for item in self._fields())

    def field(self, name: str) -> FormFieldData:
        """Primul widget al campului `name` (sau butonul radio cu acest nume)."""
        for data in self.fields():
            if data.field_name == name or data.group_name == name:
                return data
        raise KeyError(name)

    def _find(self, name: str) -> tuple[_Field, str | None]:
        """Campul cu numele dat; pentru un buton radio, si numele butonului."""
        fields = self._fields()
        for item in fields:
            if item.name == name and item.widgets:
                return item, None
        for item in fields:
            if item.kind == FormFieldType.RADIO:
                for _page, widget in item.widgets:
                    if _on_state(widget) == name:
                        return item, name
        raise KeyError(name)

    # --- completarea (H-030…H-036) ---

    def _value_for(self, item: _Field, data: FormFieldData, value: str,
                   button: str | None) -> pikepdf.Object | None:
        kind = data.field_type
        if kind in (FormFieldType.BUTTON, FormFieldType.SIGNATURE):
            raise ValueError(f"campul {item.name!r} nu primeste o valoare")
        if kind == FormFieldType.CHECKBOX:
            on = _on_state(item.widgets[0][1]) or "Yes"
            checked = value == on or value.strip().lower() not in _EMPTY_WORDS
            return pikepdf.Name("/" + (on if checked else OFF))
        if kind == FormFieldType.RADIO:
            states = {_on_state(w) for _p, w in item.widgets} - {None}
            choice = button or value
            if choice not in states:
                if choice.strip().lower() in _EMPTY_WORDS:
                    return pikepdf.Name("/" + OFF)
                raise ValueError(f"grupul {item.name!r} nu are butonul {choice!r}")
            return pikepdf.Name("/" + choice)
        if kind == FormFieldType.TEXT:
            if data.text_format == "date" and value.strip():
                value = format_date(value, data.date_format or DEFAULT_DATE_FORMAT)
            if data.max_symbols is not None and len(value) > data.max_symbols:
                raise ValueError(f"campul {item.name!r} primeste cel mult "
                                 f"{data.max_symbols} caractere")
            return pikepdf.String(value) if value else None
        # liste (H-031, H-036)
        exports = {(v if v is not None else t) for t, v, _d in data.items}
        by_text = {t: (v if v is not None else t) for t, v, _d in data.items}
        multiple = kind == FormFieldType.LISTBOX and data.allow_multiple
        chosen = [p for p in value.split("\n") if p] if multiple else (
            [value] if value else [])
        resolved: list[str] = []
        for part in chosen:
            if part in exports:
                resolved.append(part)
            elif part in by_text:
                resolved.append(by_text[part])
            elif kind == FormFieldType.DROPDOWN and data.allow_custom:
                resolved.append(part)
            else:
                raise ValueError(f"lista {item.name!r} nu are elementul {part!r}")
        if not resolved:
            return None
        if len(resolved) == 1:
            return pikepdf.String(resolved[0])
        return pikepdf.Array([pikepdf.String(v) for v in resolved])

    def _store(self, item: _Field, value: pikepdf.Object | None) -> None:
        if value is None:
            if "/V" in item.obj:
                del item.obj["/V"]
        else:
            item.obj.V = value
        if item.kind == FormFieldType.LISTBOX:
            if value is not None:
                item.obj.I = _list_indices(item, value)
            elif "/I" in item.obj:
                del item.obj["/I"]
        self._refresh(item)

    def _refresh(self, item: _Field, *, redraw: bool = False) -> None:
        pdf = self.document._pike()
        for index, (page, widget) in enumerate(item.widgets):
            _write_appearance(pdf, item, widget, _to_data(pdf, item, page, widget, index),
                              redraw=redraw)

    def set_value(self, name: str, value: str) -> None:
        """H-030…H-036: respecta `Read-Only` si `Max Number of Symbols`; data se
        reduce la formatul din `View`. Pentru un buton radio, `name` e grupul
        (cu numele butonului in `value`) sau chiar butonul."""
        item, button = self._find(name)
        data = _to_data(self.document._pike(), item, *item.widgets[0], 0)
        if data.is_readonly:
            raise ValueError(f"campul {item.name!r} e doar pentru citire")
        self._store(item, self._value_for(item, data, value, button))
        self.document._changed()

    def value(self, name: str) -> str | None:
        """Valoarea campului; pentru un buton radio dat prin nume, numele lui daca
        e ales, altfel `Off`."""
        item, button = self._find(name)
        data = _to_data(self.document._pike(), item, *item.widgets[0], 0)
        if button is not None:
            return button if _text(item.get("/V")) == button else OFF
        if data.field_type == FormFieldType.RADIO:
            return _text(item.get("/V")) or OFF
        return data.value

    # --- golirea si campurile obligatorii (H-005, H-022, H-023) ---

    def reset(self) -> None:
        """H-005: toate campurile se golesc; valoarea implicita (elementul implicit
        al listei, bifa activa implicit) revine."""
        for item in self._fields():
            if item.kind in (FormFieldType.BUTTON, FormFieldType.SIGNATURE):
                continue
            default = item.get("/DV")
            if default is not None:
                item.obj.V = default
            elif "/V" in item.obj:
                del item.obj["/V"]
            if "/I" in item.obj:
                del item.obj["/I"]
            if item.kind == FormFieldType.LISTBOX and default is not None:
                item.obj.I = _list_indices(item, default)
            self._refresh(item)
        self.document._changed()

    def incomplete_required(self) -> list[FormFieldData]:
        """H-022, H-023: campurile obligatorii necompletate (unul per camp). **Doar
        pentru avertisment: nu blocheaza salvarea, trimiterea sau tiparirea.**"""
        pdf = self.document._pike()
        out: list[FormFieldData] = []
        for item in _walk(pdf):
            if not item.widgets or item.kind == FormFieldType.BUTTON:
                continue
            if not item.flags & FF_REQUIRED:
                continue
            value = item.get("/V")
            if value is None or _text(value) in ("", OFF):
                out.append(_to_data(pdf, item, *item.widgets[0], 0))
        return out

    # --- datele de formular (H-003, H-004) ---

    def load_data(self, path: Path) -> tuple[int, list[str]]:
        """H-003: valorile dintr-un fisier FDF sau XFDF. Intoarce (campuri
        completate, campuri necunoscute sau cu valori nepotrivite, ignorate)."""
        raw = Path(path).read_bytes()
        if raw.lstrip()[:5] == b"%FDF-":
            fdf, root = _open_fdf(raw)
            with fdf:
                pairs = list(_fdf_values(root.get("/Fields")))
        else:
            if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                raise UnsupportedFormatError("XFDF cu DOCTYPE nu se citeste")
            try:
                xml_root = ET.fromstring(raw)
            except ET.ParseError as exc:
                raise FileCorruptError("fisierul XFDF nu se poate citi") from exc
            if xml_root.tag.rsplit("}", 1)[-1] != "xfdf":
                raise UnsupportedFormatError("se asteapta un fisier FDF sau XFDF")
            node = next((c for c in xml_root if c.tag.rsplit("}", 1)[-1] == "fields"), None)
            pairs = list(_xfdf_values(node)) if node is not None else []
        pdf = self.document._pike()
        known = {item.name: item for item in _walk(pdf) if item.widgets}
        filled, ignored = 0, []
        for name, value in pairs:
            item = known.get(name)
            if item is None or item.kind in (FormFieldType.BUTTON, FormFieldType.SIGNATURE):
                ignored.append(name)
                continue
            data = _to_data(pdf, item, *item.widgets[0], 0)
            try:
                self._store(item, self._value_for(item, data, value, None))
            except ValueError:
                ignored.append(name)
                continue
            filled += 1
        if filled:
            self.document._changed()
        return filled, ignored

    def _data_values(self) -> list[tuple[str, str, bool]]:
        """(nume, valoare, e nume PDF) pentru campurile care pot avea valoare."""
        out: list[tuple[str, str, bool]] = []
        for item in self._fields():
            if not item.widgets or item.kind in (FormFieldType.BUTTON,
                                                 FormFieldType.SIGNATURE):
                continue
            value = item.get("/V")
            is_name = isinstance(value, pikepdf.Name) or item.kind in (
                FormFieldType.CHECKBOX, FormFieldType.RADIO)
            out.append((item.name, _text(value), is_name))
        return out

    def save_data(self, path: Path, fmt: str = "fdf") -> None:
        """H-004: valorile campurilor in FDF, XFDF sau HTML."""
        fmt = fmt.lower()
        if fmt not in DATA_FORMATS:
            raise UnsupportedFormatError(f"format de date necunoscut: {fmt}")
        values = self._data_values()
        source = self.document.path.name if self.document.path else ""
        if fmt == "fdf":
            entries = []
            for name, value, is_name in values:
                if is_name:
                    v = bytes(pikepdf.Name("/" + (value or OFF)).unparse()).decode("latin-1")
                elif "\n" in value:
                    v = "[" + " ".join(_pdf_literal(p) for p in value.split("\n")) + "]"
                else:
                    v = _pdf_literal(value)
                entries.append(f"<< /T {_pdf_literal(name)} /V {v} >>")
            file_entry = f"/F {_pdf_literal(source)} " if source else ""
            text = ("%FDF-1.2\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /FDF << " + file_entry
                    + "/Fields [\n" + "\n".join(entries) + "\n] >> >>\nendobj\n"
                    "trailer\n<< /Root 1 0 R >>\n%%EOF\n")
            Path(path).write_bytes(text.encode("latin-1"))
            return
        if fmt == "xfdf":
            root = ET.Element("xfdf", {"xmlns": XFDF_NS, "xml:space": "preserve"})
            fields_node = ET.SubElement(root, "fields")
            for name, value, _is_name in values:
                node = fields_node
                for partial in name.split("."):
                    found = next((c for c in node if c.get("name") == partial), None)
                    node = found if found is not None else ET.SubElement(
                        node, "field", {"name": partial})
                for part in value.split("\n") if value else [""]:
                    ET.SubElement(node, "value").text = part
            if source:
                ET.SubElement(root, "f", {"href": source})
            Path(path).write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
            return
        rows = "\n".join(
            f"<tr><th>{html.escape(name)}</th><td>"
            f"{html.escape(value).replace(chr(10), '<br>')}</td></tr>"
            for name, value, _is_name in values)
        page = ("<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
                f"<title>{html.escape(source)}</title></head>\n<body><table>\n{rows}\n"
                "</table></body></html>\n")
        Path(path).write_text(page, encoding="utf-8")

    # --- crearea si modificarea (H-012…H-021, H-030…H-036, H-109) ---

    def _names(self) -> set[str]:
        """Toate numele folosite: campuri, grupuri si butoane radio, parinti."""
        names: set[str] = set()
        for item in self._fields():
            names.add(item.name)
            parts = item.name.split(".")
            names.update(".".join(parts[:i]) for i in range(1, len(parts)))
            if item.kind == FormFieldType.RADIO:
                names.update(s for s in (_on_state(w) for _p, w in item.widgets) if s)
        return names

    def validate_field_name(self, name: str, *, current: str | None = None) -> None:
        """H-030: nevid, unic, fara punct la inceput, la sfarsit sau dublat.
        Erori: `InvalidFieldNameError`, `DuplicateFieldNameError`."""
        _check_name(name)
        if name != current and name in self._names():
            raise DuplicateFieldNameError("exista deja un camp cu acest nume", name=name)

    def next_name(self, kind: FormFieldType, *, group: bool = False) -> str:
        """H-109: primul nume liber de forma `TextField 3`."""
        base = RADIO_GROUP_NAME if group else AUTO_NAMES[FormFieldType(kind)]
        taken = self._names()
        n = 1
        while f"{base} {n}" in taken:
            n += 1
        return f"{base} {n}"

    def create_field(self, data: FormFieldData) -> FormFieldData:
        """H-012, H-013, H-030…H-036: campul nou. Fara nume, primeste unul generat
        (H-109); un buton radio intra in grupul `group_name` (nou sau existent)."""
        kind = FormFieldType(data.field_type)
        _page_check(self.document, data)
        name = data.field_name or self.next_name(kind)
        self.validate_field_name(name)
        pdf = self.document._pike()
        form = _acroform(pdf)
        page = pdf.pages[data.page_number - 1]
        data = replace(data, field_name=name, field_type=kind)
        widget = pdf.make_indirect(pikepdf.Dictionary())
        _write_widget(pdf, page, widget, data)
        if kind == FormFieldType.RADIO:
            group_name = data.group_name or self.next_name(kind, group=True)
            group = next((i for i in self._fields() if i.name == group_name), None)
            if group is None:
                _check_name(group_name)
                if group_name in self._names():
                    raise DuplicateFieldNameError("numele grupului e deja folosit",
                                                  name=group_name)
                node = pdf.make_indirect(pikepdf.Dictionary(Kids=pikepdf.Array()))
                _write_field(pdf, node, data)
                _set(node, "/TU", pikepdf.String(data.tooltip) if data.tooltip else None)
                _attach(pdf, form, group_name, node)
            elif group.kind != FormFieldType.RADIO:
                raise DuplicateFieldNameError("numele e al unui camp care nu e grup radio",
                                              name=group_name)
            else:
                node = group.obj
            node.Kids.append(widget)
            widget.Parent = node
            item = _Field(group_name, node, [(data.page_number, widget)])
            _write_appearance(pdf, item, widget, data, redraw=True)
            if _is_on(data.value):
                node.DV = pikepdf.Name("/" + name)
                node.V = node.DV
                widget.AS = node.V
        else:
            _write_field(pdf, widget, data)
            _attach(pdf, form, name, widget)
            if kind == FormFieldType.CHECKBOX and _is_on(data.value):
                widget.DV = pikepdf.Name("/Yes")
                widget.V = widget.DV
            elif kind in (FormFieldType.DROPDOWN, FormFieldType.LISTBOX) and "/DV" in widget:
                widget.V = widget.DV
            item = _Field(name, widget, [(data.page_number, widget)])
            _write_appearance(pdf, item, widget, data, redraw=True)
        if "/Annots" not in page.obj:
            page.obj.Annots = pdf.make_indirect(pikepdf.Array())
        page.obj.Annots.append(widget)
        self.document._changed()
        return self._read(widget.objgen[0])

    def _read(self, widget_id: int) -> FormFieldData:
        pdf = self.document._pike()
        item, page, widget, index = _find_widget(pdf, widget_id)
        return _to_data(pdf, item, page, widget, index)

    def default_on(self, data: FormFieldData) -> bool:
        """H-032, H-033: `Enabled by Default` (valoarea implicita a bifei sau a
        butonului radio)."""
        item, _page, widget, _index = _find_widget(self.document._pike(), int(data.id or 0))
        default = _text(item.get("/DV"))
        return bool(default) and default == _on_state(widget)

    def update_field(self, data: FormFieldData) -> FormFieldData:
        """H-014, H-016, H-017, H-019, H-020, H-030…H-036: proprietatile noi ale
        widgetului `data.id`. Pentru bife si butoane radio, `value` inseamna
        `Enabled by Default` (decizia 4). Redenumirea unei copii legate o face
        independenta (H-016)."""
        if data.id is None:
            raise ValueError("campul nu are id")
        pdf = self.document._pike()
        form = _acroform(pdf)
        item, page, widget, index = _find_widget(pdf, data.id)
        old = _to_data(pdf, item, page, widget, index)
        kind = old.field_type
        data = replace(data, field_type=kind)
        if data.page_number != page:
            raise ValueError("campul nu se poate muta pe alta pagina (H-017)")
        _page_check(self.document, data)
        pdf_page = pdf.pages[page - 1]
        if kind == FormFieldType.RADIO:
            self._update_radio(pdf, form, item, widget, old, data)
        else:
            if data.field_name != old.field_name:
                self.validate_field_name(data.field_name, current=old.field_name)
                if len(item.widgets) > 1:
                    node = _unlink_widget(pdf, form, item, widget)
                else:
                    node = item.obj
                    _detach(form, node)
                _attach(pdf, form, data.field_name, node)
                item = _Field(data.field_name, node, [(page, widget)])
            _write_field(pdf, item.obj, data)
            if kind == FormFieldType.CHECKBOX:
                on = _on_state(widget) or "Yes"
                _set(item.obj, "/DV", pikepdf.Name("/" + on) if _is_on(data.value)
                     else None)
            for _p, other in item.widgets:
                if other.objgen != widget.objgen:  # copiile legate: acelasi stil de camp
                    other_data = _to_data(pdf, item, _p, other, 1)
                    _write_widget(pdf, pdf.pages[_p - 1], other, replace(
                        data, rect=other_data.rect, page_number=_p))
        _write_widget(pdf, pdf_page, widget, data)
        item = next(i for i in _walk(pdf) if any(w.objgen == widget.objgen
                                                  for _p, w in i.widgets))
        self._refresh(item, redraw=True)
        self.document._changed()
        return self._read(data.id)

    def _update_radio(self, pdf: pikepdf.Pdf, form: pikepdf.Dictionary, item: _Field,
                      widget: pikepdf.Object, old: FormFieldData,
                      data: FormFieldData) -> None:
        """H-033: numele butonului, grupul (nou sau existent), tooltipul grupului."""
        selected = _text(item.get("/V")) == old.field_name
        default = _text(item.get("/DV")) == old.field_name
        if data.field_name != old.field_name:
            self.validate_field_name(data.field_name, current=old.field_name)
        group_name = data.group_name or old.group_name or item.name
        node = item.obj
        if group_name != item.name:
            target = next((i for i in self._fields() if i.name == group_name), None)
            if target is not None and target.kind != FormFieldType.RADIO:
                raise DuplicateFieldNameError("numele e al unui camp care nu e grup radio",
                                              name=group_name)
            for i in range(len(node.Kids) - 1, -1, -1):
                if node.Kids[i].objgen == widget.objgen:
                    del node.Kids[i]
            if not len(node.Kids):
                _detach(form, node)
            elif selected:
                del node["/V"]
            if target is None:
                self.validate_field_name(group_name)
                new = pdf.make_indirect(pikepdf.Dictionary(Kids=pikepdf.Array()))
                _attach(pdf, form, group_name, new)
                node = new
            else:
                node = target.obj
            node.Kids.append(widget)
            widget.Parent = node
        _write_field(pdf, node, data)
        _set(node, "/TU", pikepdf.String(data.tooltip) if data.tooltip else None)
        # starea „pornit” poarta numele butonului
        ap = widget.get("/AP")
        if isinstance(ap, pikepdf.Dictionary):
            del widget["/AP"]
        if _is_on(data.value):
            node.DV = pikepdf.Name("/" + data.field_name)
        elif default or _text(node.get("/DV")) == old.field_name:
            _set(node, "/DV", None)
        if selected:
            node.V = pikepdf.Name("/" + data.field_name)
        group = _Field(group_name, node, [(data.page_number, widget)])
        _write_appearance(pdf, group, widget, data, redraw=True)

    def _remove_widgets(self, widgets: Sequence[pikepdf.Object]) -> None:
        pdf = self.document._pike()
        form = _acroform(pdf)
        doomed = {w.objgen for w in widgets}
        for page in pdf.pages:
            annots = page.obj.get("/Annots")
            if annots is None:
                continue
            for i in range(len(annots) - 1, -1, -1):
                if annots[i].is_indirect and annots[i].objgen in doomed:
                    del annots[i]
        for widget in widgets:
            parent = widget.get("/Parent")
            if isinstance(parent, pikepdf.Dictionary) and "/T" not in widget:
                # widget al unui camp cu mai multe widgeturi (copii legate, radio)
                for i in range(len(parent.Kids) - 1, -1, -1):
                    if parent.Kids[i].objgen == widget.objgen:
                        del parent.Kids[i]
                if not len(parent.Kids):
                    _detach(form, parent)
                elif _text(parent.get("/V")) == _on_state(widget):
                    del parent["/V"]
            else:
                _detach(form, widget)
        self.document._changed()

    def delete_fields(self, names: Sequence[str]) -> None:
        """H-021: campurile cu numele date, cu toate copiile lor legate; un nume
        de buton radio sterge numai butonul."""
        widgets: list[pikepdf.Object] = []
        for name in names:
            item, button = self._find(name)
            widgets.extend(w for _p, w in item.widgets
                           if button is None or _on_state(w) == button)
        self._remove_widgets(widgets)

    def delete_widgets(self, ids: Sequence[int]) -> None:
        """H-021: widgeturile selectate (o copie legata se sterge singura)."""
        pdf = self.document._pike()
        self._remove_widgets([_find_widget(pdf, i)[2] for i in ids])

    def _shifted(self, data: FormFieldData, page: int | None,
                 at: tuple[float, float] | None) -> FormFieldData:
        from app.core.pdf.text import page_geometry

        number = page or data.page_number
        pdf_page = self.document._pike().pages[number - 1]
        _left, _bottom, height = page_geometry(pdf_page)
        width = abs(float(pdf_page.mediabox[2]) - float(pdf_page.mediabox[0]))
        x, y = at if at is not None else (data.rect.x + PASTE_OFFSET,
                                          data.rect.y + PASTE_OFFSET)
        x = max(0.0, min(x, width - data.rect.w))
        y = max(0.0, min(y, height - data.rect.h))
        return replace(data, page_number=number, rect=Rect(x, y, data.rect.w, data.rect.h))

    def copy_field(self, name: str, *, page: int | None = None,
                   at: tuple[float, float] | None = None) -> FormFieldData:
        """H-015: copia pastreaza toate proprietatile in afara numelui, care se
        incrementeaza. Numai campurile de semnatura goale se pot copia
        (`SignedFieldCopyError`)."""
        data = self.field(name)
        if data.field_type == FormFieldType.SIGNATURE and data.value:
            raise SignedFieldCopyError("campul de semnatura e semnat", name=name)
        if data.field_type in (FormFieldType.CHECKBOX, FormFieldType.RADIO):
            data = replace(data, value="Yes" if self.default_on(data) else None)
        elif data.field_type != FormFieldType.BUTTON:
            data = replace(data, value=None)
        new = replace(self._shifted(data, page, at), id=None,
                      field_name=_copy_name(data.field_name, self._names()),
                      linked_to=None)
        return self.create_field(new)

    def create_linked_copy(self, name: str, *, page: int | None = None,
                           at: tuple[float, float] | None = None) -> FormFieldData:
        """H-016: copia are acelasi nume si aceeasi valoare (un widget nou al
        aceluiasi camp)."""
        item, button = self._find(name)
        if item.kind == FormFieldType.RADIO or button is not None:
            raise ValueError("butoanele radio nu au copii legate")
        pdf = self.document._pike()
        form = _acroform(pdf)
        data = _to_data(pdf, item, *item.widgets[0], 0)
        target = self._shifted(data, page, at)
        _page_check(self.document, target)
        parent = _split_widget(pdf, form, item)
        widget = pdf.make_indirect(pikepdf.Dictionary(Parent=parent))
        pdf_page = pdf.pages[target.page_number - 1]
        _write_widget(pdf, pdf_page, widget, target)
        source = item.widgets[0][1]
        for key in ("/AA", "/Q"):
            if key in source:
                widget[key] = source[key]
        parent.Kids.append(widget)
        if "/Annots" not in pdf_page.obj:
            pdf_page.obj.Annots = pdf.make_indirect(pikepdf.Array())
        pdf_page.obj.Annots.append(widget)
        fresh = next(i for i in _walk(pdf) if i.name == item.name)
        self._refresh(fresh)
        self.document._changed()
        return self._read(widget.objgen[0])

    def move_field(self, widget_id: int, x: float, y: float) -> FormFieldData:
        """H-017, H-019: noua pozitie, numai in interiorul paginii."""
        data = self._read(widget_id)
        return self.update_field(replace(data, rect=Rect(x, y, data.rect.w, data.rect.h),
                                         value=self._value_for_update(data)))

    def resize_field(self, widget_id: int, w: float, h: float) -> FormFieldData:
        """H-020: noua marime; inaltimea (si latimea) nu pot fi sub 8 puncte."""
        data = self._read(widget_id)
        return self.update_field(replace(data, rect=Rect(data.rect.x, data.rect.y, w, h),
                                         value=self._value_for_update(data)))

    def _value_for_update(self, data: FormFieldData) -> str | None:
        if data.field_type in (FormFieldType.CHECKBOX, FormFieldType.RADIO):
            return "Yes" if self.default_on(data) else None
        return data.value

    @staticmethod
    def alignment_guides(moving: FormFieldData, others: Sequence[FormFieldData]
                         ) -> list[tuple[str, float]]:
        """H-018: ghidajele apar la X sau Y identice (marginile stanga, dreapta,
        sus, jos ale campului mutat fata de ale celorlalte de pe pagina)."""
        mine_x = (moving.rect.x, moving.rect.x + moving.rect.w)
        mine_y = (moving.rect.y, moving.rect.y + moving.rect.h)
        guides: list[tuple[str, float]] = []
        for other in others:
            if other.id == moving.id or other.page_number != moving.page_number:
                continue
            for axis, mine, theirs in (
                    ("x", mine_x, (other.rect.x, other.rect.x + other.rect.w)),
                    ("y", mine_y, (other.rect.y, other.rect.y + other.rect.h))):
                for value in theirs:
                    if any(abs(value - m) <= GUIDE_TOLERANCE for m in mine) and \
                            (axis, round(value, 2)) not in guides:
                        guides.append((axis, round(value, 2)))
        return guides

    def validate_document(self) -> list[CoreError]:
        """H-013: verificarile pe tot formularul; `OrphanRadioButtonError` pentru
        grupurile radio cu un singur buton."""
        problems: list[CoreError] = []
        for item in self._fields():
            if item.kind == FormFieldType.RADIO and len(item.widgets) < 2:
                problems.append(OrphanRadioButtonError(
                    "grupul radio are un singur buton", group=item.name))
        return problems
