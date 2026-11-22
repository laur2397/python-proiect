"""Sursele compararii (faza 12, pasul 12.1): R-002, R-005, R-007, R-008,
R-020, R-021, R-035.

Orice sursa acceptata ajunge la acelasi lucru: un PDF (cel original sau unul
construit) si cuvintele lui, fiecare cu pagina si dreptunghiul (R-005).

- PDF: textul din fisier (`Use Only Text from PDF`, R-020); paginile fara text
  trec prin OCR (R-007). `auto` recunoaste si paginile cu text de proasta
  calitate, `ocr` le recunoaste pe toate (R-021).
- Imaginile devin un PDF doar-imagine si trec prin OCR.
- Formatele editabile (DOCX, XLSX, PPTX, ODT, ODS, ODP, RTF, HTML, TXT) se citesc
  cu biblioteci din stiva sau cu cititoare proprii, iar textul se aseaza intr-un
  PDF simplu (`docs/plan/faza_12_pasi.md`, decizia 1).

Coordonatele: puncte, originea sus-stanga a paginii (ca in `pdf/text.py`).
"""

from __future__ import annotations

import html.parser
import io
import re
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from xml.etree import ElementTree as ET

from app.core.errors import NoTextFoundError, UnsupportedFormatError
from app.core.model import Progress, ProgressCallback, Rect

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.pdf.document import PdfDocument

COMPARE_LANGUAGES: tuple[str, ...] = (
    "ron", "ron-MD", "eng", "fra", "deu", "ita", "spa", "por", "cat", "glg", "eus", "nld",
    "dan", "swe", "nor", "fin", "isl", "est", "lav", "lit", "pol", "ces", "slk", "slv",
    "hrv", "bos", "srp", "srp_latn", "hun", "bul", "rus", "ukr", "bel", "mkd", "ell", "tur",
    "sqi",
)
"""R-008, P-101: limbile de comparare, declarate separat: 37 de limbi OCR cu
alfabet latin, chirilic sau grecesc, in care cuvintele se despart prin spatii.
Limbile fara spatii intre cuvinte (chineza, japoneza, thai...) nu apar."""

PDF_MODES = ("text", "auto", "ocr")
"""R-020: `Use Only Text from PDF`, `Automatically Choose between OCR and Text
from PDF`, `Use OCR`."""

PDF_EXTENSIONS = frozenset({".pdf"})
EDITABLE_EXTENSIONS = frozenset({".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".rtf",
                                 ".htm", ".html", ".txt"})
"""R-002, SPEC_09 B.1: formatele editabile citite fara Microsoft Office."""
LEGACY_EXTENSIONS = frozenset({".doc", ".xls", ".ppt", ".xps", ".djvu", ".djv", ".jbig2",
                               ".jb2"})
"""SPEC_09 B.1 le accepta in Compare; DocuLens nu le citeste inca (INCOMPLET)."""

PAGE_SIZE = (595.0, 842.0)
"""A4, in puncte, pentru PDF-ul construit din formatele editabile."""
MARGIN = 56.0
FONT_SIZE = 11.0
HEADER_SIZE = 9.0
BAD_TEXT_RATIO = 0.3
"""R-020 `auto`: peste aceasta proportie de caractere neobisnuite, stratul de
text e considerat de proasta calitate si pagina se recunoaste."""


# --- cuvintele ---------------------------------------------------------------------------


@dataclass(slots=True)
class SourceWord:
    """Un cuvant al sursei, cu pagina si dreptunghiurile lui (un cuvant despartit
    la capat de rand are doua, R-035)."""

    text: str
    page: int
    rect: Rect
    line: int = 0
    """Numarul randului in pagina (R-030)."""
    rects: list[tuple[int, Rect]] = field(default_factory=list)
    paragraph: int = 0
    """Numarul paragrafului in document (R-030)."""


@dataclass
class SourceDocument:
    """O sursa adusa la PDF si cuvinte."""

    path: Path
    document: PdfDocument
    words: list[SourceWord]
    recognized: bool = False
    """S-a folosit OCR (R-062: avertismentul la DOCX)."""
    converted: bool = False
    """PDF-ul e construit din textul unui format editabil (decizia 1)."""

    def close(self) -> None:
        self.document.close()


def compare_languages() -> tuple[str, ...]:
    """R-008: lista din combo-ul de limbi de comparare."""
    return COMPARE_LANGUAGES


def can_compare(path: Path) -> bool:
    """R-002: PDF, imaginile acceptate de OCR si formatele editabile."""
    from app.core.images.loader import RASTER_EXTENSIONS

    ext = Path(path).suffix.lower()
    return ext in PDF_EXTENSIONS or ext in EDITABLE_EXTENSIONS or ext in RASTER_EXTENSIONS


