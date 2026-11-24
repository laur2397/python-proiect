"""Pachetul de depunere (SPEC_11, E-514…E-518): fiecare document semnat ramane
octet cu octet, contrasemnat incremental de reprezentantul legal; semnaturile de
dinainte raman valide si se verifica dupa semnare. Semnaturi reale (pyHanko), cu
certificate de test."""

from __future__ import annotations

import hashlib
import zipfile

import pikepdf
import pytest
from test_pdf_dossier import pkcs12, sign
from test_pdf_navigation import _signer
from test_pdf_search import text_pdf
from test_pdf_signing import BOX, ctx, no_network, texts  # noqa: F401

from app.core.model import Rect
from app.core.pdf import submission
from app.core.pdf.signatures import STATUS_VALID, validate_bytes
from app.core.pdf.signing import CertificateStore, SignatureOptions, SignatureService
from app.core.pdf.submission import (
    ISSUE_LOCKED,
    ISSUE_NOT_LAST,
    ISSUE_REVERTED,
    ISSUE_TOO_BIG,
    ISSUE_UNSIGNED,
    build_pack,
    docmdp_level,
    output_name,
    signer_service_countersign,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certify(source, target, level):
    """Un document certificat (DocMDP) de un tert."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    with source.open("rb") as f:
        out = signers.sign_pdf(IncrementalPdfFileWriter(f), signers.PdfSignatureMetadata(
            field_name="Certificare", certify=True,
            docmdp_permissions=fields.MDPPerm(level)), signer=_signer())
    target.write_bytes(out.getvalue())
    return target


@pytest.fixture
def signed(tmp_path):
    """Doua anexe semnate de terti, ca in dosarele reale."""
    a = sign(text_pdf(tmp_path / "a.pdf", [["Contract de finantare"], ["Anexa"]]),
             tmp_path / "contract.pdf")
    b = sign(text_pdf(tmp_path / "b.pdf", [["Declaratie pe propria raspundere"]]),
             tmp_path / "declaratie.pdf", name="SemnaturaTert")
    return [a, b]


@pytest.fixture
def representative(ctx, tmp_path):  # noqa: F811
    store = CertificateStore(ctx.settings)
    store.add(pkcs12(tmp_path), b"parola")
    service = SignatureService(store, texts)
    [(cert_id, holder, _issuer)] = service.list_certificates()

    def options_for(document):  # semnatura vizibila pe ultima pagina
        return SignatureOptions(certificate_id=cert_id, page=document.page_count,
                                rect=Rect(300, 650, 220, 70),
                                reason="Reprezentant legal")

    return signer_service_countersign(service, options_for, b"parola"), holder.split(" (")[0]


def test_T_E514_copies_are_byte_identical_numbered_and_zipped(tmp_path, signed):
    result = build_pack(signed, tmp_path / "pachet", archive_name="pachet.zip")
    names = [e.output.name for e in result.entries]
    assert names == ["01_contract.pdf", "02_declaratie.pdf"]
    for entry, source in zip(result.entries, signed, strict=True):
        assert sha(entry.output) == sha(source) and not entry.countersigned
        assert [s.status for s in entry.after] == [STATUS_VALID]
    with zipfile.ZipFile(result.archive) as archive:
        assert archive.namelist() == names
    assert output_name(3, 120, signed[0]) == "003_contract.pdf"


def test_T_E515_E516_countersigning_keeps_every_earlier_signature_valid(
        tmp_path, signed, representative, no_network):  # noqa: F811
    countersign, holder = representative
    result = build_pack(signed, tmp_path / "pachet", countersign=countersign,
                        representative=holder)
    assert result.ok
    for entry, source in zip(result.entries, signed, strict=True):
        data = entry.output.read_bytes()
        assert entry.countersigned
        assert data.startswith(source.read_bytes())  # originalul, neatins, la inceput
        statuses = [(s.field_name, s.status) for s in validate_bytes(data)]
        assert statuses[0][1] == STATUS_VALID  # semnatura tertului: tot valida
        assert statuses[-1][1] == STATUS_VALID and len(statuses) == 2  # contrasemnatura
        assert entry.after[-1].signer == holder and ISSUE_NOT_LAST not in entry.issues


def test_T_E516_a_countersignature_that_would_break_a_signature_is_undone(
        tmp_path, signed):
    def rewriting(source, target, visible):  # nu incremental: rescrie fisierul si strica semnatura
        with pikepdf.open(source) as pdf:
            pdf.pages[0].Contents = pdf.make_stream(b"BT /F1 12 Tf 50 50 Td (alt) Tj ET")
            pdf.save(target)

    result = build_pack(signed[:1], tmp_path / "pachet", countersign=rewriting)
    [entry] = result.entries
    assert ISSUE_REVERTED in entry.issues and not entry.countersigned
    assert sha(entry.output) == sha(signed[0])  # ramane originalul, valid
    assert not result.ok
    assert not list((tmp_path / "pachet").glob(".*"))  # nimic temporar ramas


def test_T_E517_certified_no_changes_document_is_not_countersigned(
        tmp_path, representative):
    countersign, _holder = representative
    locked = certify(text_pdf(tmp_path / "c.pdf", [["Certificat"]]), tmp_path / "cert.pdf", 1)
    assert docmdp_level(locked.read_bytes()) == 1
    result = build_pack([locked], tmp_path / "pachet", countersign=countersign)
    [entry] = result.entries
    assert ISSUE_LOCKED in entry.issues and not entry.countersigned
    assert sha(entry.output) == sha(locked)
    assert [s.status for s in validate_bytes(entry.output.read_bytes())] == [STATUS_VALID]


def test_T_E517_certified_form_filling_document_accepts_a_signature(
        tmp_path, representative, no_network):  # noqa: F811
    countersign, _holder = representative
    certified = certify(text_pdf(tmp_path / "c.pdf", [["Certificat"]]),
                        tmp_path / "cert2.pdf", 2)
    assert docmdp_level(certified.read_bytes()) == 2
    result = build_pack([certified], tmp_path / "pachet", countersign=countersign)
    [entry] = result.entries
    assert entry.countersigned, entry.issues
    assert [s.status for s in entry.after] == [STATUS_VALID, STATUS_VALID]


def test_T_E518_preflight_rules(tmp_path, signed):
    plain = text_pdf(tmp_path / "nesemnat.pdf", [["Buget"]])
    result = build_pack([plain, signed[0]], tmp_path / "pachet", max_mb=0.0001,
                        representative="Alt Reprezentant")
    unsigned, big = result.entries
    assert ISSUE_UNSIGNED in unsigned.issues
    assert ISSUE_TOO_BIG in big.issues
    assert ISSUE_NOT_LAST in big.issues  # semnatura tertului e ultima, nu a reprezentantului
    assert docmdp_level(plain.read_bytes()) is None
    assert set(submission.ISSUES) >= {ISSUE_UNSIGNED, ISSUE_TOO_BIG, ISSUE_LOCKED}


def test_T_E519_portfolio_variant_is_a_pdf_collection(tmp_path, signed):
    from app.core.pdf.dossier import build_dossier

    target = tmp_path / "portofoliu.pdf"
    build_dossier(signed, target, texts=texts, reading_copies=False)
    with pikepdf.open(target) as pdf:
        assert pdf.Root.Collection.Type == "/Collection"
        assert str(pdf.Root.Collection.D) == "contract.pdf"  # primul original
        assert set(pdf.attachments) == {"contract.pdf", "declaratie.pdf"}
        for name, source in zip(("contract.pdf", "declaratie.pdf"), signed, strict=True):
            data = pdf.attachments[name].get_file().read_bytes()
            assert data == source.read_bytes()
            assert [s.status for s in validate_bytes(data)] == [STATUS_VALID]
    build_dossier(signed, tmp_path / "dosar.pdf", texts=texts)
    with pikepdf.open(tmp_path / "dosar.pdf") as pdf:
        assert "/Collection" not in pdf.Root  # cu copii de citire: dosar obisnuit


# --- certificatul reprezentantului ca fisier PKCS#12 (dialogul dosarului) ---------------


def test_T_E515_pkcs12_countersign_visible_and_invisible(tmp_path, signed, no_network):  # noqa: F811
    from app.core.pdf.submission import pkcs12_countersign, representative_name

    p12 = pkcs12(tmp_path)
    countersign = pkcs12_countersign(p12, b"parola", stamp_text="Semnat de %(signer)s")
    certified = certify(text_pdf(tmp_path / "c.pdf", [["Certificat"]]),
                        tmp_path / "cert3.pdf", 3)
    holder = representative_name(p12, b"parola")
    assert holder == "Firma de test SRL"
    result = build_pack([*signed, certified], tmp_path / "pachet", countersign=countersign,
                        representative=holder)
    assert result.ok and all(e.countersigned for e in result.entries)
    for entry in result.entries:
        statuses = [s.status for s in validate_bytes(entry.output.read_bytes())]
        assert statuses == [STATUS_VALID, STATUS_VALID]
        assert entry.after[-1].signer == holder
    with pikepdf.open(result.entries[0].output) as pdf:  # vizibila, pe ultima pagina
        widgets = [a for a in pdf.pages[-1].get("/Annots", []) if a.get("/FT") == "/Sig"]
        assert widgets and float(widgets[0].Rect[2]) > 0
    with pikepdf.open(result.entries[2].output) as pdf:  # certificat: invizibila
        assert not [a for p in pdf.pages for a in p.get("/Annots", [])
                    if a.get("/FT") == "/Sig" and float(a.Rect[2]) - float(a.Rect[0]) > 0]


def test_T_E515_expired_representative_certificate_is_refused(tmp_path):
    from app.core.pdf.dossier import CertificateInvalidError
    from app.core.pdf.submission import pkcs12_countersign

    with pytest.raises(CertificateInvalidError):
        pkcs12_countersign(pkcs12(tmp_path, days=-1, start_days=-30), b"parola",
                           stamp_text="x")


def test_T_E514_dialog_builds_the_pack(qtbot, tmp_path, signed, no_network):  # noqa: F811
    pytest.importorskip("PySide6")
    from app.gui.dossier_dialog import DossierDialog, make_dossier
    from app.gui.i18n import tr as tr_

    dialog = DossierDialog(signed)
    qtbot.addWidget(dialog)
    assert dialog.kind() == "pdf"  # E-505: dosarul ramane implicit
    dialog.format.setCurrentIndex(dialog.format.findData("pack"))
    assert dialog.archive.isEnabled() and not dialog.portfolio.isEnabled()
    assert dialog.seal.title() == tr_("submission.countersign")
    dialog.name.setText("Anexe")
    dialog.folder.setText(str(tmp_path))
    dialog.archive.setChecked(True)
    dialog.seal.setChecked(True)
    dialog.certificate.setText(str(pkcs12(tmp_path)))
    dialog.passphrase.setText("parola")
    messages = []
    folder = make_dossier(dialog, None, None, show=messages.append)
    assert folder == tmp_path / "Anexe"
    assert sorted(p.name for p in folder.iterdir()) == [
        "01_contract.pdf", "02_declaratie.pdf", "Anexe.zip"]
    assert "02_declaratie.pdf" in messages[-1]
