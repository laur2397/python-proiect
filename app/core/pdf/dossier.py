"""Dosarul care pastreaza semnaturile valide (faza 8, pasul 8.5): E-500…E-512.

O semnatura electronica acopera octetii exacti ai fisierului semnat; orice
unire care muta paginile o invalideaza (SPEC_11, contextul). De aceea dosarul:

- incorporeaza fiecare fisier sursa ca atasament, **octet cu octet** (E-501), si
  verifica amprenta SHA-256 a fiecarui atasament dupa salvare; o diferenta
  anuleaza operatia si nu se scrie nimic;
- incepe cu o pagina de cuprins si raport de semnaturi (E-502), cu linkuri catre
  copia de citire si catre atasament;
- continua cu copiile de citire ale paginilor (E-503), etichetate pe fiecare
  pagina, fara campurile de semnatura; varianta portofoliu le omite (E-505);
- are cate un semn de carte de nivel 1 pe document (E-504);
- poarta in `Root` un dictionar `/DocuLensDossier` cu numele, amprenta si
  numarul de pagini ale fiecarui original, dupa care se recunoaste (E-512) si se
  verifica la extragere (E-511) si dupa sigilare (E-506).

Verificarea semnaturilor e strict offline (E-507). Textele vizibile din dosar
(cuprinsul, eticheta) vin de la apelant, prin `texts(cheie, **parametri)`, din
fisierele de traducere: nucleul nu contine text afisabil (CLAUDE.md §6.5).
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import quoteattr

import pikepdf

from app.core.errors import CoreError, PasswordRequiredError, WrongPasswordError
from app.core.model import PasswordCallback, Progress, ProgressCallback
from app.core.pdf.signatures import (
    STATUS_EXPIRED,
    STATUS_INVALID,
    STATUS_MODIFIED,
    STATUS_UNVERIFIABLE,
    STATUS_VALID,
    SignatureInfo,
    validate_bytes,
)

if TYPE_CHECKING:
    from app.core.context import AppContext

Texts = Callable[..., str]
"""`texts(cheie, **parametri)`: textul tradus (cheile `dossier.*`)."""

MARK = "/DocuLensDossier"
"""E-512: dictionarul din `Root` dupa care se recunoaste un dosar."""
STATUS_NONE = "none"
"""E-502: documentul nu are semnaturi."""
STATUSES = (STATUS_VALID, STATUS_EXPIRED, STATUS_INVALID, STATUS_MODIFIED, STATUS_UNVERIFIABLE,
            STATUS_NONE)
SEAL_FIELD = "SigiliuDosar"
"""E-506: campul semnaturii care sigileaza dosarul."""
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif",
                            ".jp2", ".webp"})
"""Fisierele care au copie de citire pe langa PDF-uri; restul sunt doar atasate."""
ASICE_MIMETYPE = "application/vnd.etsi.asic-e+zip"

_PAGE = (595.28, 841.89)
_MARGIN = 56.0
_TITLE_SIZE = 16.0
_TEXT_SIZE = 9.5
_LABEL_SIZE = 7.0
_LINE = 1.35


class DossierIntegrityError(CoreError):
    """E-501, E-511: un atasament nu mai are amprenta originalului."""

    code = "DOSSIER_INTEGRITY"


class CertificateInvalidError(CoreError):
    """E-506: certificatul de sigilare e expirat sau inca nevalid."""

    code = "CERTIFICATE_INVALID"


@dataclass
class DossierEntry:
    """Un document din dosar."""

    source: Path
    name: str
    """Numele atasamentului (unic in dosar)."""
    sha256: str
    pages: int | None
    """Paginile documentului; None = nu are copie de citire (alt tip de fisier)."""
    signatures: list[SignatureInfo] = field(default_factory=list)
    first_page: int | None = None
    """Prima pagina a copiei de citire in dosar (de la 1)."""

    @property
    def status(self) -> str:
        """Starea cea mai slaba dintre semnaturi (E-502)."""
        if not self.signatures:
            return STATUS_NONE
        # E-502: certificatul expirat dupa semnare (cazul obisnuit la dosarele
        # vechi) e o stare proprie, intre `nu se poate verifica` si `valida`.
        # O stare necunoscuta nu opreste raportul: se trateaza ca neverificabila.
        order = (STATUS_INVALID, STATUS_MODIFIED, STATUS_UNVERIFIABLE, STATUS_EXPIRED,
                 STATUS_VALID)
        return next((s for s in order if any(sig.status == s for sig in self.signatures)),
                    STATUS_UNVERIFIABLE)


@dataclass
class DossierResult:
    path: Path
    entries: list[DossierEntry]
    skipped: list[tuple[Path, CoreError]] = field(default_factory=list)
    """J-050: fisierele ilizibile sau cu parola refuzata, sarite."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- E-509: semnaturile care s-ar pierde la unirea clasica --------------------------------


