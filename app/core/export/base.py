"""Baza exportului (faza 6, pasul 6.1): Q-001..Q-007, Q-023, Q-024, Q-051.

`ExportOptions`, `Exporter` si `ExportService` din SPEC_05 sectiunea 13.
Matricea mod → formate e `ExportFormat.allowed_for` (model.py, faza 0): 27 de
combinatii valide din 90, dupa tabelul Q-002..Q-006 (CLAUDE.md spune 29;
specificatia decide, vezi tests/test_model.py).

Documentul de exportat se citeste aici o singura data pentru toti
exportatorii: paginile alese, zonele in ordinea lor (M-022), blocurile (cu
celulele tabelelor), antetele si subsolurile numai la cerere (X-103), textul
redactat ca puncte (O-072).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.errors import (
    CoreError,
    IncompatibleLayoutError,
    NoTextFoundError,
    PagesNotRecognizedError,
    PdfAEncryptionConflictError,
)
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    CancelToken,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    PageData,
    PageStatus,
    PdfAVersion,
    Progress,
    ProgressCallback,
)

PDF_FORMATS = frozenset({ExportFormat.PDF, ExportFormat.PDFA, ExportFormat.PDFUA})
IMAGE_FORMATS = frozenset({ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG,
                           ExportFormat.JBIG2})
"""Formatele fara mod de layout: imaginile paginilor (Q-030). PDF/A si PDF/UA
urmeaza regula PDF-ului (Q-002); PDF-ul doar-imagine merge in orice mod (Q-012)."""


# SPEC_05 sect. 13
@dataclass(slots=True)
class ExportOptions:
    layout_mode: LayoutMode = LayoutMode.EDITABLE
    keep_pictures: bool = True              # Q-007
    keep_headers_footers: bool = False      # X-103
    keep_line_breaks: bool = False          # X-104
    image_quality: ImageQuality = ImageQuality.BALANCED
    image_dpi: int | None = None
    pdfa_version: PdfAVersion | None = None
    use_mrc: bool = False
    searchable: bool = True
    create_bookmarks_from_headings: bool = False
    """X-060, O-041: stilurile cu heading_level > 0 devin semne de carte."""
    tagged_pdf: bool = False
    separate_file_per_page: bool = False    # Q-022
    page_range: tuple[int, ...] | None = None
    encoding: str = "utf-8"
    format_options: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)
    password: str | None = None
    """A-028, I-006: PDF/A nu se combina cu o parola."""

    def validate(self, target: ExportFormat) -> None:
        """Q-001, A-028: `IncompatibleLayoutError` daca formatul nu e permis in
        `layout_mode`; `PdfAEncryptionConflictError` pentru PDF/A cu parola."""
        target = ExportFormat(target)
        image_only_pdf = target in PDF_FORMATS and not self.searchable
        if target not in IMAGE_FORMATS and not image_only_pdf:
            mode = LayoutMode(self.layout_mode)
            check = ExportFormat.PDF if target in PDF_FORMATS else target
            allowed = ExportFormat.allowed_for(mode)
            if check not in allowed:
                raise IncompatibleLayoutError(
                    "formatul nu e permis in acest mod de layout",
                    layout_mode=mode.value, requested_format=target.value,
                    allowed_formats=sorted(f.value for f in allowed))
        if (target is ExportFormat.PDFA or self.pdfa_version is not None) and self.password:
            raise PdfAEncryptionConflictError("PDF/A nu se poate proteja cu parola")


# SPEC_05 sect. 13
@runtime_checkable
class Exporter(Protocol):
    format: ExportFormat

    @property
    def supported_layout_modes(self) -> frozenset[LayoutMode]: ...
    def default_options(self) -> ExportOptions: ...
    def validate(self, options: ExportOptions) -> None: ...
    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]: ...


class BaseExporter:
    """Partea comuna a exportatorilor: modurile permise (din matrice) si
    validarea."""

    format: ExportFormat

    @property
    def supported_layout_modes(self) -> frozenset[LayoutMode]:
        return frozenset(m for m in LayoutMode if self.format in ExportFormat.allowed_for(m))

    def default_options(self) -> ExportOptions:
        modes = self.supported_layout_modes
        mode = LayoutMode.EDITABLE if LayoutMode.EDITABLE in modes else next(
            (m for m in LayoutMode if m in modes), LayoutMode.EXACT)
        return ExportOptions(layout_mode=mode)

    def validate(self, options: ExportOptions) -> None:
        options.validate(self.format)


# SPEC_05 sect. 13
class ExportService:
    """Punctul unic de export: regulile se verifica aici, o singura data."""

    def __init__(self) -> None:
        self._exporters: dict[ExportFormat, Exporter] = {}

    def register(self, exporter: Exporter) -> None:
        self._exporters[ExportFormat(exporter.format)] = exporter

    def formats(self) -> list[ExportFormat]:
        return list(self._exporters)

    def formats_for(self, mode: LayoutMode) -> list[ExportFormat]:
        """Q-001: ce se arata activ in interfata pentru un mod."""
        allowed = ExportFormat.allowed_for(mode)
        return [f for f in ExportFormat if f in allowed]

    def check_before_export(self, pages: Sequence[PageData], options: ExportOptions,
                            target: ExportFormat) -> list[CoreError]:
        """Avertismente care nu opresc exportul (apelantul decide):
        Q-051 pagini invalidate; XLSX fara tabele."""
        chosen = select_pages(pages, options)
        out: list[CoreError] = []
        stale = [p.page_number for p in chosen
                 if p.status not in (PageStatus.RECOGNIZED, PageStatus.VERIFIED)]
        if stale:
            out.append(PagesNotRecognizedError("exista pagini nerecunoscute sau invalidate",
                                               page_numbers=stale))
        if ExportFormat(target) in PDF_FORMATS:
            from app.core.export.pdf import export_warnings

            out += [CoreError(key) for key in export_warnings(dict(options.format_options))]
        if ExportFormat(target) is ExportFormat.XLSX and not any(
                a.area_type is AreaType.TABLE for p in chosen for a in p.areas):
            out.append(NoTextFoundError("documentul nu are tabele", format="xlsx"))
        return out

    def export(self, pages: Sequence[PageData], target: Path, fmt: ExportFormat,
               options: ExportOptions, *, progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        fmt = ExportFormat(fmt)
        options.validate(fmt)
        exporter = self._exporters.get(fmt)
        if exporter is None:
            raise ValueError(f"formatul {fmt.value} nu are inca exportator")
        exporter.validate(options)
        chosen = select_pages(pages, options)
        if not chosen:
            raise ValueError("nicio pagina de exportat")
        return exporter.export(chosen, Path(target), options, progress=progress, cancel=cancel)


def default_service() -> ExportService:
    """Serviciul cu toti exportatorii disponibili."""
    from app.core.export.csvfile import CsvExporter
    from app.core.export.docx import DocxExporter
    from app.core.export.epub import EpubExporter
    from app.core.export.fb2 import Fb2Exporter
    from app.core.export.html import HtmlExporter
    from app.core.export.odt import OdtExporter
    from app.core.export.pdf import PdfExporter
    from app.core.export.pdfa import PdfAExporter, PdfUaExporter
    from app.core.export.pptx import PptxExporter
    from app.core.export.rtf import RtfExporter
    from app.core.export.txt import TxtExporter
    from app.core.export.xlsx import XlsxExporter

    service = ExportService()
    for exporter in (TxtExporter(), PdfExporter(), PdfAExporter(), PdfUaExporter(),
                     DocxExporter(), RtfExporter(), OdtExporter(), XlsxExporter(),
                     CsvExporter(), PptxExporter(), HtmlExporter(), EpubExporter(),
                     Fb2Exporter()):
        service.register(exporter)
    return service


def options_from_settings(settings: Any, fmt: ExportFormat, **overrides: Any) -> ExportOptions:
    """Q-024: optiunile salvate ale formatului (`<format>.*`, SPEC_03 X.5)."""
    from app.core.settings import CATALOG

    fmt = ExportFormat(fmt)
    prefix = f"{fmt.value}."
    values = {d.key[len(prefix):]: settings.get(d.key) for d in CATALOG
              if d.key.startswith(prefix)}
    options = ExportOptions(format_options=values)
    if "layout" in values:
        options.layout_mode = LayoutMode(values["layout"])
    for key in ("keep_headers_footers", "keep_line_breaks", "keep_pictures"):
        if key in values:
            setattr(options, key, bool(values[key]))
    if "encoding" in values:
        options.encoding = str(values["encoding"])
    return replace(options, **overrides) if overrides else options


# Q-023, I-015: paginile alese
def select_pages(pages: Sequence[PageData], options: ExportOptions) -> list[PageData]:
    if options.page_range is None:
        return list(pages)
    wanted = set(options.page_range)
    return [p for p in pages if p.page_number in wanted]


# --- documentul de exportat -----------------------------------------------------------


@dataclass(slots=True)
class ExportBlock:
    area: AreaData
    block: BlockData
    cell: Any = None
    """Celula tabelului (TableCellData), sau None pentru textul obisnuit."""


def page_blocks(page: PageData, options: ExportOptions) -> Iterator[ExportBlock]:
    """Blocurile paginii in ordinea zonelor (M-022), cu celulele tabelelor
    rand cu rand. Antetele si subsolurile numai cu `keep_headers_footers`
    (X-103)."""
    for area in page._ordered_areas():
        for block in area.blocks:
            if not options.keep_headers_footers and block.block_type in ("header", "footer"):
                continue
            yield ExportBlock(area, block)
        if area.table is not None:
            for cell in sorted(area.table.cells, key=lambda c: (c.row, c.col)):
                for block in cell.blocks:
                    yield ExportBlock(area, block, cell)


def word_text(word: Any) -> str:
    """O-072: textul redactat devine puncte in formatele fara culori."""
    from app.core.text.editor import redacted_text

    return redacted_text(word)


def block_lines(block: BlockData) -> list[str]:
    return [" ".join(word_text(w) for w in line.words) for line in block.lines]


def block_text(block: BlockData, keep_line_breaks: bool) -> str:
    """X-104: randurile blocului unite intr-un paragraf, sau pastrate. La unire,
    cuvantul despartit la capat de rand se reface (R-035)."""
    lines = block_lines(block)
    if keep_line_breaks:
        return "\n".join(lines)
    out = ""
    for line in lines:
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out


def report(progress: ProgressCallback | None, done: int, total: int, stage: str) -> None:
    if progress is not None:
        progress(Progress(done, total, stage, str(done)))


def check_cancel(cancel: CancelToken | None, done: int, total: int) -> None:
    from app.core.errors import OperationCancelledError

    if cancel is not None and cancel():
        raise OperationCancelledError(done=done, total=total)
