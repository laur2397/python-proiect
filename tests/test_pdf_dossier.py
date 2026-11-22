"""Dosarul care pastreaza semnaturile valide (faza 8, pasul 8.5): E-500…E-512.
Certificatele sunt de test, generate aici; cele calificate reale le verifica
utilizatorul (SPEC_11, „Ce trebuie verificat”)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import socket
import zipfile
from pathlib import Path

import pikepdf
import pytest
from test_pdf_navigation import _signer
from test_pdf_search import text_pdf

from app.core.pdf import dossier
from app.core.pdf.dossier import (
    MARK,
    SEAL_FIELD,
    CertificateInvalidError,
    DossierIntegrityError,
    build_dossier,
    dossier_report,
    export_asice,
    extract_original,
    manifest,
    seal_dossier,
    signed_among,
    verify_dossier,
)
from app.core.pdf.signatures import STATUS_VALID, validate_bytes

CATALOG = json.loads((Path(__file__).resolve().parent.parent / "app/gui/i18n/ro.json")
                     .read_text(encoding="utf-8"))


def texts(key, **params):
    return CATALOG[key].format(**params)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sign(source, target, name="Semnatura1"):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    with source.open("rb") as f:
        out = signers.sign_pdf(IncrementalPdfFileWriter(f),
                               signers.PdfSignatureMetadata(field_name=name),
                               signer=_signer())
    target.write_bytes(out.getvalue())
    return target


@pytest.fixture
def sources(tmp_path):
    a = sign(text_pdf(tmp_path / "a.pdf", [["Contract"], ["Anexa la contract"]]),
             tmp_path / "contract.pdf")
    b = sign(text_pdf(tmp_path / "b.pdf", [["Declaratie"]]), tmp_path / "declaratie.pdf")
    c = text_pdf(tmp_path / "buget.pdf", [["Buget"]])
    d = tmp_path / "nota.txt"
    d.write_text("nota explicativa", encoding="utf-8")
    return [a, b, c, d]


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("dosarul a incercat sa iasa pe retea (E-507)")
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def page_texts(path):
    from app.core.pdf.document import PdfDocument

    with PdfDocument.open(path) as doc:
        return [doc.extract_text(n) for n in range(1, doc.page_count + 1)]


# --- E-500, E-501 (prioritate 1), E-507 ------------------------------------------------


def test_T_E501_originals_are_attached_byte_for_byte_and_stay_valid(tmp_path, sources,
                                                                    no_network):
    before = {p: sha(p.read_bytes()) for p in sources}
    target = tmp_path / "dosar.pdf"
    result = build_dossier(sources, target, texts=texts)
    assert [e.name for e in result.entries] == ["contract.pdf", "declaratie.pdf",
                                                "buget.pdf", "nota.txt"]
    assert {p: sha(p.read_bytes()) for p in sources} == before  # sursele, neatinse
    with pikepdf.open(target) as pdf:
        attached = {n: s.get_file().read_bytes() for n, s in pdf.attachments.items()}
    for path in sources:
        assert sha(attached[path.name]) == before[path]
    for name in ("contract.pdf", "declaratie.pdf"):  # semnaturile raman valide
        [sig] = validate_bytes(attached[name])
        assert sig.status == STATUS_VALID and sig.signer == "Ana Popescu"
    assert verify_dossier(target) == {p.name: True for p in sources}


def test_T_E501_a_different_attachment_cancels_and_writes_nothing(tmp_path, sources,
                                                                  monkeypatch):
    real = dossier._assemble

    def tampered(entries, sources_, copies, **kw):
        sources_["buget.pdf"] = sources_["buget.pdf"] + b"%alterat"
        return real(entries, sources_, copies, **kw)

    monkeypatch.setattr(dossier, "_assemble", tampered)
    target = tmp_path / "dosar.pdf"
    with pytest.raises(DossierIntegrityError) as err:
        build_dossier(sources, target, texts=texts)
    assert err.value.params["name"] == "buget.pdf" and not target.exists()


def test_T_E500_needs_two_files_and_skips_unreadable_ones(tmp_path, sources):
    with pytest.raises(ValueError):
        build_dossier(sources[:1], tmp_path / "x.pdf", texts=texts)
    locked = tmp_path / "parola.pdf"
    with pikepdf.open(sources[2]) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(owner="o", user="u"))
    result = build_dossier([sources[0], locked, sources[2], tmp_path / "lipsa.pdf"],
                           tmp_path / "dosar.pdf", texts=texts)
    assert [e.name for e in result.entries] == ["contract.pdf", "buget.pdf"]
    assert [p.name for p, _err in result.skipped] == ["parola.pdf", "lipsa.pdf"]
    with_password = build_dossier([sources[0], locked], tmp_path / "dosar2.pdf",
                                  texts=texts, password=lambda path: "u")
    assert [e.pages for e in with_password.entries] == [2, 1]


# --- E-502…E-505 ------------------------------------------------------------------------


def test_T_E502_contents_page_with_signature_report_and_links(tmp_path, sources):
    target = tmp_path / "dosar.pdf"
    result = build_dossier(sources, target, texts=texts)
    toc = page_texts(target)[0]
    assert "cuprins" in toc
    for entry in result.entries:
        assert entry.name in toc and entry.sha256 in toc
    assert "Ana Popescu" in toc and "validă" in toc and "Fără semnătură" in toc
    assert "nu se poate verifica offline" in toc  # E-507: increderea, nu semnatura
    with pikepdf.open(target) as pdf:
        actions = [a.A for a in pdf.pages[0].obj.Annots]
        pages = {p.objgen: i for i, p in enumerate(pdf.pages, start=1)}
        goto = [pages[a.D[0].objgen] for a in actions if a.S == "/GoTo"]
        embedded = [str(a.T.N) for a in actions if a.S == "/GoToE"]
    assert goto == [2, 4, 5]
    assert embedded == ["contract.pdf", "declaratie.pdf", "buget.pdf", "nota.txt"]
    assert [e.first_page for e in result.entries] == [2, 4, 5, None]


def test_T_E503_reading_copies_are_labelled_and_have_no_signature_fields(tmp_path, sources):
    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    pages = page_texts(target)
    assert len(pages) == 5  # cuprins + 2 + 1 + 1
    for text in pages[1:]:
        assert "Copie de citire" in text and "originalul semnat este atașat" in text
    assert "Contract" in pages[1] and "Declaratie" in pages[3] and "Buget" in pages[4]
    with pikepdf.open(target) as pdf:
        for page in pdf.pages[1:]:
            for annot in page.obj.get("/Annots", []):
                assert annot.get("/Subtype") != "/Widget"
    assert validate_bytes(target.read_bytes()) == []  # nicio semnatura care sa para valida


def test_T_E504_one_level_one_bookmark_per_document(tmp_path, sources):
    from app.core.pdf.document import PdfDocument

    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    with PdfDocument.open(target) as doc:
        marks = doc.bookmarks()
    assert [(m.title, m.level, m.target_page) for m in marks] == [
        ("contract.pdf", 1, 2), ("declaratie.pdf", 1, 4), ("buget.pdf", 1, 5)]


def test_T_E505_portfolio_without_reading_copies(tmp_path, sources):
    target = tmp_path / "portofoliu.pdf"
    result = build_dossier(sources, target, texts=texts, reading_copies=False)
    assert len(page_texts(target)) == 1
    assert all(e.first_page is None for e in result.entries)
    assert verify_dossier(target) == {p.name: True for p in sources}


def test_images_get_a_reading_copy(tmp_path, sources):
    from PIL import Image

    from app.core.context import AppContext
    from app.core.paths import AppPaths

    image = tmp_path / "chitanta.png"
    Image.new("RGB", (600, 800), "white").save(image)
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    try:
        result = build_dossier([sources[0], image], tmp_path / "d.pdf", texts=texts,
                               context=ctx)
    finally:
        ctx.close()
    assert [e.pages for e in result.entries] == [2, 1]


# --- E-506 (prioritate 1) ------------------------------------------------------------------


def pkcs12(tmp_path, *, days=30, start_days=-1):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import (
        BestAvailableEncryption,
        pkcs12,
    )
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Firma de test SRL")])
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(11)
            .not_valid_before(now + dt.timedelta(days=start_days))
            .not_valid_after(now + dt.timedelta(days=days))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False,
                                         False, False), critical=True)
            .sign(key, hashes.SHA256()))
    path = tmp_path / f"cert{days}.p12"
    path.write_bytes(pkcs12.serialize_key_and_certificates(
        b"test", key, cert, None, BestAvailableEncryption(b"parola")))
    return path


def test_T_E506_sealing_keeps_every_signature_valid(tmp_path, sources, no_network):
    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    seal_dossier(target, pkcs12(tmp_path), b"parola")
    sigs = validate_bytes(target.read_bytes())
    assert [(s.field_name, s.status) for s in sigs] == [(SEAL_FIELD, STATUS_VALID)]
    assert verify_dossier(target) == {p.name: True for p in sources}
    report = {name: (ok, [s.status for s in sigs]) for name, ok, sigs in dossier_report(target)}
    assert report["contract.pdf"] == (True, [STATUS_VALID])
    assert report["declaratie.pdf"] == (True, [STATUS_VALID])


def test_T_E506_expired_certificate_leaves_the_dossier_unsigned(tmp_path, sources):
    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    before = target.read_bytes()
    with pytest.raises(CertificateInvalidError):
        seal_dossier(target, pkcs12(tmp_path, days=-1, start_days=-30), b"parola")
    with pytest.raises(CertificateInvalidError):
        seal_dossier(target, pkcs12(tmp_path, days=40), b"gresita")
    assert target.read_bytes() == before


# --- E-509 (prioritate 1) ------------------------------------------------------------------


def test_T_E509_signed_files_are_found_before_a_classic_merge(sources):
    found = signed_among(sources)
    assert sorted(p.name for p in found) == ["contract.pdf", "declaratie.pdf"]
    assert found[sources[0]][0].signer == "Ana Popescu"


# --- E-510, E-511, E-512 -------------------------------------------------------------------


def test_T_E510_asice_container(tmp_path, sources):
    target = export_asice(sources[:2], tmp_path / "dosar.asice")
    with zipfile.ZipFile(target) as archive:
        first = archive.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/vnd.etsi.asic-e+zip"
        manifest_xml = archive.read("META-INF/manifest.xml").decode()
        for path in sources[:2]:
            assert archive.read(path.name) == path.read_bytes()
            assert f'full-path="{path.name}"' in manifest_xml


def test_T_E511_extracting_an_original_checks_its_fingerprint(tmp_path, sources):
    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    out = tmp_path / "extrase"
    out.mkdir()
    saved = extract_original(target, "contract.pdf", out)
    assert saved.read_bytes() == sources[0].read_bytes()
    [sig] = validate_bytes(saved.read_bytes())
    assert sig.status == STATUS_VALID
    with pikepdf.open(target, allow_overwriting_input=True) as pdf:  # amprenta schimbata
        pdf.Root[MARK].Files[1].SHA256 = pikepdf.String("0" * 64)
        pdf.save(target)
    with pytest.raises(DossierIntegrityError):
        extract_original(target, "declaratie.pdf", out / "d.pdf")
    assert not (out / "d.pdf").exists()


def test_T_E512_a_dossier_is_recognized(tmp_path, sources):
    target = tmp_path / "dosar.pdf"
    build_dossier(sources, target, texts=texts)
    assert [f["name"] for f in manifest(target.read_bytes())] == [p.name for p in sources]
    assert manifest(sources[2].read_bytes()) is None
    assert dossier_report(sources[2]) == []
    report = dossier_report(target)
    assert [(n, ok) for n, ok, _s in report] == [(p.name, True) for p in sources]


# E-502: certificatul expirat dupa semnare. Gasit la testul cu doua documente
# reale semnate in 2024 (CertDigital), al caror certificat a expirat intre timp:
# `DossierEntry.status` arunca StopIteration si oprea raportul.
def test_e502_status_with_expired_certificate() -> None:
    from app.core.pdf.dossier import STATUSES, DossierEntry
    from app.core.pdf.signatures import (
        STATUS_EXPIRED,
        STATUS_MODIFIED,
        STATUS_VALID,
        SignatureInfo,
    )

    def entry(*states: str) -> DossierEntry:
        return DossierEntry(Path("a.pdf"), "a.pdf", "0" * 64, 1,
                            [SignatureInfo(f"S{i}", s) for i, s in enumerate(states)])

    assert STATUS_EXPIRED in STATUSES
    assert entry(STATUS_EXPIRED).status == STATUS_EXPIRED
    assert entry(STATUS_VALID, STATUS_EXPIRED).status == STATUS_EXPIRED
    assert entry(STATUS_EXPIRED, STATUS_MODIFIED).status == STATUS_MODIFIED
    assert entry("stare_necunoscuta").status == "unverifiable"


def sign_visible(source, target, box=(300, 100, 520, 170)):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    with source.open("rb") as f:
        writer = IncrementalPdfFileWriter(f)
        fields.append_signature_field(
            writer, fields.SigFieldSpec("SemnaturaVizibila", on_page=0, box=box))
        out = signers.sign_pdf(writer, signers.PdfSignatureMetadata(
            field_name="SemnaturaVizibila"), signer=_signer())
    target.write_bytes(out.getvalue())
    return target


# E-513: semnatura vizibila ramane desenata pe copia de citire, fara camp de
# semnatura, cu un link care deschide originalul atasat (GoToE).
def test_e513_visible_signature_links_to_original(tmp_path, no_network):
    from app.core.pdf.dossier import build_dossier
    from app.core.pdf.signatures import validate_bytes

    a = sign_visible(text_pdf(tmp_path / "a.pdf", [["Contract"]]), tmp_path / "contract.pdf")
    b = sign(text_pdf(tmp_path / "b.pdf", [["Declaratie"]]), tmp_path / "declaratie.pdf")
    result = build_dossier([a, b], tmp_path / "dosar.pdf", texts=texts)
    contract, declaratie = result.entries
    with pikepdf.open(tmp_path / "dosar.pdf") as pdf:
        page = pdf.pages[contract.first_page - 1]
        annots = list(page.obj.get("/Annots", []))
        assert not any(a.get("/FT") == "/Sig" or "/Parent" in a for a in annots
                       if a.get("/Subtype") == "/Widget")
        links = [a for a in annots if a.get("/Subtype") == "/Link"
                 and a.A.get("/S") == "/GoToE"]
        assert len(links) == 1
        link = links[0]
        assert str(link.A.T.N) == "contract.pdf" and bool(link.A.NewWindow)
        assert [round(float(v)) for v in link.Rect] == [300, 100, 520, 170]
        assert str(link.Contents) == texts("dossier.signature_link")
        drawn = b"".join(c.read_bytes() for c in (
            page.obj.Contents if isinstance(page.obj.Contents, pikepdf.Array)
            else [page.obj.Contents]))
        assert b"/DLSig" in drawn
        # semnatura invizibila a declaratiei nu primeste link
        other = pdf.pages[declaratie.first_page - 1]
        assert not [a for a in other.obj.get("/Annots", [])
                    if a.get("/Subtype") == "/Link" and a.A.get("/S") == "/GoToE"]
        original = pdf.attachments["contract.pdf"].get_file().read_bytes()
    assert original == a.read_bytes()
    assert validate_bytes(original)[0].status in ("valid", "valid_expired", "unverifiable")
