"""Dialogurile tabului `Security` din PDF Editor (faza 10, pasul 10.4):
`Password Security` (G-001…G-012), `Delete Objects and Data` (G-111),
`Add Digital Signature` (G-030…G-040, G-104…G-106).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.i18n import tr
from app.gui.pdf_content import dialog_buttons

EDITING = ("none", "pages", "forms", "comments", "all")
"""G-007: nimic; inserare, stergere, rotire de pagini; completarea formularelor si
semnarea; plus comentariile; orice in afara de extragerea paginilor."""
REASON_KEYS = ("author", "agree", "inspected", "approved", "integrity")
"""G-104: cele cinci motive predefinite (textele, in traduceri)."""


class PasswordDialog(QDialog):
    """G-001…G-011: `Security Settings`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("password_dialog")
        self.setWindowTitle(tr("security.title"))
        self.use_open = QCheckBox(tr("security.open"))  # G-002
        self.use_open.setObjectName("security_use_open")
        self.open = QLineEdit()
        self.open.setObjectName("security_open_password")
        self.open_again = QLineEdit()
        self.open_again.setObjectName("security_open_again")
        self.hide = QCheckBox(tr("security.hide"))  # G-003
        self.hide.setObjectName("security_hide")
        self.hide.setChecked(True)
        self.use_permissions = QCheckBox(tr("security.permissions"))  # G-004
        self.use_permissions.setObjectName("security_use_permissions")
        self.permissions = QLineEdit()
        self.permissions.setObjectName("security_permissions_password")
        self.permissions_again = QLineEdit()
        self.permissions_again.setObjectName("security_permissions_again")
        self.printing = QComboBox()  # G-006
        self.printing.setObjectName("security_printing")
        for key in ("none", "low", "high"):
            self.printing.addItem(tr(f"security.print.{key}"), key)
        self.printing.setCurrentIndex(2)
        self.editing = QComboBox()  # G-007
        self.editing.setObjectName("security_editing")
        for key in EDITING:
            self.editing.addItem(tr(f"security.edit.{key}"), key)
        self.editing.setCurrentIndex(len(EDITING) - 1)
        self.copying = QCheckBox(tr("security.copying"))  # G-008
        self.copying.setObjectName("security_copying")
        self.copying.setChecked(True)
        self.readers = QCheckBox(tr("security.readers"))  # G-009
        self.readers.setObjectName("security_readers")
        self.readers.setChecked(True)
        self.encryption = QComboBox()  # G-010
        self.encryption.setObjectName("security_encryption")
        self.encryption.addItem(tr("security.aes128"), "aes128")
        self.encryption.addItem(tr("security.aes256"), "aes256")
        self.encryption.setCurrentIndex(1)
        self.scope = QComboBox()  # G-011
        self.scope.setObjectName("security_scope")
        self.scope.addItem(tr("security.scope.all"), True)
        self.scope.addItem(tr("security.scope.except_metadata"), False)
        self.hide.toggled.connect(self._echo)
        for box in (self.use_open, self.use_permissions):
            box.toggled.connect(lambda _on: self._enable())
        open_box = QGroupBox()
        open_form = QFormLayout(open_box)
        open_form.addRow(self.use_open)
        open_form.addRow(tr("security.password"), self.open)
        open_form.addRow(tr("security.confirm"), self.open_again)
        perm_box = QGroupBox()
        perm_form = QFormLayout(perm_box)
        perm_form.addRow(self.use_permissions)
        perm_form.addRow(tr("security.password"), self.permissions)
        perm_form.addRow(tr("security.confirm"), self.permissions_again)
        perm_form.addRow(tr("security.printing"), self.printing)
        perm_form.addRow(tr("security.editing"), self.editing)
        perm_form.addRow(self.copying)
        perm_form.addRow(self.readers)
        form = QFormLayout()
        form.addRow(tr("security.encrypt"), self.encryption)
        form.addRow(tr("security.scope"), self.scope)
        column = QVBoxLayout(self)
        column.addWidget(open_box)
        column.addWidget(self.hide)
        column.addWidget(perm_box)
        column.addLayout(form)
        column.addWidget(dialog_buttons(self, "organize.ok"))
        self._echo(True)
        self._enable()

    def _echo(self, hidden: bool) -> None:
        """G-003: caracterele tastate se pot arata."""
        mode = QLineEdit.EchoMode.Password if hidden else QLineEdit.EchoMode.Normal
        for edit in (self.open, self.open_again, self.permissions, self.permissions_again):
            edit.setEchoMode(mode)

    def _enable(self) -> None:
        for edit in (self.open, self.open_again):
            edit.setEnabled(self.use_open.isChecked())
        for widget in (self.permissions, self.permissions_again, self.printing, self.editing,
                       self.copying, self.readers):
            widget.setEnabled(self.use_permissions.isChecked())

    def options(self) -> Any:
        """`SecurityOptions`. Parole care nu coincid cu confirmarea → `ValueError`
        (G-002); parole identice → `SamePasswordError` (G-004)."""
        from app.core.model import EncryptionLevel, PrintPermission
        from app.core.pdf.security import SecurityOptions

        use_open, use_perm = self.use_open.isChecked(), self.use_permissions.isChecked()
        if use_open and self.open.text() != self.open_again.text():
            raise ValueError("open")
        if use_perm and self.permissions.text() != self.permissions_again.text():
            raise ValueError("permissions")
        editing = str(self.editing.currentData())
        options = SecurityOptions(
            open_password=self.open.text() if use_open else None,
            permissions_password=self.permissions.text() if use_perm else None,
            print_permission=PrintPermission(self.printing.currentData()),
            allow_assembly=editing in ("pages", "all"),
            allow_form_filling=editing in ("forms", "comments", "all"),
            allow_annotations=editing in ("comments", "all"),
            allow_editing=editing == "all", allow_copying=self.copying.isChecked(),
            allow_screen_readers=self.readers.isChecked(),
            encryption=EncryptionLevel(self.encryption.currentData()),
            encrypt_metadata=bool(self.scope.currentData()))
        options.validate()
        return options


