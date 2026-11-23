"""Pornirea aplicatiei (faza 6b, pasul 6b.1; faza 6c, pasul 6c.4).

`python -m app.gui.main`: deschide contextul aplicatiei (Y-022..Y-026), alege
limba interfetei si arata ecranul de pornire (A-001): Lansatorul sau OCR Editor. La iesire, documentele deschise
se inchid inainte de curatarea fisierelor temporare (AppContext.close).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.gui import i18n, theme
from app.gui.application import Application
from app.gui.error_dialog import install_excepthook


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv)
    args = argv[1:]
    app = QApplication.instance() or QApplication(argv)
    screenshot = "--screenshot-reader" in args  # V-001: utilitarul in proces propriu
    if not screenshot:
        from app.gui.instance import send_to_running

        if send_to_running(args):  # W-094: prima instanta primeste fisierele
            return 0
    context = AppContext.start()
    try:
        language = context.settings.get("ui.language")
        i18n.set_language(language if language in i18n.LANGUAGES else i18n.DEFAULT)
        app.setApplicationName(i18n.tr("app.name"))
        theme.apply(app)  # paleta si stilul din prototip
        if screenshot:
            from app.gui.screenshot_window import run

            return run(context)
        from app.gui.instance import InstanceServer

        application = Application(context)
        server = InstanceServer()
        server.listen()
        server.received.connect(application.handle_args)  # W-094
        window = application.start()  # A-001: ecranul de pornire
        install_excepthook(context, window)  # Y-025
        if args:
            application.handle_args(args)  # W-092: fisierele din linia de comanda
        code = int(app.exec())
        server.close()
        return code
    finally:
        context.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
