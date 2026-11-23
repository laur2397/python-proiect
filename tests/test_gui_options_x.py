"""Setarile X fara test pana acum: tabul General (X-004, X-405, X-406), Image
Processing (X-013…X-015, X-019, X-408, X-412), Languages (X-043…X-049), OCR
(X-061, X-069, X-070, X-415, X-418), Format Settings (X-087…X-092, X-094,
X-102, X-104, X-107, X-420, X-422), Areas and Text (X-161…X-164), Other
(X-148), ordinea taburilor (X-402) si scurtaturile Lansatorului si ale
compararii (X-200, X-203)."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

import pytest
from PIL import Image
from test_gui_options import ctx, dialog, project  # noqa: F401  (fixture-uri)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QLabel

from app.core import integration
from app.core.compare.sources import compare_languages
from app.core.export.base import options_from_settings
from app.core.export.docx import encode_picture, picture_quality
from app.core.model import ExportFormat
from app.core.ocr import languages
from app.core.ocr.languages import LanguageRegistry
from app.core.settings import definition
from app.gui import theme
from app.gui.i18n import tr
from app.gui.options_dialog import OTHER_KEYS, TABS

ROOT = Path(__file__).resolve().parent.parent
SPEC_09 = ROOT / "docs" / "spec" / "SPEC_09_anexe_referinta.md"


def _visible_texts(widget) -> str:
    return "\n".join(w.text() for w in widget.findChildren(QLabel) + widget.findChildren(
        QCheckBox))


# --- ordinea, General -----------------------------------------------------------------


def test_T_X402_tab_order():
    assert TABS == ("general", "image", "languages", "ocr", "format", "areas", "other")


def test_T_X004_X406_default_viewer_message(dialog):  # noqa: F811
    registry = integration.MemoryRegistry()
    assert not dialog.update_default_viewer(registry)
    assert not dialog.default_pdf_note.isHidden() and not dialog.default_pdf_button.isHidden()
    assert "bold" in dialog.default_pdf_note.styleSheet()
    assert dialog.default_pdf_note.text() == tr("options.general.not_default")
    registry.set(integration.USER_CHOICE, "ProgId", integration.PROG_ID)
    assert dialog.update_default_viewer(registry)  # deja implicit: mesajul dispare
    assert dialog.default_pdf_note.isHidden() and dialog.default_pdf_button.isHidden()


def test_T_X405_scan_interface_radios_and_help_link(dialog):  # noqa: F811
    radios = dialog.radios["general.scan_interface"]
    assert set(radios) == {"app", "driver"}
    assert "(" in radios["app"].text()  # `(scanners only)`
    assert tr("options.general.which_interface") in _visible_texts(dialog)


# --- Image Processing -----------------------------------------------------------------


def test_T_X013_X014_X015_preprocessing_modes(dialog, ctx, project, tmp_path):  # noqa: F811
    assert definition("image.preprocess_mode").default == "auto"  # X-014: activ implicit
    assert dialog.preprocess_note.text() == tr("options.image.preprocess_note")
    manual = dialog.radios["image.preprocess_mode"]["manual"]
    manual.setChecked(True)  # X-015: `Specify settings manually`
    assert all(dialog.fields[k][0].isEnabled() for k in ("image.split_facing_pages",
                                                         "image.correct_orientation"))
    before = [p.page_number for p in project.pages]
    dialog.accept()
    assert project.settings().get("image.preprocess_mode") == "manual"
    assert [p.page_number for p in project.pages] == before  # paginile existente raman


def test_T_X019_show_and_hide_custom_settings(dialog):  # noqa: F811
    assert dialog.custom.isHidden()
    dialog.custom_toggle.setChecked(True)
    assert not dialog.custom.isHidden()
    assert dialog.custom_toggle.text() == tr("options.image.hide_custom")
    dialog.custom_toggle.setChecked(False)
    assert dialog.custom_toggle.text() == tr("options.image.show_custom")


def test_T_X408_background_note_and_X412_photo_note(dialog):  # noqa: F811
    texts = _visible_texts(dialog)
    assert tr("options.image.background_note") in texts
    assert tr("options.image.photo_note") in texts


# --- Languages ------------------------------------------------------------------------


def test_T_X043_new_language_and_group(dialog):  # noqa: F811
    new = dialog.new_language()
    new.name.setText("Romana veche")
    assert new.create() == "user:romana_veche"
    names = [dialog.language_lists["lang.manual"].item(i).text()
             for i in range(dialog.language_lists["lang.manual"].count())]
    assert "Romana veche*" in names  # baza (romana) are dictionar
    group = dialog.new_language()
    group.kind_group.setChecked(True)
    group.name.setText("Dosar")
    assert group.create() is None and group.error.text()  # un grup are nevoie de 2 limbi
    for i in range(3):
        group.members.item(i).setCheckState(group.members.item(i).checkState().Checked)
    assert group.create() == "group:Dosar"
    dup = dialog.new_language()
    dup.name.setText("Romana veche")
    assert dup.create() is None  # numele e unic


def test_T_X044_three_categories():
    reg = LanguageRegistry()
    assert set(reg.by_category(languages.ARTIFICIAL)) == {"ido", "ina", "ile", "epo"}
    assert {"basic", "cpp", "cobol", "fortran", "java", "pascal", "math", "digits"} <= \
        set(reg.by_category(languages.FORMAL))
    assert len(reg.by_category(languages.NATURAL)) > 100


def test_T_X045_dictionary_languages_have_an_asterisk(dialog):  # noqa: F811
    lst = dialog.language_lists["lang.auto_candidates"]
    by_code = {lst.item(i).data(0x0100): lst.item(i).text() for i in range(lst.count())}
    assert by_code["ron"].endswith("*") and not by_code["digits"].endswith("*")


def test_T_X046_compare_languages():
    assert len(compare_languages()) == 37


def test_T_X047_license_info_lists_all_languages(qtbot, ctx):  # noqa: F811
    from app.gui.about_dialog import AboutDialog

    about = AboutDialog(ctx)
    qtbot.addWidget(about)
    info = about.show_license_info()
    text = info.text.toPlainText()
    assert tr("about.languages.total", n=len(LanguageRegistry().all())) in text
    assert "Esperanto" in text or "epo" in text
    info.close()


def test_T_X048_gothic_languages_alone():
    assert sorted(languages.GOTHIC.values()) == sorted([
        "Old English", "Old French", "Old German", "Old Italian", "Old Spanish",
        "Latvian Gothic"])
    assert languages.gothic_mixed(["frk", "deu"]) and not languages.gothic_mixed(["frk"])


def test_T_X049_romanian_and_romanian_moldavia():
    reg = LanguageRegistry()
    assert reg.is_builtin("ron") and reg.is_builtin("ron-MD")
    assert definition("ocr.keep_cedilla_diacritics") is not None  # varianta cu sedila


# --- OCR ------------------------------------------------------------------------------


def test_T_X061_searchable_pdfs_always_use_ocr(dialog):  # noqa: F811
    from app.core.model import PdfRecognitionMode as M
    from app.core.ocr import textlayer

    assert dialog.pdf_mode_note.text() == tr("options.ocr.pdf_mode_note")
    for requested in M:  # o pagina fara strat de text -> OCR, orice ar spune setarea
        assert textlayer.choose_mode(None, requested) is M.FORCE_OCR


def test_T_X069_pattern_editor_button(dialog):  # noqa: F811
    assert dialog.pattern_editor_button.isEnabled()
    editor = dialog.open_pattern_editor()
    assert editor.objectName() == "pattern_editor"
    editor.close()


def test_T_X070_patterns_file_types(dialog, tmp_path):  # noqa: F811
    assert dialog.patterns_bundle(load=False, path=tmp_path / "s.fbtx")
    assert dialog.patterns_bundle(load=True, path=tmp_path / "s.fbtx")
    source = (ROOT / "app" / "gui" / "options_dialog.py").read_text(encoding="utf-8")
    assert '"*.fbtx *.fbt"' in source


def test_T_X415_which_mode_link(dialog):  # noqa: F811
    assert tr("options.ocr.which_mode") in _visible_texts(dialog)


def test_T_X418_select_fonts(dialog, project):  # noqa: F811
    assert tr("options.ocr.fonts") in _visible_texts(dialog)
    fonts = dialog.choose_fonts()
    assert fonts.list.count() > 0
    fonts.list.item(0).setCheckState(fonts.list.item(0).checkState().Checked)
    chosen = fonts.list.item(0).text()
    fonts.accept()
    dialog.accept()
    assert project.settings().get("ocr.export_fonts") == [chosen]


# --- Format Settings ------------------------------------------------------------------


def test_T_X087_X088_X089_X090_X091_pdf_controls(dialog):  # noqa: F811
    for key in ("pdf.smooth_characters", "pdf.bookmarks_from_headings", "pdf.create_tags",
                "pdf.searchable_mode", "pdf.fonts"):
        assert key in dialog.fields, key
    assert definition("pdf.searchable_mode").allowed == ("text_and_pictures", "text_over",
                                                         "text_under")
    assert definition("pdf.fonts").allowed == ("predefined", "system")


def test_T_X092_embed_fonts_only_without_text_under(dialog):  # noqa: F811
    mode = dialog.fields["pdf.searchable_mode"][0]
    embed = dialog.fields["pdf.embed_fonts"][0]
    for value, enabled in (("text_and_pictures", True), ("text_over", True),
                           ("text_under", False)):
        mode.setCurrentIndex(mode.findData(value))
        assert embed.isEnabled() is enabled, value


def test_T_X094_edit_metadata(dialog, project):  # noqa: F811
    edit = dialog.edit_metadata()
    edit.edits["title"].setText("Cerere de finantare")
    edit.edits["author"].setText("Primaria")
    edit.accept()
    dialog.accept()
    assert project.settings().get("pdf.metadata") == {"title": "Cerere de finantare",
                                                     "author": "Primaria"}
    options = options_from_settings(project.settings(), ExportFormat.PDF)
    assert options.metadata == {"title": "Cerere de finantare", "author": "Primaria"}
    with pytest.raises(ValueError):
        project.settings().set("pdf.metadata", {"necunoscut": "x"})


def test_T_X102_keep_pictures_with_quality(dialog):  # noqa: F811
    keep = dialog.fields["docx.keep_pictures"][0]
    quality = dialog.fields["docx.image_quality"][0]
    custom = dialog.fields["docx.image_custom_quality"][0]
    keep.setChecked(True)
    quality.setCurrentIndex(quality.findData("custom"))
    assert custom.isEnabled()  # `Custom...`
    quality.setCurrentIndex(quality.findData("compact"))
    assert not custom.isEnabled()
    keep.setChecked(False)
    assert not quality.isEnabled()
    assert picture_quality("best") is None and picture_quality("custom", 40) == 40
    png = io.BytesIO()
    Image.new("RGB", (200, 200), (30, 120, 200)).save(png, "PNG")
    assert encode_picture(png.getvalue(), None) == png.getvalue()
    assert encode_picture(png.getvalue(), 60)[:2] == b"\xff\xd8"  # JPEG


def test_T_X104_X107_docx_checkboxes(dialog):  # noqa: F811
    assert isinstance(dialog.fields["docx.keep_line_breaks"][0], QCheckBox)
    assert isinstance(dialog.fields["docx.keep_colors"][0], QCheckBox)
    assert definition("docx.keep_line_breaks").default is False
    assert definition("docx.keep_colors").default is True


def test_T_X420_selected_format_is_blue():
    color = QColor(theme.COLORS["accent_soft"])
    assert color.blue() > color.red() and color.blue() > color.green()
    assert "QListWidget::item:selected" in theme.stylesheet()


def test_T_X422_pdfa_version_grey_until_checked(dialog):  # noqa: F811
    pdfa = dialog.fields["pdf.create_pdfa"][0]
    pdfa.setChecked(False)
    assert not dialog.fields["pdf.pdfa_version"][0].isEnabled()
    pdfa.setChecked(True)
    assert dialog.fields["pdf.pdfa_version"][0].isEnabled()


# --- Areas and Text, Other ------------------------------------------------------------


def test_T_X161_X162_X163_X164_areas_tab(dialog):  # noqa: F811
    for key in ("areas.ignore_words_with_digits", "areas.check_compound_words",
                "areas.fix_punctuation_spaces", "areas.user_dictionaries_folder",
                "areas.plain_text_font"):
        assert key in dialog.fields, key
    assert definition("areas.user_dictionaries_folder").value_type == "path"  # `Browse...`


def test_T_X148_shortcuts_are_not_in_the_other_tab(dialog):  # noqa: F811
    from app.gui.shortcuts_dialog import CustomizeDialog

    assert not any("shortcut" in key for key in OTHER_KEYS)
    assert CustomizeDialog is not None  # `View > Toolbars > Customize...` (J-012)


# --- scurtaturile A.1 si A.4 ----------------------------------------------------------


def _table(section: str) -> dict[str, str]:
    text = SPEC_09.read_text(encoding="utf-8")
    body = text.split(f"### {section}", 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
    rows = {}
    for line in body.splitlines():
        cells = [c.strip(" *`") for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] and cells[0] not in ("Comanda", "---"):
            rows[cells[0]] = cells[1]
    return rows


def _normal(key: str) -> str:
    for ro, en in (("Sus", "Up"), ("Jos", "Down"), ("Stanga", "Left"), ("Dreapta", "Right")):
        key = re.sub(rf"\b{ro}\b", en, key)
    return key


def test_T_X200_launcher_shortcuts_follow_a1(qtbot, ctx):  # noqa: F811
    from app.gui.convert_screen import ConvertScreen  # noqa: F401  (Alt+Sus/Jos, Del, Ctrl+A)
    from app.gui.launcher import SHORTCUTS, Launcher

    table = _table("A.1")
    commands = {"New PDF Document": "new_pdf", "Open PDF Document...": "open_pdf",
                "Open in OCR Editor...": "open_in_ocr_editor",
                "Scan to OCR Editor": "scan_to_ocr_editor",
                "New OCR Project": "new_ocr_project", "Open OCR Project...": "open_ocr_project",
                "Options...": "options", "Exit": "exit",
                "Find Recent Documents": "find_recent", "Help": "F1"}
    for name, key in commands.items():
        if key == "F1":
            assert table["Help"] == SHORTCUTS["help"]
            continue
        assert SHORTCUTS[key] == _normal(table[name]), name
    source = (ROOT / "app" / "gui" / "convert_screen.py").read_text(encoding="utf-8")
    for name in ("Move Up", "Move Down", "Remove", "Select All"):
        assert f'"{_normal(table[name])}"' in source, name
    launcher = Launcher(ctx)
    qtbot.addWidget(launcher)
    requested = []
    launcher.ocr_editor_requested.connect(requested.append)
    launcher.shortcut_actions["new_ocr_project"].trigger()
    assert requested == [[]]
    scans = []
    launcher.scan_requested.connect(scans.append)
    launcher.shortcut_actions["scan_to_ocr_editor"].trigger()
    assert scans == ["ocr_editor"]
    projects = []
    launcher.project_requested.connect(projects.append)
    launcher.open_ocr_project(Path("/tmp/proiect"))
    assert projects == [Path("/tmp/proiect")]
    assert launcher.shortcut_actions["exit"].shortcut().toString() == "Ctrl+Q"


def test_T_X203_compare_shortcuts_follow_a4():
    from app.gui.compare_window import SHORTCUTS

    table = _table("A.4")
    commands = {"New Comparison": "new", "Open Document...": "open", "Close Document": "close",
                "Save...": "save", "Exit": "exit", "Undo": "undo", "Redo": "redo",
                "Select All Differences": "select_all", "Zoom In": "zoom_in",
                "Zoom Out": "zoom_out", "Fit to Width": "fit_width", "Next Page": "next_page",
                "Previous Page": "previous_page", "Compare Documents": "compare",
                "Next Difference": "next_difference",
                "Previous Difference": "previous_difference", "Ignore Difference": "ignore",
                "Help": "help"}
    assert set(commands) == set(table)
    for name, key in commands.items():
        assert SHORTCUTS[key] == _normal(table[name]), name

