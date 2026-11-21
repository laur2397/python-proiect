"""Pornirea aplicatiei (faza 6b, pasul 6b.1; faza 6c, pasul 6c.4).

`python -m app.gui.main`: deschide contextul aplicatiei (Y-022..Y-026), alege
limba interfetei si arata ecranul de pornire (A-001): Lansatorul sau OCR Editor. La iesire, documentele deschise
se inchid inainte de curatarea fisierelor temporare (AppContext.close).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.gui import i18n
from app.gui.application import Application
from app.gui.error_dialog import install_excepthook


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    context = AppContext.start()
    try:
        language = context.settings.get("ui.language")
        i18n.set_language(language if language in i18n.LANGUAGES else i18n.DEFAULT)
        app.setApplicationName(i18n.tr("app.name"))
        application = Application(context)
        window = application.start()  # A-001: ecranul de pornire
        install_excepthook(context, window)  # Y-025
        return int(app.exec())
    finally:
        context.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
