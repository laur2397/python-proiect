"""Un font de sistem incorporat (subset) pentru textul vizibil scris de PDF
Editor: casetele de text (D-017, D-019) si stampilele de text (D-048).

Fontul e cel gasit de `redact.text_font_file()` (Arial, DejaVu Sans, Liberation
Sans...), cu diacriticele romanesti. Se incorporeaza numai glifele folosite,
ca Type0/Identity-H cu `ToUnicode`, deci textul se vede la fel in orice cititor
si se poate cauta si copia.

Fara un astfel de font pe sistem se foloseste Helvetica standard (neincorporata),
in care literele fara corespondent WinAnsi (ș, ț) se scriu cu varianta cu
sedila, iar restul devin „?” — marcat in `TextFont.fallback`.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf

_WINANSI_FALLBACK = str.maketrans({"ș": "ş", "ț": "ţ", "Ș": "Ş", "Ț": "Ţ"})


@dataclass
class TextFont:
    """Fontul incorporat intr-un PDF: dictionarul /Font si masurarea textului."""

    font: pikepdf.Object
    widths: dict[str, float] = field(default_factory=dict)
    """Latimea fiecarui caracter, in miimi de em."""
    gids: dict[str, int] = field(default_factory=dict)
    ascent: float = 905
    descent: float = -212
    fallback: bool = False

    def width(self, text: str, size: float) -> float:
        return sum(self.widths.get(ch, 500) for ch in text) * size / 1000

    def encode(self, text: str) -> str:
        """Textul pentru operatorul Tj: <hex> (Identity-H) sau (sir) WinAnsi."""
        if self.fallback:
            raw = text.translate(_WINANSI_FALLBACK).encode("cp1252", errors="replace")
            escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            return "(" + escaped.decode("latin-1") + ")"
        return "<" + "".join(f"{self.gids.get(ch, 0):04X}" for ch in text) + ">"


def _helvetica(pdf: pikepdf.Pdf) -> TextFont:
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))
    return TextFont(font, {}, {}, 718, -207, fallback=True)


def _to_unicode(gids: dict[str, int]) -> bytes:
    entries = [f"<{gid:04X}> <{ch.encode('utf-16-be').hex().upper()}>"
               for ch, gid in sorted(gids.items(), key=lambda item: item[1])]
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


def embed_text_font(pdf: pikepdf.Pdf, texts: Sequence[str], *,
                    font_path: Path | None = None) -> TextFont:
    """Fontul pentru textele date, incorporat in `pdf` (subset cu glifele lor).
    `font_path`: un font TrueType anume (F-041); implicit, fontul de sistem cu
    diacriticele romanesti."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    from app.core.pdf.redact import text_font_file

    path = font_path or text_font_file()
    chars = sorted({ch for text in texts for ch in text if ch not in "\r\n"} | {" "})
    if path is None:
        return _helvetica(pdf)
    try:
        font = TTFont(str(path), fontNumber=0)
    except (OSError, ValueError):
        return _helvetica(pdf)
    if "glyf" not in font:  # numai TrueType se incorporeaza ca FontFile2
        return _helvetica(pdf)
    cmap = font.getBestCmap() or {}
    options = subset.Options()
    options.retain_gids = True
    options.notdef_outline = True
    options.name_IDs = ["*"]
    options.layout_features = []
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=[ord(ch) for ch in chars if ord(ch) in cmap])
    subsetter.subset(font)
    out = io.BytesIO()
    font.save(out)
    units = font["head"].unitsPerEm
    hmtx = font["hmtx"]
    gids: dict[str, int] = {}
    widths: dict[str, float] = {}
    for ch in chars:
        glyph = cmap.get(ord(ch))
        if glyph is None:
            continue
        gids[ch] = font.getGlyphID(glyph)
        widths[ch] = hmtx[glyph][0] * 1000 / units
    hhea = font["hhea"]
    ascent, descent = hhea.ascent * 1000 / units, hhea.descent * 1000 / units
    name = "DocuLensText"
    descriptor = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor, FontName=pikepdf.Name("/" + name), Flags=32,
        FontBBox=[-200, round(descent), 1200, round(ascent)], ItalicAngle=0,
        Ascent=round(ascent), Descent=round(descent), CapHeight=round(ascent * 0.75),
        StemV=80, FontFile2=pdf.make_stream(out.getvalue())))
    w_array: list[object] = []
    for ch, gid in sorted(gids.items(), key=lambda item: item[1]):
        w_array += [gid, [round(widths[ch])]]
    cid_font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType2,
        BaseFont=pikepdf.Name("/" + name),
        CIDSystemInfo=pikepdf.Dictionary(Registry=pikepdf.String("Adobe"),
                                         Ordering=pikepdf.String("Identity"), Supplement=0),
        FontDescriptor=descriptor, DW=1000, W=w_array, CIDToGIDMap=pikepdf.Name.Identity))
    type0 = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0, BaseFont=pikepdf.Name("/" + name),
        Encoding=pikepdf.Name("/Identity-H"), DescendantFonts=[cid_font],
        ToUnicode=pdf.make_stream(_to_unicode(gids))))
    return TextFont(type0, widths, gids, ascent, descent)


def wrap(font: TextFont, text: str, size: float, width: float) -> list[str]:
    """Textul impartit pe randuri care incap in `width` (puncte); randurile
    date de utilizator se pastreaza, un cuvant prea lung ramane pe randul lui."""
    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").split("\n"):
        current = ""
        for word in paragraph.split(" "):
            candidate = word if not current else current + " " + word
            if current and font.width(candidate, size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines
