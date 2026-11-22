"""Tabul `Form Editor` din PDF Editor (faza 11, pasul 11.5): H-010…H-022,
H-030…H-036, H-101…H-110.

`FormDesignController` lucreaza pe vederea documentului curent cat timp e activ
tabul: uneltele de camp (cursorul `+`, clic sau tragere), desenarea campurilor
in modul de editare (dreptunghi albastru, numele in coltul din dreapta-sus,
semnaturile cu `Sign`), selectia, mutarea cu ghidaje mov, redimensionarea din
maner, copierea, copia legata, stergerea, meniul contextual si dialogul de
proprietati. Fiecare modificare trece prin `PdfEditorWindow.modify` (cu Undo).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPen
from PySide6.QtWidgets import QMenu

from app.core.model import FormFieldData, FormFieldType, Rect
from app.gui.i18n import tr

if TYPE_CHECKING:
    from app.gui.pdf_editor import PdfEditorWindow

FIELD_FILL = QColor(120, 170, 255, 70)
"""H-101: dreptunghi albastru deschis, semitransparent."""
FIELD_LINE = QColor(60, 110, 220)
NAME_LABEL = QColor(20, 20, 20)
REQUIRED_NAME = QColor(255, 90, 90)
"""H-022: numele campurilor obligatorii, cu rosu."""
SIGN_LABEL = QColor(240, 140, 30)
"""H-102: eticheta portocalie `Sign`."""
GUIDE = QColor(150, 60, 200)
"""H-110: ghidajele mov."""
SELECTED = QColor("#2f6df6")
HANDLE = 7
DRAG_MIN = 4
"""Sub atatia pixeli, tragerea e un clic (campul are marimea implicita)."""
DEFAULT_SIZES = {
    FormFieldType.TEXT: (150, 20), FormFieldType.CHECKBOX: (14, 14),
    FormFieldType.RADIO: (14, 14), FormFieldType.DROPDOWN: (150, 20),
    FormFieldType.LISTBOX: (150, 60), FormFieldType.BUTTON: (80, 24),
    FormFieldType.SIGNATURE: (180, 50),
}
"""Marimea, in puncte, a unui camp pus cu un clic (H-012)."""
TOOL_ACTIONS = {
    "text_field": FormFieldType.TEXT, "check_box": FormFieldType.CHECKBOX,
    "radio_button": FormFieldType.RADIO, "dropdown_list": FormFieldType.DROPDOWN,
    "list_box": FormFieldType.LISTBOX, "button": FormFieldType.BUTTON,
    "signature_field": FormFieldType.SIGNATURE,
}
"""B-207: uneltele din tabul `Form Editor`."""
STYLE_SETTING = "pdf_forms.default_style"
UNITS_SETTING = "pdf_forms.units"
ACTION_ERRORS = ("go_to_page", "open_file", "follow_link", "send_form")


def _editor(document: Any) -> Any:
    from app.core.pdf.forms import FormEditor

    return FormEditor(document)


class FormDesignController(QObject):
    """H-010: modul de editare a formularelor, pe vederea documentului curent."""

    def __init__(self, window: PdfEditorWindow) -> None:
        super().__init__(window)
        self.window = window
        self.view: Any = None
        self.tool: FormFieldType | None = None
        self.radio_group: str | None = None
        """H-013: grupul in care se adauga butoanele, pana la `Esc`."""
        self.selected: list[int] = []
        self.show_names = True
        """H-011: `Show Field Names`."""
        self.clipboard: list[str] = []
        self._press: tuple[int, float, float] | None = None
        self._mode: str | None = None
        """`create`, `move`, `resize` cat timp butonul mouse-ului e apasat."""
        self._preview: dict[int, Rect] = {}
        self._rubber: Rect | None = None
        self._guides: list[tuple[str, float]] = []
        self._fields: list[FormFieldData] | None = None

    # --- intrarea si iesirea ---

    @property
    def active(self) -> bool:
        return self.view is not None

    def enter(self, view: Any) -> None:
        if self.view is view:
            return
        self.exit()
        self.view = view
        self.selected = []
        self._fields = None
        view.overlays.append(self.paint)
        view.viewport().installEventFilter(self)
        view.viewport().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        view.viewport().update()

    def exit(self) -> None:
        if self.view is None:
            return
        self._stop_radio()
        view, self.view = self.view, None
        if self.paint in view.overlays:
            view.overlays.remove(self.paint)
        view.viewport().removeEventFilter(self)
        view.viewport().unsetCursor()
        self.tool = None
        self.selected = []
        view.viewport().update()

    def _form(self) -> Any:
        current = self.window.current()
        return _editor(current.document) if current is not None else None

    def fields(self) -> list[FormFieldData]:
        if self._fields is None:
            form = self._form()
            self._fields = form.fields() if form is not None else []
        return self._fields

    def refresh(self) -> None:
        self._fields = None
        self.selected = [i for i in self.selected if any(f.id == i for f in self.fields())]
        if self.view is not None:
            self.view.viewport().update()

    def field(self, widget_id: int) -> FormFieldData | None:
        return next((f for f in self.fields() if f.id == widget_id), None)

    # --- uneltele (H-012, H-013, H-103) ---

    def set_tool(self, kind: FormFieldType | None) -> None:
        """Unealta de camp: cursorul devine `+` (H-103)."""
        self._stop_radio()
        self.tool = FormFieldType(kind) if kind is not None else None
        if self.view is not None:
            viewport = self.view.viewport()
            if self.tool is None:
                viewport.unsetCursor()
            else:
                viewport.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.window.sync_form_tools()

    def _stop_radio(self) -> None:
        """H-013: `Esc` opreste adaugarea; un grup cu un singur buton primeste
        avertisment."""
        group, self.radio_group = self.radio_group, None
        if group is None:
            return
        form = self._form()
        if form is None:
            return
        for problem in form.validate_document():
            if problem.params.get("group") == group:
                self.window.show_message(tr("form.radio_single", group=group))

    def _default_style(self, kind: FormFieldType) -> dict[str, Any]:
        styles = self.window.settings.get(STYLE_SETTING) or {}
        style = styles.get(kind.value) if isinstance(styles, dict) else None
        return dict(style) if isinstance(style, dict) else {}

    def create(self, page: int, rect: Rect) -> FormFieldData | None:
        """H-012: campul nou cu unealta curenta; numele e generat (H-109)."""
        from app.core.pdf.forms import with_style

        kind = self.tool
        if kind is None:
            return None
        data = FormFieldData(None, "", kind, page, rect,
                             units=str(self.window.settings.get(UNITS_SETTING) or "cm"))
        data = with_style(data, self._default_style(kind))
        if kind == FormFieldType.RADIO:
            if self.radio_group is None:
                self.radio_group = self._form().next_name(kind, group=True)
            data = replace(data, group_name=self.radio_group)
        if kind == FormFieldType.BUTTON:
            data = replace(data, value=tr("form.default_button_text"))
        created = self.window.modify(lambda d: _editor(d).create_field(data),
                                     "form.error.outside")
        if created is not None:
            self.selected = [int(created.id or 0)]
            if kind != FormFieldType.RADIO:  # H-013: radio continua pana la Esc
                self.set_tool(None)
        self.refresh()
        return created

    # --- desenarea (H-011, H-018, H-022, H-101, H-102, H-110) ---

    def _rect_of(self, data: FormFieldData) -> Rect:
        return self._preview.get(int(data.id or 0), data.rect)

    def paint(self, painter: Any, view: Any) -> None:
        if view is not self.view:
            return
        label_font = QFont(painter.font())
        label_font.setPointSizeF(7.5)
        for data in self.fields():
            box = view.page_to_view(data.page_number, self._rect_of(data))
            if box is None:
                continue
            signature = data.field_type == FormFieldType.SIGNATURE
            painter.fillRect(box, FIELD_FILL)
            pen = QPen(SIGN_LABEL if signature else FIELD_LINE, 1)
            if signature:
                pen.setStyle(Qt.PenStyle.DotLine)  # H-102: chenar punctat
            painter.setPen(pen)
            painter.drawRect(box)
            if signature:
                self._paint_sign(painter, box, label_font)
            if self.show_names:
                self._paint_name(painter, box, data, label_font)
            if data.id in self.selected:
                painter.setPen(QPen(SELECTED, 2))
                painter.drawRect(box.adjusted(-2, -2, 2, 2))
                corner = box.bottomRight()
                painter.fillRect(QRectF(corner.x() - HANDLE / 2, corner.y() - HANDLE / 2,
                                        HANDLE, HANDLE), SELECTED)
        if self._rubber is not None and self._press is not None:
            box = view.page_to_view(self._press[0], self._rubber)
            if box is not None:
                painter.setPen(QPen(SELECTED, 1, Qt.PenStyle.DashLine))
                painter.drawRect(box)
        self._paint_guides(painter, view)

    def _paint_name(self, painter: Any, box: QRectF, data: FormFieldData,
                    font: QFont) -> None:
        """H-101: eticheta neagra cu numele, in coltul din dreapta-sus; H-022:
        numele campurilor obligatorii cu rosu."""
        painter.setFont(font)
        text = data.field_name
        width = painter.fontMetrics().horizontalAdvance(text) + 6
        height = painter.fontMetrics().height() + 2
        label = QRectF(box.right() - width, box.top() - height, width, height)
        painter.fillRect(label, NAME_LABEL)
        painter.setPen(REQUIRED_NAME if data.is_required else QColor("white"))
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)

    @staticmethod
    def _paint_sign(painter: Any, box: QRectF, font: QFont) -> None:
        """H-102: eticheta portocalie `Sign` si un simbol in mijloc."""
        painter.setFont(font)
        text = tr("form.sign_label")
        width = painter.fontMetrics().horizontalAdvance(text) + 8
        height = painter.fontMetrics().height() + 2
        label = QRectF(box.left(), box.top(), width, height)
        painter.fillRect(label, SIGN_LABEL)
        painter.setPen(QColor("white"))
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)
        painter.setPen(SIGN_LABEL)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, "✎")

    def _paint_guides(self, painter: Any, view: Any) -> None:
        if not self._guides or self._press is None:
            return
        page = self._press[0]
        slot = view.slot(page)
        if slot is None:
            return
        painter.setPen(QPen(GUIDE, 1))
        for axis, value in self._guides:
            point = view.page_to_view(page, Rect(value, value, 0, 0))
            if point is None:
                continue
            if axis == "x":
                painter.drawLine(QPointF(point.x(), slot.rect.top()),
                                 QPointF(point.x(), slot.rect.bottom()))
            else:
                painter.drawLine(QPointF(slot.rect.left(), point.y()),
                                 QPointF(slot.rect.right(), point.y()))

    # --- mouse-ul si tastatura ---

    def _hit(self, position: QPointF) -> tuple[int, float, float] | None:
        return self.view.view_to_page(QPointF(position) + self.view._offset())

    def field_at(self, page: int, x: float, y: float) -> FormFieldData | None:
        for data in reversed(self.fields()):
            r = data.rect
            if data.page_number == page and r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                return data
        return None

    def _on_handle(self, page: int, x: float, y: float) -> FormFieldData | None:
        tolerance = HANDLE / max(self.view.scale, 0.01)
        for widget_id in self.selected:
            data = self.field(widget_id)
            if data is None or data.page_number != page:
                continue
            r = data.rect
            if abs(x - (r.x + r.w)) <= tolerance and abs(y - (r.y + r.h)) <= tolerance:
                return data
        return None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        if self.view is None or watched is not self.view.viewport():
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            return self.press(event.position(), event.button(),  # type: ignore[attr-defined]
                              event.modifiers())  # type: ignore[attr-defined]
        if kind == QEvent.Type.MouseMove and self._press is not None:
            self.move(event.position(), event.modifiers())  # type: ignore[attr-defined]
            return True
        if kind == QEvent.Type.MouseButtonRelease and self._press is not None:
            self.release()
            return True
        if kind == QEvent.Type.MouseButtonDblClick:
            hit = self._hit(event.position())  # type: ignore[attr-defined]
            data = self.field_at(*hit) if hit is not None else None
            if data is not None:
                self.properties(data)  # H-014
            return True
        if kind == QEvent.Type.ContextMenu:
            hit = self._hit(QPointF(event.pos()))  # type: ignore[attr-defined]
            data = self.field_at(*hit) if hit is not None else None
            if data is not None and data.id not in self.selected:
                self.selected = [int(data.id or 0)]
            self.context_menu().popup(event.globalPos())  # type: ignore[attr-defined]
            return True
        if kind == QEvent.Type.KeyPress:
            return self.key(event.key(), event.modifiers())  # type: ignore[attr-defined]
        return False

    def press(self, position: QPointF, button: Any = Qt.MouseButton.LeftButton,
              modifiers: Any = Qt.KeyboardModifier.NoModifier) -> bool:
        if button != Qt.MouseButton.LeftButton:
            return False
        hit = self._hit(position)
        if hit is None:
            return True
        page, x, y = hit
        self.view.viewport().setFocus()
        self._press = (page, x, y)
        if self.tool is not None:
            self._mode = "create"
            self._rubber = Rect(x, y, 0, 0)
            return True
        handle = self._on_handle(page, x, y)
        if handle is not None:
            self._mode = "resize"
            self.selected = [int(handle.id or 0)]
            return True
        data = self.field_at(page, x, y)
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        self._mode = None
        if data is None:
            if not ctrl:
                self.selected = []
        else:
            widget_id = int(data.id or 0)
            if ctrl:  # H-017: `Ctrl`+clic pentru mai multe
                if widget_id in self.selected:
                    self.selected.remove(widget_id)
                else:
                    self.selected.append(widget_id)
            elif widget_id not in self.selected:
                self.selected = [widget_id]
            self._mode = "move" if widget_id in self.selected else None
        self.view.viewport().update()
        self.window._update_state()
        return True

    def move(self, position: QPointF,
             modifiers: Any = Qt.KeyboardModifier.NoModifier) -> None:
        hit = self._hit(position)
        if hit is None or self._press is None:
            return
        page, x, y = hit
        start_page, x0, y0 = self._press
        if page != start_page:
            return
        if self._mode == "create":
            self._rubber = Rect(min(x0, x), min(y0, y), abs(x - x0), abs(y - y0))
        elif self._mode == "move":
            self._preview = {}
            for widget_id in self.selected:
                data = self.field(widget_id)
                if data is not None:
                    r = data.rect
                    self._preview[widget_id] = Rect(r.x + x - x0, r.y + y - y0, r.w, r.h)
            self._update_guides(bool(modifiers & Qt.KeyboardModifier.ControlModifier))
        elif self._mode == "resize" and self.selected:
            data = self.field(self.selected[0])
            if data is not None:
                r = data.rect
                self._preview = {self.selected[0]: Rect(r.x, r.y, max(1.0, x - r.x),
                                                        max(1.0, y - r.y))}
        self.view.viewport().update()

    def _update_guides(self, hidden: bool) -> None:
        """H-018, H-110: ghidaje la X sau Y identice; `Ctrl` le ascunde."""
        from app.core.pdf.forms import FormEditor

        self._guides = []
        if hidden or not self.selected:
            return
        first = self.field(self.selected[0])
        if first is None:
            return
        moving = replace(first, rect=self._preview.get(self.selected[0], first.rect))
        others = [f for f in self.fields() if f.id not in self.selected]
        self._guides = FormEditor.alignment_guides(moving, others)

    @property
    def guides(self) -> list[tuple[str, float]]:
        return list(self._guides)

    def release(self) -> None:
        mode, press = self._mode, self._press
        self._mode, self._press = None, None
        self._guides = []
        preview, self._preview = self._preview, {}
        rubber, self._rubber = self._rubber, None
        if press is None:
            return
        page = press[0]
        scale = max(self.view.scale, 0.01)
        if mode == "create" and rubber is not None:
            if rubber.w * scale < DRAG_MIN and rubber.h * scale < DRAG_MIN:
                w, h = DEFAULT_SIZES[self.tool or FormFieldType.TEXT]
                rubber = Rect(rubber.x, rubber.y, w, h)
            self.create(page, rubber)
        elif mode == "move" and preview:
            moved: dict[int, Rect] = {}
            for widget_id, rect in preview.items():
                data = self.field(widget_id)
                if data is not None and (rect.x, rect.y) != (data.rect.x, data.rect.y):
                    moved[widget_id] = rect
            if moved:
                self.move_to(moved)
        elif mode == "resize" and preview:
            [(widget_id, rect)] = preview.items()
            self.window.modify(lambda d: _editor(d).resize_field(widget_id, rect.w, rect.h),
                               "form.error.size")
            self.refresh()
        if self.view is not None:
            self.view.viewport().update()

    def move_to(self, rects: dict[int, Rect]) -> bool:
        """H-017: campurile se pot muta numai in interiorul paginii lor."""
        def run(document: Any) -> bool:
            editor = _editor(document)
            for widget_id, rect in rects.items():
                editor.move_field(widget_id, rect.x, rect.y)
            return True

        done = self.window.modify(run, "form.error.outside") is not None
        self.refresh()
        return done

    def key(self, key: int, modifiers: Any) -> bool:
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        if key == Qt.Key.Key_Escape:
            self.set_tool(None)
            return True
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected:
            self.delete()  # H-021
            return True
        if ctrl and key == Qt.Key.Key_C:
            self.copy()  # H-015
            return True
        if ctrl and key == Qt.Key.Key_V:
            self.paste()
            return True
        return False

    # --- comenzile (H-014…H-016, H-021) ---

    def context_menu(self) -> QMenu:
        """H-011, H-014…H-016, H-021, H-005: meniul contextual."""
        menu = QMenu(self.window)
        menu.setObjectName("form_design_menu")
        one = len(self.selected) == 1
        entries = (("properties", self._properties_selected, one),
                   ("copy", self.copy, bool(self.selected)),
                   ("paste", self.paste, bool(self.clipboard)),
                   ("linked_copy", self.linked_copy, one),
                   ("delete", self.delete, bool(self.selected)))
        for key, slot, enabled in entries:
            action = menu.addAction(tr(f"form.menu.{key}"), slot)
            action.setObjectName(f"form_menu_{key}")
            action.setEnabled(enabled)
        menu.addSeparator()
        names = menu.addAction(tr("form.menu.show_names"))
        names.setObjectName("form_menu_show_names")
        names.setCheckable(True)
        names.setChecked(self.show_names)
        names.toggled.connect(self.set_show_names)
        reset = menu.addAction(tr("pdf.action.reset_form"), self.window.forms.reset_form)
        reset.setObjectName("form_menu_reset")
        return menu

    def set_show_names(self, on: bool) -> None:
        """H-011: `Show Field Names`."""
        self.show_names = on
        action = self.window.actions.get("show_field_names")
        if action is not None and action.isChecked() != on:
            action.setChecked(on)
        if self.view is not None:
            self.view.viewport().update()

    def _properties_selected(self) -> None:
        if len(self.selected) == 1:
            data = self.field(self.selected[0])
            if data is not None:
                self.properties(data)

    def _names(self) -> list[str]:
        out: list[str] = []
        for widget_id in self.selected:
            data = self.field(widget_id)
            if data is not None and data.field_name not in out:
                out.append(data.field_name)
        return out

    def copy(self) -> list[str]:
        """H-015: `Ctrl+C`; se copiaza numele, copia se face la `Ctrl+V`."""
        self.clipboard = self._names()
        return self.clipboard

    def paste(self) -> list[FormFieldData]:
        """H-015: copiile pastreaza tot, in afara numelui; o semnatura completata
        nu se copiaza (`SignedFieldCopyError`, cu mesaj)."""
        names = list(self.clipboard)
        if not names:
            return []
        page = self.view.current_page if self.view is not None else None

        def run(document: Any) -> list[FormFieldData]:
            editor = _editor(document)
            return [editor.copy_field(name, page=page) for name in names]

        created = self.window.modify(run) or []
        self.selected = [int(c.id or 0) for c in created]
        self.refresh()
        return created

    def linked_copy(self) -> FormFieldData | None:
        """H-016: `Create Linked Copy`."""
        names = self._names()
        if len(names) != 1:
            return None
        page = self.view.current_page if self.view is not None else None
        created = self.window.modify(
            lambda d: _editor(d).create_linked_copy(names[0], page=page))
        if created is not None:
            self.selected = [int(created.id or 0)]
        self.refresh()
        return created

    def delete(self) -> bool:
        """H-021: campurile selectate (o copie legata se sterge singura)."""
        ids = list(self.selected)
        if not ids:
            return False
        done = self.window.modify(lambda d: _editor(d).delete_widgets(ids) or True)
        self.selected = []
        self.refresh()
        return done is not None

    def properties(self, data: FormFieldData) -> FormFieldData | None:
        """H-014: dialogul de proprietati; la `OK` campul se modifica."""
        from app.gui.pdf_form_dialogs import FieldPropertiesDialog

        form = self._form()
        if form is None or data.id is None:
            return None
        document = self.window.current().document
        groups = sorted({f.group_name for f in self.fields() if f.group_name})
        name = data.field_name

        def check_name(new: str) -> None:
            if new != name:
                form.validate_field_name(new, current=name)

        checks = data.field_type in (FormFieldType.CHECKBOX, FormFieldType.RADIO)
        dialog = FieldPropertiesDialog(
            data, page_size=document.page_size(data.page_number), groups=groups,
            default_on=form.default_on(data) if checks else False,
            units=str(self.window.settings.get(UNITS_SETTING) or data.units or "cm"),
            validate_name=check_name, edit_action=self.edit_action, parent=self.window)
        if not self.window.exec_dialog(dialog):
            return None
        result = dialog.field_data()
        self.window.settings.set(UNITS_SETTING, result.units)
        if dialog.default_style is not None:  # `Set as Default Style`
            styles = dict(self.window.settings.get(STYLE_SETTING) or {})
            styles[data.field_type.value] = dialog.default_style
            self.window.settings.set(STYLE_SETTING, styles)
        updated = self.window.modify(lambda d: _editor(d).update_field(result),
                                     "form.error.outside")
        self.refresh()
        return updated

    def edit_action(self, action: Any) -> tuple[str, str, dict[str, Any]] | None:
        """H-041, H-042: dialogul `Action`; parametrii se verifica la `Save`."""
        from app.core.pdf.form_actions import validate_action
        from app.gui.pdf_form_dialogs import ActionDialog

        current = self.window.current()
        if current is None:
            return None
        dialog = ActionDialog(current.document.page_count, action, self.window)
        if not self.window.exec_dialog(dialog):
            return None
        event, kind, params = dialog.action_data()
        try:
            params = validate_action(current.document, event, kind, params)
        except ValueError:
            self.window.show_message(tr(f"form.error.action.{kind}")
                                     if kind in ACTION_ERRORS else tr("error.generic"))
            return None
        return event, kind, params
