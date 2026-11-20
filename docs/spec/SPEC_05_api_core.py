#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPECIFICATIE 05 - API-UL PACHETULUI CORE
Alternativa desktop la ABBYY FineReader PDF

CE ESTE ACEST FISIER
    Contractul complet al nucleului, scris in Python ca sa fie verificabil:
    tipuri, enumerari, excepții, protocoale si semnaturile tuturor functiilor
    publice. Corpurile sunt goale (`...`). Nu e cod de productie si nu face
    nimic la rulare - e specificatia pe care o implementeaza programatorul,
    fisier cu fisier.

    Fiecare semnatura poarta ID-ul cerintei din SPEC_01, SPEC_02 si SPEC_03.
    Cine implementeaza o functie citeste cerinta cu acel ID si acolo gaseste
    validarile, rezultatul si erorile.

REGULA DE ARHITECTURA, NENEGOCIABILA
    `core` nu importa niciodata `gui`. Nucleul nu stie ca exista o interfata.
    Comunicarea catre interfata se face prin callback-uri de progres si prin
    excepții, nu prin dialoguri.

STRUCTURA PACHETULUI (asa se vor numi fisierele reale)
    app/
      core/
        model.py          tipurile de date din acest fisier
        errors.py         excepțiile
        settings.py       SettingsStore
        project.py        OcrProject
        images/
          loader.py       ImageLoader
          preprocess.py   PreprocessPipeline + uneltele L-001..L-034
          scanner.py      ScannerService
        layout/
          analyzer.py     LayoutAnalyzer
          tables.py       TableAnalyzer
        ocr/
          engine.py       OcrEngine (protocol) + implementari
          languages.py    LanguageRegistry
          patterns.py     PatternStore
          dictionary.py   DictionaryService
        pdf/
          document.py     PdfDocument
          editor.py       PdfContentEditor
          forms.py        FormEditor
          security.py     SecurityService
          signature.py    SignatureService
          organize.py     PageOrganizer
        export/
          base.py         Exporter (protocol) + ExportOptions
          pdf_exporter.py docx_exporter.py xlsx_exporter.py ...
        compare/
          engine.py       DocumentComparer
        automation/
          tasks.py        AutomatedTaskRunner
          hotfolder.py    HotFolderService
        fonts.py          FontMatcher
      gui/                nu apare in acest fisier
      cli/                main.py, foloseste doar core

CONVENȚII
    - toate coordonatele sunt in pixeli de imagine, origine stanga-sus
    - toate operatiile lungi primesc `progress` si `cancel`
    - nicio functie din core nu afiseaza nimic si nu citeste de la tastatura
    - nicio functie din core nu face cereri de retea (Y-001)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Protocol,
    Sequence,
    runtime_checkable,
)

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
"""Apelat din firul de lucru. Implementarea din GUI trebuie sa marsaleze
singura catre firul de interfata. Nucleul nu stie nimic despre fire de UI."""

CancelToken = Callable[[], bool]
"""Intors True cand operatia trebuie oprita. Operatiile verifica token-ul
intre pagini, nu in mijlocul unei pagini (N-026, A-028)."""

PasswordCallback = Callable[[str], str | None]
"""Primeste calea fisierului, intoarce parola sau None pentru renuntare.
Nucleul nu deschide dialoguri; cere parola prin acest callback (A-011, K-002).
Apelantul e responsabil de limita de 3 incercari."""


@dataclass(frozen=True, slots=True)
class Rect:
    x: Px
    y: Px
    w: Px
    h: Px

    @property
    def right(self) -> Px: ...
    @property
    def bottom(self) -> Px: ...
    def intersects(self, other: Rect) -> bool:
        """M-009: folosit la verificarea suprapunerii zonelor."""
        ...
    def contains(self, point: Point) -> bool: ...
    def scaled(self, factor: float) -> Rect:
        """M-041: la incarcarea unui sablon pe o pagina de alta dimensiune."""
        ...


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
# Valorile sunt exact cele din schema bazei de date (SPEC_04).
# =============================================================================


class PageStatus(str, Enum):
    IMPORTED = "imported"
    PREPROCESSED = "preprocessed"
    ANALYZED = "analyzed"
    RECOGNIZED = "recognized"
    VERIFIED = "verified"
    ERROR = "error"


class AreaType(str, Enum):
    RECOGNITION = "recognition"          # M-001
    TEXT = "text"                        # M-002
    TABLE = "table"                      # M-003
    PICTURE = "picture"                  # M-004
    BACKGROUND_PICTURE = "background_picture"  # M-005
    BARCODE = "barcode"                  # M-006


class TextFunction(str, Enum):
    """M-026. Valabil doar pentru zone de tip TEXT."""

    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    CAPTION = "caption"


class Orientation(str, Enum):
    AUTO = "auto"
    DEG_0 = "0"
    DEG_90 = "90"
    DEG_180 = "180"
    DEG_270 = "270"


class PrintType(str, Enum):
    """M-028, N-013..N-015."""

    AUTO = "auto"
    TYPEWRITER = "typewriter"
    FAX = "fax"


class ColorMode(str, Enum):
    BW = "bw"
    GRAY = "gray"
    COLOR = "color"


class OcrQuality(str, Enum):
    THOROUGH = "thorough"    # N-011
    FAST = "fast"            # N-012


class PdfRecognitionMode(str, Enum):
    """N-008. Decide dacă se foloseste stratul de text existent sau OCR."""

    AUTO = "auto"            # N-009, N-010 (Pull & Recognize)
    FORCE_OCR = "ocr"
    TEXT_ONLY = "text"


class LayoutMode(str, Enum):
    """Q-001..Q-006. Modul limiteaza formatele de export - vezi
    `ExportFormat.allowed_for()`. Aceasta e una dintre regulile care nu apar in
    documentatie si care au fost citite din interfata."""

    EXACT = "exact"
    EDITABLE = "editable"
    FORMATTED = "formatted"
    PLAIN = "plain"
    FLEXIBLE = "flexible"


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

    @staticmethod
    def allowed_for(mode: LayoutMode) -> frozenset[ExportFormat]:
        """Q-002..Q-006. Matricea completa:

        EXACT     -> RTF, DOCX, PDF, PPTX, ODT, DJVU
        EDITABLE  -> RTF, DOCX, ODT
        FORMATTED -> RTF, DOCX, XLSX, TXT, HTML, ODT, FB2, EPUB
        PLAIN     -> RTF, DOCX, XLSX, TXT, CSV, HTML, ODT, FB2, EPUB
        FLEXIBLE  -> HTML

        Interfata dezactiveaza formatele care nu apar in set (Q-001);
        CLI-ul raspunde cu `IncompatibleLayoutError` (U-006).
        """
        ...


class PdfAVersion(str, Enum):
    A1A = "1a"
    A1B = "1b"
    A2A = "2a"
    A2B = "2b"
    A2U = "2u"
    A3A = "3a"
    A3B = "3b"
    A3U = "3u"


class ImageQuality(str, Enum):
    BEST = "best"            # A-025
    BALANCED = "balanced"
    COMPACT = "compact"
    CUSTOM = "custom"


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


