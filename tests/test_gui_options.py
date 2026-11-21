"""Faza 6b, pasul 6b.5: dialogul Options (X-400…X-423) si raportarea unei
erori neasteptate (Y-025)."""

from __future__ import annotations

import os
import re

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QComboBox, QDialogButtonBox, QLabel

from app.core.applog import record_unexpected_error
from app.core.context import AppContext
from app.core.model import AutoProcessMode
from app.core.paths import AppPaths
from app.core.project import OcrProject
from app.core.settings import CATALOG
from app.gui.error_dialog import ErrorDialog, install_excepthook
from app.gui.main_window import MainWindow
from app.gui.options_dialog import FORMATS, PREPROCESS_COLUMNS, TABS, OptionsDialog


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def project(ctx, tmp_path):
    Image.new("L", (600, 800), 255).save(tmp_path / "p1.png", dpi=(300, 300))
    p = OcrProject.create(context=ctx)
    p.add_images([tmp_path / "p1.png"], auto_process=AutoProcessMode.NONE)
    yield p
    p.close()


@pytest.fixture
def dialog(qtbot, ctx, project):
    d = OptionsDialog(ctx, project)
    qtbot.addWidget(d)
    return d


def test_T_X400_1_modal_size_and_X423_buttons(dialog):
    assert dialog.isModal()
    assert abs(dialog.width() - 650) <= 50 and abs(dialog.height() - 620) <= 50
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isDefault()
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel) is not None


def test_T_X401_1_and_X402_1_tabs(dialog):
    from PySide6.QtWidgets import QListView

    assert dialog.tabs.viewMode() == QListView.ViewMode.IconMode  # eticheta sub icon
    assert [dialog.tabs.item(i).text() for i in range(dialog.tabs.count())] == [
        "General", "Procesarea imaginilor", "Limbi", "OCR", "Setări de format",
        "Zone și text", "Altele"]
    assert TABS == ("general", "image", "languages", "ocr", "format", "areas", "other")


def test_every_visible_setting_has_a_control(dialog):
    # recentele; fonturile au dialog propriu; folderul mobil se alege in Lansator (A-107)
    internal = {"lang.recent", "ocr.export_fonts", "launcher.mobile_folder"}
    assert {d.key for d in CATALOG} - set(dialog.fields) == internal


def test_no_untranslated_key_in_the_dialog(dialog):
    texts = [w.text() for w in dialog.findChildren(QLabel) + dialog.findChildren(
        QAbstractButton)]
    for combo in dialog.findChildren(QComboBox):
        texts += [combo.itemText(i) for i in range(combo.count())]
    texts += [dialog.tabs.item(i).text() for i in range(dialog.tabs.count())]
    assert [t for t in texts if re.fullmatch(r"[a-z_]+(\.[a-z_0-9-]+)+", t)] == []


def test_T_X403_1_startup_radios(dialog):
    radios = dialog.radios["general.startup_screen"]
    assert [b.text() for b in radios.values()] == ["Deschide un proiect OCR nou",
                                                   "Deschide ultimul proiect OCR folosit"]


def test_T_X410_1_preprocess_columns_and_X412_star(dialog):
    assert [len(c) for c in PREPROCESS_COLUMNS] == [5, 5, 3]
    assert all(dialog.fields[k][0].text().endswith("*") for k in PREPROCESS_COLUMNS[1])
    assert not dialog.fields[PREPROCESS_COLUMNS[0][0]][0].text().endswith("*")


def test_T_X411_1_custom_settings_toggle(dialog):
    assert dialog.custom.isHidden()
    dialog.custom_toggle.click()
    assert not dialog.custom.isHidden()
    assert dialog.custom_toggle.text() == "Ascunde setările personalizate"
    dialog.custom_toggle.click()
    assert dialog.custom_toggle.text() == "Arată setările personalizate"


def test_T_X413_1_and_X414_1_modes_keep_checkboxes(dialog):
    deskew = dialog.fields["image.deskew"][0]
    deskew.setChecked(False)
    dialog.radios["image.preprocess_mode"]["none"].setChecked(True)
    assert not deskew.isEnabled()
    dialog.radios["image.preprocess_mode"]["manual"].setChecked(True)
    assert deskew.isEnabled() and not deskew.isChecked()  # bifa nu s-a pierdut


def test_T_X416_1_two_also_use_builtin_checkboxes(dialog):
    also_user = dialog.fields["ocr.user_patterns_also_builtin"][0]
    also_training = dialog.fields["ocr.training_also_builtin"][0]
    dialog.radios["ocr.patterns"]["builtin"].setChecked(True)
    dialog.fields["ocr.use_training"][0].setChecked(False)
    assert not also_user.isEnabled() and not also_training.isEnabled()
    dialog.radios["ocr.patterns"]["user"].setChecked(True)
    dialog.fields["ocr.use_training"][0].setChecked(True)
    assert also_user.isEnabled() and also_training.isEnabled()


