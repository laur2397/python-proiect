"""Dialogurile de stampila din PDF Editor (faza 7, pasul 7.9c): D-045…D-050,
D-107…D-110, Z-013.

- `ImageStampDialog` (D-047, D-108): numele, `Open` si `Paste from Clipboard`,
  sliderul de dimensiune, `Save`;
- `TextStampDialog` (D-048, D-109, D-110): numele, textul, combo-ul `Add
  Date/Time` (eticheta intra la pozitia cursorului), marimea si culoarea
  textului, `Add border`, previzualizarea (Z-013), `Save`;
- `ManageStampsDialog` (D-050): lista, `Edit...`, `Use`, `Delete...`.

Biblioteca e in nucleu (`app/core/pdf/stamps.py`); dialogurile doar o editeaza.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.pdf.stamps import BORDERS, Stamp, StampLibrary, stamp_text
from app.gui.i18n import tr, tr_error

DATE_TAGS = ("<d/>", "<date/>", "<t12/>", "<t24/>", "<time/>")
"""D-049, Z-001…Z-005: elementele combo-ului `Add Date/Time`."""


def stamp_label(stamp: Stamp) -> str:
    """Numele afisat: cele livrate se traduc, cele proprii raman cum le-a numit
    utilizatorul."""
    return tr(f"stamp.{stamp.name}") if stamp.is_builtin else stamp.name


def image_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


class ImageStampDialog(QDialog):
    """D-047, D-108."""

    def __init__(self, parent: QWidget | None = None, *, name: str = "",
                 image: bytes | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_stamp_dialog")
        self.setWindowTitle(tr("stamps.image.title"))
        self.image: bytes | None = image
        self.name = QLineEdit(name)
        self.name.setObjectName("stamp_name")
        open_button = QPushButton(tr("stamps.image.open"))
        open_button.setObjectName("stamp_open")
        open_button.clicked.connect(lambda: self.open_file())
        paste = QPushButton(tr("stamps.image.paste"))
        paste.setObjectName("stamp_paste")
        paste.clicked.connect(self.paste)
        self.slider = QSlider(Qt.Orientation.Horizontal)  # marimea stampilei
        self.slider.setObjectName("stamp_size")
        self.slider.setRange(10, 400)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self._update_preview)
        self.preview = QLabel()
        self.preview.setObjectName("stamp_preview")
        self.preview.setMinimumSize(200, 120)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(tr("stamps.name"), self.name)
        row = QHBoxLayout()
        row.addWidget(open_button)
        row.addWidget(paste)
        form.addRow(row)
        form.addRow(tr("stamps.image.size"), self.slider)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview, 1)
        layout.addWidget(buttons)
        self.name.textChanged.connect(self._update_state)
        self._update_preview()

    @property
    def scale(self) -> float:
        return self.slider.value() / 100

    def open_file(self, path: str | None = None) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, tr("stamps.image.open"), "",
                                                  tr("stamps.image.filter"))
        if path:
            with open(path, "rb") as fh:
                self.set_image(fh.read())

    def paste(self) -> None:
        """`Paste from Clipboard`."""
        image = QApplication.clipboard().image()
        if not image.isNull():
            self.set_image(image_bytes(image))

    def set_image(self, data: bytes) -> None:
        self.image = data
        self._update_preview()

    def _update_preview(self) -> None:
        image = QImage.fromData(self.image) if self.image else QImage()
        if not image.isNull():
            scaled = image.scaled(max(1, int(image.width() * self.scale)),
                                  max(1, int(image.height() * self.scale)),
                                  Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(QPixmap.fromImage(scaled).scaled(
                self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self._update_state()

    def _update_state(self) -> None:
        self.save_button.setEnabled(bool(self.name.text().strip() and self.image))


class TextStampDialog(QDialog):
    """D-048, D-109, D-110, Z-013."""

    def __init__(self, parent: QWidget | None = None, *, stamp: Stamp | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("text_stamp_dialog")
        self.setWindowTitle(tr("stamps.text.title"))
        self.color = (stamp.text_color if stamp else None) or "#B42318"
        self.name = QLineEdit(stamp.name if stamp else "")
        self.name.setObjectName("stamp_name")
        self.text = QPlainTextEdit(stamp.text if stamp and stamp.text else "")
        self.text.setObjectName("stamp_text")
        self.text.setFixedHeight(80)
        self.date_combo = QComboBox()  # D-109: `Add Date/Time`
        self.date_combo.setObjectName("stamp_add_date")
        self.date_combo.addItem(tr("stamps.text.add_date"), "")
        for tag in DATE_TAGS:
            self.date_combo.addItem(tr(f"stamps.tag.{tag.strip('<>/')}"), tag)
        self.date_combo.activated.connect(self.insert_tag)
        self.size = QSpinBox()
        self.size.setObjectName("stamp_font_size")
        self.size.setRange(6, 72)
        self.size.setValue(int(stamp.font_size) if stamp and stamp.font_size else 18)
        self.color_button = QPushButton(tr("style.text_color"))
        self.color_button.setObjectName("stamp_color")
        self.color_button.clicked.connect(self.choose_color)
        self.border = QCheckBox(tr("stamps.text.border"))  # `Add border`
        self.border.setObjectName("stamp_border")
        self.border_style = QComboBox()
        self.border_style.setObjectName("stamp_border_style")
        for style in BORDERS[1:]:
            self.border_style.addItem(tr(f"stamps.border.{style}"), style)
        current_border = (stamp.border_style if stamp else None) or "solid"
        self.border.setChecked(current_border != "none")
        if current_border != "none":
            self.border_style.setCurrentIndex(self.border_style.findData(current_border))
        self.preview = QLabel()  # Z-013: rezultatul inainte de salvare
        self.preview.setObjectName("stamp_preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(60)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(tr("stamps.name"), self.name)
        form.addRow(tr("stamps.text.text"), self.text)
        form.addRow(tr("stamps.text.add_date"), self.date_combo)
        font_row = QHBoxLayout()
        font_row.addWidget(self.size)
        font_row.addWidget(self.color_button)
        form.addRow(tr("stamps.text.font"), font_row)
        border_row = QHBoxLayout()
        border_row.addWidget(self.border)
        border_row.addWidget(self.border_style)
        form.addRow(border_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("stamps.text.preview")))
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        for signal in (self.name.textChanged, self.text.textChanged, self.size.valueChanged,
                       self.border.toggled, self.border_style.currentIndexChanged):
            signal.connect(self.update_preview)
        self.update_preview()

    def insert_tag(self, index: int) -> None:
        """D-110: eticheta intra la pozitia cursorului, nu la sfarsit."""
        tag = self.date_combo.itemData(index)
        if tag:
            self.text.insertPlainText(tag)
        self.date_combo.setCurrentIndex(0)

    def choose_color(self) -> None:
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor(self.color), self)
        if color.isValid():
            self.color = color.name().upper()
            self.update_preview()

    def border_value(self) -> str:
        return self.border_style.currentData() if self.border.isChecked() else "none"

    def update_preview(self) -> None:
        stamp = Stamp(0, self.name.text(), "text", self.text.toPlainText(),
                      font_size=float(self.size.value()), text_color=self.color,
                      border_style=self.border_value())
        border = {"none": "none", "solid": "2px solid", "double": "4px double",
                  "dashed": "2px dashed"}[self.border_value()]
        self.preview.setText(stamp_text(stamp).replace("\n", "<br>"))
        self.preview.setStyleSheet(f"color: {self.color}; font-size: {self.size.value()}px;"
                                   f" border: {border} {self.color}; padding: 4px;")
        self.save_button.setEnabled(bool(self.name.text().strip() and
                                         self.text.toPlainText().strip()))


class ManageStampsDialog(QDialog):
    """D-050: `Edit...`, `Use`, `Delete...` pe stampilele din biblioteca."""

    def __init__(self, library: StampLibrary, window: Any = None) -> None:
        super().__init__(window)
        self.setObjectName("manage_stamps_dialog")
        self.setWindowTitle(tr("stamps.manage.title"))
        self.library = library
        self.window_ref = window
        self.chosen: Stamp | None = None
        self.list = QListWidget()
        self.list.setObjectName("stamps_list")
        buttons = {}
        for key, slot in (("edit", self.edit_selected), ("use", self.use_selected),
                          ("delete", self.delete_selected)):
            button = QPushButton(tr(f"stamps.manage.{key}"))
            button.setObjectName(f"stamps_{key}")
            button.clicked.connect(slot)
            buttons[key] = button
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        side = QVBoxLayout()
        for button in buttons.values():
            side.addWidget(button)
        side.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(self.list, 1)
        row.addLayout(side)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(close)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for stamp in self.library.stamps():
            item = QListWidgetItem(stamp_label(stamp))
            item.setData(Qt.ItemDataRole.UserRole, stamp.name)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def select(self, name: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(i)

    def selected(self) -> Stamp | None:
        item = self.list.currentItem()
        return self.library.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _report(self, exc: CoreError) -> None:
        if self.window_ref is not None:
            self.window_ref.show_message(tr_error(exc))

    def use_selected(self) -> None:
        self.chosen = self.selected()
        if self.chosen is not None:
            self.accept()

    def delete_selected(self) -> None:
        """Cele livrate nu se sterg (mesaj)."""
        stamp = self.selected()
        if stamp is None:
            return
        try:
            self.library.delete(stamp.name)
        except CoreError as exc:
            self._report(exc)
            return
        self.refresh()

    def edit_selected(self) -> None:
        stamp = self.selected()
        if stamp is None or self.window_ref is None:
            return
        try:
            self.window_ref.edit_stamp(stamp)
        except CoreError as exc:
            self._report(exc)
        self.refresh()
