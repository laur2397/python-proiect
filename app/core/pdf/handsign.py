"""Semnaturile text si imagine (faza 10, pasul 10.3): G-050…G-055.

Nu sunt semnaturi criptografice: sunt imagini de semnatura, pastrate in app.db
(`saved_signature`, SPEC_04) si puse pe pagina ca stampile (`/Stamp`, ca in
faza 7). O semnatura text (G-050) se deseneaza cu fontul ales, pe fond
transparent; una din imagine (G-051) vine dintr-un fisier sau din clipboard, se
poate redimensiona si i se poate face fundalul transparent. Dupa plasare se
muta si se redimensioneaza ca orice stampila (D-052) si se roteste (G-052).
"""

from __future__ import annotations

import io
import math
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.errors import UnsupportedFormatError

if TYPE_CHECKING:
    from app.core.model import AnnotationData
    from app.core.pdf.document import PdfDocument

TEXT_SIZE_PX = 96
"""Inaltimea textului desenat (pixeli), la 200 dpi."""
TEXT_COLOR = "#1a237e"
WHITE_LEVEL = 235
"""Fundalul transparent (G-051): pixelii mai deschisi de atat devin transparenti."""
SCRIPT_FONTS = ("Segoe Script", "Lucida Handwriting", "Brush Script MT", "Snell Roundhand",
                "Apple Chancery", "URW Chancery L")
"""G-050: fonturile de mana cautate intai; fara ele, fontul implicit."""


@dataclass
class SavedSignature:
    id: int
    name: str
    kind: str
    """`text` sau `image`."""
    text: str | None
    image: bytes
    """PNG cu transparenta."""
    transparent: bool = False


