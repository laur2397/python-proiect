"""Linia de comanda (faza 14): doua executabile cu doua sintaxe (U-001, U-020).

- Conversia (`DocuLensOCR`, faza_14_pasi.md decizia 1), parametri separati prin
  spatiu: `DocuLensOCR <surse> /lang <limbi> /send <aplicatie> /out <fisier>
  /report <fisier>` (U-001…U-013), plus extinderile proprii (U-040…U-050),
  grupate separat in `/help` (U-012, decizia 2).
- Compararea (`DocuLensCompare`), sintaxa cu doua puncte: `DocuLensCompare
  /compare /file1:<cale> /file2:<cale> /lang:<limba> /recMode:<mod>
  /options:<lista> /saveFile:<cale> /saveMode:<mod>` (U-020…U-028).

Codurile de iesire (U-051): 0 succes, 1 parametri gresiti, 2 eroare de fisier sau
parola, 3 eroare de recunoastere, 4 eroare de scriere, 5 anulat.

Textele vin din fisierele de traducere (decizia 10). Deschiderea fisierelor si
clipboard-ul sunt functii date din afara, ca testele sa le poata inlocui.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from app.core.errors import (
    CoreError,
    DiskFullError,
    FileCorruptError,
    FileLockedError,
    LanguageModelMissingError,
    NoTextFoundError,
    NoWritePermissionError,
    OperationCancelledError,
    PasswordRequiredError,
    RecognitionFailedError,
    UnsupportedFormatError,
    WrongPasswordError,
)
from app.core.model import ExportFormat, LayoutMode, PdfAVersion, Progress
from app.gui import i18n

EXIT_OK, EXIT_USAGE, EXIT_FILE, EXIT_RECOGNITION, EXIT_WRITE, EXIT_CANCELLED = range(6)
"""U-051."""

OCR_PROGRAM = "DocuLensOCR"
COMPARE_PROGRAM = "DocuLensCompare"

ORIGINAL_OPTIONS = ("/scan", "/lang", "/send", "/out", "/report")
"""U-001…U-008: parametrii originalului."""

EXTENSION_OPTIONS = ("/indir", "/outdir", "/pattern", "/recursive", "/pages", "/layout",
                     "/pdfa", "/mrc", "/password", "/threads", "/json", "/quiet",
                     "/listlangs", "/listformats", "/version", "/help")
"""U-040…U-050 (si `/password`, decizia 7): extinderile DocuLens."""

REFUSED_OPTIONS = ("/format", "/dpi", "/split", "/merge", "/config")
"""U-012: nu exista in original si nu au extindere definita (decizia 2)."""

SEND_TARGETS: dict[str, ExportFormat] = {
    "MSWord": ExportFormat.DOCX, "MSExcel": ExportFormat.XLSX,
    "OpenOffice": ExportFormat.ODT, "Mail": ExportFormat.DOCX,
    "Clipboard": ExportFormat.TXT, "WebBrowser": ExportFormat.HTML,
    "PDFViewer": ExportFormat.PDF, "PowerPoint": ExportFormat.PPTX,
}
"""U-006: exact aceste 8 valori (decizia 3)."""

EXTENSIONS: dict[str, ExportFormat] = {
    ".pdf": ExportFormat.PDF, ".docx": ExportFormat.DOCX, ".rtf": ExportFormat.RTF,
    ".odt": ExportFormat.ODT, ".xlsx": ExportFormat.XLSX, ".csv": ExportFormat.CSV,
    ".pptx": ExportFormat.PPTX, ".txt": ExportFormat.TXT, ".html": ExportFormat.HTML,
    ".htm": ExportFormat.HTML, ".epub": ExportFormat.EPUB, ".fb2": ExportFormat.FB2,
    ".djvu": ExportFormat.DJVU,
}
"""U-007: extensia din `/out` decide formatul."""

PDFA_VERSIONS = {v.value: v for v in PdfAVersion}
"""U-045: `1a`, `1b`, `2a`, `2b`, `2u`, `3a`, `3b`, `3u`."""

REC_MODES = {"useonlypdftext": "text", "autochoose": "auto", "useonlyocr": "ocr"}
"""U-024: `UseOnlyPdfText` / `AutoChoose` / `UseOnlyOCR`."""

COMPARE_OPTIONS = ("noheadersfooters", "ignorepunctdiff", "ignoreoneletterdiff",
                   "ungroupdiff")
"""U-025."""

SAVE_MODES = ("pdfdocument1", "pdfdocument2", "word")
"""U-027."""


def tr(key: str, **params: Any) -> str:
    return i18n.tr(key, **params)


class UsageError(Exception):
    """Parametri gresiti: codul 1 (U-051). `key` e cheia mesajului."""

    def __init__(self, key: str, **params: Any) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


# --- serviciile sistemului (inlocuibile in teste) -----------------------------------------

def open_with_default(path: Path) -> None:
    """Deschide fisierul (sau o adresa) cu aplicatia implicita a sistemului (U-009)."""
    target = str(path)
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def copy_to_clipboard(text: str) -> None:
    """U-006 `Clipboard`: textul ajunge in clipboard-ul sistemului."""
    if sys.platform.startswith("win"):
        command, data = ["clip"], text.encode("utf-16-le")
    elif sys.platform == "darwin":
        command, data = ["pbcopy"], text.encode("utf-8")
    else:
        tool = shutil.which("wl-copy") or shutil.which("xclip")
        if tool is None:
            raise OSError("nu exista un program de clipboard (wl-copy sau xclip)")
        command = [tool] if tool.endswith("wl-copy") else [tool, "-selection", "clipboard"]
        data = text.encode("utf-8")
    subprocess.run(command, input=data, check=True)


def interactive_session() -> bool:
    """U-013: pe Windows, sesiunea 0 e a serviciilor (niciun utilizator conectat)."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes

        session = ctypes.c_ulong()
        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        ok = kernel.ProcessIdToSessionId(kernel.GetCurrentProcessId(), ctypes.byref(session))
        return not ok or session.value != 0
    except (OSError, AttributeError):
        return True


@dataclass
class Services:
    """Ce vine din afara nucleului: contextul, motorul OCR, scanerul, sistemul."""

    context: Any = None
    engine: Any = None
    scanner: Any = None
    opener: Callable[[Path], None] = open_with_default
    clipboard: Callable[[str], None] = copy_to_clipboard
    interactive: Callable[[], bool] = interactive_session
    stdout: TextIO | None = None
    stderr: TextIO | None = None


# --- limbile (U-004, U-005, U-023) ----------------------------------------------------------

def _language_names() -> dict[str, str]:
    """Numele limbilor (englezesc, romanesc) → cod (decizia 4)."""
    names: dict[str, str] = {}
    for lang in ("en", "ro"):
        for key, text in i18n.catalog(lang).items():
            if key.startswith("language.") and key.count(".") == 1:
                names.setdefault(str(text).lower(), key[len("language."):])
    return names


def resolve_languages(tokens: Sequence[str], context: Any,
                      allowed: Sequence[str] | None = None) -> list[str]:
    """Numele date → coduri. `@@Nume` = limba proprie (U-005, decizia 5)."""
    from app.core.ocr.languages import LanguageRegistry

    registry = LanguageRegistry(con=context.app_db)
    catalog = set(registry.all())
    user = {code.split(":", 1)[-1].lower(): code for code in registry.user_languages()}
    names = _language_names()
    codes: list[str] = []
    for token in tokens:
        if token.startswith("@@"):
            name = token[2:]
            if not name or not name.isalnum():
                raise UsageError("cli.error.user_language_name", name=token)
            if name.lower() not in user:
                raise UsageError("cli.error.unknown_language", name=token)
            code = user[name.lower()]
        else:
            low = token.lower()
            code = low if low in catalog else names.get(low, "")
            if not code or code not in catalog:
                raise UsageError("cli.error.unknown_language", name=token)
        if allowed is not None and code not in allowed:
            raise UsageError("cli.error.compare_language", name=token)
        if code not in codes:
            codes.append(code)
    return codes


# --- conversia: analiza parametrilor (U-001…U-013, U-040…U-050) -----------------------------

@dataclass
class OcrCommand:
    sources: list[Path] = field(default_factory=list)
    scan: bool = False
    scan_source: str | None = None
    languages: list[str] = field(default_factory=list)
    send: str | None = None
    out: Path | None = None
    report: Path | None = None
    indir: Path | None = None
    outdir: Path | None = None
    pattern: str = "*"
    recursive: bool = False
    pages: tuple[int, ...] | None = None
    layout: LayoutMode | None = None
    pdfa: PdfAVersion | None = None
    mrc: bool = False
    password: str | None = None
    threads: int | None = None
    json: bool = False
    quiet: bool = False
    info: str | None = None
    """`/listlangs`, `/listformats`, `/version`, `/help` (U-050)."""


def _is_option(token: str) -> bool:
    """`/nume`: o bara la inceput si niciuna dupa (caile absolute au mai multe)."""
    return token.startswith("/") and len(token) > 1 and "/" not in token[1:] and \
        "\\" not in token and "." not in token


def parse_pages(text: str) -> tuple[int, ...]:
    """U-043: `1-5,8`."""
    pages: list[int] = []
    for part in text.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not match:
            raise UsageError("cli.error.pages", value=text)
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first < 1 or last < first:
            raise UsageError("cli.error.pages", value=text)
        pages += [p for p in range(first, last + 1) if p not in pages]
    return tuple(pages)


def parse_ocr(argv: Sequence[str]) -> OcrCommand:
    cmd = OcrCommand()
    args = list(argv)
    i = 0

    def value(option: str) -> str:
        nonlocal i
        if i + 1 >= len(args) or _is_option(args[i + 1]):
            raise UsageError("cli.error.missing_value", option=option)
        i += 1
        return args[i]

    def free_word(index: int) -> bool:
        """Un cuvant dupa `/lang` sau `/scan` care nu e parametru si nu e fisier."""
        return index < len(args) and not _is_option(args[index]) and \
            not Path(args[index]).exists()

    while i < len(args):
        token = args[i]
        if not _is_option(token):
            cmd.sources.append(Path(token))  # U-002
            i += 1
            continue
        option = token.lower()
        if option in REFUSED_OPTIONS:
            raise UsageError("cli.error.not_supported", option=token)
        if option == "/scan":  # U-003
            cmd.scan = True
            if free_word(i + 1):
                i += 1
                cmd.scan_source = args[i]
        elif option == "/lang":  # U-004
            start = i
            while free_word(i + 1):
                i += 1
                cmd.languages.append(args[i])
            if i == start:
                raise UsageError("cli.error.missing_value", option=token)
        elif option == "/send":  # U-006
            target = value(token)
            match = next((t for t in SEND_TARGETS if t.lower() == target.lower()), None)
            if match is None:
                raise UsageError("cli.error.send_target", target=target,
                                 targets=", ".join(SEND_TARGETS))
            cmd.send = match
        elif option == "/out":  # U-007
            cmd.out = Path(value(token))
        elif option == "/report":  # U-008
            cmd.report = Path(value(token))
        elif option == "/indir":  # U-040
            cmd.indir = Path(value(token))
        elif option == "/outdir":
            cmd.outdir = Path(value(token))
        elif option == "/pattern":  # U-041
            cmd.pattern = value(token)
        elif option == "/recursive":  # U-042
            cmd.recursive = True
        elif option == "/pages":  # U-043
            cmd.pages = parse_pages(value(token))
        elif option == "/layout":  # U-044
            text = value(token).lower()
            try:
                cmd.layout = LayoutMode(text)
            except ValueError:
                raise UsageError("cli.error.layout", value=text) from None
        elif option == "/pdfa":  # U-045
            text = value(token).lower()
            if text not in PDFA_VERSIONS:
                raise UsageError("cli.error.pdfa", value=text,
                                 values=", ".join(PDFA_VERSIONS))
            cmd.pdfa = PDFA_VERSIONS[text]
        elif option == "/mrc":  # U-046
            cmd.mrc = True
        elif option == "/password":
            cmd.password = value(token)
        elif option == "/threads":  # U-047
            text = value(token)
            cores = os.cpu_count() or 1
            if not text.isdigit() or not 1 <= int(text) <= cores:
                raise UsageError("cli.error.threads", value=text, cores=cores)
            cmd.threads = int(text)
        elif option == "/json":  # U-048
            cmd.json = True
        elif option == "/quiet":  # U-049
            cmd.quiet = True
        elif option in ("/listlangs", "/listformats", "/version", "/help"):  # U-050
            cmd.info = option[1:]
        else:
            raise UsageError("cli.error.unknown_option", option=token)
        i += 1
    _check_ocr(cmd)
    return cmd