def file_signatures(path: Path, password: str | None = None) -> list[SignatureInfo]:
    """Semnaturile unui fisier (numai PDF), validate offline."""
    path = Path(path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return []
    return validate_bytes(path.read_bytes(), password)


def signed_among(paths: Sequence[Path]) -> dict[Path, list[SignatureInfo]]:
    """E-509: fisierele din lista care contin semnaturi, cu semnaturile lor."""
    found: dict[Path, list[SignatureInfo]] = {}
    for path in paths:
        sigs = file_signatures(Path(path))
        if sigs:
            found[Path(path)] = sigs
    return found


# --- E-500…E-505: construirea dosarului ---------------------------------------------------


def build_dossier(files: Sequence[Path], target: Path, *, texts: Texts,
                  reading_copies: bool = True, password: PasswordCallback | None = None,
                  context: AppContext | None = None,
                  progress: ProgressCallback | None = None) -> DossierResult:
    """E-500: un singur PDF-dosar din `files` (minimum 2, in ordinea data).
    `reading_copies=False` = portofoliu: cuprins si atasamente (E-505). Un fisier
    ilizibil sau cu parola refuzata se raporteaza in `skipped` si se sare (J-050).
    Dupa salvare, fiecare atasament se compara cu sursa (E-501): o diferenta
    ridica `DossierIntegrityError` si fisierul nu se scrie."""
    if len(files) < 2:
        raise ValueError("dosarul cere cel putin doua fisiere (E-500)")
    entries: list[DossierEntry] = []
    sources: dict[str, bytes] = {}
    copies: dict[str, pikepdf.Pdf] = {}
    skipped: list[tuple[Path, CoreError]] = []
    used: set[str] = set()
    try:
        for i, raw in enumerate(files):
            path = Path(raw)
            if progress is not None:
                progress(Progress(i, len(files), "stage.dossier", path.name))
            try:
                data = path.read_bytes()
            except OSError as exc:
                skipped.append((path, CoreError(str(exc), path=str(path))))
                continue
            try:
                copy, used_password = _reading_pdf(path, data, password, context)
            except CoreError as exc:
                skipped.append((path, exc))
                continue
            name = _unique(path.name, used)
            entry = DossierEntry(path, name, sha256(data), None)
            if copy is not None:
                entry.pages = len(copy.pages)
                copies[name] = copy
                if data[:5] == b"%PDF-":
                    entry.signatures = validate_bytes(data, used_password)
            entries.append(entry)
            sources[name] = data
        if len(entries) < 2:
            raise ValueError("au ramas mai putin de doua fisiere care se pot citi (E-500)")
        data = _assemble(entries, sources, copies, texts=texts, reading_copies=reading_copies)
    finally:
        for copy in copies.values():
            copy.close()
    check_attachments(data, {e.name: e.sha256 for e in entries})  # E-501
    _write_atomic(Path(target), data)
    if progress is not None:
        progress(Progress(len(files), len(files), "stage.dossier"))
    return DossierResult(Path(target), entries, skipped)


def _unique(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate = f"{stem} ({n}){dot}{ext}"
        n += 1
    used.add(candidate.lower())
    return candidate


def _reading_pdf(path: Path, data: bytes, password: PasswordCallback | None,
                 context: AppContext | None) -> tuple[pikepdf.Pdf | None, str | None]:
    """Paginile pentru copia de citire si parola folosita: PDF-ul insusi, o
    imagine convertita, sau None pentru alte fisiere (raman doar atasate)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf" or data[:5] == b"%PDF-":
        return _open_pdf(path, data, password)
    if suffix in IMAGE_SUFFIXES:
        from app.core.pdf.organize import files_to_pdf

        return pikepdf.open(io.BytesIO(files_to_pdf([path], context=context))), None
    return None, None


def _open_pdf(path: Path, data: bytes, password: PasswordCallback | None
              ) -> tuple[pikepdf.Pdf, str | None]:
    from app.core.errors import FileCorruptError

    attempt, tried = "", False
    while True:
        try:
            return pikepdf.open(io.BytesIO(data), password=attempt), attempt or None
        except pikepdf.PasswordError:
            pass
        except pikepdf.PdfError as exc:
            raise FileCorruptError(str(exc), path=str(path)) from exc
        answer = password(str(path)) if password is not None else None
        if answer is None:
            if tried:
                raise WrongPasswordError("parola nu e corecta", path=str(path))
            raise PasswordRequiredError("PDF-ul cere parola", path=str(path))
        attempt, tried = answer, True


def _assemble(entries: list[DossierEntry], sources: dict[str, bytes],
              copies: dict[str, pikepdf.Pdf], *, texts: Texts, reading_copies: bool) -> bytes:
    from app.core.pdf.embedded_font import embed_text_font, wrap

    out = pikepdf.new()
    label = texts("dossier.label")
    blocks = [_entry_lines(i, e, texts) for i, e in enumerate(entries, start=1)]
    every = [texts("dossier.title"), texts("dossier.intro"), label,
             texts("dossier.open_copy"), texts("dossier.open_original"),
             *(line for block in blocks for line in block)]
    font = embed_text_font(out, every)
    width = _PAGE[0] - 2 * _MARGIN
    wrapped = [[part for line in block for part in wrap(font, line, _TEXT_SIZE, width)]
               for block in blocks]
    layout = _toc_layout(wrapped)
    for _ in layout:
        out.add_blank_page(page_size=_PAGE)
    if reading_copies:  # E-503: copiile de citire, in ordinea listei
        for entry in entries:
            copy = copies.get(entry.name)
            if copy is None:
                continue
            entry.first_page = len(out.pages) + 1
            for page in copy.pages:
                out.pages.append(page)
                spots = _strip_signature_fields(out, out.pages[-1])
                _label_page(out, out.pages[-1], font, label)
                for rect in spots:  # E-513: click pe semnatura deschide originalul
                    _add_annot(out.pages[-1], _signature_link(out, rect, entry.name,
                                                              texts("dossier.signature_link")))
    for entry in entries:  # E-501: originalele, octet cu octet
        mime = mimetypes.guess_type(entry.name)[0] or "application/octet-stream"
        out.attachments[entry.name] = pikepdf.AttachedFileSpec(
            out, sources[entry.name], filename=entry.name, mime_type=mime,
            description=f"SHA-256 {entry.sha256}")
    for index, rows in enumerate(layout):  # E-502: cuprinsul, cu linkurile
        _draw_toc_page(out, out.pages[index], font, texts, rows, entries, wrapped,
                       first=index == 0)
    with out.open_outline() as outline:  # E-504
        outline.root[:] = [pikepdf.OutlineItem(e.name, e.first_page - 1)
                           for e in entries if e.first_page is not None]
    out.Root[MARK] = pikepdf.Dictionary(
        Version=1, Created=pikepdf.String(datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        Files=pikepdf.Array([pikepdf.Dictionary(
            Name=pikepdf.String(e.name), SHA256=pikepdf.String(e.sha256),
            Pages=e.pages if e.pages is not None else 0) for e in entries]))
    if not reading_copies:  # E-519: Adobe il deschide ca portofoliu, cu originalele
        first = entries[0].name if entries else ""
        out.Root.Collection = pikepdf.Dictionary(
            Type=pikepdf.Name.Collection, View=pikepdf.Name.D,
            D=pikepdf.String(first))
        out.Root.PageMode = pikepdf.Name.UseAttachments
    out.docinfo["/Title"] = pikepdf.String(texts("dossier.title"))
    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def local_time(stamp: str | None) -> str:
    """E-502: data semnarii, din UTC (`2024-08-09T14:41:57Z`) in ora locala, de
    forma `09.08.2024 17:41` (auditul 23.11.2026, defectul 5)."""
    if not stamp:
        return "?"
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone().strftime("%d.%m.%Y %H:%M")


def _entry_lines(index: int, entry: DossierEntry, texts: Texts) -> list[str]:
    """E-502: numarul, numele, paginile, semnatarii si starea, amprenta."""
    pages = texts("dossier.pages", count=entry.pages) if entry.pages is not None \
        else texts("dossier.no_pages")
    lines = [f"{index}. {entry.name} — {pages}"]
    if not entry.signatures:
        lines.append(texts("dossier.status.none"))
    for sig in entry.signatures:
        lines.append(texts("dossier.signature", signer=sig.signer or "?",
                           issuer=sig.issuer or "?", date=local_time(sig.signed_at),
                           status=texts(f"dossier.status.{sig.status}")))
        if sig.status == STATUS_VALID and sig.trusted is None:
            lines.append(texts("dossier.trust_offline"))  # E-507
    lines.append(texts("dossier.sha", sha=entry.sha256))
    return lines


def _toc_layout(wrapped: list[list[str]]) -> list[list[int]]:
    """Ce blocuri (indici) intra pe fiecare pagina de cuprins."""
    step = _TEXT_SIZE * _LINE
    room = _PAGE[1] - 2 * _MARGIN
    left = room - _TITLE_SIZE - step * 4
    pages: list[list[int]] = [[]]
    for i, block in enumerate(wrapped):
        need = (len(block) + 2) * step  # + randul cu linkuri + spatiul
        if pages[-1] and need > left:
            pages.append([])
            left = room
        pages[-1].append(i)
        left -= need
    return pages


def _draw_toc_page(pdf: pikepdf.Pdf, page: pikepdf.Page, font: Any, texts: Texts,
                   rows: list[int], entries: list[DossierEntry], wrapped: list[list[str]],
                   *, first: bool) -> None:
    step = _TEXT_SIZE * _LINE
    y = _PAGE[1] - _MARGIN
    ops = ["BT 0 0 0 rg"]
    if first:
        y -= _TITLE_SIZE
        ops.append(_text(font, texts("dossier.title"), _TITLE_SIZE, _MARGIN, y))
        y -= step * 2
        ops.append(_text(font, texts("dossier.intro"), _TEXT_SIZE, _MARGIN, y))
        y -= step * 2
    annots = []
    for i in rows:
        entry = entries[i]
        for line in wrapped[i]:
            y -= step
            ops.append(_text(font, line, _TEXT_SIZE, _MARGIN, y))
        y -= step
        x = _MARGIN
        if entry.first_page is not None:
            caption = texts("dossier.open_copy")
            ops.append("0.1 0.3 0.8 rg " + _text(font, caption, _TEXT_SIZE, x, y))
            w = font.width(caption, _TEXT_SIZE)
            annots.append(_link(pdf, [x, y - 2, x + w, y + _TEXT_SIZE], pikepdf.Dictionary(
                S=pikepdf.Name.GoTo, D=pikepdf.Array([pdf.pages[entry.first_page - 1].obj,
                                                      pikepdf.Name.Fit]))))
            x += w + 18
        caption = texts("dossier.open_original")
        ops.append("0.1 0.3 0.8 rg " + _text(font, caption, _TEXT_SIZE, x, y))
        annots.append(_link(pdf, [x, y - 2, x + font.width(caption, _TEXT_SIZE),
                                  y + _TEXT_SIZE], pikepdf.Dictionary(
            S=pikepdf.Name.GoToE, NewWindow=True,
            T=pikepdf.Dictionary(R=pikepdf.Name.C, N=pikepdf.String(entry.name)))))
        ops.append("0 0 0 rg")
        y -= step
    ops.append("ET")
    page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font))
    page.obj.Contents = pdf.make_stream(" ".join(ops).encode("latin-1"))
    if annots:
        page.obj.Annots = pdf.make_indirect(pikepdf.Array(annots))


def _text(font: Any, text: str, size: float, x: float, y: float) -> str:
    return f"/F1 {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm {font.encode(text)} Tj"


def _link(pdf: pikepdf.Pdf, rect: list[float], action: pikepdf.Dictionary) -> Any:
    return pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=rect,
        Border=[0, 0, 0], A=action))


def _is_signature_widget(annot: Any) -> bool:
    if annot.get("/Subtype") != "/Widget":
        return False
    node = annot
    for _ in range(32):
        if node is None:
            return False
        if node.get("/FT") == "/Sig":
            return True
        node = node.get("/Parent")
    return False


def _strip_signature_fields(pdf: pikepdf.Pdf, page: pikepdf.Page) -> list[list[float]]:
    """E-503: campurile de semnatura si adnotarile lor nu intra in copie, ca sa
    nu para semnaturi valide.
    E-513: aspectul vizibil al semnaturii (imaginea, numele) se pastreaza ca
    simplu desen in continutul paginii, fara camp de semnatura. Intoarce
    dreptunghiurile semnaturilor vizibile, pentru linkurile catre original."""
    annots = page.obj.get("/Annots")
    if annots is None:
        return []
    spots: list[list[float]] = []
    kept = []
    for annot in annots:
        if not _is_signature_widget(annot):
            kept.append(annot)
            continue
        rect = _visible_rect(annot)
        if rect is not None and _draw_appearance(pdf, page, annot, rect):
            spots.append(rect)
    if len(kept) != len(annots):
        page.obj.Annots = pikepdf.Array(kept)
    return spots


def _visible_rect(annot: Any) -> list[float] | None:
    """Dreptunghiul unei semnaturi vizibile; None pentru semnaturile invizibile
    (dreptunghi gol) sau ascunse (flagurile Hidden / NoView)."""
    try:
        x0, y0, x1, y1 = (float(v) for v in annot.Rect)
    except (AttributeError, TypeError, ValueError):
        return None
    if abs(x1 - x0) < 1 or abs(y1 - y0) < 1:
        return None
    if int(annot.get("/F", 0)) & (2 | 32):
        return None
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _draw_appearance(pdf: pikepdf.Pdf, page: pikepdf.Page, annot: Any,
                     rect: list[float]) -> bool:
    """E-513: deseneaza aspectul normal (/AP /N) al semnaturii in continutul
    paginii, scalat la dreptunghiul ei. Fara aspect, nu se deseneaza nimic."""
    ap = annot.get("/AP")
    normal = ap.get("/N") if ap is not None else None
    if not isinstance(normal, pikepdf.Stream):
        return False
    try:
        bx0, by0, bx1, by1 = (float(v) for v in normal.BBox)
    except (AttributeError, TypeError, ValueError):
        return False
    if abs(bx1 - bx0) < 1e-6 or abs(by1 - by0) < 1e-6:
        return False
    sx = (rect[2] - rect[0]) / (bx1 - bx0)
    sy = (rect[3] - rect[1]) / (by1 - by0)
    name = page.add_resource(normal, pikepdf.Name.XObject, prefix="DLSig")
    tx, ty = rect[0] - bx0 * sx, rect[1] - by0 * sy
    page.contents_add(pdf.make_stream(
        f"q {sx:.6f} 0 0 {sy:.6f} {tx:.4f} {ty:.4f} cm {name} Do Q".encode("latin-1")))
    return True


def _signature_link(pdf: pikepdf.Pdf, rect: list[float], name: str, tooltip: str) -> Any:
    """E-513: linkul de pe semnatura copiei: deschide originalul atasat intr-o
    fereastra noua, unde semnatura se verifica. Chenar albastru subtire, ca
    linkul sa se vada; textul apare la trecerea mouse-ului (/Contents)."""
    return pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=rect,
        Border=[0, 0, 1], C=[0.1, 0.3, 0.8], Contents=pikepdf.String(tooltip),
        A=pikepdf.Dictionary(S=pikepdf.Name.GoToE, NewWindow=True,
                             T=pikepdf.Dictionary(R=pikepdf.Name.C,
                                                  N=pikepdf.String(name)))))


def _add_annot(page: pikepdf.Page, annot: Any) -> None:
    annots = page.obj.get("/Annots")
    if annots is None:
        page.obj.Annots = pikepdf.Array([annot])
    else:
        annots.append(annot)


def _label_page(pdf: pikepdf.Pdf, page: pikepdf.Page, font: Any, label: str) -> None:
    """E-503: eticheta de copie de citire, sus pe pagina, peste continut."""
    from app.core.pdf.embedded_font import wrap

    x0, y0, x1, y1 = (float(v) for v in page.cropbox)
    left, top = min(x0, x1), max(y0, y1)
    width = abs(x1 - x0) - 24
    lines = wrap(font, label, _LABEL_SIZE, width)
    height = len(lines) * _LABEL_SIZE * _LINE + 6
    name = page.add_resource(font.font, pikepdf.Name.Font, prefix="DLLabel")
    ops = [(f"q 1 1 0.85 rg {left + 8:.2f} {top - 8 - height:.2f} {width + 8:.2f} "
            f"{height:.2f} re f 0.7 0 0 rg BT")]
    y = top - 8 - _LABEL_SIZE * 1.1
    for line in lines:
        ops.append(f"{name} {_LABEL_SIZE:.2f} Tf 1 0 0 1 {left + 12:.2f} {y:.2f} Tm "
                   f"{font.encode(line)} Tj")
        y -= _LABEL_SIZE * _LINE
    ops.append("ET Q")
    page.contents_add(pdf.make_stream(b"q"), prepend=True)
    page.contents_add(pdf.make_stream(("Q " + " ".join(ops)).encode("latin-1")))


def _write_atomic(target: Path, data: bytes) -> None:
    from app.core.errors import NoWritePermissionError

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".doculens-", suffix=target.suffix,
                                   dir=target.parent)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except OSError as exc:
        raise NoWritePermissionError(str(exc), path=str(target)) from exc


# --- E-501, E-511, E-512: verificarea si extragerea ---------------------------------------


def manifest(data: bytes) -> list[dict[str, Any]] | None:
    """E-512: originalele declarate de dosar (nume, amprenta, pagini); None =
    nu e un dosar DocuLens."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        mark = pdf.Root.get(MARK)
        if mark is None:
            return None
        return [{"name": str(item.Name), "sha256": str(item.SHA256),
                 "pages": int(item.get("/Pages", 0)) or None}
                for item in mark.get("/Files", [])]


def check_attachments(data: bytes, expected: dict[str, str]) -> None:
    """E-501: fiecare atasament are amprenta asteptata, altfel
    `DossierIntegrityError` (cu numele atasamentului)."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        found = {name: sha256(spec.get_file().read_bytes())
                 for name, spec in pdf.attachments.items()}
    for name, digest in expected.items():
        if found.get(name) != digest:
            raise DossierIntegrityError("atasamentul nu e identic cu originalul", name=name)


def verify_dossier(path: Path) -> dict[str, bool]:
    """E-501, E-506, E-512: pentru fiecare original din dosar, daca atasamentul
    are inca amprenta lui."""
    return {name: ok for name, ok, _sigs in dossier_report(path, signatures=False)}


def dossier_report(path: Path, *, signatures: bool = True
                   ) -> list[tuple[str, bool, list[SignatureInfo]]]:
    """E-512: pentru bara de informare, fiecare original: amprenta corecta si
    semnaturile lui, validate offline. Un fisier care nu e dosar → lista goala."""
    data = Path(path).read_bytes()
    files = manifest(data) or []
    out = []
    with pikepdf.open(io.BytesIO(data)) as pdf:
        for item in files:
            spec = pdf.attachments.get(item["name"])
            original = spec.get_file().read_bytes() if spec is not None else b""
            ok = spec is not None and sha256(original) == item["sha256"]
            sigs = validate_bytes(original) if signatures and ok and \
                original[:5] == b"%PDF-" else []
            out.append((item["name"], ok, sigs))
    return out


def extract_original(path: Path, name: str, target: Path) -> Path:
    """E-511: scrie originalul exact; amprenta se verifica inainte si dupa
    scriere, iar o diferenta da `DossierIntegrityError` (fisierul nu ramane)."""
    data = Path(path).read_bytes()
    files = {f["name"]: f["sha256"] for f in manifest(data) or []}
    with pikepdf.open(io.BytesIO(data)) as pdf:
        spec = pdf.attachments.get(name)
        if spec is None:
            raise KeyError(name)
        original = spec.get_file().read_bytes()
    expected = files.get(name)
    if expected is not None and sha256(original) != expected:
        raise DossierIntegrityError("atasamentul nu e identic cu originalul", name=name)
    target = Path(target)
    if target.is_dir():
        target = target / name
    _write_atomic(target, original)
    if expected is not None and sha256(target.read_bytes()) != expected:
        target.unlink(missing_ok=True)
        raise DossierIntegrityError("originalul scris difera", name=name)
    return target


# --- E-506: sigiliul dosarului ------------------------------------------------------------


def seal_dossier(path: Path, pkcs12: Path, passphrase: bytes | None, *,
                 target: Path | None = None, now: datetime | None = None) -> Path:
    """E-506: semnatura pe dosarul complet, cu certificatul utilizatorului
    (PKCS#12). Certificat expirat sau inca nevalid → `CertificateInvalidError`,
    iar dosarul ramane nesemnat. Dupa semnare se verifica din nou fiecare
    atasament (E-501)."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    source = Path(path)
    data = source.read_bytes()
    files = manifest(data)
    if files is None:
        raise ValueError("fisierul nu e un dosar (E-500)")
    try:
        signer = signers.SimpleSigner.load_pkcs12(str(pkcs12), passphrase=passphrase)
    except (OSError, ValueError) as exc:
        raise CertificateInvalidError(str(exc), path=str(pkcs12)) from exc
    if signer is None:
        raise CertificateInvalidError("certificatul nu se poate citi", path=str(pkcs12))
    validity = signer.signing_cert["tbs_certificate"]["validity"]
    start, end = validity["not_before"].native, validity["not_after"].native
    moment = now or datetime.now(UTC)
    if not start <= moment <= end:
        raise CertificateInvalidError("certificatul nu e valid acum",
                                      not_before=start.isoformat(), not_after=end.isoformat())
    writer = IncrementalPdfFileWriter(io.BytesIO(data))
    signed = signers.sign_pdf(writer, signers.PdfSignatureMetadata(field_name=SEAL_FIELD),
                              signer=signer).getvalue()
    check_attachments(signed, {f["name"]: f["sha256"] for f in files})
    destination = Path(target) if target is not None else source
    _write_atomic(destination, signed)
    return destination


# --- E-510: ASiC-E --------------------------------------------------------------------------


def export_asice(files: Sequence[Path], target: Path) -> Path:
    """E-510: container ASiC-E (ETSI EN 319 162): `mimetype` primul, necomprimat,
    originalele neschimbate si `META-INF/manifest.xml`."""
    if len(files) < 2:
        raise ValueError("containerul cere cel putin doua fisiere (E-500)")
    used: set[str] = set()
    entries = [(_unique(Path(p).name, used), Path(p).read_bytes()) for p in files]
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             ('<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:'
              'manifest:1.0" manifest:version="1.2">'),
             (f'<manifest:file-entry manifest:full-path="/" manifest:media-type='
              f'"{ASICE_MIMETYPE}"/>')]
    for name, _data in entries:
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        lines.append(f"<manifest:file-entry manifest:full-path={quoteattr(name)} "
                     f"manifest:media-type={quoteattr(mime)}/>")
    lines.append("</manifest:manifest>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), ASICE_MIMETYPE,
                         compress_type=zipfile.ZIP_STORED)
        for name, data in entries:
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("META-INF/manifest.xml", "\n".join(lines).encode("utf-8"),
                         compress_type=zipfile.ZIP_DEFLATED)
    data = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as check:  # E-501: originalele neschimbate
        for name, original in entries:
            if sha256(check.read(name)) != sha256(original):
                raise DossierIntegrityError("fisierul din container difera", name=name)
    _write_atomic(Path(target), data)
    return Path(target)
