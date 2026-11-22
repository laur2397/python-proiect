"""Semnaturile digitale (faza 10, pasul 10.2): G-030…G-047.

Certificatele sunt fisiere PKCS#12 inregistrate in setari numai cu calea,
amprenta si datele publice ale certificatului (SPEC_04: nicio cheie privata si
nicio parola nu se pastreaza); parola fisierului se cere la fiecare semnare.

Semnatura se adauga ca actualizare incrementala peste octetii exacti ai
fisierului (pyHanko), deci semnaturile anterioare raman valide (G-044). Aspectul
vizibil (G-035…G-039, G-105, G-107) se deseneaza ca imagine, cu fontul de sistem
cu diacritice, si se pune ca fond al casetei semnaturii; textele lui vin de la
apelant (`texts(cheie, **parametri)`), din fisierele de traducere.

Marca temporala (G-037) se cere numai unui server configurat explicit de
utilizator; fara raspuns, semnarea se opreste (`TimestampUnavailableError`) sau,
daca utilizatorul a acceptat, continua fara marca.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.errors import (
    CertificateNotOwnedError,
    NoCertificateError,
    TimestampUnavailableError,
    WrongPasswordError,
)
from app.core.model import Rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

Texts = Callable[..., str]
SETTING = "signing.certificates"
HASHES = {"SHA-256": "sha256", "SHA-384": "sha384", "SHA-512": "sha512"}
"""G-045: algoritmii de semnare; MD5 numai la verificare."""
APP_VERSION = "DocuLens 0.1"
APPEARANCE_DPI = 200


@dataclass
class SignatureOptions:
    """G-030…G-039 (SPEC_05), cu datele serverului de marca temporala (G-037)."""

    certificate_id: str
    page: int
    rect: Rect
    reason: str | None = None
    location: str | None = None
    contact: str | None = None
    hash_algorithm: str = "SHA-256"
    timestamp_url: str | None = None
    timestamp_user: str | None = None
    timestamp_password: str | None = None
    show_reason: bool = True
    show_location: bool = False
    show_contact: bool = False
    show_date: bool = True
    show_owner: bool = True
    show_app_version: bool = False
    show_labels: bool = True
    borders_and_background: bool = True
    image: Path | None = None


# --- certificatele (G-031, G-032) ------------------------------------------------------------


def _load(path: Path, passphrase: bytes | None) -> Any:
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        key, cert, _extra = pkcs12.load_key_and_certificates(Path(path).read_bytes(),
                                                             passphrase)
    except ValueError as exc:
        raise WrongPasswordError("parola certificatului nu e corecta", path=str(path)) from exc
    except OSError as exc:
        raise NoCertificateError(str(exc), path=str(path)) from exc
    if key is None or cert is None:
        raise NoCertificateError("fisierul nu are cheie privata", path=str(path))
    return cert


def _common_name(name: Any) -> str:
    from cryptography.x509.oid import NameOID

    common = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return str(common[0].value) if common else name.rfc4514_string()


class CertificateStore:
    """G-031: certificatele cu cheie privata (fisiere PKCS#12) ale utilizatorului."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def _entries(self) -> list[dict[str, Any]]:
        return list(self.settings.get(SETTING) or [])

    def add(self, path: Path, passphrase: bytes | None) -> str:
        """Verifica fisierul si parola, apoi pastreaza calea, amprenta si datele
        publice ale certificatului."""
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cert = _load(path, passphrase)
        fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
        try:
            usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
            key_usage = [k for k in ("digital_signature", "content_commitment")
                         if getattr(usage, k)]
        except x509.ExtensionNotFound:
            key_usage = []
        entries = [e for e in self._entries() if e["fingerprint"] != fingerprint]
        entries.append({
            "path": str(Path(path).resolve()), "fingerprint": fingerprint,
            "subject": _common_name(cert.subject), "issuer": _common_name(cert.issuer),
            "subject_dn": cert.subject.rfc4514_string(),
            "issuer_dn": cert.issuer.rfc4514_string(),
            "serial": format(cert.serial_number, "x"),
            "not_before": cert.not_valid_before_utc.isoformat(),
            "not_after": cert.not_valid_after_utc.isoformat(), "key_usage": key_usage})
        self.settings.set(SETTING, entries)
        return fingerprint

    def remove(self, cert_id: str) -> None:
        self.settings.set(SETTING, [e for e in self._entries() if e["fingerprint"] != cert_id])

    def list_certificates(self) -> list[tuple[str, str, str]]:
        """(id, titular, emitent) ale certificatelor al caror fisier exista."""
        return [(e["fingerprint"], e["subject"], e["issuer"]) for e in self._entries()
                if Path(e["path"]).is_file()]

    def entry(self, cert_id: str) -> dict[str, Any]:
        for e in self._entries():
            if e["fingerprint"] == cert_id:
                return e
        raise NoCertificateError("certificatul nu e instalat", certificate=cert_id)

    def certificate_details(self, cert_id: str) -> Mapping[str, Any]:
        """G-032 `Show Certificate...`: datele publice ale certificatului."""
        return dict(self.entry(cert_id))

    def signer(self, cert_id: str, passphrase: bytes | None) -> Any:
        from pyhanko.sign import signers

        entry = self.entry(cert_id)
        _load(Path(entry["path"]), passphrase)  # parola gresita → WrongPasswordError
        return signers.SimpleSigner.load_pkcs12(entry["path"], passphrase=passphrase)


# --- aspectul semnaturii (G-035…G-039, G-105, G-107) ------------------------------------------


def appearance_lines(options: SignatureOptions, signer: str, when: datetime,
                     texts: Texts) -> list[str]:
    """G-105, G-106: `Digitally signed by <nume>`, motivul, locatia, contactul,
    data si versiunea aplicatiei, dupa bife; G-036: fara etichete la cerere."""
    def labelled(key: str, value: str) -> str:
        return f"{texts(f'signature.label.{key}')}: {value}" if options.show_labels else value

    lines = []
    if options.show_owner:
        lines.append(texts("signature.signed_by", name=signer))
    if options.show_reason and options.reason:
        lines.append(labelled("reason", options.reason))
    if options.show_location and options.location:
        lines.append(labelled("location", options.location))
    if options.show_contact and options.contact:
        lines.append(labelled("contact", options.contact))
    if options.show_date:
        lines.append(labelled("date", when.strftime("%Y.%m.%d %H:%M:%S %z").strip()))
    if options.show_app_version:
        lines.append(labelled("version", APP_VERSION))
    return lines


def appearance_image(options: SignatureOptions, lines: list[str]) -> Any:
    """Imaginea casetei: fundal si chenar (G-038), imaginea proprie in stanga
    (G-039), textul in dreapta (sau pe toata caseta)."""
    from PIL import Image, ImageDraw, ImageFont

    from app.core.pdf.redact import text_font_file

    scale = APPEARANCE_DPI / 72
    width = max(int(options.rect.w * scale), 20)
    height = max(int(options.rect.h * scale), 10)
    background = (232, 238, 247, 255) if options.borders_and_background else (255, 255, 255, 0)
    image = Image.new("RGBA", (width, height), background)
    left = 0
    if options.image is not None:
        with Image.open(options.image) as source:
            picture = source.convert("RGBA")
        picture.thumbnail((max(width // 2 - 8, 1), max(height - 8, 1)))
        image.alpha_composite(picture, (4, (height - picture.height) // 2))
        left = width // 2
    font_path = text_font_file()
    draw = ImageDraw.Draw(image)
    size = max(8, min(int(height / max(len(lines), 1) * 0.75), int(14 * scale)))
    font: Any = ImageFont.load_default()
    while size > 6:
        font = ImageFont.truetype(str(font_path), size) if font_path else \
            ImageFont.load_default()
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if widest <= width - left - 8 and size * 1.2 * len(lines) <= height - 4:
            break
        size -= 1
    y = max(2.0, (height - size * 1.2 * len(lines)) / 2)
    for line in lines:
        draw.text((left + 4, y), line, fill=(20, 30, 60, 255), font=font)
        y += size * 1.2
    return image


# --- semnarea (G-030, G-033…G-040, G-044, G-045, G-037) ----------------------------------------


class SignatureService:
    """G-030…G-047 (SPEC_05)."""

    def __init__(self, store: CertificateStore, texts: Texts) -> None:
        self.store = store
        self.texts = texts

    def list_certificates(self) -> list[tuple[str, str, str]]:
        return self.store.list_certificates()

    def certificate_details(self, cert_id: str) -> Mapping[str, Any]:
        return self.store.certificate_details(cert_id)

    def _source(self, document: PdfDocument) -> bytes:
        """Octetii de semnat: fisierul exact (semnaturile vechi raman valide,
        G-044) sau, cu modificari nesalvate, documentul salvat in memorie."""
        if document.path is not None and document.path.is_file() and not document.is_modified:
            return document.path.read_bytes()
        pdf = document._pike()
        out = io.BytesIO()
        pdf.save(out, **document._save_kwargs(pdf, keep_encryption=True))
        return out.getvalue()

    def sign(self, document: PdfDocument, options: SignatureOptions, *,
             passphrase: bytes | None = None, pin_callback: Callable[[], str] | None = None,
             allow_without_timestamp: bool = False, target: Path | None = None,
             timestamper: Any = None, field_name: str | None = None) -> Path:
        """`Save and sign` (G-040): semnatura se aplica si fisierul se scrie
        (`target` sau fisierul documentului), iar documentul trece pe el.
        `field_name`: un camp de semnatura gol din formular (H-035), semnat in
        locul unui camp nou.
        Erori: `NoCertificateError`, `WrongPasswordError`,
        `TimestampUnavailableError` (G-037), `ValueError` (algoritm nepermis)."""
        from pyhanko.pdf_utils.images import PdfImage
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers
        from pyhanko.stamp import TextStampStyle

        from app.core.pdf.text import page_geometry, to_pdf_rect

        if options.hash_algorithm not in HASHES:
            raise ValueError(f"algoritm de semnare nepermis: {options.hash_algorithm} (G-045)")
        document._check_pages([options.page])
        destination = Path(target) if target is not None else document.path
        if destination is None:
            raise ValueError("documentul trebuie salvat intai")
        if passphrase is None and pin_callback is not None:
            entered = pin_callback()
            passphrase = entered.encode() if entered else None
        signer = self.store.signer(options.certificate_id, passphrase)
        native = signer.signing_cert.subject.native
        name = str(native.get("common_name") or signer.signing_cert.subject.human_friendly)
        when = datetime.now(UTC).astimezone()
        image = appearance_image(options, appearance_lines(options, name, when, self.texts))
        page = document._pike().pages[options.page - 1]
        box = to_pdf_rect(page_geometry(page), options.rect)
        existing = field_name is not None
        field_name = field_name or _free_field_name(document)
        source = self._source(document)

        def run(stamper: Any) -> bytes:
            writer = IncrementalPdfFileWriter(io.BytesIO(source))
            if writer.prev.encrypted and document._password:
                writer.encrypt(document._password)
            meta = signers.PdfSignatureMetadata(
                field_name=field_name, reason=options.reason, location=options.location,
                contact_info=options.contact, md_algorithm=HASHES[options.hash_algorithm])
            style = TextStampStyle(stamp_text=" ",
                                   border_width=1 if options.borders_and_background else 0,
                                   background=PdfImage(image), background_opacity=1.0)
            spec = None if existing else fields.SigFieldSpec(
                sig_field_name=field_name, on_page=options.page - 1, box=box)
            pdf_signer = signers.PdfSigner(meta, signer, timestamper=stamper,
                                           stamp_style=style, new_field_spec=spec)
            return pdf_signer.sign_pdf(writer).getvalue()

        stamper = timestamper
        if stamper is None and options.timestamp_url:
            from pyhanko.sign.timestamps import HTTPTimeStamper

            auth = (options.timestamp_user, options.timestamp_password or "") \
                if options.timestamp_user else None
            stamper = HTTPTimeStamper(options.timestamp_url, auth=auth)
        try:
            signed = run(stamper)
        except Exception as exc:
            if stamper is None:
                raise
            if not allow_without_timestamp:
                raise TimestampUnavailableError("serverul de marca temporala nu raspunde",
                                                url=options.timestamp_url or "") from exc
            signed = run(None)
        own = document.path is not None and destination.resolve() == document.path.resolve()
        document._replace_file(signed, destination)
        if not own:
            document._switch_to(destination, keep_encryption=True)
        document._reload_from(destination)
        document.is_modified = False
        return destination

    # G-041, G-042
    def validate_all(self, document: PdfDocument) -> list[Mapping[str, Any]]:
        """Starea fiecarei semnaturi; un certificat expirat da `valid_expired`,
        nu `invalid` (G-041)."""
        from app.core.pdf.signatures import signatures

        return [{"field_name": s.field_name, "status": s.status, "page": s.page, "signer": s.signer,
                     "issuer": s.issuer, "signed_at": s.signed_at, "trusted": s.trusted,
                     "reason": s.reason, "location": s.location} for s in signatures(document)]

    def properties(self, document: PdfDocument, field_name: str) -> Mapping[str, Any]:
        """G-042 `Show Signature Properties...`: starea si certificatul."""
        from pyhanko.pdf_utils.reader import PdfFileReader

        info = next((s for s in self.validate_all(document) if s["field_name"] == field_name),
                    None)
        if info is None or document.path is None:
            raise KeyError(field_name)
        reader = PdfFileReader(io.BytesIO(document.path.read_bytes()), strict=False)
        if reader.encrypted and document._password:
            reader.decrypt(document._password)
        sig = next(s for s in reader.embedded_signatures if s.field_name == field_name)
        cert = sig.signer_cert
        validity = cert["tbs_certificate"]["validity"]
        contact = sig.sig_object.get("/ContactInfo")
        return {**info, "contact": str(contact) if contact is not None else None,
                "serial": format(cert.serial_number, "x"),
                "certificate_subject": cert.subject.human_friendly,
                "certificate_issuer": cert.issuer.human_friendly,
                "not_before": validity["not_before"].native.isoformat(),
                "not_after": validity["not_after"].native.isoformat(),
                "hash_algorithm": sig.md_algorithm.upper().replace("SHA", "SHA-"),
                "fingerprint": hashlib.sha256(cert.dump()).hexdigest()}

    # G-043
    def delete_signature(self, document: PdfDocument, field_name: str) -> None:
        """`Remove Signature`: cere certificatul potrivit
        (`CertificateNotOwnedError` fara el). Campul si aspectul lui dispar."""
        owned = {c[0] for c in self.store.list_certificates()}
        if self.properties(document, field_name)["fingerprint"] not in owned:
            raise CertificateNotOwnedError("semnatura apartine altui certificat",
                                           field=field_name)
        pdf = document._pike()
        form = pdf.Root.get("/AcroForm")
        target = None
        if form is not None:
            kept = []
            for item in form.get("/Fields", []):
                if str(item.get("/T", "")) == field_name:
                    target = item
                else:
                    kept.append(item)
            form.Fields = pikepdf.Array(kept)
        if target is None:
            raise KeyError(field_name)
        for page in pdf.pages:
            annots = page.obj.get("/Annots")
            if annots is None:
                continue
            page.obj.Annots = pikepdf.Array([
                a for a in annots
                if not (a.objgen == target.objgen or
                        (a.get("/Parent") is not None and a.Parent.objgen == target.objgen))])
        document._changed()


def _free_field_name(document: PdfDocument) -> str:
    form = document._pike().Root.get("/AcroForm")
    taken = {str(f.get("/T", "")) for f in form.get("/Fields", [])} if form is not None \
        else set()
    n = 1
    while f"Semnatura{n}" in taken:
        n += 1
    return f"Semnatura{n}"
