"""Tipurile de date ale nucleului.

Implementeaza SPEC_05_api_core.py, sectiunile 0 (tipuri elementare),
1 (enumerari) si 3 (modelul de date). Numele, campurile si semnaturile sunt
cele din contract; nu se redenumesc.

Valorile enumerarilor sunt exact cele din schema bazei de date (SPEC_04).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# =============================================================================
# 0. TIPURI ELEMENTARE
# =============================================================================

Px = int
"""Pixel de imagine. Intreg. Origine stanga-sus."""

Point = tuple[Px, Px]
Polygon = Sequence[Point]
LanguageCode = str
"""Cod de limba de recunoastere: 'ron', 'eng', 'ron_moldavia'."""

ProgressCallback = Callable[["Progress"], None]
"""Apelat din firul de lucru. Nucleul nu stie nimic despre fire de UI."""

CancelToken = Callable[[], bool]
"""Intoarce True cand operatia trebuie oprita. Verificat intre pagini
(N-026, A-028)."""

PasswordCallback = Callable[[str], "str | None"]
"""Primeste calea fisierului, intoarce parola sau None (A-011, K-002)."""


# SPEC_05 sect. 0 — Rect. M-009 (suprapunere), M-041 (scalare sablon)
@dataclass(frozen=True, slots=True)
class Rect:
    x: Px
    y: Px
    w: Px
    h: Px

    @property
    def right(self) -> Px:
        """Prima coloana din afara dreptunghiului (exclusiv)."""
        return self.x + self.w

    @property
    def bottom(self) -> Px:
        """Primul rand din afara dreptunghiului (exclusiv)."""
        return self.y + self.h

    # M-009: doua zone care doar se ating pe o latura nu se suprapun.
    def intersects(self, other: Rect) -> bool:
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )

    def contains(self, point: Point) -> bool:
        px, py = point
        return self.x <= px < self.right and self.y <= py < self.bottom

    # M-041: incarcarea unui sablon pe o pagina de alta dimensiune.
    def scaled(self, factor: float) -> Rect:
        if factor <= 0:
            raise ValueError(f"factorul de scalare trebuie sa fie pozitiv: {factor}")
        x = round(self.x * factor)
        y = round(self.y * factor)
        # Se scaleaza marginile, nu latimea, ca zonele alaturate sa ramana lipite.
        return Rect(x, y, round(self.right * factor) - x, round(self.bottom * factor) - y)


# SPEC_05 sect. 0 — Progress
@dataclass(frozen=True, slots=True)
class Progress:
    """Starea unei operatii lungi. Trimis catre `ProgressCallback`."""

    current: int
    total: int
    stage: str
    """Cheie de traducere, nu text afisabil: 'stage.recognizing'."""
    detail: str = ""
    """Numele fisierului sau al paginii curente. Text, nu cheie."""
    indeterminate: bool = False


# =============================================================================
# 1. ENUMERARI
# =============================================================================


# SPEC_04 page.status
class PageStatus(str, Enum):
    IMPORTED = "imported"
    PREPROCESSED = "preprocessed"
    ANALYZED = "analyzed"
    RECOGNIZED = "recognized"
    VERIFIED = "verified"
    ERROR = "error"


# M-001..M-006
class AreaType(str, Enum):
    RECOGNITION = "recognition"  # M-001
    TEXT = "text"  # M-002
    TABLE = "table"  # M-003
    PICTURE = "picture"  # M-004
    BACKGROUND_PICTURE = "background_picture"  # M-005
    BARCODE = "barcode"  # M-006


# M-026. Valabil doar pentru zone de tip TEXT.
class TextFunction(str, Enum):
    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    CAPTION = "caption"


# SPEC_04 area.orientation
class Orientation(str, Enum):
    AUTO = "auto"
    DEG_0 = "0"
    DEG_90 = "90"
    DEG_180 = "180"
    DEG_270 = "270"


# M-028, N-013..N-015
class PrintType(str, Enum):
    AUTO = "auto"
    TYPEWRITER = "typewriter"
    FAX = "fax"


# SPEC_04 page.color_mode
class ColorMode(str, Enum):
    BW = "bw"
    GRAY = "gray"
    COLOR = "color"


# N-011, N-012
class OcrQuality(str, Enum):
    THOROUGH = "thorough"  # N-011
    FAST = "fast"  # N-012


# N-008
class PdfRecognitionMode(str, Enum):
    AUTO = "auto"  # N-009, N-010
    FORCE_OCR = "ocr"
    TEXT_ONLY = "text"


# Q-001..Q-006
class LayoutMode(str, Enum):
    EXACT = "exact"
    EDITABLE = "editable"
    FORMATTED = "formatted"
    PLAIN = "plain"
    FLEXIBLE = "flexible"


# Q-001..Q-006 — formatele de export si matricea mod -> formate
class ExportFormat(str, Enum):
    PDF = "pdf"
    PDFA = "pdfa"
    PDFUA = "pdfua"
    DOCX = "docx"
    RTF = "rtf"
    ODT = "odt"
    XLSX = "xlsx"
    CSV = "csv"
    PPTX = "pptx"
    TXT = "txt"
    HTML = "html"
    EPUB = "epub"
    FB2 = "fb2"
    DJVU = "djvu"
    TIFF = "tiff"
    JPEG = "jpeg"
    PNG = "png"
    JBIG2 = "jbig2"

    # Q-002..Q-006: interfata dezactiveaza restul (Q-001), CLI-ul raspunde
    # cu IncompatibleLayoutError (U-006).
    @staticmethod
    def allowed_for(mode: LayoutMode) -> frozenset[ExportFormat]:
        return _ALLOWED_FORMATS[LayoutMode(mode)]


_F = ExportFormat
_FORMATTED = frozenset(
    {_F.RTF, _F.DOCX, _F.XLSX, _F.TXT, _F.HTML, _F.ODT, _F.FB2, _F.EPUB}
)
_ALLOWED_FORMATS: dict[LayoutMode, frozenset[ExportFormat]] = {
    LayoutMode.EXACT: frozenset({_F.RTF, _F.DOCX, _F.PDF, _F.PPTX, _F.ODT, _F.DJVU}),  # Q-002
    LayoutMode.EDITABLE: frozenset({_F.RTF, _F.DOCX, _F.ODT}),  # Q-003
    LayoutMode.FORMATTED: _FORMATTED,  # Q-004
    LayoutMode.PLAIN: _FORMATTED | {_F.CSV},  # Q-005
    LayoutMode.FLEXIBLE: frozenset({_F.HTML}),  # Q-006
}
del _F, _FORMATTED


# SPEC_05 sect. 1
class PdfAVersion(str, Enum):
    A1A = "1a"
    A1B = "1b"
    A2A = "2a"
    A2B = "2b"
    A2U = "2u"
    A3A = "3a"
    A3B = "3b"
    A3U = "3u"


# A-025
class ImageQuality(str, Enum):
    BEST = "best"
    BALANCED = "balanced"
    COMPACT = "compact"
    CUSTOM = "custom"


# SPEC_04 annotation.annotation_type
class AnnotationType(str, Enum):
    NOTE = "note"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    INSERT_TEXT = "insert_text"
    INK = "ink"
    LINE = "line"
    ARROW = "arrow"
    RECTANGLE = "rectangle"
    OVAL = "oval"
    POLYGON = "polygon"
    CLOUD = "cloud"
    POLYLINE = "polyline"
    TEXT_BOX = "text_box"
    STAMP = "stamp"
    REDACTION = "redaction"
    LINK = "link"
    SIGNATURE = "signature"


# D-031
class ReviewStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# H-006..H-031
class FormFieldType(str, Enum):
    TEXT = "text"  # H-006
    CHECKBOX = "checkbox"  # H-007
    RADIO = "radio"  # H-013
    DROPDOWN = "dropdown"  # H-031
    LISTBOX = "listbox"  # H-010
    BUTTON = "button"  # H-011
    SIGNATURE = "signature"  # H-012


# G-003
class PrintPermission(str, Enum):
    NONE = "none"
    LOW_RES = "low"
    HIGH_RES = "high"


# G-007. RC4 doar la citire, niciodata la scriere.
class EncryptionLevel(str, Enum):
    AES_128 = "aes128"
    AES_256 = "aes256"


# SPEC_04 comparison_difference.diff_type
class DiffType(str, Enum):
    INSERTED = "inserted"
    DELETED = "deleted"
    REPLACED = "replaced"
    FORMATTING = "formatting"


# L-011..L-023, L-033 si setarile X-023..X-029. ID-urile reale din SPEC_02 si
# SPEC_03; SPEC_05 foloseste numerotarea veche (docs/plan/faza_2_pasi.md).
class PreprocessOp(str, Enum):
    DESKEW = "deskew"  # L-011
    STRAIGHTEN_LINES = "straighten_lines"  # L-012
    PHOTO_CORRECTION = "photo_correction"  # L-013
    TRAPEZOID = "trapezoid"  # L-014
    ROTATE = "rotate"  # L-015
    FLIP = "flip"  # L-015
    SPLIT = "split"  # L-016
    CROP = "crop"  # L-017
    INVERT = "invert"  # L-018
    RESOLUTION = "resolution"  # L-019
    BRIGHTNESS_CONTRAST = "brightness_contrast"  # L-020
    LEVELS = "levels"  # L-021
    ERASE = "erase"  # L-022
    REMOVE_COLOR_MARKS = "remove_color_marks"  # L-023
    DENOISE = "denoise"  # X-025
    DEBLUR = "deblur"  # X-026
    WHITEN_BACKGROUND = "whiten_background"  # X-024
    DETECT_EDGES = "detect_edges"  # X-023
    TO_BW = "to_bw"  # L-033, X-029


# X-010
class AutoProcessMode(str, Enum):
    READ = "read"
    ANALYZE_AND_READ = "analyze_and_read"
    PREPROCESS_ONLY = "preprocess_only"
    NONE = "none"


# =============================================================================
# 3. MODELUL DE DATE
# Oglindeste SPEC_04. Obiectele sunt mutabile; persistenta e in repository.
# =============================================================================


def _empty_rect() -> Rect:
    return Rect(0, 0, 0, 0)


# SPEC_04 word. N-022 (incredere per cuvant), N-023 (prag de nesiguranta)
@dataclass(slots=True)
class WordData:
    id: int | None
    text: str
    confidence: float
    """0..100, per cuvant (N-022)."""
    char_confidences: tuple[float, ...] = ()
    bbox: Rect = field(default_factory=_empty_rect)
    is_uncertain: bool = False
    """True cand confidence < pragul din setari (N-023, implicit 70)."""
    in_dictionary: bool = False
    original_text: str | None = None
    is_edited: bool = False
    is_verified: bool = False
    is_redacted: bool = False
    font_name: str | None = None
    font_size: float | None = None
    is_bold: bool | None = None
    is_italic: bool | None = None
    is_underline: bool | None = None
    is_superscript: bool | None = None
    is_subscript: bool | None = None
    text_color: str | None = None
    language_code: LanguageCode | None = None


# SPEC_04 text_line. R-035 (cratima de final de rand)
@dataclass(slots=True)
class LineData:
    id: int | None
    words: list[WordData] = field(default_factory=list)
    bbox: Rect = field(default_factory=_empty_rect)
    baseline_y: Px | None = None
    ends_with_hyphen: bool = False
    """R-035, si exportul: cuvantul despartit se reunifica."""

    @property
    def text(self) -> str:
        """Cuvintele randului, separate prin spatiu, in ordinea din lista.

        Cratima de final ramane in text; reunificarea cuvantului despartit
        (R-035) e treaba exportului si a compararii, nu a modelului.
        """
        return " ".join(w.text for w in self.words)


# SPEC_05 sect. 8, SPEC_04 text_style. O-035..O-041
@dataclass(slots=True)
class TextStyle:
    name: str
    font_name: str | None = None
    font_size: float | None = None
    horizontal_scale: float = 100.0
    letter_spacing: float = 0.0
    is_bold: bool = False
    is_italic: bool = False
    is_underline: bool = False
    is_smallcaps: bool = False
    text_color: str | None = None
    background_color: str | None = None
    heading_level: int = 0
    """O-041: 0 = fara rol, 1..10 = Heading 1..10. Valorile peste 0 genereaza
    semne de carte la exportul in PDF, cand optiunea e activa."""
    is_builtin: bool = False


# SPEC_04 text_block
@dataclass(slots=True)
class BlockData:
    id: int | None
    block_type: str = "paragraph"
    lines: list[LineData] = field(default_factory=list)
    bbox: Rect = field(default_factory=_empty_rect)
    style_name: str | None = None
    list_level: int | None = None
    alignment: str | None = None
    direction: str = "ltr"

    @property
    def text(self) -> str:
        """Randurile blocului, separate prin linie noua."""
        return "\n".join(line.text for line in self.lines)


# SPEC_04 table_cell. M-048 (celula ca imagine)
@dataclass(slots=True)
class TableCellData:
    id: int | None
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    bbox: Rect = field(default_factory=_empty_rect)
    as_picture: bool = False
    """M-048."""
    is_header: bool = False
    blocks: list[BlockData] = field(default_factory=list)


# SPEC_05 sect. 10: adnotarile PDF (D-001…D-052)
@dataclass(slots=True)
class AnnotationData:
    id: int | None
    annot_type: AnnotationType
    page_number: int
    geometry: Mapping[str, Any]
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    author: str | None = None
    subject: str | None = None
    content: str | None = None
    color: str | None = None
    fill_color: str | None = None
    opacity: float = 1.0
    line_width: float | None = None
    """D-016: intre 0,5 si 12 pt."""
    review_status: ReviewStatus | None = None
    is_checked: bool = False
    parent_id: int | None = None
    replies: list[AnnotationData] = field(default_factory=list)
    created_at: str = ""
    modified_at: str = ""


# SPEC_05 sect. 10: campurile de formular (H-001…H-058). Un obiect = un widget
# de pe pagina: copiile legate (H-016) au acelasi `field_name` si `linked_to`
# setat; butoanele radio (H-033) au numele butonului in `field_name` si grupul
# in `group_name`.
@dataclass(slots=True)
class FormFieldData:
    id: int | None
    field_name: str
    field_type: FormFieldType
    page_number: int
    rect: Rect
    tooltip: str | None = None
    is_required: bool = False
    is_readonly: bool = False
    units: str = "cm"
    fill_color: str | None = None
    border_color: str | None = None
    border_width: float | None = None
    font_name: str | None = None
    font_size: float | None = None
    text_color: str | None = None
    check_color: str | None = None
    text_format: str | None = None
    date_format: str | None = None
    is_multiline: bool = False
    max_symbols: int | None = None
    group_name: str | None = None
    allow_custom: bool = False
    allow_multiple: bool = False
    linked_to: str | None = None
    items: list[tuple[str, str | None, bool]] = field(default_factory=list)
    """(text, valoare, e implicit)."""
    actions: list[tuple[str, str, Mapping[str, Any]]] = field(default_factory=list)
    """(eveniment, tip de actiune, parametri)."""
    value: str | None = None


# SPEC_05 sect. 12: compararea documentelor (R-001…R-068)
@dataclass(slots=True)
class Difference:
    order_index: int
    diff_type: DiffType
    text_left: str | None
    text_right: str | None
    page_left: int | None
    page_right: int | None
    bbox_left: Rect | None = None
    bbox_right: Rect | None = None
    is_ignored: bool = False
    group: str = "body"
    """R-034: `body`, `headers_footers` sau `numbering` (adaugat fata de SPEC_05)."""
    rects_left: list[tuple[int, Rect]] = field(default_factory=list)
    """Toate dreptunghiurile diferentei, (pagina, dreptunghi), pentru evidentiere
    (R-413); `bbox_left` e primul (adaugat fata de SPEC_05)."""
    rects_right: list[tuple[int, Rect]] = field(default_factory=list)


@dataclass(slots=True)
class CompareOptions:
    """R-008, R-015, R-016, R-020, R-022, R-033 (SPEC_05: R-008, R-023…R-033)."""

    languages: tuple[LanguageCode, ...] = ("ron", "eng")
    ignore_whitespace: bool = True
    ignore_hyphenation: bool = True
    ignore_tables: bool = False
    ignore_headers_footers: bool = False
    group_distance_words: int = 3
    """R-034: diferentele din acelasi paragraf, la mai putin de atatea cuvinte
    una de alta, se unesc."""
    find_punctuation: bool = False
    """R-015 `Find differences in punctuation` (adaugat fata de SPEC_05)."""
    find_one_letter: bool = False
    """R-016 `Find one-letter differences` (adaugat fata de SPEC_05)."""
    pdf_mode: str = "text"
    """R-020: `text` (`Use Only Text from PDF`), `auto` sau `ocr`."""
    find_headers_footers: bool = True
    """R-022 `Find Headers and Footers Automatically`."""


# SPEC_05 sect. 10: semnele de carte (B-021, F-042…F-046)
@dataclass(slots=True)
class BookmarkData:
    id: int | None
    title: str
    level: int = 1
    target_page: int | None = None
    target_y: Px | None = None
    children: list[BookmarkData] = field(default_factory=list)
    generated_from_style: str | None = None


# SPEC_04 table_cell (structura tabelului)
@dataclass(slots=True)
class TableData:
    rows: int
    cols: int
    cells: list[TableCellData] = field(default_factory=list)
    h_separators: list[Px] = field(default_factory=list)
    v_separators: list[Px] = field(default_factory=list)

    def cell_at(self, row: int, col: int) -> TableCellData | None:
        """Celula care acopera pozitia (row, col), tinand cont de celulele unite.

        Intoarce None in afara tabelului sau daca pozitia nu e acoperita.
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return None
        for cell in self.cells:
            if (
                cell.row <= row < cell.row + cell.row_span
                and cell.col <= col < cell.col + cell.col_span
            ):
                return cell
        return None


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Testul razei (even-odd). Punctele de pe margine nu sunt garantate."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


