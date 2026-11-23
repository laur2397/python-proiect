"""Tema aplicatiei: paleta si foaia de stil, dupa `docs/prototip_ocr_editor.html`.

Paleta e a noastra (prototipul DocuLens), nu a originalului (CLAUDE.md §6.6).
Culorile zonelor raman setari (`areas.color.*`, X-165); aici e numai cromajul
ferestrelor. Elementele cu rol special se marcheaza cu proprietati Qt:
`primary` (butonul principal, ex. Recognize), `card` (cardurile Lansatorului),
`section` (titlurile de sectiune).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#eef0f3", "panel": "#ffffff", "ink": "#1b1f27", "ink2": "#5a6474",
    "ink3": "#8b95a6", "line": "#d6dae1", "line2": "#e6e9ee", "accent": "#2f6df6",
    "accent_soft": "#e6eeff", "accent_line": "#bcd0fb", "accent_dark": "#17408f",
    "warn": "#b4690e", "warn_soft": "#fdf3e2", "ok": "#1a7f52", "ok_soft": "#e7f6ee",
    "canvas": "#9ba3af", "notice": "#fff6c7", "notice_line": "#ead98c",
}

DARK_COLORS = {
    "bg": "#1d2026", "panel": "#262a32", "ink": "#e6e8ec", "ink2": "#b3bac6",
    "ink3": "#8b95a6", "line": "#3a404b", "line2": "#323844", "accent": "#5b8cff",
    "accent_soft": "#2b3a5c", "accent_line": "#3f5a96", "accent_dark": "#a9c1ff",
    "warn": "#f0a24a", "warn_soft": "#3d3020", "ok": "#4cc38a", "ok_soft": "#1f3a2e",
    "canvas": "#454b56", "notice": "#4a4420", "notice_line": "#6b6230",
}
"""B-044 (`N`, nu exista in original): modul intunecat, din `Options > Other` (setarea `ui.dark_theme`, X-149)."""

STYLE = """
QMainWindow, QDialog {{ background: {bg}; }}
QToolBar {{ background: {panel}; border: 0; border-bottom: 1px solid {line};
           padding: 4px 6px; spacing: 3px; }}
QToolBar::separator {{ background: {line}; width: 1px; margin: 4px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px;
              padding: 4px 7px; color: {ink}; }}
QToolButton:hover {{ background: #f1f4f9; border-color: {line2}; }}
QToolButton:checked {{ background: {accent_soft}; border-color: {accent_line};
                      color: {accent_dark}; }}
QToolButton:disabled {{ color: {ink3}; }}
QToolButton[primary="true"] {{ background: {accent}; color: white; font-weight: 600;
                              padding: 5px 12px; }}
QToolButton[primary="true"]:hover {{ background: #2057d8; }}
QToolButton[card="true"] {{ background: {panel}; border: 1px solid {line};
                           border-radius: 10px; padding: 12px; }}
QToolButton[card="true"]:hover {{ border: 2px solid {accent}; }}
QToolButton[card="true"]:disabled {{ color: {ink3}; }}
QPushButton {{ background: {panel}; border: 1px solid {line}; border-radius: 6px;
              padding: 5px 12px; color: {ink}; }}
QPushButton:hover {{ background: #f1f4f9; }}
QPushButton:default {{ background: {accent}; color: white; border-color: {accent}; }}
QPushButton:disabled {{ color: {ink3}; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {panel};
    border: 1px solid {line}; border-radius: 6px; padding: 3px 6px; min-height: 20px; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {accent}; }}
QComboBox {{ padding-right: 20px; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox::down-arrow {{ image: url({arrow}); width: 10px; height: 10px; }}
QDockWidget::title {{ background: {panel}; padding: 6px 8px; border-bottom: 1px solid {line2}; }}
QDockWidget > QWidget {{ background: {panel}; }}
QListWidget, QTextEdit, QPlainTextEdit {{ background: {panel}; border: 1px solid {line2};
    border-radius: 4px; }}
QListWidget::item:selected {{ background: {accent_soft}; color: {accent_dark}; }}
QTabWidget::pane {{ border: 0; border-top: 1px solid {line2}; background: {panel}; }}
QTabBar::tab {{ background: transparent; padding: 6px 12px; border: 0;
               border-bottom: 2px solid transparent; color: {ink2}; }}
QTabBar::tab:selected {{ color: {accent}; border-bottom-color: {accent}; font-weight: 600; }}
QStatusBar {{ background: {panel}; border-top: 1px solid {line}; color: {ink2}; }}
QLabel[section="true"] {{ font-size: 15px; font-weight: 600; color: {ink};
                         padding: 10px 0 4px; }}
QLabel[warning="true"] {{ background: {warn_soft}; color: {warn}; border: 1px solid #f0dcb6;
                         border-radius: 6px; padding: 2px 8px; }}
QFrame#pdf_form_band {{ background: {notice}; border-bottom: 1px solid {notice_line}; }}
QLabel[pill="true"] {{ background: {ok_soft}; color: {ok}; border-radius: 9px;
                      padding: 1px 9px; }}
QGroupBox {{ border: 1px solid {line2}; border-radius: 8px; margin-top: 12px;
            padding-top: 8px; background: {panel}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {ink2};
                   font-weight: 600; }}
QMenu {{ background: {panel}; border: 1px solid {line}; }}
QMenu::item:selected {{ background: {accent_soft}; color: {accent_dark}; }}
"""


ARROW = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M2 3.5l3 3 3-3" '
         'fill="none" stroke="#5a6474" stroke-width="1.5" stroke-linecap="round" '
         'stroke-linejoin="round"/></svg>')


def _arrow_file() -> str:
    """Sageata combo-urilor, ca fisier: foile de stil Qt cer o cale."""
    import tempfile
    from pathlib import Path

    path = Path(tempfile.gettempdir()) / "doculens-combo-arrow.svg"
    if not path.is_file() or path.read_text(encoding="utf-8") != ARROW:
        path.write_text(ARROW, encoding="utf-8")
    return path.as_posix()


def stylesheet(dark: bool = False) -> str:
    colors = DARK_COLORS if dark else COLORS
    style = STYLE.format(**colors, arrow=_arrow_file())
    if dark:  # culorile de hover scrise direct in foaia de stil
        style = style.replace("#f1f4f9", colors["line2"])
    return style


def apply(app: QApplication, dark: bool = False) -> None:
    """Paleta si foaia de stil pe toata aplicatia; `dark` = modul intunecat (B-044)."""
    c = DARK_COLORS if dark else COLORS
    palette = app.palette()
    roles = {QPalette.ColorRole.Window: c["bg"], QPalette.ColorRole.Base: c["panel"],
             QPalette.ColorRole.AlternateBase: c["accent_soft"],
             QPalette.ColorRole.Text: c["ink"], QPalette.ColorRole.WindowText: c["ink"],
             QPalette.ColorRole.Button: c["panel"],
             QPalette.ColorRole.ButtonText: c["ink"],
             QPalette.ColorRole.Highlight: c["accent"],
             QPalette.ColorRole.HighlightedText: "#ffffff",
             QPalette.ColorRole.Mid: c["line"]}
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(dark))
    app.setProperty("dark_mode", bool(dark))
