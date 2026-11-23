"""Accesibilitatea (faza 16, Y-019): fiecare control interactiv are un nume
accesibil (cititoarele de ecran) si se poate atinge cu tastatura.

Numele vine, in ordine, din: numele pus explicit, textul controlului, tooltip,
textul de ajutor din camp, eticheta din formular (`QFormLayout.labelForField`) si,
pentru controalele fara eticheta vizibila, cheia de traducere `a11y.<objectName>`
(CLAUDE.md §6.5). Controalele interne ale Qt (`qt_*`, listele combo-urilor,
antetele tabelelor) au nume puse de Qt si se sar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTabBar,
    QWidget,
)

from app.gui.i18n import catalog, language, tr

INTERACTIVE = (QAbstractButton, QComboBox, QLineEdit, QAbstractItemView, QAbstractSpinBox)


def _internal(widget: QWidget) -> bool:
    if widget.objectName().startswith("qt_") or isinstance(widget, QHeaderView):
        return True
    parent = widget.parentWidget()
    while parent is not None:  # lista unui combo, butoanele de derulare ale taburilor
        if isinstance(parent, (QComboBox, QTabBar, QLineEdit)):  # si butonul „sterge”
            return True
        parent = parent.parentWidget()
    return False


def _form_label(widget: QWidget) -> str:
    parent = widget.parentWidget()
    while parent is not None:
        layout = parent.layout()
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(widget)
            if isinstance(label, QLabel) and label.text().strip():
                return label.text().replace("&", "").rstrip(":")
        parent = parent.parentWidget() if parent is not widget.window() else None
    return ""


def accessible_label(widget: QWidget) -> str:
    if widget.accessibleName():
        return widget.accessibleName()
    text = widget.text() if isinstance(widget, (QAbstractButton, QLineEdit)) and \
        not isinstance(widget, QLineEdit) else ""
    if not text and isinstance(widget, QAbstractButton):
        action = getattr(widget, "defaultAction", lambda: None)()
        text = action.text() if action is not None else ""
    text = text or widget.toolTip()
    if not text and isinstance(widget, QLineEdit):
        text = widget.placeholderText()
    text = text or _form_label(widget)
    key = f"a11y.{widget.objectName()}"
    if not text and widget.objectName() and (key in catalog(language()) or key in catalog("en")):
        text = tr(key)
    return text.replace("&", "").strip()


def ensure_accessible(root: QWidget) -> list[str]:
    """Pune numele accesibile; intoarce controalele care au ramas fara nume."""
    missing: list[str] = []
    for widget in root.findChildren(QWidget):
        if not isinstance(widget, INTERACTIVE) or _internal(widget):
            continue
        name = accessible_label(widget)
        if name:
            widget.setAccessibleName(name)
        else:
            missing.append(f"{type(widget).__name__}:{widget.objectName()}")
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus and \
                not isinstance(widget, QAbstractButton):
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # tastatura (Y-019)
    return missing
