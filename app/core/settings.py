"""Setarile aplicatiei: catalogul cheilor X-* si stocarea lor in app.db.

Implementeaza SPEC_05_api_core.py sectiunea 4 (PreprocessSettings,
OcrSettings, SettingsStore) peste tabela `setting` din SPEC_04, plus
exportul si importul setarilor intr-un fisier JSON (Y-022, pasul 0c).

Lista cheilor si deciziile luate sunt in docs/plan/faza_0b_setari.md,
confirmata de utilizator. ID-urile din comentarii sunt cele din SPEC_03
capitolul X; docstring-urile din SPEC_05 sectiunea 4 folosesc o numerotare
veche (vezi documentul de plan).

Doar nucleul: dialogul Options vine in faza GUI. ExportOptions (tot
sectiunea 4) se implementeaza in faza 6, in app/core/export/base.py.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.model import (
    AreaType,
    AutoProcessMode,
    ExportFormat,
    ImageQuality,
    LanguageCode,
    LayoutMode,
    OcrQuality,
    PdfAVersion,
    PdfRecognitionMode,
    PrintType,
)

# =============================================================================
# SPEC_05 sectiunea 4 — structurile de setari
# =============================================================================


# X-010..X-031 (SPEC_05 le numeste X-010..X-023, numerotare veche)
@dataclass(slots=True)
class PreprocessSettings:
    """Setarile de preprocesare efective. Optiunile marcate `photo_only` se
    aplica doar fotografiilor (L-018)."""

    auto_mode: AutoProcessMode = AutoProcessMode.READ
    split_facing_pages: bool = False
    correct_orientation: bool = True
    use_recommended: bool = True
    deskew: bool = True
    straighten_lines: bool = True
    correct_resolution: bool = True
    detect_page_edges: bool = True  # photo_only
    whiten_background: bool = True  # photo_only
    reduce_iso_noise: bool = True  # photo_only
    remove_motion_blur: bool = False  # photo_only
    fix_inverted_colors: bool = True
    convert_to_bw: bool = False
    """X-029: nerecomandat pentru foto, reviste si scrieri asiatice."""
    remove_color_marks: bool = False
    """X-030, L-014: doar scanari cu fundal alb."""


# X-040..X-068, X-141, X-167 (SPEC_05 le numeste X-040..X-049)
@dataclass(slots=True)
class OcrSettings:
    languages: tuple[LanguageCode, ...] = ("ron", "eng")
    pdf_mode: PdfRecognitionMode = PdfRecognitionMode.AUTO
    quality: OcrQuality = OcrQuality.THOROUGH
    print_type: PrintType = PrintType.AUTO
    detect_headers_footers: bool = True
    detect_numbered_lists: bool = True
    detect_table_of_contents: bool = True
    detect_footnotes: bool = True
    convert_barcodes_to_text: bool = False
    """X-066: dezactivat implicit."""
    use_builtin_patterns: bool = True
    use_user_patterns: bool = False
    also_use_builtin: bool = False
    use_training: bool = False
    """X-067: dezactivat implicit."""
    confidence_threshold: float = 70.0
    """X-167. [DECIZIE] Valoarea 70 e alegerea noastra; originalul nu o publica."""
    header_repeat_ratio: float = 0.5
    """N-016. [DECIZIE] Un text se considera antet daca apare in aceeasi pozitie
    pe mai mult de jumatate din pagini."""
    max_threads: int | None = None
    """X-141: None = toate nucleele minus unul."""


# SPEC_05 sect. 4 — contractul. X.*, J-039
@runtime_checkable
class SettingsStore(Protocol):
    """Setarile globale si cele suprascrise pe proiect (X.*, J-039).
    Cheile sunt cele din tabelul `setting`: 'ocr.quality', 'image.deskew'."""

    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def get_typed(self, key: str, kind: type) -> Any: ...
    def reset_all(self) -> None: ...
    def export_to(self, path: Path) -> None: ...
    def import_from(self, path: Path) -> None: ...
    def ocr_settings(self) -> OcrSettings: ...
    def preprocess_settings(self) -> PreprocessSettings: ...
    def with_overrides(self, overrides: Mapping[str, Any]) -> SettingsStore: ...


# =============================================================================
# Catalogul cheilor
# =============================================================================

EXPORT_FORMAT = "doculens-settings"
EXPORT_VERSION = 1
"""Y-022: versiunea formatului de export. Se mareste doar la o schimbare incompatibila."""

VALUE_TYPES = ("bool", "int", "float", "string", "enum", "json", "path", "color")
"""Exact valorile permise de CHECK-ul coloanei setting.value_type (SPEC_04)."""

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True, slots=True)
class SettingDef:
    """Descrierea unei chei: ce tip are, ce valoare livrata, ce e permis."""

    key: str
    value_type: str
    default: Any
    spec_id: str
    min_value: float | None = None
    max_value: float | None = None
    allowed: tuple[str, ...] | None = None
    nullable: bool = False
    check: Callable[[Any], str | None] | None = None
    """Validare suplimentara: intoarce motivul refuzului sau None."""

    def validate(self, value: Any) -> Any:
        """Intoarce valoarea normalizata sau arunca ValueError."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError(f"{self.key}: valoarea nu poate lipsi")
        normalized = _NORMALIZERS[self.value_type](self, value)
        if self.check is not None:
            reason = self.check(normalized)
            if reason:
                raise ValueError(f"{self.key}: {reason}")
        return normalized


