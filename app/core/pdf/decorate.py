"""Antete si subsoluri, filigrane (faza 9, pasul 9.2): F-039…F-050, Z-001…Z-012.

Textul se scrie in continutul paginii, cu fontul incorporat (subset), marcat ca
artefact de paginare, cum fac si alte programe:
`/Artifact <</Type /Pagination /Subtype /Header>> BDC ... EMC` (sau `/Footer`,
`/Watermark`). Asa filigranele se recunosc si se sterg toate (F-050): cele puse de
DocuLens, cele marcate la fel de alte programe, adnotarile `/Watermark` si
formele marcate de Acrobat ca filigran (`/PieceInfo` cu `Watermark`).

Pozitiile si distantele se masoara pe pagina asa cum se vede (cu rotatia ei);
originea e coltul stanga-jos al paginii vizibile (CropBox).

Continutul antetului (F-040) poate combina text liber cu `{page}` (numarul
paginii), `{pages}` (numarul total), `{bates}` (numarul Bates), `{date}`, `{time}`
si etichetele de data `<d/>`, `<date/>`, `<t12/>`, `<t24/>`, `<time/>`, cu cod de
regiune sau format propriu (Z-001…Z-012, `app/core/datetags.py`).
"""

from __future__ import annotations

import math
import sqlite3
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.applog import get_logger

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

_log = get_logger("pdf.decorate")

HEADER_POSITIONS = ("top_left", "top_center", "top_right",
                    "bottom_left", "bottom_center", "bottom_right")
"""F-039: cele sase pozitii (si valorile din SPEC_04 `header_footer_template`)."""
WATERMARK_POSITIONS = ("top_left", "top_center", "top_right", "middle_left", "center",
                       "middle_right", "bottom_left", "bottom_center", "bottom_right")
"""F-045: cele noua pozitii."""
UNITS = {"cm": 72 / 2.54, "in": 72.0, "pt": 1.0}
"""F-039: unitatile distantei de margine."""
APPLY_TO = ("all", "range", "odd", "even")
"""F-042: `All` / `Page range` / `Odd Pages` / `Even Pages`."""


@dataclass
class HeaderFooter:
    """Un antet sau subsol (si sablonul lui, F-043)."""

    position: str = "bottom_center"
    content: str = "{page}"
    margin: float = 1.0
    margin_unit: str = "cm"
    font_name: str | None = None
    font_size: float = 10.0
    text_color: str = "#000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    bates_start: int | None = None
    bates_digits: int = 6

    def validate(self) -> None:
        if self.position not in HEADER_POSITIONS:
            raise ValueError(f"pozitie necunoscuta: {self.position} ({HEADER_POSITIONS})")
        if self.margin_unit not in UNITS:
            raise ValueError(f"unitate necunoscuta: {self.margin_unit} ({tuple(UNITS)})")
        if self.margin < 0:
            raise ValueError("distanta de margine nu poate fi negativa")
        if not 1 <= self.font_size <= 1638:
            raise ValueError("dimensiunea fontului e intre 1 si 1638 pt")
        if not self.content.strip():
            raise ValueError("antetul nu are continut")
        if self.bates_start is not None and self.bates_start < 0:
            raise ValueError("numarul Bates incepe de la 0")
        if not 1 <= self.bates_digits <= 10:
            raise ValueError("numarul Bates are intre 1 si 10 cifre")


@dataclass
class Watermark:
    """F-045…F-048: filigran text sau imagine."""

    text: str | None = None
    image: Path | None = None
    position: str = "center"
    offset: tuple[float, float] = (0.0, 0.0)
    """Puncte: spre dreapta si in jos."""
    rotation: float = 45.0
    """Grade, in sens trigonometric."""
    opacity: float = 0.3
    """1 - transparenta (F-046)."""
    behind_content: bool = False
    """F-047: `In the background beneath page content`."""
    font_name: str | None = None
    font_size: float = 60.0
    text_color: str = "#808080"
    image_scale: float = 0.5
    """Latimea imaginii, ca parte din latimea paginii."""

    def validate(self) -> None:
        if bool(self.text and self.text.strip()) == bool(self.image):
            raise ValueError("filigranul are fie text, fie imagine")
        if self.position not in WATERMARK_POSITIONS:
            raise ValueError(f"pozitie necunoscuta: {self.position}")
        if not 0 <= self.opacity <= 1:
            raise ValueError("opacitatea e intre 0 si 1")
        if not 1 <= self.font_size <= 1638:
            raise ValueError("dimensiunea fontului e intre 1 si 1638 pt")
        if not 0 < self.image_scale <= 1:
            raise ValueError("marimea imaginii e intre 0 si 1 din latimea paginii")


