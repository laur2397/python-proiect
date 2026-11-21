"""Dialogurile de salvare si trimitere (faza 6b, pasul 6b.6b).

- `SaveDialog` — `Save document as` (Q-100): numele fisierului, `Save as
  type` cu formatele permise de modul de layout (Q-001), bifa `Open document
  after saving` (Q-101), `Options...` catre setarile formatului (Q-102),
  `Create a separate file` (un fisier sau cate unul pe pagina, Q-022).
- `EmailDialog` — `E-mail > Document...` (Q-042, Q-043): toate formatele fara
  HTML si cele trei impartiri; `E-mail > Images...` (Q-044) cu formatul
  imaginii si `Send as multi-page image file`.
- `KindleDialog` — `Send to Amazon Kindle...` (Q-045): adresa contului,
  impartirea, numele fisierului.

Dialogurile doar aduna alegerile; exportul il face nucleul.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.export.send import ALL, BLANK_PAGES, PER_PAGE
from app.core.model import ExportFormat, LayoutMode
from app.gui.i18n import tr

SAVE_FORMATS = ("pdf", "pdf_image", "pdfa", "pdfua", "docx", "rtf", "odt", "xlsx", "csv",
                "pptx", "txt", "html", "epub", "fb2", "djvu")
"""Cheile `format.*` ale butonului de salvare (J-402)."""

SUFFIX = {"pdf_image": "pdf", "pdfa": "pdf", "pdfua": "pdf"}

SPLITS = (ALL, PER_PAGE, BLANK_PAGES)
"""Q-043: cele trei impartiri."""

IMAGE_FORMATS = (ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG)

OPTIONS_TAB = {"pdf_image": "pdf", "pdfa": "pdf", "pdfua": "pdf", "rtf": "docx",
               "odt": "docx", "fb2": "epub"}
"""Q-102: elementul din lista `Document type` (X-419) al fiecarui format."""


def export_format(key: str) -> ExportFormat:
    return ExportFormat.PDF if key == "pdf_image" else ExportFormat(key)


def allowed_formats(mode: LayoutMode) -> list[str]:
    """Q-001: formatele permise de mod; PDF-ul doar-imagine merge oricum (I-033)."""
    allowed = ExportFormat.allowed_for(mode)
    out = []
    for key in SAVE_FORMATS:
        fmt = export_format(key)
        base = ExportFormat.PDF if fmt in (ExportFormat.PDFA, ExportFormat.PDFUA) else fmt
        if key == "pdf_image" or base in allowed:
            out.append(key)
    return out


def _buttons(dialog: QDialog, ok: QDialogButtonBox.StandardButton) -> QDialogButtonBox:
    buttons = QDialogButtonBox(ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


class SaveDialog(QDialog):
    options_requested = Signal(str)
    """Q-102: cheia formatului ales; fereastra deschide Options pe tabul lui."""

    def __init__(self, mode: LayoutMode, name: str, folder: Path, fmt: str = "pdf",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("save_dialog")
        self.setWindowTitle(tr("save.title"))
        self.folder = QLineEdit(str(folder))
        self.folder.setObjectName("save_folder")
        browse = QPushButton(tr("options.browse"))
        browse.clicked.connect(self._browse)
        self.name = QLineEdit(name)
        self.name.setObjectName("save_name")
        self.type = QComboBox()  # Q-100: `Save as type`
        self.type.setObjectName("save_type")
        for key in allowed_formats(mode):
            self.type.addItem(tr(f"format.{key}"), key)
        self.type.setCurrentIndex(max(0, self.type.findData(fmt)))
        self.open_after = QCheckBox(tr("save.open_after"))  # Q-101
        self.open_after.setObjectName("save_open_after")
        self.separate = QComboBox()  # Q-100: `Create a separate file`
        self.separate.setObjectName("save_separate")
        self.separate.addItem(tr("save.single_file"), False)
        self.separate.addItem(tr("save.file_per_page"), True)
        self.options_button = QPushButton(tr("action.options"))  # Q-102
        self.options_button.setObjectName("save_options")
        self.options_button.clicked.connect(
            lambda: self.options_requested.emit(self.format_key))
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        form = QFormLayout()
        form.addRow(tr("save.folder"), folder_row)
        form.addRow(tr("save.file_name"), self.name)
        form.addRow(tr("save.type"), self.type)
        form.addRow(tr("save.separate"), self.separate)
        form.addRow(self.open_after)
        buttons = _buttons(self, QDialogButtonBox.StandardButton.Save)
        buttons.addButton(self.options_button, QDialogButtonBox.ButtonRole.ActionRole)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("save.folder"), self.folder.text())
        if folder:
            self.folder.setText(folder)

    @property
    def format_key(self) -> str:
        return str(self.type.currentData())

    @property
    def target(self) -> Path:
        key = self.format_key
        name = self.name.text().strip() or "document"
        return Path(self.folder.text()) / f"{name}.{SUFFIX.get(key, key)}"

    @property
    def separate_files(self) -> bool:
        return bool(self.separate.currentData())


def _split_combo() -> QComboBox:
    combo = QComboBox()
    combo.setObjectName("split_mode")
    for split in SPLITS:
        combo.addItem(tr(f"send.split.{split}"), split)
    return combo


class EmailDialog(QDialog):
    """Q-042…Q-044: `images=False` documentul (fara HTML), `images=True` imaginile."""

    def __init__(self, *, images: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("email_dialog")
        self.images = images
        self.setWindowTitle(tr("send.email_images" if images else "send.email_document"))
        self.type = QComboBox()
        self.type.setObjectName("email_type")
        form = QFormLayout()
        form.addRow(tr("save.type"), self.type)
        if images:
            for fmt in IMAGE_FORMATS:
                self.type.addItem(fmt.value.upper(), fmt.value)
            self.multipage = QCheckBox(tr("send.multipage"))  # Q-044
            self.multipage.setObjectName("email_multipage")
            form.addRow(self.multipage)
        else:
            for key in SAVE_FORMATS:
                if key != "html":  # Q-042: toate formatele, cu excepția HTML
                    self.type.addItem(tr(f"format.{key}"), key)
            self.split = _split_combo()  # Q-043
            form.addRow(tr("send.split"), self.split)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(_buttons(self, QDialogButtonBox.StandardButton.Ok))

    @property
    def format_key(self) -> str:
        return str(self.type.currentData())


class KindleDialog(QDialog):
    """Q-045: adresa contului Kindle, impartirea, numele fisierului."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("kindle_dialog")
        self.setWindowTitle(tr("send.kindle"))
        self.address = QLineEdit()
        self.address.setObjectName("kindle_address")
        self.address.setPlaceholderText("nume@kindle.com")
        self.split = _split_combo()
        self.name = QLineEdit(name)
        self.name.setObjectName("kindle_name")
        form = QFormLayout()
        form.addRow(tr("send.kindle_address"), self.address)
        form.addRow(tr("send.split"), self.split)
        form.addRow(tr("save.file_name"), self.name)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(_buttons(self, QDialogButtonBox.StandardButton.Ok))
