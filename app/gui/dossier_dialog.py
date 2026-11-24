"""Unirea pastrand semnaturile, in interfata (faza 8, pasul 8.6): E-500, E-505,
E-506, E-509, E-510.

`DossierDialog` culege lista ordonata de fisiere, numele si folderul, varianta
portofoliu (E-505), formatul (PDF sau ASiC-E, E-510) si, optional, certificatul
pentru sigiliu (E-506). `make_dossier` construieste dosarul cu nucleul.
`ask_signed_merge` e avertismentul de dinaintea unirii clasice (E-509), cu trei
raspunsuri: `dossier`, `continue`, `cancel`.

Il folosesc Lansatorul (langa `Combine all files`, A-024) si PDF Editor
(`Organize Pages`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.gui.i18n import tr, tr_error

FORMATS = ("pdf", "pack", "asice")
"""E-500: PDF-dosarul (implicit, E-505); E-514: pachetul de depunere, cate un PDF
pe document, contrasemnat; E-510: containerul ASiC-E."""


def ask_signed_merge(parent: QWidget | None, found: Mapping[Path, Sequence[Any]]) -> str:
    """E-509: semnaturile care se pierd la unirea clasica si trei optiuni:
    `dossier` (Uneste pastrand semnaturile), `continue`, `cancel`."""
    lines = [f"{Path(path).name}: {', '.join(s.signer or '?' for s in sigs)}"
             for path, sigs in found.items()]
    box = QMessageBox(parent)
    box.setObjectName("signed_merge_warning")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("dossier.warning.title"))
    box.setText(tr("dossier.warning.text"))
    box.setInformativeText("\n".join(lines))
    keep = box.addButton(tr("dossier.action"), QMessageBox.ButtonRole.AcceptRole)
    anyway = box.addButton(tr("dossier.warning.continue"),
                           QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(tr("organize.cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(keep)
    box.exec()
    clicked = box.clickedButton()
    if clicked is keep:
        return "dossier"
    return "continue" if clicked is anyway else "cancel"


class DossierDialog(QDialog):
    """E-500: lista ordonata (ca la A-023), numele si folderul de iesire."""

    def __init__(self, files: Sequence[Path], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dossier_dialog")
        self.setWindowTitle(tr("dossier.action"))
        self.list = QListWidget()
        self.list.setObjectName("dossier_files")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._validate)
        buttons = QVBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, slot in (("add", self.browse_files), ("remove", self.remove),
                          ("up", lambda: self.move(-1)), ("down", lambda: self.move(1))):
            button = QPushButton(tr(f"dossier.files.{key}"))
            button.setObjectName(f"dossier_{key}")
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[key] = button
        buttons.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(self.list, 1)
        row.addLayout(buttons)
        self.name = QLineEdit(tr("dossier.default_name"))
        self.name.setObjectName("dossier_name")
        self.name.textChanged.connect(self._validate)
        self.folder = QLineEdit()
        self.folder.setObjectName("dossier_folder")
        self.folder.textChanged.connect(self._validate)
        browse = QPushButton(tr("organize.browse"))
        browse.clicked.connect(self.browse_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        self.format = QComboBox()
        self.format.setObjectName("dossier_format")
        for key in FORMATS:
            self.format.addItem(tr(f"dossier.format.{key}"), key)
        self.format.currentIndexChanged.connect(self._validate)
        self.portfolio = QCheckBox(tr("dossier.portfolio"))  # E-505: implicit, cu copii
        self.portfolio.setObjectName("dossier_portfolio")
        self.archive = QCheckBox(tr("submission.zip"))  # E-514: si o arhiva ZIP
        self.archive.setObjectName("dossier_pack_zip")
        self.seal = QGroupBox(tr("dossier.seal"))  # E-506, optional
        self.seal.setObjectName("dossier_seal")
        self.seal.setCheckable(True)
        self.seal.setChecked(False)
        self.certificate = QLineEdit()
        self.certificate.setObjectName("dossier_certificate")
        self.certificate.textChanged.connect(self._validate)
        cert_browse = QPushButton(tr("organize.browse"))
        cert_browse.clicked.connect(self.browse_certificate)
        cert_row = QHBoxLayout()
        cert_row.addWidget(self.certificate, 1)
        cert_row.addWidget(cert_browse)
        self.passphrase = QLineEdit()
        self.passphrase.setObjectName("dossier_passphrase")
        self.passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        seal_form = QFormLayout(self.seal)
        seal_form.addRow(tr("dossier.certificate"), cert_row)
        seal_form.addRow(tr("dossier.passphrase"), self.passphrase)
        self.seal.toggled.connect(lambda _on: self._validate())
        note = QLabel(tr("dossier.note"))
        note.setWordWrap(True)
        note.setProperty("muted", True)
        form = QFormLayout()
        form.addRow(tr("dossier.name"), self.name)
        form.addRow(tr("dossier.folder"), folder_row)
        form.addRow(tr("dossier.format"), self.format)
        column = QVBoxLayout(self)
        column.addLayout(row, 1)
        column.addLayout(form)
        column.addWidget(self.portfolio)
        column.addWidget(self.archive)
        column.addWidget(self.seal)
        column.addWidget(note)
        self.box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dossier.create"))
        self.box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("organize.cancel"))
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        column.addWidget(self.box)
        for path in files:
            self.add_file(Path(path))
        if files:
            self.folder.setText(str(Path(files[0]).parent))
        self.resize(560, 520)
        self._validate()

    # --- lista ------------------------------------------------------------------------

    def add_file(self, path: Path) -> None:
        self.list.addItem(str(path))
        self._validate()

    def files(self) -> list[Path]:
        return [Path(self.list.item(r).text()) for r in range(self.list.count())]

    def browse_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, tr("dossier.files.add"))
        for name in names:
            self.add_file(Path(name))

    def remove(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self._validate()

    def move(self, step: int) -> None:
        rows = sorted(self.list.row(i) for i in self.list.selectedItems())
        if not rows or rows[0] + step < 0 or rows[-1] + step >= self.list.count():
            return
        for row in (rows if step < 0 else reversed(rows)):
            item = self.list.takeItem(row)
            self.list.insertItem(row + step, item)
            item.setSelected(True)

    def browse_folder(self) -> None:
        name = QFileDialog.getExistingDirectory(self, tr("dossier.folder"), self.folder.text())
        if name:
            self.folder.setText(name)

    def browse_certificate(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, tr("dossier.certificate"), "",
                                              f"{tr('dossier.certificate')} (*.p12 *.pfx)")
        if name:
            self.certificate.setText(name)

    # --- valorile ---------------------------------------------------------------------

    def kind(self) -> str:
        return str(self.format.currentData())

    def target(self) -> Path:
        name = self.name.text().strip()
        if self.kind() == "pack":  # E-514: un folder cu documentele
            return Path(self.folder.text().strip()) / name
        suffix = ".asice" if self.kind() == "asice" else ".pdf"
        if not name.lower().endswith(suffix):
            name += suffix
        return Path(self.folder.text().strip()) / name

    def _validate(self) -> None:
        selected = bool(self.list.selectedItems())
        for key in ("remove", "up", "down"):
            self.buttons[key].setEnabled(selected)
        pdf = self.kind() == "pdf"
        pack = self.kind() == "pack"
        self.portfolio.setEnabled(pdf)
        self.archive.setEnabled(pack)
        self.seal.setEnabled(pdf or pack)
        self.seal.setTitle(tr("submission.countersign" if pack else "dossier.seal"))
        ok = self.list.count() >= 2 and bool(self.name.text().strip()) and \
            bool(self.folder.text().strip())
        if (pdf or pack) and self.seal.isChecked():
            ok = ok and Path(self.certificate.text().strip()).is_file()
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)


def make_dossier(dialog: DossierDialog, context: Any, parent: QWidget | None, *,
                 password: Any = None, show: Any = None) -> Path | None:
    """Construieste dosarul cerut in `dialog`; mesajele (fisiere sarite,
    certificat nevalid, erori) merg prin `show(text)`. Intoarce fisierul scris."""
    from app.core.pdf import dossier
    from app.gui.progress import run_with_progress

    def say(text: str) -> None:
        if show is not None:
            show(text)
        else:
            QMessageBox.information(parent, tr("dossier.action"), text)

    files, target = dialog.files(), dialog.target()
    if dialog.kind() == "pack":
        return make_pack(dialog, parent, say=say)
    try:
        if dialog.kind() == "asice":  # E-510
            return dossier.export_asice(files, target)
        result = run_with_progress(
            tr("stage.dossier"),
            lambda progress, cancel: dossier.build_dossier(
                files, target, texts=tr, reading_copies=not dialog.portfolio.isChecked(),
                password=password, context=context, progress=progress), parent)
    except CoreError as exc:
        say(tr_error(exc))
        return None
    except (ValueError, OSError):
        say(tr("dossier.failed"))
        return None
    if result.skipped:  # J-050: se raporteaza si se sare
        say(tr("dossier.skipped", files=", ".join(p.name for p, _e in result.skipped)))
    if dialog.seal.isChecked():  # E-506
        try:
            dossier.seal_dossier(target, Path(dialog.certificate.text().strip()),
                                 dialog.passphrase.text().encode() or None)
        except CoreError as exc:
            say(tr_error(exc))
    return target


def make_pack(dialog: DossierDialog, parent: QWidget | None, *,
              say: Any) -> Path | None:
    """E-514…E-518: pachetul de depunere; la final, raportul pe document."""
    from app.core.pdf import submission
    from app.gui.progress import run_with_progress

    files, folder = dialog.files(), dialog.target()
    countersign, representative = None, None
    if dialog.seal.isChecked():
        certificate = Path(dialog.certificate.text().strip())
        secret = dialog.passphrase.text().encode() or None
        try:
            countersign = submission.pkcs12_countersign(
                certificate, secret, stamp_text=tr("submission.stamp"))
        except CoreError as exc:
            say(tr_error(exc))
            return None
        representative = submission.representative_name(certificate, secret)
    archive = f"{folder.name}.zip" if dialog.archive.isChecked() else None
    try:
        result = run_with_progress(
            tr("stage.submission"),
            lambda progress, cancel: submission.build_pack(
                files, folder, countersign=countersign, representative=representative,
                archive_name=archive, progress=progress), parent)
    except CoreError as exc:
        say(tr_error(exc))
        return None
    except (ValueError, OSError):
        say(tr("dossier.failed"))
        return None
    if result is None:
        return None
    say(pack_report(result))
    return folder


def pack_report(result: Any) -> str:
    """E-518: ce s-a facut cu fiecare document si ce trebuie verificat."""
    lines = [tr("submission.done", n=len(result.entries), folder=str(result.folder))]
    for entry in result.entries:
        state = tr("submission.countersigned") if entry.countersigned \
            else tr("submission.copied")
        lines.append(f"• {entry.output.name if entry.output else entry.source.name}: {state}")
        lines += [f"   – {tr(f'submission.issue.{code}')}" for code in entry.issues]
    if result.archive is not None:
        lines.append(tr("submission.archive", file=result.archive.name))
    return "\n".join(lines)
