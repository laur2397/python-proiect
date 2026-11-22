"""Lista semnaturilor digitale, cu starea lor (faza 7, pasul 7.5): B-024.

Semnaturile se valideaza la deschidere, cu pyHanko, **strict offline**: nu se
descarca certificate, liste de revocare sau raspunsuri OCSP (CLAUDE.md §6.1,
Y-001). De aceea increderea in semnatar ramane necunoscuta (`trusted` None)
cand lantul certificatului nu se poate verifica local; integritatea si
acoperirea documentului se verifica intotdeauna.

Se valideaza fisierul de pe disc, nu documentul din memorie: semnatura
acopera octetii salvati. Semnarea, sigiliul de timp si verificarea de
incredere cu certificatele utilizatorului vin in faza 10 (G-*).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING, Any

from app.core.applog import get_logger

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

_log = get_logger("pdf.signatures")

STATUS_VALID = "valid"
"""Intacta si acopera documentul (dupa ea nu s-a schimbat nimic nepermis)."""
STATUS_MODIFIED = "modified"
"""Intacta, dar documentul a fost schimbat dupa semnare."""
STATUS_INVALID = "invalid"
"""Continutul semnat nu mai corespunde, sau semnatura nu se poate citi."""
STATUS_UNVERIFIABLE = "unverifiable"
"""E-507: verificarea ar cere date de pe retea (revocare); offline nu se poate
spune, deci nu e raportata ca invalida."""
_ONLINE_HINTS = ("revocation", "ocsp", "crl", "fetch")


@dataclass(frozen=True, slots=True)
class SignatureInfo:
    field_name: str
    status: str
    """STATUS_VALID, STATUS_MODIFIED sau STATUS_INVALID."""
    page: int | None = None
    signer: str | None = None
    signed_at: str | None = None
    """ISO 8601 UTC: ora sigiliului de timp, altfel cea declarata de semnatar."""
    trusted: bool | None = None
    """True = lant de incredere verificat local; None = nu se poate sti offline."""
    reason: str | None = None
    location: str | None = None
    issuer: str | None = None
    """E-502: emitentul certificatului semnatarului."""


def _page_numbers(reader: Any) -> dict[tuple[int, int], int]:
    pages: dict[tuple[int, int], int] = {}

    def walk(node_ref: Any) -> None:
        node = node_ref.get_object()
        if node.get("/Type") == "/Pages":
            for kid in node["/Kids"]:
                walk(kid)
        else:
            pages[(node_ref.idnum, node_ref.generation)] = len(pages) + 1

    try:
        walk(reader.root.raw_get("/Pages"))
    except (KeyError, AttributeError, TypeError):
        return {}
    return pages


def _page_of(field: Any, pages: dict[tuple[int, int], int]) -> int | None:
    try:
        kids = field.get("/Kids")
        widget = kids[0].get_object() if kids else field
        ref = widget.raw_get("/P")
        return pages.get((ref.idnum, ref.generation))
    except (KeyError, AttributeError, IndexError, TypeError):
        return None


def _state(status: Any) -> str:
    if not (status.intact and status.valid):
        return STATUS_INVALID
    coverage = getattr(status.coverage, "name", "")
    level = getattr(getattr(status, "modification_level", None), "name", "")
    if coverage == "ENTIRE_FILE" or level in ("NONE", "LTA_UPDATES"):
        return STATUS_VALID
    return STATUS_MODIFIED


def _name(name: Any) -> str:
    """Numele comun din certificat (`Ana Popescu`), altfel numele complet."""
    common = name.native.get("common_name") if isinstance(name.native, dict) else None
    return str(common) if common else name.human_friendly


# B-024
def signatures(document: PdfDocument) -> list[SignatureInfo]:
    """Semnaturile din fisierul documentului, in ordinea din formular."""
    if document.path is None or not document.path.is_file():
        return []
    return validate_bytes(document.path.read_bytes(), document._password)


# B-024, E-502, E-507
def validate_bytes(data: bytes, password: str | None = None) -> list[SignatureInfo]:
    """Semnaturile unui PDF dat ca octeti, validate strict offline. Un fisier
    care nu e PDF sau nu se poate citi nu are semnaturi."""
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext
    except ImportError:  # pragma: no cover - dependenta lipsa la instalare
        _log.warning("pyHanko lipseste: semnaturile nu se pot valida")
        return []
    try:
        reader = PdfFileReader(io.BytesIO(data), strict=False)
        if reader.encrypted and password:
            reader.decrypt(password)
        embedded = list(reader.embedded_signatures)
    except Exception as exc:  # noqa: BLE001 - un fisier ciudat nu blocheaza deschiderea
        _log.warning("semnaturile nu se pot citi: %s", exc)
        return []
    pages = _page_numbers(reader) if embedded else {}
    quiet = logging.getLogger("pyhanko")  # lantul neverificabil offline e normal aici
    previous, quiet.disabled = quiet.disabled, True
    out = []
    try:
        for sig in embedded:
            name = str(sig.field_name)
            page = _page_of(sig.sig_field, pages)
            signed = sig.sig_object
            reason = str(signed["/Reason"]) if "/Reason" in signed else None
            location = str(signed["/Location"]) if "/Location" in signed else None
            try:
                status = validate_pdf_signature(
                    sig, ValidationContext(trust_roots=[], allow_fetching=False))
            except Exception as exc:  # noqa: BLE001 - semnatura stricata = invalida
                _log.warning("semnatura %s nu se poate valida: %s", name, exc)
                online = any(h in str(exc).lower() for h in _ONLINE_HINTS)
                out.append(SignatureInfo(name, STATUS_UNVERIFIABLE if online else STATUS_INVALID,
                                         page, reason=reason, location=location))
                continue
            stamp = getattr(status, "timestamp_validity", None)
            when = stamp.timestamp if stamp is not None else status.signer_reported_dt
            try:
                signer = _name(status.signing_cert.subject)
                issuer = _name(status.signing_cert.issuer)
            except AttributeError:
                signer = issuer = None
            out.append(SignatureInfo(
                name, _state(status), page, signer,
                when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if when else None,
                True if status.trusted else None, reason, location, issuer))
    finally:
        quiet.disabled = previous
    return out