def _check_ocr(cmd: OcrCommand) -> None:
    if cmd.info:
        return
    if cmd.indir is not None or cmd.outdir is not None:
        if cmd.indir is None or cmd.outdir is None:
            raise UsageError("cli.error.indir_outdir")
        if cmd.sources or cmd.scan or cmd.out is not None:
            raise UsageError("cli.error.indir_with_sources")
    elif not cmd.sources and not cmd.scan:
        raise UsageError("cli.error.no_source")
    if cmd.scan and cmd.sources:
        raise UsageError("cli.error.scan_with_files")
    if cmd.pdfa is not None and cmd.password is not None:  # U-045
        raise UsageError("cli.error.pdfa_password")
    if cmd.out is not None and cmd.out.suffix.lower() not in EXTENSIONS:
        raise UsageError("cli.error.out_extension", ext=cmd.out.suffix or "-",
                         values=", ".join(sorted(EXTENSIONS)))
    if cmd.pattern != "*" and cmd.indir is None:
        raise UsageError("cli.error.needs_indir", option="/pattern")
    if cmd.recursive and cmd.indir is None:
        raise UsageError("cli.error.needs_indir", option="/recursive")


def _target(cmd: OcrCommand) -> ExportFormat:
    if cmd.out is not None:
        return EXTENSIONS[cmd.out.suffix.lower()]
    if cmd.send is not None:
        return SEND_TARGETS[cmd.send]
    return ExportFormat.PDF  # U-009: se deschide, salvarea ramane manuala


# --- codurile de iesire (U-051) ---------------------------------------------------------------

def exit_code_for(error: BaseException) -> int:
    if isinstance(error, (OperationCancelledError, KeyboardInterrupt)):
        return EXIT_CANCELLED
    if isinstance(error, (RecognitionFailedError, LanguageModelMissingError,
                          NoTextFoundError)):
        return EXIT_RECOGNITION
    if isinstance(error, (NoWritePermissionError, DiskFullError, PermissionError)):
        return EXIT_WRITE
    if isinstance(error, (WrongPasswordError, PasswordRequiredError, UnsupportedFormatError,
                          FileCorruptError, FileLockedError, FileNotFoundError)):
        return EXIT_FILE
    return EXIT_FILE


def _message(error: BaseException) -> str:
    if isinstance(error, FileNotFoundError):
        return tr("cli.error.file_not_found", file=str(error))
    if isinstance(error, CoreError):
        return i18n.tr_error(error)
    return str(error) or type(error).__name__


# --- conversia: rularea -------------------------------------------------------------------------

class _Output:
    def __init__(self, services: Services, *, quiet: bool) -> None:
        self.out = services.stdout or sys.stdout
        self.err = services.stderr or sys.stderr
        self.quiet = quiet

    def say(self, text: str) -> None:
        if not self.quiet:
            print(text, file=self.out)

    def error(self, text: str) -> None:
        print(text, file=self.err)


def help_text(program: str) -> str:
    """U-050, U-012: parametrii originalului si extinderile, in liste separate."""
    if program == COMPARE_PROGRAM:
        return tr("cli.help.compare", program=program)
    lines = [tr("cli.help.usage", program=program), "", tr("cli.help.original")]
    lines += [f"  {tr(f'cli.help.option.{o[1:]}')}" for o in ORIGINAL_OPTIONS]
    lines += ["", tr("cli.help.extensions")]
    lines += [f"  {tr(f'cli.help.option.{o[1:]}')}" for o in EXTENSION_OPTIONS]
    lines += ["", tr("cli.help.exit_codes")]
    return "\n".join(lines)


