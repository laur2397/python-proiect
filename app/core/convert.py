"""Conversia rapida din Lansator (faza 6c, pasul 6c.1): A-013…A-073.

Lista de fisiere → un format: PDF (A-035…A-038), Word (A-050…A-053), Excel
(A-060…A-063) sau celelalte (A-070), cu limbile OCR (A-039, A-051, A-061,
A-071) si, la nevoie, totul intr-un singur document, in ordinea listei
(A-024).

[DECIZIE AUTONOMA] (faza_6c_pasi.md, decizia 1) Fiecare fisier trece printr-un
proiect OCR temporar (unul singur la combinare): incarcarea, PDF-urile cu strat
de text (N-009), recunoasterea si exportul sunt cele din OCR Editor.
Eroarea unui fisier nu opreste lotul; rezultatul spune ce a reusit si ce nu
(A-028). Progresul se raporteaza pe fisiere; anularea pastreaza ce s-a scris.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.errors import CoreError, OperationCancelledError
from app.core.model import (
    AutoProcessMode,
    CancelToken,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    PasswordCallback,
    PdfAVersion,
    Progress,
    ProgressCallback,
)


class FullTextSearch(str, Enum):
    """A-036: cautarea in textul PDF-ului rezultat."""

    AS_ORIGINAL = "as_original"
    """Text numai unde originalul are strat de text."""
    TEXT_AND_IMAGES = "text_and_images"
    """Se recunosc si imaginile."""
    DISABLED = "disabled"
    """PDF doar-imagine."""


OTHER_FORMATS = (ExportFormat.PPTX, ExportFormat.ODT, ExportFormat.HTML, ExportFormat.EPUB,
                 ExportFormat.FB2, ExportFormat.RTF, ExportFormat.TXT, ExportFormat.CSV,
                 ExportFormat.DJVU)
"""A-016, A-070: `Convert to Other Formats`, in ordinea din cerinta."""

TARGETS = (ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.XLSX, *OTHER_FORMATS)

WORD_MODES = (LayoutMode.EXACT, LayoutMode.EDITABLE, LayoutMode.FORMATTED, LayoutMode.PLAIN)
"""A-050: cele patru valori din `Keep formatting` pentru Word."""

EXCEL_MODES = (LayoutMode.FORMATTED, LayoutMode.PLAIN)
"""A-060: numai doua valori pentru Excel."""

DEFAULT_PDFA = PdfAVersion.A2B
"""A-037: PDF/A-2b implicit."""


@dataclass
class ConvertSettings:
    target: ExportFormat = ExportFormat.PDF
    layout_mode: LayoutMode | None = None
    """None = modul potrivit formatului (EXACT pentru PDF, PowerPoint, DjVu; EDITABLE
    pentru Word, RTF, ODT; PLAIN pentru CSV; FORMATTED pentru restul)."""
    languages: tuple[str, ...] = ("ron",)
    keep_pictures: bool = True
    keep_headers_footers: bool = False
    sheet_per_page: bool = False
    image_quality: ImageQuality = ImageQuality.BALANCED
    full_text_search: FullTextSearch = FullTextSearch.TEXT_AND_IMAGES
    pdfa: bool = False
    pdfa_version: PdfAVersion = DEFAULT_PDFA
    use_mrc: bool = False
    combine: bool = False
    custom_dpi: int | None = None
    """A-309: `Reduce original resolution if required` (300, 150 sau 96 dpi)."""
    custom_quality: int = 85
    """A-313: calitatea JPEG la `Custom...`."""
    custom_lossless: bool = False
    """A-311: `Quality loss not allowed`."""
    pages: tuple[int, ...] | None = None
    """U-043: numai aceste pagini din fiecare fisier (de la 1); None = toate."""
    threads: int | None = None
    """U-047: firele de recunoastere (`ocr.max_threads` al proiectului temporar)."""

    def mode(self) -> LayoutMode:
        if self.layout_mode is not None:
            return LayoutMode(self.layout_mode)
        target = ExportFormat(self.target)
        if target in (ExportFormat.PDF, ExportFormat.PPTX, ExportFormat.DJVU):
            return LayoutMode.EXACT  # Q-002: PowerPoint si DjVu numai in Exact
        if target in (ExportFormat.DOCX, ExportFormat.RTF, ExportFormat.ODT):
            return LayoutMode.EDITABLE
        if target is ExportFormat.CSV:
            return LayoutMode.PLAIN  # Q-005: CSV numai in Plain
        return LayoutMode.FORMATTED

    def validate(self) -> None:
        target = ExportFormat(self.target)
        if target not in TARGETS:
            raise ValueError(f"format de conversie necunoscut: {target.value}")
        if not self.languages:
            raise ValueError("trebuie selectata cel putin o limba (A-039)")
        if target is ExportFormat.DOCX and self.mode() not in WORD_MODES:
            raise ValueError("Word: Exact, Editable, Formatted sau Plain (A-050)")
        if target is ExportFormat.XLSX and self.mode() not in EXCEL_MODES:
            raise ValueError("Excel: numai Formatted sau Plain (A-060)")
        if target not in ExportFormat.allowed_for(self.mode()):
            raise ValueError(f"{target.value} nu e permis in modul {self.mode().value} (Q-001)")


@dataclass
class ConvertResult:
    written: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, Exception]] = field(default_factory=list)
    """Fisierele care nu s-au putut converti, cu motivul (raportul de la final)."""
    cancelled: bool = False


class ConvertJob:
    def __init__(self, files: Sequence[Path], settings: ConvertSettings, *,
                 context: Any = None, engine: Any = None,
                 password: PasswordCallback | None = None) -> None:
        if not files:
            raise ValueError("lista de fisiere e goala (A-013)")
        settings.validate()
        if settings.combine and len(files) < 2:
            raise ValueError("combinarea cere cel putin doua fisiere (A-024)")
        self.files = [Path(f) for f in files]
        self.settings = settings
        self._context = context
        self._engine = engine
        self._password = password
        """U-045: parola PDF-urilor protejate (A-011)."""

    # --- rularea -------------------------------------------------------------------

    def run(self, folder: Path, name: str | None = None, *,
            progress: ProgressCallback | None = None,
            cancel: CancelToken | None = None) -> ConvertResult:
        """Scrie in `folder`: un fisier pe intrare, cu numele ei, sau unul singur
        (`name`) la combinare."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        result = ConvertResult()
        groups = [self.files] if self.settings.combine else [[f] for f in self.files]
        total = len(self.files)
        done = 0
        for group in groups:
            if cancel is not None and cancel():
                result.cancelled = True
                break
            stem = (name or "document") if self.settings.combine else group[0].stem
            target = self._free(folder / f"{stem}.{self._suffix()}")
            if progress is not None:
                progress(Progress(done, total, "stage.converting", group[0].name))
            try:
                written, failed = self._convert(group, target, cancel)
            except OperationCancelledError:
                result.cancelled = True
                break
            except (CoreError, ValueError, OSError) as exc:
                result.failed += [(f, exc) for f in group]
            else:
                result.written += written
                result.failed += failed
            done += len(group)
            if progress is not None:
                progress(Progress(done, total, "stage.converting", group[-1].name))
        return result

    def _suffix(self) -> str:
        return self.settings.target.value

    @staticmethod
    def _free(target: Path) -> Path:
        """Numele nu suprascrie un fisier existent: `nume (2).pdf`."""
        candidate, n = target, 1
        while candidate.exists():
            n += 1
            candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
        return candidate

    def _convert(self, files: list[Path], target: Path, cancel: CancelToken | None
                 ) -> tuple[list[Path], list[tuple[Path, Exception]]]:
        from app.core.export.base import default_service
        from app.core.ocr.service import RecognitionService
        from app.core.project import OcrProject

        project = OcrProject.create(context=self._context)
        try:
            self._configure(project.settings())
            _, errors = project.add_images(files, auto_process=AutoProcessMode.NONE,
                                           password=self._password, cancel=cancel)
            failed: list[tuple[Path, Exception]] = list(errors)
            if self.settings.pages and project.pages:  # U-043
                wanted = set(self.settings.pages)
                drop = [p.page_number for p in project.pages
                        if (p.source_page or 1) not in wanted]
                if len(drop) == len(project.pages):
                    raise ValueError("niciuna dintre paginile cerute nu exista (U-043)")
                if drop:
                    project.delete_pages(drop)
            if not project.pages:
                return [], failed
            s = self.settings
            image_only = s.target is ExportFormat.PDF and \
                s.full_text_search is FullTextSearch.DISABLED
            if not image_only:
                RecognitionService(project, engine=self._engine).recognize_pages(
                    cancel=cancel)
            fmt, options = self._options(project.settings(), image_only)
            written = default_service().export(project.pages, target, fmt, options)
            return written, failed
        finally:
            project.close()

    def _configure(self, settings: Any) -> None:
        """Setarile proiectului temporar, din alegerile conversiei."""
        s = self.settings
        settings.set("lang.mode", "manual")
        settings.set("lang.manual", list(s.languages))
        if s.threads:  # U-047
            settings.set("ocr.max_threads", int(s.threads))
        if s.target is ExportFormat.PDF:  # A-036
            settings.set("ocr.pdf_mode", "text" if s.full_text_search
                         is FullTextSearch.AS_ORIGINAL else "auto")
            settings.set("pdf.use_mrc", bool(s.use_mrc))
            settings.set("pdf.image_quality", ImageQuality(s.image_quality).value)
        if s.target is ExportFormat.DOCX:
            settings.set("docx.keep_pictures", bool(s.keep_pictures))
            settings.set("docx.keep_headers_footers", bool(s.keep_headers_footers))
        if s.target is ExportFormat.XLSX:
            settings.set("xlsx.keep_pictures", bool(s.keep_pictures))
            settings.set("xlsx.sheet_per_page", bool(s.sheet_per_page))

    def _options(self, settings: Any, image_only: bool) -> tuple[ExportFormat, Any]:
        from app.core.export.base import options_from_settings

        s = self.settings
        options = options_from_settings(settings, s.target, layout_mode=s.mode())
        if s.target is not ExportFormat.PDF:
            return s.target, options
        options.searchable = not image_only
        options.image_quality = ImageQuality(s.image_quality)
        options.use_mrc = bool(s.use_mrc)
        if options.image_quality is ImageQuality.CUSTOM:  # A-308…A-314
            options.image_dpi = s.custom_dpi
            options.format_options = {**options.format_options,
                                      "jpeg_quality": s.custom_quality,
                                      "lossless": bool(s.custom_lossless)}
        if s.pdfa:  # A-037
            options.pdfa_version = PdfAVersion(s.pdfa_version)
            return ExportFormat.PDFA, options
        return ExportFormat.PDF, options


