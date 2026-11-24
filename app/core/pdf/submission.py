"""Pachetul de depunere (SPEC_11, E-514…E-518): documentele semnate raman valide.

O semnatura electronica acopera octetii exacti ai fisierului; o unire de pagini o
invalideaza in orice program (SPEC_11 E.5, contextul). Cercetarea din 24.11.2026
(Adobe, EU DSS, pyHanko; docs/plan/semnaturi_2026-11-24.md) a aratat ca singura
schimbare acceptata de toti validatorii dupa o semnatura de aprobare este **o noua
semnatura**, adaugata ca actualizare incrementala. Ghidurile MySMIS2021+ cer, la
randul lor, cate un PDF pe anexa, semnat de reprezentantul legal.

De aceea pachetul:

- copiaza fiecare document **octet cu octet** (E-514), numerotat in ordinea data;
- il contrasemneaza, la cerere, cu certificatul reprezentantului legal, ca
  actualizare incrementala: semnaturile de dinainte raman neatinse (E-515);
- **verifica dupa semnare** fiecare semnatura de dinainte; daca vreuna si-ar
  schimba starea, contrasemnarea se anuleaza si ramane originalul (E-516);
- nu contrasemneaza un document certificat cu `DocMDP P=1` (nicio modificare
  permisa): ar deveni invalid (E-517);
- verifica regulile depunerii: numai PDF, marimea maxima, semnatura
  reprezentantului ultima (E-518).

Totul offline; nicio semnatura existenta nu se modifica sau nu se ascunde.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pikepdf

from app.core.errors import CoreError
from app.core.model import ProgressCallback
from app.core.pdf.signatures import (
    STATUS_EXPIRED,
    STATUS_UNVERIFIABLE,
    STATUS_VALID,
    SignatureInfo,
    validate_bytes,
)

DEFAULT_MAX_MB = 50
"""E-518: limita MySMIS2021+ pe fisier (ghidul solicitantului)."""

GOOD = frozenset({STATUS_VALID, STATUS_EXPIRED, STATUS_UNVERIFIABLE})
"""Starile care nu inseamna o semnatura stricata (G-041, E-507)."""

# Problemele unui document, ca si coduri; textul vine din traduceri (`submission.issue.*`).
ISSUE_NOT_PDF = "not_pdf"
ISSUE_TOO_BIG = "too_big"
ISSUE_UNSIGNED = "unsigned"
ISSUE_LOCKED = "docmdp_locked"
ISSUE_BROKEN = "signature_broken"
ISSUE_REVERTED = "countersign_reverted"
ISSUE_NOT_LAST = "representative_not_last"
ISSUE_UNREADABLE = "unreadable"
ISSUES = (ISSUE_NOT_PDF, ISSUE_TOO_BIG, ISSUE_UNSIGNED, ISSUE_LOCKED, ISSUE_BROKEN,
          ISSUE_REVERTED, ISSUE_NOT_LAST, ISSUE_UNREADABLE)


@dataclass
class PackEntry:
    source: Path
    output: Path | None = None
    sha256: str = ""
    size: int = 0
    before: list[SignatureInfo] = field(default_factory=list)
    after: list[SignatureInfo] = field(default_factory=list)
    countersigned: bool = False
    docmdp: int | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class PackResult:
    folder: Path
    entries: list[PackEntry]
    archive: Path | None = None

    @property
    def ok(self) -> bool:
        """Toate documentele sunt in pachet, cu semnaturile de dinainte valide."""
        return all(e.output is not None and ISSUE_BROKEN not in e.issues
                   and ISSUE_REVERTED not in e.issues for e in self.entries)


Countersign = Callable[[Path, Path, bool], None]
"""(sursa, destinatia, vizibila): scrie la destinatie documentul contrasemnat
incremental; `vizibila=False` pe documentele certificate (E-515)."""


def docmdp_level(data: bytes) -> int | None:
    """E-517: nivelul DocMDP al unui document certificat (1, 2 sau 3); None pentru
    un document fara semnatura de certificare. Implicit 2 (ISO 32000-1 §12.8.2.2)."""
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            perms = pdf.Root.get("/Perms")
            sig = perms.get("/DocMDP") if perms is not None else None
            if sig is None:
                return None
            for ref in sig.get("/Reference", []):
                if ref.get("/TransformMethod") == "/DocMDP":
                    params = ref.get("/TransformParams")
                    value = params.get("/P") if params is not None else None
                    return int(value) if value is not None else 2
            return 2
    except (pikepdf.PdfError, ValueError, TypeError):
        return None


def output_name(index: int, total: int, source: Path) -> str:
    """E-514: `01_<nume>.pdf`, ca ordinea anexelor sa se pastreze in orice listare."""
    width = max(2, len(str(total)))
    return f"{index:0{width}d}_{source.name}"


def check_entry(entry: PackEntry, data: bytes, *, max_mb: float) -> None:
    """E-518: regulile depunerii, inainte de orice semnare."""
    if not data.startswith(b"%PDF-"):
        entry.issues.append(ISSUE_NOT_PDF)
    if entry.size > max_mb * 1024 * 1024:
        entry.issues.append(ISSUE_TOO_BIG)
    if not entry.before:
        entry.issues.append(ISSUE_UNSIGNED)
    if any(s.status not in GOOD for s in entry.before):
        entry.issues.append(ISSUE_BROKEN)


def build_pack(files: Sequence[Path], folder: Path, *, countersign: Countersign | None = None,
               representative: str | None = None, max_mb: float = DEFAULT_MAX_MB,
               archive_name: str | None = None,
               password: Callable[[Path], str | None] | None = None,
               progress: ProgressCallback | None = None) -> PackResult:
    """E-514…E-518: pachetul in `folder` (creat daca lipseste; fisierele existente cu
    acelasi nume nu se suprascriu). `countersign`: contrasemnarea incrementala a
    reprezentantului legal (None = numai copiere si verificare). `representative`:
    numele din certificatul lui, pentru E-518. `archive_name`: si o arhiva ZIP cu
    pachetul. Un fisier ilizibil se raporteaza si se sare."""
    from app.core.model import Progress

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    entries: list[PackEntry] = []
    total = len(files)
    for index, raw in enumerate(files, start=1):
        source = Path(raw)
        if progress is not None:
            progress(Progress(index - 1, total, "stage.submission", source.name))
        entry = PackEntry(source)
        entries.append(entry)
        try:
            data = source.read_bytes()
        except OSError:
            entry.issues.append(ISSUE_UNREADABLE)
            continue
        entry.size = len(data)
        entry.sha256 = hashlib.sha256(data).hexdigest()
        pdf_password = password(source) if password is not None else None
        entry.before = validate_bytes(data, pdf_password) if data.startswith(b"%PDF-") else []
        entry.docmdp = docmdp_level(data)
        check_entry(entry, data, max_mb=max_mb)
        target = _free(folder / output_name(index, total, source))
        if countersign is None or ISSUE_NOT_PDF in entry.issues:
            _keep_original(entry, data, target)
        elif entry.docmdp == 1:  # E-517: orice schimbare l-ar invalida
            entry.issues.append(ISSUE_LOCKED)
            _keep_original(entry, data, target)
        else:
            _countersign_checked(entry, data, target, countersign, pdf_password)
        if representative and entry.after and \
                (entry.after[-1].signer or "") != representative:  # E-518
            entry.issues.append(ISSUE_NOT_LAST)
    if progress is not None:
        progress(Progress(total, total, "stage.submission"))
    result = PackResult(folder, entries)
    if archive_name:
        result.archive = _zip(folder / archive_name, [e.output for e in entries if e.output])
    return result


def _keep_original(entry: PackEntry, data: bytes, target: Path) -> None:
    _copy_exact(data, target, entry.sha256)
    entry.output, entry.after = target, entry.before


def _countersign_checked(entry: PackEntry, data: bytes, target: Path, countersign: Countersign,
                         password: str | None) -> None:
    """E-515, E-516: contrasemnarea, apoi verificarea semnaturilor de dinainte. O
    semnatura care isi schimba starea anuleaza contrasemnarea: ramane originalul."""
    staging = target.with_name(f".{target.name}.semnare")
    try:
        # E-515: pe un document certificat (P=2, P=3) se semneaza fara camp vizibil
        countersign(entry.source, staging, entry.docmdp is None)
        signed = staging.read_bytes()
    except (CoreError, OSError, ValueError):
        staging.unlink(missing_ok=True)
        raise
    # actualizare incrementala: octetii originalului raman, neschimbati, la inceput
    unchanged = signed.startswith(data)
    after = validate_bytes(signed, password) if unchanged else []
    earlier = {s.field_name: s.status for s in entry.before}
    kept = all(s.status in GOOD or earlier[s.field_name] not in GOOD
               for s in after if s.field_name in earlier)
    seen = {s.field_name for s in after}
    new = [s for s in after if s.field_name not in earlier]
    if not unchanged or not kept or not set(earlier) <= seen or not new \
            or any(s.status not in GOOD for s in new):
        staging.unlink(missing_ok=True)
        entry.issues.append(ISSUE_REVERTED)
        _keep_original(entry, data, target)
        return
    staging.replace(target)
    entry.output, entry.after, entry.countersigned = target, after, True


def _copy_exact(data: bytes, target: Path, digest: str) -> None:
    """E-514: copia e identica; amprenta se verifica dupa scriere."""
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(data)
    if hashlib.sha256(tmp.read_bytes()).hexdigest() != digest:
        tmp.unlink(missing_ok=True)
        raise CoreError("copia nu e identica cu originalul", path=str(target))
    tmp.replace(target)


def _free(target: Path) -> Path:
    candidate, n = target, 1
    while candidate.exists():
        n += 1
        candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
    return candidate


def _zip(target: Path, files: Sequence[Path]) -> Path:
    """Arhiva pachetului, fara compresie (PDF-urile sunt deja comprimate)."""
    target = _free(target)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return target


def signer_service_countersign(service: Any, options_for: Callable[[Any], Any],
                               passphrase: bytes | None) -> Countersign:
    """Adaptorul pentru `SignatureService.sign` (G-030): semnatura de aprobare se
    adauga incremental pe fisierul exact (semnaturile vechi raman, G-044)."""
    from app.core.pdf.document import PdfDocument

    def run(source: Path, target: Path, visible: bool) -> None:
        with PdfDocument.open(source) as document:
            options = options_for(document)
            if not visible:
                options = dataclasses.replace(options, rect=None)
            service.sign(document, options, passphrase=passphrase, target=target)

    return run


STAMP_BOX = (36.0, 36.0, 236.0, 86.0)
"""E-515: locul semnaturii vizibile pe ultima pagina, in puncte (jos, stanga)."""


def pkcs12_countersign(pkcs12: Path, passphrase: bytes | None, *, stamp_text: str,
                       now: Any = None) -> Countersign:
    """E-515: contrasemnarea cu certificatul reprezentantului (PKCS#12), ca la
    sigiliul dosarului (E-506). `stamp_text` vine din traduceri si poate folosi
    `%(signer)s` si `%(ts)s`. Certificat expirat → `CertificateInvalidError`."""
    from datetime import UTC, datetime

    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko.stamp import TextStampStyle

    from app.core.pdf.dossier import CertificateInvalidError

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

    def run(source: Path, target: Path, visible: bool) -> None:
        data = Path(source).read_bytes()
        writer = IncrementalPdfFileWriter(io.BytesIO(data))
        name = _free_field(data)
        last = len(writer.root["/Pages"]["/Kids"]) - 1 if visible else 0
        spec = fields.SigFieldSpec(name, on_page=max(0, last), box=STAMP_BOX) if visible \
            else fields.SigFieldSpec(name)
        style = TextStampStyle(stamp_text=stamp_text) if visible else None
        signed = signers.PdfSigner(signers.PdfSignatureMetadata(field_name=name), signer,
                                   stamp_style=style, new_field_spec=spec)
        Path(target).write_bytes(signed.sign_pdf(writer).getvalue())

    return run


def representative_name(pkcs12: Path, passphrase: bytes | None) -> str | None:
    """E-518: numele din certificatul reprezentantului, ca in raportul semnaturilor."""
    from pyhanko.sign import signers

    try:
        signer = signers.SimpleSigner.load_pkcs12(str(pkcs12), passphrase=passphrase)
    except (OSError, ValueError):
        return None
    if signer is None:
        return None
    native = signer.signing_cert.subject.native
    return str(native.get("common_name") or signer.signing_cert.subject.human_friendly)


def _free_field(data: bytes) -> str:
    """Un nume de camp de semnatura nefolosit in document."""
    names: set[str] = set()
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            form = pdf.Root.get("/AcroForm")
            for item in (form.get("/Fields", []) if form is not None else []):
                if "/T" in item:
                    names.add(str(item.T))
    except pikepdf.PdfError:
        pass
    n = 1
    while f"Reprezentant{n}" in names:
        n += 1
    return f"Reprezentant{n}"