# --- geometria paginii vizibile ------------------------------------------------------------


@dataclass(frozen=True)
class _View:
    width: float
    height: float
    matrix: tuple[float, float, float, float, float, float]
    """Din coordonatele paginii vizibile in coordonatele PDF ale paginii."""


def _view(page: pikepdf.Page) -> _View:
    from app.core.pdf.organize import _inherited

    x0, y0, x1, y1 = (float(v) for v in page.cropbox)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    w, h = x1 - x0, y1 - y0
    rotation = int(_inherited(page.obj, "/Rotate") or 0) % 360
    if rotation == 90:
        return _View(h, w, (0, 1, -1, 0, x1, y0))
    if rotation == 180:
        return _View(w, h, (-1, 0, 0, -1, x1, y1))
    if rotation == 270:
        return _View(h, w, (0, -1, 1, 0, x0, y1))
    return _View(w, h, (1, 0, 0, 1, x0, y0))


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"culoare invalida: #{color}")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _artifact(kind: str, body: str) -> str:
    return f"/Artifact <</Type /Pagination /Subtype /{kind}>> BDC {body} EMC"


def _add(pdf: pikepdf.Pdf, page: pikepdf.Page, body: str, *, behind: bool) -> None:
    """Continutul nou, izolat (q ... Q): sub continutul paginii sau deasupra lui."""
    stream = pdf.make_stream(body.encode("latin-1"))
    if behind:
        page.contents_add(stream, prepend=True)
    else:
        page.contents_add(pdf.make_stream(b"q"), prepend=True)
        page.contents_add(pdf.make_stream(b"Q"))
        page.contents_add(stream)


def _font_for(pdf: pikepdf.Pdf, texts: Sequence[str], name: str | None, bold: bool,
              italic: bool) -> tuple[Any, bool, bool]:
    """Fontul incorporat; (font, bold simulat, italic simulat). Fara fontul cerut
    se foloseste cel implicit, cu nota in jurnal (F-006)."""
    from app.core.fonts import font_file
    from app.core.pdf.embedded_font import embed_text_font

    path = None
    fake_bold, fake_italic = bold, italic
    if name:
        path = font_file(name, bold=bold, italic=italic)
        if path is None:
            _log.info("fontul %s nu e instalat ca TrueType; se foloseste cel implicit", name)
        else:
            style = path.stem.casefold()
            fake_bold = bold and "bold" not in style and "bd" not in style
            fake_italic = italic and "italic" not in style and "oblique" not in style
    return embed_text_font(pdf, texts, font_path=path), fake_bold, fake_italic


def _text_ops(resource: str, font: Any, text: str, size: float, x: float, y: float,
              color: str, *, bold: bool, italic: bool, underline: bool) -> str:
    r, g, b = _rgb(color)
    skew = 0.21 if italic else 0
    ops = [f"{_num(r)} {_num(g)} {_num(b)} rg {_num(r)} {_num(g)} {_num(b)} RG"]
    mode = f"2 Tr {_num(size * 0.03)} w " if bold else ""
    ops.append(f"BT {mode}{resource} {_num(size)} Tf 1 0 {_num(skew)} 1 {_num(x)} {_num(y)} "
               f"Tm {font.encode(text)} Tj ET")
    if underline:
        width = font.width(text, size)
        line_y = y - size * 0.12
        ops.append(f"{_num(max(size * 0.05, 0.5))} w {_num(x)} {_num(line_y)} m "
                   f"{_num(x + width)} {_num(line_y)} l S")
    return " ".join(ops)