def _check(path: Path) -> None:
    if not can_compare(path):
        raise UnsupportedFormatError("formatul nu se poate compara", path=str(path),
                                     extension=path.suffix.lower())
    if not path.is_file():
        raise FileNotFoundError(path)


# --- cuvintele dintr-un PDF ----------------------------------------------------------------


def _same_line(a: Rect, b: Rect) -> bool:
    mid_a, mid_b = a.y + a.h / 2, b.y + b.h / 2
    return abs(mid_a - mid_b) <= max(a.h, b.h) * 0.5


def _page_words(text: str, boxes: Sequence[Rect | None], page: int) -> list[SourceWord]:
    words: list[SourceWord] = []
    current: list[tuple[str, Rect]] = []
    state: dict[str, Any] = {"line": 0, "previous": None}

    def flush() -> None:
        if not current:
            return
        x0 = min(b.x for _c, b in current)
        y0 = min(b.y for _c, b in current)
        x1 = max(b.x + b.w for _c, b in current)
        y1 = max(b.y + b.h for _c, b in current)
        rect = Rect(x0, y0, x1 - x0, y1 - y0)
        previous = state["previous"]
        if previous is not None and not _same_line(previous, rect):
            state["line"] += 1
        state["previous"] = rect
        words.append(SourceWord("".join(c for c, _b in current), page, rect, state["line"],
                                [(page, rect)]))
        current.clear()

    for ch, box in zip(text, boxes, strict=False):
        if box is None or ch.isspace() or not box.w:
            flush()
            continue
        if current and not _same_line(current[-1][1], box):
            flush()
        current.append((ch, box))
    flush()
    return words


def _looks_bad(text: str) -> bool:
    """R-020 `auto`: stratul de text pare stricat (multe caractere neobisnuite)."""
    visible = [ch for ch in text if not ch.isspace()]
    if not visible:
        return True
    odd = sum(1 for ch in visible if not (ch.isalnum() or ch in ".,;:!?-–()[]\"'„”«»/%&@"))
    return odd / len(visible) > BAD_TEXT_RATIO


PARAGRAPH_GAP = 1.5
"""R-030: un spatiu vertical intre randuri mai mare de atatea inaltimi de rand
incepe un paragraf nou; la fel o pagina noua."""


def mark_paragraphs(words: list[SourceWord]) -> list[SourceWord]:
    """R-030: cuvintele se grupeaza in randuri, randurile in paragrafe."""
    paragraph = 0
    previous: SourceWord | None = None
    line_top: dict[tuple[int, int], float] = {}
    line_height: dict[tuple[int, int], float] = {}
    for word in words:
        key = (word.page, word.line)
        line_top[key] = min(line_top.get(key, word.rect.y), word.rect.y)
        line_height[key] = max(line_height.get(key, 0.0), word.rect.h)
    for word in words:
        if previous is not None and (word.page, word.line) != (previous.page, previous.line):
            before, now = (previous.page, previous.line), (word.page, word.line)
            gap = line_top[now] - (line_top[before] + line_height[before])
            if word.page != previous.page or gap > PARAGRAPH_GAP * max(
                    line_height[before], 1.0) - line_height[before] or gap < -line_height[
                    before] * 3:
                paragraph += 1
        word.paragraph = paragraph
        previous = word
    return words


def join_hyphenated(words: list[SourceWord]) -> list[SourceWord]:
    """R-035: cuvantul despartit la capat de rand se reunifica."""
    out: list[SourceWord] = []
    i = 0
    while i < len(words):
        word = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else None
        if (nxt is not None and len(word.text) > 1 and word.text.endswith(("-", "­"))
                and (nxt.line != word.line or nxt.page != word.page)
                and nxt.text[:1].islower()):
            out.append(SourceWord(word.text[:-1] + nxt.text, word.page, word.rect, word.line,
                                  [*word.rects, *nxt.rects], word.paragraph))
            i += 2
            continue
        out.append(word)
        i += 1
    return out


