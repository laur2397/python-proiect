"""Faza 14: linia de comanda (U-001…U-013, U-020…U-028, U-040…U-051)."""

from __future__ import annotations

import io
import json

import pytest
from test_automated_tasks import ScriptEngine
from test_hotfolder import _image
from test_pdf_search import text_pdf
from test_scanner import FakeScanner

from app.cli import main as cli
from app.cli.main import (
    EXIT_CANCELLED,
    EXIT_FILE,
    EXIT_OK,
    EXIT_RECOGNITION,
    EXIT_USAGE,
    EXIT_WRITE,
    SEND_TARGETS,
    Services,
    exit_code_for,
    help_text,
    parse_compare,
    parse_ocr,
    run_compare,
    run_ocr,
)
from app.core.context import AppContext
from app.core.errors import NoWritePermissionError, RecognitionFailedError
from app.core.paths import AppPaths


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def services(ctx):
    s = Services(context=ctx, engine=ScriptEngine(), stdout=io.StringIO(),
                 stderr=io.StringIO())
    s.opened = []
    s.copied = []
    s.opener = s.opened.append
    s.clipboard = s.copied.append
    return s


@pytest.fixture
def doc(tmp_path):
    return _image(tmp_path / "Guide German.png")


# --- conversia (U-001…U-013) ---

def test_T_U001_U010_official_syntax(services, doc):
    """U-001, U-010: `<fisier> /lang German /send MSWord`, cu spatii in cale."""
    cmd = parse_ocr([str(doc), "/lang", "German", "/send", "MSWord"])
    assert cmd.sources == [doc] and cmd.languages == ["German"] and cmd.send == "MSWord"
    assert run_ocr([str(doc), "/lang", "German", "/send", "MSWord"], services) == EXIT_OK
    [opened] = services.opened
    assert opened.suffix == ".docx" and opened.stem == "Guide German"


def test_T_U002_several_sources_combined(services, tmp_path):
    import pypdfium2 as pdfium

    files = [_image(tmp_path / f"{n}.png") for n in ("a", "b")]
    out = tmp_path / "dosar.pdf"
    assert run_ocr([*map(str, files), "/lang", "Romanian", "/out", str(out)],
                   services) == EXIT_OK
    assert len(pdfium.PdfDocument(out)) == 2


def test_T_U003_scan_named_and_last_scanner(services, ctx, tmp_path):
    scanner = FakeScanner(tmp_path)
    services.scanner = scanner
    out = tmp_path / "scan.pdf"
    assert run_ocr(["/scan", "Scaner plat", "/out", str(out)], services) == EXIT_OK
    assert scanner.scans[-1].device_id == "flat" and out.exists()
    assert ctx.settings.get("general.capture_device") == "flat"
    assert run_ocr(["/scan", "/out", str(out)], services) == EXIT_OK  # ultimul folosit
    assert scanner.scans[-1].device_id == "flat"
    assert run_ocr(["/scan", "Altul", "/out", str(out)], services) == EXIT_FILE


def test_T_U004_last_language_used(services, ctx, doc, tmp_path):
    ctx.settings.set("lang.manual", ["deu"])
    out = tmp_path / "x.txt"
    assert run_ocr([str(doc), "/out", str(out)], services) == EXIT_OK
    assert ctx.settings.get("lang.manual") == ["deu"]  # fara /lang: ultima
    assert run_ocr([str(doc), "/lang", "Romanian", "English", "/out", str(out)],
                   services) == EXIT_OK
    assert ctx.settings.get("lang.manual") == ["ron", "eng"]
    assert run_ocr([str(doc), "/lang", "Klingon", "/out", str(out)], services) == EXIT_USAGE


def test_T_U005_custom_language_with_double_at(services, ctx, doc, tmp_path):
    from app.core.ocr.languages import LanguageRegistry

    LanguageRegistry(con=ctx.app_db).create_user_language("Facturi", "ron")
    out = tmp_path / "x.txt"
    assert run_ocr([str(doc), "/lang", "@@Facturi", "/out", str(out)], services) == EXIT_OK
    assert ctx.settings.get("lang.manual") == ["user:facturi"]
    assert run_ocr([str(doc), "/lang", "@@Fac-turi", "/out", str(out)],
                   services) == EXIT_USAGE  # caractere nealfanumerice


def test_T_U006_eight_send_targets(services, doc):
    assert list(SEND_TARGETS) == ["MSWord", "MSExcel", "OpenOffice", "Mail", "Clipboard",
                                  "WebBrowser", "PDFViewer", "PowerPoint"]
    expected = {"MSWord": ".docx", "MSExcel": ".xlsx", "OpenOffice": ".odt",
                "WebBrowser": ".html", "PDFViewer": ".pdf", "PowerPoint": ".pptx"}
    for target, suffix in expected.items():
        services.opened.clear()
        assert run_ocr([str(doc), "/send", target], services) == EXIT_OK, target
        assert services.opened[0].suffix == suffix
    services.opened.clear()
    assert run_ocr([str(doc), "/send", "Mail"], services) == EXIT_OK  # Word, apoi e-mail
    assert str(services.opened[0]) == "mailto:"
    assert run_ocr([str(doc), "/send", "Clipboard"], services) == EXIT_OK
    assert "Guide" in services.copied[-1]
    assert run_ocr([str(doc), "/send", "Notepad"], services) == EXIT_USAGE  # a noua valoare


def test_T_U007_existing_out_is_replaced(services, doc, tmp_path):
    out = tmp_path / "rezultat.txt"
    out.write_text("vechi", encoding="utf-8")
    assert run_ocr([str(doc), "/out", str(out)], services) == EXIT_OK
    assert "vechi" not in out.read_text(encoding="utf-8")
    assert run_ocr([str(doc), "/out", str(tmp_path / "x.abc")], services) == EXIT_USAGE


def test_T_U008_report_file(services, doc, tmp_path):
    report = tmp_path / "jurnal" / "conv.log"
    out = tmp_path / "r.docx"
    assert run_ocr([str(doc), "/out", str(out), "/report", str(report)], services) == EXIT_OK
    text = report.read_text(encoding="utf-8")
    assert str(out) in text and cli.tr("cli.report.end", code=0) in text


def test_T_U009_without_out_result_opens(services, doc):
    assert run_ocr([str(doc)], services) == EXIT_OK
    [opened] = services.opened
    assert opened.suffix == ".pdf" and opened.exists()


def test_T_U011_saving_always_available(services, doc, tmp_path):
    """U-011: nu exista niveluri de licenta; `/out` merge intotdeauna."""
    assert run_ocr([str(doc), "/out", str(tmp_path / "a.rtf")], services) == EXIT_OK


def test_T_U012_options_of_the_original_and_extensions(services, doc):
    text = help_text(cli.OCR_PROGRAM)
    original, extensions = text.split(cli.tr("cli.help.extensions"))
    assert "/send" in original and "/pages" not in original
    for option in ("/indir", "/pages", "/layout", "/pdfa", "/mrc", "/threads", "/json",
                   "/recursive", "/quiet"):
        assert option in extensions
    for option in ("/format", "/dpi", "/split", "/merge", "/config"):  # decizia 2
        assert run_ocr([str(doc), option, "x"], services) == EXIT_USAGE


def test_T_U013_no_server_mode(services, doc):
    services.interactive = lambda: False
    assert run_ocr([str(doc)], services) == EXIT_USAGE
    assert cli.tr("cli.error.no_session") in services.stderr.getvalue()


# --- extinderile (U-040…U-050) ---

def test_T_U040_U041_U042_folder_pattern_recursive(services, tmp_path):
    src = tmp_path / "in"
    _image(src / "a.png")
    _image(src / "sub" / "b.png")
    (src / "nota.txt").write_text("x", encoding="utf-8")
    out = tmp_path / "out"
    assert run_ocr(["/indir", str(src), "/outdir", str(out), "/pattern", "*.png"],
                   services) == EXIT_OK
    assert sorted(p.name for p in out.iterdir()) == ["a.pdf"]
    assert run_ocr(["/indir", str(src), "/outdir", str(out), "/pattern", "*.png",
                    "/recursive"], services) == EXIT_OK
    assert sorted(p.name for p in out.iterdir()) == ["a.pdf", "b.pdf"]
    assert run_ocr(["/indir", str(src)], services) == EXIT_USAGE  # fara /outdir


def test_T_U043_pages(services, tmp_path):
    import pypdfium2 as pdfium

    pdf = text_pdf(tmp_path / "trei.pdf", [["unu"], ["doi"], ["trei"]])
    out = tmp_path / "x.pdf"
    assert run_ocr([str(pdf), "/pages", "1,3", "/out", str(out)], services) == EXIT_OK
    assert len(pdfium.PdfDocument(out)) == 2
    assert parse_ocr([str(pdf), "/pages", "1-3,5"]).pages == (1, 2, 3, 5)
    assert run_ocr([str(pdf), "/pages", "3-1"], services) == EXIT_USAGE


