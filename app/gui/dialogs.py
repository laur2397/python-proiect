"""Dialogurile panoului Text (faza 6b, pasul 6b.3b).

- `SymbolDialog` — `More Symbols...`: combo `Subset` si campul `Character
  code` (O-008, O-109).
- `LinkDialog` — `Hyperlink...`: pagina web cu protocol, fisier local cu
  `Browse...`, e-mail cu `mailto:`, plus `Text to display` (O-053…O-056).
- `VerifyDialog` — `Verify Text...`: parcurge cuvintele nesigure ale
  proiectului (O-003), `Skip` (O-004), `Replace` (O-005), `Add to
  Dictionary` (O-006), fontul cuvantului (O-007), simbolurile (O-109),
  `Options...` (O-009), sugestiile, si cele CJK (O-010).

Regulile (ce e nesigur, ce sugestii exista, prefixele adreselor) sunt in
nucleu (`TextEditor`, `links.make_url`); dialogurile doar le cheama.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.model import WordData
from app.core.text.editor import TextEditor
from app.core.text.links import EMAIL, FILE, WEB, WEB_PROTOCOLS, make_url
from app.gui.i18n import tr, tr_error

SUBSETS = (
    ("latin_1", 0x00A0, 0x00FF),
    ("latin_ext_a", 0x0100, 0x017F),
    ("latin_ext_b", 0x0180, 0x024F),
    ("comma_below", 0x0218, 0x021B),
    ("greek", 0x0370, 0x03FF),
    ("cyrillic", 0x0400, 0x04FF),
    ("punctuation", 0x2000, 0x206F),
    ("currency", 0x20A0, 0x20CF),
    ("letterlike", 0x2100, 0x214F),
    ("arrows", 0x2190, 0x21FF),
    ("math", 0x2200, 0x22FF),
    ("shapes", 0x25A0, 0x25FF),
)
"""O-008: grupurile din combo-ul `Subset` (blocuri Unicode). `comma_below`
pune la indemana Ș ș Ț ț cu virgula (CLAUDE.md §6.4)."""

COLUMNS = 16


class SymbolDialog(QDialog):
    """O-008, O-109: simbolul ales din tabel sau scris ca cod hexazecimal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("symbol_dialog")
        self.setWindowTitle(tr("symbol.title"))
        self.subset = QComboBox()
        self.subset.setObjectName("symbol_subset")
        for key, first, last in SUBSETS:
            self.subset.addItem(tr(f"symbol.subset.{key}"), (first, last))
        self.table = QTableWidget()
        self.table.setObjectName("symbol_table")
        self.table.setColumnCount(COLUMNS)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.code = QLineEdit()
        self.code.setObjectName("symbol_code")
        self.code.setMaxLength(8)
        self.preview = QLabel()
        self.preview.setObjectName("symbol_preview")
        self.subset.currentIndexChanged.connect(self._fill)
        self.table.currentCellChanged.connect(self._cell_chosen)
        self.table.cellDoubleClicked.connect(lambda *_: self.accept())
        self.code.textEdited.connect(self._code_typed)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow(tr("symbol.subset"), self.subset)
        form.addRow(tr("symbol.code"), self.code)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        self.symbol = ""
        self._fill()

    def _fill(self) -> None:
        first, last = self.subset.currentData()
        count = last - first + 1
        self.table.clearContents()
        self.table.setRowCount((count + COLUMNS - 1) // COLUMNS)
        for n in range(count):
            item = QTableWidgetItem(chr(first + n))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(n // COLUMNS, n % COLUMNS, item)

    def _cell_chosen(self, row: int, col: int, *_: int) -> None:
        item = self.table.item(row, col)
        if item is not None:
            self._set(item.text(), update_code=True)

    def _code_typed(self, text: str) -> None:
        try:
            value = int(text.strip().upper().removeprefix("U+"), 16)
            self._set(chr(value) if 0x20 <= value <= 0x10FFFF else "")
        except ValueError:
            self._set("")

    def _set(self, symbol: str, *, update_code: bool = False) -> None:
        self.symbol = symbol
        self.preview.setText(symbol)
        if symbol and update_code:
            self.code.setText(f"{ord(symbol):04X}")

    def choose(self, code: str) -> str:
        """Codul hexazecimal scris in campul `Character code`."""
        self.code.setText(code)
        self._code_typed(code)
        return self.symbol


class LinkDialog(QDialog):
    """O-053…O-056: tipul legaturii, adresa, `Text to display`."""

    def __init__(self, text_to_display: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("link_dialog")
        self.setWindowTitle(tr("link.title"))
        self.kinds = QButtonGroup(self)
        self.kind_buttons: dict[str, QRadioButton] = {}
        self.protocol = QComboBox()
        self.protocol.setObjectName("link_protocol")
        self.protocol.addItems(list(WEB_PROTOCOLS))
        self.protocol.setCurrentText("https://")
        self.address = QLineEdit()
        self.address.setObjectName("link_address")
        self.browse = QPushButton(tr("link.browse"))
        self.browse.setObjectName("link_browse")
        self.browse.clicked.connect(self._browse)
        kinds = QHBoxLayout()
        for kind in (WEB, FILE, EMAIL):
            button = QRadioButton(tr(f"link.kind.{kind}"))
            button.setObjectName(f"link_{kind}")
            self.kinds.addButton(button)
            self.kind_buttons[kind] = button
            kinds.addWidget(button)
            button.toggled.connect(self._kind_changed)
        self.display = QLineEdit(text_to_display)
        self.display.setObjectName("link_display")
        self.error = QLabel()
        self.error.setObjectName("link_error")
        address_row = QHBoxLayout()
        address_row.addWidget(self.protocol)
        address_row.addWidget(self.address, 1)
        address_row.addWidget(self.browse)
        form = QFormLayout()
        form.addRow(tr("link.link_to"), kinds)
        form.addRow(tr("link.address"), address_row)
        form.addRow(tr("link.display"), self.display)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self.kind_buttons[WEB].setChecked(True)

    @property
    def kind(self) -> str:
        return next((k for k, b in self.kind_buttons.items() if b.isChecked()), WEB)

    def set_kind(self, kind: str) -> None:
        self.kind_buttons[kind].setChecked(True)

    def _kind_changed(self) -> None:
        self.protocol.setVisible(self.kind == WEB)  # O-054
        self.browse.setVisible(self.kind == FILE)  # O-055

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("link.browse"))
        if path:
            self.address.setText(path)

    def url(self) -> str:
        """Adresa completa, cu prefixul tipului (din nucleu: `make_url`)."""
        return make_url(self.kind, self.address.text(), self.protocol.currentText())

    def accept(self) -> None:
        try:
            self.url()
        except ValueError:
            self.error.setText(tr("link.invalid"))
            return
        super().accept()


class VerifyDialog(QDialog):
    """O-003: cuvintele nesigure ale proiectului, unul cate unul."""

    word_changed = Signal(object)
    """Cuvantul curent (fereastra il arata in text si in imagine)."""
    options_requested = Signal()
    """O-009: `Options...` deschide setarile de verificare (dialogul Options)."""
    changed = Signal()

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("verify_dialog")
        self.setWindowTitle(tr("verify.title"))
        self.project = project
        self.word: WordData | None = None
        self.finished_all = False
        self.context = QLabel()
        self.context.setObjectName("verify_context")
        self.context.setWordWrap(True)
        self.edit = QLineEdit()
        self.edit.setObjectName("verify_word")
        self.suggestions = QListWidget()
        self.suggestions.setObjectName("verify_suggestions")
        self.suggestions.currentTextChanged.connect(self._suggestion_chosen)
        self.status = QLabel()
        self.status.setObjectName("verify_status")
        buttons = QVBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, slot in (("skip", self.skip), ("replace", self.replace),
                          ("add", self.add_to_dictionary), ("symbol", self.insert_symbol),
                          ("options", self.options_requested.emit), ("close", self.reject)):
            button = QPushButton(tr(f"verify.{key}"))
            button.setObjectName(f"verify_{key}")
            button.clicked.connect(lambda _=False, s=slot: s())
            buttons.addWidget(button)
            self.buttons[key] = button
        buttons.addStretch(1)
        self.font_combo = QFontComboBox()  # O-007
        self.font_combo.setObjectName("verify_font")
        self.font_combo.activated.connect(lambda _: self._format(
            font_name=self.font_combo.currentFont().family()))
        self.effects: dict[str, QCheckBox] = {}
        effects = QHBoxLayout()
        for key, attr in (("bold", "is_bold"), ("italic", "is_italic"),
                          ("underline", "is_underline")):
            box = QCheckBox(tr(f"text.{key}"))
            box.setObjectName(f"verify_{key}")
            box.clicked.connect(lambda on, a=attr: self._format(**{a: bool(on)}))
            self.effects[attr] = box
            effects.addWidget(box)
        left = QGridLayout()
        left.addWidget(self.context, 0, 0)
        left.addWidget(self.edit, 1, 0)
        left.addWidget(self.font_combo, 2, 0)
        left.addLayout(effects, 3, 0)
        left.addWidget(QLabel(tr("verify.suggestions")), 4, 0)
        left.addWidget(self.suggestions, 5, 0)
        left.addWidget(self.status, 6, 0)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addLayout(buttons)

    @property
    def editor(self) -> TextEditor:
        return TextEditor(self.project)

    # --- parcurgerea ----------------------------------------------------------------

    def start(self) -> bool:
        """Primul cuvant nesigur; False si mesaj cand nu e niciunul (O-003)."""
        return self._go(self.editor.next_uncertain(self.project.pages))

    def advance(self) -> bool:
        pages = self.project.pages
        following = None
        if self.word is not None:
            current = self._fresh(self.word)
            following = self.editor.next_uncertain(pages, current) if current else None
        if following is None:  # de la inceput: cele rezolvate nu mai apar
            following = self.editor.next_uncertain(pages)
        return self._go(following)

    def _go(self, word: WordData | None) -> bool:
        self.word = word
        if word is None:
            self.finished_all = True
            self.status.setText(tr("verify.done"))
            self.edit.setText("")
            self.context.setText("")
            self.suggestions.clear()
            for key in ("skip", "replace", "add", "symbol"):
                self.buttons[key].setEnabled(False)
            return False
        self.edit.setText(word.text)
        self.context.setText(self._line_of(word))
        self.suggestions.blockSignals(True)
        self.suggestions.clear()
        self.suggestions.addItems(self.editor.suggestions(word))
        self.suggestions.blockSignals(False)
        for attr, box in self.effects.items():
            box.setChecked(bool(getattr(word, attr)))
        if word.font_name:
            self.font_combo.setCurrentFont(QFont(word.font_name))
        self.status.setText("")
        self.word_changed.emit(word)
        return True

    def _suggestion_chosen(self, text: str) -> None:
        if text:
            self.edit.setText(text)

    def _fresh(self, word: WordData) -> WordData | None:
        return next((w for p in self.project.pages for w in p.iter_words() if w.id == word.id),
                    None)

    def _line_of(self, word: WordData) -> str:
        for page in self.project.pages:
            for area in page.areas:
                for block in area.blocks:
                    for line in block.lines:
                        if any(w.id == word.id for w in line.words):
                            return line.text
        return word.text

    def _run(self, operation: Any) -> bool:
        try:
            operation()
        except (CoreError, ValueError) as exc:
            self.status.setText(tr_error(exc))
            return False
        self.changed.emit()
        return True

    # --- butoanele (O-004…O-007) ----------------------------------------------------

    def skip(self) -> None:
        """O-004: evidentierea dispare, textul ramane."""
        word = self.word
        if word is not None and self._run(lambda: self.editor.skip(word)):
            self.advance()

    def replace(self) -> None:
        """O-005: sugestia aleasa sau textul scris."""
        word, text = self.word, self.edit.text().strip()
        if word is not None and text and self._run(
                lambda: self.editor.set_word_text(word, text)):
            self.advance()

    def add_to_dictionary(self) -> None:
        """O-006: in dictionarul limbii cuvantului; nu mai e semnalat nicaieri."""
        word = self.word
        if word is not None and self._run(lambda: self.editor.add_to_dictionary(word)):
            self.advance()

    def insert_symbol(self) -> None:
        """O-109: `More Symbols...` din dialog; simbolul intra la cursor."""
        dialog = SymbolDialog(self)
        if dialog.exec() and dialog.symbol:
            self.edit.insert(dialog.symbol)

    def _format(self, **attrs: Any) -> None:
        """O-007: fontul si efectele se aplica cuvantului curent."""
        word = self.word
        if word is not None and self._run(lambda: self.editor.apply_formatting([word], **attrs)):
            self.word = self._fresh(word) or word
