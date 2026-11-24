"""GlyphRecovery: refacerea codificarii stricate a unui PDF (F-057).

Un PDF al carui text se copiaza ca semne fara sens are fonturi cu tabelul
cod → caracter gresit sau lipsa (de exemplu `º` in loc de `ș`, frecvent in
documentele romanesti produse cu fonturi vechi Windows-1250). Glifele desenate
pe pagina sunt corecte; numai textul extras e gresit.

Algoritmul (functional, fara cunoasterea implementarii originalului):

1. Se citesc caracterele paginii cu dreptunghiul si fontul fiecaruia (PDFium).
2. Pagina se randeaza si se recunoaste (OCR), ca text de referinta.
3. Cuvintele din PDF se aliniaza cu cuvintele recunoscute dupa pozitie; la
   cuvintele de aceeasi lungime, fiecare caracter extras voteaza pentru
   caracterul recunoscut, separat pe font.
4. Un caracter al unui font se corecteaza numai cu destule voturi si cu o
   majoritate clara (`MIN_VOTES`, `AGREEMENT`); un font corect primeste voturi
   de acord si nu se atinge.
5. Pentru fontul reparat, tabelul lui cod → caracter (ToUnicode existent, altfel
   codificarea si `Differences`) se inverseaza si se scrie un ToUnicode nou, cu
   corecturile. Continutul paginii nu se schimba, deci nici aspectul.

Un font fara ToUnicode si fara codificare cunoscuta (CID fara tabel) nu se poate
inversa: ramane cum e, iar raportul il numeste (F-057: atunci se propune OCR).
"""

from __future__ import annotations

import ctypes
import io
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.model import CancelToken, LanguageCode, Progress, ProgressCallback, Rect

if TYPE_CHECKING:  # pragma: no cover
    from app.core.pdf.document import PdfDocument

MIN_VOTES = 2
"""De cate ori trebuie vazuta aceeasi corectura pe un font."""
AGREEMENT = 0.6
"""Ce parte din aparitiile caracterului trebuie sa fie de acord cu corectura."""
OVERLAP = 0.3
"""Suprapunerea minima (IoU) intre un cuvant din PDF si unul recunoscut."""
OCR_DPI = 200

OcrWords = Callable[[Any, int], list[tuple[str, Rect]]]
"""(imaginea paginii, dpi) → cuvintele recunoscute, in pixelii imaginii."""


@dataclass(slots=True)
class GlyphReport:
    """F-057: ce s-a verificat si ce s-a reparat."""

    pages: list[int] = field(default_factory=list)
    fonts: dict[str, dict[str, str]] = field(default_factory=dict)
    """Fontul reparat → {caracterul extras gresit: caracterul corect}."""
    unfixable: list[str] = field(default_factory=list)
    """Fonturile cu erori care nu au un tabel de coduri care sa se poata inversa."""

    @property
    def changed(self) -> bool:
        return bool(self.fonts)

    def as_dict(self) -> dict[str, Any]:
        return {"pages": list(self.pages), "fonts": {k: dict(v) for k, v in self.fonts.items()},
                "unfixable": list(self.unfixable)}


@dataclass(slots=True)
class _Char:
    text: str
    box: Rect
    font: str


# --- citirea caracterelor -------------------------------------------------------------


def _base_name(name: str) -> str:
    """`ABCDEF+Arial-Bold` → `Arial-Bold` (prefixul subsetului nu conteaza)."""
    return re.sub(r"^[A-Z]{6}\+", "", name.lstrip("/"))


def page_chars(document: PdfDocument, number: int) -> list[_Char]:
    """Caracterele paginii (de la 1): textul extras, dreptunghiul in puncte (sus-
    stanga MediaBox) si numele fontului; spatiile si sfarsiturile de rand raman
    afara."""
    from pypdfium2 import raw

    from app.core.pdf.document import PDFIUM_LOCK

    doc = document._require_open()
    out: list[_Char] = []
    with PDFIUM_LOCK:
        page = doc[number - 1]
        try:
            left, _bottom, _right, top = page.get_mediabox()
            textpage = page.get_textpage()
            try:
                buffer = ctypes.create_string_buffer(256)
                flags = ctypes.c_int(0)
                for i in range(textpage.count_chars()):
                    ch = textpage.get_text_range(i, 1)
                    if not ch or ch.isspace():
                        continue
                    size = raw.FPDFText_GetFontInfo(textpage.raw, i, buffer, len(buffer),
                                                    ctypes.byref(flags))
                    name = buffer.value.decode("utf-8", "replace") if size else ""
                    x0, y0, x1, y1 = textpage.get_charbox(i)
                    out.append(_Char(ch[0], Rect(x0 - left, top - y1, x1 - x0, y1 - y0),
                                     _base_name(name)))
            finally:
                textpage.close()
        finally:
            page.close()
    return out