def pdf_words(document: PdfDocument, *, mode: str = "text",
              languages: Sequence[str] | None = None, context: AppContext | None = None,
              engine: Any = None, progress: ProgressCallback | None = None,
              cancel: Callable[[], bool] | None = None) -> tuple[list[SourceWord], bool]:
    """Cuvintele PDF-ului, pe pagini; (cuvinte, s-a folosit OCR). R-007, R-020,
    R-021."""
    from app.core.pdf import background
    from app.core.pdf.text import read_page_text

    if mode not in PDF_MODES:
        raise ValueError(f"mod necunoscut: {mode}")
    words: list[SourceWord] = []
    recognized = False
    total = document.page_count
    for number in range(1, total + 1):
        if cancel is not None and cancel():
            break
        if progress is not None:
            progress(Progress(number - 1, total, "stage.compare_reading", str(number)))
        layer = read_page_text(document._require_open(), number)
        has_text = any(not ch.isspace() for ch in layer.text)
        if mode == "ocr" or not has_text or (mode == "auto" and _looks_bad(layer.text)):
            layer = background._recognize_page(document, number, context=context,
                                               engine=engine, languages=languages)
            recognized = True
        words.extend(_page_words(layer.text, layer.boxes, number))
    if progress is not None:
        progress(Progress(total, total, "stage.compare_reading", ""))
    return join_hyphenated(mark_paragraphs(words)), recognized


# --- formatele editabile -----------------------------------------------------------------

Block = tuple[str, str]
"""(tip, text): `body`, `header`, `footer` sau `page` (pagina noua)."""


def _docx_blocks(path: Path) -> list[Block]:
    import docx
    from docx.oxml.ns import qn

    document = docx.Document(str(path))
    blocks: list[Block] = []
    if document.sections:
        section = document.sections[0]
        blocks += [("header", p.text) for p in section.header.paragraphs if p.text.strip()]
        blocks += [("footer", p.text) for p in section.footer.paragraphs if p.text.strip()]
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            if any(b.get(qn("w:type")) == "page" for b in child.iter(qn("w:br"))):
                blocks.append(("page", ""))
            blocks.append(("body", "".join(t.text or "" for t in child.iter(qn("w:t")))))
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                cells = ["".join(t.text or "" for t in cell.iter(qn("w:t")))
                         for cell in row.iter(qn("w:tc"))]
                blocks.append(("body", " ".join(c for c in cells if c)))
    return blocks


def _xlsx_blocks(path: Path) -> list[Block]:
    import openpyxl

    book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    blocks: list[Block] = []
    try:
        for index, sheet in enumerate(book.worksheets):
            if index:
                blocks.append(("page", ""))
            for row in sheet.iter_rows(values_only=True):
                cells = [str(v) for v in row if v is not None and str(v).strip()]
                if cells:
                    blocks.append(("body", " ".join(cells)))
    finally:
        book.close()
    return blocks


def _pptx_blocks(path: Path) -> list[Block]:
    from pptx import Presentation

    blocks: list[Block] = []
    for index, slide in enumerate(Presentation(str(path)).slides):
        if index:
            blocks.append(("page", ""))
        for shape in slide.shapes:
            if shape.has_text_frame:
                blocks += [("body", "".join(r.text for r in p.runs))
                           for p in shape.text_frame.paragraphs]
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    blocks.append(("body", " ".join(c.text for c in row.cells if c.text)))
    return blocks


_ODF_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_ODF_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_ODF_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_ODF_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_ODF_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
_ODF_PARAGRAPHS = {f"{{{_ODF_TEXT}}}p", f"{{{_ODF_TEXT}}}h"}