def _info(cmd: OcrCommand, out: _Output, context: Any) -> int:
    from app.core.context import APP_VERSION

    if cmd.info == "version":
        out.say(tr("cli.version", program=OCR_PROGRAM, version=APP_VERSION))
    elif cmd.info == "help":
        out.say(help_text(OCR_PROGRAM))
    elif cmd.info == "listformats":
        for ext, fmt in EXTENSIONS.items():
            out.say(f"{ext:7} {tr(f'format.{fmt.value}')}")
    else:  # listlangs
        from app.core.ocr.languages import LanguageRegistry

        en = i18n.catalog("en")
        for code in LanguageRegistry(con=context.app_db).all():
            out.say(f"{code:14} {en.get(f'language.{code}', code)}")
    return EXIT_OK


def _collect(cmd: OcrCommand, services: Services, context: Any) -> list[Path]:
    """Sursele: fisierele (U-002), folderul (U-040…U-042) sau scanerul (U-003)."""
    if cmd.indir is not None:
        if not cmd.indir.is_dir():
            raise FileNotFoundError(str(cmd.indir))
        walker = cmd.indir.rglob(cmd.pattern) if cmd.recursive else cmd.indir.glob(cmd.pattern)
        return sorted(p for p in walker if p.is_file())
    if cmd.scan:
        return _scan(cmd, services, context)
    missing = [p for p in cmd.sources if not p.exists()]
    if missing:
        raise FileNotFoundError(str(missing[0]))
    return list(cmd.sources)


def _scan(cmd: OcrCommand, services: Services, context: Any) -> list[Path]:
    """U-003: scanerul numit; fara nume, ultimul scaner folosit (decizia 6)."""
    from app.core.errors import NoScannerError
    from app.core.images.scanner import ScanSession, ScanSettings

    service = services.scanner
    if service is None:
        from app.core.images.wia import default_scanner

        service = default_scanner()
    session = ScanSession(service)
    devices = session.devices()
    if not devices:
        raise NoScannerError("niciun scaner")
    wanted = (cmd.scan_source or context.settings.get("general.capture_device") or "").lower()
    device = next((d for d in devices if wanted and wanted in (d[0].lower(), d[1].lower())),
                  None)
    if device is None:
        if cmd.scan_source:
            raise NoScannerError("scanerul nu exista", name=cmd.scan_source)
        device = devices[0]
    context.settings.set("general.capture_device", device[0])
    images, _warnings = session.acquire(ScanSettings(device_id=device[0]))
    return [Path(image.path) for image in images]


def run_ocr(argv: Sequence[str], services: Services | None = None) -> int:
    """Conversia (U-001…U-013, U-040…U-051). Intoarce codul de iesire."""
    services = services or Services()
    err = services.stderr or sys.stderr
    try:
        cmd = parse_ocr(argv)
    except UsageError as exc:
        print(tr(exc.key, **exc.params), file=err)
        print(tr("cli.see_help", program=OCR_PROGRAM), file=err)
        return EXIT_USAGE
    out = _Output(services, quiet=cmd.quiet or cmd.json)
    if not services.interactive():  # U-013
        out.error(tr("cli.error.no_session"))
        return EXIT_USAGE
    own = services.context is None
    if own:
        from app.core.context import AppContext

        services.context = AppContext.start()
    context = services.context
    try:
        if cmd.info:
            return _info(cmd, out, context)
        return _convert(cmd, out, services, context)
    finally:
        if own:
            context.close()
            services.context = None