def _render_text(text: str, font_name: str | None, color: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    from app.core.fonts import font_file
    from app.core.pdf.decorate import _rgb
    from app.core.pdf.redact import text_font_file

    path = font_file(font_name) if font_name else None
    if path is None:
        path = next((p for p in (font_file(n) for n in SCRIPT_FONTS) if p), None) or \
            text_font_file()
    font: Any = ImageFont.truetype(str(path), TEXT_SIZE_PX) if path else \
        ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    image = Image.new("RGBA", (int(right - left) + 16, int(bottom - top) + 16),
                      (255, 255, 255, 0))
    r, g, b = (round(c * 255) for c in _rgb(color))
    ImageDraw.Draw(image).text((8 - left, 8 - top), text, font=font, fill=(r, g, b, 255))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def prepare_image(data: bytes, *, transparent: bool, scale: float = 1.0) -> bytes:
    """G-051: redimensionarea si fundalul transparent (pixelii aproape albi)."""
    import numpy as np
    from PIL import Image

    if not 0.05 <= scale <= 4:
        raise ValueError("scara e intre 0,05 si 4")
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise UnsupportedFormatError("imaginea semnaturii nu se poate citi") from exc
    if scale != 1:
        image = image.resize((max(1, round(image.width * scale)),
                              max(1, round(image.height * scale))))
    if transparent:
        pixels = np.array(image)
        light = pixels[:, :, :3].min(axis=2) >= WHITE_LEVEL
        pixels[light, 3] = 0
        image = Image.fromarray(pixels, "RGBA")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class SignatureImageLibrary:
    """G-053…G-055: semnaturile text si imagine salvate."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def signatures(self) -> list[SavedSignature]:
        rows = self._con.execute(
            "SELECT id, name, signature_kind, text_content, image_blob, transparent_bg"
            " FROM saved_signature WHERE signature_kind IN ('text', 'image')"
            " ORDER BY name COLLATE NOCASE").fetchall()
        return [SavedSignature(int(i), n, k, t, bytes(b), bool(tr))
                for i, n, k, t, b, tr in rows]

    def get(self, name: str) -> SavedSignature:
        for signature in self.signatures():
            if signature.name == name:
                return signature
        raise KeyError(name)

    def _check_name(self, name: str, *, current: str | None = None) -> str:
        name = name.strip()
        if not name:
            raise ValueError("semnatura trebuie sa aiba un nume")
        taken = {s.name for s in self.signatures()} - ({current} if current else set())
        if name in taken:
            raise ValueError(f"exista deja o semnatura cu numele {name!r}")
        return name

    def create_text(self, name: str, text: str, *, font_name: str | None = None,
                    color: str = TEXT_COLOR) -> SavedSignature:
        """G-050 `Create Text Signature...`."""
        name = self._check_name(name)
        if not text.strip():
            raise ValueError("textul semnaturii e gol")
        image = _render_text(text, font_name, color)
        with self._con:
            self._con.execute(
                "INSERT INTO saved_signature (name, signature_kind, text_content, image_blob,"
                " transparent_bg) VALUES (?, 'text', ?, ?, 1)", (name, text, image))
        return self.get(name)

    def create_image(self, name: str, data: bytes, *, transparent: bool = False,
                     scale: float = 1.0) -> SavedSignature:
        """G-051 `Create Signature from Image...` (fisier sau clipboard)."""
        name = self._check_name(name)
        image = prepare_image(data, transparent=transparent, scale=scale)
        with self._con:
            self._con.execute(
                "INSERT INTO saved_signature (name, signature_kind, image_blob, transparent_bg)"
                " VALUES (?, 'image', ?, ?)", (name, image, int(transparent)))
        return self.get(name)

    def update(self, name: str, *, new_name: str | None = None, text: str | None = None,
               font_name: str | None = None, transparent: bool | None = None,
               scale: float = 1.0) -> SavedSignature:
        """G-054 `Edit...`, apoi `Save`."""
        signature = self.get(name)
        final = self._check_name(new_name, current=name) if new_name else name
        image, content = signature.image, signature.text
        if signature.kind == "text" and (text is not None or font_name is not None):
            content = text if text is not None else signature.text or ""
            if not content.strip():
                raise ValueError("textul semnaturii e gol")
            image = _render_text(content, font_name, TEXT_COLOR)
        flag = signature.transparent if transparent is None else transparent
        if signature.kind == "image" and (transparent or scale != 1):
            image = prepare_image(image, transparent=flag, scale=scale)
        with self._con:
            self._con.execute(
                "UPDATE saved_signature SET name = ?, text_content = ?, image_blob = ?,"
                " transparent_bg = ? WHERE id = ?",
                (final, content, image, int(flag), signature.id))
        return self.get(final)

    def delete(self, name: str) -> None:
        """G-055."""
        signature = self.get(name)
        with self._con:
            self._con.execute("DELETE FROM saved_signature WHERE id = ?", (signature.id,))


# --- plasarea (G-052) ------------------------------------------------------------------------


def place_signature(document: PdfDocument, page: int, signature: SavedSignature,
                    at: tuple[float, float], *, scale: float = 1.0,
                    author: str | None = None) -> AnnotationData:
    """Semnatura pe pagina, cu coltul stanga-sus in `at` (puncte, sus-stanga), ca
    stampila; se pot pune oricate (G-053)."""
    from app.core.pdf.stamps import Stamp, place_stamp

    stamp = Stamp(-1, signature.name, "image", image=signature.image)
    return place_stamp(document, page, stamp, at, scale=scale, author=author)


def rotate_placed(document: PdfDocument, annot_id: int, degrees: int = 90) -> None:
    """G-052: rotirea semnaturii plasate, in pasi de 90 de grade, in jurul
    centrului ei."""
    from app.core.pdf.annotations import _find

    if degrees % 90:
        raise ValueError("semnatura se roteste in pasi de 90 de grade")
    _number, annot = _find(document, annot_id)
    appearance = annot.AP.N
    old = [float(v) for v in appearance.get("/Matrix", [1, 0, 0, 1, 0, 0])]
    current = math.degrees(math.atan2(old[1], old[0]))
    angle = math.radians(round(current + degrees) % 360)
    cos, sin = round(math.cos(angle)), round(math.sin(angle))
    appearance.Matrix = pikepdf.Array([cos, sin, -sin, cos, 0, 0])
    x0, y0, x1, y1 = (float(v) for v in annot.Rect)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0), abs(y1 - y0)
    if degrees % 180:
        w, h = h, w
    annot.Rect = pikepdf.Array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
    document._changed()
