"""`View > Toolbars > Customize...` din OCR Editor, tabul `Keyboard Shortcuts`
(auditul 23.11.2026, defectul 7): X-204…X-207.

Se alege o categorie in `Categories`, o comanda in `Commands`, se apasa
combinatia in `Press new shortcut key`, apoi `Assign`; combinatia apare in
`Current shortcut`; `OK` salveaza (X-205). `Reset` aduce scurtaturile livrate ale
categoriei, `Reset All` pe toate (X-206). O combinatie folosita de alta comanda
nu se atribuie pana nu e eliberata (X-207). Regulile sunt in `ShortcutStore`.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.i18n import tr


class CustomizeDialog(QDialog):
    """X-204: `Customize`, cu tabul `Keyboard Shortcuts`."""

    def __init__(self, store: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.gui.pdf_content import dialog_buttons

        self.setObjectName("customize_dialog")
        self.setWindowTitle(tr("customize.title"))
        self.store = store
        self.rows = {r["command_id"]: dict(r) for r in store.all()}
        """Starea din dialog; se scrie in `store` numai la `OK`."""
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        page = QWidget()
        form = QVBoxLayout(page)
        lists = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("customize.categories")))
        self.categories = QListWidget()
        self.categories.setObjectName("customize_categories")
        for category in dict.fromkeys(r["category"] for r in self.rows.values()):
            item = QListWidgetItem(tr(f"menu.{category}").replace("&", ""))
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.categories.addItem(item)
        left.addWidget(self.categories)
        right = QVBoxLayout()
        right.addWidget(QLabel(tr("customize.commands")))
        self.commands = QListWidget()
        self.commands.setObjectName("customize_commands")
        right.addWidget(self.commands)
        lists.addLayout(left)
        lists.addLayout(right, 1)
        form.addLayout(lists)
        fields = QFormLayout()
        self.current = QLabel()
        self.current.setObjectName("customize_current")
        fields.addRow(tr("customize.current"), self.current)
        self.key = QKeySequenceEdit()
        self.key.setObjectName("customize_key")
        fields.addRow(tr("customize.press_new"), self.key)
        form.addLayout(fields)
        self.message = QLabel()
        self.message.setObjectName("customize_message")
        self.message.setProperty("warning", True)
        self.message.setWordWrap(True)
        self.message.hide()
        form.addWidget(self.message)
        buttons = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, slot in (("assign", self.assign), ("remove", self.remove),
                          ("reset", self.reset), ("reset_all", self.reset_all)):
            button = QPushButton(tr(f"customize.{key}"))
            button.setObjectName(f"customize_{key}")
            button.clicked.connect(slot)
            self.buttons[key] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        form.addLayout(buttons)
        self.tabs.addTab(page, tr("customize.tab.shortcuts"))
        layout.addWidget(self.tabs)
        layout.addWidget(dialog_buttons(self, "customize.ok"))
        self.categories.currentRowChanged.connect(self._show_commands)
        self.commands.currentRowChanged.connect(self._show_current)
        if self.categories.count():
            self.categories.setCurrentRow(0)

    # --- afisarea ---

    def _category(self) -> str | None:
        item = self.categories.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def command(self) -> str | None:
        item = self.commands.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _show_commands(self) -> None:
        category = self._category()
        self.commands.clear()
        for row in self.rows.values():
            if row["category"] == category:
                item = QListWidgetItem(tr(row["display_name"]).replace("&", ""))
                item.setData(Qt.ItemDataRole.UserRole, row["command_id"])
                self.commands.addItem(item)
        if self.commands.count():
            self.commands.setCurrentRow(0)
        self._show_current()

    def _show_current(self) -> None:
        command = self.command()
        shortcut = self.rows[command]["shortcut"] if command else None
        self.current.setText(shortcut or tr("customize.none"))
        self.message.hide()

    def select(self, command_id: str) -> None:
        category = self.rows[command_id]["category"]
        for i in range(self.categories.count()):
            if self.categories.item(i).data(Qt.ItemDataRole.UserRole) == category:
                self.categories.setCurrentRow(i)
        for i in range(self.commands.count()):
            if self.commands.item(i).data(Qt.ItemDataRole.UserRole) == command_id:
                self.commands.setCurrentRow(i)

    # --- comenzile (X-205…X-207) ---

    def assign(self) -> bool:
        """X-205: combinatia apasata trece la comanda aleasa; X-207: daca e a altei
        comenzi, se refuza cu mesaj."""
        command = self.command()
        shortcut = self.key.keySequence().toString()
        if not command or not shortcut:
            return False
        owner = next((r for r in self.rows.values()
                      if r["shortcut"] == shortcut and r["command_id"] != command), None)
        if owner is not None:
            self.message.setText(tr("customize.conflict", shortcut=shortcut,
                                    command=tr(owner["display_name"]).replace("&", "")))
            self.message.show()
            return False
        self.rows[command]["shortcut"] = shortcut
        self.key.clear()
        self._show_current()
        return True

    def remove(self) -> None:
        """Elibereaza combinatia comenzii alese (X-207)."""
        command = self.command()
        if command:
            self.rows[command]["shortcut"] = None
            self._show_current()

    def reset(self) -> None:
        """X-206: scurtaturile livrate ale categoriei alese."""
        self._reset(self._category())

    def reset_all(self) -> None:
        """X-206: toate scurtaturile livrate."""
        self._reset(None)

    def _reset(self, category: str | None) -> None:
        chosen = [r for r in self.rows.values() if category is None or r["category"] == category]
        for row in chosen:
            row["shortcut"] = None
        for row in chosen:
            default = row["default_shortcut"]
            if default and not any(r["shortcut"] == default for r in self.rows.values()):
                row["shortcut"] = default
        self._show_current()

    def save(self) -> None:
        """`OK`: scurtaturile schimbate se scriu (intai se elibereaza, ca o
        inversare intre doua comenzi sa nu dea conflict)."""
        saved = {r["command_id"]: r["shortcut"] for r in self.store.all()}
        changed = {c: r["shortcut"] for c, r in self.rows.items() if saved.get(c) != r["shortcut"]}
        for command in changed:
            self.store.assign(command, None)
        for command, shortcut in changed.items():
            self.store.assign(command, shortcut)

    def accept(self) -> None:  # API Qt
        self.save()
        super().accept()
