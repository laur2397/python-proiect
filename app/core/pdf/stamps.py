"""Stampilele din PDF Editor (faza 7, pasul 7.4b): D-045…D-052.

Biblioteca stampilelor e tabela `stamp` din app.db (SPEC_04). Stampilele
livrate (D-045) sunt definite in `app/core/data/stamps.json`, cu textul in
fiecare limba, si se adauga in tabela cu `is_builtin = 1` (nu se sterg si nu se
modifica). Stampilele proprii: din imagine (D-047) sau de text, cu etichete de
data si ora (D-048, D-049, `app/core/datetags.py`).

Pe pagina, o stampila e o adnotare PDF `/Stamp` cu aspect generat; primeste
comentarii si statusuri ca orice adnotare (D-046), se sterge ca ele (D-051) si
se muta sau redimensioneaza schimbandu-i dreptunghiul (D-052).
"""

from __future__ import annotations

import io
import json
import sqlite3
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf
from PIL import Image

from app.core.datetags import expand
from app.core.errors import BuiltinNotEditableError, UnsupportedFormatError
from app.core.model import AnnotationData
from app.core.pdf.markup import pdf_date, rgb
from app.core.pdf.text import page_geometry

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

BUILTINS_FILE = Path(__file__).resolve().parent.parent / "data" / "stamps.json"
BORDERS = ("none", "solid", "double", "dashed")
"""Valorile din CHECK-ul `stamp.border_style` (SPEC_04)."""

DEFAULT_FONT_SIZE = 18.0
DEFAULT_TEXT_COLOR = "#B42318"
IMAGE_DPI = 150
"""O stampila din imagine se plaseaza la 150 dpi (scara 1)."""

STANDARD_NAMES = {"approved": "Approved", "rejected": "NotApproved", "final": "Final",
                  "draft": "Draft", "confidential": "Confidential",
                  "for_comment": "ForComment"}
"""Numele standard din PDF pentru stampilele livrate care au unul."""


