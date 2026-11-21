"""Pornirea OCR Editor-ului (faza 6b, pasul 6b.1).

`python -m app.gui.main`: deschide contextul aplicatiei (Y-022..Y-026), alege
limba interfetei si arata fereastra principala. La iesire, documentele deschise
se inchid inainte de curatarea fisierelor temporare (AppContext.close).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.gui import i18n
from app.gui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    context = AppContext.start()
    try:
        language = context.settings.get("ui.language")
        i18n.set_language(language if language in i18n.LANGUAGES else i18n.DEFAULT)
        app.setApplicationName(i18n.tr("app.name"))
        window = MainWindow(context)
        window.show()
        return int(app.exec())
    finally:
        context.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