class DeleteObjectsDialog(QDialog):
    """G-111: sase bife, `Apply` si `Cancel`."""

    KEYS = ("hidden_text_and_objects", "comments_and_markup",
            "links_media_actions_scripts_form_data", "bookmarks", "attachments", "metadata")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("delete_objects_dialog")
        self.setWindowTitle(tr("security.delete.title"))
        self.boxes: dict[str, QCheckBox] = {}
        column = QVBoxLayout(self)
        for key in self.KEYS:
            box = QCheckBox(tr(f"security.delete.{key}"))
            box.setObjectName(f"delete_{key}")
            column.addWidget(box)
            self.boxes[key] = box
        self.warning = QLabel(tr("security.delete.image_only"))  # G-024
        self.warning.setObjectName("delete_warning")
        self.warning.setStyleSheet("color: #b45309;")
        self.warning.setVisible(False)
        self.boxes["hidden_text_and_objects"].toggled.connect(self.warning.setVisible)
        column.addWidget(self.warning)
        column.addWidget(dialog_buttons(self, "security.apply"))

    def choices(self) -> dict[str, bool]:
        return {k: b.isChecked() for k, b in self.boxes.items()}


class SignDialog(QDialog):
    """G-030…G-040, G-104…G-106: `Add Digital Signature`."""

    def __init__(self, service: Any, settings: Any, page: int, rect: Any,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sign_dialog")
        self.setWindowTitle(tr("sign.title"))
        self.service, self.settings, self.page, self.rect = service, settings, page, rect
        self.certificate = QComboBox()  # G-031
        self.certificate.setObjectName("sign_certificate")
        self.add_certificate = QPushButton(tr("sign.add_certificate"))
        self.add_certificate.setObjectName("sign_add_certificate")
        self.show_certificate = QPushButton(tr("sign.show_certificate"))  # G-032
        self.show_certificate.setObjectName("sign_show_certificate")
        self.missing = QLabel(tr("sign.no_certificate"))
        self.missing.setObjectName("sign_missing")
        self.missing.setWordWrap(True)
        self.reason = QComboBox()  # G-033, G-104
        self.reason.setObjectName("sign_reason")
        self.reason.setEditable(True)
        reasons = list(settings.get("signing.reasons") or []) or \
            [tr(f"sign.reason.{k}") for k in REASON_KEYS]
        self.reason.addItems(reasons)
        self.location = QLineEdit()  # G-034
        self.location.setObjectName("sign_location")
        self.contact = QLineEdit()
        self.contact.setObjectName("sign_contact")
        self.flags: dict[str, QCheckBox] = {}
        for key, default in (("reason", True), ("location", False), ("contact", False),
                             ("date", True), ("owner", True), ("app_version", False),
                             ("labels", True), ("borders", True)):  # G-035, G-036, G-038
            box = QCheckBox(tr(f"sign.show.{key}"))
            box.setObjectName(f"sign_show_{key}")
            box.setChecked(default)
            box.toggled.connect(lambda _on: self._preview())
            self.flags[key] = box
        self.image = QLineEdit()  # G-039
        self.image.setObjectName("sign_image")
        pick = QPushButton(tr("sign.select_image"))
        pick.clicked.connect(self._pick_image)
        self.hash = QComboBox()  # G-045
        self.hash.setObjectName("sign_hash")
        self.hash.addItems(["SHA-256", "SHA-384", "SHA-512"])
        self.timestamp = QLineEdit(str(settings.get("signing.timestamp_url") or ""))  # G-037
        self.timestamp.setObjectName("sign_timestamp")
        self.timestamp.setPlaceholderText("https://…")
        self.timestamp_user = QLineEdit(str(settings.get("signing.timestamp_user") or ""))
        self.timestamp_user.setObjectName("sign_timestamp_user")
        self.preview = QLabel()  # G-105
        self.preview.setObjectName("sign_preview")
        self.preview.setStyleSheet("background: #e8eef7; border: 1px solid #9aa4b2;"
                                   " padding: 6px;")
        self.reason.editTextChanged.connect(lambda _t: self._preview())
        self.location.textChanged.connect(lambda _t: self._preview())
        self.contact.textChanged.connect(lambda _t: self._preview())
        cert_row = QHBoxLayout()
        cert_row.addWidget(self.certificate, 1)
        cert_row.addWidget(self.show_certificate)
        cert_row.addWidget(self.add_certificate)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image, 1)
        image_row.addWidget(pick)
        form = QFormLayout()
        form.addRow(tr("sign.sign_as"), cert_row)
        form.addRow(self.missing)
        form.addRow(tr("sign.reason"), self.reason)
        form.addRow(tr("sign.location"), self.location)
        form.addRow(tr("sign.contact"), self.contact)
        form.addRow(tr("sign.image"), image_row)
        form.addRow(tr("sign.hash"), self.hash)
        form.addRow(tr("sign.timestamp"), self.timestamp)
        form.addRow(tr("sign.timestamp_user"), self.timestamp_user)
        flags = QGroupBox(tr("sign.appearance"))
        flag_column = QVBoxLayout(flags)
        for box in self.flags.values():
            flag_column.addWidget(box)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(flags)
        column.addWidget(self.preview)
        self.box = dialog_buttons(self, "sign.save_and_sign")  # G-040
        column.addWidget(self.box)
        self.reload_certificates()

    def reload_certificates(self) -> None:
        self.certificate.clear()
        for cert_id, holder, issuer in self.service.list_certificates():
            self.certificate.addItem(f"{holder} ({issuer})", cert_id)
        has = self.certificate.count() > 0
        self.missing.setVisible(not has)  # G-031: instructiunile
        self.show_certificate.setEnabled(has)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(has)
        self._preview()

    def _pick_image(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, tr("sign.select_image"), "",
                                              "*.png *.jpg *.jpeg *.bmp")
        if name:
            self.image.setText(name)

    def holder(self) -> str:
        text = self.certificate.currentText()
        return text.split(" (")[0] if text else ""

    def options(self) -> Any:
        from app.core.pdf.signing import SignatureOptions

        image = self.image.text().strip()
        return SignatureOptions(
            certificate_id=str(self.certificate.currentData() or ""), page=self.page,
            rect=self.rect, reason=self.reason.currentText().strip() or None,
            location=self.location.text().strip() or None,
            contact=self.contact.text().strip() or None, hash_algorithm=self.hash.currentText(),
            timestamp_url=self.timestamp.text().strip() or None,
            timestamp_user=self.timestamp_user.text().strip() or None,
            show_reason=self.flags["reason"].isChecked(),
            show_location=self.flags["location"].isChecked(),
            show_contact=self.flags["contact"].isChecked(),
            show_date=self.flags["date"].isChecked(), show_owner=self.flags["owner"].isChecked(),
            show_app_version=self.flags["app_version"].isChecked(),
            show_labels=self.flags["labels"].isChecked(),
            borders_and_background=self.flags["borders"].isChecked(),
            image=Path(image) if image else None)

    def _preview(self) -> None:
        """G-105: textul semnaturii, inainte de semnare."""
        from app.core.pdf.signing import appearance_lines

        lines = appearance_lines(self.options(), self.holder() or "…", datetime.now(), tr)
        self.preview.setText("\n".join(lines))


class ManageSignaturesDialog(QDialog):
    """G-054: `Manage Signatures...`: se alege, `Edit...`, `Delete`, `Use`."""

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QListWidget

        super().__init__(parent)
        self.setObjectName("manage_signatures_dialog")
        self.setWindowTitle(tr("sign.manage"))
        self.list = QListWidget()
        self.list.setObjectName("manage_signatures_list")
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        for key in ("edit", "delete", "use"):
            button = QPushButton(tr(f"sign.manage.{key}"))
            button.setObjectName(f"manage_signatures_{key}")
            row.addWidget(button)
            self.buttons[key] = button
        column = QVBoxLayout(self)
        column.addWidget(self.list, 1)
        column.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        column.addWidget(close)
        self.set_names(names)

    def set_names(self, names: list[str]) -> None:
        self.list.clear()
        self.list.addItems(names)
        if names:
            self.list.setCurrentRow(0)

    def current(self) -> str | None:
        item = self.list.currentItem()
        return item.text() if item is not None else None
