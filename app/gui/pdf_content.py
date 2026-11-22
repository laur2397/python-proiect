"""Dialogurile pentru continutul documentului in PDF Editor (faza 9, pasul 9.3):
`Link Editor` (F-026…F-028), `Document Properties` (F-054, F-055) si alegerea
unei zone pe pagina (pentru link si `Erase`, F-024).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.model import Rect
from app.gui.i18n import tr
from app.gui.pdf_view import from_display

AREA_COLOR = QColor("#2f6df6")


class AreaPicker(QObject):
    """O zona trasa cu mouse-ul pe pagina; la eliberare `done(pagina, Rect)`.
    Zona e in coordonatele nucleului (puncte, sus-stanga)."""

    def __init__(self, view: Any, done: Callable[[int, Rect], None]) -> None:
        super().__init__(view)
        self.view = view
        self.done = done
        self._start: tuple[int, float, float] | None = None
        self.draft: tuple[int, Rect] | None = None
        view.viewport().installEventFilter(self)
        view.overlays.append(self.paint)
        view.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def detach(self) -> None:
        self.view.viewport().removeEventFilter(self)
        if self.paint in self.view.overlays:
            self.view.overlays.remove(self.paint)
        self.view.viewport().unsetCursor()
        self.view.viewport().update()

    def _content(self, event: Any) -> QPointF:
        return event.position() + QPointF(self.view.horizontalScrollBar().value(),
                                          self.view.verticalScrollBar().value())

    def _clamped(self, page: int, event: Any) -> tuple[float, float]:
        point = self._content(event)
        slot = self.view.slot(page)
        x = min(max(point.x(), slot.rect.left()), slot.rect.right())
        y = min(max(point.y(), slot.rect.top()), slot.rect.bottom())
        rotation, w, h = self.view._page_geometry(page)
        return from_display(rotation, w, h, (x - slot.rect.left()) / self.view.scale,
                            (y - slot.rect.top()) / self.view.scale)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._start = self.view.view_to_page(self._content(event))
            return True
        if kind == QEvent.Type.MouseMove and self._start is not None:
            page, x0, y0 = self._start
            x1, y1 = self._clamped(page, event)
            self.draft = (page, Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)))
            self.view.viewport().update()
            return True
        if kind == QEvent.Type.MouseButtonRelease and self._start is not None:
            draft, self.draft, self._start = self.draft, None, None
            self.view.viewport().update()
            if draft is not None and draft[1].w >= 3 and draft[1].h >= 3:
                self.done(*draft)
            return True
        return kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease)

    def paint(self, painter: QPainter, view: Any) -> None:
        if view is not self.view or self.draft is None:
            return
        box = view.page_to_view(*self.draft)
        if box is not None:
            painter.setPen(QPen(AREA_COLOR, 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(box)


def dialog_buttons(dialog: QDialog, ok_key: str) -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                           QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(tr(ok_key))
    box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("organize.cancel"))
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class LinkEditorDialog(QDialog):
    """F-026: o pagina din document (cu `Select specific destination...`) sau
    alta resursa: adresa web, e-mail cu `mailto:`, fisier cu `file://` (F-027)."""

    def __init__(self, page_count: int, target: dict[str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("link_editor")
        self.setWindowTitle(tr("pdflink.title"))
        self.to_page = QRadioButton(tr("pdflink.to_page"))
        self.to_page.setObjectName("link_to_page")
        self.to_other = QRadioButton(tr("pdflink.to_other"))
        self.to_other.setObjectName("link_to_other")
        kinds = QButtonGroup(self)
        kinds.addButton(self.to_page)
        kinds.addButton(self.to_other)
        self.page = QSpinBox()
        self.page.setObjectName("link_page")
        self.page.setRange(1, max(page_count, 1))
        self.specific = QCheckBox(tr("pdflink.specific"))
        self.specific.setObjectName("link_specific")
        self.position = QDoubleSpinBox()
        self.position.setObjectName("link_position")
        self.position.setRange(0, 20000)
        self.position.setSuffix(" pt")
        self.position.setEnabled(False)
        self.specific.toggled.connect(self.position.setEnabled)
        self.address = QLineEdit()
        self.address.setObjectName("link_address")
        self.address.setPlaceholderText("https://…  mailto:…  file://…")
        page_box = QGroupBox()
        page_form = QFormLayout(page_box)
        page_form.addRow(tr("pdflink.page"), self.page)
        page_form.addRow(self.specific, self.position)
        self.message = QLabel()
        self.message.setObjectName("link_message")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #c62828;")
        column = QVBoxLayout(self)
        column.addWidget(self.to_page)
        column.addWidget(page_box)
        column.addWidget(self.to_other)
        column.addWidget(self.address)
        hint = QLabel(tr("pdflink.prefixes"))
        hint.setWordWrap(True)
        hint.setProperty("muted", True)
        column.addWidget(hint)
        column.addWidget(self.message)
        self.box = dialog_buttons(self, "organize.ok")
        column.addWidget(self.box)
        for signal in (self.to_page.toggled, self.specific.toggled):
            signal.connect(lambda _on: self._validate())
        self.address.textChanged.connect(lambda _t: self._validate())
        self.page.valueChanged.connect(lambda _v: self._validate())
        self._load(target)
        self._validate()

    def _load(self, target: dict[str, Any] | None) -> None:
        if target is None or target.get("kind") == "page":
            self.to_page.setChecked(True)
            if target is not None:
                self.page.setValue(int(target.get("page") or 1))
                if target.get("y") is not None:
                    self.specific.setChecked(True)
                    self.position.setValue(float(target["y"]))
        else:
            self.to_other.setChecked(True)
            self.address.setText(str(target.get("uri", "")))

    def target(self) -> dict[str, Any]:
        """Tinta, validata (F-027); `ValueError` daca adresa nu are prefixul."""
        from app.core.pdf.navigation import validate_link_target

        if self.to_page.isChecked():
            y = self.position.value() if self.specific.isChecked() else None
            return validate_link_target({"kind": "page", "page": self.page.value(), "y": y})
        uri = self.address.text().strip()
        low = uri.lower()
        kind = "email" if low.startswith("mailto:") else \
            "file" if low.startswith("file://") else "url"
        return validate_link_target({"kind": kind, "uri": uri})

    def _validate(self) -> None:
        self.page.setEnabled(self.to_page.isChecked())
        self.specific.setEnabled(self.to_page.isChecked())
        self.address.setEnabled(self.to_other.isChecked())
        try:
            self.target()
            ok, text = True, ""
        except ValueError:
            ok = False
            text = tr("pdflink.invalid") if self.address.text().strip() else ""
        self.message.setText(text)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)


EDITABLE = ("title", "author", "subject", "keywords")
"""F-054: campurile editabile."""
READ_ONLY = ("file_name", "location", "file_size", "page_size", "pages", "producer",
             "application", "pdf_version", "pdfa", "pdfua", "tagged", "fast_web_view",
             "created", "modified")
"""F-055: campurile doar in citire, in ordinea din dialog."""


class PropertiesDialog(QDialog):
    """F-054, F-055: `Document Properties`."""

    def __init__(self, properties: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("document_properties")
        self.setWindowTitle(tr("properties.window"))
        self.fields: dict[str, QLineEdit] = {}
        editable = QGroupBox(tr("properties.description"))
        form = QFormLayout(editable)
        for key in EDITABLE:
            edit = QLineEdit(str(properties.get(key) or ""))
            edit.setObjectName(f"properties_{key}")
            edit.setEnabled(bool(properties.get("editable")))  # protejat → gri
            form.addRow(tr(f"properties.{key}"), edit)
            self.fields[key] = edit
        info = QGroupBox(tr("properties.info"))
        info_form = QFormLayout(info)
        self.values: dict[str, QLabel] = {}
        for key in READ_ONLY:
            label = QLabel(self._text(key, properties.get(key)))
            label.setObjectName(f"properties_{key}")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_form.addRow(tr(f"properties.{key}"), label)
            self.values[key] = label
        column = QVBoxLayout(self)
        column.addWidget(editable)
        if not properties.get("editable"):
            note = QLabel(tr("properties.protected"))
            note.setWordWrap(True)
            note.setProperty("muted", True)
            column.addWidget(note)
        column.addWidget(info)
        column.addWidget(dialog_buttons(self, "organize.ok"))

    @staticmethod
    def _text(key: str, value: Any) -> str:
        from app.gui.pdf_panels import size_text

        if value is None or value == "":
            return "—"
        if key == "file_size":
            return size_text(int(value))
        if key == "page_size":
            w, h = value
            return tr("properties.page_size_value", w=f"{w * 25.4 / 72:.0f}",
                      h=f"{h * 25.4 / 72:.0f}")
        if isinstance(value, bool):
            return tr("properties.yes") if value else tr("properties.no")
        return str(value)

    def changes(self, properties: dict[str, Any]) -> dict[str, str]:
        """Campurile schimbate, pentru `set_metadata`."""
        return {k: e.text().strip() for k, e in self.fields.items()
                if e.text().strip() != str(properties.get(k) or "")}


# --- 9.4: antet si subsol, filigran (F-039…F-050, Z-013) ------------------------------------


def _pages_for(apply_to: str, text: str, page_count: int, selected: list[int]) -> list[int]:
    """F-042, F-048: paginile alese in dialog."""
    from app.core.pdf.organize import parse_range

    everything = list(range(1, page_count + 1))
    if apply_to == "odd":
        return everything[0::2]
    if apply_to == "even":
        return everything[1::2]
    if apply_to == "selected":
        return list(selected)
    if apply_to == "range":
        return list(parse_range(text, page_count).pages)
    return everything


class _PagesBox(QGroupBox):
    """F-042 (`All` / `Page range` / `Odd Pages` / `Even Pages`) si F-048
    (`All` / `Selected` / `Page range`)."""

    def __init__(self, choices: tuple[str, ...], page_count: int, selected: list[int]) -> None:
        from PySide6.QtWidgets import QComboBox, QHBoxLayout

        super().__init__(tr("decorate.pages"))
        self.page_count, self.selected = page_count, selected
        self.apply_to = QComboBox()
        self.apply_to.setObjectName("decorate_apply_to")
        for key in choices:
            self.apply_to.addItem(tr(f"decorate.apply.{key}"), key)
        self.range = QLineEdit()
        self.range.setObjectName("decorate_range")
        self.range.setPlaceholderText("2, 3, 5-7")
        self.apply_to.currentIndexChanged.connect(
            lambda _i: self.range.setEnabled(self.apply_to.currentData() == "range"))
        self.range.setEnabled(False)
        row = QHBoxLayout(self)
        row.addWidget(self.apply_to)
        row.addWidget(self.range, 1)

    def pages(self) -> list[int]:
        return _pages_for(str(self.apply_to.currentData()), self.range.text(),
                          self.page_count, self.selected)


def _font_names() -> list[str]:
    from app.core.fonts import FontMatcher

    try:
        return FontMatcher().installed_fonts()
    except OSError:
        return []


class _FontBox(QGroupBox):
    """F-041: fontul, dimensiunea, efectele, culoarea."""

    def __init__(self, size: float, color: str, effects: bool = True) -> None:
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton

        super().__init__(tr("decorate.font"))
        self.family = QComboBox()
        self.family.setObjectName("decorate_font")
        self.family.addItem(tr("decorate.font_default"), "")
        for name in _font_names():
            self.family.addItem(name, name)
        self.size = QDoubleSpinBox()
        self.size.setObjectName("decorate_size")
        self.size.setRange(1, 1638)
        self.size.setValue(size)
        self.color = color
        self.color_button = QPushButton()
        self.color_button.setObjectName("decorate_color")
        self.color_button.clicked.connect(self.pick_color)
        self.bold = QCheckBox(tr("decorate.bold"))
        self.bold.setObjectName("decorate_bold")
        self.italic = QCheckBox(tr("decorate.italic"))
        self.italic.setObjectName("decorate_italic")
        self.underline = QCheckBox(tr("decorate.underline"))
        self.underline.setObjectName("decorate_underline")
        form = QFormLayout(self)
        form.addRow(tr("decorate.font_name"), self.family)
        form.addRow(tr("decorate.size"), self.size)
        form.addRow(tr("decorate.color"), self.color_button)
        if effects:
            row = QHBoxLayout()
            for box in (self.bold, self.italic, self.underline):
                row.addWidget(box)
            form.addRow(row)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.color = color
        self.color_button.setText(color)
        self.color_button.setStyleSheet(f"QPushButton {{ color: {color}; }}")

    def pick_color(self) -> None:
        from PySide6.QtGui import QColor as _QColor
        from PySide6.QtWidgets import QColorDialog

        chosen = QColorDialog.getColor(_QColor(self.color), self)
        if chosen.isValid():
            self.set_color(chosen.name())

    def font_name(self) -> str | None:
        return str(self.family.currentData()) or None


class HeaderFooterDialog(QDialog):
    """F-039…F-043, Z-013: `Create Header and Footer...`."""

    def __init__(self, page_count: int, selected: list[int], *, bates_next: int = 1,
                 template: Any = None, parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton

        from app.core.pdf.decorate import HEADER_POSITIONS, UNITS, HeaderFooter

        super().__init__(parent)
        self.setObjectName("header_footer_dialog")
        self.setWindowTitle(tr("decorate.header_title"))
        hf = template or HeaderFooter()
        self.page_count = page_count
        self.save_and_add = False
        """F-043: `Save and Add`: fereastra cere numele sablonului."""
        self.position = QComboBox()
        self.position.setObjectName("header_position")
        for key in HEADER_POSITIONS:
            self.position.addItem(tr(f"decorate.position.{key}"), key)
        self.position.setCurrentIndex(HEADER_POSITIONS.index(hf.position))
        self.margin = QDoubleSpinBox()
        self.margin.setObjectName("header_margin")
        self.margin.setRange(0, 1000)
        self.margin.setDecimals(2)
        self.margin.setValue(hf.margin)
        self.unit = QComboBox()
        self.unit.setObjectName("header_unit")
        for key in UNITS:
            self.unit.addItem(tr(f"decorate.unit.{key}"), key)
        self.unit.setCurrentIndex(list(UNITS).index(hf.margin_unit))
        self.content = QLineEdit(hf.content)
        self.content.setObjectName("header_content")
        inserts = QHBoxLayout()
        self.insert_buttons: dict[str, QPushButton] = {}
        for key, token in (("page", "{page}"), ("bates", "{bates}"), ("date", "<d/>")):
            button = QPushButton(tr(f"decorate.insert.{key}"))  # F-040
            button.setObjectName(f"header_insert_{key}")
            button.clicked.connect(lambda _c=False, t=token: self.content.insert(t))
            inserts.addWidget(button)
            self.insert_buttons[key] = button
        self.bates_start = QSpinBox()
        self.bates_start.setObjectName("header_bates_start")
        self.bates_start.setRange(0, 999_999_999)
        self.bates_start.setValue(hf.bates_start if hf.bates_start is not None else 1)
        self.bates_next = bates_next
        self.continue_from = QCheckBox(tr("decorate.continue_from", n=bates_next))
        self.continue_from.setObjectName("header_continue_from")
        self.continue_from.toggled.connect(self._continue_toggled)
        self.bates_digits = QSpinBox()
        self.bates_digits.setObjectName("header_bates_digits")
        self.bates_digits.setRange(1, 10)
        self.bates_digits.setValue(hf.bates_digits)
        bates = QGroupBox(tr("decorate.bates"))
        bates_form = QFormLayout(bates)
        bates_form.addRow(tr("decorate.start_at"), self.bates_start)
        bates_form.addRow(self.continue_from)
        bates_form.addRow(tr("decorate.digits"), self.bates_digits)
        self.font = _FontBox(hf.font_size, hf.text_color)
        if hf.font_name:
            index = self.font.family.findData(hf.font_name)
            if index >= 0:
                self.font.family.setCurrentIndex(index)
        self.font.bold.setChecked(hf.bold)
        self.font.italic.setChecked(hf.italic)
        self.font.underline.setChecked(hf.underline)
        self.pages = _PagesBox(("all", "range", "odd", "even"), page_count, selected)
        self.preview = QLabel()  # Z-013: rezultatul inainte de aplicare
        self.preview.setObjectName("header_preview")
        self.preview.setWordWrap(True)
        for signal in (self.content.textChanged, self.bates_start.valueChanged,
                       self.bates_digits.valueChanged):
            signal.connect(lambda *_a: self._update())
        form = QFormLayout()
        form.addRow(tr("decorate.position"), self.position)
        margin_row = QHBoxLayout()
        margin_row.addWidget(self.margin)
        margin_row.addWidget(self.unit)
        form.addRow(tr("decorate.margin"), margin_row)
        form.addRow(tr("decorate.content"), self.content)
        form.addRow(inserts)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(bates)
        column.addWidget(self.font)
        column.addWidget(self.pages)
        column.addWidget(self.preview)
        self.box = dialog_buttons(self, "decorate.apply")
        save = self.box.addButton(tr("decorate.save_and_add"),
                                  QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("header_save_and_add")
        save.clicked.connect(self._save_clicked)
        column.addWidget(self.box)
        self._update()

    def _save_clicked(self) -> None:
        self.save_and_add = True

    def _continue_toggled(self, on: bool) -> None:
        """F-040: `Continue from`: numerotarea continua de unde a ramas."""
        if on:
            self.bates_start.setValue(self.bates_next)
        self.bates_start.setEnabled(not on)

    def settings(self) -> Any:
        from app.core.pdf.decorate import HeaderFooter

        uses_bates = "{bates}" in self.content.text()
        return HeaderFooter(
            position=str(self.position.currentData()), content=self.content.text(),
            margin=self.margin.value(), margin_unit=str(self.unit.currentData()),
            font_name=self.font.font_name(), font_size=self.font.size.value(),
            text_color=self.font.color, bold=self.font.bold.isChecked(),
            italic=self.font.italic.isChecked(), underline=self.font.underline.isChecked(),
            bates_start=self.bates_start.value() if uses_bates else None,
            bates_digits=self.bates_digits.value())

    def _update(self) -> None:
        from app.core.pdf.decorate import expand_content

        hf = self.settings()
        try:
            hf.validate()
            pages = self.pages.pages()
            first = pages[0] if pages else 1
            sample = expand_content(hf.content, page=first, pages=self.page_count,
                                    bates=hf.bates_start, bates_digits=hf.bates_digits)
            self.preview.setText(tr("decorate.preview", text=sample))
            ok = True
        except ValueError:
            self.preview.setText("")
            ok = False
        for button in self.box.buttons():
            if self.box.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole:
                button.setEnabled(ok)


class ManageHeadersDialog(QDialog):
    """F-044: `Manage Headers and Footers...`: `Copy...`, `Edit...`, `Delete`
    (`Save` e in dialogul de editare)."""

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton

        super().__init__(parent)
        self.setObjectName("manage_headers_dialog")
        self.setWindowTitle(tr("decorate.manage"))
        self.list = QListWidget()
        self.list.setObjectName("manage_headers_list")
        self.list.addItems(names)
        if names:
            self.list.setCurrentRow(0)
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        for key in ("copy", "edit", "delete"):
            button = QPushButton(tr(f"decorate.manage.{key}"))
            button.setObjectName(f"manage_headers_{key}")
            row.addWidget(button)
            self.buttons[key] = button
        column = QVBoxLayout(self)
        column.addWidget(self.list, 1)
        column.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        column.addWidget(close)

    def current(self) -> str | None:
        item = self.list.currentItem()
        return item.text() if item is not None else None

    def set_names(self, names: list[str]) -> None:
        self.list.clear()
        self.list.addItems(names)
        if names:
            self.list.setCurrentRow(0)


class WatermarkDialog(QDialog):
    """F-045…F-049: `Add Watermark...`."""

    def __init__(self, page_count: int, selected: list[int],
                 parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSlider

        from app.core.pdf.decorate import WATERMARK_POSITIONS

        super().__init__(parent)
        self.setObjectName("watermark_dialog")
        self.setWindowTitle(tr("decorate.watermark_title"))
        self.add_another = False
        """F-049: `Save and Add`: dupa aplicare, dialogul se redeschide."""
        self.use_text = QRadioButton(tr("decorate.wm_text"))
        self.use_text.setObjectName("watermark_use_text")
        self.use_image = QRadioButton(tr("decorate.wm_image"))
        self.use_image.setObjectName("watermark_use_image")
        kinds = QButtonGroup(self)
        kinds.addButton(self.use_text)
        kinds.addButton(self.use_image)
        self.use_text.setChecked(True)
        self.text = QLineEdit(tr("decorate.wm_default"))
        self.text.setObjectName("watermark_text")
        self.image = QLineEdit()
        self.image.setObjectName("watermark_image")
        browse = QPushButton(tr("organize.browse"))
        browse.clicked.connect(self._browse)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image, 1)
        image_row.addWidget(browse)
        self.font = _FontBox(60.0, "#808080", effects=False)
        self.position = QComboBox()
        self.position.setObjectName("watermark_position")
        for key in WATERMARK_POSITIONS:
            self.position.addItem(tr(f"decorate.position.{key}"), key)
        self.position.setCurrentIndex(WATERMARK_POSITIONS.index("center"))
        self.offset_x = QDoubleSpinBox()
        self.offset_x.setObjectName("watermark_offset_x")
        self.offset_y = QDoubleSpinBox()
        self.offset_y.setObjectName("watermark_offset_y")
        for spin in (self.offset_x, self.offset_y):
            spin.setRange(-2000, 2000)
            spin.setSuffix(" pt")
        self.rotation, self.rotation_slider = QSpinBox(), QSlider(Qt.Orientation.Horizontal)
        self.rotation.setObjectName("watermark_rotation")
        self.transparency, self.transparency_slider = QSpinBox(), \
            QSlider(Qt.Orientation.Horizontal)
        self.transparency.setObjectName("watermark_transparency")
        for spin, slider, low, high, value, suffix in (
                (self.rotation, self.rotation_slider, -180, 180, 45, "°"),
                (self.transparency, self.transparency_slider, 0, 100, 70, " %")):
            spin.setRange(low, high)
            slider.setRange(low, high)
            spin.setSuffix(suffix)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(spin.setValue)
            spin.setValue(value)
        self.above = QRadioButton(tr("decorate.above"))
        self.above.setObjectName("watermark_above")
        self.behind = QRadioButton(tr("decorate.behind"))
        self.behind.setObjectName("watermark_behind")
        places = QButtonGroup(self)
        places.addButton(self.above)
        places.addButton(self.behind)
        self.above.setChecked(True)
        self.pages = _PagesBox(("all", "selected", "range"), page_count, selected)
        form = QFormLayout()
        form.addRow(self.use_text, self.text)
        form.addRow(self.use_image, image_row)
        form.addRow(tr("decorate.position"), self.position)
        offsets = QHBoxLayout()
        offsets.addWidget(self.offset_x)
        offsets.addWidget(self.offset_y)
        form.addRow(tr("decorate.offset"), offsets)
        rotate_row = QHBoxLayout()
        rotate_row.addWidget(self.rotation)
        rotate_row.addWidget(self.rotation_slider, 1)
        form.addRow(tr("decorate.rotate"), rotate_row)
        transparency_row = QHBoxLayout()
        transparency_row.addWidget(self.transparency)
        transparency_row.addWidget(self.transparency_slider, 1)
        form.addRow(tr("decorate.transparency"), transparency_row)
        form.addRow(self.above)
        form.addRow(self.behind)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(self.font)
        column.addWidget(self.pages)
        self.box = dialog_buttons(self, "decorate.apply")
        more = self.box.addButton(tr("decorate.save_and_add"),
                                  QDialogButtonBox.ButtonRole.AcceptRole)
        more.setObjectName("watermark_save_and_add")
        more.clicked.connect(self._more_clicked)
        column.addWidget(self.box)

    def _more_clicked(self) -> None:
        self.add_another = True

    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        name, _ = QFileDialog.getOpenFileName(self, tr("decorate.wm_image"), "",
                                              "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")
        if name:
            self.image.setText(name)
            self.use_image.setChecked(True)

    def settings(self) -> Any:
        from pathlib import Path

        from app.core.pdf.decorate import Watermark

        image = self.image.text().strip()
        return Watermark(
            text=self.text.text() if self.use_text.isChecked() else None,
            image=Path(image) if self.use_image.isChecked() and image else None,
            position=str(self.position.currentData()),
            offset=(self.offset_x.value(), self.offset_y.value()),
            rotation=float(self.rotation.value()),
            opacity=1 - self.transparency.value() / 100,
            behind_content=self.behind.isChecked(), font_name=self.font.font_name(),
            font_size=self.font.size.value(), text_color=self.font.color)


class RecognizeDialog(QDialog):
    """F-018: `Recognize Document`, cu `Correct page orientation`, `Deskew
    images and correct image resolution` si `Recognize`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recognize_dialog")
        self.setWindowTitle(tr("edit.text_layer.title"))
        self.orientation = QCheckBox(tr("organize.enhance.orientation"))
        self.orientation.setObjectName("recognize_orientation")
        self.orientation.setChecked(True)
        self.deskew = QCheckBox(tr("organize.enhance.deskew"))
        self.deskew.setObjectName("recognize_deskew")
        column = QVBoxLayout(self)
        column.addWidget(self.orientation)
        column.addWidget(self.deskew)
        column.addWidget(dialog_buttons(self, "edit.text_layer.recognize"))
