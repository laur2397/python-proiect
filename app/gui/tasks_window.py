"""Sarcinile automate in interfata (faza 13, pasul 13.3): T-001…T-021, T-100…T-107.

`Tools > Automated Tasks` (si cardul din Lansator) deschide managerul: lista
sarcinilor livrate si proprii, cu toolbarul de creare, modificare, copiere,
stergere, import, export si rulare (T-001, T-002, T-019). `New` / `Modify` deschid
editorul `Task Settings` (T-100…T-105). Regulile sunt in
`app.core.automation.tasks`; aici numai afisarea si alegerile utilizatorului.

Dialogurile modale trec prin `exec_dialog`, alegerile de fisiere prin `pick_*` si
confirmarile prin `confirm`, ca testele sa le poata inlocui.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.automation.tasks import (
    BUILTIN_PREFIX,
    DOCUMENT_FORMATS,
    IMAGE_FORMATS,
    TASK_FILE_SUFFIX,
    AutomatedTask,
    TaskStep,
    add_step,
    remove_step,
    validate_steps,
)
from app.core.errors import CoreError, ShortcutConflictError, TaskValidationError
from app.gui.i18n import tr


def task_title(task: AutomatedTask | str) -> str:
    """Numele afisat: sarcinile livrate au cheie de traducere (decizia 8)."""
    name = task if isinstance(task, str) else task.name
    return tr(name) if name.startswith(BUILTIN_PREFIX) else name


def step_title(step: TaskStep) -> str:
    """T-102: numele pasului, ca in panoul de pasi."""
    p = step.parameters
    if step.step_type == "get_images":
        return tr(f"tasks.step.get_images.{p.get('source', 'files')}")
    if step.step_type in ("save", "send_to"):
        return tr(f"tasks.step.{step.step_type}.{p.get('kind', 'document')}")
    return tr(f"tasks.step.{step.step_type}")


SAVE_MENU = (("save", "document"), ("send_to", "app"), ("send_to", "email_document"),
             ("save", "images"), ("send_to", "email_images"), ("save", "project"))
"""T-011…T-016: meniul `Save/Send ▾`, in ordinea din cerinta."""


# --- editorul (T-100…T-107) ---------------------------------------------------------------

class TaskEditor(QDialog):
    """T-100: `Task Settings`: in stanga panoul `Task steps`, in dreapta numele si
    configurarea pasului ales."""

    def __init__(self, runner: Any, task: AutomatedTask | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("task_editor")
        self.setWindowTitle(tr("tasks.editor.title"))
        self.runner = runner
        self.previous = task.name if task is not None else None
        self.task = AutomatedTask(task.name, [TaskStep(s.step_type, dict(s.parameters))
                                              for s in task.steps],
                                  shortcut=task.shortcut, description=task.description) \
            if task is not None else AutomatedTask("")
        self.saved: AutomatedTask | None = None
        layout = QVBoxLayout(self)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        body.addWidget(self._palette())
        right = QVBoxLayout()
        body.addLayout(right, 1)
        form = QFormLayout()
        self.name = QLineEdit(self.task.name)
        self.name.setObjectName("task_name")
        form.addRow(tr("tasks.editor.name"), self.name)
        self.shortcut = QKeySequenceEdit()  # T-020
        self.shortcut.setObjectName("task_shortcut")
        if self.task.shortcut:
            from PySide6.QtGui import QKeySequence

            self.shortcut.setKeySequence(QKeySequence(self.task.shortcut))
        form.addRow(tr("tasks.editor.shortcut"), self.shortcut)
        right.addLayout(form)
        self.steps = QListWidget()
        self.steps.setObjectName("task_steps_list")
        self.steps.currentRowChanged.connect(self._show_step)
        right.addWidget(self.steps, 1)
        self.remove_button = QPushButton(tr("tasks.editor.remove_step"))
        self.remove_button.setObjectName("task_remove_step")
        self.remove_button.clicked.connect(self.remove_current)
        right.addWidget(self.remove_button)
        self.config = QStackedWidget()
        self.config.setObjectName("task_step_config")
        self.hint = QLabel(tr("tasks.editor.choose_first"))  # T-104
        self.hint.setObjectName("task_hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config.addWidget(self.hint)
        right.addWidget(self.config, 1)
        self.message = QLabel()
        self.message.setObjectName("task_message")
        self.message.setProperty("warning", True)
        self.message.setWordWrap(True)
        self.message.hide()
        layout.addWidget(self.message)
        bottom = QHBoxLayout()  # T-105: `Help`, `Finish`, `Cancel`
        self.help = QPushButton(tr("tasks.editor.help"))
        self.help.setObjectName("task_help")
        self.help.clicked.connect(self.show_help)
        bottom.addWidget(self.help)
        bottom.addStretch(1)
        self.finish_button = QPushButton(tr("tasks.editor.finish"))
        self.finish_button.setObjectName("task_finish")
        self.finish_button.setDefault(True)
        self.finish_button.clicked.connect(self.finish)
        cancel = QPushButton(tr("tasks.editor.cancel"))
        cancel.setObjectName("task_cancel")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(self.finish_button)
        bottom.addWidget(cancel)
        layout.addLayout(bottom)
        self.resize(820, 560)
        self._refresh()

    # --- panoul de pasi (T-101…T-103) ---

    def _palette(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("task_palette")
        col = QVBoxLayout(panel)
        col.addWidget(QLabel(tr("tasks.editor.steps")))
        col.addWidget(QLabel(tr("tasks.editor.project")))  # T-101
        self.project_buttons: dict[str, QPushButton] = {}
        for mode in ("new", "existing", "current"):
            button = QPushButton(tr(f"tasks.project.{mode}"))
            button.setObjectName(f"task_project_{mode}")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, m=mode: self.choose_project(m))
            self.project_buttons[mode] = button
            col.addWidget(button)
        self.groups: dict[str, QWidget] = {}
        for key, source in (("open", "files"), ("scan", "scan")):  # T-102
            button = QPushButton(tr(f"tasks.palette.{key}"))
            button.setObjectName(f"task_palette_{key}")
            button.clicked.connect(lambda _=False, s=source: self.choose_source(s))
            self.groups[key] = button
            col.addWidget(button)
        for key, kind in (("preprocess", "preprocess"), ("analyze", "analyze"),
                          ("ocr", "recognize")):
            button = QPushButton(tr(f"tasks.palette.{key}"))
            button.setObjectName(f"task_palette_{key}")
            button.clicked.connect(lambda _=False, k=kind: self.add(TaskStep(k)))
            self.groups[key] = button
            col.addWidget(button)
        save = QToolButton()
        save.setObjectName("task_palette_save")
        save.setText(tr("tasks.palette.save"))
        save.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(save)
        self.save_actions: dict[tuple[str, str], QAction] = {}
        for kind, sub in SAVE_MENU:
            action = menu.addAction(tr(f"tasks.step.{kind}.{sub}"))
            action.setObjectName(f"task_add_{kind}_{sub}")
            action.triggered.connect(lambda _=False, k=kind, s=sub: self.add_output(k, s))
            self.save_actions[(kind, sub)] = action
        save.setMenu(menu)
        self.groups["save"] = save
        col.addWidget(save)
        col.addStretch(1)
        return panel

    def _first(self) -> TaskStep | None:
        return self.task.steps[0] if self.task.steps else None

    def choose_project(self, mode: str) -> None:
        """T-006: primul pas e proiectul; sursa implicita e `Open image or PDF`."""
        first = self._first()
        if first is None:
            self.task.steps.insert(0, TaskStep("get_images", {"project": mode,
                                                              "source": "files"}))
        else:
            first.parameters["project"] = mode
        self._refresh(0)

    def choose_source(self, source: str) -> None:
        """T-007: `Open image or PDF` sau `Scan`."""
        first = self._first()
        if first is not None:
            first.parameters["source"] = source
            self._refresh(0)

    def add(self, step: TaskStep) -> None:
        """T-010: recunoasterea aduce si analiza (in nucleu, `add_step`)."""
        if self._first() is None:
            return
        if step.step_type == "analyze":
            step.parameters.setdefault("mode", "auto")
        index = next((i for i, s in enumerate(self.task.steps)
                      if s.step_type in ("save", "send_to")), None)
        add_step(self.task, step, index)
        self._refresh(self.task.steps.index(step))

    def add_output(self, kind: str, sub: str) -> None:
        params: dict[str, Any] = {"kind": sub}
        if kind == "save" and sub == "document":
            params.update(format="pdf", folder="", timestamped_subfolder=False,
                          image_only=False)
        elif kind == "save" and sub == "images":
            params.update(format="tiff", folder="", multipage=True)
        elif kind == "save":
            params.update(path="")
        self.task.steps.append(TaskStep(kind, params))
        self._refresh(len(self.task.steps) - 1)

    def remove_current(self) -> None:
        """T-017: primul pas nu se sterge; T-010: analiza ia cu ea recunoasterea."""
        row = self.steps.currentRow()
        if row < 0:
            return
        try:
            remove_step(self.task, row)
        except TaskValidationError:
            self._say(tr("tasks.error.first_step", n=1))
            return
        self._refresh(min(row, len(self.task.steps) - 1))

    def _refresh(self, select: int | None = None) -> None:
        first = self._first()
        for mode, button in self.project_buttons.items():  # T-101: chenarul celui ales
            button.setChecked(first is not None and first.parameters.get("project") == mode)
        for widget in self.groups.values():  # T-103: gri pana la primul pas
            widget.setEnabled(first is not None)
        self.steps.blockSignals(True)
        self.steps.clear()
        for i, step in enumerate(self.task.steps):
            self.steps.addItem(tr("tasks.editor.step_n", n=i + 1, name=step_title(step)))
        self.steps.blockSignals(False)
        self.remove_button.setEnabled(bool(self.task.steps))
        if select is not None and 0 <= select < len(self.task.steps):
            self.steps.setCurrentRow(select)
            self._show_step(select)
        else:
            self._show_step(-1)

    # --- configurarea pasului ales ---

    def _show_step(self, row: int) -> None:
        while self.config.count() > 1:
            widget = self.config.widget(1)
            self.config.removeWidget(widget)
            widget.deleteLater()
        if row < 0 or row >= len(self.task.steps):
            self.config.setCurrentWidget(self.hint)
            return
        page = StepPanel(self.task.steps[row], self.runner)
        self.config.addWidget(page)
        self.config.setCurrentWidget(page)

    def current_panel(self) -> StepPanel | None:
        widget = self.config.currentWidget()
        return widget if isinstance(widget, StepPanel) else None

    # --- terminarea (T-018) ---

    def _say(self, text: str) -> None:
        self.message.setText(text)
        self.message.show()

    def build(self) -> AutomatedTask:
        self.task.name = self.name.text().strip()
        shortcut = self.shortcut.keySequence().toString()
        self.task.shortcut = shortcut or None
        return self.task

    def finish(self) -> bool:
        """T-018: pasii trebuie sa fie coerenti; mesajul spune ce pas lipseste."""
        task = self.build()
        try:
            if not task.name:
                raise TaskValidationError("", step_index=-1, reason="name")
            validate_steps(task.steps)
            self.runner.save(task, previous_name=self.previous)
        except TaskValidationError as exc:
            n = int(exc.params.get("step_index", -1))
            self._say(tr(f"tasks.error.{exc.params.get('reason')}", n=n + 1))
            return False
        except ShortcutConflictError as exc:  # T-020
            self._say(tr("tasks.error.shortcut", shortcut=exc.params.get("shortcut", "")))
            return False
        except CoreError as exc:
            self._say(exc.message or exc.code)
            return False
        self.saved = task
        self.accept()
        return True

    def show_help(self) -> None:
        QMessageBox.information(self, tr("tasks.editor.title"), tr("tasks.editor.help_text"))


class StepPanel(QWidget):
    """Campurile pasului ales; scrie direct in `step.parameters`."""

    def __init__(self, step: TaskStep, runner: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"step_panel_{step.step_type}")
        self.step = step
        self.fields: dict[str, QWidget] = {}
        form = QFormLayout(self)
        form.addRow(QLabel(f"<b>{step_title(step)}</b>"))
        p = step.parameters
        kind = step.step_type
        if kind == "get_images" and p.get("project") == "existing":
            form.addRow(tr("tasks.field.project_path"), self._path("project_path", folder=True))
        elif kind == "analyze":  # T-009
            form.addRow(tr("tasks.field.analyze"), self._combo(
                "mode", [(m, tr(f"tasks.analyze.{m}")) for m in ("auto", "manual", "template")]))
            names = _templates(runner)
            form.addRow(tr("tasks.field.template"),
                        self._combo("template", [("", "")] + [(n, n) for n in names]))
            form.addRow(self._check("ask_template", tr("tasks.field.ask_template")))  # T-107
        elif kind == "recognize":
            line = QLineEdit(", ".join(p.get("languages") or []))
            line.setObjectName("step_languages")
            line.setPlaceholderText(tr("tasks.field.languages_hint"))
            line.textChanged.connect(lambda t: p.__setitem__(
                "languages", [c.strip() for c in t.split(",") if c.strip()]))
            self.fields["languages"] = line
            form.addRow(tr("tasks.field.languages"), line)
        elif kind == "save" and p.get("kind") in ("document", "images"):
            formats = DOCUMENT_FORMATS if p.get("kind") == "document" else IMAGE_FORMATS
            form.addRow(tr("tasks.field.format"), self._combo(
                "format", [(f.value, tr(f"format.{f.value}")) for f in formats]))
            form.addRow(tr("tasks.field.folder"), self._path("folder", folder=True))
            if p.get("kind") == "document":  # T-011
                form.addRow(self._check("image_only", tr("tasks.field.image_only")))
                form.addRow(self._check("timestamped_subfolder", tr("tasks.field.timestamped")))
            else:  # T-014
                form.addRow(self._check("multipage", tr("tasks.field.multipage")))
        elif kind == "save":  # T-016
            form.addRow(tr("tasks.field.project_path"), self._path("path", folder=True))
        elif kind == "send_to" and p.get("kind") == "app":  # T-012
            form.addRow(tr("tasks.field.app"), self._path("app", folder=False))

    def _combo(self, key: str, values: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"step_{key}")
        for value, text in values:
            combo.addItem(text, value)
        index = combo.findData(self.step.parameters.get(key, values[0][0] if values else ""))
        combo.setCurrentIndex(max(index, 0))
        self.step.parameters[key] = combo.currentData()
        combo.currentIndexChanged.connect(
            lambda _i: self.step.parameters.__setitem__(key, combo.currentData()))
        self.fields[key] = combo
        return combo

    def _check(self, key: str, text: str) -> QCheckBox:
        box = QCheckBox(text)
        box.setObjectName(f"step_{key}")
        box.setChecked(bool(self.step.parameters.get(key)))
        box.toggled.connect(lambda v: self.step.parameters.__setitem__(key, bool(v)))
        self.fields[key] = box
        return box

    def _path(self, key: str, *, folder: bool) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        line = QLineEdit(str(self.step.parameters.get(key) or ""))
        line.setObjectName(f"step_{key}")
        line.textChanged.connect(lambda t: self.step.parameters.__setitem__(key, t.strip()))
        browse = QPushButton(tr("tasks.field.browse"))

        def pick() -> None:
            chosen = QFileDialog.getExistingDirectory(self) if folder else \
                QFileDialog.getOpenFileName(self)[0]
            if chosen:
                line.setText(chosen)
        browse.clicked.connect(pick)
        h.addWidget(line, 1)
        h.addWidget(browse)
        self.fields[key] = line
        return row


def _templates(runner: Any) -> list[str]:
    """Sabloanele de zone din biblioteca (M-032)."""
    con = runner._con
    return [r[0] for r in con.execute("SELECT name FROM area_template ORDER BY name")]


# --- managerul (T-001, T-002, T-019, T-021) ---------------------------------------------

class TasksManager(QDialog):
    """T-001: lista sarcinilor livrate si proprii; T-002: toolbarul."""

    run_requested = Signal(str)
    """T-019: numele sarcinii de rulat (o ruleaza aplicatia: fisiere, scaner, proiect)."""

    def __init__(self, runner: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tasks_manager")
        self.setWindowTitle(tr("tasks.title"))
        self.runner = runner
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.toolbar.setObjectName("tasks_toolbar")
        self.actions: dict[str, QAction] = {}
        for key, slot in (("new", self.new_task), ("modify", self.modify_task),
                          ("copy", self.copy_task), ("delete", self.delete_task),
                          ("import", self.import_task), ("export", self.export_task),
                          ("run", self.run_task)):
            action = self.toolbar.addAction(tr(f"tasks.action.{key}"))
            action.setObjectName(f"tasks_{key}")
            action.triggered.connect(lambda _=False, f=slot: f())
            self.actions[key] = action
        layout.addWidget(self.toolbar)
        self.list = QListWidget()
        self.list.setObjectName("tasks_list")
        self.list.currentRowChanged.connect(self._selection_changed)
        self.list.itemActivated.connect(lambda _item: self.run_task())
        layout.addWidget(self.list, 1)
        self.message = QLabel()
        self.message.setObjectName("tasks_message")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.resize(520, 480)
        self.refresh()

    # --- puncte de inlocuire pentru teste ---

    def exec_dialog(self, dialog: QDialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def confirm(self, text: str) -> bool:
        return QMessageBox.question(self, tr("tasks.title"), text) == \
            QMessageBox.StandardButton.Yes

    def pick_open(self) -> Path | None:
        chosen, _ = QFileDialog.getOpenFileName(self, tr("tasks.action.import"), "",
                                                tr("tasks.filter"))
        return Path(chosen) if chosen else None

    def pick_save(self, name: str) -> Path | None:
        chosen, _ = QFileDialog.getSaveFileName(self, tr("tasks.action.export"),
                                                f"{name}{TASK_FILE_SUFFIX}", tr("tasks.filter"))
        return Path(chosen) if chosen else None

    # --- lista ---

    def refresh(self, select: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for task in self.runner.all_tasks():
            text = task_title(task)
            if task.shortcut:
                text += f"    {task.shortcut}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, task.name)
            if task.is_builtin:
                item.setToolTip(tr("tasks.builtin_hint"))
            self.list.addItem(item)
            if task.name == select:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self._selection_changed()

    def selected(self) -> AutomatedTask | None:
        item = self.list.currentItem()
        return self.runner.task(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def select(self, name: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(i)

    def _selection_changed(self, *_: Any) -> None:
        task = self.selected()
        own = task is not None and not task.is_builtin
        for key in ("modify", "delete"):  # T-003
            self.actions[key].setEnabled(own)
        for key in ("copy", "export", "run"):
            self.actions[key].setEnabled(task is not None)

    # --- comenzile ---

    def new_task(self) -> AutomatedTask | None:
        """T-005: editorul gol."""
        return self._edit(None)

    def modify_task(self) -> AutomatedTask | None:
        task = self.selected()
        if task is None or task.is_builtin:
            return None
        return self._edit(task)

    def _edit(self, task: AutomatedTask | None) -> AutomatedTask | None:
        editor = TaskEditor(self.runner, task, parent=self)
        self.editor = editor
        if self.exec_dialog(editor) and editor.saved is not None:
            self.refresh(editor.saved.name)
            return editor.saved
        return None

    def copy_task(self) -> AutomatedTask | None:
        """T-003: orice sarcina se duplica; copia unei sarcini livrate primeste
        numele tradus."""
        task = self.selected()
        if task is None:
            return None
        copy = self.runner.duplicate(task.name, task_title(task) if task.is_builtin else None)
        self.refresh(copy.name)
        return copy

    def delete_task(self) -> bool:
        task = self.selected()
        if task is None or task.is_builtin:
            return False
        if not self.confirm(tr("tasks.confirm_delete", name=task.name)):
            return False
        self.runner.delete(task.name)
        self.refresh()
        return True

    def import_task(self) -> AutomatedTask | None:
        """T-021."""
        path = self.pick_open()
        if path is None:
            return None
        try:
            task = self.runner.import_task(path)
        except CoreError as exc:
            self.message.setText(tr("tasks.import_failed", reason=exc.message or exc.code))
            return None
        self.refresh(task.name)
        return task

    def export_task(self) -> Path | None:
        task = self.selected()
        if task is None:
            return None
        path = self.pick_save(task_title(task))
        if path is None:
            return None
        self.runner.export_task(task.name, path)
        self.message.setText(tr("tasks.exported", path=str(path)))
        return path

    def run_task(self) -> None:
        task = self.selected()
        if task is not None:
            self.run_requested.emit(task.name)
