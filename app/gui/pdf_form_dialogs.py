"""Dialogurile din `Form Editor` (faza 11, pasul 11.5): proprietatile campului
(H-014, H-030…H-036, H-104…H-106) si actiunea (H-041, H-042, H-107, H-108).

Dialogurile nu scriu nimic in document: intorc `FormFieldData` si actiunile, iar
controlerul le trimite nucleului (`FormEditor`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.model import FormFieldData, FormFieldType, Rect
from app.gui.i18n import tr
from app.gui.pdf_content import dialog_buttons

UNITS = ("cm", "in", "pt")
"""H-030: centimetri, inci sau puncte."""
SUGGESTED_MAX_SYMBOLS = 250
"""H-106: valoarea sugerata pentru `Max Number of Symbols`."""
DATE_VIEWS = ("dd.mm.yyyy", "dd/mm/yyyy", "d.m.yyyy", "dd.mm.yy", "yyyy-mm-dd", "mm/dd/yyyy")
"""H-030: formatele propuse in caseta `View` (se poate tasta altul)."""
SEND_FORMATS = ("pdf", "fdf", "xfdf", "html")
"""H-049, H-108: formatele din `File Format`."""


class ColorButton(QWidget):
    """O culoare aleasa (sau niciuna: transparent)."""

    def __init__(self, color: str | None, *, allow_none: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton()
        self.button.setFixedWidth(64)
        self.button.clicked.connect(self._pick)
        row.addWidget(self.button)
        self.clear = QToolButton()
        self.clear.setText("✕")
        self.clear.setToolTip(tr("form.prop.no_color"))
        self.clear.clicked.connect(lambda: self.set_color(None))
        self.clear.setVisible(allow_none)
        row.addWidget(self.clear)
        row.addStretch(1)
        self.color: str | None = None
        self.set_color(color)

    def set_color(self, color: str | None) -> None:
        self.color = color.upper() if color else None
        if self.color:
            self.button.setStyleSheet(f"background: {self.color};")
            self.button.setText("")
        else:
            self.button.setStyleSheet("")
            self.button.setText(tr("form.prop.no_color"))

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color or "#000000"), self)
        if chosen.isValid():
            self.set_color(chosen.name())


def _spin(value: float, maximum: float, decimals: int = 3) -> QDoubleSpinBox:
    """H-105: spinbox cu sageti."""
    spin = QDoubleSpinBox()
    spin.setDecimals(decimals)
    spin.setRange(0, maximum)
    spin.setValue(value)
    return spin


class FieldPropertiesDialog(QDialog):
    """H-014, H-030…H-036: proprietatile campului, pe taburi (`General`,
    `Appearance`, `Format`, `List Items`, `Actions`, dupa tip)."""

    def __init__(self, data: FormFieldData, *, page_size: tuple[float, float],
                 groups: Sequence[str] = (), default_on: bool = False, units: str = "cm",
                 validate_name: Callable[[str], None] | None = None,
                 edit_action: Callable[[Any], Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.pdf.forms import from_units, to_units

        self.setObjectName("form_properties_dialog")
        self.setWindowTitle(tr(f"form.type.{data.field_type.value}"))
        self.data = data
        self.kind = FormFieldType(data.field_type)
        self.page_size = page_size
        self.groups = list(groups)
        self.validate_name = validate_name
        self.edit_action = edit_action
        self.default_style: dict[str, Any] | None = None
        """`Set as Default Style`: stilul cerut, de pastrat de controler."""
        self._to_units, self._from_units = to_units, from_units
        self._units = units if units in UNITS else "cm"
        self._busy = False
        self._ratio = data.rect.w / data.rect.h if data.rect.h else 1.0
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._general(default_on), tr("form.tab.general"))
        self.tabs.addTab(self._appearance(), tr("form.tab.appearance"))
        if self.kind == FormFieldType.TEXT:
            self.tabs.addTab(self._format(), tr("form.tab.format"))
        if self.kind in (FormFieldType.DROPDOWN, FormFieldType.LISTBOX):
            self.tabs.addTab(self._list_items(), tr("form.tab.list_items"))
        if self.kind == FormFieldType.BUTTON:
            self.tabs.addTab(self._actions(), tr("form.tab.actions"))
        self.error = QLabel()
        self.error.setObjectName("form_properties_error")
        self.error.setProperty("warning", True)
        self.error.hide()
        layout.addWidget(self.error)
        self.box = dialog_buttons(self, "form.prop.ok")
        layout.addWidget(self.box)

    # --- General (H-030, H-033, H-034, H-104…H-106) ---

    def _general(self, default_on: bool) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        d = self.data
        self.name = QLineEdit(d.field_name)
        self.name.setObjectName("form_prop_name")
        self.group = QComboBox()  # H-033: nou sau ales dintre grupurile existente
        self.group.setEditable(True)
        self.group_tooltip = QLineEdit(d.tooltip or "")
        if self.kind == FormFieldType.RADIO:
            self.group.addItems(sorted({*self.groups, d.group_name or ""} - {""}))
            self.group.setEditText(d.group_name or "")
            form.addRow(tr("form.prop.group"), self.group)
            form.addRow(tr("form.prop.group_tooltip"), self.group_tooltip)
            form.addRow(tr("form.prop.button_name"), self.name)
        else:
            form.addRow(tr("form.prop.name"), self.name)
        self.tooltip = QLineEdit(d.tooltip or "")
        if self.kind != FormFieldType.RADIO:
            form.addRow(tr("form.prop.tooltip"), self.tooltip)
        self.button_text = QLineEdit((d.value or "") if self.kind == FormFieldType.BUTTON
                                     else "")
        if self.kind == FormFieldType.BUTTON:
            form.addRow(tr("form.prop.button_text"), self.button_text)
        self.max_enabled = QCheckBox(tr("form.prop.max_symbols"))
        self.max_symbols = QSpinBox()
        self.max_symbols.setRange(1, 32767)
        self.max_symbols.setValue(d.max_symbols or SUGGESTED_MAX_SYMBOLS)
        self.max_enabled.toggled.connect(self.max_symbols.setEnabled)  # H-106
        self.max_enabled.setChecked(d.max_symbols is not None)
        self.max_symbols.setEnabled(d.max_symbols is not None)
        if self.kind == FormFieldType.TEXT:
            row = QHBoxLayout()
            row.addWidget(self.max_enabled)
            row.addWidget(self.max_symbols)
            form.addRow(row)
        self.default_on = QCheckBox(tr("form.prop.default_on"))
        self.default_on.setChecked(default_on)
        if self.kind in (FormFieldType.CHECKBOX, FormFieldType.RADIO):
            form.addRow(self.default_on)
        self.required = QCheckBox(tr("form.prop.required"))
        self.required.setChecked(d.is_required)
        if self.kind != FormFieldType.BUTTON:  # H-022
            form.addRow(self.required)
        self.readonly = QCheckBox(tr("form.prop.readonly"))
        self.readonly.setChecked(d.is_readonly)
        form.addRow(self.readonly)
        self.units = QComboBox()
        for unit in UNITS:
            self.units.addItem(tr(f"form.unit.{unit}"), unit)
        self.units.setCurrentIndex(UNITS.index(self._units))
        self.units.currentIndexChanged.connect(self._units_changed)
        form.addRow(tr("form.prop.units"), self.units)
        w, h = self.page_size
        self.x, self.y = _spin(0, w), _spin(0, h)
        self.width, self.height = _spin(0, w), _spin(0, h)
        self.lock = QToolButton()  # H-104
        self.lock.setObjectName("form_prop_lock")
        self.lock.setCheckable(True)
        self.lock.setText("🔒")
        self.lock.setToolTip(tr("form.prop.lock"))
        size = QHBoxLayout()
        size.addWidget(self.width)
        size.addWidget(self.lock)
        size.addWidget(self.height)
        form.addRow(tr("form.prop.size"), size)
        position = QHBoxLayout()
        position.addWidget(self.x)
        position.addWidget(self.y)
        form.addRow(tr("form.prop.position"), position)
        self._show_geometry(d.rect)
        self.width.valueChanged.connect(lambda v: self._locked("w", v))
        self.height.valueChanged.connect(lambda v: self._locked("h", v))
        return page

    def _unit(self) -> str:
        return str(self.units.currentData())

    def _show_geometry(self, rect: Rect) -> None:
        unit = self._unit()
        self._busy = True
        for spin, points in ((self.x, rect.x), (self.y, rect.y), (self.width, rect.w),
                             (self.height, rect.h)):
            spin.setMaximum(self._to_units(max(self.page_size), unit))
            spin.setValue(self._to_units(points, unit))
        minimum = self._to_units(8, unit)  # H-020: inaltimea nu poate fi 0
        self.width.setMinimum(minimum)
        self.height.setMinimum(minimum)
        self._busy = False

    def _units_changed(self) -> None:
        rect = self._rect_in(self._units)
        self._units = self._unit()
        self._show_geometry(rect)

    def _locked(self, which: str, value: float) -> None:
        """H-104: cu lacatul inchis, latimea si inaltimea pastreaza proportia."""
        if self._busy:
            return
        if not self.lock.isChecked():
            if self.height.value():
                self._ratio = self.width.value() / self.height.value()
            return
        self._busy = True
        if which == "w":
            self.height.setValue(value / self._ratio if self._ratio else value)
        else:
            self.width.setValue(value * self._ratio)
        self._busy = False

    def _rect_in(self, unit: str) -> Rect:
        f = self._from_units
        return Rect(f(self.x.value(), unit), f(self.y.value(), unit),
                    f(self.width.value(), unit), f(self.height.value(), unit))

    # --- Appearance ---

    def _appearance(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        d = self.data
        self.colors: dict[str, ColorButton] = {}
        checks = self.kind in (FormFieldType.CHECKBOX, FormFieldType.RADIO)
        rows: list[tuple[str, str | None]] = [("fill", d.fill_color), ("stroke", d.border_color)]
        if checks:
            rows.append(("check", d.check_color or "#000000"))
        elif self.kind != FormFieldType.SIGNATURE:
            rows.append(("font_color", d.text_color or "#000000"))
        for key, color in rows:
            button = ColorButton(color, allow_none=key in ("fill", "stroke"))
            self.colors[key] = button
            label = "form.prop.dot_color" if key == "check" and \
                self.kind == FormFieldType.RADIO else f"form.prop.{key}"
            form.addRow(tr(label), button)
        self.thickness = _spin(d.border_width if d.border_width is not None else
                               (1.0 if d.border_color else 0.0), 12, 1)
        form.addRow(tr("form.prop.thickness"), self.thickness)
        self.font = QFontComboBox()
        self.font_size = QSpinBox()
        self.font_size.setRange(0, 72)
        self.font_size.setSpecialValueText(tr("form.prop.auto"))
        self.font_size.setValue(int(d.font_size or 0))
        if d.font_name:
            self.font.setCurrentFont(QFont(d.font_name))
        if not checks and self.kind != FormFieldType.SIGNATURE:
            form.addRow(tr("form.prop.font"), self.font)
            form.addRow(tr("form.prop.font_size"), self.font_size)
        self.default_style_button = QPushButton(tr("form.prop.default_style"))
        self.default_style_button.clicked.connect(self._set_default_style)
        form.addRow(self.default_style_button)
        return page

    def _set_default_style(self) -> None:
        from app.core.pdf.forms import style_of

        self.default_style = style_of(self.field_data())

    # --- Format (H-030) ---

    def _format(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.format = QComboBox()
        self.format.addItem(tr("form.format.text"), "text")
        self.format.addItem(tr("form.format.date"), "date")
        self.format.setCurrentIndex(1 if self.data.text_format == "date" else 0)
        form.addRow(tr("form.prop.format"), self.format)
        self.format_pages = QStackedWidget()
        text_page = QWidget()
        text_form = QFormLayout(text_page)
        self.field_type = QComboBox()
        self.field_type.addItem(tr("form.format.single_line"), False)
        self.field_type.addItem(tr("form.format.multiline"), True)
        self.field_type.setCurrentIndex(1 if self.data.is_multiline else 0)
        text_form.addRow(tr("form.prop.field_type"), self.field_type)
        date_page = QWidget()
        date_form = QFormLayout(date_page)
        self.date_view = QComboBox()
        self.date_view.setEditable(True)
        self.date_view.addItems(DATE_VIEWS)
        self.date_view.setEditText(self.data.date_format or DATE_VIEWS[0])
        date_form.addRow(tr("form.prop.view"), self.date_view)
        self.format_pages.addWidget(text_page)
        self.format_pages.addWidget(date_page)
        self.format_pages.setCurrentIndex(self.format.currentIndex())
        self.format.currentIndexChanged.connect(self.format_pages.setCurrentIndex)
        form.addRow(self.format_pages)
        return page

    # --- List Items (H-031, H-036) ---

    def _list_items(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        self.item_text = QLineEdit()
        self.item_text.setPlaceholderText(tr("form.items.text"))
        box.addWidget(self.item_text)
        row = QHBoxLayout()
        self.items = QListWidget()
        self.items.setObjectName("form_items")
        self.items.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for text, value, is_default in self.data.items:
            self._add_item(text, value, is_default)
        row.addWidget(self.items, 1)
        buttons = QVBoxLayout()
        self.item_buttons: dict[str, QPushButton] = {}
        for key, slot in (("add", self.add_item), ("edit", self.edit_item),
                          ("delete", self.delete_items), ("set_default", self.set_default),
                          ("unset_default", self.unset_default),
                          ("up", lambda: self.move(-1)), ("down", lambda: self.move(1))):
            button = QPushButton(tr(f"form.items.{key}"))
            button.clicked.connect(slot)
            self.item_buttons[key] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        row.addLayout(buttons)
        box.addLayout(row)
        self.allow_custom = QCheckBox(tr("form.items.allow_custom"))
        self.allow_custom.setChecked(self.data.allow_custom)
        self.allow_multiple = QCheckBox(tr("form.items.allow_multiple"))
        self.allow_multiple.setChecked(self.data.allow_multiple)
        if self.kind == FormFieldType.DROPDOWN:
            box.addWidget(self.allow_custom)
        else:
            box.addWidget(self.allow_multiple)
        return page

    def _add_item(self, text: str, value: str | None, is_default: bool) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, value)
        self._mark(item, is_default)
        self.items.addItem(item)

    @staticmethod
    def _mark(item: QListWidgetItem, is_default: bool) -> None:
        item.setData(Qt.ItemDataRole.UserRole + 1, is_default)
        font = item.font()
        font.setBold(is_default)
        item.setFont(font)

    def add_item(self) -> None:
        text = self.item_text.text().strip()
        if text:
            self._add_item(text, None, False)
            self.item_text.clear()

    def edit_item(self) -> None:
        text = self.item_text.text().strip()
        selected = self.items.selectedItems()
        if text and len(selected) == 1:
            selected[0].setText(text)
            selected[0].setData(Qt.ItemDataRole.UserRole, None)
            self.item_text.clear()

    def delete_items(self) -> None:
        """`Delete`; cu `Ctrl` se aleg mai multe (H-031)."""
        for item in self.items.selectedItems():
            self.items.takeItem(self.items.row(item))

    def set_default(self) -> None:
        """`Set as Default`: un singur element, in afara listei cu selectie
        multipla."""
        selected = self.items.selectedItems()
        if not selected:
            return
        multiple = self.kind == FormFieldType.LISTBOX and self.allow_multiple.isChecked()
        if not multiple:
            for i in range(self.items.count()):
                self._mark(self.items.item(i), False)
            selected = selected[:1]
        for item in selected:
            self._mark(item, True)

    def unset_default(self) -> None:
        for item in self.items.selectedItems():
            self._mark(item, False)

    def move(self, step: int) -> None:
        row = self.items.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < self.items.count():
            return
        item = self.items.takeItem(row)
        self.items.insertItem(target, item)
        self.items.setCurrentRow(target)

    def item_list(self) -> list[tuple[str, str | None, bool]]:
        out: list[tuple[str, str | None, bool]] = []
        for i in range(self.items.count()):
            item = self.items.item(i)
            out.append((item.text(), item.data(Qt.ItemDataRole.UserRole),
                        bool(item.data(Qt.ItemDataRole.UserRole + 1))))
        return out

    # --- Actions (H-034, H-041, H-042) ---

    def _actions(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        self.actions_list = QListWidget()
        self.actions_list.setObjectName("form_actions")
        self.action_data: list[tuple[str, str, dict[str, Any]]] = [
            (e, k, dict(p)) for e, k, p in self.data.actions]
        row.addWidget(self.actions_list, 1)
        buttons = QVBoxLayout()
        self.action_buttons: dict[str, QPushButton] = {}
        for key, slot in (("create", self.create_action), ("edit", self.edit_selected_action),
                          ("delete", self.delete_action)):
            button = QPushButton(tr(f"form.actions.{key}"))
            button.clicked.connect(slot)
            self.action_buttons[key] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        row.addLayout(buttons)
        self._show_actions()
        return page

    def _show_actions(self) -> None:
        self.actions_list.clear()
        for event, kind, _params in self.action_data:
            self.actions_list.addItem(f"{tr(f'form.event.{event}')}: "
                                      f"{tr(f'form.action.{kind}')}")

    def create_action(self) -> None:
        """`Create...` (H-041)."""
        if self.edit_action is None:
            return
        result = self.edit_action(None)
        if result is not None:
            self.action_data.append(result)
            self._show_actions()

    def edit_selected_action(self) -> None:
        """`Edit...` (H-042)."""
        row = self.actions_list.currentRow()
        if self.edit_action is None or row < 0:
            return
        result = self.edit_action(self.action_data[row])
        if result is not None:
            self.action_data[row] = result
            self._show_actions()

    def delete_action(self) -> None:
        row = self.actions_list.currentRow()
        if row >= 0:
            del self.action_data[row]
            self._show_actions()

    # --- rezultatul ---

    def field_data(self) -> FormFieldData:
        """Campul cu valorile din dialog. Pentru bife si butoane radio, `value`
        e `Enabled by Default`; pentru butoane, textul butonului (decizia 4)."""
        kind = self.kind
        d = self.data
        checks = kind in (FormFieldType.CHECKBOX, FormFieldType.RADIO)
        tooltip = (self.group_tooltip.text() if kind == FormFieldType.RADIO
                   else self.tooltip.text()).strip() or None
        value: str | None = d.value
        if checks:
            value = "Yes" if self.default_on.isChecked() else None
        elif kind == FormFieldType.BUTTON:
            value = self.button_text.text() or None
        text_fields = not checks and kind != FormFieldType.SIGNATURE
        out = replace(
            d, field_name=self.name.text().strip(), tooltip=tooltip,
            rect=self._rect_in(self._unit()), units=self._unit(),
            is_required=self.required.isChecked() and kind != FormFieldType.BUTTON,
            is_readonly=self.readonly.isChecked(), value=value,
            fill_color=self.colors["fill"].color, border_color=self.colors["stroke"].color,
            border_width=self.thickness.value(),
            check_color=self.colors["check"].color if checks else d.check_color,
            text_color=self.colors["font_color"].color if "font_color" in self.colors
            else d.text_color,
            font_name=self.font.currentFont().family() if text_fields else d.font_name,
            font_size=(float(self.font_size.value()) or None) if text_fields else None,
            max_symbols=self.max_symbols.value() if kind == FormFieldType.TEXT
            and self.max_enabled.isChecked() else None)
        if kind == FormFieldType.RADIO:
            out = replace(out, group_name=self.group.currentText().strip() or d.group_name)
        if kind == FormFieldType.TEXT:
            date = self.format.currentData() == "date"
            out = replace(out, text_format="date" if date else "text",
                          date_format=self.date_view.currentText().strip() if date else None,
                          is_multiline=bool(self.field_type.currentData()) and not date)
        if kind in (FormFieldType.DROPDOWN, FormFieldType.LISTBOX):
            out = replace(out, items=self.item_list(),
                          allow_custom=kind == FormFieldType.DROPDOWN
                          and self.allow_custom.isChecked(),
                          allow_multiple=kind == FormFieldType.LISTBOX
                          and self.allow_multiple.isChecked())
        if kind == FormFieldType.BUTTON:
            out = replace(out, actions=list(self.action_data))
        return out

    def accept(self) -> None:  # API Qt
        """Numele se verifica inainte de inchidere (H-030)."""
        from app.core.errors import CoreError
        from app.gui.i18n import tr_error

        if self.validate_name is not None:
            try:
                self.validate_name(self.name.text().strip())
            except CoreError as exc:
                self.error.setText(tr_error(exc))
                self.error.show()
                return
        super().accept()


class ActionDialog(QDialog):
    """H-041, H-042: `Trigger Event` si `Action`, cu parametrii actiunii, apoi
    `Save`. La `Send form`: adresa, formatul (H-108) si nota H-107."""

    def __init__(self, page_count: int, action: tuple[str, str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.pdf.form_actions import ACTION_GROUPS, TRIGGER_EVENTS

        self.setObjectName("form_action_dialog")
        self.setWindowTitle(tr("form.actions.title"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.event = QComboBox()
        for event in TRIGGER_EVENTS:  # H-040
            self.event.addItem(tr(f"form.event.{event}"), event)
        form.addRow(tr("form.actions.trigger"), self.event)
        self.action = QComboBox()
        for kinds in ACTION_GROUPS.values():
            if self.action.count():
                self.action.insertSeparator(self.action.count())
            for kind in kinds:
                self.action.addItem(tr(f"form.action.{kind}"), kind)
        form.addRow(tr("form.actions.action"), self.action)
        layout.addLayout(form)
        self.params = QStackedWidget()
        self.pages: dict[str, int] = {}
        self.page_number = QSpinBox()  # H-044
        self.page_number.setRange(1, max(1, page_count))
        self.file = QLineEdit()  # H-047
        self.link = QLineEdit()  # H-048
        self.link.setPlaceholderText("https://")
        self.send_to = QLineEdit()  # H-049
        self.send_format = QComboBox()
        for fmt in SEND_FORMATS:
            self.send_format.addItem(tr(f"form.send.{fmt}"), fmt)
        self.script = QPlainTextEdit()  # H-058
        self.script.setObjectName("form_action_script")
        self._add_page("none", QWidget())
        self._add_page("go_to_page", self._rows([("form.actions.page", self.page_number)]))
        self._add_page("open_file", self._rows([("form.actions.file", self.file)]))
        self._add_page("follow_link", self._rows([("form.actions.link", self.link)]))
        send = self._rows([("form.actions.send_to", self.send_to),
                           ("form.actions.file_format", self.send_format)])
        self.send_note = QLabel(tr("form.actions.send_note"))  # H-107
        self.send_note.setObjectName("form_send_note")
        send.layout().addWidget(self.send_note)
        self._add_page("send_form", send)
        self._add_page("run_javascript",
                       self._rows([("form.actions.javascript", self.script)]))
        layout.addWidget(self.params)
        self.action.currentIndexChanged.connect(self._action_changed)
        self.box = dialog_buttons(self, "form.actions.save")
        layout.addWidget(self.box)
        if action is not None:
            self.set_action(*action)
        self._action_changed()

    @staticmethod
    def _rows(rows: Sequence[tuple[str, QWidget]]) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        for key, widget in rows:
            form.addRow(tr(key), widget)
        return page

    def _add_page(self, key: str, widget: QWidget) -> None:
        self.pages[key] = self.params.addWidget(widget)

    def _action_changed(self) -> None:
        kind = str(self.action.currentData())
        self.params.setCurrentIndex(self.pages.get(kind, self.pages["none"]))

    def set_action(self, event: str, kind: str, params: Any) -> None:
        self.event.setCurrentIndex(max(0, self.event.findData(event)))
        self.action.setCurrentIndex(max(0, self.action.findData(kind)))
        params = dict(params or {})
        if kind == "go_to_page":
            self.page_number.setValue(int(params.get("page", 1)))
        elif kind == "open_file":
            self.file.setText(str(params.get("file", "")))
        elif kind == "follow_link":
            self.link.setText(str(params.get("url", "")))
        elif kind == "send_form":
            self.send_to.setText(str(params.get("to", "")))
            self.send_format.setCurrentIndex(max(0, self.send_format.findData(
                params.get("format", "pdf"))))
        elif kind == "run_javascript":
            self.script.setPlainText(str(params.get("script", "")))

    def action_data(self) -> tuple[str, str, dict[str, Any]]:
        kind = str(self.action.currentData())
        params: dict[str, Any] = {}
        if kind == "go_to_page":
            params = {"page": self.page_number.value()}
        elif kind == "open_file":
            params = {"file": self.file.text().strip()}
        elif kind == "follow_link":
            params = {"url": self.link.text().strip()}
        elif kind == "send_form":
            params = {"to": self.send_to.text().strip(),
                      "format": str(self.send_format.currentData())}
        elif kind == "run_javascript":
            params = {"script": self.script.toPlainText()}
        return str(self.event.currentData()), kind, params