def test_T_X417_1_save_and_load_patterns(dialog, tmp_path):
    names = [b.objectName() for b in dialog.findChildren(QAbstractButton)]
    assert {"pattern_editor", "load_patterns", "save_patterns"} <= set(names)
    assert dialog.patterns_bundle(load=False, path=tmp_path / "s.fbtx")
    assert (tmp_path / "s.fbtx").is_file()
    assert dialog.patterns_bundle(load=True, path=tmp_path / "s.fbtx")
    (tmp_path / "rau.fbt").write_bytes(b"x")
    assert not dialog.patterns_bundle(load=True, path=tmp_path / "rau.fbt")
    assert dialog.error.text() == "Fișierul de șabloane nu a putut fi folosit"


def test_T_X419_1_format_list_order(dialog):
    assert [dialog.formats.item(i).text() for i in range(dialog.formats.count())] == [
        "PDF", "DOC(X) / RTF / ODT", "XLS(X)", "PPTX", "CSV", "TXT", "HTML", "EPUB / FB2",
        "DjVu"]
    assert [k for k, _ in FORMATS][-1] == "djvu"
    dialog.formats.setCurrentRow(3)
    assert dialog.format_pages.currentWidget().objectName() == "format_pptx"


def test_T_X421_1_pdfua_forces_tags_and_X422_1_pdfa_version(dialog):
    tags = dialog.fields["pdf.create_tags"][0]
    ua = dialog.fields["pdf.create_pdfua"][0]
    ua.setChecked(False)
    tags.setChecked(False)
    ua.setChecked(True)
    assert tags.isChecked() and not tags.isEnabled()
    ua.setChecked(False)
    assert tags.isEnabled()
    pdfa = dialog.fields["pdf.create_pdfa"][0]
    pdfa.setChecked(False)
    assert not dialog.fields["pdf.pdfa_version"][0].isEnabled()
    pdfa.setChecked(True)
    assert dialog.fields["pdf.pdfa_version"][0].isEnabled()


def test_delete_objects_items(dialog, project):
    dialog.fields["pdf.delete_objects"][0].setChecked(True)
    dialog.delete_boxes["comments"].setChecked(False)
    assert dialog.apply()
    assert "comments" not in project.settings().get("pdf.delete_objects_items")


def test_ok_saves_project_and_global_settings(dialog, ctx, project):
    """Decizia 10: setarile aplicatiei in cele globale, restul in proiect."""
    dialog.fields["ui.language"][2]("en")
    dialog.fields["docx.keep_pictures"][2](False)
    dialog.fields["areas.color.text"][2]("#112233")
    dialog.fields["ocr.max_threads"][2](2)
    dialog.accept()
    assert ctx.settings.get("ui.language") == "en"
    assert ctx.settings.get("ocr.max_threads") == 2
    assert project.settings().get("docx.keep_pictures") is False
    assert ctx.settings.get("docx.keep_pictures") is True  # numai in proiect
    assert project.settings().get("areas.color.text").lower() == "#112233"


def test_cancel_changes_nothing(dialog, project):
    dialog.fields["docx.keep_pictures"][2](False)
    dialog.reject()
    assert project.settings().get("docx.keep_pictures") is True


def test_opening_and_closing_changes_nothing(qtbot, ctx, project):
    project.settings().set("lang.manual", ["ron", "eng"])
    d = OptionsDialog(ctx, project)
    qtbot.addWidget(d)
    assert {k: v for k, v in d.values().items() if v != d._initial[k]} == {}
    assert d.values()["lang.manual"] == ["ron", "eng"]  # ordinea limbilor ramane


def test_T_X409_1_languages_link_opens_the_tab(dialog):
    dialog.show_tab("image")
    dialog.languages_link.linkActivated.emit("#")
    assert dialog.current_tab == "languages"


def test_main_window_opens_options(qtbot, ctx, project):
    window = MainWindow(ctx, project)
    qtbot.addWidget(window)
    dialog = window.open_options("ocr", modal=False)
    assert dialog.current_tab == "ocr"
    dialog.fields["areas.color.text"][2]("#445566")
    dialog.accept()
    assert project.settings().get("areas.color.text").lower() == "#445566"


# =============================================================================
# Y-025
# =============================================================================


def test_T_Y025_1_error_dialog(qtbot, ctx, tmp_path):
    try:
        raise RuntimeError("ceva neasteptat")
    except RuntimeError as exc:
        report = record_unexpected_error(exc, ctx.paths.log_dir)
    dialog = ErrorDialog(report)
    qtbot.addWidget(dialog)
    assert "RuntimeError: ceva neasteptat" in dialog.findChild(QLabel, "crash_message").text()
    assert "raise RuntimeError" in dialog.trace.toPlainText()
    assert dialog.trace.isReadOnly()
    dialog.copy()
    from PySide6.QtWidgets import QApplication

    assert "ceva neasteptat" in QApplication.clipboard().text()
    assert dialog.save(tmp_path / "raport.txt")
    assert "RuntimeError" in (tmp_path / "raport.txt").read_text(encoding="utf-8")


def test_excepthook_reports_and_keeps_running(ctx, monkeypatch):
    import sys

    shown = []
    monkeypatch.setattr(ErrorDialog, "exec", lambda self: shown.append(self.report))
    old = sys.excepthook
    try:
        install_excepthook(ctx)
        try:
            raise ValueError("oops")
        except ValueError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = old
    assert shown and shown[0].error_type == "ValueError" and shown[0].report_path.is_file()
