"""Semnaturile digitale (faza 10, pasul 10.2): G-030…G-045, G-104…G-107.
Certificatele sunt de test, generate in teste."""

from __future__ import annotations

import io
import json
import socket
from datetime import datetime
from pathlib import Path

import pikepdf
import pytest
from test_pdf_dossier import pkcs12
from test_pdf_search import text_pdf

from app.core.context import AppContext
from app.core.errors import (
    CertificateNotOwnedError,
    NoCertificateError,
    TimestampUnavailableError,
    WrongPasswordError,
)
from app.core.model import Rect
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.signatures import STATUS_EXPIRED, STATUS_VALID
from app.core.pdf.signing import (
    CertificateStore,
    SignatureOptions,
    SignatureService,
    appearance_lines,
)

CATALOG = json.loads((Path(__file__).resolve().parent.parent / "app/gui/i18n/ro.json")
                     .read_text(encoding="utf-8"))
BOX = Rect(300, 650, 220, 70)


def texts(key, **params):
    return CATALOG[key].format(**params)


class EmptySettings:
    """Setarile altui utilizator: niciun certificat instalat."""

    def get(self, key):
        return []

    def set(self, key, value):
        pass


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def service(ctx, tmp_path):
    store = CertificateStore(ctx.settings)
    store.add(pkcs12(tmp_path), b"parola")
    return SignatureService(store, texts)


@pytest.fixture
def doc(tmp_path):
    path = text_pdf(tmp_path / "contract.pdf", [["Contract de finantare"], ["Anexa"]])
    with PdfDocument.open(path) as d:
        yield d


def options(service, **kw):
    [(cert_id, _holder, _issuer)] = service.list_certificates()
    return SignatureOptions(certificate_id=cert_id, page=1, rect=BOX, **kw)