def _convert(cmd: OcrCommand, out: _Output, services: Services, context: Any) -> int:
    from app.core.convert import ConvertJob, ConvertSettings

    report: list[str] = []
    result: dict[str, Any] = {"exit_code": EXIT_OK, "outputs": [], "failed": []}
    try:
        languages = resolve_languages(
            cmd.languages or list(context.settings.get("lang.manual") or ["ron"]), context)
    except UsageError as exc:
        out.error(tr(exc.key, **exc.params))
        return EXIT_USAGE
    target = _target(cmd)
    settings = ConvertSettings(target=target, layout_mode=cmd.layout,
                               languages=tuple(languages), pdfa=cmd.pdfa is not None,
                               use_mrc=cmd.mrc, pages=cmd.pages, threads=cmd.threads)
    if cmd.pdfa is not None:
        if target is not ExportFormat.PDF:
            out.error(tr("cli.error.pdfa_needs_pdf"))
            return EXIT_USAGE
        settings.pdfa_version = cmd.pdfa
    try:
        settings.validate()  # U-044: matricea Q-001
    except ValueError as exc:
        out.error(tr("cli.error.layout_format", detail=str(exc)))
        return EXIT_USAGE
    if cmd.languages:  # decizia 4: limbile devin „ultimele folosite”
        context.settings.set("lang.manual", languages)
    code = EXIT_OK
    try:
        files = _collect(cmd, services, context)
        if not files:
            raise FileNotFoundError(str(cmd.indir or ""))
        password = _password_once(cmd.password) if cmd.password is not None else None
        report.append(tr("cli.report.start", files=len(files), format=target.value,
                         languages=", ".join(languages)))

        def progress(step: Progress) -> None:
            out.say(tr("cli.progress", current=step.current, total=step.total,
                       file=step.detail or ""))

        groups = [[f] for f in files] if cmd.indir is not None else [files]  # U-040
        for group in groups:
            settings.combine = len(group) > 1
            job = ConvertJob(group, settings, context=context, engine=services.engine,
                             password=password)
            with tempfile.TemporaryDirectory(prefix="doculens-cli-") as tmp:
                done = job.run(Path(tmp), cmd.out.stem if cmd.out else group[0].stem,
                               progress=progress)
                if done.cancelled:
                    raise OperationCancelledError("anulat")
                for path, error in done.failed:
                    result["failed"].append({"file": str(path), "error": _message(error)})
                    report.append(tr("cli.report.failed", file=str(path),
                                     error=_message(error)))
                    code = max(code, exit_code_for(error))
                placed = _place(cmd, group, done.written)
                result["outputs"] += [str(p) for p in placed]
                report += [tr("cli.report.written", file=str(p)) for p in placed]
        if result["outputs"] and cmd.out is None and cmd.indir is None:
            _deliver(cmd, [Path(p) for p in result["outputs"]], services)
    except KeyboardInterrupt as exc:
        code = exit_code_for(exc)
    except (CoreError, OSError, ValueError) as exc:
        code = exit_code_for(exc)
        out.error(_message(exc))
        report.append(tr("cli.report.error", error=_message(exc)))
    if code == EXIT_OK and not result["outputs"]:
        code = EXIT_FILE
    report.append(tr("cli.report.end", code=code))
    if cmd.report is not None:  # U-008
        try:
            cmd.report.parent.mkdir(parents=True, exist_ok=True)
            cmd.report.write_text("\n".join(report) + "\n", encoding="utf-8")
        except OSError as exc:
            out.error(_message(exc))
            code = max(code, EXIT_WRITE)
    result["exit_code"] = code
    if cmd.json:  # U-048
        print(json.dumps(result, ensure_ascii=False), file=services.stdout or sys.stdout)
    else:
        for path in result["outputs"]:
            out.say(tr("cli.written", file=path))
        for item in result["failed"]:
            out.error(tr("cli.failed", file=item["file"], error=item["error"]))
    return code


def _password_once(password: str) -> Callable[[str], str | None]:
    """U-045: parola se incearca o singura data pe fisier; a doua cerere inseamna
    parola gresita (codul 2), nu o bucla."""
    asked: set[str] = set()

    def give(path: str) -> str | None:
        if path in asked:
            return None
        asked.add(path)
        return password
    return give


