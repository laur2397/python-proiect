"""Trimiterea si tiparirea, partea din nucleu (faza 6, pasul 6.8): Q-040..Q-050,
Q-060..Q-065.

Nucleul pregateste fisierele; fereastra (faza 6b) deschide clientul de e-mail,
aplicatia sau imprimanta. Nimic nu se trimite prin retea (CLAUDE.md §6.1):
mesajele de e-mail se scriu ca fisiere `.eml`, pe care utilizatorul le
deschide si le trimite din programul lui de e-mail.

Q-060..Q-065: originalul lucreaza cu Office si SharePoint instalate; noi citim
si scriem formatele cu biblioteci proprii, fara Office (Q-065, CLAUDE.md §6.3).
"""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Callable, Sequence
from email.message import EmailMessage
from pathlib import Path

from app.core.export.base import ExportOptions, default_service, export_page_images
from app.core.model import ExportFormat, LayoutMode, PageData

ALL, PER_PAGE, BLANK_PAGES = "all", "per_page", "blank_pages"
"""Q-043, Q-045: cum se impart paginile in atasamente."""
LOST_ON_SEND = ("attachments", "bookmarks", "comments", "annotations")
"""Q-041: ce nu se transfera la trimiterea in PDF Editor."""
_KINDLE = re.compile(r"^[^@\s]+@(free\.)?kindle\.com$", re.IGNORECASE)


# Q-043
def split_pages(pages: Sequence[PageData], mode: str,
                is_blank: Callable[[PageData], bool] | None = None) -> list[list[PageData]]:
    """Grupurile de pagini, cate un atasament pe grup. La `blank_pages`, o
    pagina goala desparte documentele si nu intra in niciunul."""
    if mode == ALL:
        return [list(pages)]
    if mode == PER_PAGE:
        return [[p] for p in pages]
    if mode != BLANK_PAGES:
        raise ValueError(f"impartire necunoscuta: {mode!r}")
    blank = is_blank or (lambda p: (p.blank_score or 0) >= 0.99)
    groups: list[list[PageData]] = [[]]
    for page in pages:
        if blank(page):
            if groups[-1]:
                groups.append([])
            continue
        groups[-1].append(page)
    return [g for g in groups if g]


def _export_groups(groups: Sequence[Sequence[PageData]], folder: Path, name: str,
                   fmt: ExportFormat, options: ExportOptions) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    service = default_service()
    written: list[Path] = []
    for i, group in enumerate(groups, start=1):
        stem = name if len(groups) == 1 else f"{name}_{i:03d}"
        written += service.export(group, folder / f"{stem}.{fmt.value}", fmt, options)
    return written


def write_eml(target: Path, attachments: Sequence[Path], *, to: str = "",
              subject: str = "") -> Path:
    """Mesajul cu atasamentele, ca fisier `.eml` (nu se trimite nimic)."""
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("")
    for path in attachments:
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        main, sub = kind.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
    target = Path(target)
    target.write_bytes(bytes(msg))
    return target


# Q-042, Q-043
def email_document(pages: Sequence[PageData], folder: Path, name: str, fmt: ExportFormat,
                   options: ExportOptions, *, split: str = ALL) -> Path:
    """`E-mail > Document...`: toate formatele, cu exceptia HTML."""
    fmt = ExportFormat(fmt)
    if fmt is ExportFormat.HTML:
        raise ValueError("HTML nu se trimite pe e-mail (Q-042)")
    files = _export_groups(split_pages(pages, split), Path(folder), name, fmt, options)
    return write_eml(Path(folder) / f"{name}.eml", files, subject=name)


# Q-044
def email_images(pages: Sequence[PageData], folder: Path, name: str, fmt: ExportFormat, *,
                 multipage: bool = False) -> Path:
    """`E-mail > Images...`, cu `Send as multi-page image file` (TIFF)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    suffix = {ExportFormat.TIFF: ".tif", ExportFormat.JPEG: ".jpg", ExportFormat.PNG: ".png"}
    files = export_page_images(pages, folder / f"{name}{suffix.get(ExportFormat(fmt), '')}",
                               fmt, multipage=multipage)
    return write_eml(folder / f"{name}.eml", files, subject=name)


# Q-045
def send_to_kindle(pages: Sequence[PageData], folder: Path, name: str, address: str, *,
                   split: str = ALL) -> Path:
    """Mesajul catre contul Kindle, cu EPUB-ul atasat; il trimite utilizatorul."""
    if not _KINDLE.match(address.strip()):
        raise ValueError("adresa Kindle trebuie sa fie de forma nume@kindle.com (Q-045)")
    options = ExportOptions(layout_mode=LayoutMode.FORMATTED)
    files = _export_groups(split_pages(pages, split), Path(folder), name, ExportFormat.EPUB,
                           options)
    return write_eml(Path(folder) / f"{name}.eml", files, to=address.strip(), subject=name)


# Q-040, Q-041
def send_to_pdf_editor(pages: Sequence[PageData], folder: Path, name: str) -> Path:
    """PDF-ul cautabil care se deschide in PDF Editor: fara semne de carte,
    comentarii si legaturi (Q-041)."""
    from app.core.export.pdf import PdfExporter

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    pdf = PdfExporter().build(pages, ExportOptions(layout_mode=LayoutMode.EXACT), links=False)
    target = folder / f"{name}.pdf"
    pdf.save(target)
    return target


# Q-046, Q-048
def send_to_application(pages: Sequence[PageData], folder: Path, name: str,
                        fmt: ExportFormat) -> Path:
    """Fisierul pentru Word (DOCX), Excel (XLSX), PowerPoint (PPTX) sau
    browser (HTML); fereastra il deschide cu programul implicit."""
    modes = {ExportFormat.DOCX: LayoutMode.EDITABLE, ExportFormat.XLSX: LayoutMode.FORMATTED,
             ExportFormat.PPTX: LayoutMode.EXACT, ExportFormat.HTML: LayoutMode.FORMATTED}
    fmt = ExportFormat(fmt)
    if fmt not in modes:
        raise ValueError(f"{fmt.value} nu are o aplicatie de trimitere (Q-046, Q-048)")
    (path, *_) = _export_groups([list(pages)], Path(folder), name, fmt,
                                ExportOptions(layout_mode=modes[fmt]))
    return path


# Q-047, Q-049
def text_pages(pages: Sequence[PageData]) -> list[str]:
    """Textul fiecarei pagini: pentru clipboard (Q-047) si `Print text` (Q-049)."""
    from app.core.export.txt import document_text

    options = ExportOptions(layout_mode=LayoutMode.PLAIN, keep_line_breaks=True)
    return [document_text([p], options) for p in pages]


# Q-050
def image_pages(pages: Sequence[PageData]) -> list[Path]:
    """`Print image`: imaginile paginilor, in ordine."""
    return [p.image_path for p in pages]
