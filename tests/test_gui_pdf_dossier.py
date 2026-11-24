"""Dosarul cu semnaturile pastrate, in interfata (faza 8, pasul 8.6): E-500,
E-505, E-506, E-509…E-512."""

from __future__ import annotations

import os

import pikepdf
import pytest
from test_pdf_dossier import pkcs12, sign
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialogButtonBox

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.pdf.dossier import MARK, SEAL_FIELD, manifest
from app.core.pdf.signatures import STATUS_VALID, validate_bytes
from app.gui.convert_screen import ConvertScreen
from app.gui.dossier_dialog import DossierDialog, make_dossier
from app.gui.pdf_editor import PdfEditorWindow


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    yield c
    c.close()


@pytest.fixture
def files(tmp_path):
    a = sign(text_pdf(tmp_path / "a.pdf", [["Contract"]]), tmp_path / "contract.pdf")
    b = text_pdf(tmp_path / "anexa.pdf", [["Anexa"]])
    return [a, b]


def fill_dialog(dialog, folder, name="Dosar"):
    dialog.folder.setText(str(folder))
    dialog.name.setText(name)


# --- E-500, E-505, E-506, E-510: dialogul ------------------------------------------------


def test_T_E500_dossier_dialog(qtbot, files, tmp_path):
    dialog = DossierDialog(files[:1])
    qtbot.addWidget(dialog)
    ok = dialog.box.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()  # minimum doua fisiere
    dialog.add_file(files[1])
    assert ok.isEnabled() and dialog.folder.text() == str(tmp_path)
    dialog.list.item(1).setSelected(True)
    dialog.move(-1)  # ordinea listei, ca la A-023
    assert dialog.files() == [files[1], files[0]]
    assert dialog.target() == tmp_path / "Dosar.pdf"
    dialog.seal.setChecked(True)  # E-506: cere certificatul
    assert not ok.isEnabled()
    dialog.seal.setChecked(False)
    dialog.format.setCurrentIndex(dialog.format.findData("asice"))  # E-510
    assert dialog.target().suffix == ".asice"
    assert not dialog.portfolio.isEnabled() and not dialog.seal.isEnabled()


def test_T_E506_sealed_dossier_from_the_dialog(qtbot, ctx, files, tmp_path):
    dialog = DossierDialog(files)
    qtbot.addWidget(dialog)
    fill_dialog(dialog, tmp_path / "iesire")
    dialog.portfolio.setChecked(True)  # E-505
    dialog.seal.setChecked(True)
    dialog.certificate.setText(str(pkcs12(tmp_path)))
    dialog.passphrase.setText("parola")
    messages = []
    path = make_dossier(dialog, ctx, None, show=messages.append)
    assert path == tmp_path / "iesire" / "Dosar.pdf" and messages == []
    [seal] = validate_bytes(path.read_bytes())
    assert (seal.field_name, seal.status) == (SEAL_FIELD, STATUS_VALID)
    with pikepdf.open(path) as pdf:
        assert len(pdf.pages) == 1  # portofoliu: doar cuprinsul


def test_T_E506_wrong_password_keeps_the_dossier_unsigned(qtbot, ctx, files, tmp_path):
    dialog = DossierDialog(files)
    qtbot.addWidget(dialog)
    fill_dialog(dialog, tmp_path)
    dialog.seal.setChecked(True)
    dialog.certificate.setText(str(pkcs12(tmp_path)))
    dialog.passphrase.setText("gresita")
    messages = []
    path = make_dossier(dialog, ctx, None, show=messages.append)
    assert path.exists() and validate_bytes(path.read_bytes()) == []
    assert messages and "nesemnat" in messages[0]


# --- E-500, E-509 in Lansator ---------------------------------------------------------------


@pytest.fixture
def screen(qtbot, ctx, files):
    s = ConvertScreen(ctx, "pdf", files)
    qtbot.addWidget(s)
    return s