# --- F-039…F-042: antet si subsol ------------------------------------------------------------


def expand_content(content: str, *, page: int, pages: int, bates: int | None,
                   bates_digits: int = 6, moment: datetime | None = None,
                   region: str | None = None) -> str:
    """F-040: variabilele si etichetele de data (Z-001…Z-012) inlocuite."""
    from app.core import datetags

    text = content.replace("{page}", str(page)).replace("{pages}", str(pages))
    text = text.replace("{bates}", "" if bates is None else str(bates).zfill(bates_digits))
    text = text.replace("{date}", "<d/>").replace("{time}", "<time/>")
    return datetags.expand(text, moment, region=region)


def add_header_footer(document: PdfDocument, hf: HeaderFooter, *,
                      pages: Sequence[int] | None = None, moment: datetime | None = None,
                      region: str | None = None) -> int | None:
    """F-039…F-042: antetul sau subsolul pe paginile alese (None = toate).
    Intoarce urmatorul numar Bates (pentru `Continue from`), sau None."""
    hf.validate()
    total = document.page_count
    chosen = list(range(1, total + 1)) if pages is None else sorted(set(pages))
    document._check_pages(chosen)
    moment = moment or datetime.now()
    texts: dict[int, str] = {}
    bates = hf.bates_start
    for n in chosen:
        texts[n] = expand_content(hf.content, page=n, pages=total, bates=bates,
                                  bates_digits=hf.bates_digits, moment=moment, region=region)
        if bates is not None:
            bates += 1
    pdf = document._pike()
    font, fake_bold, fake_italic = _font_for(pdf, list(texts.values()), hf.font_name,
                                             hf.bold, hf.italic)
    margin = hf.margin * UNITS[hf.margin_unit]
    size = hf.font_size
    kind = "Header" if hf.position.startswith("top") else "Footer"
    for n, text in texts.items():
        page = pdf.pages[n - 1]
        view = _view(page)
        width = font.width(text, size)
        horizontal = hf.position.split("_")[1]
        x = {"left": margin, "center": (view.width - width) / 2,
             "right": view.width - margin - width}[horizontal]
        if kind == "Header":
            y = view.height - margin - size * font.ascent / 1000
        else:
            y = margin + size * abs(font.descent) / 1000
        resource = page.add_resource(font.font, pikepdf.Name.Font, prefix="DLHF")
        body = _text_ops(resource, font, text, size, x, y, hf.text_color, bold=fake_bold,
                         italic=fake_italic, underline=hf.underline)
        matrix = " ".join(_num(v) for v in view.matrix)
        _add(pdf, page, _artifact(kind, f"q {matrix} cm {body} Q"), behind=False)
    document._changed()
    return bates


# --- F-045…F-049: filigranul -----------------------------------------------------------------


def _image_xobject(pdf: pikepdf.Pdf, path: Path) -> tuple[pikepdf.Stream, int, int]:
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGBA")
    width, height = image.size
    rgb = image.convert("RGB").tobytes()
    alpha = image.getchannel("A").tobytes()
    stream = pikepdf.Stream(pdf, zlib.compress(rgb), Type=pikepdf.Name.XObject,
                            Subtype=pikepdf.Name.Image, Width=width, Height=height,
                            ColorSpace=pikepdf.Name.DeviceRGB, BitsPerComponent=8,
                            Filter=pikepdf.Name.FlateDecode)
    if any(a != 255 for a in alpha):
        stream.SMask = pikepdf.Stream(pdf, zlib.compress(alpha), Type=pikepdf.Name.XObject,
                                      Subtype=pikepdf.Name.Image, Width=width, Height=height,
                                      ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=8,
                                      Filter=pikepdf.Name.FlateDecode)
    return pdf.make_indirect(stream), width, height