def _odf_text(node: ET.Element) -> str:
    parts: list[str] = [node.text or ""]
    for child in node:
        if child.tag == f"{{{_ODF_TEXT}}}s":
            parts.append(" " * int(child.get(f"{{{_ODF_TEXT}}}c", "1")))
        elif child.tag in (f"{{{_ODF_TEXT}}}tab", f"{{{_ODF_TEXT}}}line-break"):
            parts.append(" ")
        elif child.tag != f"{{{_ODF_TEXT}}}note":
            parts.append(_odf_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _odf_blocks(path: Path) -> list[Block]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            content = archive.read("content.xml")
            styles = archive.read("styles.xml") if "styles.xml" in names else b""
    except (zipfile.BadZipFile, KeyError) as exc:
        raise UnsupportedFormatError("fisierul OpenDocument nu se poate citi",
                                     path=str(path)) from exc
    blocks: list[Block] = []
    if styles:
        root = ET.fromstring(styles)
        for kind in ("header", "footer"):
            part = next(root.iter(f"{{{_ODF_STYLE}}}{kind}"), None)
            if part is not None:
                blocks += [(kind, _odf_text(p)) for p in part.iter(f"{{{_ODF_TEXT}}}p")
                           if _odf_text(p).strip()]
    root = ET.fromstring(content)
    state = {"first": True}

    def walk(node: ET.Element) -> None:
        for child in node:
            if child.tag in (f"{{{_ODF_DRAW}}}page", f"{{{_ODF_TABLE}}}table") and \
                    node.tag.startswith(f"{{{_ODF_OFFICE}}}"):  # foaie sau diapozitiv
                if not state["first"]:
                    blocks.append(("page", ""))
                state["first"] = False
            if child.tag == f"{{{_ODF_TABLE}}}table-row":
                cells = [_odf_text(p) for p in child.iter() if p.tag in _ODF_PARAGRAPHS]
                blocks.append(("body", " ".join(c for c in cells if c.strip())))
                continue
            if child.tag in _ODF_PARAGRAPHS:
                blocks.append(("body", _odf_text(child)))
                continue
            walk(child)

    body = root.find(f"{{{_ODF_OFFICE}}}body")
    walk(body if body is not None else root)
    return blocks


class _HtmlText(html.parser.HTMLParser):
    BLOCKS: ClassVar[set[str]] = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "title",
              "section", "article", "table", "ul", "ol", "blockquote", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _decode(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1250", errors="replace")


def _html_blocks(path: Path) -> list[Block]:
    raw = path.read_bytes()
    match = re.search(rb"charset=[\"']?([A-Za-z0-9_-]+)", raw[:2048])
    try:
        text = raw.decode(match.group(1).decode("ascii")) if match else _decode(raw)
    except (LookupError, UnicodeDecodeError):
        text = _decode(raw)
    parser = _HtmlText()
    parser.feed(text)
    parser.close()
    lines = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts)).split("\n")
    return [("body", line.strip()) for line in lines if line.strip()]


_RTF_SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer",
             "headerl", "headerr", "footerl", "footerr", "listtable", "listoverridetable",
             "rsidtbl", "generator", "themedata", "colorschememapping", "datastore",
             "latentstyles", "xmlnstbl", "object", "fldinst"}


def rtf_text(data: str) -> str:
    """Textul unui fisier RTF: grupurile de destinatie (`{\\*...}`, fonturi, culori,
    stiluri, imagini) se sar; `\\par` si `\\line` dau rand nou; `\\'hh` (cp1252) si
    `\\uN` dau caracterele."""
    out: list[str] = []
    stack: list[bool] = []
    skip = False
    pending_uc = 0
    i, n = 0, len(data)
    while i < n:
        ch = data[i]
        if ch == "{":
            stack.append(skip)
            i += 1
            continue
        if ch == "}":
            skip = stack.pop() if stack else False
            i += 1
            continue
        if ch in "\r\n":
            i += 1
            continue
        if ch != "\\":
            if pending_uc:  # caracterul de rezerva de dupa \uN
                pending_uc -= 1
            elif not skip:
                out.append(ch)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        nxt = data[i]
        if nxt == "*":
            skip = True
            i += 1
            continue
        if nxt == "'":
            hexa = data[i + 1:i + 3]
            i += 3
            if pending_uc:
                pending_uc -= 1
            elif not skip:
                try:
                    out.append(bytes([int(hexa, 16)]).decode("cp1252", errors="replace"))
                except ValueError:
                    pass
            continue
        if not nxt.isalpha():
            if not skip and nxt in "\\{}":
                out.append(nxt)
            elif not skip and nxt == "~":
                out.append(" ")
            i += 1
            continue
        match = re.match(r"([a-zA-Z]+)(-?\d+)? ?", data[i:])
        if match is None:
            i += 1
            continue
        word, arg = match.group(1), match.group(2)
        i += match.end()
        if word in _RTF_SKIP:
            skip = True
        elif skip:
            continue
        elif word in ("par", "line", "row", "sect", "page"):
            out.append("\n")
        elif word in ("tab", "cell"):
            out.append(" ")
        elif word == "u" and arg is not None:
            code = int(arg)
            out.append(chr(code + 65536 if code < 0 else code))
            pending_uc = 1
    return "".join(out)


def _rtf_blocks(path: Path) -> list[Block]:
    text = rtf_text(path.read_bytes().decode("latin-1"))
    return [("body", line.strip()) for line in text.split("\n") if line.strip()]


def _txt_blocks(path: Path) -> list[Block]:
    blocks: list[Block] = []
    for part_index, part in enumerate(_decode(path.read_bytes()).split("\f")):
        if part_index:
            blocks.append(("page", ""))
        blocks += [("body", line) for line in part.splitlines()]
    return blocks