def _words(chars: Sequence[_Char]) -> list[list[_Char]]:
    """Caracterele unite in cuvinte: alaturate pe acelasi rand, fara gol mare."""
    words: list[list[_Char]] = []
    for ch in chars:
        if words:
            last = words[-1][-1].box
            same_line = abs((last.y + last.h / 2) - (ch.box.y + ch.box.h / 2)) < \
                max(last.h, ch.box.h) * 0.6
            gap = ch.box.x - last.right
            if same_line and -last.w <= gap < max(last.h, ch.box.h) * 0.25:
                words[-1].append(ch)
                continue
        words.append([ch])
    return words


def _union(boxes: Sequence[Rect]) -> Rect:
    x0, y0 = min(b.x for b in boxes), min(b.y for b in boxes)
    return Rect(x0, y0, max(b.right for b in boxes) - x0, max(b.bottom for b in boxes) - y0)


def _iou(a: Rect, b: Rect) -> float:
    ix = max(0.0, min(a.right, b.right) - max(a.x, b.x))
    iy = max(0.0, min(a.bottom, b.bottom) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


# --- OCR-ul de referinta --------------------------------------------------------------


def _default_ocr(context: Any, engine: Any, languages: Sequence[LanguageCode]) -> OcrWords:
    from app.core.pdf.background import ocr_lines

    def run(image: Any, dpi: int) -> list[tuple[str, Rect]]:
        lines = ocr_lines(image, context=context, engine=engine, languages=languages, dpi=dpi)
        return [word for line in lines for word in line]

    return run


def _reference_words(document: PdfDocument, number: int, ocr: OcrWords,
                     dpi: int) -> list[tuple[str, Rect]]:
    """Cuvintele recunoscute pe pagina, cu dreptunghiul in puncte."""
    from PIL import Image

    png = document.render_page(number, dpi / 96, annotations=False)
    with Image.open(io.BytesIO(png)) as rendered:
        image = rendered.convert("RGB")
    scale = 72 / dpi
    return [(text, Rect(b.x * scale, b.y * scale, b.w * scale, b.h * scale))
            for text, b in ocr(image, dpi) if text.strip()]


# --- voturile -------------------------------------------------------------------------


def _vote(words: Sequence[Sequence[_Char]], reference: Sequence[tuple[str, Rect]],
          votes: dict[str, dict[str, Counter[str]]]) -> None:
    for word in words:
        box = _union([c.box for c in word])
        best = max(reference, key=lambda item: _iou(box, item[1]), default=None)
        if best is None or _iou(box, best[1]) < OVERLAP:
            continue
        truth = best[0].strip()
        if len(truth) != len(word):
            continue
        for ch, right in zip(word, truth, strict=True):
            votes[ch.font][ch.text][right] += 1


ROMANIAN_TEXT = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "ăâîșțĂÂÎȘȚşţŞŢ.,;:!?()[]{}\"'„”«»-–—/\\%&*+=<>@#€$°§_|~^`’‘")
"""Ce poate aparea intr-un text romanesc corect; `ª`, `º`, `Þ`, `þ` nu."""


def _alphabet(languages: Sequence[LanguageCode]) -> frozenset[str] | None:
    """Setul de caractere cunoscut: romana, singura sau cu engleza (care nu aduce
    litere noi; e setarea implicita, X-042); altfel nu se presupune nimic."""
    codes = set(languages)
    if codes & {"ron", "ron-MD"} and codes <= {"ron", "ron-MD", "eng"}:
        return ROMANIAN_TEXT
    return None