def _anchor(position: str, view: _View, w: float, h: float, offset: tuple[float, float]
            ) -> tuple[float, float]:
    """Centrul elementului de marime w x h, cu marginea de 36 pt (F-045)."""
    row, _, col = position.partition("_") if position != "center" else ("middle", "", "center")
    pad = 36.0
    cx = {"left": pad + w / 2, "center": view.width / 2,
          "right": view.width - pad - w / 2}[col]
    cy = {"top": view.height - pad - h / 2, "middle": view.height / 2,
          "bottom": pad + h / 2}[row]
    return cx + offset[0], cy - offset[1]


def add_watermark(document: PdfDocument, wm: Watermark, *,
                  pages: Sequence[int] | None = None) -> None:
    """F-045…F-048: filigranul pe paginile alese (None = toate). Se pot adauga
    mai multe filigrane, unul dupa altul (F-049)."""
    wm.validate()
    chosen = list(range(1, document.page_count + 1)) if pages is None else sorted(set(pages))
    document._check_pages(chosen)
    pdf = document._pike()
    angle = math.radians(wm.rotation)
    cos, sin = math.cos(angle), math.sin(angle)
    state = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.ExtGState,
                                                 CA=wm.opacity, ca=wm.opacity))
    if wm.text:
        font, _b, _i = _font_for(pdf, [wm.text], wm.font_name, False, False)
    else:
        image, img_w, img_h = _image_xobject(pdf, Path(wm.image))  # type: ignore[arg-type]
    for n in chosen:
        page = pdf.pages[n - 1]
        view = _view(page)
        gs = page.add_resource(state, pikepdf.Name.ExtGState, prefix="DLGS")
        if wm.text:
            w = font.width(wm.text, wm.font_size)
            h = wm.font_size * (font.ascent - font.descent) / 1000
        else:
            w = view.width * wm.image_scale
            h = w * img_h / img_w
        cx, cy = _anchor(wm.position, view, w, h, wm.offset)
        place = f"{_num(cos)} {_num(sin)} {_num(-sin)} {_num(cos)} {_num(cx)} {_num(cy)} cm"
        if wm.text:
            resource = page.add_resource(font.font, pikepdf.Name.Font, prefix="DLWM")
            baseline = -h / 2 + wm.font_size * abs(font.descent) / 1000
            inner = _text_ops(resource, font, wm.text, wm.font_size, -w / 2, baseline,
                              wm.text_color, bold=False, italic=False, underline=False)
        else:
            resource = page.add_resource(image, pikepdf.Name.XObject, prefix="DLWI")
            inner = f"q {_num(w)} 0 0 {_num(h)} {_num(-w / 2)} {_num(-h / 2)} cm {resource} Do Q"
        matrix = " ".join(_num(v) for v in view.matrix)
        body = f"q {matrix} cm {gs} gs {place} {inner} Q"
        _add(pdf, page, _artifact("Watermark", body), behind=wm.behind_content)
    document._changed()


# --- F-050: stergerea tuturor filigranelor ---------------------------------------------------


def _is_watermark_props(props: Any, resources: Any) -> bool:
    if isinstance(props, pikepdf.Name) and resources is not None:
        named = resources.get("/Properties")
        props = named.get(props) if named is not None else None
    return isinstance(props, pikepdf.Dictionary) and props.get("/Subtype") == "/Watermark"


def _is_watermark_form(xobject: Any) -> bool:
    piece = xobject.get("/PieceInfo") if isinstance(xobject, pikepdf.Stream) else None
    if piece is None:
        return False
    compound = piece.get("/ADBE_CompoundType")
    private = compound.get("/Private") if isinstance(compound, pikepdf.Dictionary) else None
    return private == "/Watermark"