READERS: dict[str, Callable[[Path], list[Block]]] = {
    ".docx": _docx_blocks, ".xlsx": _xlsx_blocks, ".pptx": _pptx_blocks, ".odt": _odf_blocks,
    ".ods": _odf_blocks, ".odp": _odf_blocks, ".rtf": _rtf_blocks, ".htm": _html_blocks,
    ".html": _html_blocks, ".txt": _txt_blocks,
}


def editable_blocks(path: Path) -> list[Block]:
    """Textul unui format editabil, pe paragrafe, cu antetele si subsolurile."""
    reader = READERS.get(Path(path).suffix.lower())
    if reader is None:
        raise UnsupportedFormatError("formatul nu se poate compara", path=str(path))
    try:
        return reader(Path(path))
    except (UnsupportedFormatError, FileNotFoundError):
        raise
    except Exception as exc:  # fisierul stricat devine eroare de format
        raise UnsupportedFormatError("fisierul nu se poate citi", path=str(path)) from exc


def blocks_to_pdf(blocks: Sequence[Block]) -> bytes:
    """Un PDF simplu din paragrafe: A4, fontul de sistem cu diacritice; antetele
    si subsolurile se repeta pe fiecare pagina, ca in documentul original."""
    import pikepdf

    from app.core.pdf.embedded_font import embed_text_font, wrap

    pdf = pikepdf.new()
    font = embed_text_font(pdf, [t for _k, t in blocks if t] or [" "])
    width, height = PAGE_SIZE
    headers = [t for k, t in blocks if k == "header"]
    footers = [t for k, t in blocks if k == "footer"]
    line_height = FONT_SIZE * 1.35
    top = height - MARGIN - (len(headers) * HEADER_SIZE * 1.4 + 6 if headers else 0)
    bottom = MARGIN + (len(footers) * HEADER_SIZE * 1.4 + 6 if footers else 0)
    pages: list[list[str]] = [[]]
    y = top

    def emit(text: str, x: float, at: float, size: float) -> str:
        return f"BT /F1 {size:g} Tf 1 0 0 1 {x:.2f} {at:.2f} Tm {font.encode(text)} Tj ET"

    for kind, text in blocks:
        if kind == "page":
            if pages[-1]:
                pages.append([])
                y = top
            continue
        if kind != "body":
            continue
        for line in wrap(font, text, FONT_SIZE, width - 2 * MARGIN) if text.strip() else []:
            if y - line_height < bottom:
                pages.append([])
                y = top
            y -= line_height
            pages[-1].append(emit(line, MARGIN, y, FONT_SIZE))
        y -= FONT_SIZE * 0.6  # spatiul dintre paragrafe
    for ops in pages:
        ops[:0] = [emit(text, MARGIN, height - MARGIN - (i + 1) * HEADER_SIZE * 1.4,
                        HEADER_SIZE) for i, text in enumerate(headers)]
        for i, text in enumerate(footers):
            ops.append(emit(text, MARGIN, MARGIN + (len(footers) - 1 - i) * HEADER_SIZE * 1.4,
                            HEADER_SIZE))
        page = pdf.add_blank_page(page_size=PAGE_SIZE)
        page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font))
        page.obj.Contents = pdf.make_stream((" ".join(ops) or " ").encode("ascii"))
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


# --- intrarea: orice sursa ------------------------------------------------------------------


def load_source(path: Path, *, mode: str = "text", languages: Sequence[str] | None = None,
                password: Callable[[str], str | None] | None = None,
                context: AppContext | None = None, engine: Any = None,
                progress: ProgressCallback | None = None,
                cancel: Callable[[], bool] | None = None) -> SourceDocument:
    """R-002, R-005, R-007: sursa ca PDF si cuvinte. `NoTextFoundError` daca nici
    dupa OCR nu are text (R-007)."""
    from app.core.export.base import ExportOptions
    from app.core.pdf.document import PdfDocument

    path = Path(path)
    _check(path)
    ext = path.suffix.lower()
    converted = False
    if ext in PDF_EXTENSIONS:
        document = PdfDocument.open(path, password=password)
    elif ext in EDITABLE_EXTENSIONS:
        document = PdfDocument._from_bytes(blocks_to_pdf(editable_blocks(path)), None)
        converted = True
    else:
        document = PdfDocument.from_images([path], options=ExportOptions(searchable=False),
                                           context=context, engine=engine)
        mode = "ocr"
    try:
        words, recognized = pdf_words(document, mode=mode, languages=languages,
                                      context=context, engine=engine, progress=progress,
                                      cancel=cancel)
    except Exception:
        document.close()
        raise
    if not words:
        document.close()
        raise NoTextFoundError("documentul nu are text de comparat", path=str(path))
    return SourceDocument(path, document, words, recognized, converted)
