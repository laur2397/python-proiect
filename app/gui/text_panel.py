"""Panoul Text (faza 6b, pasul 6b.3a).

Textul recunoscut al paginii, editabil, cu: blocurile separate prin linii
punctate (O-104), caracterele nesigure pe fundalul din setari (O-105, X-166),
sincronizarea cu imaginea (O-021), caracterele neimprimabile (O-028, X-169),
fontul textului simplu (O-029, X-164), toolbarul pe doua randuri (O-100,
O-101), uneltele de tabel ascunse implicit (O-064), bara de jos cu zoom
propriu (J-417), mesajul pentru pagina nerecunoscuta (O-103).

Fiecare caracter al unui cuvant poarta id-ul cuvantului in formatul lui
(`WORD_ID`). Dupa editare, textul se aduna inapoi pe cuvinte si fiecare
cuvant schimbat trece prin `TextEditor.set_word_text` (O-020): nucleul
pastreaza textul original si istoricul de undo.

INCOMPLET, marcat (vin in 6b.3b): dialogul `Verify Text`, simbolurile
(`Ω`, `More Symbols...`), legaturile, bara `Text Properties` (O-106), combo-ul
de stil la selectie mixta (O-102). `Style Editor` si spatierea nu au inca
operatii in nucleu.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextFrameFormat,
    QTextOption,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFontComboBox,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.model import (
    AreaData,
    BlockData,
    PageData,
    PageStatus,
    TableCellData,
    WordData,
)
from app.core.text.editor import REDACTION_DOT, TextEditor
from app.gui.i18n import tr, tr_error

WORD_ID = QTextFormat.Property.UserProperty + 1
"""Proprietatea din formatul caracterelor care leaga textul de cuvantul lui."""

ZOOM_STEPS = (50, 75, 100, 125, 150, 200, 300)
"""J-417: zoom-ul propriu al panoului Text."""

FONT_SIZES = (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)

_ALIGN = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
          "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}

_TOGGLES = {"bold": "is_bold", "italic": "is_italic", "underline": "is_underline",
            "superscript": "is_superscript", "subscript": "is_subscript"}
"""O-101: butoanele care comuta un atribut al cuvintelor (O-022)."""


def collect_words(chars: list[tuple[str, int | None]]) -> dict[int, str]:
    """Textul fiecarui cuvant, din caracterele documentului (caracter, id).

    Textul scris intre cuvinte (fara id) se lipeste de cuvantul vecin: de cel
    care urmeaza imediat, fara spatiu intre ele, altfel de cel dinainte."""
    owners = [wid for _, wid in chars]
    n = len(chars)
    i = 0
    while i < n:
        if owners[i] is not None or chars[i][0].isspace():
            i += 1
            continue
        j = i
        while j < n and owners[j] is None and not chars[j][0].isspace():
            j += 1
        target = owners[j] if j < n else None
        if target is None and i > 0:
            target = owners[i - 1]
        if target is None:
            target = next((o for o in reversed(owners[:i]) if o is not None), None)
        if target is None:
            target = next((o for o in owners[j:] if o is not None), None)
        for k in range(i, j):
            owners[k] = target
        i = j
    texts: dict[int, str] = {wid: "" for _, wid in chars if wid is not None}
    for (ch, _), owner in zip(chars, owners, strict=True):
        if owner is not None:
            texts[owner] += ch
    return texts


class TextPanel(QWidget):
    word_selected = Signal(object)
    """WordData sub cursor (O-021: se evidentiaza in imagine si in Zoom)."""
    changed = Signal()
    message = Signal(str)

    def __init__(self, project: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("text_panel")
        self.project = project
        self.page: PageData | None = None
        self.words: dict[int, WordData] = {}
        self.blocks: dict[int, BlockData] = {}
        """id cuvant → blocul lui."""
        self.cells: dict[int, tuple[AreaData, TableCellData]] = {}
        """id cuvant → (zona tabel, celula), pentru uneltele de tabel."""
        self.actions: dict[str, QAction] = {}
        self._rendering = False
        self._zoom = 100
        self.view = QTextEdit()
        self.view.setObjectName("text_view")
        self.view.setAcceptRichText(False)
        self.view.setPlaceholderText(tr("panel.text.empty"))  # O-103
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(700)
        self._commit_timer.timeout.connect(self.commit)
        self.view.document().contentsChanged.connect(self._edited)
        self.view.cursorPositionChanged.connect(self._cursor_moved)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._row1())
        layout.addWidget(self._row2())
        layout.addWidget(self._table_bar())
        layout.addWidget(self._find_bar())
        layout.addWidget(self.view, 1)
        layout.addWidget(self._bottom_bar())

    @property
    def editor(self) -> TextEditor:
        return TextEditor(self.project)

    # --- toolbarul (O-100, O-101) -----------------------------------------------------

    def _action(self, bar: QToolBar, key: str, slot: Callable[[], Any] | None = None, *,
                checkable: bool = False) -> QAction:
        action = bar.addAction(tr(f"text.{key}"))
        action.setObjectName(f"text_{key}")
        action.setCheckable(checkable)
        if slot is not None:
            action.triggered.connect(lambda _=False: slot())
        self.actions[key] = action
        return action

    def _row1(self) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName("text_toolbar_1")
        self.style_combo = QComboBox()
        self.style_combo.setObjectName("text_style")
        self.style_combo.activated.connect(self._style_chosen)
        bar.addWidget(self.style_combo)
        self.font_combo = QFontComboBox()
        self.font_combo.setObjectName("text_font")
        self.font_combo.activated.connect(
            lambda _: self.format_words(font_name=self.font_combo.currentFont().family()))
        bar.addWidget(self.font_combo)
        self.size_combo = QComboBox()
        self.size_combo.setObjectName("text_size")
        self.size_combo.setEditable(True)
        for size in FONT_SIZES:
            self.size_combo.addItem(str(size), size)
        self.size_combo.activated.connect(self._size_chosen)
        bar.addWidget(self.size_combo)
        self._action(bar, "grow", lambda: self._step_size(1))
        self._action(bar, "shrink", lambda: self._step_size(-1))
        self._action(bar, "symbol").setEnabled(False)  # INCOMPLET: 6b.3b
        self._action(bar, "link").setEnabled(False)  # INCOMPLET: 6b.3b
        self._action(bar, "find", self.show_find)
        return bar

    def _row2(self) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName("text_toolbar_2")
        self._action(bar, "style_editor").setEnabled(False)  # INCOMPLET: fara nucleu
        bar.addSeparator()
        for key in _TOGGLES:
            self._action(bar, key, lambda k=key: self.toggle(k), checkable=True)
        bar.addSeparator()
        for key in _ALIGN:
            self._action(bar, f"align_{key}", lambda k=key: self.paragraph(alignment=k),
                         checkable=True)
        self._action(bar, "spacing").setEnabled(False)  # INCOMPLET: fara nucleu
        self._action(bar, "list", self._toggle_list, checkable=True)
        self._action(bar, "redaction", self.redact)
        return bar

    # O-064: uneltele de tabel, ascunse implicit
    def _table_bar(self) -> QToolBar:
        self.table_bar = QToolBar()
        self.table_bar.setObjectName("text_table_toolbar")
        self._action(self.table_bar, "merge_cells", self.merge_cells)
        self._action(self.table_bar, "split_cells", self.split_cells)
        self._action(self.table_bar, "merge_rows", self.merge_rows)
        self._action(self.table_bar, "clear_cell", self.clear_cells)
        self.table_bar.setVisible(False)
        return self.table_bar

    def _find_bar(self) -> QWidget:
        self.find_bar = QWidget()
        self.find_bar.setObjectName("text_find_bar")
        row = QHBoxLayout(self.find_bar)
        row.setContentsMargins(4, 2, 4, 2)
        self.find_edit = QLineEdit()
        self.find_edit.setObjectName("find_text")
        self.find_edit.setPlaceholderText(tr("text.find"))
        self.find_edit.returnPressed.connect(self.find_next)
        row.addWidget(self.find_edit, 1)
        self.match_case = QCheckBox(tr("text.match_case"))
        self.whole_word = QCheckBox(tr("text.whole_word"))
        row.addWidget(self.match_case)
        row.addWidget(self.whole_word)
        self.replace_edit = QLineEdit()
        self.replace_edit.setObjectName("replace_text")
        self.replace_edit.setPlaceholderText(tr("text.replace_with"))
        row.addWidget(self.replace_edit, 1)
        bar = QToolBar()
        self._action(bar, "find_next", self.find_next)
        self._action(bar, "replace_all", self.replace_all)
        row.addWidget(bar)
        self.find_bar.setVisible(False)
        return self.find_bar

    # J-417
    def _bottom_bar(self) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName("text_bottom_bar")
        self._action(bar, "nonprinting", self._toggle_nonprinting, checkable=True)
        bar.addSeparator()
        self.zoom_combo = QComboBox()
        self.zoom_combo.setObjectName("text_zoom")
        for step in ZOOM_STEPS:
            self.zoom_combo.addItem(f"{step}%", step)
        self.zoom_combo.setCurrentIndex(ZOOM_STEPS.index(100))
        self.zoom_combo.currentIndexChanged.connect(
            lambda i: self.set_zoom(self.zoom_combo.itemData(i)))
        bar.addWidget(self.zoom_combo)
        return bar

    # --- afisarea ---------------------------------------------------------------------

    def set_page(self, page: PageData | None) -> None:
        if self._commit_timer.isActive():
            self.commit()
        self.page = page
        self.render()

    def render(self) -> None:
        """Pagina in document: zonele in ordine, blocurile in cadre punctate."""
        self._rendering = True
        position = self.view.textCursor().position()
        doc = self.view.document()
        doc.clear()
        self.words, self.blocks, self.cells = {}, {}, {}
        self._apply_view_settings()
        page = self.page
        recognized = page is not None and page.status in (PageStatus.RECOGNIZED,
                                                          PageStatus.VERIFIED)
        self.view.setReadOnly(not recognized)
        if recognized:
            settings = self.project.settings()
            self._uncertain = QColor(settings.get("areas.uncertain_color"))
            self._threshold = float(settings.get("ocr.confidence_threshold"))
            cursor = QTextCursor(doc)
            for area in sorted(page.areas, key=lambda a: a.order_index):
                if area.table is not None:
                    self._render_table(cursor, area)
                for block in area.blocks:
                    self._render_block(cursor, block)
        self._refresh_styles()
        cursor = self.view.textCursor()
        cursor.setPosition(min(position, max(0, doc.characterCount() - 1)))
        self.view.setTextCursor(cursor)
        self._rendering = False

    @staticmethod
    def _frame() -> QTextFrameFormat:
        """O-104: fiecare bloc intr-un cadru cu chenar punctat."""
        fmt = QTextFrameFormat()
        fmt.setBorder(1)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Dotted)
        fmt.setBorderBrush(QColor(Qt.GlobalColor.gray))
        fmt.setPadding(2)
        fmt.setMargin(2)
        return fmt

    def _render_block(self, cursor: QTextCursor, block: BlockData) -> None:
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertFrame(self._frame())
        self._write_block(cursor, block)
        cursor.movePosition(QTextCursor.MoveOperation.End)

    def _write_block(self, cursor: QTextCursor, block: BlockData,
                     cell: tuple[AreaData, TableCellData] | None = None) -> None:
        fmt = QTextBlockFormat()
        if block.alignment in _ALIGN:
            fmt.setAlignment(_ALIGN[block.alignment])
        if block.direction == "rtl":
            fmt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        if block.list_level:
            fmt.setIndent(block.list_level)
        cursor.setBlockFormat(fmt)
        for n, line in enumerate(block.lines):
            if n:
                cursor.insertText("\n", QTextCharFormat())
            for i, word in enumerate(line.words):
                if i:
                    cursor.insertText(" ", QTextCharFormat())
                self._write_word(cursor, word)
                self.words[word.id] = word
                self.blocks[word.id] = block
                if cell is not None:
                    self.cells[word.id] = cell

    @staticmethod
    def _word_format(word: WordData) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setProperty(WORD_ID, word.id)
        if word.font_name:
            fmt.setFontFamilies([word.font_name])
        if word.font_size:
            fmt.setFontPointSize(word.font_size)
        fmt.setFontWeight(QFont.Weight.Bold if word.is_bold else QFont.Weight.Normal)
        fmt.setFontItalic(bool(word.is_italic))
        fmt.setFontUnderline(bool(word.is_underline))
        if word.is_superscript:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
        elif word.is_subscript:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
        if word.text_color:
            fmt.setForeground(QColor(word.text_color))
        return fmt

    def _write_word(self, cursor: QTextCursor, word: WordData) -> None:
        fmt = self._word_format(word)
        if word.is_redacted:
            fmt.setBackground(QColor(Qt.GlobalColor.black))
            cursor.insertText(REDACTION_DOT * len(word.text), fmt)
            return
        if not word.is_uncertain or word.is_verified:
            cursor.insertText(word.text, fmt)
            return
        chars = word.char_confidences
        if len(chars) != len(word.text):  # fara incredere pe caractere: tot cuvantul
            chars = (0.0,) * len(word.text)
        marked = QTextCharFormat(fmt)
        marked.setBackground(self._uncertain)  # O-105
        for ch, confidence in zip(word.text, chars, strict=True):
            cursor.insertText(ch, marked if confidence < self._threshold else fmt)

    def _render_table(self, cursor: QTextCursor, area: AreaData) -> None:
        table = area.table
        cursor.movePosition(QTextCursor.MoveOperation.End)
        qt_table = cursor.insertTable(table.rows, table.cols)
        for cell in table.cells:
            if cell.row_span > 1 or cell.col_span > 1:
                qt_table.mergeCells(cell.row, cell.col, cell.row_span, cell.col_span)
        for cell in table.cells:
            cell_cursor = qt_table.cellAt(cell.row, cell.col).firstCursorPosition()
            for n, block in enumerate(cell.blocks):
                if n:
                    cell_cursor.insertBlock()
                self._write_block(cell_cursor, block, (area, cell))
        cursor.movePosition(QTextCursor.MoveOperation.End)

    def _apply_view_settings(self) -> None:
        settings = self.project.settings()
        doc = self.view.document()
        font = QFont(doc.defaultFont())
        family = settings.get("areas.plain_text_font")  # O-029
        if family:
            font.setFamily(family)
        font.setPointSizeF(QFont().pointSizeF() * self._zoom / 100)
        doc.setDefaultFont(font)
        option = doc.defaultTextOption()
        shown = bool(settings.get("areas.show_nonprinting"))  # O-028
        flags = (QTextOption.Flag.ShowTabsAndSpaces
                 | QTextOption.Flag.ShowLineAndParagraphSeparators) if shown \
            else QTextOption.Flag(0)
        option.setFlags(flags)
        doc.setDefaultTextOption(option)
        self.actions["nonprinting"].setChecked(shown)

    def _refresh_styles(self) -> None:
        from app.core.text.styles import StyleManager

        self.style_combo.clear()
        for style in StyleManager(self.project._ctx.app_db).all():
            self.style_combo.addItem(style.name, style.name)

    # --- zoom si neimprimabile (J-417, O-028) ---------------------------------------

    @property
    def zoom(self) -> int:
        return self._zoom

    def set_zoom(self, percent: int) -> None:
        self._zoom = int(percent)
        self._apply_view_settings()

    def _toggle_nonprinting(self) -> None:
        self.project.settings().set("areas.show_nonprinting",
                                    self.actions["nonprinting"].isChecked())
        self._apply_view_settings()

    # --- cuvintele de sub cursor ---------------------------------------------------

    def _id_before(self, position: int) -> int | None:
        """Id-ul cuvantului caracterului dinaintea pozitiei."""
        doc = self.view.document()
        if position <= 0 or position >= doc.characterCount():
            return None
        probe = QTextCursor(doc)
        probe.setPosition(position)
        wid = probe.charFormat().property(WORD_ID)
        return int(wid) if wid is not None and int(wid) in self.words else None

    def word_at(self, position: int) -> WordData | None:
        wid = self._id_before(position)
        if wid is None:
            wid = self._id_before(position + 1)
        return self.words.get(wid) if wid is not None else None

    def current_word(self) -> WordData | None:
        return self.word_at(self.view.textCursor().position())

    def selected_words(self) -> list[WordData]:
        cursor = self.view.textCursor()
        if not cursor.hasSelection():
            word = self.current_word()
            return [word] if word else []
        ids: list[int] = []
        for pos in range(cursor.selectionStart() + 1, cursor.selectionEnd() + 1):
            wid = self._id_before(pos)
            if wid is not None and wid not in ids:
                ids.append(wid)
        return [self.words[i] for i in ids]

    def word_span(self, word_id: int) -> tuple[int, int] | None:
        """Pozitiile (inceput, sfarsit) ale cuvantului in document, din fragmente."""
        start = end = None
        block = self.view.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.charFormat().property(WORD_ID) == word_id:
                    if start is None:
                        start = fragment.position()
                    end = fragment.position() + fragment.length()
                elif start is not None:
                    return start, end
                it += 1
            block = block.next()
        return (start, end) if start is not None else None

    def select_word(self, word: WordData) -> bool:
        """O-021: clic in imagine → cuvantul se selecteaza in text."""
        span = self.word_span(word.id)
        if span is None:
            return False
        cursor = QTextCursor(self.view.document())
        cursor.setPosition(span[0])
        cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        self.view.setTextCursor(cursor)
        return True

    def _cursor_moved(self) -> None:
        if self._rendering:
            return
        word = self.current_word()
        self._show_format(word)
        if word is not None:
            self.word_selected.emit(word)

    def _show_format(self, word: WordData | None) -> None:
        for key, attr in _TOGGLES.items():
            self.actions[key].setChecked(bool(word is not None and getattr(word, attr)))
        block = self.blocks.get(word.id) if word is not None else None
        for key in _ALIGN:
            self.actions[f"align_{key}"].setChecked(block is not None
                                                    and block.alignment == key)
        self.actions["list"].setChecked(bool(block is not None and block.list_level))
        if block is not None and block.style_name:
            self.style_combo.setCurrentIndex(self.style_combo.findData(block.style_name))
        if word is not None and word.font_size:
            self.size_combo.setEditText(f"{word.font_size:g}")
        self.table_bar.setEnabled(word is not None and word.id in self.cells)

    # --- editarea (O-020) ----------------------------------------------------------

    def _edited(self) -> None:
        if not self._rendering:
            self._commit_timer.start()

    def document_chars(self) -> list[tuple[str, int | None]]:
        chars: list[tuple[str, int | None]] = []
        block = self.view.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                wid = fragment.charFormat().property(WORD_ID)
                chars.extend((ch, None if wid is None else int(wid)) for ch in fragment.text())
                it += 1
            chars.append(("\n", None))
            block = block.next()
        return chars

    def commit(self) -> int:
        """Cuvintele schimbate in panou ajung in proiect; intoarce cate."""
        self._commit_timer.stop()
        if self._rendering or self.page is None or self.view.isReadOnly():
            return 0
        texts = collect_words(self.document_chars())
        changed = 0
        try:
            for wid, word in self.words.items():
                new = texts.get(wid, "").strip()
                if word.is_redacted or new == word.text:
                    continue
                self.editor.set_word_text(word, new)
                changed += 1
        except CoreError as exc:
            self.message.emit(tr_error(exc))
        if changed:
            self.page = self.project.page(self.page.page_number)
            self.render()
            self.changed.emit()
        return changed

    # --- formatarea si paragrafele (O-022, O-101) -------------------------------------

    def _run(self, operation: Callable[[], Any]) -> None:
        self.commit()
        try:
            operation()
        except (CoreError, ValueError) as exc:
            self.message.emit(tr_error(exc))
            return
        if self.page is not None:
            self.page = self.project.page(self.page.page_number)
        self.render()
        self.changed.emit()

    def format_words(self, **attrs: Any) -> None:
        words = self.selected_words()
        if words:
            self._run(lambda: self.editor.apply_formatting(words, **attrs))

    def toggle(self, key: str) -> None:
        words = self.selected_words()
        if not words:
            return
        attr = _TOGGLES[key]
        value = not all(getattr(w, attr) for w in words)
        attrs = {attr: value}
        if value and key == "superscript":
            attrs["is_subscript"] = False
        if value and key == "subscript":
            attrs["is_superscript"] = False
        self.format_words(**attrs)

    def _size_chosen(self, index: int) -> None:
        self.format_words(font_size=float(self.size_combo.itemData(index)))

    def _step_size(self, step: int) -> None:
        words = self.selected_words()
        if words:
            current = words[0].font_size or QFont().pointSizeF()
            self.format_words(font_size=max(1.0, float(current) + step))

    def _selected_blocks(self) -> list[BlockData]:
        seen: dict[int, BlockData] = {}
        for word in self.selected_words():
            block = self.blocks.get(word.id)
            if block is not None and block.id is not None:
                seen.setdefault(block.id, block)
        return list(seen.values())

    def paragraph(self, **fmt: Any) -> None:
        blocks = self._selected_blocks()
        if blocks:
            self._run(lambda: self.editor.set_paragraph_format(blocks, **fmt))

    def _toggle_list(self) -> None:
        blocks = self._selected_blocks()
        if blocks:
            self.paragraph(list_level=None if all(b.list_level for b in blocks) else 1)

    def _style_chosen(self, index: int) -> None:
        blocks = self._selected_blocks()
        name = self.style_combo.itemData(index)
        if blocks and name:
            self._run(lambda: self.editor.apply_style(blocks, name))

    def redact(self) -> None:
        words = self.selected_words()
        if words:
            self._run(lambda: self.editor.redact_words(words))

    # --- cautarea (O-024, O-025) ------------------------------------------------------

    def show_find(self) -> None:
        self.find_bar.setVisible(True)
        self.find_edit.setFocus()

    def _found(self) -> list[WordData]:
        query = self.find_edit.text()
        if not query or self.page is None:
            return []
        self.commit()
        return self.editor.find([self.project.page(self.page.page_number)], query,
                                match_case=self.match_case.isChecked(),
                                whole_word=self.whole_word.isChecked())

    def find_next(self) -> WordData | None:
        found = self._found()
        if not found:
            self.message.emit(tr("text.not_found"))
            return None
        current = self.current_word()
        ids = [w.id for w in found]
        index = (ids.index(current.id) + 1) % len(found) if current and current.id in ids else 0
        self.select_word(found[index])
        return found[index]

    def replace_all(self) -> int:
        found = self._found()
        if found:
            self._run(lambda: self.editor.replace(found, self.replace_edit.text()))
        self.message.emit(tr("text.replaced", n=len(found)))
        return len(found)

    # --- tabelele (O-060…O-063) -------------------------------------------------------

    def _selected_cells(self) -> tuple[AreaData | None, list[TableCellData]]:
        area: AreaData | None = None
        cells: dict[int, TableCellData] = {}
        for word in self.selected_words():
            if word.id in self.cells:
                area, cell = self.cells[word.id]
                cells.setdefault(cell.id, cell)
        return area, list(cells.values())

    def merge_cells(self) -> None:
        area, cells = self._selected_cells()
        if area is not None and len(cells) > 1:
            self._run(lambda: self.editor.merge_cells(self.page, area, cells))

    def split_cells(self) -> None:
        area, cells = self._selected_cells()
        if area is not None and cells:
            self._run(lambda: self.editor.split_cells(self.page, area, cells[0]))

    def merge_rows(self) -> None:
        area, cells = self._selected_cells()
        rows = sorted({c.row for c in cells})
        if area is not None and len(rows) > 1:
            self._run(lambda: self.editor.merge_rows(self.page, area, rows))

    def clear_cells(self) -> None:
        _, cells = self._selected_cells()
        for cell in cells:
            self._run(lambda c=cell: self.editor.clear_cell(c))