def _strip_page(pdf: pikepdf.Pdf, page: pikepdf.Page) -> int:
    """Scoate din continutul paginii artefactele `/Watermark` si formele de
    filigran; intoarce cate s-au scos."""
    resources = page.obj.get("/Resources")
    xobjects = resources.get("/XObject") if resources is not None else None
    kept: list[Any] = []
    removed = 0
    depth = 0  # adancimea in interiorul unui filigran (BDC/BMC imbricate)
    for operands, operator in pikepdf.parse_content_stream(page):
        op = str(operator)
        if depth:
            if op in ("BDC", "BMC"):
                depth += 1
            elif op == "EMC":
                depth -= 1
            continue
        if op == "BDC" and len(operands) == 2 and operands[0] == "/Artifact" and \
                _is_watermark_props(operands[1], resources):
            depth = 1
            removed += 1
            continue
        if op == "Do" and xobjects is not None and operands and \
                _is_watermark_form(xobjects.get(operands[0])):
            removed += 1
            continue
        kept.append((operands, operator))
    if removed:
        page.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(kept))
    return removed


def remove_watermarks(document: PdfDocument) -> int:
    """F-050: sterge TOATE filigranele (din continut si adnotarile `/Watermark`),
    nu doar cele puse de DocuLens. Intoarce cate s-au sters."""
    pdf = document._pike()
    removed = 0
    for page in pdf.pages:
        removed += _strip_page(pdf, page)
        annots = page.obj.get("/Annots")
        if annots is not None:
            kept = [a for a in annots if a.get("/Subtype") != "/Watermark"]
            if len(kept) != len(annots):
                removed += len(annots) - len(kept)
                page.obj.Annots = pikepdf.Array(kept)
    if removed:
        document._changed()
    return removed


# --- F-043, F-044: sabloanele de antet si subsol -----------------------------------------------


class HeaderFooterStore:
    """Sabloanele salvate in app.db (`header_footer_template`, SPEC_04).
    Efectele de text (bold, italic, subliniat) nu au coloane in schema si nu
    se salveaza in sablon."""

    _COLUMNS = ("position", "content", "margin_value", "margin_unit", "font_name",
                "font_size", "text_color", "bates_start", "bates_digits")

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def names(self) -> list[str]:
        rows = self._con.execute(
            "SELECT name FROM header_footer_template ORDER BY name COLLATE NOCASE")
        return [name for (name,) in rows.fetchall()]

    def load(self, name: str) -> HeaderFooter:
        row = self._con.execute(
            f"SELECT {', '.join(self._COLUMNS)} FROM header_footer_template WHERE name = ?",
            (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        (position, content, margin, unit, font, size, color, start, digits) = row
        return HeaderFooter(position=position, content=content, margin=float(margin),
                            margin_unit=unit, font_name=font,
                            font_size=float(size) if size is not None else 10.0,
                            text_color=color or "#000000", bates_start=start,
                            bates_digits=int(digits) if digits is not None else 6)

    def save(self, name: str, hf: HeaderFooter, *, replace_existing: bool = False) -> None:
        """F-043 `Save and Add`: numele e unic; un nume folosit → `ValueError`
        (interfata cere altul), afara de `Save` pe sablonul editat (F-044)."""
        name = name.strip()
        if not name:
            raise ValueError("sablonul trebuie sa aiba un nume")
        hf.validate()
        exists = name in self.names()
        if exists and not replace_existing:
            raise ValueError(f"exista deja un sablon cu numele {name!r}")
        values = (hf.position, hf.content, hf.margin, hf.margin_unit, hf.font_name,
                  hf.font_size, hf.text_color, hf.bates_start, hf.bates_digits)
        with self._con:
            if exists:
                sets = ", ".join(f"{c} = ?" for c in self._COLUMNS)
                self._con.execute(f"UPDATE header_footer_template SET {sets} WHERE name = ?",
                                  (*values, name))
            else:
                self._con.execute(
                    f"INSERT INTO header_footer_template (name, {', '.join(self._COLUMNS)})"
                    f" VALUES (?, {', '.join('?' * len(self._COLUMNS))})", (name, *values))

    def copy(self, name: str, new_name: str) -> None:
        """F-044 `Copy...`."""
        self.save(new_name, replace(self.load(name)))

    def delete(self, name: str) -> None:
        """F-044 `Delete`."""
        with self._con:
            self._con.execute("DELETE FROM header_footer_template WHERE name = ?", (name,))