def _decide(votes: dict[str, dict[str, Counter[str]]],
            alphabet: frozenset[str] | None = None) -> dict[str, dict[str, str]]:
    """Corecturile sigure, pe font: destule voturi si o majoritate clara. Un
    caracter care nu poate aparea in limba documentului (`alphabet`) se corecteaza
    si dupa un singur vot, daca nimic nu il contrazice (o majuscula rara: `Ș`)."""
    fixes: dict[str, dict[str, str]] = {}
    for font, chars in votes.items():
        for wrong, seen in chars.items():
            right, count = seen.most_common(1)[0]
            total = sum(seen.values())
            foreign = alphabet is not None and wrong not in alphabet and right in alphabet
            needed = 1 if foreign and count == total else MIN_VOTES
            if right != wrong and count >= needed and count / total >= AGREEMENT \
                    and seen[wrong] < count:
                fixes.setdefault(font, {})[wrong] = right
    return fixes


# --- tabelele de coduri ---------------------------------------------------------------


def _hex(value: str) -> bytes:
    return bytes.fromhex(re.sub(r"\s", "", value))


def _utf16(data: bytes) -> str:
    return data.decode("utf-16-be", "replace")


def parse_to_unicode(stream: bytes) -> tuple[dict[int, str], int]:
    """Tabelul ToUnicode: cod → text, si latimea codului in octeti."""
    text = stream.decode("latin-1")
    width = 1
    space = re.search(r"begincodespacerange\s*<([0-9A-Fa-f]+)>", text)
    if space:
        width = max(1, len(space.group(1)) // 2)
    mapping: dict[int, str] = {}
    for body in re.findall(r"beginbfchar(.*?)endbfchar", text, re.DOTALL):
        for src, dst in re.findall(r"<([0-9A-Fa-f\s]+)>\s*<([0-9A-Fa-f\s]*)>", body):
            mapping[int.from_bytes(_hex(src), "big")] = _utf16(_hex(dst))
    for body in re.findall(r"beginbfrange(.*?)endbfrange", text, re.DOTALL):
        for lo, hi, dst in re.findall(
                r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f\s]*>|\[[^\]]*\])", body):
            start, end = int(lo, 16), int(hi, 16)
            if dst.startswith("["):
                for k, item in enumerate(re.findall(r"<([0-9A-Fa-f\s]*)>", dst)):
                    if start + k <= end:
                        mapping[start + k] = _utf16(_hex(item))
                continue
            base = _hex(dst[1:-1])
            for k in range(end - start + 1):
                value = int.from_bytes(base, "big") + k
                mapping[start + k] = _utf16(value.to_bytes(len(base), "big"))
    return mapping, width


_BASE_CODECS = {"/WinAnsiEncoding": "cp1252", "/MacRomanEncoding": "mac_roman",
                "/StandardEncoding": "latin-1", "/PDFDocEncoding": "latin-1"}


def _simple_encoding(font: pikepdf.Dictionary) -> dict[int, str] | None:
    """Codificarea unui font simplu (WinAnsi, MacRoman, `Differences`)."""
    from fontTools import agl

    encoding = font.get("/Encoding")
    base = "/WinAnsiEncoding"
    differences: Sequence[Any] = ()
    if isinstance(encoding, pikepdf.Name):
        base = str(encoding)
    elif isinstance(encoding, pikepdf.Dictionary):
        base = str(encoding.get("/BaseEncoding", "/WinAnsiEncoding"))
        differences = encoding.get("/Differences", ())
    elif encoding is not None:
        return None
    codec = _BASE_CODECS.get(base)
    if codec is None:
        return None
    mapping = {}
    for code in range(32, 256):
        try:
            mapping[code] = bytes([code]).decode(codec)
        except UnicodeDecodeError:
            continue
    code = 0
    for item in differences:
        if isinstance(item, int):
            code = int(item)
            continue
        text = agl.toUnicode(str(item).lstrip("/"))
        if text:
            mapping[code] = text
        code += 1
    return mapping


def code_map(font: pikepdf.Dictionary) -> tuple[dict[int, str], int] | None:
    """Tabelul cod → text al fontului, cum il citeste un program de vizualizare;
    None daca nu se poate afla (CID fara ToUnicode)."""
    to_unicode = font.get("/ToUnicode")
    if isinstance(to_unicode, pikepdf.Stream):
        try:
            mapping, width = parse_to_unicode(to_unicode.read_bytes())
        except (pikepdf.PdfError, ValueError):
            mapping, width = {}, 1
        if mapping:
            return mapping, width
    if str(font.get("/Subtype", "")) in ("/Type1", "/TrueType", "/MMType1"):
        simple = _simple_encoding(font)
        if simple is not None:
            return simple, 1
    return None


