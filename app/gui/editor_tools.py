"""Uneltele OCR Editor-ului din `Tools` si `View` (J-013, J-059…J-063, J-302,
O-036, O-037, P-040…P-044, P-053…P-063).

- `DictionaryDialog`: `Tools > View Dictionaries...` (`Ctrl+Alt+D`): limba, cuvintele
  dictionarului utilizatorului, `Add word` (duplicat → avertisment), `Delete`,
  `Import...`, `Export...`.
- `PatternEditorDialog`: `Tools > Pattern Editor...`: sabloanele, `New...`,
  `Set Active`, caracterele antrenate, `Properties...` (`Character`, `Effects`),
  `Delete`.
- `StyleEditorDialog`: `Tools > Style Editor...`: stilurile textului si
  proprietatile lor (O-037, O-110).
- `ReorderPagesDialog`: dialogul de reordonare din panoul `Pages` (J-059…J-063).
- `WarningsPanel`: `View > Show Warnings` (J-013): avertismentele paginii alese,
  cu navigare si stergere.

Regulile sunt in nucleu (`DictionaryService`, `PatternStore`, `StyleManager`,
`OcrProject`); aici numai afisarea.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.gui.i18n import tr, tr_exception


def _button(key: str, slot: Any, layout: Any) -> QPushButton:
    button = QPushButton(tr(key))
    button.setObjectName(key.replace(".", "_"))
    button.clicked.connect(lambda _=False: slot())
    layout.addWidget(button)
    return button


# --- dictionarele (P-040…P-044) ------------------------------------------------------------

class DictionaryDialog(QDialog):
    """P-040: `View Dictionaries...`: limba, apoi cuvintele ei."""

    def __init__(self, context: Any, languages: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.ocr.dictionary import DictionaryService
        from app.gui.options_dialog import language_name

        self.setObjectName("dictionary_dialog")
        self.setWindowTitle(tr("dictionary.title"))
        self.service = DictionaryService(context.app_db, context.settings)
        self.messages: list[str] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.language = QComboBox()
        self.language.setObjectName("dictionary_language")
        for code in languages:
            self.language.addItem(language_name(code), code)
        self.language.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow(tr("dictionary.language"), self.language)
        layout.addLayout(form)
        self.words = QListWidget()
        self.words.setObjectName("dictionary_words")
        layout.addWidget(self.words, 1)
        row = QHBoxLayout()
        self.word = QLineEdit()
        self.word.setObjectName("dictionary_word")
        self.word.setPlaceholderText(tr("dictionary.word"))
        row.addWidget(self.word, 1)
        _button("dictionary.add", self.add_word, row)
        _button("dictionary.delete", self.delete_word, row)
        layout.addLayout(row)
        files = QHBoxLayout()
        _button("dictionary.import", self.import_words, files)
        _button("dictionary.export", self.export_words, files)
        files.addStretch(1)
        layout.addLayout(files)
        self.message = QLabel()
        self.message.setObjectName("dictionary_message")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(460, 520)
        self.refresh()

    def code(self) -> str:
        return str(self.language.currentData() or "")

    def refresh(self) -> None:
        self.words.clear()
        if self.code():
            self.words.addItems(sorted(self.service.words(self.code()), key=str.lower))

    def _say(self, text: str) -> None:
        self.messages.append(text)
        self.message.setText(text)

    def add_word(self, word: str | None = None) -> bool:
        """P-041: un duplicat produce un avertisment."""
        word = (word if word is not None else self.word.text()).strip()
        if not word or not self.code():
            return False
        try:
            added = self.service.add(word, self.code())
        except (CoreError, ValueError) as exc:
            self._say(tr_exception(exc))
            return False
        if not added:
            self._say(tr("dictionary.duplicate", word=word))
            return False
        self.word.clear()
        self.refresh()
        return True

    def delete_word(self) -> bool:
        item = self.words.currentItem()
        if item is None:
            return False
        self.service.remove(item.text(), self.code())
        self.refresh()
        return True

    def pick_open(self) -> Path | None:
        chosen, _ = QFileDialog.getOpenFileName(self, tr("dictionary.import"), "",
                                                tr("dictionary.filter"))
        return Path(chosen) if chosen else None

    def pick_save(self) -> Path | None:
        chosen, _ = QFileDialog.getSaveFileName(self, tr("dictionary.export"),
                                                f"{self.code()}.txt", tr("dictionary.filter"))
        return Path(chosen) if chosen else None

    def import_words(self) -> int:
        """P-044: lista de cuvinte (si dictionarele exportate din alte programe)."""
        path = self.pick_open()
        if path is None:
            return 0
        count = self.service.import_words(path, self.code())
        self._say(tr("dictionary.imported", count=count))
        self.refresh()
        return count

    def export_words(self) -> int:
        path = self.pick_save()
        if path is None:
            return 0
        return self.service.export_words(path, self.code())

    def done(self, result: int) -> None:  # API Qt
        self.service.end_edit()
        super().done(result)


# --- sabloanele de caractere (P-053…P-063) -------------------------------------------------

class PatternEditorDialog(QDialog):
    """P-053: `Pattern Editor`."""

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.ocr.patterns import PatternStore

        self.setObjectName("pattern_editor")
        self.setWindowTitle(tr("patterns.title"))
        self.store = PatternStore(context.app_db)
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("patterns.sets")))
        self.sets = QListWidget()
        self.sets.setObjectName("pattern_sets")
        self.sets.currentRowChanged.connect(lambda _r: self.show_characters())
        left.addWidget(self.sets, 1)
        buttons = QHBoxLayout()
        _button("patterns.new", self.new_set, buttons)
        _button("patterns.set_active", self.set_active, buttons)
        _button("patterns.delete_set", self.delete_set, buttons)
        left.addLayout(buttons)
        layout.addLayout(left, 1)
        right = QVBoxLayout()
        right.addWidget(QLabel(tr("patterns.characters")))
        self.characters = QListWidget()
        self.characters.setObjectName("pattern_characters")
        right.addWidget(self.characters, 1)
        char_buttons = QHBoxLayout()
        _button("patterns.properties", self.edit_character, char_buttons)
        _button("patterns.delete", self.delete_character, char_buttons)
        right.addLayout(char_buttons)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        right.addWidget(close)
        layout.addLayout(right, 1)
        self.resize(640, 440)
        self.refresh()

    def refresh(self, select: str | None = None) -> None:
        active = self.store.active_set()
        self.sets.clear()
        for name in self.store.sets():
            item = QListWidgetItem(name + (f"  {tr('patterns.active_mark')}"
                                           if name == active else ""))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.sets.addItem(item)
            if name == select:
                self.sets.setCurrentItem(item)
        if self.sets.currentRow() < 0 and self.sets.count():
            self.sets.setCurrentRow(0)
        self.show_characters()

    def current_set(self) -> str | None:
        item = self.sets.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def show_characters(self) -> None:
        self.characters.clear()
        name = self.current_set()
        if not name:
            return
        for char in self.store.characters(name):
            item = QListWidgetItem(f"{char.character}   ({', '.join(char.effects) or '-'})")
            item.setData(Qt.ItemDataRole.UserRole, char.id)
            self.characters.addItem(item)

    def ask_text(self, title_key: str, label_key: str, value: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, tr(title_key), tr(label_key), text=value)
        return text.strip() if ok and text.strip() else None

    def new_set(self) -> str | None:
        """P-054: `Create Pattern`, cu un nume."""
        name = self.ask_text("patterns.create", "patterns.name")
        if name is None:
            return None
        try:
            self.store.create_set(name)
        except (CoreError, ValueError) as exc:
            QMessageBox.warning(self, tr("patterns.title"), tr_exception(exc))
            return None
        self.refresh(name)
        return name

    def set_active(self) -> None:
        """P-061: un singur sablon activ."""
        name = self.current_set()
        if name:
            self.store.set_active(name)
            self.refresh(name)

    def delete_set(self) -> None:
        name = self.current_set()
        if name:
            self.store.delete_set(name)
            self.refresh()

    def edit_character(self) -> bool:
        """P-062: `Properties...` cu `Character` si `Effects`."""
        item = self.characters.currentItem()
        if item is None:
            return False
        char_id = item.data(Qt.ItemDataRole.UserRole)
        current = next(c for c in self.store.characters(self.current_set() or "")
                       if c.id == char_id)
        value = self.ask_text("patterns.properties", "patterns.character", current.character)
        if value is None:
            return False
        self.store.edit(char_id, character=value)
        self.show_characters()
        return True

    def delete_character(self) -> bool:
        """P-063."""
        item = self.characters.currentItem()
        if item is None:
            return False
        self.store.delete_pattern(item.data(Qt.ItemDataRole.UserRole))
        self.show_characters()
        return True


# --- stilurile textului (O-036, O-037, O-110) ------------------------------------------------

class StyleEditorDialog(QDialog):
    """O-036: `Style Editor...`: stilurile si proprietatile lor."""

    changed = Signal()

    def __init__(self, context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.text.styles import StyleManager

        self.setObjectName("style_editor")
        self.setWindowTitle(tr("styles.title"))
        self.manager = StyleManager(context.app_db)
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setObjectName("styles_list")
        self.list.currentRowChanged.connect(lambda _r: self.show_style())
        left.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        _button("styles.new", self.new_style, buttons)
        self.delete_button = _button("styles.delete", self.delete_style, buttons)
        left.addLayout(buttons)
        layout.addLayout(left, 1)
        box = QGroupBox(tr("styles.properties"))
        form = QFormLayout(box)
        self.font = QFontComboBox()
        self.font.setObjectName("style_font")
        form.addRow(tr("styles.font"), self.font)
        self.size = QDoubleSpinBox()
        self.size.setObjectName("style_size")
        self.size.setRange(0, 400)
        self.size.setSpecialValueText(tr("styles.auto"))
        form.addRow(tr("styles.size"), self.size)
        self.scale = QDoubleSpinBox()
        self.scale.setObjectName("style_scale")
        self.scale.setRange(10, 500)
        self.scale.setSuffix(" %")
        form.addRow(tr("styles.scale"), self.scale)
        self.spacing = QDoubleSpinBox()
        self.spacing.setObjectName("style_spacing")
        self.spacing.setRange(-20, 100)
        form.addRow(tr("styles.spacing"), self.spacing)
        self.flags: dict[str, QCheckBox] = {}
        for key in ("is_bold", "is_italic", "is_underline", "is_smallcaps"):
            check = QCheckBox(tr(f"styles.{key}"))
            check.setObjectName(f"style_{key}")
            self.flags[key] = check
            form.addRow(check)
        self.heading = QSpinBox()
        self.heading.setObjectName("style_heading")
        self.heading.setRange(0, 10)
        self.heading.setSpecialValueText(tr("styles.no_heading"))
        form.addRow(tr("styles.heading"), self.heading)
        self.apply_button = QPushButton(tr("styles.apply"))
        self.apply_button.setObjectName("styles_apply")
        self.apply_button.clicked.connect(lambda: self.apply())
        form.addRow(self.apply_button)
        right = QVBoxLayout()
        right.addWidget(box)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        right.addWidget(close)
        layout.addLayout(right, 1)
        self.resize(640, 460)
        self.refresh()

    def refresh(self, select: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for style in self.manager.all():
            item = QListWidgetItem(style.name)
            self.list.addItem(item)
            if style.name == select:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self.show_style()

    def current(self) -> Any:
        item = self.list.currentItem()
        return self.manager.get(item.text()) if item is not None else None

    def show_style(self) -> None:
        style = self.current()
        if style is None:
            return
        if style.font_name:
            self.font.setCurrentText(style.font_name)
        self.size.setValue(style.font_size or 0)
        self.scale.setValue(style.horizontal_scale)
        self.spacing.setValue(style.letter_spacing)
        for key, check in self.flags.items():
            check.setChecked(bool(getattr(style, key)))
        self.heading.setValue(style.heading_level)
        self.delete_button.setEnabled(not style.is_builtin)

    def apply(self) -> Any:
        """O-037: proprietatile stilului; textul care il foloseste se schimba fara
        a relua recunoasterea (Y-204)."""
        style = self.current()
        if style is None:
            return None
        props = {"font_name": self.font.currentText(),
                 "font_size": self.size.value() or None,
                 "horizontal_scale": self.scale.value(), "letter_spacing": self.spacing.value(),
                 "heading_level": self.heading.value(),
                 **{k: c.isChecked() for k, c in self.flags.items()}}
        try:
            updated = self.manager.update(style.name, **props)
        except (CoreError, ValueError) as exc:
            QMessageBox.warning(self, tr("styles.title"), tr_exception(exc))
            return None
        self.changed.emit()
        return updated

    def new_style(self) -> Any:
        name, ok = QInputDialog.getText(self, tr("styles.new"), tr("styles.name"))
        if not ok or not name.strip():
            return None
        try:
            style = self.manager.create(name.strip())
        except (CoreError, ValueError) as exc:
            QMessageBox.warning(self, tr("styles.title"), tr_exception(exc))
            return None
        self.refresh(style.name)
        return style

    def delete_style(self) -> bool:
        style = self.current()
        if style is None or style.is_builtin:
            return False
        self.manager.delete(style.name)
        self.refresh()
        self.changed.emit()
        return True


# --- reordonarea paginilor (J-059…J-063) ----------------------------------------------------

class ReorderPagesDialog(QDialog):
    """J-059: `Reorder Pages...`: refacerea ordinii dupa scanarea duplex (J-061),
    inversarea paginilor de carte (J-062), anularea ultimei reordonari (J-063)."""

    def __init__(self, project: Any, selected: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reorder_dialog")
        self.setWindowTitle(tr("reorder.title"))
        self.project = project
        self.selected = sorted(selected) if len(selected) > 1 else \
            [p.page_number for p in project.pages]
        layout = QVBoxLayout(self)
        box = QGroupBox(tr("reorder.group"))  # J-060
        col = QVBoxLayout(box)
        consecutive = all(b - a == 1 for a, b in zip(self.selected, self.selected[1:],
                                                       strict=False))
        self.duplex = QRadioButton(tr("reorder.duplex"))  # J-061
        self.duplex.setObjectName("reorder_duplex")
        self.duplex.setEnabled(consecutive and len(self.selected) >= 3)
        col.addWidget(self.duplex)
        self.reversed = QCheckBox(tr("reorder.backs_reversed"))
        self.reversed.setObjectName("reorder_reversed")
        self.reversed.setChecked(True)
        col.addWidget(self.reversed)
        self.swap = QRadioButton(tr("reorder.swap"))  # J-062
        self.swap.setObjectName("reorder_swap")
        self.swap.setEnabled(consecutive and len(self.selected) >= 2)
        col.addWidget(self.swap)
        (self.duplex if self.duplex.isEnabled() else self.swap).setChecked(True)
        layout.addWidget(box)
        self.undo_button = QPushButton(tr("reorder.undo"))  # J-063
        self.undo_button.setObjectName("reorder_undo")
        self.undo_button.setEnabled(self._last_is_reorder())
        self.undo_button.clicked.connect(lambda: self.undo_last())
        layout.addWidget(self.undo_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _last_is_reorder(self) -> bool:
        description = self.project.undo_description() if self.project.can_undo() else ""
        return any(k in (description or "") for k in ("reorder", "interleave", "swap", "duplex"))

    def apply(self) -> bool:
        try:
            if self.duplex.isChecked() and self.duplex.isEnabled():
                self.project.interleave_duplex(self.selected,
                                               backs_reversed=self.reversed.isChecked())
            elif self.swap.isChecked() and self.swap.isEnabled():
                self.project.swap_book_pages(self.selected)
            else:
                return False
        except (CoreError, ValueError) as exc:
            QMessageBox.warning(self, tr("reorder.title"), tr_exception(exc))
            return False
        self.accept()
        return True

    def undo_last(self) -> bool:
        """J-063: anuleaza ultima reordonare."""
        if not self._last_is_reorder():
            return False
        self.project.undo()
        self.undo_button.setEnabled(self._last_is_reorder())
        return True


# --- panoul de avertismente (J-013) ----------------------------------------------------------

class WarningsPanel(QWidget):
    """J-013: mesajele paginii alese, cu navigare la paginile cu avertismente si
    stergere."""

    page_requested = Signal(int)
    changed = Signal()

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("warnings_panel")
        self.project = project
        self.page = 1
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("warnings_items")
        self.list.setWordWrap(True)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        _button("warnings.previous", lambda: self.step(-1), row)
        _button("warnings.next", lambda: self.step(1), row)
        _button("warnings.delete", self.delete_current, row)
        layout.addLayout(row)

    def show_page(self, number: int) -> None:
        self.page = number
        self.list.clear()
        if not 1 <= number <= len(self.project.pages):
            return
        for warning in self.project.page(number).warnings:
            if warning.is_dismissed:
                continue
            item = QListWidgetItem(tr(warning.message_key, **dict(warning.params)))
            item.setData(Qt.ItemDataRole.UserRole, warning.code)
            self.list.addItem(item)

    def pages_with_warnings(self) -> list[int]:
        return [p.page_number for p in self.project.pages
                if any(not w.is_dismissed for w in p.warnings)]

    def step(self, direction: int) -> int | None:
        pages = self.pages_with_warnings()
        candidates = [p for p in pages if (p > self.page if direction > 0 else p < self.page)]
        if not candidates:
            return None
        target = candidates[0] if direction > 0 else candidates[-1]
        self.page_requested.emit(target)
        return target

    def delete_current(self) -> bool:
        item = self.list.currentItem() or (self.list.item(0) if self.list.count() else None)
        if item is None:
            return False
        self.project.dismiss_warning(self.page, item.data(Qt.ItemDataRole.UserRole))
        self.show_page(self.page)
        self.changed.emit()
        return True


class PatternTrainingDialog(QDialog):
    """P-055…P-057: `Pattern Training`. Cuvintele paginii se parcurg caracter cu
    caracter (`glyph_boxes`); fiecare caracter primeste textul si efectele lui
    (bold, italic, exponent, indice) si se adauga la sablonul activ. `Back` revine
    la caracterul anterior din acelasi cuvant."""

    EFFECTS = ("bold", "italic", "superscript", "subscript")

    def __init__(self, context: Any, page: Any, set_name: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import numpy as np
        from PIL import Image

        from app.core.ocr.patterns import PatternStore, glyph_boxes

        self.setObjectName("pattern_training")
        self.setWindowTitle(tr("training.title"))
        self.store = PatternStore(context.app_db)
        self.page = page
        self.set_name = set_name
        with Image.open(page.image_path) as src:
            array = np.asarray(src.convert("L"))
        self.words: list[list[Any]] = [b for b in (glyph_boxes(array, w.bbox)
                                                   for w in page.iter_words()) if b]
        self.word_index, self.char_index = 0, 0
        self.trained = 0
        self.preview = QLabel()
        self.preview.setObjectName("training_glyph")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(120, 120)
        self.character = QLineEdit()
        self.character.setObjectName("training_character")
        self.character.setMaxLength(2)  # P-060: unul sau doua caractere
        self.effects = {key: QCheckBox(tr(f"training.effect.{key}")) for key in self.EFFECTS}
        self.position = QLabel()
        self.position.setObjectName("training_position")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        for key, slot in (("train", self.train), ("skip", self.skip), ("back", self.back),
                          ("close", self.accept)):
            button = QPushButton(tr(f"training.{key}"))
            button.setObjectName(f"training_{key}")
            button.clicked.connect(slot)
            self.buttons[key] = button
            row.addWidget(button)
        self.buttons["train"].setDefault(True)
        effects = QHBoxLayout()
        for box in self.effects.values():
            effects.addWidget(box)
        form = QFormLayout()
        form.addRow(tr("training.character"), self.character)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.position)
        layout.addLayout(form)
        layout.addLayout(effects)
        layout.addWidget(self.message)
        layout.addLayout(row)
        self._image = Image.fromarray(array)
        self._show()

    def current(self) -> Any:
        if self.word_index >= len(self.words):
            return None
        return self.words[self.word_index][self.char_index]

    def _show(self) -> None:
        from PIL.ImageQt import ImageQt
        from PySide6.QtGui import QPixmap

        box = self.current()
        done = box is None
        for key in ("train", "skip"):
            self.buttons[key].setEnabled(not done)
        self.buttons["back"].setEnabled(not done and self.char_index > 0)  # P-057
        self.character.setEnabled(not done)
        if done:
            self.preview.clear()
            self.position.setText(tr("training.done", n=self.trained))
            return
        crop = self._image.crop((box.x, box.y, box.right, box.bottom))
        pixmap = QPixmap.fromImage(ImageQt(crop.convert("RGB")))
        self.preview.setPixmap(pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio))
        self.position.setText(tr("training.position", word=self.word_index + 1,
                                 words=len(self.words), char=self.char_index + 1,
                                 chars=len(self.words[self.word_index])))
        self.character.clear()
        self.character.setFocus()

    def _advance(self) -> None:
        self.char_index += 1
        if self.char_index >= len(self.words[self.word_index]):
            self.word_index, self.char_index = self.word_index + 1, 0
        self._show()

    def train(self) -> bool:
        """P-055, P-056: caracterul, cu efectele bifate, intra in sablon."""
        from app.core.errors import CoreError

        box, text = self.current(), self.character.text().strip()
        if box is None or not text:
            return False
        effects = [k for k, b in self.effects.items() if b.isChecked()]
        try:
            self.store.train(self.set_name, self.page.image_path, box, text, effects=effects,
                             dpi=int(self.page.dpi_x or 300))
        except (CoreError, ValueError) as exc:
            self.message.setText(tr_exception(exc))
            return False
        self.trained += 1
        self.message.clear()
        self._advance()
        return True

    def skip(self) -> None:
        if self.current() is not None:
            self._advance()

    def back(self) -> None:
        """P-057: caracterul anterior din acelasi cuvant."""
        if self.current() is not None and self.char_index > 0:
            self.char_index -= 1
            self._show()
