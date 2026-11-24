"""Ultimele cerinte fara test din Lansator (A-042, A-052, A-109, A-200, A-306),
scanare (K-008), preprocesare (L-031, L-034, L-101, L-104), OCR Editor
(O-009, O-082, O-107), limbi (P-024), salvare (Q-010, Q-048) si Screenshot
Reader (V-008, V-023)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image
from test_gui_dialogs import ScriptEngine, ctx, project, window  # noqa: F401
from test_scanner import FakeScanner

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QRect
from PySide6.QtGui import QTextCursor

from app.core.images.loader import LoadedImage
from app.core.images.scanner import ScanSettings, crop_to_area
from app.core.model import BlockData, ColorMode, LineData, PreprocessOp, Rect, WordData
from app.core.ocr.engine import RecognitionResult
from app.core.ocr.languages import CASE_PATTERNS, case_allowed, case_pattern
from app.core.ocr.service import _apply_case_rules
from app.gui.i18n import tr

ROOT = Path(__file__).resolve().parents[1]


# --- Lansatorul ------------------------------------------------------------------------


def _files(tmp_path):
    out = []
    for name in ("a", "b"):
        Image.new("L", (200, 200), 255).save(tmp_path / f"{name}.png", dpi=(300, 300))
        out.append(tmp_path / f"{name}.png")
    return out


def test_T_A042_A052_A306_convert_screen(qtbot, ctx, tmp_path):  # noqa: F811
    from app.gui.convert_screen import ConvertScreen

    pdf = ConvertScreen(ctx, "pdf", _files(tmp_path))
    qtbot.addWidget(pdf)
    assert pdf.convert_button.text() == tr("convert.start", format=tr("launcher.card.pdf"))
    word = ConvertScreen(ctx, "docx", _files(tmp_path))
    qtbot.addWidget(word)
    assert word.fields["pictures"].isChecked()  # A-052: `Keep pictures`, bifat
    word.files.clearSelection()
    word._update()
    assert not any(word.file_actions[k].isEnabled() for k in ("remove", "up", "down"))
    word.files.item(0).setSelected(True)
    word._update()
    assert all(word.file_actions[k].isEnabled() for k in ("remove", "up", "down"))


def test_T_A109_mobile_items(qtbot, ctx, tmp_path):  # noqa: F811
    from app.gui.launcher import Launcher

    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    pdfs, conversions = [], []
    launcher.pdf_requested.connect(pdfs.append)
    launcher.convert_requested.connect(lambda key, files: conversions.append((key, files)))
    folder = tmp_path / "poze"
    folder.mkdir()
    Image.new("RGB", (50, 50)).save(folder / "1.jpg")
    launcher.open_mobile(folder)  # folder de imagini -> PDF din JPG-uri
    launcher.open_mobile(tmp_path / "doc.pdf")  # PDF -> editor
    assert conversions[0][0] == "pdf" and conversions[0][1] == [folder / "1.jpg"]
    assert pdfs == [tmp_path / "doc.pdf"]


def test_T_A200_launcher_menus(qtbot, ctx):  # noqa: F811
    from app.gui.launcher import LAUNCHER_MENUS, Launcher

    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    titles = [a.text().replace("&", "") for a in launcher.menuBar().actions()]
    assert titles == [tr(f"launcher.menu.{k}").replace("&", "") for k in
                      ("file", "edit", "tools", "help")]
    assert list(LAUNCHER_MENUS) == ["file", "edit", "tools", "help"]
    asked = []
    launcher.automated_tasks_requested.connect(lambda: asked.append("tasks"))
    launcher.shortcut_actions["automated_tasks"].trigger()
    assert asked == ["tasks"]
    find = launcher.shortcut_actions["find_recent"]
    assert find.shortcut().toString() == "Ctrl+F"
    find.trigger()
    assert launcher.current_task == "recent"


# --- scanarea, preprocesarea -----------------------------------------------------------


def test_T_K008_scan_area_crops_the_sheet(tmp_path):
    path = tmp_path / "foaie.png"
    Image.new("L", (300, 400), 255).save(path, dpi=(72, 72))
    image = LoadedImage(path, 300, 400, 72, 72, ColorMode.GRAY)
    cropped = crop_to_area(image, Rect(10, 20, 100, 50))  # puncte = pixeli la 72 dpi
    assert (cropped.width_px, cropped.height_px) == (100, 50)
    with Image.open(path) as saved:
        assert saved.size == (100, 50)
    with pytest.raises(ValueError):
        crop_to_area(cropped, Rect(500, 500, 10, 10))


def test_T_K008_area_drawn_on_the_preview(qtbot, ctx, tmp_path):  # noqa: F811
    from app.gui.scan_dialog import ScanDialog

    folder = tmp_path / "scanari"
    folder.mkdir()
    dialog = ScanDialog(ctx, FakeScanner(folder), project=None)
    qtbot.addWidget(dialog)
    dialog.device.setCurrentIndex(1)
    assert dialog.preview()
    pixmap = dialog.preview_label.pixmap()
    ox = (dialog.preview_label.width() - pixmap.width()) // 2
    oy = (dialog.preview_label.height() - pixmap.height()) // 2
    area = dialog.set_scan_area(QRect(ox, oy, pixmap.width() // 2, pixmap.height() // 2))
    assert area is not None and area.x == pytest.approx(0, abs=1)
    assert isinstance(dialog.settings(), ScanSettings) and dialog.settings().scan_area == area
    assert dialog.set_scan_area(QRect(0, 0, 1, 1)) is None  # un clic: formatul hartiei


def test_T_L031_L034_default_and_no_preprocessing(ctx):  # noqa: F811
    from app.core.settings import definition

    assert definition("image.preprocess_mode").default == "auto"  # L-031
    ctx.settings.set("image.preprocess_mode", "none")
    flags = ctx.settings.preprocess_settings()
    assert not any(getattr(flags, f) for f in ("deskew", "split_facing_pages",
                                               "fix_inverted_colors"))
    from app.core.images.preprocess import default_pipeline

    assert PreprocessOp.DESKEW in default_pipeline().ops  # L-034: manual, din Image Editor


def test_T_L101_L104_image_editor_tools_and_next_page(qtbot, window):  # noqa: F811
    from app.gui.image_editor import TOOLS

    assert len(TOOLS) == 14 and TOOLS[0] == "recommended" and TOOLS[-1] == "remove_color_marks"
    editor = window.image_editor
    assert editor.show_next.text() == tr("editor.show_next")


# --- OCR Editor ------------------------------------------------------------------------


def test_T_O009_verify_options_open_the_settings(window, monkeypatch):  # noqa: F811
    opened = []
    monkeypatch.setattr(type(window), "open_options", lambda self, tab="general":
                        opened.append(tab))
    dialog = window.verify()
    dialog.options_requested.emit()
    assert opened == ["areas"]
    dialog.close()


def test_T_O082_copy_area_as_image(window):  # noqa: F811
    from app.gui.main_window import SHORTCUTS

    assert SHORTCUTS["copy_area_image"] == "Ctrl+Shift+C"
    view = window.image_view
    view.select([view.areas[0].id])
    image = window.edit_command("copy_area_image")
    assert image is not None and not image.isNull()


def test_T_O107_table_cells_with_lines_and_arrow_navigation(window):  # noqa: F811
    from PySide6.QtGui import QTextDocument

    doc = QTextDocument()
    cursor = QTextCursor(doc)
    table = cursor.insertTable(2, 2)
    assert table.format().border() > 0  # randuri si coloane cu linii
    cell = table.cellAt(0, 0).firstCursorPosition()
    cell.movePosition(QTextCursor.MoveOperation.NextCell)
    assert table.cellAt(cell).column() == 1  # tastele muta intre celule
    source = (ROOT / "app" / "gui" / "text_panel.py").read_text(encoding="utf-8")
    assert "insertTable(table.rows, table.cols)" in source


# --- P-024 -----------------------------------------------------------------------------


def test_T_P024_capitalization_rules():
    assert CASE_PATTERNS == ("lower", "capitalized", "upper", "mixed")
    assert [case_pattern(w) for w in ("casa", "Casa", "CASA", "cAsA", "123")] == [
        "lower", "capitalized", "upper", "mixed", None]
    assert case_allowed("Casa", ["lower", "capitalized"])
    assert not case_allowed("cAsA", ["lower", "capitalized"])
    words = [WordData(None, t, 95.0, bbox=Rect(0, 0, 10, 10), language_code="ron")
             for t in ("Casa", "cAsA")]
    block = BlockData(None, lines=[LineData(None, words=words, bbox=Rect(0, 0, 20, 10))])
    result = RecognitionResult(1, blocks=[block])
    _apply_case_rules(result, {"ron": ["lower", "capitalized", "upper"]})
    assert [w.is_uncertain for w in words] == [False, True] and result.uncertain_count == 1


def test_T_P024_rules_table_in_the_language_dialog(qtbot, ctx):  # noqa: F811
    from PySide6.QtCore import Qt

    from app.gui.options_dialog import OptionsDialog

    dialog = OptionsDialog(ctx)
    qtbot.addWidget(dialog)
    new = dialog.new_language()
    assert new.case_rules.rowCount() == 4
    new.case_rules.item(3, 0).setCheckState(Qt.CheckState.Unchecked)  # fara `cAsA`
    new.name.setText("Acte")
    code = new.create()
    assert ctx.settings.get("lang.case_rules")[code] == ["lower", "capitalized", "upper"]


# --- salvarea, Screenshot Reader -------------------------------------------------------


def test_T_Q010_save_button_follows_the_format(window):  # noqa: F811
    from app.gui.main_window import SAVE_LOOK

    window.update_save_button("pdf")
    pdf_icon = window.save_button.icon().pixmap(16, 16).toImage()
    window.update_save_button("docx")  # iconul se schimba dupa formatul ales
    assert window.save_format == "docx" and SAVE_LOOK["docx"] != SAVE_LOOK["pdf"]
    assert window.save_button.icon().pixmap(16, 16).toImage() != pdf_icon


def test_T_Q048_send_to_browser(window, monkeypatch):  # noqa: F811
    from app.core.model import ExportFormat
    from app.gui.document_actions import DocumentActions

    sent = []
    monkeypatch.setattr(DocumentActions, "send_to_application",
                        lambda self, fmt: sent.append(fmt))
    window.actions["send_browser"].trigger()
    assert sent == [ExportFormat.HTML]


def test_T_V008_V023_screenshot_recognition_stop_and_one_language(qtbot, ctx, monkeypatch):  # noqa: F811
    from app.core.errors import OperationCancelledError
    from app.gui import progress
    from app.gui.screenshot_window import ScreenshotWindow

    reader = ScreenshotWindow(ctx)
    qtbot.addWidget(reader)
    assert reader.language.toolTip() == tr("screenshot.one_language")  # V-023
    labels = []
    original = progress.ProgressRunner.__init__

    def init(self, *a, **k):
        original(self, *a, **k)
        labels.append(self.dialog)

    monkeypatch.setattr(progress.ProgressRunner, "__init__", init)

    def operation(cancel):
        labels[0].cancel()  # `Stop` sau `Esc` in dialogul de progres
        if cancel():
            raise OperationCancelledError("oprit")
        return "text"

    assert reader.run_recognition(operation) is None  # V-008: recunoasterea se opreste
    assert labels[0].labelText() == tr("screenshot.recognizing")


# --- J-404, J-411, J-415 ---------------------------------------------------------------


def test_T_J404_pages_toolbar(window):  # noqa: F811
    bar = window.pages_panel.findChild(object, "pages_toolbar")
    names = [a.objectName() for a in bar.actions() if a.objectName()]
    assert names[:4] == ["pages_save", "pages_delete", "pages_rotate_left", "pages_rotate_right"]
    assert window.pages_panel.findChild(object, "pages_more").text() == "..."


def test_T_J411_image_toolbar_second_row(window):  # noqa: F811
    from app.core.model import AreaType

    bar = window.image_panel.findChild(object, "image_toolbar_2")
    names = [a.objectName() for a in bar.actions()]
    tools = [n for n in names if n.startswith("image_tool.")]
    assert names[:2] == ["image_recognize_page", "image_analyze_page"]
    assert tools == [f"image_tool.{k.value}" for k in (
        AreaType.TEXT, AreaType.PICTURE, AreaType.TABLE, AreaType.BACKGROUND_PICTURE,
        AreaType.RECOGNITION)]
    assert bar.actions()[2].isSeparator()


def test_T_J415_image_properties_tab(window, project):  # noqa: F811
    page = project.page(1)
    info = window.image_panel.image_info
    assert info["size"].text() == tr("image.info.size_value", w=page.width_px,
                                     h=page.height_px)
    assert info["resolution"].text() == tr("image.info.dpi_value", dpi=page.dpi_x)
    assert info["format"].text() == "PNG"
    assert info["source"].text().endswith(".png")