def test_T_U044_layout_checked_against_format(services, doc, tmp_path):
    assert run_ocr([str(doc), "/layout", "flexible", "/out", str(tmp_path / "a.docx")],
                   services) == EXIT_USAGE  # Q-001: flexible numai HTML
    assert run_ocr([str(doc), "/layout", "flexible", "/out", str(tmp_path / "a.html")],
                   services) == EXIT_OK


def test_T_U045_pdfa_not_with_password(services, doc, tmp_path):
    assert run_ocr([str(doc), "/pdfa", "2b", "/password", "x"], services) == EXIT_USAGE
    out = tmp_path / "a.pdf"
    assert run_ocr([str(doc), "/pdfa", "2b", "/out", str(out)], services) == EXIT_OK
    assert run_ocr([str(doc), "/pdfa", "9z"], services) == EXIT_USAGE


def test_T_U046_U047_mrc_and_threads(services, doc, tmp_path):
    import os

    assert run_ocr([str(doc), "/mrc", "/threads", "1", "/out", str(tmp_path / "m.pdf")],
                   services) == EXIT_OK
    too_many = str((os.cpu_count() or 1) + 1)
    assert run_ocr([str(doc), "/threads", too_many], services) == EXIT_USAGE


def test_T_U048_U049_json_and_quiet(services, doc, tmp_path):
    out = tmp_path / "j.txt"
    assert run_ocr([str(doc), "/out", str(out), "/json"], services) == EXIT_OK
    result = json.loads(services.stdout.getvalue().strip().splitlines()[-1])
    assert result == {"exit_code": 0, "outputs": [str(out)], "failed": []}
    services.stdout = io.StringIO()
    assert run_ocr([str(doc), "/out", str(out), "/quiet"], services) == EXIT_OK
    assert services.stdout.getvalue() == ""


def test_T_U050_discovery(services):
    for option in ("/version", "/help", "/listlangs", "/listformats"):
        services.stdout = io.StringIO()
        assert run_ocr([option], services) == EXIT_OK
        assert services.stdout.getvalue()
    services.stdout = io.StringIO()
    run_ocr(["/listlangs"], services)
    assert "ron" in services.stdout.getvalue() and "Romanian" in services.stdout.getvalue()


def test_T_U051_exit_codes(services, doc, tmp_path):
    import pikepdf

    assert run_ocr([str(doc), "/nimic"], services) == EXIT_USAGE  # 1
    assert run_ocr([str(tmp_path / "lipsa.png")], services) == EXIT_FILE  # 2
    locked = text_pdf(tmp_path / "parola.pdf", [["secret"]])
    with pikepdf.open(locked, allow_overwriting_input=True) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(owner="o", user="u"))
    assert run_ocr([str(locked), "/password", "gresit"], services) == EXIT_FILE  # 2
    assert exit_code_for(RecognitionFailedError("x")) == EXIT_RECOGNITION  # 3
    assert exit_code_for(NoWritePermissionError("x")) == EXIT_WRITE  # 4
    assert exit_code_for(KeyboardInterrupt()) == EXIT_CANCELLED  # 5

    class FailingEngine(ScriptEngine):
        def recognize_area(self, page, area, settings, cancel=None):
            raise RecognitionFailedError("motorul a cazut", page_number=page.page_number)
    services.engine = FailingEngine()
    assert run_ocr([str(doc), "/out", str(tmp_path / "e.txt")], services) == EXIT_RECOGNITION

    class Cancelling(ScriptEngine):
        def recognize_area(self, page, area, settings, cancel=None):
            raise KeyboardInterrupt
    services.engine = Cancelling()
    assert run_ocr([str(doc), "/out", str(tmp_path / "c.txt")], services) == EXIT_CANCELLED


def test_T_U051_write_error(services, doc, tmp_path):
    blocker = tmp_path / "fisier"
    blocker.write_text("x", encoding="utf-8")
    assert run_ocr([str(doc), "/out", str(blocker / "sub" / "a.pdf")], services) == EXIT_WRITE


# --- compararea (U-020…U-028) ---

@pytest.fixture
def pair(tmp_path):
    left = text_pdf(tmp_path / "Document1.pdf", [["Termenul este 30 zile", "Pret 10 lei"]])
    right = text_pdf(tmp_path / "Document2.pdf", [["Termenul este 45 zile", "Pret 10 lei."]])
    return left, right