@lru_cache(maxsize=1)
def builtin_definitions() -> list[dict[str, Any]]:
    return json.loads(BUILTINS_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Stamp:
    id: int
    name: str
    kind: str
    """'text' sau 'image'."""
    text: str | None = None
    image: bytes | None = None
    include_date: bool = False
    include_time: bool = False
    font_name: str | None = None
    font_size: float | None = None
    text_color: str | None = None
    border_style: str | None = None
    is_builtin: bool = False


_COLUMNS = ("id, name, stamp_kind, text_content, image_blob, include_date, include_time,"
            " font_name, font_size, text_color, border_style, is_builtin")


def _row(row: tuple[Any, ...]) -> Stamp:
    (sid, name, kind, text, image, date, time, font, size, color, border, builtin) = row
    return Stamp(int(sid), name, kind, text, image, bool(date), bool(time), font,
                 None if size is None else float(size), color, border, bool(builtin))


def _has(text: str, tags: tuple[str, ...]) -> bool:
    return any(f"<{tag}" in text for tag in tags)


def _validate_text(text: str, font_size: float | None, color: str, border: str) -> None:
    if not text.strip():
        raise ValueError("textul stampilei e gol")
    if font_size is not None and not 4 <= font_size <= 144:
        raise ValueError("dimensiunea fontului e intre 4 si 144 pt")
    rgb(color)
    if border not in BORDERS:
        raise ValueError(f"chenar necunoscut: {border}")


def _normalize_image(data: bytes, scale: float) -> bytes:
    if not 0.1 <= scale <= 4:
        raise ValueError("scara stampilei e intre 0,1 si 4")
    try:
        with Image.open(io.BytesIO(data)) as src:
            image = src.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise UnsupportedFormatError("imaginea stampilei nu se poate citi") from exc
    if scale != 1:
        image = image.resize((max(1, round(image.width * scale)),
                              max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class StampLibrary:
    """D-047, D-048, D-050: biblioteca stampilelor. `con` = `AppContext.app_db`."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._ensure_builtins()

    def _ensure_builtins(self) -> None:
        with self._con:
            for item in builtin_definitions():
                self._con.execute(
                    "INSERT OR IGNORE INTO stamp (name, stamp_kind, text_content, include_date,"
                    " include_time, text_color, border_style, is_builtin)"
                    " VALUES (?, 'text', ?, ?, ?, ?, ?, 1)",
                    (item["key"], item["key"], int(item["date"]), int(item["time"]),
                     item["color"], item["border"]))

    # D-045, D-050
    def stamps(self) -> list[Stamp]:
        """Cele livrate intai (in ordinea lor), apoi cele proprii, dupa nume."""
        order = {item["key"]: i for i, item in enumerate(builtin_definitions())}
        rows = [_row(r) for r in self._con.execute(f"SELECT {_COLUMNS} FROM stamp")]
        builtin = sorted((s for s in rows if s.is_builtin),
                         key=lambda s: order.get(s.name, len(order)))
        own = sorted((s for s in rows if not s.is_builtin), key=lambda s: s.name.casefold())
        return builtin + own

    def get(self, name: str) -> Stamp:
        row = self._con.execute(f"SELECT {_COLUMNS} FROM stamp WHERE name = ?", (name,)
                                ).fetchone()
        if row is None:
            raise KeyError(name)
        return _row(row)

    def _check_new(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("stampila trebuie sa aiba un nume")
        if self._con.execute("SELECT 1 FROM stamp WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"exista deja o stampila cu numele {name!r}")
        return name

    # D-048, D-049
    def create_text(self, name: str, text: str, *, font_name: str | None = None,
                    font_size: float | None = None, text_color: str = DEFAULT_TEXT_COLOR,
                    border_style: str = "solid") -> Stamp:
        """`border_style='none'` = fara `Add border`."""
        name = self._check_new(name)
        _validate_text(text, font_size, text_color, border_style)
        with self._con:
            self._con.execute(
                "INSERT INTO stamp (name, stamp_kind, text_content, include_date, include_time,"
                " font_name, font_size, text_color, border_style)"
                " VALUES (?, 'text', ?, ?, ?, ?, ?, ?, ?)",
                (name, text, int(_has(text, ("d", "date"))),
                 int(_has(text, ("t12", "t24", "time"))), font_name, font_size, text_color,
                 border_style))
        return self.get(name)

    # D-047
    def create_image(self, name: str, data: bytes, *, scale: float = 1.0) -> Stamp:
        """Din imagine (fisier deschis sau lipit din clipboard). `scale` e
        sliderul de dimensiune: imaginea se salveaza la marimea aleasa."""
        name = self._check_new(name)
        png = _normalize_image(data, scale)
        with self._con:
            self._con.execute(
                "INSERT INTO stamp (name, stamp_kind, image_blob) VALUES (?, 'image', ?)",
                (name, png))
        return self.get(name)

    # D-050 `Edit...`
    def update(self, name: str, *, new_name: str | None = None, text: str | None = None,
               font_name: str | None = None, font_size: float | None = None,
               text_color: str | None = None, border_style: str | None = None,
               image: bytes | None = None, scale: float = 1.0) -> Stamp:
        stamp = self.get(name)
        if stamp.is_builtin:
            raise BuiltinNotEditableError("stampilele livrate nu se modifica", name=name)
        target = name if new_name is None or new_name == name else self._check_new(new_name)
        if stamp.kind == "text":
            text = stamp.text or "" if text is None else text
            font_size = stamp.font_size if font_size is None else font_size
            color = text_color or stamp.text_color or DEFAULT_TEXT_COLOR
            border = border_style or stamp.border_style or "solid"
            _validate_text(text, font_size, color, border)
            with self._con:
                self._con.execute(
                    "UPDATE stamp SET name = ?, text_content = ?, include_date = ?,"
                    " include_time = ?, font_name = ?, font_size = ?, text_color = ?,"
                    " border_style = ? WHERE id = ?",
                    (target, text, int(_has(text, ("d", "date"))),
                     int(_has(text, ("t12", "t24", "time"))),
                     font_name if font_name is not None else stamp.font_name, font_size,
                     color, border, stamp.id))
        else:
            blob = stamp.image if image is None else _normalize_image(image, scale)
            with self._con:
                self._con.execute("UPDATE stamp SET name = ?, image_blob = ? WHERE id = ?",
                                  (target, blob, stamp.id))
        return self.get(target)

    # D-050 `Delete...`
    def delete(self, name: str) -> None:
        stamp = self.get(name)
        if stamp.is_builtin:
            raise BuiltinNotEditableError("stampilele livrate nu se sterg", name=name)
        with self._con:
            self._con.execute("DELETE FROM stamp WHERE id = ?", (stamp.id,))


# D-049, D-107
def stamp_text(stamp: Stamp, *, language: str = "ro", moment: datetime | None = None,
               region: str | None = None) -> str:
    """Textul care apare pe pagina: la cele livrate, cel din limba aleasa, cu
    data si ora completate automat (D-107); la cele proprii, textul cu
    etichetele inlocuite. Gol pentru o stampila din imagine."""
    if stamp.kind != "text":
        return ""
    if stamp.is_builtin:
        item = next((i for i in builtin_definitions() if i["key"] == stamp.name), None)
        label = item["text"].get(language, item["text"]["en"]) if item else stamp.name
        parts = [p for p, on in (("<d/>", stamp.include_date), ("<t24/>", stamp.include_time))
                 if on]
        template = label + ("\n" + " ".join(parts) if parts else "")
    else:
        template = stamp.text or ""
    return expand(template, moment, region=region)


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _form(pdf: pikepdf.Pdf, box: list[float], ops: str,
          resources: pikepdf.Dictionary) -> pikepdf.Stream:
    stream = pdf.make_stream(ops.encode("ascii"))
    stream.Type, stream.Subtype = pikepdf.Name.XObject, pikepdf.Name.Form
    stream.BBox = box
    stream.Resources = resources
    return stream


def _text_appearance(pdf: pikepdf.Pdf, stamp: Stamp, text: str, x: float, top: float,
                     scale: float) -> tuple[list[float], pikepdf.Stream]:
    """Textul centrat, primul rand mare, celelalte (data, ora) mai mici, in chenar."""
    from app.core.pdf.embedded_font import embed_text_font

    lines = text.split("\n")
    size = (stamp.font_size or DEFAULT_FONT_SIZE) * scale
    sizes = [size] + [size * 0.55] * (len(lines) - 1)
    font = embed_text_font(pdf, lines)
    pad = size * 0.4
    ascent, descent = font.ascent / 1000, abs(font.descent) / 1000
    gap = size * 0.1
    width = max(font.width(line, s) for line, s in zip(lines, sizes, strict=True)) + 2 * pad
    height = sum(s * (ascent + descent) for s in sizes) + gap * (len(lines) - 1) + 2 * pad
    box = [x, top - height, x + width, top]
    r, g, b = (_num(v) for v in rgb(stamp.text_color or DEFAULT_TEXT_COLOR))
    border = stamp.border_style or "solid"
    lw = max(1.0, size * 0.08)
    ops = [f"{r} {g} {b} RG {r} {g} {b} rg {_num(lw)} w"]
    if border == "dashed":
        ops.append(f"[{_num(lw * 4)} {_num(lw * 2)}] 0 d")
    if border != "none":
        half = lw / 2
        ops.append(f"{_num(x + half)} {_num(top - height + half)} {_num(width - lw)} "
                   f"{_num(height - lw)} re S")
        if border == "double":
            inset = lw * 2.5
            ops.append(f"{_num(x + inset)} {_num(top - height + inset)} "
                       f"{_num(width - 2 * inset)} {_num(height - 2 * inset)} re S")
    y = top - pad
    text_ops = ["BT"]
    for i, (line, s) in enumerate(zip(lines, sizes, strict=True)):
        y -= s * ascent if i == 0 else sizes[i - 1] * descent + gap + s * ascent
        left = x + (width - font.width(line, s)) / 2
        text_ops.append(f"/F1 {_num(s)} Tf 1 0 0 1 {_num(left)} {_num(y)} Tm "
                        f"{font.encode(line)} Tj")
    text_ops.append("ET")
    ops.append(" ".join(text_ops))
    return box, _form(pdf, box, " ".join(ops),
                      pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font)))


def _image_appearance(pdf: pikepdf.Pdf, stamp: Stamp, x: float, top: float, scale: float
                      ) -> tuple[list[float], pikepdf.Stream]:
    with Image.open(io.BytesIO(stamp.image or b"")) as src:
        image = src.convert("RGBA")
    width = image.width * 72 / IMAGE_DPI * scale
    height = image.height * 72 / IMAGE_DPI * scale
    smask = pdf.make_stream(zlib.compress(image.getchannel("A").tobytes()),
                            Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                            Width=image.width, Height=image.height,
                            ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=8,
                            Filter=pikepdf.Name.FlateDecode)
    picture = pdf.make_stream(zlib.compress(image.convert("RGB").tobytes()),
                              Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                              Width=image.width, Height=image.height,
                              ColorSpace=pikepdf.Name.DeviceRGB, BitsPerComponent=8,
                              Filter=pikepdf.Name.FlateDecode, SMask=smask)
    box = [x, top - height, x + width, top]
    ops = f"q {_num(width)} 0 0 {_num(height)} {_num(x)} {_num(top - height)} cm /Im1 Do Q"
    return box, _form(pdf, box, ops,
                      pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im1=picture)))


# D-045, D-047, D-048
def place_stamp(document: PdfDocument, page: int, stamp: Stamp, at: tuple[float, float], *,
                scale: float = 1.0, author: str | None = None, language: str = "ro",
                moment: datetime | None = None, region: str | None = None) -> AnnotationData:
    """Pune stampila pe pagina, cu coltul din stanga-sus in `at` (puncte,
    sus-stanga). Intoarce adnotarea creata."""
    from app.core.pdf.annotations import _append, _id, read_annotation

    total = document.page_count
    if not 1 <= page <= total:
        raise ValueError(f"pagina {page} nu exista (1..{total})")
    if not 0.1 <= scale <= 4:
        raise ValueError("scara stampilei e intre 0,1 si 4")
    pdf = document._pike()
    pdf_page = pdf.pages[page - 1]
    left, bottom, height = page_geometry(pdf_page)
    x, top = left + at[0], bottom + height - at[1]
    content = None
    if stamp.kind == "image":
        box, appearance = _image_appearance(pdf, stamp, x, top, scale)
    else:
        content = stamp_text(stamp, language=language, moment=moment, region=region)
        box, appearance = _text_appearance(pdf, stamp, content, x, top, scale)
    name = STANDARD_NAMES.get(stamp.name) if stamp.is_builtin else None
    now = pikepdf.String(pdf_date())
    annot = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Stamp, Rect=box, F=4, P=pdf_page.obj,
        Name=pikepdf.Name("/" + (name or "DocuLens")), NM=pikepdf.String(uuid.uuid4().hex),
        CreationDate=now, M=now, Subj=pikepdf.String(stamp.name),
        AP=pikepdf.Dictionary(N=appearance)))
    if stamp.kind == "text":
        annot.C = list(rgb(stamp.text_color or DEFAULT_TEXT_COLOR))
    if content:
        annot.Contents = pikepdf.String(content)
    if author:
        annot.T = pikepdf.String(author)
    _append(pdf_page, pdf, annot)
    document._changed()
    return read_annotation(document, _id(annot))