@pytest.fixture
def no_network(monkeypatch):
    real = socket.socket.connect

    def local_only(self, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError("semnarea a incercat sa iasa pe retea")
        return real(self, address)
    monkeypatch.setattr(socket.socket, "connect", local_only)


# --- G-031, G-032 -----------------------------------------------------------------------------


def test_T_G031_G032_certificates(ctx, tmp_path):
    store = CertificateStore(ctx.settings)
    path = pkcs12(tmp_path)
    with pytest.raises(WrongPasswordError):
        store.add(path, b"gresita")
    cert_id = store.add(path, b"parola")
    assert store.list_certificates() == [(cert_id, "Firma de test SRL", "Firma de test SRL")]
    details = store.certificate_details(cert_id)
    assert details["not_after"] > details["not_before"]
    assert "digital_signature" in details["key_usage"]
    assert "parola" not in json.dumps(ctx.settings.get("signing.certificates"))
    with pytest.raises(NoCertificateError):
        store.entry("lipsa")


# --- G-030, G-033…G-040, G-104…G-107 ------------------------------------------------------------


def test_T_G030_G040_sign_and_save(service, doc, no_network):
    target = service.sign(doc, options(service, reason="Sunt autorul acestui document",
                                       location="Bucuresti", contact="ana@exemplu.ro"),
                          passphrase=b"parola")
    assert target == doc.path and not doc.is_modified
    [sig] = service.validate_all(doc)
    assert sig["status"] == STATUS_VALID and sig["signer"] == "Firma de test SRL"
    props = service.properties(doc, sig["field_name"])
    assert props["reason"] == "Sunt autorul acestui document"
    assert props["location"] == "Bucuresti" and props["contact"] == "ana@exemplu.ro"
    assert props["hash_algorithm"] == "SHA-256"
    with pikepdf.open(doc.path) as pdf:  # G-107: caseta semnaturii pe pagina
        widgets = [a for a in pdf.pages[0].obj.Annots if a.get("/Subtype") == "/Widget"]
        assert len(widgets) == 1 and "/AP" in widgets[0]
    assert doc.extract_text(1).strip().startswith("Contract")


def test_T_G033_G036_appearance_text():
    opts = SignatureOptions("x", 1, BOX, reason="Am aprobat", location="Cluj",
                            show_location=True, show_app_version=True)
    when = datetime(2026, 2, 7, 14, 5, 9)
    lines = appearance_lines(opts, "Ana Popescu", when, texts)
    assert lines[0] == "Semnat digital de Ana Popescu"
    assert "Motiv: Am aprobat" in lines and "Locație: Cluj" in lines
    assert any(line.startswith("Data: 2026.02.07 14:05:09") for line in lines)
    assert any("DocuLens" in line for line in lines)
    opts.show_labels = False  # G-036
    assert "Am aprobat" in appearance_lines(opts, "Ana Popescu", when, texts)
    opts.show_owner = opts.show_date = False  # G-035
    assert not any("Ana Popescu" in line
                   for line in appearance_lines(opts, "Ana Popescu", when, texts))


def test_T_G039_custom_image_in_the_signature(service, doc, tmp_path):
    from PIL import Image

    logo = tmp_path / "sigla.png"
    Image.new("RGB", (100, 50), "red").save(logo)
    service.sign(doc, options(service, image=logo, borders_and_background=False),
                 passphrase=b"parola")
    assert service.validate_all(doc)[0]["status"] == STATUS_VALID


# --- G-044, G-045 -------------------------------------------------------------------------------


def test_T_G044_earlier_signatures_stay_valid(service, doc):
    service.sign(doc, options(service), passphrase=b"parola")
    second = SignatureOptions(certificate_id=service.list_certificates()[0][0], page=2,
                              rect=BOX, hash_algorithm="SHA-512")
    service.sign(doc, second, passphrase=b"parola")
    sigs = service.validate_all(doc)
    assert [s["status"] for s in sigs] == [STATUS_VALID, STATUS_VALID]
    assert [s["field_name"] for s in sigs] == ["Semnatura1", "Semnatura2"]
    assert service.properties(doc, "Semnatura2")["hash_algorithm"] == "SHA-512"  # G-045


def test_T_G045_md5_is_not_used_for_signing(service, doc):
    with pytest.raises(ValueError):
        service.sign(doc, options(service, hash_algorithm="MD5"), passphrase=b"parola")


def test_wrong_passphrase_and_pin_callback(service, doc):
    with pytest.raises(WrongPasswordError):
        service.sign(doc, options(service), passphrase=b"gresita")
    service.sign(doc, options(service), pin_callback=lambda: "parola")
    assert len(service.validate_all(doc)) == 1


# --- G-037 -------------------------------------------------------------------------------------


def test_T_G037_unreachable_timestamp_server(service, doc):
    opts = options(service, timestamp_url="http://127.0.0.1:9/tsa")
    with pytest.raises(TimestampUnavailableError):
        service.sign(doc, opts, passphrase=b"parola")
    assert service.validate_all(doc) == []  # nimic semnat
    service.sign(doc, opts, passphrase=b"parola", allow_without_timestamp=True)
    assert service.validate_all(doc)[0]["status"] == STATUS_VALID


# --- G-041, G-043 -----------------------------------------------------------------------------


def test_T_G041_expired_certificate_is_valid_but_expired(ctx, doc, tmp_path):
    store = CertificateStore(ctx.settings)
    cert_id = store.add(pkcs12(tmp_path, days=-1, start_days=-30), b"parola")
    service = SignatureService(store, texts)
    service.sign(doc, SignatureOptions(cert_id, 1, BOX), passphrase=b"parola")
    assert service.validate_all(doc)[0]["status"] == STATUS_EXPIRED


def test_T_G043_remove_signature_needs_the_matching_certificate(service, doc):
    service.sign(doc, options(service), passphrase=b"parola")
    stranger = SignatureService(CertificateStore(EmptySettings()), texts)
    with pytest.raises(CertificateNotOwnedError):
        stranger.delete_signature(doc, "Semnatura1")
    service.delete_signature(doc, "Semnatura1")
    with pikepdf.open(io.BytesIO(doc._snapshot()[0])) as pdf:
        assert not [a for a in pdf.pages[0].obj.get("/Annots", [])
                    if a.get("/Subtype") == "/Widget"]
        assert len(pdf.Root.AcroForm.Fields) == 0
    assert doc.is_modified