def _norm_bool(d: SettingDef, v: Any) -> bool:
    if not isinstance(v, bool):
        raise ValueError(f"{d.key}: se asteapta bool, nu {type(v).__name__}")  # noqa: TRY004 — SPEC_05: set() ridica ValueError
    return v


def _in_range(d: SettingDef, v: float) -> None:
    if d.min_value is not None and v < d.min_value:
        raise ValueError(f"{d.key}: {v} e sub minimul {d.min_value:g}")
    if d.max_value is not None and v > d.max_value:
        raise ValueError(f"{d.key}: {v} e peste maximul {d.max_value:g}")


def _norm_int(d: SettingDef, v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{d.key}: se asteapta un numar intreg, nu {v!r}")  # noqa: TRY004 — SPEC_05: set() ridica ValueError
    _in_range(d, v)
    return v


def _norm_float(d: SettingDef, v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise ValueError(f"{d.key}: se asteapta un numar, nu {v!r}")  # noqa: TRY004 — SPEC_05: set() ridica ValueError
    v = float(v)
    if math.isnan(v):
        raise ValueError(f"{d.key}: NaN nu e o valoare valida")
    _in_range(d, v)
    return v


def _norm_string(d: SettingDef, v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{d.key}: se asteapta text, nu {type(v).__name__}")  # noqa: TRY004 — SPEC_05: set() ridica ValueError
    return v


def _norm_enum(d: SettingDef, v: Any) -> str:
    if isinstance(v, Enum):
        v = v.value
    assert d.allowed is not None
    if v not in d.allowed:
        raise ValueError(f"{d.key}: {v!r} nu e in {list(d.allowed)}")
    return v


def _norm_json(d: SettingDef, v: Any) -> Any:
    if isinstance(v, tuple):
        v = list(v)
    try:
        return json.loads(json.dumps(v))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{d.key}: valoarea nu se poate salva ca JSON: {exc}") from exc


def _norm_path(d: SettingDef, v: Any) -> str:
    if not isinstance(v, str | Path) or str(v) == "":
        raise ValueError(f"{d.key}: se asteapta o cale")
    return str(v)


def _norm_color(d: SettingDef, v: Any) -> str:
    if not isinstance(v, str) or not _COLOR_RE.match(v):
        raise ValueError(f"{d.key}: culoarea trebuie sa fie #RRGGBB, nu {v!r}")
    return v.upper()


_NORMALIZERS: dict[str, Callable[[SettingDef, Any], Any]] = {
    "bool": _norm_bool,
    "int": _norm_int,
    "float": _norm_float,
    "string": _norm_string,
    "enum": _norm_enum,
    "json": _norm_json,
    "path": _norm_path,
    "color": _norm_color,
}


def _language_list(v: Any) -> str | None:
    """P-001: minimum o limba; codurile sunt text nevid, fara duplicate."""
    if not isinstance(v, list) or not v:
        return "trebuie selectata cel putin o limba"
    if not all(isinstance(x, str) and x.strip() for x in v):
        return "codurile de limba trebuie sa fie text nevid"
    if len(set(v)) != len(v):
        return "o limba apare de doua ori"
    return None


def _string_list_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
        return "se asteapta o lista de nume"
    return None


_DELETE_OBJECT_ITEMS = ("comments", "links_media_forms", "bookmarks", "attachments")


def _delete_objects_items(v: Any) -> str | None:
    """X-084: cele patru elemente care se pot sterge la salvare."""
    if not isinstance(v, list) or not all(x in _DELETE_OBJECT_ITEMS for x in v):
        return f"elementele permise sunt {list(_DELETE_OBJECT_ITEMS)}"
    if len(set(v)) != len(v):
        return "un element apare de doua ori"
    return None


def _ratio_above_zero(v: float) -> str | None:
    return "trebuie sa fie mai mare decat 0" if v <= 0 else None


def _values(enum_cls: type[Enum]) -> tuple[str, ...]:
    return tuple(e.value for e in enum_cls)


def _layouts_for(fmt: ExportFormat) -> tuple[str, ...]:
    """Q-001..Q-006: modurile de layout in care formatul e permis."""
    return tuple(m.value for m in LayoutMode if fmt in ExportFormat.allowed_for(m))


# M-100, X-165: culorile zonelor sunt setari, nu constante. Paleta e a noastra,
# nu cea ABBYY (CLAUDE.md §6.6); confirmata in docs/plan/faza_0b_setari.md.
_AREA_COLORS: dict[AreaType, str] = {
    AreaType.RECOGNITION: "#6B7280",
    AreaType.TEXT: "#0F9D8A",
    AreaType.TABLE: "#D97706",
    AreaType.PICTURE: "#7C3AED",
    AreaType.BACKGROUND_PICTURE: "#C084FC",
    AreaType.BARCODE: "#DC2626",
}


def _b(key: str, default: bool, spec_id: str) -> SettingDef:
    return SettingDef(key, "bool", default, spec_id)


def _e(key: str, default: str, allowed: tuple[str, ...], spec_id: str) -> SettingDef:
    return SettingDef(key, "enum", default, spec_id, allowed=allowed)


_IMAGE_QUALITY = _values(ImageQuality)
_ENCODINGS = ("utf-8", "utf-16", "windows-1250", "iso-8859-2")

CATALOG: tuple[SettingDef, ...] = (
    # --- 1. General ---------------------------------------------------------
    _e("general.startup_screen", "new_task",
       ("new_task", "ocr_new_project", "ocr_last_project"), "X-001"),
    SettingDef("general.capture_device", "string", None, "X-002", nullable=True),
    _e("general.scan_interface", "app", ("app", "driver"), "X-003"),
    _b("general.shell_integration", True, "X-005"),
    # --- 2. Image Processing -------------------------------------------------
    _b("image.background_recognition_pdf", True, "X-010"),
    _b("image.auto_process", True, "X-011"),
    _e("image.auto_mode", "recognize", ("recognize", "analyze", "preprocess"), "X-012"),
    _e("image.preprocess_mode", "auto", ("auto", "manual", "none"), "X-014"),
    _b("image.split_facing_pages", False, "X-016"),
    _b("image.correct_orientation", True, "X-017"),
    _b("image.use_recommended", True, "X-018"),
    _b("image.deskew", True, "X-020"),
    _b("image.straighten_lines", True, "X-021"),
    _b("image.correct_resolution", True, "X-022"),
    _b("image.detect_page_edges", True, "X-023"),
    _b("image.whiten_background", True, "X-024"),
    _b("image.reduce_iso_noise", True, "X-025"),
    _b("image.remove_motion_blur", False, "X-026"),
    _b("image.correct_trapezoid", True, "X-027"),
    _b("image.fix_inverted_colors", True, "X-028"),
    _b("image.convert_to_bw", False, "X-029"),
    _b("image.remove_color_marks", False, "X-030"),
    # --- 3. Languages ---------------------------------------------------------
    _e("lang.mode", "auto", ("auto", "manual"), "X-040"),
    SettingDef("lang.auto_candidates", "json", ["ron", "eng"], "X-041", check=_language_list),
    SettingDef("lang.manual", "json", ["ron", "eng"], "X-042", check=_language_list),
    # --- 4. OCR ---------------------------------------------------------------
    _e("ocr.pdf_mode", "auto", _values(PdfRecognitionMode), "X-060"),
    _e("ocr.quality", "thorough", _values(OcrQuality), "X-062"),
    _e("ocr.document_type", "auto", _values(PrintType), "X-064"),
    _b("ocr.detect_headers_footers", True, "X-065"),
    _b("ocr.detect_footnotes", True, "X-065"),
    _b("ocr.detect_table_of_contents", True, "X-065"),
    _b("ocr.detect_numbered_lists", True, "X-065"),
    _b("ocr.barcodes_to_text", False, "X-066"),
    _b("ocr.use_training", False, "X-067"),
    _e("ocr.patterns", "builtin", ("builtin", "user"), "X-068"),
    _b("ocr.user_patterns_also_builtin", False, "X-068"),
    _b("ocr.training_also_builtin", False, "X-416"),
    SettingDef("ocr.export_fonts", "json", None, "X-071", nullable=True,
               check=_string_list_or_none),
    SettingDef("ocr.header_repeat_ratio", "float", 0.5, "N-016", min_value=0.0,
               max_value=1.0, check=_ratio_above_zero),
    SettingDef("ocr.max_threads", "int", None, "X-141", min_value=1, nullable=True),
    SettingDef("ocr.confidence_threshold", "float", 70.0, "X-167",
               min_value=0.0, max_value=100.0),
    # --- 5.1 PDF --------------------------------------------------------------
    _e("pdf.image_quality", "balanced", _IMAGE_QUALITY, "X-080"),
    _b("pdf.create_pdfa", False, "X-081"),
    _e("pdf.pdfa_version", "2b", _values(PdfAVersion), "X-081"),
    _b("pdf.create_pdfua", False, "X-082"),
    _b("pdf.protect_with_password", False, "X-083"),
    _b("pdf.delete_objects", False, "X-084"),
    SettingDef("pdf.delete_objects_items", "json", list(_DELETE_OBJECT_ITEMS), "X-084",
               check=_delete_objects_items),
    _b("pdf.single_paper_size", False, "X-085"),
    _b("pdf.use_mrc", False, "X-086"),
    _b("pdf.smooth_characters", False, "X-087"),
    _e("pdf.searchable_mode", "text_under",
       ("text_and_pictures", "text_over", "text_under"), "X-088"),
    _b("pdf.bookmarks_from_headings", False, "X-089"),
    _b("pdf.create_tags", False, "X-090"),
    _e("pdf.fonts", "predefined", ("predefined", "system"), "X-091"),
    _b("pdf.embed_fonts", True, "X-092"),
    _b("pdf.preserve_metadata", True, "X-093"),
    _b("pdf.enable_javascript", False, "X-145"),
    _b("pdf.detect_urls", True, "X-146"),
    # --- 5.2 DOC(X) / RTF / ODT -------------------------------------------------
    _e("docx.layout", "editable", _layouts_for(ExportFormat.DOCX), "X-100"),
    _e("docx.paper_size", "auto", ("auto", "a3", "a4", "a5", "letter", "legal"), "X-101"),
    _b("docx.keep_pictures", True, "X-102"),
    _b("docx.keep_headers_footers", False, "X-103"),
    _b("docx.keep_line_breaks", False, "X-104"),
    _b("docx.keep_page_breaks", True, "X-105"),
    _b("docx.keep_line_numbers", False, "X-106"),
    _b("docx.keep_colors", True, "X-107"),
    _b("docx.keep_styles_in_plain", True, "X-108"),
    _b("docx.highlight_low_confidence", False, "X-109"),
    # --- 5.3 Celelalte formate --------------------------------------------------
    _e("xlsx.layout", "formatted", _layouts_for(ExportFormat.XLSX), "X-120"),
    _b("xlsx.keep_pictures", True, "X-120"),
    _b("xlsx.keep_headers_footers", False, "X-120"),
    _b("xlsx.ignore_text_outside_tables", False, "X-120"),
    _b("xlsx.numbers_as_numbers", True, "X-120"),
    _b("xlsx.sheet_per_page", False, "X-120"),
    _b("pptx.keep_pictures", True, "X-121"),
    _b("pptx.keep_headers_footers", False, "X-121"),
    _b("pptx.keep_line_breaks", True, "X-121"),
    _b("pptx.shrink_on_overflow", True, "X-121"),
    _b("csv.ignore_text_outside_tables", True, "X-122"),
    _b("csv.page_break_char", False, "X-122"),
    _e("csv.delimiter", ";", (",", ";", "tab"), "X-122"),
    _e("csv.encoding", "utf-8", _ENCODINGS, "X-122"),
    _e("txt.layout", "plain", _layouts_for(ExportFormat.TXT), "X-123"),
    _b("txt.keep_line_breaks", True, "X-123"),
    _b("txt.page_break_char", False, "X-123"),
    _b("txt.blank_line_paragraphs", False, "X-123"),
    _b("txt.keep_headers_footers", False, "X-123"),
    _e("txt.encoding", "utf-8", _ENCODINGS, "X-123"),
    _e("html.layout", "formatted", _layouts_for(ExportFormat.HTML), "X-124"),
    _b("html.keep_pictures", True, "X-124"),
    _b("html.keep_line_breaks", False, "X-124"),
    _b("html.keep_colors", True, "X-124"),
    _b("html.keep_headers_footers", False, "X-124"),
    _e("html.encoding", "utf-8", _ENCODINGS, "X-124"),
    _e("html.book_split", "none", ("none", "auto", "h1", "h2"), "X-125"),
    _e("epub.layout", "formatted", _layouts_for(ExportFormat.EPUB), "X-126"),
    _b("epub.retain_fonts", True, "X-126"),
    _b("epub.embed_fonts", False, "X-126"),
    _b("epub.first_page_cover", False, "X-126"),
    _b("epub.keep_pictures", True, "X-126"),
    _e("epub.version", "3.0", ("2.0", "3.0"), "X-126"),
    _e("djvu.save_mode", "text_under", ("text_under", "image_only"), "X-127"),
    _e("djvu.image_quality", "balanced", _IMAGE_QUALITY, "X-127"),
    _e("djvu.multiple_layers", "auto", ("auto", "on", "off"), "X-127"),
    # --- 6. Other ---------------------------------------------------------------
    _e("ui.language", "ro", ("ro", "en"), "X-140"),
    _b("ui.dark_theme", False, "X-149"),
    SettingDef("app.temp_folder", "path", None, "X-150", nullable=True),
    # --- 7. Areas and Text ------------------------------------------------------
    _b("areas.check_uncertain", True, "X-160"),
    SettingDef("areas.uncertain_color", "color", "#FFB000", "X-166"),
    _b("areas.ignore_words_with_digits", True, "X-161"),
    _b("areas.check_compound_words", True, "X-161"),
    _b("areas.fix_punctuation_spaces", True, "X-162"),
    SettingDef("areas.user_dictionaries_folder", "path", None, "X-163", nullable=True),
    SettingDef("areas.plain_text_font", "string", None, "X-164", nullable=True),
    *(
        SettingDef(f"areas.color.{t.value}", "color", color, "X-165")
        for t, color in _AREA_COLORS.items()
    ),
    *(
        SettingDef(f"areas.border_width.{t.value}", "int", 2, "X-165",
                   min_value=1, max_value=6)
        for t in AreaType
    ),
    _b("areas.show_numbers", True, "X-168"),
    _b("areas.show_nonprinting", False, "X-169"),
)

_BY_KEY: dict[str, SettingDef] = {d.key: d for d in CATALOG}


def definition(key: str) -> SettingDef:
    """Descrierea cheii. ValueError pentru o cheie necunoscuta."""
    try:
        return _BY_KEY[key]
    except KeyError:
        raise ValueError(f"cheie de setare necunoscuta: {key!r}") from None


# =============================================================================
# Valorile efective
# =============================================================================

# X-012 -> AutoProcessMode. X-011 debifat -> NONE. Mapare confirmata in
# docs/plan/faza_0b_setari.md, intrebarea 1.
_AUTO_MODE: dict[str, AutoProcessMode] = {
    "recognize": AutoProcessMode.READ,
    "analyze": AutoProcessMode.ANALYZE_AND_READ,
    "preprocess": AutoProcessMode.PREPROCESS_ONLY,
}

# Campurile bool din PreprocessSettings -> cheia lor.
_PREPROCESS_KEYS: dict[str, str] = {
    "split_facing_pages": "image.split_facing_pages",
    "correct_orientation": "image.correct_orientation",
    "use_recommended": "image.use_recommended",
    "deskew": "image.deskew",
    "straighten_lines": "image.straighten_lines",
    "correct_resolution": "image.correct_resolution",
    "detect_page_edges": "image.detect_page_edges",
    "whiten_background": "image.whiten_background",
    "reduce_iso_noise": "image.reduce_iso_noise",
    "remove_motion_blur": "image.remove_motion_blur",
    "fix_inverted_colors": "image.fix_inverted_colors",
    "convert_to_bw": "image.convert_to_bw",
    "remove_color_marks": "image.remove_color_marks",
}


class _SettingsBase:
    """Logica comuna: tipare, structuri efective, suprascrieri.
    Subclasele dau `get`, `set` si `reset_all`."""

    def get(self, key: str, default: Any = None) -> Any:  # pragma: no cover
        raise NotImplementedError

    def get_typed(self, key: str, kind: type) -> Any:
        """Valoarea cheii convertita la `kind` (bool, int, float, str, Path sau
        o enumerare). TypeError cand valoarea nu are tipul cerut. None ramane None."""
        definition(key)
        value = self.get(key)
        if value is None:
            return None
        if isinstance(kind, type) and issubclass(kind, Enum):
            return kind(value)
        if kind is Path:
            return Path(value)
        if kind is float and isinstance(value, int) and not isinstance(value, bool):
            return float(value)
        if kind is int and isinstance(value, bool):
            raise TypeError(f"{key}: valoarea e bool, nu int")
        if not isinstance(value, kind):
            raise TypeError(f"{key}: valoarea {value!r} nu e {kind.__name__}")
        return value

    # X-012..X-031, X-413, X-414
    def preprocess_settings(self) -> PreprocessSettings:
        """Setarile de preprocesare efective.

        `image.preprocess_mode`: `none` -> toate bifele False; `auto` -> valorile
        livrate; `manual` -> bifele salvate. Bifele salvate nu se modifica la
        schimbarea modului (X-414).
        """
        if not self.get("image.auto_process"):
            auto_mode = AutoProcessMode.NONE
        else:
            auto_mode = _AUTO_MODE[self.get("image.auto_mode")]
        mode = self.get("image.preprocess_mode")
        if mode == "none":
            flags = {f: False for f in _PREPROCESS_KEYS}
        elif mode == "auto":
            flags = {f: definition(k).default for f, k in _PREPROCESS_KEYS.items()}
        else:
            flags = {f: self.get(k) for f, k in _PREPROCESS_KEYS.items()}
        return PreprocessSettings(auto_mode=auto_mode, **flags)

    # X-040..X-068, X-141, X-167, X-416
    def ocr_settings(self) -> OcrSettings:
        lang_key = "lang.auto_candidates" if self.get("lang.mode") == "auto" else "lang.manual"
        user_patterns = self.get("ocr.patterns") == "user"
        training = self.get("ocr.use_training")
        return OcrSettings(
            languages=tuple(self.get(lang_key)),
            pdf_mode=PdfRecognitionMode(self.get("ocr.pdf_mode")),
            quality=OcrQuality(self.get("ocr.quality")),
            print_type=PrintType(self.get("ocr.document_type")),
            detect_headers_footers=self.get("ocr.detect_headers_footers"),
            detect_numbered_lists=self.get("ocr.detect_numbered_lists"),
            detect_table_of_contents=self.get("ocr.detect_table_of_contents"),
            detect_footnotes=self.get("ocr.detect_footnotes"),
            convert_barcodes_to_text=self.get("ocr.barcodes_to_text"),
            use_builtin_patterns=not user_patterns,
            use_user_patterns=user_patterns,
            # X-416: fiecare bifa conteaza doar cand parintele ei e activ.
            also_use_builtin=(
                (user_patterns and self.get("ocr.user_patterns_also_builtin"))
                or (training and self.get("ocr.training_also_builtin"))
            ),
            use_training=training,
            confidence_threshold=self.get("ocr.confidence_threshold"),
            header_repeat_ratio=self.get("ocr.header_repeat_ratio"),
            max_threads=self.get("ocr.max_threads"),
        )

    # J-039
    def with_overrides(self, overrides: Mapping[str, Any]) -> OverrideSettingsStore:
        return OverrideSettingsStore(self, overrides)

    def _apply_many(self, values: Mapping[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    # Y-022: setarile se pot exporta intr-un fisier si importa inapoi.
    def export_to(self, path: Path) -> None:
        """Scrie toate setarile intr-un fisier JSON. Scrierea e atomica: un
        fisier existent nu ramane pe jumatate suprascris."""
        payload = {
            "format": EXPORT_FORMAT,
            "version": EXPORT_VERSION,
            "exported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "settings": {d.key: self.get(d.key) for d in CATALOG},
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        tmp.replace(path)

    def import_from(self, path: Path) -> None:
        """Citeste un fisier scris de `export_to`. Totul sau nimic: daca o
        singura valoare e invalida, nu se schimba nicio setare (ValueError).
        Cheile necunoscute (dintr-o versiune mai noua) se ignora."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"fisierul de setari nu e JSON valid: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("format") != EXPORT_FORMAT:
            raise ValueError("fisierul nu e un export de setari DocuLens")
        version = payload.get("version")
        if not isinstance(version, int) or version > EXPORT_VERSION:
            raise ValueError(f"versiune de export necunoscuta: {version!r}")
        values = payload.get("settings")
        if not isinstance(values, dict):
            raise ValueError("fisierul de setari nu are sectiunea 'settings'")  # noqa: TRY004 — continut gresit, nu tip gresit
        validated = {
            key: definition(key).validate(value)
            for key, value in values.items()
            if key in _BY_KEY
        }
        self._apply_many(validated)


# =============================================================================
# Stocarea in app.db
# =============================================================================


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# SPEC_04 tabela setting; SPEC_05 SettingsStore; X-147
class AppSettingsStore(_SettingsBase):
    """Setarile globale, in tabela `setting` din app.db.

    La creare adauga cheile din catalog care lipsesc si actualizeaza
    descrierea (tip, implicit, limite) celor existente, fara sa le schimbe
    valoarea. Randurile cu chei care nu mai sunt in catalog se ignora.
    """

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._cache: dict[str, Any] = {}
        self._sync_catalog()
        self._load()

    def _sync_catalog(self) -> None:
        rows = [
            (
                d.key,
                _encode(d.default),
                d.value_type,
                _encode(d.default),
                d.min_value,
                d.max_value,
                None if d.allowed is None else _encode(list(d.allowed)),
                d.spec_id,
            )
            for d in CATALOG
        ]
        with self._con:
            self._con.executemany(
                "INSERT INTO setting (key, value, value_type, default_value, min_value,"
                " max_value, allowed_values, spec_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value_type = excluded.value_type,"
                " default_value = excluded.default_value, min_value = excluded.min_value,"
                " max_value = excluded.max_value, allowed_values = excluded.allowed_values,"
                " spec_id = excluded.spec_id",
                rows,
            )

    def _load(self) -> None:
        self._cache.clear()
        for key, raw in self._con.execute("SELECT key, value FROM setting"):
            d = _BY_KEY.get(key)
            if d is None:
                continue
            try:
                self._cache[key] = d.validate(json.loads(raw))
            except (TypeError, ValueError):
                # Valoare stricata sau scrisa de o versiune cu alte reguli:
                # revine la implicit, nu blocheaza pornirea aplicatiei.
                self._cache[key] = d.default
                with self._con:
                    self._con.execute(
                        "UPDATE setting SET value = ? WHERE key = ?", (_encode(d.default), key)
                    )

    def get(self, key: str, default: Any = None) -> Any:
        """Valoarea salvata. Pentru o cheie necunoscuta intoarce `default`."""
        if key not in _BY_KEY:
            return default
        return _copy(self._cache[key])

    def set(self, key: str, value: Any) -> None:
        """Valideaza si salveaza. ValueError la cheie necunoscuta sau valoare invalida."""
        value = definition(key).validate(value)
        with self._con:
            self._con.execute("UPDATE setting SET value = ? WHERE key = ?", (_encode(value), key))
        self._cache[key] = value

    def _apply_many(self, values: Mapping[str, Any]) -> None:
        """Valori deja validate, scrise intr-o singura tranzactie."""
        with self._con:
            self._con.executemany(
                "UPDATE setting SET value = ? WHERE key = ?",
                [(_encode(v), k) for k, v in values.items()],
            )
        self._cache.update(values)

    # X-147: toate tab-urile, nu doar unul
    def reset_all(self) -> None:
        with self._con:
            self._con.execute("UPDATE setting SET value = default_value")
        self._load()


def _copy(value: Any) -> Any:
    """Listele se dau ca copie, ca apelantul sa nu modifice cache-ul."""
    return list(value) if isinstance(value, list) else value


# J-039: setarile unui proiect, peste cele globale
class OverrideSettingsStore(_SettingsBase):
    """Setarile unui proiect: valorile suprascrise, apoi cele globale.

    `set` si `reset_all` lucreaza doar pe suprascrieri; setarile globale nu se
    ating. `overrides` se salveaza de apelant in project.settings_override.
    """

    def __init__(self, base: _SettingsBase, overrides: Mapping[str, Any]) -> None:
        self._base = base
        self._overrides: dict[str, Any] = {}
        for key, value in overrides.items():
            self.set(key, value)

    @property
    def overrides(self) -> dict[str, Any]:
        """Copie a valorilor suprascrise, gata de salvat ca JSON."""
        return {k: _copy(v) for k, v in self._overrides.items()}

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return _copy(self._overrides[key])
        return self._base.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._overrides[key] = definition(key).validate(value)

    def reset_all(self) -> None:
        self._overrides.clear()

    def _apply_many(self, values: Mapping[str, Any]) -> None:
        self._overrides.update(values)
