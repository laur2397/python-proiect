"""Completarea formularelor in PDF Editor (faza 11, pasul 11.4): H-001…H-007,
H-022, H-023, H-040…H-058, H-100, B-036…B-041.

`FormFillController` tine de fereastra: banda galbena de detectie (H-100),
evidentierea campurilor (H-002), editarea direct pe pagina (un editor Qt pus
peste camp), bifele si butoanele radio, butoanele cu actiuni si executia
comenzilor intoarse de nucleu (`FormScripts`). Regulile sunt in nucleu
(`app/core/pdf/forms.py`, `form_actions.py`); aici e numai interfata.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QToolButton,
    QWidget,
)

from app.core.applog import get_logger
from app.core.errors import CoreError
from app.core.model import FormFieldData, FormFieldType
from app.gui.i18n import tr, tr_error

if TYPE_CHECKING:
    from app.gui.pdf_editor import PdfEditorWindow

_log = get_logger(__name__)

HIGHLIGHT = QColor(110, 150, 255, 60)
"""H-002: fundalul campurilor evidentiate."""
FOCUS = "#2f6df6"
TEXT_EDITORS = (FormFieldType.TEXT, FormFieldType.DROPDOWN, FormFieldType.LISTBOX)
DATA_FILTERS = {"fdf": "pdf.form.filter.fdf", "xfdf": "pdf.form.filter.xfdf",
                "html": "pdf.form.filter.html"}


class FormFillController(QObject):
    """H-001…H-007, H-100: completarea formularului documentului curent."""

    def __init__(self, window: PdfEditorWindow) -> None:
        super().__init__(window)
        self.window = window
        self.highlight = False
        """H-002: campurile au fundal colorat."""
        self._closed: set[int] = set()
        """H-100: documentele la care banda a fost inchisa cu `X`."""
        self._fields: dict[int, list[FormFieldData]] = {}
        self.editor_widget: QWidget | None = None
        self.editing: FormFieldData | None = None
        self._committing = False
        self._hover: dict[int, int | None] = {}

    # --- documentul curent ---

    def _document(self) -> Any:
        current = self.window.current()
        return current.document if current is not None else None

    def form(self, document: Any = None) -> Any:
        from app.core.pdf.forms import FormEditor

        document = document if document is not None else self._document()
        return FormEditor(document) if document is not None else None

    def scripts(self, document: Any = None) -> Any:
        """B-038…B-040: scripturile ruleaza numai cu JavaScript-ul activat."""
        from app.core.pdf.form_actions import FormScripts

        document = document if document is not None else self._document()
        return FormScripts(self.form(document), enabled=self.window.policy.allows(document))

    def fields(self, document: Any = None) -> list[FormFieldData]:
        document = document if document is not None else self._document()
        if document is None:
            return []
        key = id(document)
        if key not in self._fields:
            try:
                self._fields[key] = self.form(document).fields()
            except (CoreError, ValueError, KeyError) as exc:
                _log.warning("campurile nu s-au putut citi: %s", exc)
                self._fields[key] = []
        return self._fields[key]

    def invalidate(self, document: Any = None) -> None:
        document = document if document is not None else self._document()
        if document is not None:
            self._fields.pop(id(document), None)

    def field_at(self, page: int, x: float, y: float) -> FormFieldData | None:
        for data in reversed(self.fields()):
            r = data.rect
            if data.page_number == page and r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                return data
        return None

    # --- banda de detectie (H-001, H-100) ---

    def build_band(self) -> QWidget:
        """H-100: bara galbena, cu `Highlight fields` si `X`."""
        self.band = QFrame()
        self.band.setObjectName("pdf_form_band")
        self.band.setProperty("warning", True)
        row = QHBoxLayout(self.band)
        row.setContentsMargins(10, 4, 10, 4)
        row.addWidget(QLabel(tr("pdf.form.banner")), 1)
        self.highlight_box = QCheckBox(tr("pdf.form.highlight"))
        self.highlight_box.setObjectName("pdf_form_highlight")
        self.highlight_box.toggled.connect(self.set_highlight)
        row.addWidget(self.highlight_box)
        close = QToolButton()
        close.setObjectName("pdf_form_band_close")
        close.setText("✕")
        close.setToolTip(tr("pdf.form.close_banner"))
        close.clicked.connect(self.close_band)
        row.addWidget(close)
        self.band.hide()
        return self.band

    def update_band(self) -> None:
        """H-001: banda apare cand documentul are campuri interactive."""
        document = self._document()
        show = document is not None and id(document) not in self._closed and \
            bool(self.fields(document))
        self.band.setVisible(show)

    def close_band(self) -> None:
        document = self._document()
        if document is not None:
            self._closed.add(id(document))
        self.band.hide()

    def set_highlight(self, on: bool) -> None:
        """H-002: bifa din banda si `Form Editor > Highlight Fields`."""
        self.highlight = on
        if self.highlight_box.isChecked() != on:
            self.highlight_box.setChecked(on)
        current = self.window.current()
        if current is not None:
            current.view.viewport().update()

    def paint(self, painter: Any, view: Any) -> None:
        """H-002: fundalul campurilor; campul editat are chenar albastru."""
        current = self.window.current()
        if current is None or view is not current.view:
            return
        for data in self.fields():
            box = view.page_to_view(data.page_number, data.rect)
            if box is None:
                continue
            if self.highlight:
                painter.fillRect(box, HIGHLIGHT)
            if self.editing is not None and data.id == self.editing.id:
                painter.setPen(QPen(QColor(FOCUS), 2))
                painter.drawRect(box.adjusted(-1, -1, 1, 1))

    def attach(self, view: Any) -> None:
        view.overlays.append(self.paint)
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    # --- clicul pe camp ---

    def activate(self, page: int, x: float, y: float) -> bool:
        """Un clic pe pagina: True daca a fost pe un camp si l-a tratat."""
        if self.window.edit_mode or getattr(self.window, "form_editor_mode", False):
            return False
        data = self.field_at(page, x, y)
        self.finish_editing()
        if data is None:
            return False
        self._run_event(data, "drop")
        if data.field_type == FormFieldType.BUTTON:
            self._run_event(data, "click")
            return True
        if data.is_readonly:
            return True
        if data.field_type in (FormFieldType.CHECKBOX, FormFieldType.RADIO):
            self.toggle(data)
        elif data.field_type in TEXT_EDITORS:
            self.open_editor(data)
        elif data.field_type == FormFieldType.SIGNATURE and data.value is None:
            self.window.sign_document(data.page_number, data.rect, data.field_name)
        self._run_event(data, "click")
        return True

    def toggle(self, data: FormFieldData) -> bool:
        """H-032, H-033: bifa se comuta; butonul radio se alege."""
        if data.field_type == FormFieldType.CHECKBOX:
            checked = data.value not in (None, "Off")
            return self._commit(data.field_name, "" if checked else "on")
        return self._commit(data.field_name, data.field_name)

    def open_editor(self, data: FormFieldData) -> QWidget | None:
        """Editorul pus peste camp: text (pe un rand sau pe mai multe), lista
        derulanta, lista cu selectie."""
        current = self.window.current()
        if current is None:
            return None
        view = current.view
        box = view.page_to_view(data.page_number, data.rect)
        if box is None:
            return None
        parent = view.viewport()
        widget: QWidget
        if data.field_type == FormFieldType.DROPDOWN:
            combo = QComboBox(parent)
            combo.setEditable(data.allow_custom)
            for text, value, _default in data.items:
                combo.addItem(text, value if value is not None else text)
            index = combo.findData(data.value) if data.value is not None else -1
            if index >= 0:
                combo.setCurrentIndex(index)
            elif data.value:
                combo.setEditText(data.value)
            combo.activated.connect(lambda _i: self.commit_editor())
            widget = combo
        elif data.field_type == FormFieldType.LISTBOX:
            box = box.adjusted(0, 0, 0, max(0.0, 80 - box.height()))
            listing = QListWidget(parent)
            listing.setSelectionMode(QListWidget.SelectionMode.MultiSelection
                                     if data.allow_multiple else
                                     QListWidget.SelectionMode.SingleSelection)
            chosen = set((data.value or "").split("\n"))
            for text, value, _default in data.items:
                listing.addItem(text)
                item = listing.item(listing.count() - 1)
                item.setData(Qt.ItemDataRole.UserRole, value if value is not None else text)
                item.setSelected((value if value is not None else text) in chosen)
            widget = listing
        elif data.is_multiline:
            edit = QPlainTextEdit(parent)
            edit.setPlainText(data.value or "")
            widget = edit
        else:
            line = QLineEdit(parent)
            line.setText(data.value or "")
            if data.max_symbols:
                line.setMaxLength(data.max_symbols)  # H-030
            line.returnPressed.connect(self.commit_editor)
            widget = line
        widget.setObjectName("pdf_form_editor")
        widget.setToolTip(data.tooltip or data.field_name)
        widget.setGeometry(box.translated(-view._offset()).toRect())
        widget.installEventFilter(self)
        widget.show()
        widget.setFocus()
        self.editor_widget, self.editing = widget, data
        self._run_event(data, "on_focus")
        view.viewport().update()
        return widget

    def editor_value(self) -> str:
        widget = self.editor_widget
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            if widget.isEditable() and widget.currentText() != widget.itemText(
                    widget.currentIndex()):
                return widget.currentText()
            return str(data) if data is not None else widget.currentText()
        if isinstance(widget, QListWidget):
            return "\n".join(str(widget.item(i).data(Qt.ItemDataRole.UserRole))
                             for i in range(widget.count()) if widget.item(i).isSelected())
        return ""

    def commit_editor(self) -> bool:
        """Valoarea din editor se scrie in camp (cu verificarile H-006)."""
        if self.editor_widget is None or self.editing is None or self._committing:
            return False
        self._committing = True
        data, value = self.editing, self.editor_value()
        self._close_editor()
        try:
            accepted = self._commit(data.field_name, value)
        finally:
            self._committing = False
        self._run_event(data, "on_blur")
        return accepted

    def finish_editing(self) -> None:
        if self.editor_widget is not None:
            self.commit_editor()

    def cancel_editing(self) -> None:
        self._close_editor()

    def _close_editor(self) -> None:
        widget = self.editor_widget
        self.editor_widget, self.editing = None, None
        if widget is not None:
            widget.removeEventFilter(self)
            widget.hide()
            widget.deleteLater()
        current = self.window.current()
        if current is not None:
            current.view.viewport().update()

    def _commit(self, name: str, value: str) -> bool:
        try:
            outcome = self.scripts().commit(name, value)
        except (ValueError, KeyError) as exc:
            _log.info("valoare refuzata pentru %s: %s", name, exc)
            self.window.show_message(tr("pdf.form.value_rejected", field=name))
            return False
        self.perform(outcome)
        self.changed()
        return outcome.accepted

    def _run_event(self, data: FormFieldData, event: str) -> None:
        if data.id is None or not any(e == event for e, _k, _p in data.actions):
            return
        try:
            outcome = self.scripts().run_event(data.id, event)
        except KeyError:
            return
        if any(k == "run_javascript" for e, k, _p in data.actions if e == event):
            self.changed()
        self.perform(outcome)

    def changed(self) -> None:
        """Documentul s-a schimbat: campurile se recitesc, pagina se redeseneaza."""
        self.invalidate()
        current = self.window.current()
        if current is not None:
            current.view.reload()
        self.window._update_state()

    # --- mouse-ul peste campuri (H-040: `Mouse Over`, `Mouse Out`) ---

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # API Qt
        if watched is self.editor_widget:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()  # type: ignore[attr-defined]
                if key == Qt.Key.Key_Escape:
                    self.cancel_editing()
                    return True
                ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier  # type: ignore[attr-defined]
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and ctrl and isinstance(
                        watched, QPlainTextEdit):
                    self.commit_editor()
                    return True
            elif event.type() == QEvent.Type.FocusOut and not self._committing and \
                    not isinstance(watched, QComboBox):
                self.commit_editor()
            return False
        if event.type() == QEvent.Type.MouseMove:
            self._hovered(watched, event)
        return False

    def _hovered(self, viewport: Any, event: Any) -> None:
        current = self.window.current()
        if current is None or viewport is not current.view.viewport():
            return
        view = current.view
        hit = view.view_to_page(QPointF(event.position()) + view._offset())
        data = self.field_at(*hit) if hit is not None else None
        before = self._hover.get(id(current.document))
        now = data.id if data is not None else None
        if before == now:
            return
        self._hover[id(current.document)] = now
        if before is not None:
            old = next((f for f in self.fields() if f.id == before), None)
            if old is not None:
                self._run_event(old, "mouse_exit")
        if data is not None:
            self._run_event(data, "mouse_enter")

    # --- comenzile intoarse de nucleu (H-043…H-058) ---

    def perform(self, outcome: Any) -> None:
        """Mesajele scripturilor si comenzile pentru fereastra."""
        if outcome.timed_out:  # B-041: se noteaza
            from app.core.pdf.javascript import SCRIPT_TIMEOUT_S

            _log.warning("script oprit dupa %s secunde", SCRIPT_TIMEOUT_S)
            self.window.show_message(tr("pdf.js.timeout", seconds=f"{SCRIPT_TIMEOUT_S:g}"))
        for error in outcome.errors:
            _log.info("eroare de script: %s", error)
        for kind, detail in outcome.alerts:
            if kind == "text":
                self.window.show_message(detail)
            else:
                self.window.show_message(tr(f"pdf.form.alert.{kind}", field=detail))
        for name, params in outcome.commands:
            self.run_command(name, params)

    def run_command(self, name: str, params: dict[str, Any]) -> None:
        from app.gui.pdf_view import FitMode, ViewMode

        w = self.window
        simple = {
            "first_page": lambda: w._on_view("first_page"),
            "last_page": lambda: w._on_view("last_page"),
            "next_page": lambda: w._on_view("next_page"),
            "prev_page": lambda: w._on_view("previous_page"),
            "go_back": lambda: w._on_view("back"),
            "go_forward": lambda: w._on_view("forward"),
            "single_page": lambda: w.set_mode(ViewMode.ONE_PAGE),
            "two_pages": lambda: w.set_mode(ViewMode.TWO_PAGE),
            "single_page_scroll": lambda: w.set_mode(ViewMode.ONE_PAGE_SCROLLING),
            "two_pages_scroll": lambda: w.set_mode(ViewMode.TWO_PAGE_SCROLLING),
            "zoom_100": lambda: w.set_zoom(100),
            "fit_width": lambda: w.set_fit(FitMode.FIT_WIDTH),
            "fit_page": lambda: w.set_fit(FitMode.BEST_FIT),
            "full_screen": w.toggle_full_screen,
            "toggle_pages": lambda: w.show_pane(0),
            "toggle_bookmarks": lambda: w.show_pane(1),
            "toggle_attachments": lambda: w.show_pane(3),
            "toggle_signatures": lambda: w.show_pane(4),
            "reset_form": self.reset_form,
            "save_form_as": w.save_as,
            "print_form": w.print_current,
            "close_document": w.close_current,
            "exit_application": w.close,
            "search_document": lambda: w.open_search("find"),
            "document_properties": w.show_properties,
            "scan_pages": w.add_pages_from_scanner,
        }
        if name in simple:
            simple[name]()
        elif name == "go_to_page":
            w._go_to(int(params.get("page", 1)))
        elif name == "open_file":
            self.open_file(str(params.get("file", "")))
        elif name == "follow_link":
            url = str(params.get("url", ""))
            if w.ask_allow("link", url):
                w.open_external(QUrl(url))
        elif name == "send_form":
            self.send_form(str(params.get("to", "")), str(params.get("format", "pdf")))
        elif name == "focus":
            target = next((f for f in self.fields() if f.field_name == params.get("field")),
                          None)
            if target is not None and target.field_type in TEXT_EDITORS:
                self.open_editor(target)

    def open_file(self, name: str) -> None:
        """H-047: fisierul, relativ la document; se cere `Allow` inainte (B-034)."""
        document = self._document()
        path = Path(name.removeprefix("file://"))
        if not path.is_absolute() and document is not None and document.path is not None:
            path = document.path.parent / path
        if not self.window.ask_allow("attachment", path.name):
            return
        if path.suffix.lower() == ".pdf" and path.is_file():
            self.window.open_path(path)
        else:
            self.window.open_external(QUrl.fromLocalFile(str(path)))

    # --- datele formularului, golirea, trimiterea (H-003…H-005, H-023, H-049) ---

    def warn_required(self) -> list[str]:
        """H-023: campurile obligatorii goale doar se semnaleaza; salvarea,
        trimiterea si tiparirea continua."""
        form = self.form()
        if form is None:
            return []
        try:
            names = [f.group_name or f.field_name for f in form.incomplete_required()]
        except (CoreError, ValueError, KeyError):
            return []
        if names:
            self.window.show_message(tr("pdf.form.required_warning",
                                        fields=", ".join(names)))
        return names

    def load_data(self, path: Path | None = None) -> tuple[int, list[str]] | None:
        """H-003: FDF sau XFDF; campurile necunoscute se raporteaza."""
        form = self.form()
        if form is None:
            return None
        if not form.has_fields():
            self.window.show_message(tr("pdf.form.no_fields"))  # H-007
            return None
        path = path or self.window.ask_form_data_file()
        if path is None:
            return None
        try:
            filled, ignored = form.load_data(path)
        except (CoreError, OSError) as exc:
            self.window.show_message(tr_error(exc) if isinstance(exc, CoreError)
                                     else tr("error.generic"))
            return None
        text = tr("pdf.form.loaded", filled=filled)
        if ignored:
            text += "\n" + tr("pdf.form.ignored", names=", ".join(ignored))
        self.window.show_message(text)
        self.changed()
        return filled, ignored

    def save_data(self, target: tuple[Path, str] | None = None) -> Path | None:
        """H-004: FDF, XFDF sau HTML."""
        form = self.form()
        if form is None:
            return None
        if not form.has_fields():
            self.window.show_message(tr("pdf.form.no_fields"))
            return None
        target = target or self.window.ask_form_data_target(form.document)
        if target is None:
            return None
        path, fmt = target
        try:
            form.save_data(path, fmt)
        except (CoreError, OSError) as exc:
            self.window.show_message(tr_error(exc) if isinstance(exc, CoreError)
                                     else tr("error.generic"))
            return None
        return path

    def reset_form(self) -> bool:
        """H-005: cu confirmare; toate campurile se golesc."""
        form = self.form()
        if form is None or not form.has_fields():
            return False
        if not self.window.ask_confirm(tr("pdf.form.reset_confirm")):
            return False
        form.reset()
        self.changed()
        return True

    def send_form(self, to: str, fmt: str) -> Path | None:
        """H-049, B-036: confirmare, avertismentul pentru obligatorii (H-023), apoi
        mesajul `.eml` cu fisierul atasat; un URL nu se foloseste (offline)."""
        from app.core.export.send import write_eml
        from app.core.pdf.form_actions import submission, submit_target

        form = self.form()
        if form is None:
            return None
        kind, address = submit_target(to)
        if not self.window.ask_allow("form", address):
            return None
        self.warn_required()
        if kind != "email":
            self.window.show_message(tr("pdf.form.send_offline", target=address))
            return None
        target = self.window.ask_save_path(form.document, ".eml")
        if target is None:
            return None
        folder = Path(tempfile.mkdtemp(prefix="doculens-formular-"))
        try:
            attachment = submission(form, fmt, folder)
            message = write_eml(target, [attachment], to=address, subject=attachment.stem)
        except (CoreError, OSError, ValueError) as exc:
            self.window.show_message(tr_error(exc) if isinstance(exc, CoreError)
                                     else tr("error.generic"))
            return None
        self.window.show_message(tr("pdf.form.sent", path=str(message)))
        return message


def ask_form_data_file(parent: QWidget) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(parent, tr("pdf.action.load_form_data"), "",
                                          tr("pdf.form.filter.data"))
    return Path(path) if path else None


def ask_form_data_target(parent: QWidget, document: Any) -> tuple[Path, str] | None:
    stem = document.path.with_suffix("") if document.path else Path(tr("pdf.untitled"))
    filters = {tr(key): fmt for fmt, key in DATA_FILTERS.items()}
    path, chosen = QFileDialog.getSaveFileName(parent, tr("pdf.action.save_form_data"),
                                               str(stem) + ".fdf", ";;".join(filters))
    if not path:
        return None
    fmt = filters.get(chosen) or Path(path).suffix.lstrip(".").lower() or "fdf"
    if fmt not in DATA_FILTERS:
        fmt = "fdf"
    target = Path(path)
    if target.suffix.lower() != "." + fmt:
        target = target.with_suffix("." + fmt)
    return target, fmt
