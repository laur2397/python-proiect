"""Ecranul de conversie al Lansatorului (faza 6c, pasul 6c.3).

`< Back` (A-029, A-305), coloana de setari in stanga (circa 190 px), lista de
fisiere in dreapta cu toolbarul ei (A-020…A-026, A-306, A-307), setarile pe
format: PDF (A-035…A-042), Word (A-050…A-055), Excel (A-060…A-065), alte
formate (A-070…A-073), dialogul `Custom Settings` (A-308…A-314), dialogul de
progres (A-027, A-028, A-315), recomandarea pentru documente complexe (A-017).

Conversia o face nucleul (`app.core.convert.ConvertJob`).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import QFileInfo, Qt, Signal
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSlider,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.core.convert import (
    EXCEL_MODES,
    OTHER_FORMATS,
    WORD_MODES,
    ConvertJob,
    ConvertResult,
    ConvertSettings,
    FullTextSearch,
)
from app.core.model import ExportFormat, ImageQuality, LayoutMode, Progress
from app.gui.filters import conversion_filter
from app.gui.i18n import tr, tr_error

TARGET = {"pdf": ExportFormat.PDF, "docx": ExportFormat.DOCX, "xlsx": ExportFormat.XLSX}
"""Cardurile `Convert to`; `other` alege formatul din combo (A-070)."""

QUALITIES = (ImageQuality.BEST, ImageQuality.BALANCED, ImageQuality.COMPACT,
             ImageQuality.CUSTOM)
"""A-035."""

DPI_CHOICES = (300, 150, 96)
"""A-309."""

OPTIONS_TAB = {"odt": "docx", "rtf": "docx", "fb2": "epub"}
"""A-072: elementul din `Format Settings` (X-419) al formatelor fara tab propriu."""


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class CustomSettingsDialog(QDialog):
    """A-308…A-314: rezolutia, culoarea, calitatea, codecurile, `Reset`."""

    DEFAULTS: ClassVar[dict[str, Any]] = {"reduce": False, "dpi": 300, "lossless": False, "quality": 85}

    def __init__(self, values: dict[str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("custom_settings")
        self.setWindowTitle(tr("convert.custom.title"))
        resolution = QGroupBox(tr("convert.custom.resolution"))  # A-309
        box = QVBoxLayout(resolution)
        self.reduce = QCheckBox(tr("convert.custom.reduce"))
        self.reduce.setObjectName("custom_reduce")
        box.addWidget(self.reduce)
        self.dpi_group = QButtonGroup(self)
        self.dpi_buttons: dict[int, QRadioButton] = {}
        for dpi in DPI_CHOICES:
            radio = QRadioButton(f"{dpi} dpi")
            radio.setObjectName(f"custom_dpi_{dpi}")
            self.dpi_group.addButton(radio)
            self.dpi_buttons[dpi] = radio
            box.addWidget(radio)
        self.reduce.toggled.connect(self._update)
        color = QGroupBox(tr("convert.custom.color"))  # A-310
        self.color = QComboBox()
        self.color.addItem(tr("convert.custom.keep_color"))
        QVBoxLayout(color).addWidget(self.color)
        quality = QGroupBox(tr("convert.custom.quality"))  # A-311, A-313
        qbox = QVBoxLayout(quality)
        self.loss = QComboBox()
        self.loss.setObjectName("custom_loss")
        self.loss.addItem(tr("convert.custom.loss_allowed"), False)
        self.loss.addItem(tr("convert.custom.loss_not_allowed"), True)
        self.loss.currentIndexChanged.connect(self._update)
        self.slider_label = QLabel()
        self.slider_label.setObjectName("custom_quality_label")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("custom_quality")
        self.slider.setRange(1, 100)
        self.slider.valueChanged.connect(self._update)
        qbox.addWidget(self.loss)
        qbox.addWidget(self.slider_label)
        qbox.addWidget(self.slider)
        codecs = QLabel(tr("convert.custom.codecs"))  # A-312
        codecs.setObjectName("custom_codecs")
        codecs.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        self.reset_button = buttons.addButton(tr("convert.custom.reset"),  # A-314
                                              QDialogButtonBox.ButtonRole.ResetRole)
        self.reset_button.setObjectName("custom_reset")
        self.reset_button.clicked.connect(lambda: self.load(self.DEFAULTS))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (resolution, color, quality, codecs, buttons):
            layout.addWidget(widget)
        self.load({**self.DEFAULTS, **(values or {})})

    def load(self, values: dict[str, Any]) -> None:
        self.reduce.setChecked(bool(values["reduce"]))
        self.dpi_buttons[int(values["dpi"])].setChecked(True)
        self.loss.setCurrentIndex(1 if values["lossless"] else 0)
        self.slider.setValue(int(values["quality"]))
        self._update()

    def _update(self, *_: Any) -> None:
        for radio in self.dpi_buttons.values():
            radio.setEnabled(self.reduce.isChecked())
        self.slider.setEnabled(not self.loss.currentData())  # A-311
        self.slider_label.setText(tr("convert.custom.quality_value", n=self.slider.value()))

    def values(self) -> dict[str, Any]:
        dpi = next(d for d, b in self.dpi_buttons.items() if b.isChecked())
        return {"reduce": self.reduce.isChecked(), "dpi": dpi,
                "lossless": bool(self.loss.currentData()), "quality": self.slider.value()}


class LanguagePicker(QComboBox):
    """A-039: combo cu mai multe limbi bifate; ordinea bifarii se pastreaza."""

    def __init__(self, codes: list[str], chosen: list[str], parent: QWidget | None = None
                 ) -> None:
        super().__init__(parent)
        from app.gui.options_dialog import language_name

        self._name = language_name
        self.setObjectName("convert_languages")
        model = QStandardItemModel(self)
        for code in codes:
            item = QStandardItem(language_name(code))
            item.setData(code, Qt.ItemDataRole.UserRole)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if code in chosen
                               else Qt.CheckState.Unchecked)
            model.appendRow(item)
        self.setModel(model)
        self._order = [c for c in chosen if c in codes]
        model.itemChanged.connect(self._changed)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self._show()

    def _changed(self, item: QStandardItem) -> None:
        code = item.data(Qt.ItemDataRole.UserRole)
        checked = item.checkState() == Qt.CheckState.Checked
        if checked and code not in self._order:
            self._order.append(code)
        elif not checked and code in self._order:
            self._order.remove(code)
        self._show()

    def _show(self) -> None:
        self.lineEdit().setText(", ".join(self._name(c) for c in self._order))

    def codes(self) -> list[str]:
        return list(self._order)

    def set_checked(self, code: str, checked: bool) -> None:
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == code:
                item.setCheckState(Qt.CheckState.Checked if checked
                                   else Qt.CheckState.Unchecked)


class ConvertScreen(QWidget):
    back_requested = Signal()
    """A-029: `< Back`."""
    ocr_editor_requested = Signal(object)
    """A-017: fisierele merg in OCR Editor (conversia avansata)."""
    options_requested = Signal(str, str)
    """A-040, A-041, A-054, A-064, A-072: tabul Options si formatul."""
    finished = Signal(object)
    """ConvertResult, dupa conversie."""
    dossier_created = Signal(object)
    """E-500: dosarul cu semnaturile pastrate (calea), de deschis in PDF Editor."""

    def __init__(self, context: Any, key: str, files: list[Path],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("convert_screen")
        self.context = context
        self.key = key
        self.engine: Any = None
        """Motorul OCR; None = Tesseract (testele pun un motor scriptat)."""
        self.custom = dict(CustomSettingsDialog.DEFAULTS)
        self.back = QPushButton(tr("convert.back"))  # A-305
        self.back.setObjectName("convert_back")
        self.back.clicked.connect(self.go_back)
        settings = QWidget()
        settings.setObjectName("convert_settings")
        settings.setFixedWidth(240)  # A-305: coloana de setari, circa 190 px plus margini
        self.form = QFormLayout(settings)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.fields: dict[str, Any] = {}
        self.files = QListWidget()  # A-020, A-307
        self.files.setObjectName("convert_files")
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        getattr(self, f"_settings_{key}")()
        self._common()
        self.files.itemSelectionChanged.connect(self._update)
        right = QVBoxLayout()
        right.addWidget(self._file_toolbar())
        right.addWidget(self.files, 1)
        top = QHBoxLayout()
        top.addWidget(self.back)
        top.addStretch(1)
        body = QHBoxLayout()
        body.addWidget(settings)
        body.addLayout(right, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(body, 1)
        for shortcut, slot in (("Del", self.remove_selected),  # A-025
                               ("Ctrl+A", self.files.selectAll),  # A-026
                               ("Alt+Up", lambda: self.move(-1)),  # A-023
                               ("Alt+Down", lambda: self.move(1))):
            action = QAction(self)
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda _=False, f=slot: f())
            self.addAction(action)
        self.add_files(files)

    # --- lista de fisiere (A-020…A-026) ---------------------------------------------

    def _file_toolbar(self) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName("convert_file_toolbar")
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)  # A-306
        self.file_actions: dict[str, QAction] = {}
        for key, slot in (("add", self.pick_and_add), ("remove", self.remove_selected),
                          ("up", lambda: self.move(-1)), ("down", lambda: self.move(1))):
            action = bar.addAction(tr(f"convert.file.{key}"))
            action.setObjectName(f"file_{key}")
            action.triggered.connect(lambda _=False, f=slot: f())
            self.file_actions[key] = action
        self._update()
        return bar

    def file_paths(self) -> list[Path]:
        return [self.files.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.files.count())]

    def add_files(self, files: list[Path]) -> None:
        """A-021: la sfarsitul listei; icon dupa tip, nume, dimensiune."""
        icons = QFileIconProvider()
        for path in map(Path, files):
            size = path.stat().st_size if path.exists() else 0
            item = QListWidgetItem(icons.icon(QFileInfo(str(path))),
                                   f"{path.name}  ({_size(size)})")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(str(path))
            self.files.addItem(item)
        self._update()

    def pick_and_add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("convert.file.add"), "",
                                                conversion_filter())
        self.add_files([Path(f) for f in files])

    def _selected_rows(self) -> list[int]:
        return sorted(self.files.row(i) for i in self.files.selectedItems())

    def remove_selected(self) -> None:
        """A-022, A-025: macar un fisier ramane in lista."""
        rows = self._selected_rows()
        if not rows or len(rows) >= self.files.count():
            return
        for row in reversed(rows):
            self.files.takeItem(row)
        self._update()

    def move(self, step: int) -> None:
        """A-023: primul nu urca, ultimul nu coboara; ordinea conteaza la combinare."""
        rows = self._selected_rows()
        if not rows:
            return
        if (step < 0 and rows[0] == 0) or (step > 0 and rows[-1] == self.files.count() - 1):
            return
        for row in rows if step < 0 else list(reversed(rows)):
            item = self.files.takeItem(row)
            self.files.insertItem(row + step, item)
        self.files.clearSelection()
        for row in rows:
            self.files.item(row + step).setSelected(True)
        self._update()

    def _update(self) -> None:
        if not hasattr(self, "file_actions") or not hasattr(self, "combine"):
            return
        selected = bool(self.files.selectedItems())
        for key in ("remove", "up", "down"):  # A-306: gri fara selectie
            self.file_actions[key].setEnabled(selected)
        enough = self.files.count() >= 2
        self.combine.setEnabled(enough)  # A-024: activa cu minimum 2 fisiere
        self.dossier_button.setEnabled(enough)  # E-500: minimum 2 fisiere
        if not enough:
            self.combine.setChecked(False)
        self.convert_button.setEnabled(self.files.count() > 0)

    # --- setarile (A-035…A-073) ----------------------------------------------------

    def _combo(self, key: str, items: list[tuple[str, Any]], label_key: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"convert_{key}")
        for text, data in items:
            combo.addItem(text, data)
        self.form.addRow(tr(label_key), combo)
        self.fields[key] = combo
        return combo

    def _check(self, key: str, label_key: str, checked: bool = False) -> QCheckBox:
        box = QCheckBox(tr(label_key))
        box.setObjectName(f"convert_{key}")
        box.setChecked(checked)
        self.form.addRow(box)
        self.fields[key] = box
        return box

    def _languages(self) -> None:
        from app.core.ocr.languages import LanguageRegistry

        codes = LanguageRegistry(con=self.context.app_db).all()
        chosen = list(self.context.settings.get("lang.manual") or ["ron"])
        self.languages = LanguagePicker(codes, chosen)
        self.form.addRow(tr("convert.languages"), self.languages)

    def _more(self, fmt: Callable[[], str]) -> None:
        button = QPushButton(tr("convert.more_options"))
        button.setObjectName("convert_more")
        button.clicked.connect(lambda: self.options_requested.emit("format", fmt()))
        self.form.addRow(button)

    def _modes(self, modes: tuple[LayoutMode, ...]) -> None:
        self._combo("layout", [(tr(f"layout.{m.value}"), m) for m in modes],
                    "convert.keep_formatting")

    def _settings_pdf(self) -> None:
        quality = self._combo("quality", [(tr(f"convert.quality.{q.value}"), q)
                                          for q in QUALITIES], "convert.image_quality")
        quality.setCurrentIndex(1)
        quality.activated.connect(self._quality_chosen)
        self._combo("search", [(tr(f"convert.search.{s.value}"), s) for s in FullTextSearch],
                    "convert.full_text_search").setCurrentIndex(1)
        self._check("pdfa", "convert.pdfa")
        self._check("mrc", "convert.mrc")
        self._languages()
        preprocess = QPushButton(tr("convert.preprocessing"))  # A-040
        preprocess.setObjectName("convert_preprocessing")
        preprocess.clicked.connect(lambda: self.options_requested.emit("image", ""))
        self.form.addRow(preprocess)
        self._more(lambda: "pdf")  # A-041

    def _settings_docx(self) -> None:
        self._modes(WORD_MODES)  # A-050
        self.fields["layout"].setCurrentIndex(1)
        self._languages()
        self._check("pictures", "convert.keep_pictures", True)  # A-052
        self._check("headers", "convert.keep_headers")  # A-053
        self._more(lambda: "docx")  # A-054

    def _settings_xlsx(self) -> None:
        self._modes(EXCEL_MODES)  # A-060
        self._languages()
        self._check("pictures", "convert.keep_pictures_xlsx", True)  # A-062
        self._check("sheet_per_page", "convert.sheet_per_page")  # A-063
        self._more(lambda: "xlsx")  # A-064

    def _settings_other(self) -> None:
        fmt = self._combo("format", [(f".{f.value}", f) for f in OTHER_FORMATS],
                          "convert.output_format")  # A-070
        fmt.currentIndexChanged.connect(self._update_button)
        self._languages()
        self._more(lambda: OPTIONS_TAB.get(self.target().value, self.target().value))

    def _common(self) -> None:
        self.combine = self._check("combine", "convert.combine")  # A-024
        self.dossier_button = QPushButton(tr("dossier.action"))  # E-500, langa A-024
        self.dossier_button.setObjectName("convert_dossier")
        self.dossier_button.setToolTip(tr("dossier.note"))
        self.dossier_button.clicked.connect(self.make_dossier)
        self.form.addRow(self.dossier_button)
        advice = QLabel(f'<a href="#">{tr("convert.complex")}</a>')  # A-017
        advice.setObjectName("convert_complex")
        advice.setWordWrap(True)
        advice.linkActivated.connect(
            lambda _: self.ocr_editor_requested.emit(self.file_paths()))
        self.form.addRow(advice)
        self.convert_button = QPushButton()
        self.convert_button.setObjectName("convert_start")
        self.convert_button.setDefault(True)
        self.convert_button.clicked.connect(lambda: self.start())
        self.form.addRow(self.convert_button)
        self._update_button()

    def target(self) -> ExportFormat:
        if self.key == "other":  # combo-ul intoarce valoarea, nu enum-ul
            return ExportFormat(self.fields["format"].currentData())
        return TARGET[self.key]

    def _update_button(self, *_: Any) -> None:
        """A-042, A-055, A-065, A-073: `Convert to <format>`."""
        if hasattr(self, "convert_button"):
            name = tr(f"launcher.card.{self.key}") if self.key != "other" \
                else f".{self.target().value}"
            self.convert_button.setText(tr("convert.start", format=name))

    def _quality_chosen(self, index: int) -> None:
        if ImageQuality(self.fields["quality"].itemData(index)) is ImageQuality.CUSTOM:
            self.edit_custom()

    def edit_custom(self) -> bool:
        """A-308: `Custom...` deschide dialogul, confirmat cu `OK`."""
        dialog = CustomSettingsDialog(self.custom, self)
        if dialog.exec():
            self.custom = dialog.values()
            return True
        return False

    def settings(self) -> ConvertSettings:
        f = self.fields
        s = ConvertSettings(target=self.target(), languages=tuple(self.languages.codes()),
                            combine=self.combine.isChecked())
        if "layout" in f:
            s.layout_mode = LayoutMode(f["layout"].currentData())
        if "pictures" in f:
            s.keep_pictures = f["pictures"].isChecked()
        if "headers" in f:
            s.keep_headers_footers = f["headers"].isChecked()
        if "sheet_per_page" in f:
            s.sheet_per_page = f["sheet_per_page"].isChecked()
        if self.key == "pdf":
            s.image_quality = ImageQuality(f["quality"].currentData())
            s.full_text_search = FullTextSearch(f["search"].currentData())
            s.pdfa = f["pdfa"].isChecked()
            s.use_mrc = f["mrc"].isChecked()
            s.custom_dpi = self.custom["dpi"] if self.custom["reduce"] else None
            s.custom_quality = int(self.custom["quality"])
            s.custom_lossless = bool(self.custom["lossless"])
        return s

    # --- pornirea (A-027, A-028, A-315) --------------------------------------------------

    def confirm_back(self) -> bool:
        answer = QMessageBox.question(self, tr("convert.title"), tr("convert.back_warning"))
        return answer == QMessageBox.StandardButton.Yes

    def go_back(self) -> bool:
        """A-029: avertisment daca lista are fisiere."""
        if self.files.count() and not self.confirm_back():
            return False
        self.back_requested.emit()
        return True

    def pick_destination(self) -> tuple[Path, str | None] | None:
        """A-027: folderul de destinatie; la combinare si numele (A-024)."""
        folder = QFileDialog.getExistingDirectory(self, tr("convert.destination"))
        if not folder:
            return None
        name = None
        if self.combine.isChecked():
            name, ok = QInputDialog.getText(self, tr("convert.title"), tr("convert.name"),
                                            text=tr("save.default_name"))
            if not ok or not name.strip():
                return None
        return Path(folder), name

    def report_text(self, result: ConvertResult) -> str:
        """A-028: raportul de la final."""
        lines = [tr("convert.done", n=len(result.written))]
        if result.cancelled:
            lines.append(tr("convert.cancelled"))
        for path, error in result.failed:
            reason = tr_error(error) if hasattr(error, "code") else tr("convert.failed_file")
            lines.append(f"{Path(path).name}: {reason}")
        return "\n".join(lines)

    # --- E-500, E-509: unirea pastrand semnaturile --------------------------------------

    def exec_dialog(self, dialog: Any) -> bool:
        return bool(dialog.exec())

    def ask_signed_merge(self, found: Any) -> str:
        from app.gui.dossier_dialog import ask_signed_merge

        return ask_signed_merge(self, found)

    def make_dossier(self) -> Path | None:
        """E-500: dosarul din lista de fisiere, in ordinea ei (A-023)."""
        from app.gui.dossier_dialog import DossierDialog, make_dossier

        dialog = DossierDialog(self.file_paths(), self)
        if not self.exec_dialog(dialog):
            return None
        path = make_dossier(dialog, self.context, self)
        if path is not None:
            self.dossier_created.emit(path)
        return path

    def start(self, destination: tuple[Path, str | None] | None = None
              ) -> ConvertResult | None:
        if self.combine.isChecked():  # E-509: inainte de unirea clasica
            from app.core.pdf.dossier import signed_among

            found = signed_among(self.file_paths())
            if found:
                choice = self.ask_signed_merge(found)
                if choice == "dossier":
                    self.make_dossier()
                    return None
                if choice != "continue":
                    return None
        try:
            job = ConvertJob(self.file_paths(), self.settings(), context=self.context,
                             engine=self.engine)
        except ValueError:
            QMessageBox.information(self, tr("convert.title"), tr("convert.invalid"))
            return None
        destination = destination or self.pick_destination()
        if destination is None:
            return None
        folder, name = destination
        status = tr("convert.status", format=f".{self.target().value}")
        dialog = QProgressDialog(status, tr("progress.cancel"), 0, len(self.file_paths()),
                                 self)
        dialog.setObjectName("convert_progress")
        dialog.setWindowTitle(tr("convert.title"))  # A-315
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        self.progress_lines: list[str] = []

        def progress(report: Progress) -> None:
            text = "\n".join([status, tr("convert.processing", file=report.detail),
                              tr("convert.counter", n=report.current, total=report.total)])
            self.progress_lines.append(text)
            dialog.setLabelText(text)
            dialog.setValue(report.current)
            QApplication.processEvents()

        def cancel() -> bool:
            QApplication.processEvents()
            return dialog.wasCanceled()

        result = job.run(folder, name, progress=progress, cancel=cancel)
        dialog.reset()
        QMessageBox.information(self, tr("convert.title"), self.report_text(result))
        self.finished.emit(result)
        return result