SCAN_TIFF_COMPRESSIONS = ("packbits", "jpeg", "zip", "lzw")
"""A-088: compresiile TIFF oferite la `Scan to Image Files`, in ordinea din cerinta."""


# A-087, A-088
def save_images(files: Sequence[Path], folder: Path, name: str, fmt: ExportFormat, *,
                compression: str | None = None, multipage: bool = False,
                context: Any = None) -> list[Path]:
    """Imaginile scanate, salvate ca TIFF, JPEG sau PNG (compresia numai la TIFF)."""
    from app.core.export.base import export_page_images
    from app.core.project import OcrProject

    fmt = ExportFormat(fmt)
    if fmt not in (ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG):
        raise ValueError(f"format de imagine necunoscut: {fmt.value}")
    if compression is not None and fmt is not ExportFormat.TIFF:
        raise ValueError("compresia se alege numai pentru TIFF (A-088)")
    if compression is not None and compression not in SCAN_TIFF_COMPRESSIONS:
        raise ValueError(f"compresie necunoscuta: {compression!r}")
    project = OcrProject.create(context=context)
    try:
        project.add_images(list(files), auto_process=AutoProcessMode.NONE)
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        suffix = {ExportFormat.TIFF: ".tif", ExportFormat.JPEG: ".jpg",
                  ExportFormat.PNG: ".png"}[fmt]
        return export_page_images(project.pages, folder / f"{name}{suffix}", fmt,
                                  multipage=multipage, compression=compression)
    finally:
        project.close()


# W-012, W-013 (faza_15_pasi.md, decizia 9)
def editable_to_pdf(source: Path, target: Path | None = None) -> Path:
    """Un document editabil (DOCX, XLSX, PPTX, ODT, RTF, TXT, HTML) devine PDF, cu
    cititoarele proprii: textul, paragrafele, antetele si subsolurile. Fara
    Microsoft Office (CLAUDE.md §6.3). INCOMPLET (W-014): structura completa,
    semnele de carte si hyperlinkurile nu se pastreaza."""
    from app.core.compare.sources import (
        EDITABLE_EXTENSIONS,
        blocks_to_pdf,
        editable_blocks,
    )
    from app.core.errors import UnsupportedFormatError

    source = Path(source)
    if source.suffix.lower() not in EDITABLE_EXTENSIONS:
        raise UnsupportedFormatError("nu e un format editabil", path=str(source))
    target = Path(target) if target is not None else ConvertJob._free(source.with_suffix(".pdf"))
    target.write_bytes(blocks_to_pdf(editable_blocks(source)))
    return target