# SPEC_04 area. M-013 (zona devine poligon), M-025, M-026
@dataclass(slots=True)
class AreaData:
    id: int | None
    area_type: AreaType
    polygon: Polygon
    order_index: int
    bbox: Rect = field(default_factory=_empty_rect)
    language_codes: tuple[LanguageCode, ...] | None = None
    """M-025: None inseamna limbile proiectului."""
    text_function: TextFunction | None = None
    """M-026: doar pentru AreaType.TEXT."""
    orientation: Orientation = Orientation.AUTO
    print_type: PrintType = PrintType.AUTO
    is_inverted: bool = False
    cjk_direction: str | None = None
    barcode_type: str | None = None
    barcode_value: str | None = None
    blocks: list[BlockData] = field(default_factory=list)
    table: TableData | None = None
    """Prezent doar la AreaType.TABLE."""

    # M-013: dupa `Add area part` / `Cut area part` zona nu mai e dreptunghi.
    @property
    def is_polygon(self) -> bool:
        """True cand conturul nu e simplu dreptunghiul `bbox`.

        Un contur gol sau cele 4 colturi ale lui `bbox` (in orice ordine)
        inseamna zona dreptunghiulara.
        """
        if len(self.polygon) == 0:
            return False
        b = self.bbox
        corners = {(b.x, b.y), (b.right, b.y), (b.right, b.bottom), (b.x, b.bottom)}
        return {tuple(p) for p in self.polygon} != corners