def to_unicode_stream(mapping: dict[int, str], width: int) -> bytes:
    """Un ToUnicode nou, cu toate codurile (cate 100 pe bloc, ca in standard)."""
    digits = width * 2
    entries = [f"<{code:0{digits}X}> <{text.encode('utf-16-be').hex().upper()}>"
               for code, text in sorted(mapping.items()) if text]
    body = []
    for start in range(0, len(entries), 100):
        chunk = entries[start:start + 100]
        body.append(f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar")
    low, high = "0" * digits, "F" * digits
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            f"1 begincodespacerange\n<{low}> <{high}>\nendcodespacerange\n"
            + "\n".join(body) + "\nendcmap\nCMapName currentdict /CMap defineresource pop\n"
            "end\nend\n").encode("ascii")


def _fonts_named(pdf: pikepdf.Pdf, name: str) -> list[pikepdf.Dictionary]:
    """Dictionarele de font cu acest nume, din pagini si din XObject-urile lor."""
    found: dict[tuple[int, int], pikepdf.Dictionary] = {}
    seen: set[tuple[int, int]] = set()

    def walk(resources: Any) -> None:
        if not isinstance(resources, pikepdf.Dictionary):
            return
        fonts = resources.get("/Font")
        if isinstance(fonts, pikepdf.Dictionary):
            for key in list(fonts.keys()):
                font = fonts[key]
                if isinstance(font, pikepdf.Dictionary) and \
                        _base_name(str(font.get("/BaseFont", ""))) == name:
                    found[font.objgen] = font
        xobjects = resources.get("/XObject")
        if isinstance(xobjects, pikepdf.Dictionary):
            for name_key in list(xobjects.keys()):
                xobj = xobjects[name_key]
                key = xobj.objgen
                if key in seen or str(xobj.get("/Subtype", "")) != "/Form":
                    continue
                seen.add(key)
                walk(xobj.get("/Resources"))

    for page in pdf.pages:
        walk(page.obj.get("/Resources"))
    return list(found.values())


def _apply(pdf: pikepdf.Pdf, fixes: dict[str, dict[str, str]], report: GlyphReport) -> None:
    for name, changes in fixes.items():
        fixed = False
        for font in _fonts_named(pdf, name):
            known = code_map(font)
            if known is None:
                continue
            mapping, width = known
            new = {code: changes.get(text, text) for code, text in mapping.items()}
            if new == mapping:
                continue
            font.ToUnicode = pdf.make_stream(to_unicode_stream(new, width))
            fixed = True
        if fixed:
            report.fonts[name] = dict(changes)
        else:
            report.unfixable.append(name)


# --- operatia -------------------------------------------------------------------------


def recover_glyphs(document: PdfDocument, pages: Sequence[int] | None = None, *,
                   languages: Sequence[LanguageCode] = ("ron",), context: Any = None,
                   engine: Any = None, ocr: OcrWords | None = None, dpi: int = OCR_DPI,
                   progress: ProgressCallback | None = None,
                   cancel: CancelToken | None = None) -> GlyphReport:
    """F-057: verifica paginile cu text si repara fonturile cu codificarea
    stricata. `ocr`: recunoasterea de referinta (implicit Tesseract, prin
    `background.ocr_lines`). Documentul se modifica numai daca ceva s-a reparat."""
    from app.core.errors import OperationCancelledError

    chosen = list(pages) if pages is not None else [
        n for n in range(1, document.page_count + 1) if document.has_text_layer(n)]
    reader = ocr or _default_ocr(context, engine, languages)
    report = GlyphReport()
    votes: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for i, number in enumerate(chosen):
        if cancel is not None and cancel():
            raise OperationCancelledError(done=i, total=len(chosen))
        if progress is not None:
            progress(Progress(i, len(chosen), "stage.glyph_recovery", str(number)))
        chars = page_chars(document, number)
        if not chars:
            continue
        _vote(_words(chars), _reference_words(document, number, reader, dpi), votes)
        report.pages.append(number)
    fixes = _decide(votes, _alphabet(languages))
    if fixes:
        _apply(document._pike(), fixes, report)
        if report.fonts:
            document._changed()
    if progress is not None:
        progress(Progress(len(chosen), len(chosen), "stage.glyph_recovery"))
    return report
