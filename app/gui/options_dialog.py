"""Dialogul Options (faza 6b, pasul 6b.5): X-400…X-423 peste setarile X-*.

Fiecare control citeste si scrie o cheie din catalogul de setari
(`app.core.settings.CATALOG`); tipul controlului vine din tipul cheii, iar
validarea ramane in nucleu (`SettingDef.validate`, `SettingsStore.set`).
Textele vin din traduceri (`setting.<cheie>`, `setting.<cheie>.<valoare>`).

Structura din SPEC_10: dialog modal de circa 650 x 620 (X-400), bara de
taburi cu iconuri mari si eticheta dedesubt (X-401), in ordinea din X-402;
grupurile si dependentele din X-403…X-423.

[DECIZIE AUTONOMA] (faza_6b_pasi.md, decizia 10) Setarile aplicatiei
(`general.*`, `ui.*`, `app.*`, `ocr.max_threads`) se scriu in setarile
globale; celelalte in setarile proiectului deschis, care se salveaza odata cu
proiectul (fara proiect, tot in cele globale).

`Select Device...` (X-404, X-407) foloseste scanarea din faza 6d.
INCOMPLET, marcat: mesajul de vizualizator implicit si `Make Default...` (X-406) cer
integrarea cu sistemul (faza 16); `Pattern Editor...` si `Select Fonts...`
(X-417, X-418) nu au inca dialog.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app.core.settings import CATALOG, definition
from app.gui.i18n import catalog, language, tr

TABS = ("general", "image", "languages", "ocr", "format", "areas", "other")
"""X-402: ordinea taburilor."""

FORMATS = (("pdf", ("pdf.",)), ("docx", ("docx.",)), ("xlsx", ("xlsx.",)),
           ("pptx", ("pptx.",)), ("csv", ("csv.",)), ("txt", ("txt.",)),
           ("html", ("html.",)), ("epub", ("epub.",)), ("djvu", ("djvu.",)))
"""X-419: lista `Document type`, in ordinea exacta."""

GLOBAL_KEYS = ("general.", "ui.", "app.", "ocr.max_threads")
"""Setarile aplicatiei (decizia 10); restul sunt ale proiectului."""

PREPROCESS_COLUMNS = (
    ("image.split_facing_pages", "image.correct_orientation", "image.deskew",
     "image.straighten_lines", "image.correct_resolution"),
    ("image.detect_page_edges", "image.whiten_background", "image.reduce_iso_noise",
     "image.remove_motion_blur", "image.correct_trapezoid"),
    ("image.fix_inverted_colors", "image.convert_to_bw", "image.remove_color_marks"),
)
"""X-410: cele trei coloane; a doua e marcata cu `*` (numai fotografii, X-412)."""

OTHER_KEYS = ("ui.language", "ui.dark_theme", "app.temp_folder", "ocr.max_threads",
              "pdf.enable_javascript", "pdf.detect_urls")
"""Tabul `Other` (X-140…X-150)."""

_TAB_ICONS = {"general": "SP_ComputerIcon", "image": "SP_FileDialogContentsView",
              "languages": "SP_FileDialogDetailedView", "ocr": "SP_FileDialogInfoView",
              "format": "SP_FileIcon", "areas": "SP_DialogApplyButton",
              "other": "SP_FileDialogListView"}
"""Iconuri standard ale sistemului (fara identitatea vizuala a originalului)."""


def is_global(key: str) -> bool:
    return any(key == g or (g.endswith(".") and key.startswith(g)) for g in GLOBAL_KEYS)


def _known(key: str) -> bool:
    return key in catalog(language()) or key in catalog("en")


def label(key: str) -> str:
    return tr(f"setting.{key}")


def value_label(key: str, value: Any) -> str:
    """Textul unei valori de enum; codurile fara traducere (utf-8, a4) raman asa."""
    for k in (f"setting.{key}.{value}", f"value.{value}"):
        if _known(k):
            return tr(k)
    return str(value)


def language_name(code: str) -> str:
    key = f"language.{code}"
    return tr(key) if _known(key) else code


class OptionsDialog(QDialog):
    applied = Signal()
    """Setarile s-au salvat (fereastra se reimprospateaza)."""

    def __init__(self, context: Any, project: Any = None, *, tab: str = "general",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("options_dialog")
        self.setWindowTitle(tr("options.title"))
        self.setModal(True)  # X-400
        self.resize(650, 620)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, True)
        self.context = context
        self.project = project
        self.scanner_service: Any = None
        """Serviciul de scanare pentru `Select Device...`; None = WIA."""
        self.fields: dict[str, tuple[QWidget, Callable[[], Any], Callable[[Any], None]]] = {}
        self.radios: dict[str, dict[str, QRadioButton]] = {}
        self._initial: dict[str, Any] = {}
        self.error = QLabel()
        self.error.setObjectName("options_error")
        self.error.setWordWrap(True)
        self.tabs = QListWidget()  # X-401: iconuri mari, eticheta dedesubt
        self.tabs.setObjectName("options_tabs")
        self.tabs.setViewMode(QListWidget.ViewMode.IconMode)
        self.tabs.setFlow(QListWidget.Flow.LeftToRight)
        self.tabs.setWrapping(False)
        self.tabs.setMovement(QListWidget.Movement.Static)
        self.tabs.setIconSize(QSize(32, 32))
        self.tabs.setFixedHeight(84)
        self.pages = QStackedWidget()
        for key in TABS:
            icon = self.style().standardIcon(getattr(QStyle.StandardPixmap, _TAB_ICONS[key]))
            item = QListWidgetItem(icon, tr(f"options.tab.{key}"))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.tabs.addItem(item)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = getattr(self, f"_tab_{key}")()
            page.setObjectName(f"options_{key}")
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        self.tabs.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok  # X-423
                                        | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages, 1)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)
        self.load()
        self.show_tab(tab)

    # --- magazinul ---------------------------------------------------------------------

    def store(self, key: str) -> Any:
        if self.project is None or is_global(key):
            return self.context.settings
        return self.project.settings()

    def show_tab(self, key: str) -> None:
        self.tabs.setCurrentRow(TABS.index(key))

    @property
    def current_tab(self) -> str:
        return TABS[self.tabs.currentRow()]

    # --- controalele -------------------------------------------------------------------

    def _register(self, key: str, widget: QWidget, get: Callable[[], Any],
                  put: Callable[[Any], None]) -> QWidget:
        widget.setObjectName(f"setting_{key}")
        self.fields[key] = (widget, get, put)
        return widget

    def control(self, key: str) -> QWidget:
        """Controlul potrivit tipului cheii (bool, enum, int, float, color, path, string)."""
        d = definition(key)
        if d.value_type == "bool":
            box = QCheckBox(label(key))
            return self._register(key, box, box.isChecked, lambda v: box.setChecked(bool(v)))
        if d.value_type == "enum":
            combo = QComboBox()
            for value in d.allowed or ():
                combo.addItem(value_label(key, value), value)
            return self._register(key, combo, combo.currentData,
                                  lambda v: combo.setCurrentIndex(max(0, combo.findData(v))))
        if d.value_type in ("int", "float"):
            return self._number(key)
        if d.value_type == "color":
            return self._color(key)
        if d.value_type == "path":
            return self._path(key)
        edit = QLineEdit()
        return self._register(key, edit, lambda: edit.text() or None,
                              lambda v: edit.setText(v or ""))

    def _number(self, key: str) -> QWidget:
        """Numerele; la cheile care accepta None, valoarea minima afiseaza `Automat`."""
        d = definition(key)
        spin: QSpinBox | QDoubleSpinBox = QSpinBox() if d.value_type == "int" \
            else QDoubleSpinBox()
        low = d.min_value if d.min_value is not None else 0
        high = d.max_value if d.max_value is not None else 10**6
        if d.nullable:
            low -= 1
            spin.setSpecialValueText(tr("value.auto"))
        spin.setRange(low, high)
        cast = int if d.value_type == "int" else float

        def get() -> Any:
            value = spin.value()
            return None if d.nullable and value == spin.minimum() else cast(value)

        def put(value: Any) -> None:
            spin.setValue(spin.minimum() if value is None else cast(value))

        return self._register(key, spin, get, put)

    def _color(self, key: str) -> QWidget:
        button = QPushButton()
        state = {"value": "#000000"}

        def put(value: Any) -> None:
            state["value"] = str(value)
            button.setText(str(value))
            button.setStyleSheet(f"background-color: {value};")

        def pick() -> None:
            color = QColorDialog.getColor(QColor(state["value"]), self)
            if color.isValid():
                put(color.name())

        button.clicked.connect(pick)
        return self._register(key, button, lambda: state["value"], put)

    def _path(self, key: str) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        browse = QPushButton(tr("options.browse"))
        browse.clicked.connect(lambda: edit.setText(
            QFileDialog.getExistingDirectory(self, label(key)) or edit.text()))
        row.addWidget(edit, 1)
        row.addWidget(browse)
        return self._register(key, box, lambda: edit.text() or None,
                              lambda v: edit.setText(str(v) if v else ""))

    def _form(self, keys: tuple[str, ...] | list[str], parent: QVBoxLayout) -> QFormLayout:
        form = QFormLayout()
        for key in keys:
            widget = self.control(key)
            if isinstance(widget, QCheckBox):
                form.addRow(widget)
            else:
                form.addRow(label(key), widget)
        parent.addLayout(form)
        return form

    def _radios(self, key: str, values: tuple[str, ...], parent: Any) -> QButtonGroup:
        group = QButtonGroup(self)
        buttons: dict[str, QRadioButton] = {}
        for value in values:
            radio = QRadioButton(value_label(key, value))
            radio.setObjectName(f"radio_{key}_{value}")
            group.addButton(radio)
            buttons[value] = radio
            parent.addWidget(radio)

        def get() -> Any:
            return next((v for v, b in buttons.items() if b.isChecked()), self._initial[key])

        def put(value: Any) -> None:
            if value in buttons:
                buttons[value].setChecked(True)

        self._register(key, QWidget(), get, put)
        self.radios[key] = buttons
        return group

    @staticmethod
    def _link(text: str, on_click: Callable[[], Any]) -> QLabel:
        link = QLabel(f'<a href="#">{text}</a>')
        link.setTextFormat(Qt.TextFormat.RichText)
        link.linkActivated.connect(lambda _: on_click())
        return link

    def _help(self, key: str) -> None:
        QMessageBox.information(self, tr("options.title"), tr(f"options.help.{key}"))

    # --- taburile ----------------------------------------------------------------------

    def _tab_general(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        start = QGroupBox(tr("options.general.start"))  # X-403
        start_box = QVBoxLayout(start)
        self._radios("general.startup_screen", ("ocr_new_project", "ocr_last_project"),
                     start_box)
        layout.addWidget(start)
        device = QGroupBox(tr("options.general.device"))  # X-404
        device_box = QVBoxLayout(device)
        row = QHBoxLayout()
        edit = self.control("general.capture_device")
        edit.setReadOnly(True)
        self.select_device = QPushButton(tr("options.general.select_device"))
        self.select_device.setObjectName("select_device")
        self.select_device.clicked.connect(lambda: self.choose_device())  # X-407
        row.addWidget(edit, 1)
        row.addWidget(self.select_device)
        device_box.addLayout(row)
        self._radios("general.scan_interface", ("app", "driver"), device_box)  # X-405
        device_box.addWidget(self._link(tr("options.general.which_interface"),
                                        lambda: self._help("scan_interface")))
        layout.addWidget(device)
        self._form(["general.shell_integration"], layout)
        hot = QGroupBox(tr("options.general.hotfolder"))  # S-006, S-071
        hot_box = QVBoxLayout(hot)
        self._form(["hotfolder.autostart", "hotfolder.monthly_page_limit"], hot_box)
        layout.addWidget(hot)
        layout.addStretch(1)
        return page

    def choose_device(self, service: Any = None) -> bool:
        """X-404, X-407: dialogul `Select Device`; alegerea intra in camp."""
        from app.core.images.wia import default_scanner
        from app.gui.scan_dialog import DeviceDialog

        current = self.fields["general.capture_device"][1]()
        dialog = DeviceDialog(service or self.scanner_service or default_scanner(), current,
                              self)
        self.device_dialog = dialog
        if not dialog.exec() or dialog.chosen() is None:
            return False
        self.fields["general.capture_device"][2](dialog.chosen()[0])
        return True

    def _tab_image(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._form(["image.background_recognition_pdf"], layout)
        note = QLabel(tr("options.image.background_note"))  # X-408
        note.setWordWrap(True)
        layout.addWidget(note)
        languages = QHBoxLayout()  # X-409
        languages.addWidget(QLabel(tr("options.image.ocr_languages")))
        self.languages_link = self._link(self._languages_text(),
                                         lambda: self.show_tab("languages"))
        self.languages_link.setObjectName("languages_link")
        languages.addWidget(self.languages_link, 1)
        layout.addLayout(languages)
        self._form(["image.auto_process", "image.auto_mode", "image.use_recommended"], layout)
        modes = QGroupBox(tr("options.image.preprocess"))  # X-413
        modes_box = QVBoxLayout(modes)
        self._radios("image.preprocess_mode", ("auto", "manual", "none"), modes_box)
        for button in self.radios["image.preprocess_mode"].values():
            button.toggled.connect(self._update_dependencies)
        layout.addWidget(modes)
        self.custom_toggle = QPushButton(tr("options.image.show_custom"))  # X-411
        self.custom_toggle.setObjectName("custom_toggle")
        self.custom_toggle.setCheckable(True)
        self.custom_toggle.toggled.connect(self._toggle_custom)
        layout.addWidget(self.custom_toggle)
        self.custom = QWidget()
        self.custom.setObjectName("custom_settings")
        grid = QGridLayout(self.custom)  # X-410
        for col, keys in enumerate(PREPROCESS_COLUMNS):
            for row, key in enumerate(keys):
                box = self.control(key)
                if col == 1:
                    box.setText(f"{box.text()}*")
                grid.addWidget(box, row, col)
        grid.addWidget(QLabel(tr("options.image.photo_note")), 5, 0, 1, 3)  # X-412
        self.custom.setVisible(False)
        layout.addWidget(self.custom)
        layout.addStretch(1)
        return page

    def _toggle_custom(self, shown: bool) -> None:
        self.custom.setVisible(shown)
        self.custom_toggle.setText(tr("options.image.hide_custom" if shown
                                      else "options.image.show_custom"))

    def _languages_text(self) -> str:
        store = self.store("lang.manual")
        key = "lang.manual" if store.get("lang.mode") == "manual" else "lang.auto_candidates"
        return ", ".join(language_name(c) for c in store.get(key)) \
            or tr("options.languages.none")

    def _tab_languages(self) -> QWidget:
        from app.core.ocr.languages import LanguageRegistry

        page = QWidget()
        layout = QVBoxLayout(page)
        group = QVBoxLayout()
        self._radios("lang.mode", ("auto", "manual"), group)
        layout.addLayout(group)
        codes = LanguageRegistry(con=self.context.app_db).all()
        self.language_lists: dict[str, QListWidget] = {}
        for key in ("lang.auto_candidates", "lang.manual"):
            layout.addWidget(QLabel(label(key)))
            lst = QListWidget()
            for code in codes:
                item = QListWidgetItem(language_name(code))
                item.setData(Qt.ItemDataRole.UserRole, code)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                lst.addItem(item)
            self.language_lists[key] = lst
            layout.addWidget(lst, 1)

            def get(lst: QListWidget = lst, key: str = key) -> list[str]:
                """Ordinea conteaza (prima limba e cea principala): cele de dinainte
                raman in ordinea lor, cele noi se adauga la sfarsit."""
                checked = [lst.item(i).data(Qt.ItemDataRole.UserRole)
                           for i in range(lst.count())
                           if lst.item(i).checkState() == Qt.CheckState.Checked]
                before = [c for c in self._initial.get(key) or () if c in checked]
                return before + [c for c in checked if c not in before]

            def put(values: Any, lst: QListWidget = lst) -> None:
                chosen = set(values or ())
                for i in range(lst.count()):
                    item = lst.item(i)
                    item.setCheckState(Qt.CheckState.Checked if item.data(
                        Qt.ItemDataRole.UserRole) in chosen else Qt.CheckState.Unchecked)

            self._register(key, lst, get, put)
        return page

    def _tab_ocr(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._form(["ocr.pdf_mode"], layout)
        layout.addWidget(self._link(tr("options.ocr.which_mode"),  # X-415
                                    lambda: self._help("pdf_mode")))
        quality = QHBoxLayout()
        self._radios("ocr.quality", ("thorough", "fast"), quality)
        layout.addLayout(quality)
        self._form(["ocr.document_type", "ocr.detect_headers_footers", "ocr.detect_footnotes",
                    "ocr.detect_table_of_contents", "ocr.detect_numbered_lists",
                    "ocr.barcodes_to_text", "ocr.confidence_threshold",
                    "ocr.keep_cedilla_diacritics", "ocr.header_repeat_ratio"], layout)
        training = QGroupBox(tr("options.ocr.patterns"))
        grid = QGridLayout(training)
        patterns = QVBoxLayout()
        self._radios("ocr.patterns", ("builtin", "user"), patterns)
        also_user = self.control("ocr.user_patterns_also_builtin")
        use_training = self.control("ocr.use_training")
        also_training = self.control("ocr.training_also_builtin")
        for indented in (also_user, also_training):  # X-416: indentate sub parinte
            indented.setStyleSheet("margin-left: 24px;")
        patterns.insertWidget(2, also_user)
        patterns.addWidget(use_training)
        patterns.addWidget(also_training)
        for button in self.radios["ocr.patterns"].values():
            button.toggled.connect(self._update_dependencies)
        use_training.toggled.connect(self._update_dependencies)
        grid.addLayout(patterns, 0, 0)
        buttons = QVBoxLayout()  # X-417: coloana din dreapta
        editor = QPushButton(tr("options.ocr.pattern_editor"))
        editor.setObjectName("pattern_editor")
        editor.setEnabled(False)  # INCOMPLET: editorul de sabloane nu are inca dialog
        self.load_patterns = QPushButton(tr("options.ocr.load_patterns"))
        self.load_patterns.setObjectName("load_patterns")
        self.load_patterns.clicked.connect(lambda: self.patterns_bundle(load=True))
        self.save_patterns = QPushButton(tr("options.ocr.save_patterns"))
        self.save_patterns.setObjectName("save_patterns")
        self.save_patterns.clicked.connect(lambda: self.patterns_bundle(load=False))
        for button in (editor, self.load_patterns, self.save_patterns):
            buttons.addWidget(button)
        buttons.addStretch(1)
        grid.addLayout(buttons, 0, 1)
        layout.addWidget(training)
        fonts = QHBoxLayout()  # X-418
        fonts.addWidget(QLabel(tr("options.ocr.fonts")), 1)
        select_fonts = QPushButton(tr("options.ocr.select_fonts"))
        select_fonts.setObjectName("select_fonts")
        select_fonts.setEnabled(False)  # INCOMPLET: dialogul de fonturi
        fonts.addWidget(select_fonts)
        layout.addLayout(fonts)
        layout.addStretch(1)
        return page

    def patterns_bundle(self, *, load: bool, path: Path | None = None) -> bool:
        """X-417: `Load/Save Patterns and Languages...` (fisierul .fbtx, P-066)."""
        from app.core.errors import CoreError
        from app.core.ocr.patterns import PatternStore

        if path is None:
            dialog = QFileDialog.getOpenFileName if load else QFileDialog.getSaveFileName
            chosen, _ = dialog(self, tr("options.ocr.load_patterns" if load
                                        else "options.ocr.save_patterns"), "", "*.fbtx")
            if not chosen:
                return False
            path = Path(chosen)
        store = PatternStore(self.context.app_db)
        try:
            if load:
                store.load_bundle(path)
            else:
                store.save_bundle(path)
        except (CoreError, ValueError, OSError):
            self.error.setText(tr("options.patterns_failed"))
            return False
        return True

    def _tab_format(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("options.format.document_type")))
        self.formats = QListWidget()  # X-419, X-420
        self.formats.setObjectName("format_list")
        self.format_pages = QStackedWidget()
        for key, prefixes in FORMATS:
            self.formats.addItem(tr(f"options.format.{key}"))
            sub = QWidget()
            sub.setObjectName(f"format_{key}")
            box = QVBoxLayout(sub)
            keys = [d.key for d in CATALOG if d.key.startswith(prefixes)
                    and d.key not in OTHER_KEYS and d.value_type != "json"]
            self._form(keys, box)
            if key == "pdf":
                self._delete_items(box)
            box.addStretch(1)
            self.format_pages.addWidget(sub)
        self.formats.currentRowChanged.connect(self.format_pages.setCurrentIndex)
        self.formats.setCurrentRow(0)
        left.addWidget(self.formats, 1)
        layout.addLayout(left)
        layout.addWidget(self.format_pages, 1)
        for key in ("pdf.create_pdfua", "pdf.create_pdfa", "pdf.delete_objects"):
            self.fields[key][0].toggled.connect(self._update_dependencies)
        return page

    def _delete_items(self, box: QVBoxLayout) -> None:
        """X-084: elementele de sters, sub bifa `Delete objects and data`."""
        from app.core.settings import _DELETE_OBJECT_ITEMS

        self.delete_boxes: dict[str, QCheckBox] = {}
        for item in _DELETE_OBJECT_ITEMS:
            check = QCheckBox(tr(f"setting.pdf.delete_objects_items.{item}"))
            check.setObjectName(f"delete_item_{item}")
            check.setStyleSheet("margin-left: 24px;")
            self.delete_boxes[item] = check
            box.addWidget(check)

        def put(values: Any) -> None:
            for name, check in self.delete_boxes.items():
                check.setChecked(name in (values or ()))

        self._register("pdf.delete_objects_items", QWidget(),
                       lambda: [k for k, b in self.delete_boxes.items() if b.isChecked()], put)

    def _tab_areas(self) -> QWidget:
        from app.core.model import AreaType

        page = QWidget()
        layout = QVBoxLayout(page)
        self._form(["areas.check_uncertain", "areas.uncertain_color",
                    "areas.ignore_words_with_digits", "areas.check_compound_words",
                    "areas.fix_punctuation_spaces", "areas.user_dictionaries_folder",
                    "areas.show_numbers", "areas.show_nonprinting"], layout)
        font = QComboBox()  # O-029, X-164
        font.addItem(tr("options.areas.default_font"), None)
        for family in QFontDatabase.families():
            font.addItem(family, family)
        self._register("areas.plain_text_font", font, font.currentData,
                       lambda v: font.setCurrentIndex(max(0, font.findData(v))))
        form = QFormLayout()
        form.addRow(label("areas.plain_text_font"), font)
        layout.addLayout(form)
        colors = QGroupBox(tr("options.areas.colors"))  # X-165, M-100, M-101
        grid = QGridLayout(colors)
        for row, kind in enumerate(AreaType):
            grid.addWidget(QLabel(tr(f"image.tool.{kind.value}")), row, 0)
            grid.addWidget(self.control(f"areas.color.{kind.value}"), row, 1)
            grid.addWidget(self.control(f"areas.border_width.{kind.value}"), row, 2)
        layout.addWidget(colors)
        layout.addStretch(1)
        return page

    def _tab_other(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._form(list(OTHER_KEYS), layout)
        layout.addStretch(1)
        return page

    # --- dependentele (X-414, X-416, X-421, X-422) ------------------------------------------

    def _update_dependencies(self, *_: Any) -> None:
        if not self._initial:
            return
        mode = self.fields["image.preprocess_mode"][1]()
        for keys in PREPROCESS_COLUMNS:  # X-414: bifele raman, doar se dezactiveaza
            for key in keys:
                self.fields[key][0].setEnabled(mode != "none")
        user = self.fields["ocr.patterns"][1]() == "user"
        self.fields["ocr.user_patterns_also_builtin"][0].setEnabled(user)  # X-416
        self.fields["ocr.training_also_builtin"][0].setEnabled(
            self.fields["ocr.use_training"][0].isChecked())
        pdfua = self.fields["pdf.create_pdfua"][0].isChecked()
        tags = self.fields["pdf.create_tags"][0]
        if pdfua:  # X-421: tagurile sunt fortate de PDF/UA
            tags.setChecked(True)
        tags.setEnabled(not pdfua)
        self.fields["pdf.pdfa_version"][0].setEnabled(  # X-422
            self.fields["pdf.create_pdfa"][0].isChecked())
        deleting = self.fields["pdf.delete_objects"][0].isChecked()
        for box in self.delete_boxes.values():
            box.setEnabled(deleting)

    # --- citirea si salvarea ---------------------------------------------------------------

    def load(self) -> None:
        self._initial = {key: self.store(key).get(key) for key in self.fields}
        for key, (_, _, put) in self.fields.items():
            put(self._initial[key])
        self._update_dependencies()

    def values(self) -> dict[str, Any]:
        return {key: get() for key, (_, get, _) in self.fields.items()}

    def apply(self) -> bool:
        """Scrie numai cheile schimbate; o valoare refuzata de nucleu opreste salvarea."""
        changed = {k: v for k, v in self.values().items() if v != self._initial[k]}
        for key, value in changed.items():
            try:
                definition(key).validate(value)
            except ValueError:
                self.error.setText(tr("options.invalid", setting=label(key)))
                return False
        for key, value in changed.items():
            self.store(key).set(key, value)
        self._initial.update(changed)
        self.applied.emit()
        return True

    def accept(self) -> None:
        if self.apply():
            super().accept()
