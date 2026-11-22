"""Dialogurile din `Organize Pages` (faza 8, pasul 8.4a): E-013…E-017, E-019,
E-020, E-108.

Fiecare dialog doar culege valorile; fereastra aplica operatia prin
`PageOrganizer`, cu pas de Undo. Pozitia de inserare (E-016) are trei variante:
inainte de prima pagina, dupa ultima, dupa o pagina aleasa.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.pdf.organize import format_range, insertion_point, parse_range
from app.gui.i18n import tr

MM = 72 / 25.4
"""Puncte intr-un milimetru."""
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "a4": (595.28, 841.89), "a3": (841.89, 1190.55), "a5": (419.53, 595.28),
    "letter": (612.0, 792.0), "legal": (612.0, 1008.0),
}
"""E-013: dimensiunile de pagina oferite, in puncte (portret)."""
MANY_PAGES = 1_000_000
"""Pentru intervalele dintr-un fisier al carui numar de pagini nu se stie inca."""
FILE_FILTER = "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.jp2 *.djvu *.webp"


def dialog_buttons(dialog: QDialog, ok_key: str) -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                           QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(tr(ok_key))
    box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("organize.cancel"))
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class PositionBox(QGroupBox):
    """E-016: inainte de prima pagina / dupa ultima / dupa pagina aleasa."""

    def __init__(self, page_count: int, after: int, parent: QWidget | None = None) -> None:
        super().__init__(tr("organize.position"), parent)
        self.setObjectName("organize_position")
        self.page_count = page_count
        self.first = QRadioButton(tr("organize.position.first"))
        self.first.setObjectName("position_first")
        self.last = QRadioButton(tr("organize.position.last"))
        self.last.setObjectName("position_last")
        self.after = QRadioButton(tr("organize.position.after"))
        self.after.setObjectName("position_after")
        self.page = QSpinBox()
        self.page.setObjectName("position_page")
        self.page.setRange(1, max(page_count, 1))
        self.page.setValue(min(max(after, 1), max(page_count, 1)))
        group = QButtonGroup(self)
        for button in (self.first, self.last, self.after):
            group.addButton(button)
        self.after.setChecked(True)
        self.after.toggled.connect(self.page.setEnabled)
        row = QHBoxLayout()
        row.addWidget(self.after)
        row.addWidget(self.page)
        row.addStretch(1)
        column = QVBoxLayout(self)
        column.addWidget(self.first)
        column.addWidget(self.last)
        column.addLayout(row)

    def set_at(self, at: int) -> None:
        """Preselectie dupa pozitia de inserare `at` (1..n+1)."""
        if at <= 1:
            self.first.setChecked(True)
        elif at > self.page_count:
            self.last.setChecked(True)
        else:
            self.after.setChecked(True)
            self.page.setValue(at - 1)

    def at(self) -> int:
        if self.first.isChecked():
            return insertion_point("first", self.page_count)
        if self.last.isChecked():
            return insertion_point("last", self.page_count)
        return insertion_point("after", self.page_count, self.page.value())


class BlankPageDialog(QDialog):
    """E-013: dimensiunea paginii goale si pozitia, apoi `Add`."""

    def __init__(self, page_count: int, current: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_blank_page_dialog")
        self.setWindowTitle(tr("pdf.action.add_blank_page"))
        self.size_box = QComboBox()
        self.size_box.setObjectName("blank_page_size")
        self.size_box.addItem(tr("organize.size.same"), "same")
        for key in PAGE_SIZES:
            self.size_box.addItem(tr(f"organize.size.{key}"), key)
        self.size_box.addItem(tr("organize.size.custom"), "custom")
        self.width = QDoubleSpinBox()
        self.width.setObjectName("blank_page_width")
        self.height = QDoubleSpinBox()
        self.height.setObjectName("blank_page_height")
        for spin, value in ((self.width, 210.0), (self.height, 297.0)):
            spin.setRange(10, 5000)
            spin.setSuffix(" mm")
            spin.setValue(value)
            spin.setEnabled(False)
        self.size_box.currentIndexChanged.connect(self._size_changed)
        self.position = PositionBox(page_count, current)
        form = QFormLayout()
        form.addRow(tr("organize.size"), self.size_box)
        form.addRow(tr("organize.size.width"), self.width)
        form.addRow(tr("organize.size.height"), self.height)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(self.position)
        column.addWidget(dialog_buttons(self, "organize.add"))

    def _size_changed(self) -> None:
        custom = self.size_box.currentData() == "custom"
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)

    def page_size(self) -> tuple[float, float] | None:
        """In puncte; None = ca pagina de langa (E-013, implicit)."""
        key = self.size_box.currentData()
        if key == "same":
            return None
        if key == "custom":
            return (self.width.value() * MM, self.height.value() * MM)
        return PAGE_SIZES[str(key)]


class InsertPagesDialog(QDialog):
    """E-014 (`Add Pages from PDF...`) si E-015, E-108 (`Add Pages from
    File...`): fisierul, paginile (`Select pages (e.g. 2,3,5-7)`), pozitia;
    pentru fisiere si `Split facing pages` si `Image Processing Settings`."""

    def __init__(self, kind: str, page_count: int, current: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName(f"organize_insert_{kind}_dialog")
        self.setWindowTitle(tr(f"pdf.action.add_pages_{kind}"))
        self.path = QLineEdit()
        self.path.setObjectName("insert_path")
        self.path.textChanged.connect(self._validate)
        browse = QPushButton(tr("organize.browse"))
        browse.setObjectName("insert_browse")
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        self.select = QCheckBox(tr("organize.select_pages"))  # E-108
        self.select.setObjectName("insert_select_pages")
        self.pages = QLineEdit()
        self.pages.setObjectName("insert_pages")
        self.pages.setPlaceholderText("2, 3, 5-7")
        self.pages.setEnabled(False)
        self.select.toggled.connect(self.pages.setEnabled)
        self.select.toggled.connect(lambda _on: self._validate())
        self.pages.textChanged.connect(self._validate)
        self.position = PositionBox(page_count, current)
        column = QVBoxLayout(self)
        column.addLayout(row)
        column.addWidget(self.select)
        column.addWidget(self.pages)
        column.addWidget(self.position)
        self.split_facing = QCheckBox(tr("organize.split_facing"))
        self.split_facing.setObjectName("insert_split_facing")
        self.image_settings = QPushButton(tr("organize.image_settings"))
        self.image_settings.setObjectName("insert_image_settings")
        if kind == "file":
            column.addWidget(self.split_facing)
            column.addWidget(self.image_settings)
        else:
            self.split_facing.hide()
            self.image_settings.hide()
        self.note = QLabel(tr(f"organize.insert.note_{kind}"))  # E-014, E-015
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        column.addWidget(self.note)
        self.box = dialog_buttons(self, "organize.add")
        column.addWidget(self.box)
        self._validate()

    def browse(self) -> None:
        pattern = "*.pdf" if self.kind == "pdf" else FILE_FILTER
        name, _ = QFileDialog.getOpenFileName(self, self.windowTitle(), "",
                                              f"{tr('organize.files')} ({pattern})")
        if name:
            self.path.setText(name)

    def source_pages(self) -> list[int] | None:
        """Paginile din sursa, in ordinea crescatoare; None = toate. Interval
        gresit → `ValueError`."""
        if not self.select.isChecked():
            return None
        pages = list(parse_range(self.pages.text(), MANY_PAGES).pages)
        if not pages:
            raise ValueError("nicio pagina")
        return pages

    def _validate(self) -> None:
        ok = Path(self.path.text().strip()).is_file()
        try:
            self.source_pages()
        except ValueError:
            ok = False
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def source(self) -> Path:
        return Path(self.path.text().strip())


class MovePagesDialog(QDialog):
    """E-019: paginile selectate se muta inainte de prima, dupa ultima sau dupa
    o pagina aleasa."""

    def __init__(self, pages: list[int], page_count: int, parent: QWidget | None = None
                 ) -> None:
        super().__init__(parent)
        self.setObjectName("organize_move_dialog")
        self.setWindowTitle(tr("pdf.action.move_pages"))
        self.pages = pages
        label = QLabel(tr("organize.move.pages", pages=format_range(pages)))
        self.position = PositionBox(page_count, max(pages))
        column = QVBoxLayout(self)
        column.addWidget(label)
        column.addWidget(self.position)
        column.addWidget(dialog_buttons(self, "organize.move"))


class ReplacePagesDialog(QDialog):
    """E-020: fisierul sursa, intervalul sursa, intervalul tinta; lungimile
    trebuie sa fie egale, altfel mesaj explicit si `Replace` dezactivat."""

    def __init__(self, targets: list[int], page_count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_replace_dialog")
        self.setWindowTitle(tr("pdf.action.replace_pages"))
        self.page_count = page_count
        self.source_count: int | None = None
        self.path = QLineEdit()
        self.path.setObjectName("replace_path")
        self.path.textChanged.connect(self._source_changed)
        browse = QPushButton(tr("organize.browse"))
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        self.source_range = QLineEdit()
        self.source_range.setObjectName("replace_source_pages")
        self.target_range = QLineEdit(format_range(targets))
        self.target_range.setObjectName("replace_target_pages")
        for edit in (self.source_range, self.target_range):
            edit.setPlaceholderText("2, 3, 5-7")
            edit.textChanged.connect(self._validate)
        self.message = QLabel()
        self.message.setObjectName("replace_message")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #c62828;")
        form = QFormLayout()
        form.addRow(tr("organize.replace.source_file"), row)
        form.addRow(tr("organize.replace.source_pages"), self.source_range)
        form.addRow(tr("organize.replace.target_pages"), self.target_range)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(self.message)
        self.box = dialog_buttons(self, "organize.replace")
        column.addWidget(self.box)
        self._validate()

    def browse(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, self.windowTitle(), "",
                                              f"{tr('organize.files')} (*.pdf)")
        if name:
            self.path.setText(name)

    def _source_changed(self) -> None:
        import pikepdf

        self.source_count = None
        path = Path(self.path.text().strip())
        if path.is_file():
            try:
                with pikepdf.open(path) as pdf:
                    self.source_count = len(pdf.pages)
            except (pikepdf.PdfError, OSError):
                self.source_count = None  # protejat sau stricat: se afla la inlocuire
        if self.source_count and not self.source_range.text().strip():
            self.source_range.setText(f"1-{self.source_count}" if self.source_count > 1
                                      else "1")
        self._validate()

    def ranges(self) -> tuple[list[int], list[int]]:
        """(tinta, sursa); `ValueError` daca un interval e gresit."""
        target = list(parse_range(self.target_range.text(), self.page_count).pages)
        source = list(parse_range(self.source_range.text(),
                                  self.source_count or MANY_PAGES).pages)
        if not target or not source:
            raise ValueError("interval gol")
        return target, source

    def _validate(self) -> None:
        ok = Path(self.path.text().strip()).is_file()
        text = ""
        try:
            target, source = self.ranges()
            if len(target) != len(source):
                ok = False
                text = tr("organize.replace.mismatch", target=len(target), source=len(source))
        except ValueError:
            ok = False
        self.message.setText(text)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def source(self) -> Path:
        return Path(self.path.text().strip())


class PositionDialog(QDialog):
    """E-017: unde intra paginile scanate, inainte de dialogul de scanare."""

    def __init__(self, title_key: str, page_count: int, after: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_position_dialog")
        self.setWindowTitle(tr(title_key))
        self.position = PositionBox(page_count, after)
        column = QVBoxLayout(self)
        column.addWidget(self.position)
        column.addWidget(dialog_buttons(self, "organize.continue"))


QUALITIES = ("best", "balanced", "compact", "custom")
"""E-038: cele patru valori ale `Image quality`."""


class ImageProcessingDialog(QDialog):
    """E-038: `Image Processing Settings...` pentru paginile adaugate din
    fisiere si de la scaner: calitatea imaginii, recunoasterea textului din
    imagini, compresia MRC (cere recunoasterea, deci limbile OCR) si netezirea
    caracterelor. Valorile se pastreaza in setari."""

    def __init__(self, settings: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_image_settings_dialog")
        self.setWindowTitle(tr("organize.image_settings"))
        self.settings = settings
        self.quality = QComboBox()
        self.quality.setObjectName("image_quality")
        for key in QUALITIES:
            self.quality.addItem(tr(f"organize.quality.{key}"), key)
        self.quality.setCurrentIndex(QUALITIES.index(
            str(settings.get("pdf_editor.image_quality"))))  # type: ignore[attr-defined]
        self.recognize = QCheckBox(tr("organize.image.recognize"))
        self.recognize.setObjectName("image_recognize")
        self.recognize.setChecked(bool(settings.get("pdf_editor.recognize_images")))  # type: ignore[attr-defined]
        self.mrc = QCheckBox(tr("organize.image.mrc"))
        self.mrc.setObjectName("image_mrc")
        self.mrc.setChecked(bool(settings.get("pdf_editor.use_mrc")))  # type: ignore[attr-defined]
        self.smooth = QCheckBox(tr("organize.image.smooth"))
        self.smooth.setObjectName("image_smooth")
        self.smooth.setChecked(bool(settings.get("pdf_editor.precise_scan")))  # type: ignore[attr-defined]
        languages = ", ".join(settings.ocr_settings().languages)  # type: ignore[attr-defined]
        self.languages = QLabel(tr("organize.image.languages", languages=languages))
        self.languages.setObjectName("image_languages")
        self.languages.setProperty("muted", True)
        self.recognize.toggled.connect(self._recognize_toggled)
        form = QFormLayout()
        form.addRow(tr("organize.image.quality"), self.quality)
        column = QVBoxLayout(self)
        column.addLayout(form)
        for widget in (self.recognize, self.mrc, self.languages, self.smooth):
            column.addWidget(widget)
        column.addWidget(dialog_buttons(self, "organize.ok"))
        self._recognize_toggled(self.recognize.isChecked())

    def _recognize_toggled(self, on: bool) -> None:
        """MRC si limbile au sens numai cu recunoasterea textului."""
        self.mrc.setEnabled(on)
        self.languages.setEnabled(on)

    def store(self) -> None:
        set_value = self.settings.set  # type: ignore[attr-defined]
        set_value("pdf_editor.image_quality", str(self.quality.currentData()))
        set_value("pdf_editor.recognize_images", self.recognize.isChecked())
        set_value("pdf_editor.use_mrc", self.mrc.isChecked() and self.recognize.isChecked())
        set_value("pdf_editor.precise_scan", self.smooth.isChecked())


def image_options(settings: object) -> object:
    """E-038: optiunile de export pentru paginile procesate (E-015, E-017).

    INCOMPLET, marcat: `pdf_editor.precise_scan` (netezirea marginilor
    caracterelor, echivalentul optiunii PreciseScan din original) se pastreaza
    in setari, dar nu are inca efect: nucleul nu are o unealta de netezire a
    contururilor (`docs/plan/faza_8_pasi.md`)."""
    from app.core.export.base import ExportOptions
    from app.core.model import ImageQuality, LayoutMode

    get = settings.get  # type: ignore[attr-defined]
    recognize = bool(get("pdf_editor.recognize_images"))
    return ExportOptions(layout_mode=LayoutMode.EXACT, searchable=recognize,
                         image_quality=ImageQuality(str(get("pdf_editor.image_quality"))),
                         use_mrc=recognize and bool(get("pdf_editor.use_mrc")))


# --- 8.4b: paginile goale, impartirea, imbunatatirea imaginilor ----------------------

BLANK_MARK = "#9fbcf7"
"""E-109: marcajul albastru al paginilor bifate pentru stergere."""


class BlankPagesDialog(QDialog):
    """E-021, E-023, E-109: paginile goale gasite, ca miniaturi; cele bifate
    (implicit toate) au chenar albastru si se sterg cu `Delete selected pages`.
    Pragul de continut se poate schimba; `-` si `+` (stanga jos) schimba marimea
    miniaturilor."""

    def __init__(self, document: object, find: object, threshold: float,
                 parent: QWidget | None = None) -> None:
        from PySide6.QtCore import QSize, Qt
        from PySide6.QtWidgets import QListWidget, QSlider, QToolButton

        super().__init__(parent)
        self.setObjectName("organize_blank_pages_dialog")
        self.setWindowTitle(tr("organize.blank.title"))
        self.document = document
        self.find = find
        """`find(prag)` → lista paginilor goale (E-021)."""
        self.sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity.setObjectName("blank_threshold")
        self.sensitivity.setRange(80, 100)  # pragul * 100
        self.sensitivity.setValue(round(threshold * 100))
        self.sensitivity.valueChanged.connect(lambda _v: self.search())
        self.list = QListWidget()
        self.list.setObjectName("blank_pages")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setIconSize(QSize(96, 136))
        self.list.setSpacing(8)
        self.list.itemChanged.connect(lambda _i: self._update())
        self.zoom_out = QToolButton()
        self.zoom_out.setObjectName("blank_zoom_out")
        self.zoom_out.setText("-")
        self.zoom_in = QToolButton()
        self.zoom_in.setObjectName("blank_zoom_in")
        self.zoom_in.setText("+")
        self.zoom_out.clicked.connect(lambda: self.zoom(-24))
        self.zoom_in.clicked.connect(lambda: self.zoom(24))
        self.message = QLabel()
        self.message.setObjectName("blank_message")
        self.message.setWordWrap(True)
        self.box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("organize.blank.delete"))
        self.box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("organize.cancel"))
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(tr("organize.blank.threshold"), self.sensitivity)
        bottom = QHBoxLayout()
        bottom.addWidget(self.zoom_out)
        bottom.addWidget(self.zoom_in)
        bottom.addStretch(1)
        bottom.addWidget(self.box)
        column = QVBoxLayout(self)
        column.addLayout(form)
        column.addWidget(self.list, 1)
        column.addWidget(self.message)
        column.addLayout(bottom)
        self.resize(640, 480)
        self.search()

    @property
    def threshold(self) -> float:
        return self.sensitivity.value() / 100

    def search(self) -> list[int]:
        """E-021: lista paginilor goale, din nou, la pragul curent."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon, QImage, QPixmap
        from PySide6.QtWidgets import QListWidgetItem

        pages = list(self.find(self.threshold))  # type: ignore[operator]
        self.list.blockSignals(True)
        self.list.clear()
        for n in pages:
            image = QImage.fromData(self.document.render_page(n, 0.3), "PNG")  # type: ignore[attr-defined]
            item = QListWidgetItem(QIcon(QPixmap.fromImage(image)), str(n))
            item.setData(Qt.ItemDataRole.UserRole, n)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # E-023: implicit toate bifate
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._update()
        return pages

    def zoom(self, step: int) -> None:
        from PySide6.QtCore import QSize

        width = max(48, min(240, self.list.iconSize().width() + step))
        self.list.setIconSize(QSize(width, int(width * 1.414)))

    def checked_pages(self) -> list[int]:
        from PySide6.QtCore import Qt

        return [int(self.list.item(r).data(Qt.ItemDataRole.UserRole))
                for r in range(self.list.count())
                if self.list.item(r).checkState() == Qt.CheckState.Checked]

    def _update(self) -> None:
        """E-109: paginile bifate pentru stergere au marcajul albastru."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QBrush, QColor

        self.list.blockSignals(True)
        for r in range(self.list.count()):
            item = self.list.item(r)
            checked = item.checkState() == Qt.CheckState.Checked
            item.setBackground(QBrush(QColor(BLANK_MARK) if checked else Qt.GlobalColor.transparent))
        self.list.blockSignals(False)
        found = self.list.count()
        self.message.setText(tr("organize.blank.found", count=found) if found
                             else tr("organize.blank.none"))
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.checked_pages()))


class SplitDialog(QDialog):
    """E-024…E-032, E-110…E-112: `Split Document`."""

    def __init__(self, organizer: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_split_dialog")
        self.setWindowTitle(tr("organize.split.title"))
        self.organizer = organizer
        document = organizer.document  # type: ignore[attr-defined]
        self.source_path = document.path
        self.stem = document.path.stem if document.path is not None else \
            tr("pdf.untitled")
        self.original = organizer.source_size()  # type: ignore[attr-defined]
        has_bookmarks = any(b.target_page for b in document.bookmarks())
        # E-024: cele trei metode
        self.by_size = QRadioButton(tr("organize.split.by_size"))
        self.by_size.setObjectName("split_by_size")
        self.by_pages = QRadioButton(tr("organize.split.by_pages"))
        self.by_pages.setObjectName("split_by_pages")
        self.by_bookmarks = QRadioButton(tr("organize.split.by_bookmarks"))
        self.by_bookmarks.setObjectName("split_by_bookmarks")
        self.by_bookmarks.setEnabled(has_bookmarks)  # E-027: fara semne de carte, gri
        methods = QButtonGroup(self)
        for button in (self.by_size, self.by_pages, self.by_bookmarks):
            methods.addButton(button)
            button.toggled.connect(lambda _on: self._update())
        self.size_mb = QDoubleSpinBox()  # E-025
        self.size_mb.setObjectName("split_size")
        self.size_mb.setRange(0.01, 100_000)
        self.size_mb.setDecimals(2)
        self.size_mb.setSuffix(" MB")
        self.size_mb.setValue(max(0.01, round(self.original / 2 / 1_000_000, 2)))
        self.page_count = QSpinBox()  # E-026
        self.page_count.setObjectName("split_pages")
        self.page_count.setRange(1, max(document.page_count, 1))
        self.page_count.setValue(max(1, min(10, document.page_count)))
        for spin in (self.size_mb, self.page_count):
            spin.valueChanged.connect(lambda _v: self._update())
        # E-028, E-029: numele
        self.name = QLineEdit(self.stem)
        self.name.setObjectName("split_name")
        self.numbering = QComboBox()
        self.numbering.setObjectName("split_numbering")
        self.numbering.addItem(tr("organize.split.number_before"), "before")
        self.numbering.addItem(tr("organize.split.number_after"), "after")
        self.digits = QSpinBox()
        self.digits.setObjectName("split_digits")
        self.digits.setRange(1, 9)
        self.digits.setValue(2)
        self.bookmark_name = QRadioButton(tr("organize.split.bookmark_name"))
        self.bookmark_name.setObjectName("split_bookmark_name")
        self.custom_name = QRadioButton(tr("organize.split.custom_name"))
        self.custom_name.setObjectName("split_custom_name")
        names = QButtonGroup(self)
        names.addButton(self.bookmark_name)
        names.addButton(self.custom_name)
        self.bookmark_name.setChecked(True)
        self.add_numeration = QCheckBox(tr("organize.split.add_numeration"))
        self.add_numeration.setObjectName("split_add_numeration")
        self.add_numeration.setChecked(True)  # E-029: bifat implicit
        for widget in (self.name, self.bookmark_name, self.custom_name):
            signal = widget.textChanged if isinstance(widget, QLineEdit) else widget.toggled
            signal.connect(lambda *_a: self._update())
        self.numbering.currentIndexChanged.connect(lambda _i: self._update())
        self.digits.valueChanged.connect(lambda _v: self._update())
        self.add_numeration.toggled.connect(lambda _on: self._update())
        self.example = QLabel()  # E-111
        self.example.setObjectName("split_example")
        # E-030, E-112: folderul
        self.same_folder = QCheckBox(tr("organize.split.same_folder"))
        self.same_folder.setObjectName("split_same_folder")
        self.folder = QLineEdit()
        self.folder.setObjectName("split_folder")
        browse = QPushButton(tr("organize.browse"))
        browse.setObjectName("split_browse")
        browse.clicked.connect(self.browse)
        if self.source_path is not None:
            self.folder.setText(str(self.source_path.parent))
            self.same_folder.setChecked(True)
        else:
            self.same_folder.setEnabled(False)
        self.same_folder.toggled.connect(self._folder_toggled)
        self.folder.textChanged.connect(lambda _t: self._update())
        self._folder_toggled(self.same_folder.isChecked())
        self.total = QLabel()  # E-110
        self.total.setObjectName("split_total")
        self.warning = QLabel()  # E-025: spus inainte, nu dupa
        self.warning.setObjectName("split_warning")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color: #b45309;")
        method_box = QGroupBox(tr("organize.split.method"))
        grid = QFormLayout(method_box)
        grid.addRow(self.by_size, self.size_mb)
        grid.addRow(self.by_pages, self.page_count)
        grid.addRow(self.by_bookmarks)
        name_box = QGroupBox(tr("organize.split.names"))
        names_form = QFormLayout(name_box)
        names_form.addRow(self.bookmark_name, self.add_numeration)
        names_form.addRow(self.custom_name)
        names_form.addRow(tr("organize.split.name"), self.name)
        names_form.addRow(tr("organize.split.numbering"), self.numbering)
        names_form.addRow(tr("organize.split.digits"), self.digits)
        names_form.addRow(self.example)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        column = QVBoxLayout(self)
        column.addWidget(method_box)
        column.addWidget(name_box)
        column.addWidget(self.same_folder)
        column.addLayout(folder_row)
        column.addWidget(self.total)
        column.addWidget(self.warning)
        self.box = dialog_buttons(self, "organize.split.ok")
        column.addWidget(self.box)
        (self.by_bookmarks if has_bookmarks else self.by_pages).setChecked(True)
        self._update()

    def browse(self) -> None:
        name = QFileDialog.getExistingDirectory(self, tr("organize.split.folder"),
                                                self.folder.text())
        if name:
            self.folder.setText(name)

    def _folder_toggled(self, same: bool) -> None:
        """E-112: cu `Same as source folder`, campul de cale se dezactiveaza."""
        if same and self.source_path is not None:
            self.folder.setText(str(self.source_path.parent))
        self.folder.setEnabled(not same)

    # --- valorile ---------------------------------------------------------------------

    def method(self) -> str:
        if self.by_size.isChecked():
            return "size"
        return "bookmarks" if self.by_bookmarks.isChecked() else "pages"

    def value(self) -> int | None:
        if self.method() == "size":
            return round(self.size_mb.value() * 1_000_000)
        return self.page_count.value() if self.method() == "pages" else None

    def naming(self) -> object:
        from app.core.pdf.organize import SplitNaming

        bookmarks = self.method() == "bookmarks"
        return SplitNaming(name=self.name.text(), numbering=str(self.numbering.currentData()),
                           digits=self.digits.value(),
                           use_bookmark_names=bookmarks and self.bookmark_name.isChecked(),
                           add_numeration=self.add_numeration.isChecked())

    def output_folder(self) -> Path:
        return Path(self.folder.text().strip())

    def plan(self) -> object | None:
        try:
            return self.organizer.plan_split(self.method(), self.value())  # type: ignore[attr-defined]
        except ValueError:
            return None

    def _update(self) -> None:
        bookmarks = self.method() == "bookmarks"
        self.size_mb.setEnabled(self.method() == "size")
        self.page_count.setEnabled(self.method() == "pages")
        for widget in (self.bookmark_name, self.custom_name, self.add_numeration):
            widget.setEnabled(bookmarks)
        custom = not bookmarks or self.custom_name.isChecked()
        self.name.setEnabled(custom)
        numbered = not bookmarks or self.custom_name.isChecked() or \
            self.add_numeration.isChecked()
        self.numbering.setEnabled(numbered)
        self.digits.setEnabled(numbered)
        too_big = self.method() == "size" and self.value() is not None and \
            self.value() >= self.original  # type: ignore[operator]
        self.size_mb.setStyleSheet("QDoubleSpinBox { color: #c62828; }" if too_big else "")
        plan = None if too_big else self.plan()
        self.total.setText(tr("organize.split.total", count=plan.file_count if plan else 0))
        if plan is not None:
            names = self.naming().file_names(plan, self.stem)  # type: ignore[attr-defined]
            self.example.setText(tr("organize.split.example", name=names[0]))
        else:
            self.example.setText("")
        oversize = getattr(plan, "oversize", [])
        self.warning.setText(tr("organize.split.oversize", count=len(oversize))
                             if oversize else "")
        ok = plan is not None and bool(self.folder.text().strip())
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)


class EnhanceDialog(QDialog):
    """E-035: `Enhance Images...`: orientarea, indreptarea si rezolutia (poate
    dura), netezirea caracterelor; limbile OCR pentru textul recunoscut."""

    def __init__(self, settings: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("organize_enhance_dialog")
        self.setWindowTitle(tr("organize.enhance.title"))
        self.orientation = QCheckBox(tr("organize.enhance.orientation"))
        self.orientation.setObjectName("enhance_orientation")
        self.orientation.setChecked(True)
        self.deskew = QCheckBox(tr("organize.enhance.deskew"))
        self.deskew.setObjectName("enhance_deskew")
        self.deskew.setChecked(True)
        self.smooth = QCheckBox(tr("organize.image.smooth"))
        self.smooth.setObjectName("enhance_smooth")
        languages = ", ".join(settings.ocr_settings().languages)  # type: ignore[attr-defined]
        self.languages = QLabel(tr("organize.image.languages", languages=languages))
        self.languages.setObjectName("enhance_languages")
        self.change_languages = QPushButton(tr("organize.enhance.languages"))
        self.change_languages.setObjectName("enhance_change_languages")
        row = QHBoxLayout()
        row.addWidget(self.languages, 1)
        row.addWidget(self.change_languages)
        column = QVBoxLayout(self)
        for widget in (self.orientation, self.deskew, self.smooth):
            column.addWidget(widget)
        column.addLayout(row)
        column.addWidget(dialog_buttons(self, "organize.enhance.ok"))

    def preprocess(self) -> object:
        """Numai uneltele alese; restul lantului recomandat ramane oprit."""
        from app.core.settings import PreprocessSettings

        deskew = self.deskew.isChecked()
        return PreprocessSettings(
            correct_orientation=self.orientation.isChecked(), deskew=deskew,
            straighten_lines=False, correct_resolution=deskew, detect_page_edges=False,
            whiten_background=False, reduce_iso_noise=False, remove_motion_blur=False,
            fix_inverted_colors=False, convert_to_bw=False, remove_color_marks=False)