def _place(cmd: OcrCommand, group: list[Path], written: list[Path]) -> list[Path]:
    """Fisierele scrise ajung la destinatie: `/out` (un fisier existent se
    inlocuieste, U-007), `/outdir` (U-040) sau un folder temporar pentru `/send` si
    pentru deschiderea fara `/out` (U-009)."""
    if not written:
        return []
    if cmd.out is not None:
        folder, stem = cmd.out.parent, cmd.out.stem
    elif cmd.outdir is not None:
        folder, stem = cmd.outdir, group[0].stem
    else:
        folder, stem = Path(tempfile.mkdtemp(prefix="doculens-")), group[0].stem
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise NoWritePermissionError("folderul nu se poate scrie", path=str(folder)) from exc
    placed: list[Path] = []
    for path in written:
        name = f"{stem}{path.suffix}" if len(written) == 1 else path.name
        destination = folder / name
        try:
            if destination.is_dir():
                shutil.rmtree(destination)
            shutil.move(str(path), str(destination))  # U-007: se inlocuieste
        except OSError as exc:
            raise NoWritePermissionError("fisierul nu se poate scrie",
                                         path=str(destination)) from exc
        placed.append(destination)
    return placed


def _deliver(cmd: OcrCommand, files: list[Path], services: Services) -> None:
    """U-006, U-009: rezultatul ajunge in aplicatia aleasa (decizia 3)."""
    if cmd.send == "Clipboard":
        services.clipboard("\n".join(p.read_text(encoding="utf-8", errors="replace")
                                     for p in files if p.suffix == ".txt"))
        return
    if cmd.send == "Mail":
        services.opener(Path("mailto:"))
        services.opener(files[0].parent)
        return
    services.opener(files[0])


# --- compararea (U-020…U-028) ---------------------------------------------------------------

@dataclass
class CompareCommand:
    file1: Path | None = None
    file2: Path | None = None
    language: str | None = None
    rec_mode: str = "text"
    """U-024: `UseOnlyPdfText` cand parametrul lipseste."""
    options: tuple[str, ...] = ()
    save_file: Path | None = None
    save_mode: str | None = None
    info: str | None = None


def parse_compare(argv: Sequence[str]) -> CompareCommand:
    """U-020: `/compare` primul; apoi numai parametri `/nume:valoare`."""
    args = list(argv)
    cmd = CompareCommand()
    if args and args[0].lower() in ("/help", "/version"):
        cmd.info = args[0].lower()[1:]
        return cmd
    if not args or args[0].lower() != "/compare":
        raise UsageError("cli.error.compare_first")
    for token in args[1:]:
        name, sep, value = token.partition(":")
        if not name.startswith("/") or not sep:  # sintaxa cu spatii nu merge aici
            raise UsageError("cli.error.colon_syntax", token=token)
        key = name[1:].lower()
        if key in ("file1", "file2"):  # U-021, U-022
            setattr(cmd, key, Path(value))
        elif key == "lang":  # U-023
            cmd.language = value
        elif key == "recmode":  # U-024
            if value.lower() not in REC_MODES:
                raise UsageError("cli.error.rec_mode", value=value)
            cmd.rec_mode = REC_MODES[value.lower()]
        elif key == "options":  # U-025: separate prin virgula, fara spatii
            items = tuple(v.lower() for v in value.split(","))
            if not value or any(v not in COMPARE_OPTIONS for v in items):
                raise UsageError("cli.error.compare_option", value=value)
            cmd.options = items
        elif key == "savefile":  # U-026
            path = Path(value)
            if path.suffix.lower() not in (".pdf", ".docx"):
                raise UsageError("cli.error.save_file", value=value)
            cmd.save_file = path
        elif key == "savemode":  # U-027
            if value.lower() not in SAVE_MODES:
                raise UsageError("cli.error.save_mode", value=value)
            cmd.save_mode = value.lower()
        else:
            raise UsageError("cli.error.unknown_option", option=name)
    if cmd.file1 is None or cmd.file2 is None:
        raise UsageError("cli.error.files_required")
    if cmd.save_mode is not None and cmd.save_file is None:
        raise UsageError("cli.error.save_mode_without_file")
    if cmd.save_file is not None:
        word = cmd.save_file.suffix.lower() == ".docx"
        mode = cmd.save_mode or ("word" if word else "pdfdocument2")
        if (mode == "word") != word:
            raise UsageError("cli.error.save_mode_extension", mode=mode,
                             ext=cmd.save_file.suffix)
        cmd.save_mode = mode
    return cmd


