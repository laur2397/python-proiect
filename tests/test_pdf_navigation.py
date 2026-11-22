"""Navigarea si siguranta in PDF Editor (faza 7, pasul 7.5): semnele de carte,
atasamentele, semnaturile, linkurile, JavaScript-ul (B-021, B-023, B-024,
B-034…B-042)."""

from __future__ import annotations

import datetime as dt
import time

import pikepdf
import pytest
from test_pdf_search import text_pdf

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.pdf import navigation, signatures
from app.core.pdf.document import PdfDocument


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


# --- B-021 ----------------------------------------------------------------------------


def test_T_B021_1_bookmark_tree(tmp_path):
    path = text_pdf(tmp_path / "carte.pdf", [["Capitol 1"], ["Capitol 2"], ["Anexa"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root.clear()
            first = pikepdf.OutlineItem("Capitolul 1", 0)
            first.children.append(pikepdf.OutlineItem(
                "Sectiunea 1.1",
                pikepdf.Array([pdf.pages[1].obj, pikepdf.Name.XYZ, 0, 742, 0])))
            outline.root.append(first)
            outline.root.append(pikepdf.OutlineItem("Fara destinatie"))
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        tree = doc.bookmarks()
    assert [b.title for b in tree] == ["Capitolul 1", "Fara destinatie"]
    assert tree[0].target_page == 1 and tree[0].level == 1
    child = tree[0].children[0]
    assert (child.title, child.level, child.target_page) == ("Sectiunea 1.1", 2, 2)
    assert child.target_y == pytest.approx(100)  # 842 - 742
    assert tree[1].target_page is None
    assert [b.id for b in (tree[0], child, tree[1])] == [1, 2, 3]


def test_T_B021_2_document_without_bookmarks(tmp_path):
    path = tmp_path / "gol.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(path)
    with PdfDocument.open(path) as doc:
        assert doc.bookmarks() == []


# --- B-023, B-034 ---------------------------------------------------------------------


def test_T_B023_1_attachments_listed_and_extracted(tmp_path):
    path = text_pdf(tmp_path / "anexe.pdf", [["Dosar"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.attachments["buget.xlsx"] = pikepdf.AttachedFileSpec(pdf, b"x" * 1234,
                                                                 filename="buget.xlsx")
        pdf.attachments["Instalare.exe"] = pikepdf.AttachedFileSpec(pdf, b"MZ",
                                                                    filename="Instalare.exe")
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        assert doc.attachments() == [("buget.xlsx", 1234, False), ("Instalare.exe", 2, True)]
        doc.extract_attachment("buget.xlsx", tmp_path / "iesire.xlsx")
        (tmp_path / "folder").mkdir()
        doc.extract_attachment("buget.xlsx", tmp_path / "folder")
        with pytest.raises(KeyError):
            doc.extract_attachment("lipsa.pdf", tmp_path)
    assert (tmp_path / "iesire.xlsx").read_bytes() == b"x" * 1234
    assert (tmp_path / "folder" / "buget.xlsx").read_bytes() == b"x" * 1234


# --- B-024 ----------------------------------------------------------------------------


def _signer():
    from asn1crypto import keys as akeys
    from asn1crypto import x509 as ax509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyhanko.sign import signers

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ana Popescu")])
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(7)
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=30))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False,
                                         False, False), critical=True)
            .sign(key, hashes.SHA256()))
    return signers.SimpleSigner(
        signing_cert=ax509.Certificate.load(cert.public_bytes(serialization.Encoding.DER)),
        signing_key=akeys.PrivateKeyInfo.load(key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())),
        cert_registry=None)


def signed_pdf(tmp_path):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    source = text_pdf(tmp_path / "nesemnat.pdf", [["Contract de finantare"]])
    with source.open("rb") as f:
        out = signers.sign_pdf(IncrementalPdfFileWriter(f), signers.PdfSignatureMetadata(
            field_name="Semnatura1", reason="Aprobare", location="Bucuresti"),
            signer=_signer())
    target = tmp_path / "semnat.pdf"
    target.write_bytes(out.getvalue())
    return target


def test_T_B024_1_signature_listed_with_state_offline(tmp_path, monkeypatch):
    import socket

    path = signed_pdf(tmp_path)

    def no_network(*args, **kwargs):
        raise AssertionError("validarea a incercat sa iasa pe retea")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    with PdfDocument.open(path) as doc:
        [info] = signatures.signatures(doc)
    assert info.field_name == "Semnatura1"
    assert info.status == signatures.STATUS_VALID
    assert info.signer == "Ana Popescu"
    assert (info.reason, info.location, info.page) == ("Aprobare", "Bucuresti", 1)
    assert info.trusted is None  # certificat auto-semnat, fara radacini de incredere
    assert info.signed_at and info.signed_at.endswith("Z")


