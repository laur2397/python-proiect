"""Y-018: ruleaza ferestrele la `QT_SCALE_FACTOR` dat si cauta etichetele si
butoanele taiate (il porneste tests/test_y_robustness.py, intr-un proces separat)."""

import pathlib
import tempfile

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.core.context import AppContext
from app.core.paths import AppPaths


def main() -> None:
    app = QApplication([])
    from app.gui.application import Application

    with tempfile.TemporaryDirectory() as tmp:
        ctx = AppContext.start(AppPaths.portable(pathlib.Path(tmp)))
        application = Application(ctx)
        bad = []
        windows = (("launcher", application.launcher), ("editor", application.editor),
                   ("pdf", application.pdf_editor))
        for name, window in windows:
            window.resize(1366, 768)
            window.show()
            app.processEvents()
            for widget in [*window.findChildren(QLabel), *window.findChildren(QPushButton)]:
                text = widget.text()
                if not widget.isVisible() or not text.strip() or "<" in text:
                    continue
                if isinstance(widget, QLabel) and widget.wordWrap():
                    continue
                need = widget.fontMetrics().horizontalAdvance(text.split("\n")[0].replace("&", ""))
                if widget.width() + 2 < need:
                    bad.append(f"{name}:{widget.objectName()}:{text[:30]!r}")
            window.close()
        print("CLIPPED", len(bad), bad[:6])
        ctx.close()


if __name__ == "__main__":
    main()