def test_T_U020_colon_syntax(services, pair, tmp_path):
    left, right = pair
    out = tmp_path / "out.docx"
    argv = ["/compare", f"/file1:{left}", f"/file2:{right}", "/lang:Romanian",
            "/recMode:AutoChoose", "/options:IgnorePunctDiff,UngroupDiff",
            f"/saveFile:{out}", "/saveMode:Word"]
    assert run_compare(argv, services) == EXIT_OK and out.exists()
    # sintaxa cu spatii, de la conversie, nu functioneaza aici
    assert run_compare(["/compare", "/file1", str(left), "/file2", str(right)],
                       services) == EXIT_USAGE
    assert run_compare([f"/file1:{left}", f"/file2:{right}"], services) == EXIT_USAGE


def test_T_U021_U022_both_files_required(services, pair):
    assert run_compare(["/compare", f"/file1:{pair[0]}"], services) == EXIT_USAGE
    assert run_compare(["/compare", f"/file1:{pair[0]}", "/file2:lipsa.pdf"],
                       services) == EXIT_FILE


def test_T_U023_compare_language(services, pair):
    left, right = pair
    assert run_compare(["/compare", f"/file1:{left}", f"/file2:{right}", "/lang:French"],
                       services) == EXIT_OK
    assert run_compare(["/compare", f"/file1:{left}", f"/file2:{right}", "/lang:Klingon"],
                       services) == EXIT_USAGE


def test_T_U024_default_rec_mode(pair):
    assert parse_compare(["/compare", f"/file1:{pair[0]}", f"/file2:{pair[1]}"]).rec_mode == \
        "text"  # UseOnlyPdfText
    assert parse_compare(["/compare", f"/file1:{pair[0]}", f"/file2:{pair[1]}",
                          "/recMode:UseOnlyOCR"]).rec_mode == "ocr"


def test_T_U025_options_change_the_result(services, pair):
    left, right = pair
    base = ["/compare", f"/file1:{left}", f"/file2:{right}"]
    run_compare(base, services)
    with_punct = services.stdout.getvalue()
    services.stdout = io.StringIO()
    run_compare([*base, "/options:IgnorePunctDiff"], services)
    without = services.stdout.getvalue()
    assert with_punct != without  # punctul din „lei.” conteaza numai fara optiune
    assert run_compare([*base, "/options:IgnorePunctDiff, UngroupDiff"],
                       services) == EXIT_USAGE  # fara spatii


def test_T_U026_U027_save_modes(services, pair, tmp_path):
    import pikepdf

    left, right = pair
    base = ["/compare", f"/file1:{left}", f"/file2:{right}"]
    for mode in ("PdfDocument1", "PdfDocument2"):
        out = tmp_path / f"{mode}.pdf"
        assert run_compare([*base, f"/saveFile:{out}", f"/saveMode:{mode}"],
                           services) == EXIT_OK
        with pikepdf.open(out) as pdf:
            assert any("/Annots" in page.obj for page in pdf.pages)
    assert run_compare([*base, f"/saveFile:{tmp_path / 'a.docx'}", "/saveMode:PdfDocument1"],
                       services) == EXIT_USAGE
    assert run_compare([*base, f"/saveFile:{tmp_path / 'a.txt'}"], services) == EXIT_USAGE


def test_T_U028_official_example(services, pair):
    left, right = pair
    assert run_compare(["/compare", f"/file1:{left}", f"/file2:{right}", "/lang:French",
                        "/recMode:AutoChoose", "/options:IgnorePunctDiff,UngroupDiff"],
                       services) == EXIT_OK
    assert cli.tr("cli.compare.found", count=1) in services.stdout.getvalue()


def test_module_entry_dispatch(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "run_ocr", lambda args: seen.append(("ocr", args)) or 0)
    monkeypatch.setattr(cli, "run_compare", lambda args: seen.append(("cmp", args)) or 0)
    cli.main(["ocr", "a.pdf"])
    cli.main(["/compare", "/file1:a"])
    cli.main(["x.pdf"], program="compare")
    assert seen == [("ocr", ["a.pdf"]), ("cmp", ["/compare", "/file1:a"]),
                    ("cmp", ["x.pdf"])]


def test_T_U001_U020_packaged_console_executables():
    """14.3: cele doua executabile de consola sunt in pachetul Windows, cu numele
    din faza_14_pasi.md (decizia 1), si sunt probate la construire."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = (root / "packaging" / "doculens.spec").read_text(encoding="utf-8")
    assert '("cli_ocr.py", "DocuLensOCR")' in spec
    assert '("cli_compare.py", "DocuLensCompare")' in spec and "console=True" in spec
    for kind in ("ocr", "compare"):
        launcher = (root / "packaging" / f"cli_{kind}.py").read_text(encoding="utf-8")
        assert f"{kind}_entry" in launcher and "_use_bundled_tesseract" in launcher
    build = (root / "packaging" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "DocuLensOCR" in build and "/version" in build