def test_T_E509_launcher_warns_before_a_classic_merge(screen, files, tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(ConvertScreen, "ask_signed_merge",
                        lambda self, found: asked.append(found) or "cancel")
    screen.combine.setChecked(True)
    assert screen.start((tmp_path, "unit")) is None
    assert [p.name for p in asked[0]] == ["contract.pdf"]
    assert not (tmp_path / "unit.pdf").exists()  # anulat: nimic scris


def test_T_E500_launcher_offers_the_dossier(screen, files, tmp_path, monkeypatch):
    created = []
    screen.dossier_created.connect(created.append)
    assert screen.dossier_button.isEnabled()
    monkeypatch.setattr(ConvertScreen, "ask_signed_merge", lambda self, found: "dossier")

    def run(self, dialog):
        fill_dialog(dialog, tmp_path / "iesire")
        return True
    monkeypatch.setattr(ConvertScreen, "exec_dialog", run)
    screen.combine.setChecked(True)
    assert screen.start((tmp_path, "unit")) is None
    assert created == [tmp_path / "iesire" / "Dosar.pdf"]
    assert manifest(created[0].read_bytes()) is not None


# --- E-509, E-511, E-512 in PDF Editor ------------------------------------------------------


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w.open_path(text_pdf(tmp_path / "dosar.pdf", [[f"Pagina {n}"] for n in range(1, 4)]))
    yield w
    w.close()


def answer(monkeypatch, fill):
    def run(self, dialog):
        fill(dialog)
        return True
    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", run)


def test_T_E509_pdf_editor_warns_before_inserting_signed_pages(window, files, monkeypatch):
    asked = []
    monkeypatch.setattr(PdfEditorWindow, "ask_signed_merge",
                        lambda self, found: asked.append(found) or "cancel")
    answer(monkeypatch, lambda dialog: dialog.path.setText(str(files[0])))
    assert window.add_pages_from_pdf() == 0
    assert [p.name for p in asked[0]] == ["contract.pdf"]
    assert window.current().document.page_count == 3
    monkeypatch.setattr(PdfEditorWindow, "ask_signed_merge", lambda self, found: "continue")
    assert window.add_pages_from_pdf() == 1  # `Continua oricum`


def test_T_E500_E512_dossier_from_pdf_editor_opens_with_info_bar(window, files, tmp_path,
                                                                 monkeypatch):
    answer(monkeypatch, lambda dialog: fill_dialog(dialog, tmp_path / "iesire"))
    path = window.signed_merge(files)
    assert path == tmp_path / "iesire" / "Dosar.pdf"
    assert window.current().document.path == path and window.tabs.count() == 2
    assert window.dossier_bar.isVisible()  # E-512
    assert "2 documente" in window.dossier_label.text()
    window.show_message = lambda text: None
    lines = window.verify_dossier()
    assert lines[0].startswith("contract.pdf: identic") and "validă" in lines[0]
    window.tabs.setCurrentIndex(0)  # documentul obisnuit: fara bara
    assert not window.dossier_bar.isVisible()


def test_T_E511_saving_an_attachment_from_a_dossier_checks_it(window, files, tmp_path,
                                                             monkeypatch):
    answer(monkeypatch, lambda dialog: fill_dialog(dialog, tmp_path / "iesire"))
    path = window.signed_merge(files)
    target = tmp_path / "salvat.pdf"
    monkeypatch.setattr(PdfEditorWindow, "ask_attachment_target", lambda self, name: target)
    assert window.save_attachment("contract.pdf") == target
    assert target.read_bytes() == files[0].read_bytes()
    window.close_current()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.Root[MARK].Files[0].SHA256 = pikepdf.String("0" * 64)
        pdf.save(path)
    window.open_path(path)
    messages = []
    window.show_message = messages.append
    target.unlink()
    assert window.save_attachment("contract.pdf") is None
    assert messages and not target.exists()


# E-502 / E-512: bara dosarului numara semnatura cu certificat expirat dupa
# semnare ca valida, la fel ca pagina de cuprins. Gasit pe doua documente reale
# semnate in 2024: bara spunea „0 cu semnaturi valide”, cuprinsul „valida”.
def test_e512_bar_counts_expired_certificate_as_valid(qtbot, monkeypatch) -> None:
    from app.core.pdf.signatures import STATUS_EXPIRED, STATUS_VALID, SignatureInfo
    from app.gui.pdf_editor import PdfEditorWindow

    window = PdfEditorWindow.__new__(PdfEditorWindow)
    from PySide6.QtWidgets import QFrame, QLabel
    window.dossier_bar, window.dossier_label = QFrame(), QLabel()
    report = [("a.pdf", True, [SignatureInfo("A", STATUS_EXPIRED)]),
              ("b.pdf", True, [SignatureInfo("B", STATUS_VALID)])]
    monkeypatch.setattr(window, "_dossier_report", lambda: report, raising=False)
    window._update_dossier_bar()
    text = window.dossier_label.text()
    assert "2 cu semnături valide" in text and "1 cu certificatul expirat" in text