def test_T_B024_2_changed_and_broken_signatures(tmp_path):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    path = signed_pdf(tmp_path)
    data = path.read_bytes()
    out = tmp_path / "modificat.pdf"
    with path.open("rb") as f:  # o modificare dupa semnare, prin actualizare incrementala
        writer = IncrementalPdfFileWriter(f)
        writer.root["/Lang"] = generic.TextStringObject("ro")
        writer.update_root()
        with out.open("wb") as dest:
            writer.write(dest)
    with PdfDocument.open(out) as doc:
        assert signatures.signatures(doc)[0].status == signatures.STATUS_MODIFIED
    broken = tmp_path / "stricat.pdf"
    assert b"Dosar de finantare" in data  # titlul, necomprimat, in zona semnata
    broken.write_bytes(data.replace(b"Dosar de finantare", b"Dosar de finantarX", 1))
    with PdfDocument.open(broken) as doc:
        assert signatures.signatures(doc)[0].status == signatures.STATUS_INVALID


def test_T_B024_3_unsigned_or_unsaved_documents(tmp_path):
    with PdfDocument.open(text_pdf(tmp_path / "x.pdf", [["a"]])) as doc:
        assert signatures.signatures(doc) == []
    with PdfDocument.create_empty() as doc:
        assert signatures.signatures(doc) == []


# --- B-035, B-042 ---------------------------------------------------------------------


def test_T_B035_1_document_links(tmp_path):
    path = text_pdf(tmp_path / "linkuri.pdf", [["Pagina unu"], ["Pagina doi"]])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        web = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[72, 700, 200, 720],
            A=pikepdf.Dictionary(S=pikepdf.Name.URI,
                                 URI=pikepdf.String("https://exemplu.ro"))))
        inner = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[72, 600, 200, 620],
            Dest=pikepdf.Array([pdf.pages[1].obj, pikepdf.Name.Fit])))
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([web, inner]))
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        first, second = navigation.page_links(doc, 1)
    assert first.uri == "https://exemplu.ro" and first.target_page is None
    assert first.rects[0].y == pytest.approx(842 - 720)
    assert second.uri is None and second.target_page == 2


def test_T_B042_1_urls_and_emails_detected_in_text(tmp_path):
    path = text_pdf(tmp_path / "text.pdf", [[
        "Vezi www.exemplu.ro sau https://ghid.exemplu.ro/pas-1.",
        "Scrieti la ana.pop@exemplu.ro, va rog."]])
    with PdfDocument.open(path) as doc:
        links = navigation.detect_links(doc, 1)
    assert [link.uri for link in links] == ["http://www.exemplu.ro",
                                            "https://ghid.exemplu.ro/pas-1",
                                            "mailto:ana.pop@exemplu.ro"]
    assert all(link.detected and link.rects for link in links)
    assert links[0].rects[0].y < links[2].rects[0].y  # al doilea rand e mai jos


# --- B-037…B-041 ----------------------------------------------------------------------


def test_T_B037_1_javascript_is_detected(tmp_path):
    path = text_pdf(tmp_path / "js.pdf", [["Formular"]])
    with PdfDocument.open(path) as doc:
        assert not navigation.has_javascript(doc)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript,
                                                 JS=pikepdf.String("app.alert(1)"))
        pdf.save(path)
    with PdfDocument.open(path) as doc:
        assert navigation.javascript_locations(doc) == ["/OpenAction"]


def test_T_B038_B040_javascript_policy(ctx, tmp_path):
    policy = navigation.ScriptPolicy.from_settings(ctx.settings)
    with PdfDocument.open(text_pdf(tmp_path / "a.pdf", [["a"]])) as a, \
            PdfDocument.open(text_pdf(tmp_path / "b.pdf", [["b"]])) as b:
        assert not policy.allows(a)  # B-040: dezactivat implicit
        policy.enable_for(a)  # B-038: numai pentru documentul acesta
        assert policy.allows(a) and not policy.allows(b)
        policy.forget(a)
        assert not policy.allows(a)
        ctx.settings.set("pdf.enable_javascript", True)  # B-039: pentru toate
        assert navigation.ScriptPolicy.from_settings(ctx.settings).allows(b)


def test_T_B041_1_script_time_limit():
    noted = []

    def slow(code, stop):
        while not stop.is_set():
            time.sleep(0.01)
        return "oprit"

    outcome = navigation.run_script("while(true){}", slow, timeout=0.1,
                                    on_timeout=noted.append)
    assert outcome.ran and outcome.timed_out
    assert noted and noted[0] >= 0.1
    assert navigation.run_script("1+1", lambda code, stop: 2).result == 2
    assert navigation.run_script("x", lambda code, stop: 1 / 0).error
    assert navigation.run_script("x", None) == navigation.ScriptOutcome(False)