def _area_blocks(area: AreaData) -> Iterator[BlockData]:
    """Blocurile unei zone: direct, apoi din celulele tabelului, rand cu rand."""
    yield from area.blocks
    if area.table is not None:
        for cell in sorted(area.table.cells, key=lambda c: (c.row, c.col)):
            yield from cell.blocks


# SPEC_04 page_warning
@dataclass(slots=True)
class PageWarning:
    severity: str
    code: str
    message_key: str
    """Cheie de traducere: 'warning.low_resolution'."""
    params: Mapping[str, Any] = field(default_factory=dict)
    is_dismissed: bool = False


# SPEC_04 page. M-022 (ordinea zonelor), E-026 (pagina goala)
@dataclass(slots=True)
class PageData:
    id: int | None
    page_number: int
    image_path: Path
    original_path: Path
    width_px: Px
    height_px: Px
    dpi_x: int
    dpi_y: int
    color_mode: ColorMode
    rotation: int = 0
    status: PageStatus = PageStatus.IMPORTED
    source_file: Path | None = None
    source_page: int | None = None
    areas: list[AreaData] = field(default_factory=list)
    warnings: list[PageWarning] = field(default_factory=list)
    skew_angle: float | None = None
    estimated_dpi: int | None = None
    blank_score: float | None = None
    """E-026: 0 = plina, 1 = complet goala."""
    avg_confidence: float | None = None
    uncertain_count: int = 0
    applied_operations: list[tuple[PreprocessOp, Mapping[str, Any]]] = field(
        default_factory=list
    )

    def _ordered_areas(self) -> list[AreaData]:
        return sorted(self.areas, key=lambda a: a.order_index)

    # M-022: textul paginii in ordinea zonelor, nu in ordinea din lista.
    @property
    def text(self) -> str:
        """Textul paginii in ordinea zonelor (M-022).

        Blocurile se separa prin linie noua. Cuvintele redactate nu apar
        (aceeasi regula ca vederea v_page_text din SPEC_04, folosita la G-029).
        """
        parts: list[str] = []
        for area in self._ordered_areas():
            for block in _area_blocks(area):
                lines = [
                    " ".join(w.text for w in line.words if not w.is_redacted)
                    for line in block.lines
                ]
                parts.append("\n".join(lines))
        return "\n".join(parts)

    def iter_words(self) -> Iterator[WordData]:
        """Toate cuvintele paginii, in ordinea zonelor, blocurilor si randurilor."""
        for area in self._ordered_areas():
            for block in _area_blocks(area):
                for line in block.lines:
                    yield from line.words

    def area_at(self, point: Point) -> AreaData | None:
        """Zona care contine punctul. Zonele nu se suprapun (M-009), deci
        rezultatul e unic; la date incoerente castiga prima in ordinea zonelor."""
        for area in self._ordered_areas():
            if not area.bbox.contains(point):
                continue
            if area.is_polygon and not _point_in_polygon(point, area.polygon):
                continue
            return area
        return None