class ReviewStatus(str, Enum):
    """D-031."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class FormFieldType(str, Enum):
    TEXT = "text"            # H-006
    CHECKBOX = "checkbox"    # H-007
    RADIO = "radio"          # H-013
    DROPDOWN = "dropdown"    # H-031
    LISTBOX = "listbox"      # H-010
    BUTTON = "button"        # H-011
    SIGNATURE = "signature"  # H-012


class PrintPermission(str, Enum):
    """G-003."""

    NONE = "none"
    LOW_RES = "low"
    HIGH_RES = "high"


class EncryptionLevel(str, Enum):
    """G-007. RC4 doar la citire, niciodata la scriere."""

    AES_128 = "aes128"
    AES_256 = "aes256"


class DiffType(str, Enum):
    INSERTED = "inserted"
    DELETED = "deleted"
    REPLACED = "replaced"
    FORMATTING = "formatting"


class PreprocessOp(str, Enum):
    """L-001..L-034. Fiecare valoare are o unealta inregistrata in registru."""

    DESKEW = "deskew"                        # L-002
    STRAIGHTEN_LINES = "straighten_lines"    # L-003
    PHOTO_CORRECTION = "photo_correction"    # L-004
    TRAPEZOID = "trapezoid"                  # L-014
    ROTATE = "rotate"                        # L-015
    FLIP = "flip"                            # L-015
    SPLIT = "split"                          # L-016
    CROP = "crop"                            # L-017
    INVERT = "invert"                        # L-018
    RESOLUTION = "resolution"                # L-010
    BRIGHTNESS_CONTRAST = "brightness_contrast"  # L-011
    LEVELS = "levels"                        # L-012
    ERASE = "erase"                          # L-013
    REMOVE_COLOR_MARKS = "remove_color_marks"    # L-014
    DENOISE = "denoise"                      # L-023
    DEBLUR = "deblur"                        # L-032
    WHITEN_BACKGROUND = "whiten_background"  # L-022
    DETECT_EDGES = "detect_edges"            # L-021
    TO_BW = "to_bw"                          # L-033


class AutoProcessMode(str, Enum):
    """X-010."""

    READ = "read"
    ANALYZE_AND_READ = "analyze_and_read"
    PREPROCESS_ONLY = "preprocess_only"
    NONE = "none"


# =============================================================================
# 2. EXCEPȚII
# Fiecare excepție poarta un cod stabil. Codul merge in jurnal, in ieșirea JSON
# a CLI-ului (U-023) si in planul de testare. Mesajul afisat utilizatorului se
# construieste in GUI din cod + parametri, ca sa fie traductibil (Y-013).
# =============================================================================


class CoreError(Exception):
    """Baza tuturor excepțiilor nucleului."""

    code: str = "CORE_ERROR"

    def __init__(self, message: str = "", **params: Any) -> None:
        ...

    @property
    def params(self) -> Mapping[str, Any]:
        """Valorile pentru interpolat in mesajul tradus."""
        ...


# --- intrare / fisiere ---------------------------------------------------------

class UnsupportedFormatError(CoreError):
    """A-012: fisierul nu e intr-un format acceptat. params: path, extension."""
    code = "UNSUPPORTED_FORMAT"


class FileCorruptError(CoreError):
    """A-010: fisierul nu poate fi deschis. params: path, detail."""
    code = "FILE_CORRUPT"


class PasswordRequiredError(CoreError):
    """A-011: documentul cere parola si nu s-a dat niciuna."""
    code = "PASSWORD_REQUIRED"


class WrongPasswordError(CoreError):
    """A-011: parola nu e corecta. CLI: cod de ieșire 2 (U-027)."""
    code = "WRONG_PASSWORD"


class FileLockedError(CoreError):
    """I-001: fisierul e deschis in alta aplicatie. params: path."""
    code = "FILE_LOCKED"


class NoWritePermissionError(CoreError):
    """E-034, S-020. params: path."""
    code = "NO_WRITE_PERMISSION"


class DiskFullError(CoreError):
    """Y-009, X-089."""
    code = "DISK_FULL"


# --- proiect -------------------------------------------------------------------

class InvalidProjectError(CoreError):
    """J-003: folderul nu e un proiect valid."""
    code = "INVALID_PROJECT"


class ProjectVersionError(CoreError):
    """P-029, J-003: proiect dintr-o versiune mai noua. params: found, supported."""
    code = "PROJECT_VERSION"


class LastPageError(CoreError):
    """E-009, J-012: documentul trebuie sa aiba cel putin o pagina."""
    code = "LAST_PAGE"


# --- zone ----------------------------------------------------------------------

class AreaOverlapError(CoreError):
    """M-009: zonele nu se pot suprapune. params: area_id, other_id."""
    code = "AREA_OVERLAP"


class AreaTooSmallError(CoreError):
    """M-007: sub 8x8 px. params: w, h, min_size."""
    code = "AREA_TOO_SMALL"


class AreaOutOfBoundsError(CoreError):
    """M-017: zona nu poate ieși din imagine."""
    code = "AREA_OUT_OF_BOUNDS"


class WrongAreaTypeError(CoreError):
    """M-013, M-031, M-042: operatia nu e permisa pe acest tip de zona.
    params: area_type, operation, allowed_types."""
    code = "WRONG_AREA_TYPE"


class CellsNotRectangularError(CoreError):
    """M-043: selectia de celule de unit nu e dreptunghiulara."""
    code = "CELLS_NOT_RECTANGULAR"


class TemplateSizeMismatchError(CoreError):
    """M-041: sablonul vine de la o pagina de alta dimensiune sau rezolutie.
    Nu e fatala: apelantul poate reporni cu scale=True."""
    code = "TEMPLATE_SIZE_MISMATCH"


# --- recunoastere --------------------------------------------------------------

class NoLanguageSelectedError(CoreError):
    """P-001: minimum o limba."""
    code = "NO_LANGUAGE"


class LanguageModelMissingError(CoreError):
    """Y-004: modelul limbii nu e instalat. params: language_code, expected_path."""
    code = "LANGUAGE_MODEL_MISSING"


class RecognitionFailedError(CoreError):
    """CLI: cod de ieșire 3 (U-027). params: page_number, detail."""
    code = "RECOGNITION_FAILED"


class NoTextFoundError(CoreError):
    """R-007: documentul nu are text care sa poata fi comparat sau exportat."""
    code = "NO_TEXT_FOUND"


class PatternLimitError(CoreError):
    """P-023: sablonul a atins 1000 de caractere."""
    code = "PATTERN_LIMIT"


# --- export --------------------------------------------------------------------

class IncompatibleLayoutError(CoreError):
    """Q-001, U-006: formatul nu e permis in modul de layout cerut.
    params: layout_mode, requested_format, allowed_formats."""
    code = "INCOMPATIBLE_LAYOUT"


class PdfAEncryptionConflictError(CoreError):
    """A-028, I-006: PDF/A nu se combina cu protectia prin parola."""
    code = "PDFA_ENCRYPTION_CONFLICT"


class PdfAComplianceError(CoreError):
    """I-006: fisierul rezultat nu respecta standardul. params: violations."""
    code = "PDFA_COMPLIANCE"


class PagesNotRecognizedError(CoreError):
    """Q-051: exista pagini invalidate dupa ultima modificare.
    Nu e fatala: se foloseste ca avertisment inainte de export.
    params: page_numbers."""
    code = "PAGES_NOT_RECOGNIZED"


# --- securitate ----------------------------------------------------------------

class SamePasswordError(CoreError):
    """G-002: parola de permisiuni trebuie sa fie diferita de cea de deschidere."""
    code = "SAME_PASSWORD"


class NoCertificateError(CoreError):
    """G-010: nu exista un certificat cu cheie privata."""
    code = "NO_CERTIFICATE"


class CertificateNotOwnedError(CoreError):
    """G-024: semnatura nu se poate sterge fara certificatul cu care a fost facuta."""
    code = "CERTIFICATE_NOT_OWNED"


class TimestampUnavailableError(CoreError):
    """G-037: serverul de marca temporala nu raspunde. Apelantul decide dacă
    semneaza fara marca temporala."""
    code = "TIMESTAMP_UNAVAILABLE"


class RedactionVerificationError(CoreError):
    """G-021: textul redactat se mai gaseste in document dupa operatie.
    Aceasta e un defect al implementarii, nu o eroare de utilizare:
    operatia se anuleaza si se raporteaza. params: page_number, found_text."""
    code = "REDACTION_VERIFICATION_FAILED"


# --- formulare -----------------------------------------------------------------

class DuplicateFieldNameError(CoreError):
    """H-013: numele campului trebuie sa fie unic."""
    code = "DUPLICATE_FIELD_NAME"


class InvalidFieldNameError(CoreError):
    """H-013: punct la inceput, la sfarsit sau dublat."""
    code = "INVALID_FIELD_NAME"


class SignedFieldCopyError(CoreError):
    """H-040: doar campurile de semnatura goale se pot copia."""
    code = "SIGNED_FIELD_COPY"


class OrphanRadioButtonError(CoreError):
    """H-013: un grup de butoane radio are nevoie de minimum doua butoane."""
    code = "ORPHAN_RADIO_BUTTON"


# --- scanare / automatizare ----------------------------------------------------

class NoScannerError(CoreError):
    """A-040, K-004: niciun dispozitiv de scanare selectat."""
    code = "NO_SCANNER"


class ScannerError(CoreError):
    """K-013: hartie blocata, alimentator gol, driver cazut. params: detail."""
    code = "SCANNER_ERROR"


class TaskValidationError(CoreError):
    """T-012: pasii sarcinii nu sunt coerenti. params: step_index, reason."""
    code = "TASK_VALIDATION"


class BuiltinNotEditableError(CoreError):
    """T-002: sarcinile si limbile livrate nu se modifica."""
    code = "BUILTIN_NOT_EDITABLE"


class ShortcutConflictError(CoreError):
    """X-085, T-015. params: shortcut, existing_command."""
    code = "SHORTCUT_CONFLICT"


class OperationCancelledError(CoreError):
    """Aruncata cand `CancelToken` intoarce True.
    CLI: cod de ieșire 5 (U-027)."""
    code = "CANCELLED"


class NetworkAccessAttemptedError(CoreError):
    """Y-001. Nucleul nu face cereri de retea. Daca o componenta terta incearca,
    stratul de izolare arunca aceasta excepție, ca sa se vada la testare."""
    code = "NETWORK_ACCESS_ATTEMPTED"


# =============================================================================
# 3. MODELUL DE DATE
# Oglindeste SPEC_04. Obiectele sunt mutabile; persistenta e in repository.
# =============================================================================


@dataclass(slots=True)
class WordData:
    id: int | None
    text: str
    confidence: float
    """0..100, per cuvant (N-022)."""
    char_confidences: tuple[float, ...] = ()
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
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


@dataclass(slots=True)
class LineData:
    id: int | None
    words: list[WordData] = field(default_factory=list)
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    baseline_y: Px | None = None
    ends_with_hyphen: bool = False
    """R-035, si exportul: cuvantul despartit se reunifica."""

    @property
    def text(self) -> str: ...


@dataclass(slots=True)
class BlockData:
    id: int | None
    block_type: str = "paragraph"
    lines: list[LineData] = field(default_factory=list)
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    style_name: str | None = None
    list_level: int | None = None
    alignment: str | None = None
    direction: str = "ltr"

    @property
    def text(self) -> str: ...


@dataclass(slots=True)
class TableCellData:
    id: int | None
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    as_picture: bool = False
    """M-048."""
    is_header: bool = False
    blocks: list[BlockData] = field(default_factory=list)


@dataclass(slots=True)
class TableData:
    rows: int
    cols: int
    cells: list[TableCellData] = field(default_factory=list)
    h_separators: list[Px] = field(default_factory=list)
    v_separators: list[Px] = field(default_factory=list)

    def cell_at(self, row: int, col: int) -> TableCellData | None: ...


@dataclass(slots=True)
class AreaData:
    id: int | None
    area_type: AreaType
    polygon: Polygon
    order_index: int
    bbox: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
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

    @property
    def is_polygon(self) -> bool: ...


@dataclass(slots=True)
class PageWarning:
    severity: str
    code: str
    message_key: str
    """Cheie de traducere: 'warning.low_resolution'."""
    params: Mapping[str, Any] = field(default_factory=dict)
    is_dismissed: bool = False


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

    @property
    def text(self) -> str:
        """Textul paginii in ordinea zonelor (M-022)."""
        ...

    def iter_words(self) -> Iterator[WordData]: ...
    def area_at(self, point: Point) -> AreaData | None: ...


# =============================================================================
# 4. SETARI
# =============================================================================


@dataclass(slots=True)
class PreprocessSettings:
    """X-010..X-023. Optiunile marcate `photo_only` se aplica doar
    fotografiilor (L-018)."""

    auto_mode: AutoProcessMode = AutoProcessMode.READ
    split_facing_pages: bool = False
    correct_orientation: bool = True
    use_recommended: bool = True
    deskew: bool = True
    straighten_lines: bool = True
    correct_resolution: bool = True
    detect_page_edges: bool = True          # photo_only
    whiten_background: bool = True          # photo_only
    reduce_iso_noise: bool = True           # photo_only
    remove_motion_blur: bool = False        # photo_only
    fix_inverted_colors: bool = True
    convert_to_bw: bool = False
    """X-022: nerecomandat pentru foto, reviste si scrieri asiatice."""
    remove_color_marks: bool = False
    """X-023, L-014: doar scanari cu fundal alb."""


@dataclass(slots=True)
class OcrSettings:
    """X-040..X-049."""

    languages: tuple[LanguageCode, ...] = ("ron", "eng")
    pdf_mode: PdfRecognitionMode = PdfRecognitionMode.AUTO
    quality: OcrQuality = OcrQuality.THOROUGH
    print_type: PrintType = PrintType.AUTO
    detect_headers_footers: bool = True
    detect_numbered_lists: bool = True
    detect_table_of_contents: bool = True
    detect_footnotes: bool = True
    convert_barcodes_to_text: bool = False
    """X-044: dezactivat implicit."""
    use_builtin_patterns: bool = True
    use_user_patterns: bool = False
    also_use_builtin: bool = False
    use_training: bool = False
    """X-046: dezactivat implicit."""
    confidence_threshold: float = 70.0
    """X-102. [DECIZIE] Valoarea 70 e alegerea noastra; originalul nu o publica."""
    header_repeat_ratio: float = 0.5
    """N-016. [DECIZIE] Un text se considera antet dacă apare in aceeasi poziție
    pe mai mult de jumatate din pagini."""
    max_threads: int | None = None
    """X-081: None = toate nucleele minus unul."""


@dataclass(slots=True)
class ExportOptions:
    """Opțiunile comune de export. Cele specifice formatului se trimit in
    `format_options` si sunt documentate in X-060..X-068."""

    layout_mode: LayoutMode = LayoutMode.EDITABLE
    keep_pictures: bool = True              # Q-007
    keep_headers_footers: bool = False      # X-103, doar EDITABLE
    keep_line_breaks: bool = False          # X-104
    image_quality: ImageQuality = ImageQuality.BALANCED
    image_dpi: int | None = None
    pdfa_version: PdfAVersion | None = None
    use_mrc: bool = False
    searchable: bool = True
    create_bookmarks_from_headings: bool = False
    """X-060, O-023: stilurile cu heading_level > 0 devin semne de carte."""
    tagged_pdf: bool = False
    separate_file_per_page: bool = False    # Q-022
    page_range: tuple[int, ...] | None = None
    encoding: str = "utf-8"
    format_options: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self, target: ExportFormat) -> None:
        """Q-001, A-028: ridica `IncompatibleLayoutError` dacă formatul nu e
        permis in `layout_mode`, si `PdfAEncryptionConflictError` dacă s-a
        cerut PDF/A impreuna cu o parola."""
        ...


@runtime_checkable
class SettingsStore(Protocol):
    """Setarile globale si cele suprascrise pe proiect (X.*, J-039).
    Cheile sunt cele din tabelul `setting`: 'ocr.quality', 'image.deskew'."""

    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None:
        """Ridica `ValueError` dacă valoarea iese din min/max sau din
        `allowed_values` declarate pentru cheie."""
        ...

    def get_typed(self, key: str, kind: type) -> Any: ...
    def reset_all(self) -> None:
        """X-147: reseteaza toate tab-urile, nu doar unul."""
        ...

    def export_to(self, path: Path) -> None: ...
    """Y-015."""
    def import_from(self, path: Path) -> None: ...
    def ocr_settings(self) -> OcrSettings: ...
    def preprocess_settings(self) -> PreprocessSettings: ...
    def with_overrides(self, overrides: Mapping[str, Any]) -> SettingsStore:
        """J-039: setarile unui proiect, peste cele globale."""
        ...


# =============================================================================
# 5. IMAGINI
# =============================================================================


@dataclass(slots=True)
class LoadedImage:
    """O imagine incarcata, cu metadatele necesare OCR-ului."""

    path: Path
    width_px: Px
    height_px: Px
    dpi_x: int
    dpi_y: int
    color_mode: ColorMode
    source_page: int | None = None
    is_photo: bool = False
    """L-018: decide dacă se aplica uneltele marcate photo_only. Estimat din
    absenta unui dpi declarat, din zgomot si din neuniformitatea fundalului."""


class ImageLoader:
    """A-012, J-008, K-001. Formatele acceptate: PDF, XPS, DjVu, JPEG,
    JPEG2000, PNG, TIFF, BMP, PCX/DCX, GIF, JBIG2."""

    SUPPORTED_EXTENSIONS: frozenset[str]

    def can_load(self, path: Path) -> bool: ...

    def load(
        self,
        path: Path,
        *,
        password: PasswordCallback | None = None,
        pages: Sequence[int] | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[LoadedImage]:
        """Un fisier multipagina intoarce o imagine per pagina.

        Erori: `UnsupportedFormatError`, `FileCorruptError`,
        `PasswordRequiredError`, `WrongPasswordError`.
        """
        ...

    def read_page_count(self, path: Path) -> int:
        """W-007: pentru previzualizarea din dialogul de deschidere."""
        ...

    def render_thumbnail(self, path: Path, page: int, max_size: Px) -> bytes:
        """PNG. Folosit la miniaturi (B-022) si la documentele recente."""
        ...


@runtime_checkable
class PreprocessTool(Protocol):
    """O unealta de preprocesare. Pura: nu scrie pe disc, nu are stare.
    L-001..L-034."""

    op: PreprocessOp
    photo_only: bool
    """L-018: se aplica automat doar fotografiilor."""

    def default_params(self) -> Mapping[str, Any]: ...
    def validate_params(self, params: Mapping[str, Any]) -> None:
        """Ridica `ValueError` cu numele parametrului greșit."""
        ...

    def apply(
        self, image: Any, params: Mapping[str, Any]
    ) -> tuple[Any, Mapping[str, Any]]:
        """Intoarce imaginea noua si metadatele produse (unghiul detectat la
        deskew, dpi-ul estimat, numarul de pagini rezultate la split).

        `image` e un ndarray; tipul nu e fixat aici ca sa nu lege nucleul de o
        biblioteca anume.
        """
        ...


class PreprocessPipeline:
    """L-001, L-015..L-034, J-009, J-013."""

    def register(self, tool: PreprocessTool) -> None: ...
    def tool_for(self, op: PreprocessOp) -> PreprocessTool: ...

    def recommended_chain(
        self, image: LoadedImage, settings: PreprocessSettings
    ) -> list[tuple[PreprocessOp, Mapping[str, Any]]]:
        """L-001: decide lantul pe baza histogramei, a dpi-ului estimat si a
        detectiei de zgomot. Uneltele photo_only intra doar dacă
        `image.is_photo`."""
        ...

    def run(
        self,
        page: PageData,
        chain: Sequence[tuple[PreprocessOp, Mapping[str, Any]]],
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[PageData]:
        """Aplica lantul si scrie imaginea rezultata langa cea originala.

        Intoarce o lista pentru ca `SPLIT` transforma o pagina in doua (L-016).
        Statusul paginii devine `PREPROCESSED`; dacă pagina era deja
        recunoscuta, textul se invalideaza (J-013, N-024).
        """
        ...

    def revert_to_original(self, page: PageData) -> PageData:
        """Reincarca `original_path` si goleste `applied_operations`."""
        ...


@dataclass(slots=True)
class ScanSettings:
    """K-003..K-002."""

    device_id: str
    color_mode: ColorMode = ColorMode.GRAY
    """K-007: gri e recomandarea implicita pentru OCR."""
    dpi: int = 300
    """K-009: peste 600 se avertizeaza."""
    brightness: int = 50
    page_size: str = "A4"
    scan_area: Rect | None = None
    duplex: bool = False
    use_adf: bool = False
    flatbed_delay_s: int | None = None
    use_driver_ui: bool = False
    image_format: str = "png"


@runtime_checkable
class ScannerService(Protocol):
    """K-003..K-002, A-040. Singurul loc din nucleu care vorbeste cu hardware."""

    def list_devices(self) -> list[tuple[str, str]]:
        """(id, nume afisabil). Lista se reinterogheaza la fiecare apel (K-004)."""
        ...

    def capabilities(self, device_id: str) -> Mapping[str, Any]:
        """Ce raporteaza driverul: duplex, ADF, rezolutii, moduri de culoare.
        Interfata dezactiveaza ce nu e raportat (K-012, K-013)."""
        ...

    def preview(self, settings: ScanSettings) -> LoadedImage:
        """K-015: scanare rapida, la rezolutie mica."""
        ...

    def scan(
        self,
        settings: ScanSettings,
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> Iterator[LoadedImage]:
        """Generator: cu ADF produce pagini pana se goleste alimentatorul.

        Erori: `NoScannerError`, `ScannerError`.
        """
        ...


# =============================================================================
# 6. ANALIZA DE LAYOUT
# =============================================================================


class LayoutAnalyzer:
    """N-001, N-002, M-022."""

    def analyze(
        self,
        page: PageData,
        settings: OcrSettings,
        *,
        template: Sequence[AreaData] | None = None,
        cancel: CancelToken | None = None,
    ) -> list[AreaData]:
        """Detecteaza zonele si le numeroteaza de la stanga la dreapta, apoi de
        sus in jos, indiferent de direcția textului (M-022).

        Zonele existente create manual nu se suprascriu: se pastreaza si se
        completeaza doar spatiile libere.
        """
        ...

    def detect_orientation(self, page: PageData) -> int:
        """L-020, E-012: 0, 90, 180 sau 270. Pe o pagina fara text intoarce
        rotatia actuala, nu ghiceste."""
        ...

    def estimate_skew(self, page: PageData) -> float:
        """L-002: unghiul in grade, cu toleranta de 0,1 grade."""
        ...

    def blank_score(self, page: PageData) -> float:
        """E-026, J-056: 0..1. Pragul de la care o pagina se considera goala
        vine din setari."""
        ...

    def detect_structural_elements(
        self, pages: Sequence[PageData], settings: OcrSettings
    ) -> None:
        """N-016..N-019. Lucreaza pe tot documentul, nu pe o pagina: antetul se
        recunoaste prin repetarea aceluiasi text in aceeasi poziție pe mai mult
        de `header_repeat_ratio` din pagini. Marcheaza `TextFunction` pe zone si
        `block_type` pe blocuri."""
        ...


class TableAnalyzer:
    """M-031..O-063."""

    def analyze_structure(self, area: AreaData, page: PageData) -> TableData:
        """Detecteaza randuri, coloane si celule unite.

        Daca structura nu se poate detecta, intoarce un tabel 1x1 si adauga un
        `PageWarning`, nu arunca excepție (M-031).
        """
        ...

    def add_separator(self, table: TableData, axis: str, position: Px) -> TableData: ...
    def remove_separator(self, table: TableData, axis: str, position: Px) -> TableData: ...

    def merge_cells(self, table: TableData, cells: Sequence[TableCellData]) -> TableData:
        """M-043: selectia trebuie sa fie dreptunghiulara, altfel
        `CellsNotRectangularError`."""
        ...

    def split_cells(self, table: TableData, cell: TableCellData) -> TableData:
        """M-042: doar celule unite anterior, altfel `WrongAreaTypeError`."""
        ...

    def merge_rows(self, table: TableData, rows: Sequence[int]) -> TableData: ...


class AreaEditor:
    """M-007..M-024, M-040, M-041. Toate operatiile pe zone trec prin aici, ca
    regula de interzicere a suprapunerii sa fie intr-un singur loc."""

    MIN_SIZE: Px = 8

    def create(
        self, page: PageData, polygon: Polygon, area_type: AreaType
    ) -> AreaData:
        """Erori: `AreaTooSmallError`, `AreaOverlapError`,
        `AreaOutOfBoundsError`."""
        ...

    def move(self, page: PageData, area: AreaData, dx: Px, dy: Px) -> AreaData: ...
    def resize(self, page: PageData, area: AreaData, new_polygon: Polygon) -> AreaData: ...

    def add_part(self, page: PageData, area: AreaData, rect: Rect) -> AreaData:
        """M-013: doar TEXT, PICTURE, BACKGROUND_PICTURE."""
        ...

    def cut_part(self, page: PageData, area: AreaData, rect: Rect) -> AreaData:
        """M-014: aceleasi tipuri."""
        ...

    def change_type(
        self, page: PageData, area: AreaData, new_type: AreaType
    ) -> AreaData:
        """M-020: invalideaza textul paginii."""
        ...

    def delete(self, page: PageData, areas: Sequence[AreaData]) -> None:
        """M-018: pe o pagina recunoscuta sterge si textul zonelor."""
        ...

    def reorder(self, page: PageData, order: Sequence[int]) -> None:
        """M-021."""
        ...

    def renumber_automatically(self, page: PageData) -> None:
        """M-022."""
        ...

    def save_template(self, page: PageData, path: Path, name: str) -> None:
        """M-040."""
        ...

    def load_template(
        self,
        pages: Sequence[PageData],
        path: Path,
        *,
        scale: bool = False,
    ) -> None:
        """M-041: suprascrie zonele existente. Daca dimensiunea sau rezolutia
        paginii difera de cea din sablon si `scale` e False, ridica
        `TemplateSizeMismatchError`; apelantul reporneste cu `scale=True`."""
        ...


# =============================================================================
# 7. RECUNOASTEREA
# =============================================================================


@dataclass(slots=True)
class RecognitionResult:
    page_number: int
    blocks: list[BlockData]
    tables: list[TableData]
    barcodes: list[tuple[AreaData, str, str]]
    """(zona, tip de cod, valoare) - N-021."""
    avg_confidence: float
    uncertain_count: int
    duration_ms: int
    warnings: list[PageWarning]


@runtime_checkable
class OcrEngine(Protocol):
    """Interfata catre motorul de recunoastere. Mai multe implementari pot
    coexista; alegerea se face din setari. Nucleul nu depinde de niciuna."""

    name: str

    def available_languages(self) -> list[LanguageCode]: ...
    def supports_language(self, code: LanguageCode) -> bool: ...

    def recognize_area(
        self,
        page: PageData,
        area: AreaData,
        settings: OcrSettings,
        *,
        cancel: CancelToken | None = None,
    ) -> list[BlockData]:
        """N-005. Erori: `LanguageModelMissingError`, `RecognitionFailedError`."""
        ...

    def recognize_page(
        self,
        page: PageData,
        settings: OcrSettings,
        *,
        cancel: CancelToken | None = None,
    ) -> RecognitionResult:
        """N-003. Daca pagina nu e analizata, cheama intai `LayoutAnalyzer`."""
        ...

    def read_barcode(self, page: PageData, area: AreaData) -> tuple[str, str] | None:
        """N-021. None cand codul nu se poate citi: zona ramane imagine."""
        ...


class RecognitionService:
    """N-001..N-026. Orchestreaza analiza, recunoasterea si paralelizarea.
    Aici trăiește decizia dintre stratul de text existent si OCR."""

    def __init__(
        self,
        engine: OcrEngine,
        analyzer: LayoutAnalyzer,
        table_analyzer: TableAnalyzer,
        settings: SettingsStore,
    ) -> None: ...

    def evaluate_text_layer(self, path: Path, page: int) -> float:
        """N-009: calitatea stratului de text existent, 0..1. Se calculeaza din
        procentul de cuvinte gasite in dictionar, din corectitudinea codificarii
        si din acoperirea paginii. Sub prag se trece pe OCR."""
        ...

    def choose_mode(self, path: Path, page: int, settings: OcrSettings) -> PdfRecognitionMode:
        """N-008, N-009: pentru un PDF digital de buna calitate intoarce
        TEXT_ONLY; pentru o scanare sau un strat de text stricat, FORCE_OCR."""
        ...

    def pull_and_recognize(
        self,
        page: PageData,
        settings: OcrSettings,
        *,
        cancel: CancelToken | None = None,
    ) -> RecognitionResult:
        """N-010: pe un document mixt extrage textul digital din zonele care il
        au si recunoaste separat zonele care sunt imagini, apoi combina."""
        ...

    def recognize_pages(
        self,
        pages: Sequence[PageData],
        *,
        skip_recognized: bool = True,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[RecognitionResult]:
        """N-004: paginile deja recunoscute se sar; cele analizate se recunosc.
        N-025: paralelizare pe `OcrSettings.max_threads`.
        N-026: anularea opreste dupa pagina curenta, nu in mijlocul ei."""
        ...

    def mark_uncertain(self, result: RecognitionResult, threshold: float) -> None:
        """N-022, N-023, O-002."""
        ...


class LanguageRegistry:
    """P-001..P-029."""

    def all(self) -> list[LanguageCode]: ...
    def display_name(self, code: LanguageCode) -> str: ...
    def is_builtin(self, code: LanguageCode) -> bool: ...
    def is_model_available(self, code: LanguageCode) -> bool: ...

    def autodetect(self, page: PageData) -> tuple[LanguageCode, ...]:
        """P-002: doar pentru limbile cu dictionar. Cand detectia e nesigura,
        intoarce prima limba din setari, nu o eroare."""
        ...

    def create_user_language(
        self,
        name: str,
        base: LanguageCode,
        *,
        alphabet: str | None = None,
        forbidden_chars: str | None = None,
        dictionary_mode: str = "builtin",
        dictionary_regex: str | None = None,
    ) -> LanguageCode:
        """P-006..P-026. `dictionary_regex` trebuie sa compileze, altfel
        `ValueError` cu mesajul erorii de compilare (P-008)."""
        ...

    def delete_user_language(self, code: LanguageCode) -> None:
        """P-006: `BuiltinNotEditableError` pentru limbile livrate."""
        ...

    def create_group(self, name: str, codes: Sequence[LanguageCode]) -> str:
        """P-027: minimum doua limbi."""
        ...


class DictionaryService:
    """P-040..P-045, O-010, O-006."""

    def contains(self, word: str, language: LanguageCode) -> bool: ...
    def suggest(self, word: str, language: LanguageCode, limit: int = 8) -> list[str]:
        """O-010: sugestii pentru un cuvant nesigur."""
        ...

    def add(self, word: str, language: LanguageCode) -> None:
        """P-041: fara spatii."""
        ...

    def remove(self, word: str, language: LanguageCode) -> None: ...

    def import_words(self, path: Path, language: LanguageCode) -> int:
        """P-043: fisier text, un cuvant pe rand, codificare detectata.
        Intoarce numarul de cuvinte adaugate. Fisier binar → `ValueError`."""
        ...

    def export_words(self, path: Path, language: LanguageCode) -> int: ...

    def set_shared_folder(self, path: Path | None) -> None:
        """P-045, X-105: folder partajat in retea. Daca devine inaccesibil, se
        revine la cel local si se adauga un avertisment, nu se arunca."""
        ...


class PatternStore:
    """P-050..P-029."""

    MAX_CHARS_PER_SET: int = 1000

    def sets(self) -> list[str]: ...
    def active_set(self) -> str | None: ...
    def set_active(self, name: str) -> None: ...
    def create_set(self, name: str, language: LanguageCode | None = None) -> None: ...
    def delete_set(self, name: str) -> None:
        """Sablonul activ nu se poate sterge (P-027)."""
        ...

    def add_pattern(self, set_name: str, glyph_png: bytes, character: str) -> None:
        """P-023: peste 1000 de caractere ridica `PatternLimitError`."""
        ...

    def save_bundle(self, path: Path) -> None:
        """P-028: sabloane si limbi in acelasi fisier."""
        ...

    def load_bundle(self, path: Path) -> None:
        """P-029: `ProjectVersionError` pentru un fisier dintr-o versiune mai
        noua."""
        ...


# =============================================================================
# 8. VERIFICAREA SI EDITAREA TEXTULUI
# =============================================================================


@dataclass(slots=True)
class TextStyle:
    """O-021..O-027."""

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
    """O-023: 0 = fara rol, 1..10 = Heading 1..10. Valorile peste 0 genereaza
    semne de carte la exportul in PDF, cand opțiunea e activa."""
    is_builtin: bool = False


class TextEditor:
    """O-001..J-008."""

    def set_word_text(self, word: WordData, text: str) -> None:
        """O-006: pastreaza `original_text`, pune `is_edited`, scoate
        `is_verified`. Modificarea se reflecta si in stratul de text exportat."""
        ...

    def next_uncertain(
        self, pages: Sequence[PageData], after: WordData | None = None
    ) -> WordData | None:
        """O-004. None cand nu mai urmeaza niciunul."""
        ...

    def previous_uncertain(
        self, pages: Sequence[PageData], before: WordData | None = None
    ) -> WordData | None:
        """O-005."""
        ...

    def mark_verified(self, page: PageData) -> None:
        """O-011: statusul paginii devine `VERIFIED`."""
        ...

    def apply_formatting(
        self, words: Sequence[WordData], **attrs: Any
    ) -> None:
        """O-022, O-020: font, marime, bold, italic, underline, indice,
        exponent, culoare."""
        ...

    def apply_style(self, blocks: Sequence[BlockData], style: TextStyle) -> None:
        """O-027."""
        ...

    def redact_words(self, words: Sequence[WordData]) -> None:
        """O-070: marcheaza `is_redacted`. La export, textul devine puncte sau
        dreptunghi negru, dupa format."""
        ...

    def find(
        self,
        pages: Sequence[PageData],
        query: str,
        *,
        match_case: bool = False,
        whole_word: bool = False,
        ignore_diacritics: bool = True,
    ) -> list[WordData]:
        """O-028, C-002. `ignore_diacritics=True` e implicit: in documentele
        romanesti scanate, 'hotarare' trebuie sa gaseasca 'hotărâre'."""
        ...

    def replace(
        self,
        words: Sequence[WordData],
        new_text: str,
    ) -> int:
        """O-029, C-015. `new_text` poate fi gol (stergere). Intoarce numarul de
        inlocuiri."""
        ...


class StyleManager:
    """O-021..O-026."""

    def all(self) -> list[TextStyle]: ...
    def create(self, name: str) -> TextStyle:
        """Nume unic, altfel `ValueError`."""
        ...

    def merge(self, styles: Sequence[TextStyle], into: str) -> TextStyle:
        """O-025."""
        ...

    def delete(self, name: str) -> None: ...
    def fragments_using(
        self, pages: Sequence[PageData], style_name: str
    ) -> list[BlockData]:
        """O-026: pentru butoanele Previous/Next Fragment."""
        ...


# =============================================================================
# 9. PROIECTUL OCR
# =============================================================================


class OcrProject:
    """J-001..J-041. Deține paginile, zonele si textul; nu stie nimic despre
    interfata. Toate modificarile trec prin el ca sa se inregistreze in
    istoricul de undo si sa se marcheze proiectul ca modificat."""

    path: Path | None
    name: str
    is_modified: bool
    languages: tuple[LanguageCode, ...]
    layout_mode: LayoutMode

    @classmethod
    def create(cls, name: str | None = None) -> OcrProject:
        """J-001, J-002: proiect gol, `Untitled project N`."""
        ...

    @classmethod
    def open(cls, path: Path) -> OcrProject:
        """J-003. Erori: `InvalidProjectError`, `ProjectVersionError`."""
        ...

    def save(self, path: Path | None = None) -> None:
        """J-004. `NoWritePermissionError` cand folderul nu e scriibil."""
        ...

    def autosave(self) -> Path:
        """J-005: la fiecare 5 minute, doar dacă exista modificari.
        [DECIZIE] Intervalul de 5 minute e alegerea noastra."""
        ...

    @classmethod
    def find_recovery(cls) -> list[tuple[Path, Path | None]]:
        """J-006, Y-008: (fisier de recuperare, calea originala)."""
        ...

    def close(self) -> None:
        """J-007. Nu intreaba nimic: apelantul verifica `is_modified`."""
        ...

    # --- pagini ---
    @property
    def pages(self) -> Sequence[PageData]: ...
    def page(self, number: int) -> PageData: ...

    def add_images(
        self,
        paths: Sequence[Path],
        *,
        at: int | None = None,
        password: PasswordCallback | None = None,
        auto_process: AutoProcessMode | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> tuple[list[PageData], list[tuple[Path, CoreError]]]:
        """J-008..J-011.

        Intoarce paginile adaugate si lista fisierelor sarite cu motivul lor.
        Un format nesuportat NU opreste lotul: se sare si se raporteaza la final
        (J-008). `auto_process=None` ia modul din setari (J-009, X-010).
        """
        ...

    def delete_pages(self, numbers: Sequence[int]) -> None:
        """J-012: `LastPageError` dacă ar rămâne zero pagini."""
        ...

    def rotate_pages(self, numbers: Sequence[int], degrees: int) -> None:
        """J-013: multiplu de 90. Invalideaza zonele si textul paginilor."""
        ...

    def reorder_pages(self, new_order: Sequence[int]) -> None:
        """J-014."""
        ...

    def interleave_duplex(self) -> None:
        """J-015: reface ordinea dupa o scanare duplex in doua treceri.
        `ValueError` dacă numarul de pagini e impar."""
        ...

    def swap_book_pages(self) -> None:
        """J-016."""
        ...

    def move_pages_to(
        self, numbers: Sequence[int], target: OcrProject
    ) -> None:
        """J-017."""
        ...

    def find_blank_pages(self, threshold: float | None = None) -> list[int]:
        """J-056, E-026: lista paginilor candidate; stergerea e separata, ca
        utilizatorul sa poata revizui (E-027)."""
        ...

    # --- metadate si setari ---
    def set_metadata(self, **fields: str) -> None:
        """J-038: title, author, subject, keywords."""
        ...

    def settings(self) -> SettingsStore:
        """J-039: setarile globale cu suprascrierile proiectului."""
        ...

    # --- istoric ---
    def can_undo(self) -> bool: ...
    def can_redo(self) -> bool: ...
    def undo_description(self) -> str | None:
        """Textul din meniu: 'Anuleaza stergerea paginii 3'."""
        ...

    def undo(self) -> None:
        """J-041, E-040: minimum 50 de pasi, operatiile pe imagine incluse."""
        ...

    def redo(self) -> None: ...


# =============================================================================
# 10. PDF
# =============================================================================


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


@dataclass(slots=True)
class BookmarkData:
    id: int | None
    title: str
    level: int = 1
    target_page: int | None = None
    target_y: Px | None = None
    children: list[BookmarkData] = field(default_factory=list)
    generated_from_style: str | None = None


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


class PdfDocument:
    """B-001..B-035, I-001..I-015. Documentul PDF deschis in editor."""

    path: Path | None
    page_count: int
    is_modified: bool
    pdf_version: str
    is_encrypted: bool
    permissions: Mapping[str, bool]
    is_tagged: bool

    @classmethod
    def open(
        cls, path: Path, *, password: PasswordCallback | None = None
    ) -> PdfDocument:
        """A-010, A-011."""
        ...

    @classmethod
    def create_empty(cls) -> PdfDocument: ...

    @classmethod
    def from_images(
        cls, images: Sequence[Path], *, options: ExportOptions
    ) -> PdfDocument:
        """A-013."""
        ...

    def save(self) -> None:
        """I-001, I-003: obiectele nemodificate se copiaza la nivel de octeti,
        iar versiunea PDF nu scade. Erori: `FileLockedError`."""
        ...

    def save_as(self, path: Path, *, options: ExportOptions | None = None) -> None:
        """I-002, I-004..I-008."""
        ...

    def close(self) -> None: ...

    def render_page(
        self, number: int, zoom: float, *, annotations: bool = True
    ) -> bytes:
        """B-001: PNG. Randarea e lenesa: interfata cere doar paginile vizibile
        plus una inainte si una dupa."""
        ...

    def page_size(self, number: int) -> tuple[float, float]:
        """In puncte."""
        ...

    def extract_text(self, number: int) -> str: ...

    def has_text_layer(self, number: int) -> bool:
        """B-029, N-008."""
        ...

    def recognize_in_background(
        self,
        *,
        pages: Sequence[int] | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> None:
        """B-029: strat de text temporar, cautabil si copiabil, care NU se
        scrie in fisier. La esec, cautarea rămâne pe textul existent si nu se
        afiseaza nimic intruziv (B-029)."""
        ...

    def recognize_and_store(
        self,
        *,
        pages: Sequence[int] | None = None,
        settings: OcrSettings | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        """B-031, E-036: strat de text permanent. Modifica fisierul."""
        ...

    # --- metadate ---
    def metadata(self) -> Mapping[str, str]:
        """F-049, F-050."""
        ...

    def set_metadata(self, **fields: str) -> None:
        """F-049: campurile sunt blocate la fisierele protejate."""
        ...

    # --- cautare ---
    def search(
        self,
        query: str,
        *,
        match_case: bool = False,
        whole_word: bool = False,
        in_comments: bool = True,
        in_bookmarks: bool = True,
        in_metadata: bool = True,
    ) -> list[tuple[int, Rect, str]]:
        """C-002..C-009: (pagina, dreptunghi, context). Rezultatele se grupeaza
        de apelant pe sursa."""
        ...

    def replace_text(
        self, hits: Sequence[tuple[int, Rect]], new_text: str
    ) -> int:
        """C-015, C-015. Pe un PDF scanat foloseste stratul OCR: acopera textul
        vechi cu fundalul detectat si deseneaza textul nou, dar **documentul
        rămâne un PDF imagine**. Daca fundalul nu e uniform, apelantul primeste
        un avertisment inainte (C-015)."""
        ...

    # --- adnotari ---
    def annotations(self, page: int | None = None) -> list[AnnotationData]:
        """D-020."""
        ...

    def add_annotation(self, annot: AnnotationData) -> AnnotationData:
        """D-001..D-016. Pentru marcajele pe text (`HIGHLIGHT`, `UNDERLINE`,
        `STRIKETHROUGH`) e nevoie de strat de text; pe scanari se foloseste
        OCR-ul de fundal (D-002)."""
        ...

    def update_annotation(self, annot: AnnotationData) -> AnnotationData: ...
    def delete_annotations(self, ids: Sequence[int]) -> None:
        """D-019: se sterg si raspunsurile."""
        ...

    def delete_all_annotations(self) -> int:
        """D-034: intoarce cate au fost sterse, ca apelantul sa confirme intai."""
        ...

    def add_reply(self, parent_id: int, content: str, author: str) -> AnnotationData:
        """D-018."""
        ...

    def set_review_status(
        self, annot_id: int, status: ReviewStatus, author: str
    ) -> None:
        """D-031: istoricul schimbarilor se pastreaza."""
        ...

    # --- semne de carte ---
    def bookmarks(self) -> list[BookmarkData]:
        """B-023."""
        ...

    def add_bookmark(self, bm: BookmarkData, parent_id: int | None = None) -> BookmarkData:
        """F-042: maximum 10 niveluri, titlu nevid."""
        ...

    def move_bookmark(self, bm_id: int, parent_id: int | None, index: int) -> None:
        """F-043, F-044."""
        ...

    def rename_bookmark(self, bm_id: int, title: str) -> None:
        """F-045."""
        ...

    def delete_bookmarks(self, ids: Sequence[int]) -> None:
        """F-046: doar la acelasi nivel."""
        ...

    def generate_bookmarks_from_styles(self, styles: Sequence[TextStyle]) -> int:
        """O-023, X-060: stilurile cu heading_level > 0 devin semne de carte."""
        ...

    # --- atasamente ---
    def attachments(self) -> list[tuple[str, int, bool]]:
        """(nume, dimensiune, e executabil) - F-047, F-048."""
        ...

    def add_attachment(self, path: Path, description: str = "") -> None: ...
    def extract_attachment(self, name: str, to: Path) -> None: ...
    def delete_attachment(self, name: str) -> None: ...

    # --- linkuri ---
    def add_link(
        self, page: int, rect: Rect, target: Mapping[str, Any]
    ) -> None:
        """F-027: target are `kind` = page | destination | url | email | file."""
        ...

    def links(self, page: int) -> list[tuple[Rect, Mapping[str, Any]]]: ...
    def delete_link(self, page: int, rect: Rect) -> None: ...

    def detect_urls(self) -> int:
        """B-032, X-084."""
        ...

    # --- JavaScript ---
    def has_javascript(self) -> bool:
        """B-033: interfata arata banda de notificare pe baza acestui raspuns."""
        ...

    def javascript_enabled(self) -> bool: ...
    def enable_javascript(self, enabled: bool) -> None:
        """B-033: implicit dezactivat. Un script care depaseste 2 secunde se
        opreste si se noteaza in jurnal.
        [DECIZIE] Limita de 2 secunde e alegerea noastra."""
        ...

    # --- tiparire ---
    def print(
        self,
        printer_name: str,
        *,
        pages: Sequence[int] | None = None,
        copies: int = 1,
        scaling: str = "fit",
        grayscale: bool = False,
        print_annotations: bool = False,
        to_file: Path | None = None,
    ) -> None:
        """I-011."""
        ...


class PageOrganizer:
    """E-001..E-040. Operatii pe pagini de PDF."""

    def __init__(self, document: PdfDocument) -> None: ...

    def parse_page_range(self, text: str, page_count: int) -> tuple[int, ...]:
        """E-005: '2, 3, 5-7'. Spatiile se accepta, intervalele inversate se
        normalizeaza, numerele din afara documentului se ignora si se
        raporteaza."""
        ...

    def delete(self, pages: Sequence[int]) -> None:
        """E-009: `LastPageError` la ultima pagina."""
        ...

    def rotate(self, pages: Sequence[int], degrees: int) -> None:
        """E-010, E-011."""
        ...

    def correct_orientation(self, pages: Sequence[int]) -> dict[int, int]:
        """E-012: intoarce rotatia aplicata per pagina. O pagina fara text
        rămâne neschimbata."""
        ...

    def crop(
        self, pages: Sequence[int], rect: Rect, *, same_for_all: bool = True
    ) -> None:
        """E-014, E-015."""
        ...

    def add_blank(self, at: int, size: tuple[float, float] | None = None) -> None:
        """E-017: implicit dimensiunea paginii curente."""
        ...

    def insert_from_pdf(
        self,
        source: Path,
        *,
        source_pages: Sequence[int] | None = None,
        at: int,
        password: PasswordCallback | None = None,
    ) -> None:
        """E-018, E-020, E-021."""
        ...

    def insert_from_file(
        self, source: Path, *, source_pages: Sequence[int] | None = None, at: int
    ) -> None:
        """E-019: orice format suportat, convertit intai in PDF."""
        ...

    def insert_from_scanner(self, settings: ScanSettings, at: int) -> None:
        """E-022."""
        ...

    def move(self, pages: Sequence[int], to: int) -> None:
        """E-023, E-024."""
        ...

    def replace(
        self,
        target_pages: Sequence[int],
        source: Path,
        source_pages: Sequence[int],
    ) -> None:
        """E-025: intervalele trebuie sa aiba acelasi numar de pagini, altfel
        `ValueError` cu ambele lungimi in parametri."""
        ...

    def find_blank(self, threshold: float | None = None) -> list[int]:
        """E-026."""
        ...

    def split(
        self,
        *,
        by: str,
        value: Any,
        output_folder: Path,
        name_template: str = "{index}_{name}",
        number_digits: int = 2,
        progress: ProgressCallback | None = None,
    ) -> list[Path]:
        """E-028..E-035. `by` = 'size' | 'pages' | 'bookmarks'.

        E-035, reguli care trebuie respectate exact:
        - semnele de carte NU se pastreaza in fisierele rezultate
        - atasamentele merg intr-un subfolder `Attachments`
        """
        ...

    def extract_to_new_document(self, pages: Sequence[int]) -> PdfDocument:
        """E-039."""
        ...

    def enhance_images(
        self, pages: Sequence[int], settings: PreprocessSettings
    ) -> None:
        """E-038."""
        ...


class PdfContentEditor:
    """F-001..F-026. Editarea textului si a imaginilor din pagina."""

    def __init__(self, document: PdfDocument, font_matcher: FontMatcher) -> None: ...

    def prepare_page(
        self, page: int, *, progress: ProgressCallback | None = None
    ) -> None:
        """F-001, F-002. Construieste modelul de blocuri editabile: din stratul
        existent pe un PDF digital, prin OCR pe o scanare, prin GlyphRecovery
        cand codificarea e stricata. Pe o pagina care nu se poate pregati,
        ridica `CoreError` si editorul rămâne in vizualizare."""
        ...

    def blocks(self, page: int) -> list[BlockData]: ...

    def set_block_text(self, page: int, block_id: int, text: str) -> None:
        """F-003: textul face reflow in limitele blocului."""
        ...

    def add_text_block(self, page: int, rect: Rect, text: str = "") -> BlockData:
        """F-005."""
        ...

    def delete_block(self, page: int, block_id: int) -> None:
        """F-006: fundalul se completeaza."""
        ...

    def move_block(self, page: int, block_id: int, dx: Px, dy: Px) -> None:
        """F-007."""
        ...

    def resize_block(self, page: int, block_id: int, rect: Rect) -> None:
        """F-008: latime minima 10 px."""
        ...

    def apply_text_format(self, page: int, block_id: int, **attrs: Any) -> None:
        """F-010..F-018. `font_size` intre 1 si 1638 pt."""
        ...

    def edit_table_cell(
        self, page: int, area_id: int, row: int, col: int, text: str
    ) -> None:
        """F-019: structura tabelului rămâne."""
        ...

    def add_picture(self, page: int, image: Path, at: Point) -> int:
        """F-020."""
        ...

    def transform_picture(
        self,
        page: int,
        picture_id: int,
        *,
        rect: Rect | None = None,
        rotation: float | None = None,
    ) -> None:
        """F-021."""
        ...

    def delete_picture(self, page: int, picture_id: int) -> None:
        """F-022: fundalul se completeaza."""
        ...

    def bring_to_front(self, page: int, object_id: int) -> None:
        """F-023."""
        ...

    def erase_region(self, page: int, rect: Rect) -> None:
        """F-024, F-033: continutul dispare din pagina **si din stratul de
        text**. Culoarea fundalului se detecteaza automat."""
        ...

    def replace_text_layer(
        self, page: int, settings: OcrSettings
    ) -> None:
        """F-026: stratul vechi se pierde; apelantul confirma intai."""
        ...

    def add_header_footer(
        self,
        *,
        position: str,
        content: str,
        pages: Sequence[int] | None = None,
        margin: float = 1.0,
        margin_unit: str = "cm",
        font_name: str | None = None,
        font_size: float | None = None,
        text_color: str | None = None,
        bates_start: int | None = None,
        bates_digits: int = 6,
    ) -> None:
        """F-031..F-037. `content` suporta variabilele {page}, {bates}, {date},
        {time} si text liber, combinabile in acelasi camp (F-032)."""
        ...

    def add_watermark(
        self,
        *,
        text: str | None = None,
        image: Path | None = None,
        position: str = "center",
        offset: tuple[float, float] = (0.0, 0.0),
        rotation: float = 0.0,
        opacity: float = 0.3,
        behind_content: bool = False,
        pages: Sequence[int] | None = None,
    ) -> None:
        """F-038..F-040."""
        ...

    def remove_watermarks(self) -> int:
        """F-041: se sterg doar filigranele adaugate de aplicatie."""
        ...


class FormEditor:
    """H-001..H-052."""

    def __init__(self, document: PdfDocument) -> None: ...

    def fields(self, page: int | None = None) -> list[FormFieldData]: ...

    def validate_field_name(self, name: str) -> None:
        """H-013: nevid, unic, fara punct la inceput, la sfarsit sau dublat.
        Erori: `InvalidFieldNameError`, `DuplicateFieldNameError`."""
        ...

    def create_field(self, data: FormFieldData) -> FormFieldData:
        """H-004..H-012. Dimensiuni minime 8x8 px (H-005)."""
        ...

    def update_field(self, data: FormFieldData) -> FormFieldData: ...
    def delete_fields(self, names: Sequence[str]) -> None: ...

    def copy_field(self, name: str) -> FormFieldData:
        """H-040: pentru un camp de semnatura deja semnat ridica
        `SignedFieldCopyError`. Numele copiei se incrementeaza."""
        ...

    def create_linked_copy(self, name: str) -> FormFieldData:
        """H-041: copia are acelasi nume si aceeasi valoare."""
        ...

    def alignment_guides(
        self, moving: FormFieldData, others: Sequence[FormFieldData]
    ) -> list[tuple[str, float]]:
        """H-043: ghidajele apar la X sau Y identice."""
        ...

    def validate_document(self) -> list[CoreError]:
        """Verificarile care nu pot fi facute pe un singur camp:
        `OrphanRadioButtonError` pentru grupuri cu un singur buton (H-013)."""
        ...

    def set_value(self, name: str, value: str) -> None:
        """H-048: respecta `is_readonly` si `max_symbols`."""
        ...

    def incomplete_required(self) -> list[FormFieldData]:
        """H-047: campurile obligatorii necompletate. **Doar pentru avertisment:
        nu blocheaza salvarea, trimiterea sau tiparirea.**"""
        ...

    def load_data(self, path: Path) -> tuple[int, list[str]]:
        """H-049: FDF sau XFDF. Intoarce (campuri completate, campuri
        necunoscute ignorate)."""
        ...

    def save_data(self, path: Path, fmt: str = "fdf") -> None:
        """H-050: fdf, xfdf sau html."""
        ...

    def reset(self) -> None:
        """H-051."""
        ...


@dataclass(slots=True)
class SecurityOptions:
    """G-001..G-009."""

    open_password: str | None = None
    permissions_password: str | None = None
    print_permission: PrintPermission = PrintPermission.HIGH_RES
    allow_editing: bool = True
    allow_copying: bool = True
    allow_annotations: bool = True
    allow_form_filling: bool = True
    allow_screen_readers: bool = True
    allow_assembly: bool = True
    encryption: EncryptionLevel = EncryptionLevel.AES_256
    encrypt_metadata: bool = True

    def validate(self) -> None:
        """G-002: `SamePasswordError` cand cele doua parole coincid."""
        ...


class SecurityService:
    """G-001..G-009, G-020..G-033."""

    def apply(self, document: PdfDocument, options: SecurityOptions) -> None: ...
    def remove_protection(self, document: PdfDocument, password: str) -> None: ...

    def redact_regions(
        self, document: PdfDocument, regions: Sequence[tuple[int, Rect]], color: str
    ) -> None:
        """G-020, G-021: continutul dispare din pagina si din stratul de text.

        **Dupa fiecare redactare se extrage textul si se verifica absenta.**
        Daca textul se mai gaseste, operatia se anuleaza si se ridica
        `RedactionVerificationError`: o redactare care lasa textul in fisier e
        mai rea decat una care eșuează vizibil.
        """
        ...

    def redact_by_keywords(
        self,
        document: PdfDocument,
        keywords: Sequence[str],
        *,
        match_case: bool = False,
        whole_word: bool = False,
    ) -> int:
        """C-016, C-017: intoarce numarul de aparitii redactate."""
        ...

    def delete_objects_and_data(
        self,
        document: PdfDocument,
        *,
        hidden_text_and_objects: bool = False,
        comments_and_markup: bool = False,
        links_media_actions_scripts_form_data: bool = False,
        bookmarks: bool = False,
        attachments: bool = False,
        metadata: bool = False,
    ) -> None:
        """G-031, G-032: `hidden_text_and_objects=True` **converteste documentul
        in PDF imagine**; apelantul avertizeaza intai."""
        ...


@dataclass(slots=True)
class SignatureOptions:
    """G-010..G-020."""

    certificate_id: str
    page: int
    rect: Rect
    reason: str | None = None
    location: str | None = None
    contact: str | None = None
    hash_algorithm: str = "SHA-256"
    timestamp_url: str | None = None
    show_reason: bool = True
    show_location: bool = False
    show_contact: bool = False
    show_date: bool = True
    show_owner: bool = True
    show_app_version: bool = False
    show_labels: bool = True
    borders_and_background: bool = True
    image: Path | None = None


class SignatureService:
    """G-010..G-054."""

    def list_certificates(self) -> list[tuple[str, str, str]]:
        """(id, titular, emitent). Doar certificate cu cheie privata."""
        ...

    def certificate_details(self, cert_id: str) -> Mapping[str, Any]:
        """G-011."""
        ...

    def sign(
        self,
        document: PdfDocument,
        options: SignatureOptions,
        *,
        pin_callback: Callable[[], str] | None = None,
        allow_without_timestamp: bool = False,
    ) -> None:
        """Erori: `NoCertificateError`; `TimestampUnavailableError` cand
        serverul nu raspunde si `allow_without_timestamp` e False (G-037).
        PIN-ul pentru smartcard e cerut de sistem, nu de aplicatie (G-021)."""
        ...

    def validate_all(self, document: PdfDocument) -> list[Mapping[str, Any]]:
        """G-022: se ruleaza la deschidere. Un certificat expirat da starea
        'valida, dar certificatul a expirat', nu 'invalida'."""
        ...

    def delete_signature(self, document: PdfDocument, sig_id: int) -> None:
        """G-024: `CertificateNotOwnedError` fara certificatul potrivit."""
        ...


class FontMatcher:
    """F-004. **Aceasta clasa exista din cauza unei reguli care nu apare in
    documentatie si care a fost declarata de ABBYY intr-un webinar: la editarea
    unui PDF, fontul original nu se pastreaza; se alege cel mai apropiat font
    instalat.** Alternativa trebuie sa faca acelasi lucru explicit, ca sa nu
    produca text cu metrici greșite."""

    def installed_fonts(self) -> list[str]: ...

    def match(
        self,
        pdf_font_name: str,
        *,
        is_bold: bool = False,
        is_italic: bool = False,
        is_serif: bool | None = None,
        is_monospace: bool | None = None,
    ) -> tuple[str, float]:
        """Intoarce (numele fontului instalat, scorul de potrivire 0..1).

        Potrivirea se face pe: numele familiei, apoi pe clasa (serif, sans,
        monospace), apoi pe metrici (inaltimea x, latimea medie, inaltimea
        ascendentelor). Cand nu exista nicio potrivire rezonabila, intoarce
        fontul implicit cu scor 0 si apelantul noteaza asta in jurnal.
        """
        ...

    def can_embed(self, font_name: str) -> bool:
        """Unele fonturi instalate nu permit incorporarea; exportul trebuie sa
        stie asta inainte, nu sa eșueze la scriere."""
        ...


class GlyphRecovery:
    """F-002. Pentru PDF-urile in care textul se copiaza ca mojibake: tabelul de
    codificare e greșit, dar formele literelor sunt corecte. Se recunosc formele
    si se reconstruiește textul."""

    def needs_recovery(self, document: PdfDocument, page: int) -> bool:
        """Euristica: procent mare de caractere din zone neasteptate ale
        Unicode, sau procent mic de cuvinte gasite in dictionar."""
        ...

    def recover(
        self, document: PdfDocument, page: int, settings: OcrSettings
    ) -> list[BlockData]: ...


# =============================================================================
# 11. EXPORT
# =============================================================================


@runtime_checkable
class Exporter(Protocol):
    """Un exportator per format. Q-010..Q-022, X-060..X-068."""

    format: ExportFormat
    supported_layout_modes: frozenset[LayoutMode]

    def default_options(self) -> ExportOptions: ...

    def validate(self, options: ExportOptions) -> None:
        """Q-001: `IncompatibleLayoutError` cand modul nu e in
        `supported_layout_modes`."""
        ...

    def export(
        self,
        pages: Sequence[PageData],
        target: Path,
        options: ExportOptions,
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[Path]:
        """Intoarce fisierele scrise: mai multe cand
        `options.separate_file_per_page` (Q-022)."""
        ...


class ExportService:
    """Punctul unic de export. Verifica regulile inainte de a chema
    exportatorul, ca aceeasi regula sa nu fie scrisa de mai multe ori."""

    def register(self, exporter: Exporter) -> None: ...
    def formats_for(self, mode: LayoutMode) -> list[ExportFormat]:
        """Q-001: ce se arata activ in interfata."""
        ...

    def check_before_export(
        self, pages: Sequence[PageData], options: ExportOptions, target: ExportFormat
    ) -> list[CoreError]:
        """Avertismentele care nu opresc exportul, dar trebuie arătate:
        - `PagesNotRecognizedError` cand exista pagini invalidate (Q-051)
        - `NoTextFoundError` pentru XLSX fara tabele (Q-014)
        Apelantul decide dacă merge inainte."""
        ...

    def export(
        self,
        pages: Sequence[PageData],
        target: Path,
        fmt: ExportFormat,
        options: ExportOptions,
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[Path]: ...

    def export_page_images(
        self,
        pages: Sequence[PageData],
        target: Path,
        fmt: ExportFormat,
        *,
        dpi: int = 300,
        multipage: bool = False,
        compression: str | None = None,
    ) -> list[Path]:
        """Q-020, I-009: TIFF, PDF, JBIG2 si DCX accepta multipagina."""
        ...

    def reduce_file_size(
        self,
        document: PdfDocument,
        target: Path,
        *,
        image_quality: ImageQuality,
        use_mrc: bool,
        languages: Sequence[LanguageCode],
    ) -> tuple[int, int]:
        """I-010: intoarce (dimensiune inainte, dimensiune dupa)."""
        ...

    def verify_pdfa(self, path: Path, version: PdfAVersion) -> list[str]:
        """I-006: lista de abateri; lista goala inseamna conform. Verificarea se
        face pe fisierul scris, nu pe modelul din memorie."""
        ...


# =============================================================================
# 12. COMPARAREA DOCUMENTELOR
# =============================================================================


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


@dataclass(slots=True)
class CompareOptions:
    """R-008, R-023..R-033."""

    languages: tuple[LanguageCode, ...] = ("ron", "eng")
    ignore_whitespace: bool = True
    ignore_hyphenation: bool = True
    ignore_tables: bool = False
    ignore_headers_footers: bool = False
    group_distance_words: int = 3
    """R-034: diferentele din acelasi paragraf, la mai putin de atatea cuvinte
    una de alta, se unesc."""


class DocumentComparer:
    """R-001..R-068."""

    SUPPORTED_FORMATS: frozenset[str]
    """R-002: PDF, DOCX, XLSX, PPTX, RTF, TXT, ODT, HTML si imagini."""

    def can_compare(self, path: Path) -> bool: ...

    def extract_text(
        self,
        path: Path,
        options: CompareOptions,
        *,
        password: PasswordCallback | None = None,
        progress: ProgressCallback | None = None,
    ) -> list[tuple[int, str, Rect]]:
        """R-007, R-020: (pagina, cuvant, poziție). Pe un document fara strat de
        text ruleaza OCR intai; dacă nici asa nu gaseste text, ridica
        `NoTextFoundError`."""
        ...

    def compare(
        self,
        left: Path,
        right: Path,
        options: CompareOptions,
        *,
        password: PasswordCallback | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[Difference]:
        """R-021, R-022, R-036: diferenta pe secvente de cuvinte, cu ancore pe
        paragrafe identice. Documentele de peste 100 de pagini se compara pe
        blocuri, cu progres."""
        ...

    def save_as_pdf_with_comments(
        self, right: Path, differences: Sequence[Difference], target: Path
    ) -> None:
        """R-050: fiecare diferenta devine o adnotare pe documentul 2."""
        ...

    def save_as_word_table(
        self, differences: Sequence[Difference], target: Path
    ) -> None:
        """R-064: tabel cu textul vechi, textul nou si numarul paginii."""
        ...

    def save_report(
        self, differences: Sequence[Difference], target: Path
    ) -> None:
        """R-064: diferentele ignorate nu apar."""
        ...


# =============================================================================
# 13. AUTOMATIZARE
# =============================================================================


@dataclass(slots=True)
class TaskStep:
    step_type: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AutomatedTask:
    name: str
    steps: list[TaskStep] = field(default_factory=list)
    is_builtin: bool = False
    shortcut: str | None = None
    description: str | None = None


class AutomatedTaskRunner:
    """T-001..T-018."""

    def all_tasks(self) -> list[AutomatedTask]: ...
    def builtin_tasks(self) -> list[AutomatedTask]:
        """T-003: Convert to PDF, Convert to searchable PDF, Convert to Word,
        Convert to Excel, Convert photo to Word, Scan to PDF, Scan to Word,
        Scan to Excel, Scan to images."""
        ...

    def validate(self, task: AutomatedTask) -> None:
        """T-012: primul pas trebuie sa fie `get_images`; un pas de salvare in
        format text cere un pas de recunoastere inainte. `TaskValidationError`
        poarta indexul pasului problematic."""
        ...

    def save(self, task: AutomatedTask) -> None:
        """T-002: `BuiltinNotEditableError` pentru sarcinile livrate."""
        ...

    def duplicate(self, name: str) -> AutomatedTask: ...
    def delete(self, name: str) -> None: ...

    def set_shortcut(self, name: str, shortcut: str | None) -> None:
        """T-015: `ShortcutConflictError` dacă e deja folosita."""
        ...

    def run(
        self,
        task: AutomatedTask,
        inputs: Sequence[Path],
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[tuple[Path, Path | None, CoreError | None]]:
        """T-013: (intrare, ieșire, eroare). Un fisier care eșuează nu opreste
        lotul (A-028)."""
        ...

    def export_task(self, name: str, path: Path) -> None:
        """T-016."""
        ...

    def import_task(self, path: Path) -> AutomatedTask:
        """T-017: `ProjectVersionError` pentru o versiune incompatibila."""
        ...


@dataclass(slots=True)
class HotFolderTask:
    """S-004..S-065."""

    name: str
    source_kind: str
    source_path: str
    include_subfolders: bool = False
    file_pattern: str = "*"
    credential_ref: str | None = None
    """S-007: parola NU se tine aici; se pastreaza o referinta catre magazinul
    de credentiale al sistemului."""
    original_action: str = "keep"
    original_move_to: str | None = None
    schedule_kind: str = "on_new_file"
    schedule_at: str | None = None
    schedule_interval_minutes: int | None = None
    schedule_time: str | None = None
    schedule_days: tuple[int, ...] = ()
    steps: list[TaskStep] = field(default_factory=list)
    max_parallel: int = 2
    notify_on_error: bool = False
    notify_email: str | None = None
    is_enabled: bool = False


class HotFolderService:
    """S-001..S-034. Editia Corporate."""

    FILE_STABLE_SECONDS: int = 3
    """S-015. [DECIZIE] Un fisier se considera complet copiat dupa ce
    dimensiunea nu se mai schimba 3 secunde."""

    MAX_RETRIES: int = 3
    """S-033. [DECIZIE] Dupa 3 incercari fisierul merge in subfolderul
    `Errors` si nu se mai reprocesează."""

    def tasks(self) -> list[HotFolderTask]: ...
    def validate(self, task: HotFolderTask) -> None:
        """S-016: minimum un pas de analiza sau de recunoastere; un pas de
        salvare are nevoie de format si de folder tinta."""
        ...

    def save(self, task: HotFolderTask) -> None: ...
    def delete(self, name: str) -> None:
        """S-064: o sarcina care ruleaza se opreste intai."""
        ...

    def test_source(self, task: HotFolderTask) -> None:
        """S-005, S-007: verifica folderul sau conexiunea FTP inainte de
        salvare. Erori: `NoWritePermissionError`, `CoreError` cu mesajul
        serverului."""
        ...

    def start(self, name: str) -> None: ...
    def stop(self, name: str) -> None:
        """S-061: se termina fisierul curent."""
        ...

    def run_now(self, name: str) -> None:
        """S-060."""
        ...

    def is_file_ready(self, path: Path) -> bool:
        """S-015."""
        ...

    def log_entries(
        self, name: str, *, limit: int = 200
    ) -> list[Mapping[str, Any]]:
        """S-030: jurnal per sarcina, cu rotatie la 10 MB."""
        ...

    def install_service(self) -> None:
        """S-031: sarcinile ruleaza si cand niciun utilizator nu e conectat.
        Fara drepturi de administrator ridica `NoWritePermissionError`."""
        ...


# =============================================================================
# 14. SCREENSHOT READER
# =============================================================================


class ScreenshotReader:
    """V-001..V-018. Ruleaza independent de aplicatia principala."""

    def capture_area(self, rect: Rect, display: int | None = None) -> LoadedImage:
        """V-003: minimum 10x10 px. Zona poate traversa monitoare (V-007).
        Fereastra utilitarului nu apare in captura (V-016)."""
        ...

    def capture_window(self, window_id: int) -> LoadedImage:
        """V-004."""
        ...

    def capture_screen(self, display: int | None = None) -> LoadedImage:
        """V-005."""
        ...

    def capture_timed(self, delay_s: int, display: int | None = None) -> LoadedImage:
        """V-006: intre 1 si 60 de secunde."""
        ...

    def to_text(self, image: LoadedImage, languages: Sequence[LanguageCode]) -> str:
        """V-008."""
        ...

    def to_table(
        self, image: LoadedImage, languages: Sequence[LanguageCode]
    ) -> list[list[str]]:
        """V-009."""
        ...

    def last_region(self) -> Rect | None:
        """V-015: None cand nu exista captura anterioara."""
        ...


# =============================================================================
# 15. SERVICII TRANSVERSALE
# =============================================================================


@runtime_checkable
class UndoStack(Protocol):
    """J-041, E-040: minimum 50 de pasi. Persistat in baza de date ca sa
    supravietuiasca unei caderi."""

    def push(
        self,
        operation: str,
        description: str,
        forward: Mapping[str, Any],
        reverse: Mapping[str, Any],
    ) -> None: ...

    def can_undo(self) -> bool: ...
    def can_redo(self) -> bool: ...
    def undo(self) -> Mapping[str, Any]: ...
    def redo(self) -> Mapping[str, Any]: ...
    def clear(self) -> None:
        """Se goleste la inchiderea curata a documentului."""
        ...


@runtime_checkable
class RecentStore(Protocol):
    """A-052..A-055."""

    def add(self, path: Path, kind: str, page_count: int | None = None) -> None: ...
    def all(self, limit: int = 50) -> list[Mapping[str, Any]]: ...
    def search(self, query: str) -> list[Mapping[str, Any]]:
        """A-053: cautare in nume si in cale, fara diacritice."""
        ...

    def remove(self, path: Path) -> None: ...
    def clear(self) -> None: ...
    def remember_position(self, path: Path, page: int, zoom: float) -> None: ...


@runtime_checkable
class ShortcutRegistry(Protocol):
    """X-085, X-086."""

    def all(self) -> list[Mapping[str, Any]]: ...
    def assign(self, command_id: str, shortcut: str | None) -> None:
        """`ShortcutConflictError` cand e deja folosita."""
        ...

    def reset_defaults(self) -> None: ...


class CommandLine:
    """U-001..U-050. Stratul subtire peste nucleu. Nu are logica proprie:
    traduce argumente in apeluri si excepții in coduri de ieșire."""

    EXIT_OK: int = 0
    EXIT_BAD_ARGS: int = 1
    EXIT_FILE_ERROR: int = 2
    EXIT_RECOGNITION_ERROR: int = 3
    EXIT_WRITE_ERROR: int = 4
    EXIT_CANCELLED: int = 5

    def run(self, argv: Sequence[str]) -> int:
        """U-027: intoarce codul de ieșire. Erorile se scriu la stderr; cu
        `/json` rezultatul structurat merge la stdout (U-023)."""
        ...

    def exit_code_for(self, error: CoreError) -> int:
        """Maparea excepție → cod de ieșire, intr-un singur loc."""
        ...


class ApplicationHealth:
    """Y-005, Y-006, Y-016, X-089."""

    def check_startup(self) -> list[CoreError]:
        """Y-005: verifica fonturile, modelele de limba si folderul temporar.
        Intoarce lista problemelor, nu arunca: aplicatia trebuie sa porneasca si
        sa spuna ce lipseste."""
        ...

    def temp_folder(self) -> Path: ...
    def free_space_bytes(self) -> int: ...
    def cleanup_temp(self) -> int:
        """Y-016: la inchidere si la pornire, pentru resturile de la o cadere.
        Intoarce octetii eliberati."""
        ...

    def log_folder(self) -> Path:
        """Y-006."""
        ...


def iter_all_requirement_ids() -> Iterable[str]:
    """Utilitar de testare: extrage din acest fisier toate ID-urile de cerinte
    menționate in docstring-uri, ca planul de testare (SPEC_06) sa poata
    verifica automat ca nicio cerinta nu a ramas fara un punct de intrare in
    API."""
    ...
