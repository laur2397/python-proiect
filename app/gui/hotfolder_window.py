"""Hot Folder in interfata (faza 13, pasul 13.4): S-001…S-004, S-015…S-020,
S-060…S-071, S-200…S-217.

Fereastra are toolbarul din S-200 (`New`, importul si exportul, `Start Now`,
`Start on Schedule`, `Stop`, `Modify`, `Copy`, `Delete`, jurnalizarea,
notificarile, `Log`), lista sarcinilor (S-003, S-201) si bara de stare cu
contorul de pagini (S-202). Un ceas (`QTimer`, 15 secunde) cheama
`HotFolderService.tick` (faza_13_pasi.md, decizia 1); procesarea ruleaza pe firul
interfetei, cu evenimentele procesate intre fisiere (decizia 11 din faza 6b).

Iconul din bara de sistem apare numai cand exista cel putin o sarcina (S-002);
notificarile de la final sunt mesajele lui (S-066). Hot Folder ruleaza cat
aplicatia e deschisa: inchiderea ferestrei o ascunde in bara de sistem (S-005).

Dialogul `Task Settings` (S-204…S-217) construieste un `HotFolderTask`; regulile
sunt in `app.core.automation.hotfolder`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDateTime, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.automation.hotfolder import (
    FILE_TYPES,
    HFT_SUFFIX,
    NAME_MACROS,
    PROJECT_FORMAT,
    HotFolderService,
    HotFolderStep,
    HotFolderTask,
    display_status,
    expand_name,
    is_ocr_project,
    summary_text,
)
from app.core.errors import CoreError, TaskValidationError
from app.core.model import ExportFormat
from app.gui import icons
from app.gui.i18n import tr, tr_error

TICK_MS = 15_000
"""Cat de des se verifica sarcinile pornite (decizia 1)."""

COLUMNS = ("name", "path", "status", "next_start")
"""S-003, S-201: numele (cu icon de ceas), calea, statusul, `Next Start Time`."""

SAVE_FORMATS = (ExportFormat.PDF, ExportFormat.PDFA, ExportFormat.DOCX, ExportFormat.RTF,
                ExportFormat.ODT, ExportFormat.XLSX, ExportFormat.CSV, ExportFormat.PPTX,
                ExportFormat.TXT, ExportFormat.HTML, ExportFormat.EPUB, ExportFormat.FB2,
                ExportFormat.DJVU)
IMAGE_SAVE_FORMATS = (ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG)

PALETTE = (
    ("schedule", (("once", True), ("recurring", True))),
    ("open", (("folder", True), ("ftp", False), ("outlook", False), ("project", True))),
    ("process", (("process", True),)),
    ("save", (("save", True),)),
)
"""S-205: categoriile paletei; FTP si Outlook sunt dezactivate (decizia 5)."""

SAVE_RESULTS = (("document", True), ("sharepoint", False), ("images", True),
                ("project", True))
"""S-206: dropdown-ul `Save results`; `Save to SharePoint` dezactivat (decizia 5)."""


def _qtime(value: str | None) -> QTime:
    hour, minute = (value or "09:00").split(":")
    return QTime(int(hour), int(minute))


# --- pasii din dialog (S-207…S-216) ------------------------------------------------------

class StepBox(QGroupBox):
    """S-207: panoul unui pas adaugat, cu antetul `Step N: <nume>` si `X`."""

    removed = Signal(object)
    changed = Signal()

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName(f"hf_step_{kind}")
        outer = QVBoxLayout(self)
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("hf_step_title")
        head.addWidget(self.title, 1)
        close = QToolButton()
        close.setObjectName("hf_step_remove")
        close.setText("✕")
        close.clicked.connect(lambda: self.removed.emit(self))
        head.addWidget(close)
        outer.addLayout(head)
        self.form = QFormLayout()
        outer.addLayout(self.form)

    def set_number(self, n: int) -> None:
        self.title.setText(tr("hotfolder.step_n", n=n,
                              name=tr(f"hotfolder.palette.{self.kind}")))

    def apply(self, task: HotFolderTask) -> None:
        """Scrie campurile pasului in sarcina."""

    def path_row(self, key: str, value: str = "", *, folder: bool = True) -> QLineEdit:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        line = QLineEdit(value)
        line.setObjectName(f"hf_{key}")
        line.textChanged.connect(lambda *_: self.changed.emit())
        browse = QPushButton(tr("hotfolder.browse"))
        browse.setObjectName(f"hf_{key}_browse")

        def pick() -> None:
            chosen = QFileDialog.getExistingDirectory(self) if folder else \
                QFileDialog.getOpenFileName(self)[0]
            if chosen:
                line.setText(chosen)
        browse.clicked.connect(pick)
        h.addWidget(line, 1)
        h.addWidget(browse)
        self.form.addRow(tr(f"hotfolder.field.{key}"), row)
        return line


class OnceStep(StepBox):
    """S-031: `Run once`, data si ora."""

    def __init__(self, task: HotFolderTask) -> None:
        super().__init__("once")
        self.when = QDateTimeEdit()
        self.when.setObjectName("hf_once_at")
        self.when.setCalendarPopup(True)
        at = QDateTime.fromString(task.schedule_at, Qt.DateFormat.ISODate) \
            if task.schedule_at else QDateTime.currentDateTime().addSecs(3600)
        self.when.setDateTime(at)
        self.when.dateTimeChanged.connect(lambda *_: self.changed.emit())
        self.form.addRow(tr("hotfolder.field.once_at"), self.when)

    def apply(self, task: HotFolderTask) -> None:
        task.schedule_kind = "once"
        task.schedule_interval_minutes = None
        task.schedule_at = self.when.dateTime().toString(Qt.DateFormat.ISODate)


class RecurringStep(StepBox):
    """S-209: `Every minute`, `Every day`, `Every week`, `Every month`, cu ora."""

    KINDS = ("interval", "daily", "weekly", "monthly")

    def __init__(self, task: HotFolderTask) -> None:
        super().__init__("recurring")
        self.group = QButtonGroup(self)
        self.radios: dict[str, QRadioButton] = {}
        row = QVBoxLayout()
        for kind in self.KINDS:
            radio = QRadioButton(tr(f"hotfolder.recurring.{kind}"))
            radio.setObjectName(f"hf_recurring_{kind}")
            radio.toggled.connect(lambda *_: self.changed.emit())
            self.group.addButton(radio)
            self.radios[kind] = radio
            row.addWidget(radio)
        self.form.addRow(row)
        current = task.schedule_kind if task.schedule_kind in self.KINDS else "interval"
        self.radios[current].setChecked(True)
        self.time = QTimeEdit(_qtime(task.schedule_time))  # campul de ora cu spinner
        self.time.setObjectName("hf_recurring_time")
        self.time.setDisplayFormat("HH:mm")
        self.form.addRow(tr("hotfolder.field.time"), self.time)
        self.weekday = QComboBox()
        self.weekday.setObjectName("hf_recurring_weekday")
        for d in range(7):
            self.weekday.addItem(tr(f"hotfolder.weekday.{d}"), d)
        self.monthday = QSpinBox()
        self.monthday.setObjectName("hf_recurring_monthday")
        self.monthday.setRange(1, 31)
        if task.schedule_days and task.schedule_kind == "weekly":
            self.weekday.setCurrentIndex(int(task.schedule_days[0]))
        if task.schedule_days and task.schedule_kind == "monthly":
            self.monthday.setValue(int(task.schedule_days[0]))
        self.form.addRow(tr("hotfolder.field.weekday"), self.weekday)
        self.form.addRow(tr("hotfolder.field.monthday"), self.monthday)

    def apply(self, task: HotFolderTask) -> None:
        kind = next(k for k, r in self.radios.items() if r.isChecked())
        task.schedule_kind = kind
        task.schedule_interval_minutes = 1 if kind == "interval" else None
        task.schedule_time = None if kind == "interval" else self.time.time().toString("HH:mm")
        task.schedule_days = {"weekly": (int(self.weekday.currentData()),),
                              "monthly": (self.monthday.value(),)}.get(kind, ())


class FolderStep(StepBox):
    """S-033, S-037, S-038, S-210, S-211: folderul, subfolderele, tipul de fisier,
    originalele."""

    def __init__(self, task: HotFolderTask) -> None:
        super().__init__("folder")
        self.path = self.path_row("source_path", task.source_path)
        self.subfolders = QCheckBox(tr("hotfolder.field.subfolders"))
        self.subfolders.setObjectName("hf_subfolders")
        self.subfolders.setChecked(task.include_subfolders)
        self.form.addRow(self.subfolders)
        self.types = QComboBox()
        self.types.setObjectName("hf_file_type")
        for key in FILE_TYPES:
            self.types.addItem(tr(f"hotfolder.file_type.{key}"), key)
        self.types.setCurrentIndex(max(self.types.findData(task.file_pattern), 0))
        self.form.addRow(tr("hotfolder.field.file_type"), self.types)
        self.original = QComboBox()
        self.original.setObjectName("hf_original")
        for key in ("keep", "delete", "move"):
            self.original.addItem(tr(f"hotfolder.original.{key}"), key)
        self.original.setCurrentIndex(max(self.original.findData(task.original_action), 0))
        self.original.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.form.addRow(tr("hotfolder.field.original"), self.original)
        self.move_to = self.path_row("move_to", task.original_move_to or "")

    def apply(self, task: HotFolderTask) -> None:
        task.source_kind = "folder"
        task.source_path = self.path.text().strip()
        task.include_subfolders = self.subfolders.isChecked()
        task.file_pattern = self.types.currentData()
        task.original_action = self.original.currentData()
        task.original_move_to = self.move_to.text().strip() or None


class ProjectStep(StepBox):
    """S-036: sursa e un proiect OCR."""

    def __init__(self, task: HotFolderTask) -> None:
        super().__init__("project")
        self.path = self.path_row("project_path", task.source_path)

    def apply(self, task: HotFolderTask) -> None:
        task.source_kind = "folder"
        task.source_path = self.path.text().strip()
        task.file_pattern = "all"


class ProcessStep(StepBox):
    """S-039…S-045, S-212, S-213: limbile, modul, optiunile, analiza, paginile goale."""

    options_requested = Signal(str)

    def __init__(self, task: HotFolderTask, context: Any) -> None:
        super().__init__("process")
        from app.core.ocr.languages import LanguageRegistry
        from app.gui.convert_screen import LanguagePicker

        p = task.process
        codes = LanguageRegistry(con=context.app_db).all()
        self.languages = LanguagePicker(codes, list(p.get("languages") or ["ron"]))
        self.languages.setObjectName("hf_languages")
        self.languages.model().itemChanged.connect(lambda *_: self.changed.emit())
        self.form.addRow(tr("hotfolder.field.languages"), self.languages)
        self.modes = QButtonGroup(self)
        self.mode_radios: dict[str, QRadioButton] = {}
        modes = QVBoxLayout()
        for mode in ("recognize", "analyze", "preprocess"):
            radio = QRadioButton(tr(f"hotfolder.mode.{mode}"))
            radio.setObjectName(f"hf_mode_{mode}")
            radio.toggled.connect(lambda *_: self.changed.emit())
            self.modes.addButton(radio)
            self.mode_radios[mode] = radio
            modes.addWidget(radio)
        self.mode_radios[p.get("mode", "recognize")].setChecked(True)
        box = QGroupBox(tr("hotfolder.field.processing"))
        box.setLayout(modes)
        self.form.addRow(box)
        buttons = QHBoxLayout()
        for key, tab in (("recognition_options", "ocr"), ("preprocessing_options", "image")):
            button = QPushButton(tr(f"hotfolder.{key}"))  # S-041, S-042
            button.setObjectName(f"hf_{key}")
            button.clicked.connect(lambda _=False, t=tab: self.options_requested.emit(t))
            buttons.addWidget(button)
        self.form.addRow(buttons)
        self.template_check = QCheckBox(tr("hotfolder.field.use_template"))  # S-043
        self.template_check.setObjectName("hf_use_template")
        self.template = QComboBox()
        self.template.setObjectName("hf_template")
        for (name,) in context.app_db.execute("SELECT name FROM area_template ORDER BY name"):
            self.template.addItem(name, name)
        self.template_check.setChecked(bool(p.get("template")))
        if p.get("template"):
            self.template.setCurrentIndex(max(self.template.findData(p["template"]), 0))
        self.form.addRow(self.template_check, self.template)
        self.delete_blank = QCheckBox(tr("hotfolder.field.delete_blank"))  # S-044
        self.delete_blank.setObjectName("hf_delete_blank")
        self.delete_blank.setChecked(bool(p.get("delete_blank")))
        self.form.addRow(self.delete_blank)
        self.move_blank = QCheckBox(tr("hotfolder.field.move_blank"))  # S-045
        self.move_blank.setObjectName("hf_move_blank")
        self.move_blank.setChecked(bool(p.get("blank_folder")))
        self.form.addRow(self.move_blank)
        self.blank_folder = self.path_row("blank_folder", p.get("blank_folder") or "")
        self.delete_blank.toggled.connect(self._blank_state)
        self.move_blank.toggled.connect(self._blank_state)
        self._blank_state()

    def _blank_state(self) -> None:
        """S-045: activ doar cu S-044 bifat."""
        on = self.delete_blank.isChecked()
        self.move_blank.setEnabled(on)
        self.blank_folder.setEnabled(on and self.move_blank.isChecked())
        self.changed.emit()

    def apply(self, task: HotFolderTask) -> None:
        mode = next(m for m, r in self.mode_radios.items() if r.isChecked())
        process: dict[str, Any] = {"mode": mode, "languages": self.languages.codes()}
        if self.template_check.isChecked() and self.template.currentData():
            process["template"] = self.template.currentData()
        if self.delete_blank.isChecked():
            process["delete_blank"] = True
            if self.move_blank.isChecked() and self.blank_folder.text().strip():
                process["blank_folder"] = self.blank_folder.text().strip()
        task.process = process


class SaveStep(StepBox):
    """S-046…S-052, S-215, S-216: formatul, PDF cautabil sau doar-imagine, folderul,
    iesirea si numele cu macrocomenzi si exemplul live."""

    options_requested = Signal(str)

    def __init__(self, kind: str, step: HotFolderStep | None = None) -> None:
        super().__init__(f"save_{kind}")
        self.save_kind = kind
        step = step or HotFolderStep("save", {"kind": kind})
        p = step.parameters
        self.format: QComboBox | None = None
        if kind in ("document", "images"):
            self.format = QComboBox()
            self.format.setObjectName("hf_save_format")
            for fmt in SAVE_FORMATS if kind == "document" else IMAGE_SAVE_FORMATS:
                self.format.addItem(tr(f"format.{fmt.value}"), fmt.value)
            self.format.setCurrentIndex(max(self.format.findData(step.output_format), 0))
            self.format.currentIndexChanged.connect(self._format_changed)
            row = QHBoxLayout()
            row.addWidget(self.format, 1)
            options = QPushButton(tr("hotfolder.options"))
            options.setObjectName("hf_save_options")
            options.clicked.connect(lambda: self.options_requested.emit("formats"))
            row.addWidget(options)
            self.form.addRow(tr("hotfolder.field.save_as"), row)
        if kind == "document":
            self.text_pdf = QRadioButton(tr("hotfolder.field.pdf_text"))  # S-046
            self.text_pdf.setObjectName("hf_pdf_text")
            self.image_pdf = QRadioButton(tr("hotfolder.field.pdf_image"))
            self.image_pdf.setObjectName("hf_pdf_image")
            (self.image_pdf if p.get("image_only") else self.text_pdf).setChecked(True)
            self.image_pdf.toggled.connect(lambda *_: self.changed.emit())
            self.form.addRow(self.text_pdf)
            self.form.addRow(self.image_pdf)
        if kind == "images":
            self.multipage = QCheckBox(tr("hotfolder.field.multipage"))
            self.multipage.setObjectName("hf_multipage")
            self.multipage.setChecked(bool(p.get("multipage", True)))
            self.form.addRow(self.multipage)
        self.folder = self.path_row("output_folder", step.output_folder or "")
        self.output = QComboBox()
        self.output.setObjectName("hf_output")
        for key in ("per_file", "per_folder", "single"):
            self.output.addItem(tr(f"hotfolder.output.{key}"), key)
        self.output.setCurrentIndex(max(self.output.findData(p.get("output", "per_file")), 0))
        self.form.addRow(tr("hotfolder.field.output"), self.output)
        self.name = QLineEdit(step.name_template or "[F]")
        self.name.setObjectName("hf_file_name")
        self.name.textChanged.connect(self._example)
        macros = QHBoxLayout()  # S-216
        self.macro_buttons: dict[str, QPushButton] = {}
        for macro in NAME_MACROS:
            key = macro.strip("[]").replace("#", "n")
            button = QPushButton(macro)
            button.setObjectName(f"hf_macro_{key}")
            button.setToolTip(tr(f"hotfolder.macro.{key}"))
            button.clicked.connect(lambda _=False, m=macro: self.name.insert(m))
            self.macro_buttons[macro] = button
            macros.addWidget(button)
        name_col = QVBoxLayout()
        name_col.addWidget(self.name)
        name_col.addLayout(macros)
        self.example = QLabel()
        self.example.setObjectName("hf_example")
        name_col.addWidget(self.example)
        self.form.addRow(tr("hotfolder.field.file_name"), name_col)
        self._format_changed()

    def _format_changed(self) -> None:
        if self.save_kind == "document" and self.format is not None:
            is_pdf = self.format.currentData() in ("pdf", "pdfa")
            self.text_pdf.setEnabled(is_pdf)
            self.image_pdf.setEnabled(is_pdf)
        self._example()

    def suffix(self) -> str:
        if self.format is None:
            return ""
        fmt = self.format.currentData()
        return {"pdfa": ".pdf", "tiff": ".tif", "jpeg": ".jpg"}.get(fmt, f".{fmt}")

    def _example(self) -> None:
        """S-216: `Example: Document.pdf`, actualizat la fiecare tasta."""
        name = expand_name(self.name.text(), Path(tr("hotfolder.example_source")),
                           datetime.now(), 1)
        self.example.setText(tr("hotfolder.example", name=f"{name}{self.suffix()}"))
        self.changed.emit()

    def step(self) -> HotFolderStep:
        params: dict[str, Any] = {"kind": self.save_kind, "output": self.output.currentData()}
        if self.save_kind == "document":
            params["image_only"] = self.image_pdf.isChecked() and self.image_pdf.isEnabled()
        if self.save_kind == "images":
            params["multipage"] = self.multipage.isChecked()
        fmt = PROJECT_FORMAT if self.format is None else self.format.currentData()
        return HotFolderStep("save", params, fmt, self.folder.text().strip() or None,
                             self.name.text() or "[F]", "number")


# --- dialogul Task Settings (S-204…S-217) -----------------------------------------------

class TaskSettingsDialog(QDialog):
    """S-204: `Task name` sus; in stanga paleta de pasi pe categorii (S-205), in
    dreapta pasii adaugati (S-207); jos `Help`, `Create Task`, `Cancel` (S-217)."""

    options_requested = Signal(str)

    def __init__(self, service: HotFolderService, context: Any,
                 task: HotFolderTask | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hf_task_settings")
        self.setWindowTitle(tr("hotfolder.settings.title"))
        self.service = service
        self.context = context
        self.previous = task.name if task is not None else None
        self.base = task or HotFolderTask("", "folder", "", steps=[])
        self.saved: HotFolderTask | None = None
        self.boxes: list[StepBox] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.base.name)
        self.name.setObjectName("hf_task_name")
        form.addRow(tr("hotfolder.field.task_name"), self.name)
        layout.addLayout(form)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        body.addWidget(self._palette())
        self.area = QVBoxLayout()
        self.placeholder = QLabel(tr("hotfolder.select_steps"))  # S-208
        self.placeholder.setObjectName("hf_select_steps")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.area.addWidget(self.placeholder)
        self.area.addStretch(1)
        holder = QWidget()
        holder.setLayout(self.area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        body.addWidget(scroll, 1)
        self.message = QLabel()
        self.message.setObjectName("hf_message")
        self.message.setWordWrap(True)
        self.message.setProperty("warning", True)
        layout.addWidget(self.message)
        bottom = QHBoxLayout()
        help_link = QLabel(f"<a href='help'>{tr('hotfolder.help')}</a>")  # S-217
        help_link.setObjectName("hf_help")
        help_link.linkActivated.connect(lambda _l: QMessageBox.information(
            self, tr("hotfolder.settings.title"), tr("hotfolder.help_text")))
        bottom.addWidget(help_link)
        bottom.addStretch(1)
        self.create_button = QPushButton(tr("hotfolder.create_task"))
        self.create_button.setObjectName("hf_create_task")
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self.create_task)
        cancel = QPushButton(tr("hotfolder.cancel"))
        cancel.setObjectName("hf_cancel")
        cancel.setFlat(True)
        cancel.clicked.connect(self.reject)
        bottom.addWidget(self.create_button)
        bottom.addWidget(cancel)
        layout.addLayout(bottom)
        self.name.textChanged.connect(self.revalidate)
        self._load(self.base)
        self.resize(900, 640)
        self.revalidate()

    # --- paleta (S-205, S-206) ---

    def _palette(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("hf_palette")
        col = QVBoxLayout(panel)
        self.palette_buttons: dict[str, QWidget] = {}
        self.save_actions: dict[str, QAction] = {}
        for category, items in PALETTE:
            col.addWidget(QLabel(f"<b>{tr(f'hotfolder.category.{category}')}</b>"))
            for key, available in items:
                button: QWidget
                if key == "save":
                    tool = QToolButton()
                    tool.setText(tr("hotfolder.palette.save_results"))
                    tool.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                    menu = QMenu(tool)
                    for sub, ok in SAVE_RESULTS:
                        action = menu.addAction(tr(f"hotfolder.palette.save_{sub}"))
                        action.setObjectName(f"hf_add_save_{sub}")
                        action.setEnabled(ok)
                        if not ok:
                            action.setToolTip(tr("hotfolder.unavailable.sharepoint"))
                        action.triggered.connect(lambda _=False, s=sub: self.add_save(s))
                        self.save_actions[sub] = action
                    tool.setMenu(menu)
                    button = tool
                else:
                    push = QPushButton(tr(f"hotfolder.palette.{key}"))
                    push.clicked.connect(lambda _=False, k=key: self.add_step(k))
                    button = push
                button.setObjectName(f"hf_palette_{key}")
                button.setEnabled(available)
                if not available:
                    button.setToolTip(tr(f"hotfolder.unavailable.{key}"))
                self.palette_buttons[key] = button
                col.addWidget(button)
        col.addStretch(1)
        return panel

    # --- pasii ---

    def _load(self, task: HotFolderTask) -> None:
        if task.source_path:
            self.add_step("project" if is_ocr_project(Path(task.source_path)) else "folder")
            self.add_step("once" if task.schedule_kind == "once" else "recurring")
            self.add_step("process")
        for step in task.steps:
            if step.step_type == "save":
                self.add_save(step.parameters.get("kind", "document"), step)

    def _make(self, key: str) -> StepBox:
        task = self.base
        if key == "once":
            return OnceStep(task)
        if key == "recurring":
            return RecurringStep(task)
        if key == "folder":
            return FolderStep(task)
        if key == "project":
            return ProjectStep(task)
        box = ProcessStep(task, self.context)
        box.options_requested.connect(self.options_requested.emit)
        return box

    def add_step(self, key: str) -> StepBox:
        """Un singur pas de planificare, unul de sursa si unul de procesare: cel nou
        il inlocuieste pe cel vechi din aceeasi categorie."""
        category = next(c for c, items in PALETTE if any(k == key for k, _ in items))
        same = {k for k, _ in dict(PALETTE)[category]}
        for box in [b for b in self.boxes if b.kind in same]:
            self.remove_box(box)
        return self._insert(self._make(key))

    def add_save(self, kind: str, step: HotFolderStep | None = None) -> StepBox:
        """S-052: mai multe pasi de salvare."""
        box = SaveStep(kind, step)
        box.options_requested.connect(self.options_requested.emit)
        return self._insert(box)

    def _insert(self, box: StepBox) -> StepBox:
        box.removed.connect(self.remove_box)
        box.changed.connect(self.revalidate)
        self.boxes.append(box)
        order = {"once": 0, "recurring": 0, "folder": 1, "project": 1, "process": 2}
        self.boxes.sort(key=lambda b: order.get(b.kind, 3))
        for b in self.boxes:
            self.area.removeWidget(b)
        for i, b in enumerate(self.boxes):
            self.area.insertWidget(i + 1, b)
        self._renumber()
        return box

    def remove_box(self, box: StepBox) -> None:
        if box in self.boxes:
            self.boxes.remove(box)
            self.area.removeWidget(box)
            box.deleteLater()
        self._renumber()

    def _renumber(self) -> None:
        for i, box in enumerate(self.boxes, start=1):
            box.set_number(i)
        self.placeholder.setVisible(not self.boxes)
        self.revalidate()

    def box(self, kind: str) -> StepBox | None:
        return next((b for b in self.boxes if b.kind == kind), None)

    # --- sarcina ---

    def build(self) -> HotFolderTask:
        task = HotFolderTask(self.name.text().strip(), "folder", "", steps=[],
                             schedule_kind="", schedule_interval_minutes=None,
                             process={"mode": "recognize", "languages": []})
        for box in self.boxes:
            if isinstance(box, SaveStep):
                task.steps.append(box.step())
            else:
                box.apply(task)
        return task

    def revalidate(self, *_: Any) -> bool:
        """S-217: `Create Task` e gri pana cand sarcina e valida."""
        if not hasattr(self, "create_button"):
            return False
        try:
            self.service.validate(self.build())
        except TaskValidationError as exc:
            self.message.setText(tr(f"hotfolder.error.{exc.params.get('reason')}"))
            self.create_button.setEnabled(False)
            return False
        self.message.setText("")
        self.create_button.setEnabled(True)
        return True

    def create_task(self) -> bool:
        """S-053; S-033, S-047: sursa si iesirile se verifica inainte de salvare."""
        task = self.build()
        try:
            self.service.test_source(task)
            self.service.save(task, previous_name=self.previous)
        except TaskValidationError as exc:
            self.message.setText(tr(f"hotfolder.error.{exc.params.get('reason')}"))
            return False
        except CoreError as exc:
            self.message.setText(tr_error(exc))
            return False
        self.saved = task
        self.accept()
        return True


# --- jurnalul (S-070) ----------------------------------------------------------------------

class LogDialog(QDialog):
    """S-070: `View Log`: randurile din jurnal si fisierul TXT (S-068)."""

    def __init__(self, service: HotFolderService, name: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hf_log")
        self.setWindowTitle(tr("hotfolder.log.title", task=name))
        layout = QVBoxLayout(self)
        entries = service.log_entries(name)
        self.table = QTableWidget(len(entries), 5)
        self.table.setObjectName("hf_log_table")
        self.table.setHorizontalHeaderLabels([tr(f"hotfolder.log.col.{c}") for c in (
            "started", "file", "status", "output", "error")])
        for row, entry in enumerate(entries):
            values = (entry["started_at"], Path(entry["source_file"]).name,
                      tr(f"hotfolder.log.status.{entry['status']}"),
                      Path(entry["output_file"]).name if entry["output_file"] else "",
                      entry["error_message"] or "")
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.log_file = service.log_path(service.task(name))
        self.open_button = QPushButton(tr("hotfolder.log.open_file"))
        self.open_button.setObjectName("hf_log_open")
        self.open_button.setEnabled(self.log_file is not None and self.log_file.exists())
        self.open_button.clicked.connect(self._open)
        layout.addWidget(self.open_button)
        self.resize(760, 420)

    def _open(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if self.log_file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_file)))


# --- fereastra (S-001…S-004, S-060…S-071, S-200…S-203) ----------------------------------

class HotFolderWindow(QMainWindow):
    """Fereastra Hot Folder (`Tools > Hot Folder`, `Ctrl+Shift+F`, S-002)."""

    options_requested = Signal(str)

    def __init__(self, context: Any, *, engine: Any = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hotfolder_window")
        self.setWindowTitle(tr("hotfolder.title"))
        self.context = context
        self.service = HotFolderService(context, engine=engine, tr=tr)
        self.toolbar = self.addToolBar(tr("hotfolder.title"))
        self.toolbar.setObjectName("hf_toolbar")
        self.actions: dict[str, QAction] = {}
        self._build_toolbar()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("hf_tasks")
        self.table.setHorizontalHeaderLabels([tr(f"hotfolder.col.{c}") for c in COLUMNS])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.modify_task())
        self.setCentralWidget(self.table)
        self.counter = QLabel()  # S-202
        self.counter.setObjectName("hf_counter")
        self.counter_info = QLabel("ⓘ")
        self.counter_info.setObjectName("hf_counter_info")
        self.counter_info.setToolTip(tr("hotfolder.counter.info"))
        self.statusBar().addWidget(self.counter, 1)
        self.statusBar().addPermanentWidget(self.counter_info)
        self.tray: QSystemTrayIcon | None = None
        self.notifications: list[str] = []
        """Textele notificarilor aratate (S-066)."""
        self.timer = QTimer(self)
        self.timer.setObjectName("hf_timer")
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)
        self.resize(860, 420)
        self.refresh()

    # --- puncte de inlocuire pentru teste ---

    def exec_dialog(self, dialog: QDialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def confirm(self, text: str) -> bool:
        return QMessageBox.question(self, tr("hotfolder.title"), text) == \
            QMessageBox.StandardButton.Yes

    def pick_open(self) -> Path | None:
        chosen, _ = QFileDialog.getOpenFileName(self, tr("hotfolder.action.import"), "",
                                                tr("hotfolder.filter"))
        return Path(chosen) if chosen else None

    def pick_save(self, name: str) -> Path | None:
        chosen, _ = QFileDialog.getSaveFileName(self, tr("hotfolder.action.export"),
                                                f"{name}{HFT_SUFFIX}", tr("hotfolder.filter"))
        return Path(chosen) if chosen else None

    # --- constructie ---

    def _add(self, key: str, slot: Any, icon: str | None = None) -> QAction:
        action = QAction(tr(f"hotfolder.action.{key}"), self)
        action.setObjectName(f"hf_{key}")
        if icon:
            action.setIcon(icons.icon(icon))
        action.triggered.connect(lambda _=False, f=slot: f())
        self.actions[key] = action
        return action

    def _build_toolbar(self) -> None:
        """S-004, S-200."""
        self.toolbar.addAction(self._add("new", self.new_task, "plus"))
        porting = QToolButton()
        porting.setObjectName("hf_import_export")
        porting.setText(tr("hotfolder.action.import_export"))
        porting.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(porting)
        menu.addAction(self._add("import", self.import_task))
        menu.addAction(self._add("export", self.export_task))
        porting.setMenu(menu)
        self.toolbar.addWidget(porting)
        self.toolbar.addSeparator()
        for key, slot, icon in (("start_now", self.start_now, "recognize"),
                                ("start_schedule", self.start_schedule, "clock"),
                                ("stop", self.stop_task, None)):
            self.toolbar.addAction(self._add(key, slot, icon))
        self.toolbar.addSeparator()
        for key, slot in (("modify", self.modify_task), ("copy", self.copy_task),
                          ("delete", self.delete_task)):
            self.toolbar.addAction(self._add(key, slot))
        self.toolbar.addSeparator()
        for key, setting in (("logging", "hotfolder.logging"),
                             ("notifications", "hotfolder.notifications")):  # S-066, S-067
            action = self._add(key, lambda s=setting, k=key: self._toggle(s, k))
            action.setCheckable(True)
            action.setChecked(bool(self.context.settings.get(setting)))
            self.toolbar.addAction(action)
        self.toolbar.addAction(self._add("log", self.view_log))

    def _toggle(self, setting: str, key: str) -> None:
        self.context.settings.set(setting, self.actions[key].isChecked())

    # --- lista ---

    def refresh(self) -> None:
        """S-003, S-201: numele cu icon de ceas, calea, statusul, ora urmatoare."""
        selected = self.selected_name()
        tasks = self.service.tasks()
        self.table.blockSignals(True)
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            status = display_status(task, processing=self.service.processing == task.name)
            values = (task.name, task.source_path, tr(f"hotfolder.status.{status}"),
                      task.next_run_at.replace("T", " ") if task.next_run_at else "")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setIcon(icons.icon("clock"))
                    item.setData(Qt.ItemDataRole.UserRole, task.name)
                if col == 2 and status == "error" and task.last_error:
                    item.setToolTip(task.last_error)
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        names = [t.name for t in tasks]
        if selected in names:
            self.table.selectRow(names.index(selected))
        elif tasks:
            self.table.selectRow(0)
        self._update_counter()
        self._update_tray(bool(tasks))
        self._selection_changed()

    def _update_counter(self) -> None:
        """S-202: `Pages remaining to recognize <N> / the limit to be renewed in <N> days`."""
        remaining = self.service.pages_remaining()
        if remaining is None:
            self.counter.setText(tr("hotfolder.counter.unlimited"))
        else:
            self.counter.setText(tr("hotfolder.counter", pages=remaining,
                                    days=self.service.days_to_renew()))

    def _update_tray(self, has_tasks: bool) -> None:
        """S-002: iconul apare numai cand exista cel putin o sarcina."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(icons.icon("clock"), self)
            self.tray.setObjectName("hf_tray")
            self.tray.setToolTip(tr("hotfolder.title"))
            self.tray.activated.connect(lambda *_: self.show_window())
        self.tray.setVisible(has_tasks)

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def selected_name(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def select(self, name: str) -> None:
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == name:
                self.table.selectRow(row)

    def _selection_changed(self) -> None:
        name = self.selected_name()
        task = self.service.task(name) if name else None
        running = task is not None and task.status == "running"
        for key in ("start_now", "copy", "delete", "export", "log"):
            self.actions[key].setEnabled(task is not None)
        self.actions["start_schedule"].setEnabled(task is not None and not running)
        self.actions["stop"].setEnabled(running)
        self.actions["modify"].setEnabled(task is not None and not running)  # S-062

    # --- comenzile (S-060…S-065, S-070) ---

    def new_task(self) -> HotFolderTask | None:
        return self._edit(None)

    def modify_task(self) -> HotFolderTask | None:
        """S-062: sarcina trebuie oprita intai."""
        name = self.selected_name()
        if name is None:
            return None
        task = self.service.task(name)
        if task.status == "running":
            self.statusBar().showMessage(tr("hotfolder.error.running"), 5000)
            return None
        return self._edit(task)

    def _edit(self, task: HotFolderTask | None) -> HotFolderTask | None:
        dialog = TaskSettingsDialog(self.service, self.context, task, parent=self)
        dialog.options_requested.connect(self.options_requested.emit)
        self.settings_dialog = dialog
        if self.exec_dialog(dialog) and dialog.saved is not None:
            self.refresh()
            self.select(dialog.saved.name)
            return dialog.saved
        return None

    def copy_task(self) -> HotFolderTask | None:
        name = self.selected_name()
        if name is None:
            return None
        copy = self.service.duplicate(name)
        self.refresh()
        self.select(copy.name)
        return copy

    def delete_task(self) -> bool:
        """S-064: cu confirmare."""
        name = self.selected_name()
        if name is None or not self.confirm(tr("hotfolder.confirm_delete", task=name)):
            return False
        self.service.delete(name)
        self.refresh()
        return True

    def start_schedule(self) -> None:
        """S-060 (`Start on Schedule`): `Scheduled` sau `Watching...`."""
        name = self.selected_name()
        if name is not None:
            self.service.start(name)
            self.refresh()

    def start_now(self) -> Any:
        """S-060 (`Start Now`): `Running...` pana la final."""
        name = self.selected_name()
        if name is None:
            return None
        summary = self.service.run_now(name, progress=self._progress)
        self._finished(summary)
        return summary

    def stop_task(self) -> None:
        """S-061."""
        name = self.selected_name()
        if name is not None:
            self.service.stop(name)
            self.refresh()

    def view_log(self) -> LogDialog | None:
        name = self.selected_name()
        if name is None:
            return None
        dialog = LogDialog(self.service, name, parent=self)
        self.log_dialog = dialog
        dialog.open()
        return dialog

    def import_task(self) -> HotFolderTask | None:
        path = self.pick_open()
        if path is None:
            return None
        try:
            task = self.service.import_task(path)
        except CoreError as exc:
            self.statusBar().showMessage(tr_error(exc), 8000)
            return None
        self.refresh()
        self.select(task.name)
        return task

    def export_task(self) -> Path | None:
        name = self.selected_name()
        if name is None:
            return None
        path = self.pick_save(name)
        if path is None:
            return None
        self.service.export_task(name, path)
        return path

    # --- ceasul si notificarile (S-066) ---

    def _progress(self, report: Any) -> None:
        if self.service.processing is not None:  # `Running...` in lista
            self.refresh()
        self.statusBar().showMessage(tr("hotfolder.processing", file=report.detail or ""))
        QApplication.processEvents()

    def tick(self) -> list[Any]:
        if self.service.processing is not None:
            return []
        summaries = self.service.tick(progress=self._progress)
        for summary in summaries:
            self._finished(summary)
        return summaries

    def _finished(self, summary: Any) -> None:
        """S-066: un mesaj deasupra barei de activitati la fiecare terminare."""
        self.statusBar().clearMessage()
        self.refresh()
        if not self.context.settings.get("hotfolder.notifications"):
            return
        text = summary_text(summary, tr)
        self.notifications.append(text)
        if self.tray is not None and self.tray.isVisible():
            icon = QSystemTrayIcon.MessageIcon.Warning if summary.errors else \
                QSystemTrayIcon.MessageIcon.Information
            self.tray.showMessage(tr("hotfolder.title"), text, icon, 8000)

    def closeEvent(self, event: QCloseEvent) -> None:  # API Qt
        """Inchiderea ascunde fereastra; sarcinile continua cat aplicatia e
        deschisa (S-005)."""
        if self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def shutdown(self) -> None:
        self.timer.stop()
        if self.tray is not None:
            self.tray.hide()
