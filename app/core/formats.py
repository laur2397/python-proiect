"""Formatele suportate (faza 16, pasul 16.1): SPEC_09 tabelul B.1, Y-100…Y-112.

Fiecare format are capabilitati distincte (Y-100): intrarea in OCR Editor, intrarea
in PDF Editor, intrarea in Compare, salvarea. Un format nu se ofera intr-un modul
care nu il accepta (Y-101). Coloana `readable` spune daca DocuLens il citeste deja;
formatele din original pe care nu le citim (`.doc`, `.xls`, `.ppt`, Visio, XPS,
DjVu, JBIG2 la intrare) dau un mesaj clar ca nu sunt suportate (Y-106,
faza_16_pasi.md decizia 1), nu o eroare generica.

Tabelul e singura sursa pentru filtrele dialogurilor de deschidere, pentru
`/listformats` (Y-112) si pentru deschiderea in PDF Editor a fisierelor care nu
sunt PDF (convertite in PDF nesalvat).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODULES = ("ocr_editor", "pdf_editor", "compare")


@dataclass(frozen=True, slots=True)
class FileFormat:
    key: str
    """Cheia textului (`format.name.<key>`)."""
    extensions: tuple[str, ...]
    ocr_editor: bool
    pdf_editor: bool
    compare: bool
    output: bool
    readable: bool = True
    """DocuLens il citeste la intrare (decizia 1)."""
    group: str = "image"
    """`pdf`, `editable`, `noneditable`, `image` (randurile tabelului B.1)."""


# SPEC_09 B.1, in ordinea din tabel
FORMATS: tuple[FileFormat, ...] = (
    FileFormat("pdf", (".pdf",), True, True, True, True, group="pdf"),
    FileFormat("word", (".doc", ".docx"), False, True, True, True, group="editable"),
    FileFormat("excel", (".xls", ".xlsx"), False, True, True, True, group="editable"),
    FileFormat("powerpoint", (".pptx",), False, True, True, True, group="editable"),
    FileFormat("powerpoint_old", (".ppt",), False, True, True, False, readable=False,
               group="editable"),
    FileFormat("visio", (".vsd", ".vsdx"), False, True, False, False, readable=False,
               group="editable"),
    FileFormat("html", (".htm", ".html"), False, True, True, True, group="editable"),
    FileFormat("rtf", (".rtf",), False, True, True, True, group="editable"),
    FileFormat("txt", (".txt",), False, True, True, True, group="editable"),
    FileFormat("csv", (".csv",), False, False, False, True, group="editable"),
    FileFormat("odt", (".odt",), False, True, True, True, group="editable"),
    FileFormat("ods", (".ods",), False, True, True, False, group="editable"),
    FileFormat("odp", (".odp",), False, True, True, False, group="editable"),
    FileFormat("fb2", (".fb2",), False, False, False, True, group="editable"),
    FileFormat("epub", (".epub",), False, False, False, True, group="editable"),
    FileFormat("xps", (".xps",), True, True, True, False, readable=False, group="noneditable"),
    FileFormat("djvu", (".djvu", ".djv"), True, True, True, True, readable=False,
               group="noneditable"),
    FileFormat("jpeg", (".jpg", ".jpeg"), True, True, True, True),
    FileFormat("jpeg2000", (".jp2", ".j2k", ".jpf", ".jpx", ".jpc"), True, True, True, True),
    FileFormat("png", (".png",), True, True, True, True),
    FileFormat("tiff", (".tiff", ".tif"), True, True, True, True),
    FileFormat("bmp", (".bmp", ".dib", ".rle"), True, True, True, True),
    FileFormat("gif", (".gif",), True, True, True, False),
    FileFormat("jbig2", (".jbig2", ".jb2"), True, True, True, True, readable=False),
    FileFormat("pcx", (".dcx", ".pcx"), True, True, True, True),
    FileFormat("svg", (".svg",), False, True, False, False),
)

UNREAD_OLD_OFFICE = (".doc", ".xls")
"""Word si Excel 97-2003: in B.1 la intrare, dar formatul binar vechi nu il citim
(decizia 1); `.docx` si `.xlsx` din acelasi rand se citesc."""


def by_extension(path: str | Path) -> FileFormat | None:
    ext = Path(path).suffix.lower()
    return next((f for f in FORMATS if ext in f.extensions), None)


def readable(path: str | Path) -> bool:
    fmt = by_extension(path)
    if fmt is None or not fmt.readable:
        return False
    return Path(path).suffix.lower() not in UNREAD_OLD_OFFICE


def accepted(path: str | Path, module: str) -> bool:
    """Y-101: formatul e acceptat la intrare in modul (dupa B.1)."""
    if module not in MODULES:
        raise ValueError(f"modul necunoscut: {module}")
    fmt = by_extension(path)
    return fmt is not None and bool(getattr(fmt, module))


def status(path: str | Path, module: str) -> str:
    """`ok`, `not_in_module` (alt modul il accepta, Y-101), `not_supported`
    (formatul e in B.1 dar DocuLens nu il citeste, Y-106) sau `unknown`."""
    fmt = by_extension(path)
    if fmt is None:
        return "unknown"
    if not accepted(path, module):
        return "not_in_module"
    return "ok" if readable(path) else "not_supported"


def extensions_for(module: str) -> list[str]:
    """Extensiile pe care modulul le deschide efectiv (B.1 si citite de DocuLens);
    din ele se fac filtrele dialogurilor de deschidere."""
    out: list[str] = []
    for fmt in FORMATS:
        if getattr(fmt, module) and fmt.readable:
            out += [e for e in fmt.extensions if e not in UNREAD_OLD_OFFICE]
    return out


def output_formats() -> list[FileFormat]:
    """Y-102: formatele de salvare (CSV, FB2, EPUB numai aici)."""
    return [f for f in FORMATS if f.output]


def input_only() -> list[FileFormat]:
    """Y-103: formatele care se deschid, dar nu se salveaza."""
    return [f for f in FORMATS if not f.output and (f.ocr_editor or f.pdf_editor)]


def pattern(extensions: Sequence[str]) -> str:
    """`*.pdf *.png …` pentru un filtru de dialog."""
    return " ".join(f"*{e}" for e in extensions)


# --- PDF Editor: orice intrare acceptata devine un PDF nesalvat (B.1) ------------------

def open_in_pdf_editor(path: Path, *, password: Any = None, context: Any = None,
                       engine: Any = None) -> Any:
    """Documentul PDF Editor-ului pentru `path`: PDF-ul insusi; imaginile si
    formatele editabile convertite intr-un PDF nesalvat (ca la `File > New`).
    SVG-ul (Y-104) il converteste interfata (QtSvg), deci aici se refuza.
    Erori: `UnsupportedFormatError` (formatul nu e al PDF Editor-ului sau nu e
    citit inca, Y-106)."""
    from app.core.errors import UnsupportedFormatError
    from app.core.pdf.document import PdfDocument

    path = Path(path)
    state = status(path, "pdf_editor")
    if state != "ok":
        raise UnsupportedFormatError("formatul nu se deschide in PDF Editor",
                                     path=str(path), reason=state)
    fmt = by_extension(path)
    assert fmt is not None
    if fmt.key == "pdf":
        return PdfDocument.open(path, password=password)
    if fmt.key == "svg":
        raise UnsupportedFormatError("SVG se converteste in interfata", path=str(path),
                                     reason="svg")
    if fmt.group == "editable":
        from app.core.compare.sources import blocks_to_pdf, editable_blocks

        document = PdfDocument._from_bytes(blocks_to_pdf(editable_blocks(path)), None)
        document.is_modified = True
        document._revision = 1
        return document
    from app.core.export.base import ExportOptions

    return PdfDocument.from_images([path], options=ExportOptions(searchable=False),
                                   context=context, engine=engine)
