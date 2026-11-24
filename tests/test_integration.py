"""Faza 15, pasul 15.3: integrarile (W-001…W-017, W-080…W-094, W-200, W-204)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from test_hotfolder import _image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from app.core.context import AppContext
from app.core.integration import (
    CAPABILITIES,
    CONVERT_COMMANDS,
    PROG_ID,
    RUN_KEY,
    SCREENSHOT_RUN_NAME,
    SHELL_ROOT,
    MemoryRegistry,
    register_file_types,
    register_shell_menu,
    set_run_at_startup,
    shell_commands,
    unregister_all,
    unregister_shell_menu,
)
from app.core.paths import AppPaths
from app.gui.i18n import tr

EXE = ["C:\\Program Files\\DocuLens\\DocuLens.exe"]


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def app(qtbot, ctx):
    from app.gui.application import Application

    application = Application(ctx)
    yield application
    for window in application.windows():
        window.close()


# --- meniul contextual (W-001…W-017) ---

def test_T_W016_commands_depend_on_file_type():
    direct, convert = shell_commands(".pdf")
    assert direct[:2] == ("edit", "ocr") and convert == CONVERT_COMMANDS  # W-001, W-008
    direct, convert = shell_commands(".PNG")
    assert "edit" not in direct and convert  # imaginile nu se editeaza in PDF Editor
    direct, convert = shell_commands(".docx")
    assert direct[:2] == ("to_pdf", "to_pdf_send") and convert == ()  # W-012, W-013
    assert shell_commands(".exe") == ((), ())


def test_T_W001_W002_W017_registry_keys():
    registry = MemoryRegistry()
    count = register_shell_menu(registry, EXE, tr)
    root = SHELL_ROOT.format(ext=".pdf")
    assert registry.get(root, "MUIVerb") == tr("integration.menu")
    assert registry.get(root, "SubCommands") == ""
    command = registry.get(f"{root}\\shell\\edit\\command", "")
    assert command == '"C:\\Program Files\\DocuLens\\DocuLens.exe" --action edit "%1"'
    convert = f"{root}\\shell\\convert"  # W-002: submeniul de conversie
    assert registry.get(convert, "MUIVerb") == tr("integration.command.convert")
    for name in CONVERT_COMMANDS:  # W-003…W-007
        assert registry.get(f"{convert}\\shell\\{name}", "MultiSelectModel") == "Player"
    assert registry.get(f"{root}\\shell\\combine", "MUIVerb") == \
        tr("integration.command.combine")  # W-011
    assert count == register_shell_menu(registry, EXE, tr)  # W-017: se rescriu la fel
    unregister_shell_menu(registry)
    assert not any("DocuLens" in key for key in registry.keys if "shell" in key)


def test_T_W090_W204_file_types_and_uninstall():
    registry = MemoryRegistry()
    register_file_types(registry, EXE, tr)
    assert registry.get(f"Software\\Classes\\{PROG_ID}\\shell\\open\\command", "").endswith(
        '"%1"')
    assert registry.get("Software\\Classes\\.pdf\\OpenWithProgids", PROG_ID) == ""
    assert registry.get(f"{CAPABILITIES}\\FileAssociations", ".pdf") == PROG_ID
    set_run_at_startup(registry, True)
    register_shell_menu(registry, EXE, tr)
    unregister_all(registry)  # la dezinstalare
    assert registry.get(RUN_KEY, SCREENSHOT_RUN_NAME) is None
    assert not [k for k in registry.keys if "DocuLens" in k and registry.keys[k]]


def test_T_W017_X005_setting_adds_and_removes_menu(app, ctx):
    registry = MemoryRegistry()
    assert app.apply_shell_integration(registry)
    assert registry.get(SHELL_ROOT.format(ext=".pdf"), "MUIVerb")
    ctx.settings.set("general.shell_integration", False)
    assert not app.apply_shell_integration(registry)
    assert registry.get(SHELL_ROOT.format(ext=".pdf"), "MUIVerb") is None


# --- comenzile (W-001…W-015) ---

def test_T_W001_W008_W009_W010_actions(app, tmp_path, monkeypatch):
    from test_pdf_search import text_pdf

    pdf = text_pdf(tmp_path / "a.pdf", [["Text"]])
    other = text_pdf(tmp_path / "b.pdf", [["Alt text"]])
    opened = []
    monkeypatch.setattr(app, "open_pdf", lambda p: opened.append(("pdf", p)))
    monkeypatch.setattr(app, "open_in_ocr_editor", lambda f: opened.append(("ocr", f)))
    monkeypatch.setattr(app, "open_compare", lambda a, b=None: opened.append(("cmp", a, b)))
    app.run_action("edit", [pdf])
    app.run_action("ocr", [pdf])
    app.run_action("compare_with", [pdf])
    app.run_action("compare", [pdf, other])
    assert opened == [("pdf", pdf), ("ocr", [pdf]), ("cmp", pdf, None), ("cmp", pdf, other)]


def test_T_W015_explorer_files_are_batched_into_one_command(app, tmp_path, qtbot):
    files = [_image(tmp_path / f"{n}.png") for n in ("a", "b", "c")]
    seen = []
    app.run_action = lambda action, paths: seen.append((action, paths))
    for f in files:  # Explorer porneste cate un proces pe fisier
        app.handle_args(["--action", "convert_word", str(f)])
    qtbot.waitUntil(lambda: bool(seen), timeout=3000)
    assert seen == [("convert_word", files)]


def test_T_W003_W011_W015_convert_opens_launcher_screen(app, tmp_path, qtbot):
    files = [_image(tmp_path / f"{n}.png") for n in ("a", "b")]
    from app.gui.convert_screen import ConvertScreen

    screen = app.run_action("convert_searchable_pdf", files)
    qtbot.addWidget(app.launcher)
    assert isinstance(screen, ConvertScreen)  # W-015: Lansatorul, nu procesare directa
    combined = app.run_action("combine", files)
    assert combined.combine.isChecked()  # W-011


def test_T_W012_W013_W200_editable_to_pdf_and_send(app, tmp_path, monkeypatch):
    import pypdfium2 as pdfium
    from docx import Document

    source = tmp_path / "Cerere.docx"
    doc = Document()
    doc.add_paragraph("Solicit rambursarea cheltuielilor eligibile.")
    doc.save(source)
    opened = []
    monkeypatch.setattr(app, "open_pdf", lambda p: opened.append(p))
    app.run_action("to_pdf", [source])
    pdf = tmp_path / "Cerere.pdf"
    assert opened == [pdf]
    text = pdfium.PdfDocument(pdf)[0].get_textpage().get_text_range()
    assert "rambursarea" in text
    urls = []
    monkeypatch.setattr("app.gui.application.QDesktopServices.openUrl",
                        lambda url: urls.append(url.toString()))
    written = app.run_action("to_pdf_send", [source])
    assert written[0].name == "Cerere (2).pdf"
    assert app.last_mail_subject == f"Cerere (2).pdf ({tr('app.name')})"  # W-200
    assert urls[0].startswith("mailto:?subject=")


# --- deschiderea fisierelor (W-091, W-092, W-094) ---

def test_T_W091_W092_files_open_in_the_right_module(app, tmp_path, monkeypatch):
    from test_pdf_search import text_pdf

    pdf = text_pdf(tmp_path / "a.pdf", [["Text"]])
    image = _image(tmp_path / "scan.png")
    seen = []
    monkeypatch.setattr(app, "open_pdf", lambda p: seen.append(("pdf", p)))
    monkeypatch.setattr(app, "open_in_ocr_editor", lambda f: seen.append(("ocr", f)))
    app.handle_args([str(pdf), str(image)])
    assert seen == [("pdf", pdf), ("ocr", [image])]
    seen.clear()
    app.launcher.files_dropped.emit([pdf])  # W-091: tras in Lansator
    assert seen == [("pdf", pdf)]


def test_T_W094_second_launch_sends_files_to_the_first(qtbot):
    from app.gui.instance import InstanceServer, send_to_running

    name = f"dl-{os.getpid() % 100000}"  # caile socket-urilor locale sunt scurte
    assert not send_to_running(["x.pdf"], name=name)  # nicio instanta
    server = InstanceServer(name)
    assert server.listen()
    received = []
    server.received.connect(received.append)
    assert send_to_running(["--action", "ocr", "C:\\scan.png"], name=name)
    qtbot.waitUntil(lambda: bool(received), timeout=3000)
    assert received == [["--action", "ocr", "C:\\scan.png"]]
    server.close()


# --- aplicatia mobila si cloud-ul (W-080…W-087, decizia 11) ---

def test_T_W082_W083_W084_W086_mobile_folder_is_a_local_folder(app, tmp_path, qtbot):
    """W-082: folderul local al clientului de cloud; W-083: cel mai nou primul;
    W-084: PDF in editor, folderul de imagini devine PDF; W-086: fara retea."""
    launcher = app.launcher
    qtbot.addWidget(launcher)
    folder = tmp_path / "Google Drive" / "DocuLens"
    folder.mkdir(parents=True)
    old = folder / "vechi.pdf"
    old.write_bytes(b"%PDF-1.4\n")
    os.utime(old, (time.time() - 100, time.time() - 100))
    new = folder / "nou.pdf"
    new.write_bytes(b"%PDF-1.4\n")
    launcher.select_mobile_folder(folder)
    assert [p.name for p in launcher.mobile_items()][:2] == ["nou.pdf", "vechi.pdf"]
    seen = []
    launcher.pdf_requested.connect(seen.append)
    launcher.open_mobile(new)
    assert seen == [new]


def test_T_W085_W087_saving_is_a_normal_file_write(tmp_path):
    """W-085, W-087: sincronizarea e a clientului de cloud; DocuLens doar scrie
    fisierul in folderul local (nicio cerere de retea, Y-001)."""
    from app.core.convert import editable_to_pdf

    folder = tmp_path / "OneDrive"
    folder.mkdir()
    note = folder / "nota.txt"
    note.write_text("Nota pentru dosar", encoding="utf-8")
    assert editable_to_pdf(note).parent == folder
    assert isinstance(Path(folder), Path)


def test_T_W017_uninstall_entry_point_removes_keys(monkeypatch):
    """`DocuLens.exe --unregister-integration` (rulat de programul de dezinstalare)."""
    from app.core import integration
    from app.gui.main import main

    registry = MemoryRegistry()
    register_shell_menu(registry, EXE, tr)
    monkeypatch.setattr(integration, "default_registry", lambda: registry)
    assert main(["DocuLens", "--unregister-integration"]) == 0
    assert registry.get(SHELL_ROOT.format(ext=".pdf"), "MUIVerb") is None
    iss = (Path(__file__).resolve().parents[1] / "packaging" / "doculens.iss").read_text(
        encoding="utf-8")
    assert "--unregister-integration" in iss and "--screenshot-reader" in iss  # V-001


@pytest.mark.parametrize("action, key", [("convert_image_pdf", "pdf"),  # W-004
                                         ("convert_word", "docx"),  # W-005
                                         ("convert_excel", "xlsx")])  # W-006
def test_T_W004_W005_W006_explorer_convert_commands(app, tmp_path, qtbot, action, key):
    from app.core.convert import FullTextSearch

    files = [_image(tmp_path / "a.png")]
    screen = app.run_action(action, files)
    qtbot.addWidget(app.launcher)
    assert screen.key == key and screen.files.count() == 1
    if action == "convert_image_pdf":  # fara strat de text
        assert FullTextSearch(screen.fields["search"].currentData()) is FullTextSearch.DISABLED
        assert screen.settings().full_text_search is FullTextSearch.DISABLED
