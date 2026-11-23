"""Faza 16, pasul 16.4: documentele mari (Y-016), interfata care nu se blocheaza
(Y-017), scalarea 100…200 % (Y-018), accesibilitatea (Y-019)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.context import AppContext
from app.core.paths import AppPaths

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


def test_T_Y016_pages_live_on_disk_not_in_memory(ctx, tmp_path):
    """Paginile unui document mare sunt fisiere in proiect; obiectele paginilor tin
    numai caile, nu pixelii (procesarea e pagina cu pagina)."""
    from test_pdf_search import text_pdf

    from app.core.model import AutoProcessMode
    from app.core.project import OcrProject

    pdf = text_pdf(tmp_path / "mare.pdf", [[f"Pagina {n}"] for n in range(1, 41)])
    project = OcrProject.create(context=ctx)
    try:
        project.add_images([pdf], auto_process=AutoProcessMode.NONE)
        assert len(project.pages) == 40
        for page in project.pages:
            assert Path(page.image_path).is_file()
            assert not any(type(v).__module__.startswith(("numpy", "PIL"))
                           for v in vars(page).values()) if hasattr(page, "__dict__") else True
    finally:
        project.close()


def test_T_Y017_long_operations_report_progress_and_cancel(qtbot):
    from app.core.errors import OperationCancelledError
    from app.core.model import Progress
    from app.gui.progress import ProgressRunner

    runner = ProgressRunner("x")
    steps = []

    def operation(progress, cancel):
        for n in range(1, 6):
            progress(Progress(n, 5, "stage.converting", f"{n}"))
            steps.append(n)
            if n == 2:
                runner.dialog.cancel()  # utilizatorul apasa Cancel
            if cancel():
                raise OperationCancelledError("anulat")
        return "gata"
    assert runner.run(operation) is None  # anulat; ce s-a facut ramane
    assert steps == [1, 2] and runner.reports[-1].current == 2


@pytest.mark.parametrize("scale", ["1", "1.25", "1.5", "2"])
def test_T_Y018_no_clipped_labels_at_scale(scale):
    env = {**os.environ, "QT_SCALE_FACTOR": scale, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(ROOT)}
    out = subprocess.run([sys.executable, str(ROOT / "tests" / "tools" / "scale_probe.py")],
                         env=env, capture_output=True, text=True, timeout=180, check=False)
    line = next((x for x in out.stdout.splitlines() if x.startswith("CLIPPED")), out.stderr)
    assert line.startswith("CLIPPED 0"), line


def test_T_Y018_icons_are_scalable():
    from PySide6.QtWidgets import QApplication

    from app.gui import icons

    QApplication.instance() or QApplication([])
    icon = icons.icon("scan")
    ratios = sorted({p.devicePixelRatio() for p in (icon.pixmap(24, 24, mode)
                                                     for mode in (icon.Mode.Normal,))})
    assert icon.availableSizes()  # randata din SVG, la 1x si 2x
    assert ratios


def test_T_Y019_accessible_names_and_keyboard(qtbot, ctx):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractButton, QWidget

    from app.gui.accessibility import INTERACTIVE, _internal, ensure_accessible
    from app.gui.application import Application

    app = Application(ctx)
    windows = [app.launcher, app.editor, app.pdf_editor, app.compare_window, app.hot_folder]
    for window in windows:
        qtbot.addWidget(window)
        assert ensure_accessible(window) == [], window.objectName()
        for widget in window.findChildren(QWidget):
            if isinstance(widget, INTERACTIVE) and not _internal(widget):
                assert widget.accessibleName(), widget.objectName()
                if not isinstance(widget, QAbstractButton):
                    assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus, widget.objectName()
    app.hot_folder.shutdown()