def run_compare(argv: Sequence[str], services: Services | None = None) -> int:
    """Compararea (U-020…U-028). Intoarce codul de iesire (U-051)."""
    from app.core.compare.engine import DocumentComparer
    from app.core.compare.sources import COMPARE_LANGUAGES
    from app.core.model import CompareOptions

    services = services or Services()
    out = _Output(services, quiet=False)
    try:
        cmd = parse_compare(argv)
    except UsageError as exc:
        out.error(tr(exc.key, **exc.params))
        out.error(tr("cli.see_help", program=COMPARE_PROGRAM))
        return EXIT_USAGE
    if cmd.info == "help":
        out.say(help_text(COMPARE_PROGRAM))
        return EXIT_OK
    if cmd.info == "version":
        from app.core.context import APP_VERSION

        out.say(tr("cli.version", program=COMPARE_PROGRAM, version=APP_VERSION))
        return EXIT_OK
    if not services.interactive():  # U-013
        out.error(tr("cli.error.no_session"))
        return EXIT_USAGE
    own = services.context is None
    if own:
        from app.core.context import AppContext

        services.context = AppContext.start()
    context = services.context
    try:
        try:
            languages = resolve_languages([cmd.language], context, COMPARE_LANGUAGES) \
                if cmd.language else ["ron", "eng"]
        except UsageError as exc:
            out.error(tr(exc.key, **exc.params))
            return EXIT_USAGE
        options = CompareOptions(  # decizia 9
            languages=tuple(languages), pdf_mode=cmd.rec_mode,
            find_punctuation="ignorepunctdiff" not in cmd.options,
            find_one_letter="ignoreoneletterdiff" not in cmd.options,
            find_headers_footers="noheadersfooters" not in cmd.options,
            group_distance_words=0 if "ungroupdiff" in cmd.options else 3)
        comparer = DocumentComparer(context=context, engine=services.engine, texts=tr)
        try:
            for path in (cmd.file1, cmd.file2):
                if path is None or not path.exists():
                    raise FileNotFoundError(str(path))
            assert cmd.file1 is not None and cmd.file2 is not None
            differences = comparer.compare(cmd.file1, cmd.file2, options)
            out.say(tr("cli.compare.found", count=len(differences)))
            if cmd.save_file is not None:
                _save_comparison(comparer, cmd, differences)
                out.say(tr("cli.written", file=str(cmd.save_file)))
        except KeyboardInterrupt as exc:
            return exit_code_for(exc)
        except (CoreError, OSError, ValueError) as exc:
            out.error(_message(exc))
            return exit_code_for(exc)
        return EXIT_OK
    finally:
        if own:
            context.close()
            services.context = None


def _save_comparison(comparer: Any, cmd: CompareCommand, differences: list[Any]) -> None:
    """U-026, U-027: `PdfDocument1` / `PdfDocument2` = comentarii pe documentul 1 / 2,
    `Word` = tabelul de diferente."""
    assert cmd.save_file is not None and cmd.file1 is not None and cmd.file2 is not None
    target = cmd.save_file
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
    except OSError as exc:
        raise NoWritePermissionError("fisierul nu se poate scrie", path=str(target)) from exc
    if cmd.save_mode == "word":
        comparer.save_as_word_table(differences, target, left=cmd.file1, right=cmd.file2)
    elif cmd.save_mode == "pdfdocument1":
        comparer.save_as_pdf_with_comments(cmd.file1, differences, target, side=1)
    else:
        comparer.save_as_pdf_with_comments(cmd.file2, differences, target, side=2)


# --- intrarea -------------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None, *, program: str | None = None) -> int:
    """`python -m app.cli ocr|compare ...`; executabilele dau `program` direct."""
    args = list(sys.argv[1:] if argv is None else argv)
    name = (program or "").lower()
    if not name:
        if args and args[0].lower() in ("ocr", "compare"):
            name = args.pop(0).lower()
        else:
            name = "compare" if args[:1] and args[0].lower() == "/compare" else "ocr"
    if platform.system() == "Windows":  # textele cu diacritice in consola
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
    return run_compare(args) if name == "compare" else run_ocr(args)


def ocr_entry() -> int:
    return main(program="ocr")


def compare_entry() -> int:
    return main(program="compare")
