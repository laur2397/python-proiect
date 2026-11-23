"""Integrarea cu sistemul de operare (faza 15): pornirea la logare (V-021) si,
in pasul 15.3, meniul contextual Explorer si asocierile de fisiere (W-*).

Scrierile in registrul Windows trec printr-un `Registry` (protocol), ca regulile
sa se poata verifica pe orice sistem: `WindowsRegistry` scrie in
`HKEY_CURRENT_USER` (per utilizator, fara administrator), `MemoryRegistry` tine
cheile intr-un dictionar (teste si alte sisteme).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

APP_NAME = "DocuLens"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
"""V-021: programele pornite la logarea utilizatorului."""

SCREENSHOT_RUN_NAME = "DocuLens Screenshot Reader"


class Registry(Protocol):
    def set(self, key: str, name: str, value: str) -> None:
        """`name` gol = valoarea implicita a cheii."""
        ...

    def get(self, key: str, name: str) -> str | None: ...

    def delete_value(self, key: str, name: str) -> None: ...

    def delete_tree(self, key: str) -> None: ...


class MemoryRegistry:
    """Registrul in memorie: {cheie: {nume: valoare}}."""

    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {}

    def set(self, key: str, name: str, value: str) -> None:
        self.keys.setdefault(key, {})[name] = value

    def get(self, key: str, name: str) -> str | None:
        return self.keys.get(key, {}).get(name)

    def delete_value(self, key: str, name: str) -> None:
        self.keys.get(key, {}).pop(name, None)

    def delete_tree(self, key: str) -> None:
        prefix = key.lower() + "\\"
        for existing in [k for k in self.keys if k.lower() == key.lower()
                         or k.lower().startswith(prefix)]:
            del self.keys[existing]


class WindowsRegistry:  # pragma: no cover - numai pe Windows
    """`HKEY_CURRENT_USER`: fara drepturi de administrator."""

    def __init__(self) -> None:
        import winreg  # type: ignore[import-not-found]

        self._w = winreg

    def set(self, key: str, name: str, value: str) -> None:
        w = self._w
        with w.CreateKeyEx(w.HKEY_CURRENT_USER, key, 0, w.KEY_SET_VALUE) as handle:
            w.SetValueEx(handle, name or None, 0, w.REG_SZ, value)

    def get(self, key: str, name: str) -> str | None:
        w = self._w
        try:
            with w.OpenKey(w.HKEY_CURRENT_USER, key) as handle:
                return str(w.QueryValueEx(handle, name or None)[0])
        except OSError:
            return None

    def delete_value(self, key: str, name: str) -> None:
        w = self._w
        try:
            with w.OpenKey(w.HKEY_CURRENT_USER, key, 0, w.KEY_SET_VALUE) as handle:
                w.DeleteValue(handle, name)
        except OSError:
            pass

    def delete_tree(self, key: str) -> None:
        w = self._w
        try:
            with w.OpenKey(w.HKEY_CURRENT_USER, key, 0, w.KEY_ALL_ACCESS) as handle:
                while True:
                    try:
                        child = w.EnumKey(handle, 0)
                    except OSError:
                        break
                    self.delete_tree(f"{key}\\{child}")
            w.DeleteKey(w.HKEY_CURRENT_USER, key)
        except OSError:
            pass


def default_registry() -> Registry:
    """Registrul Windows pe Windows; altfel unul in memorie (nu se scrie nimic)."""
    if sys.platform.startswith("win"):
        return WindowsRegistry()
    return MemoryRegistry()


def launch_command(args: Sequence[str] = ()) -> list[str]:
    """Comanda care porneste DocuLens: executabilul impachetat sau, din sursa,
    `python -m app.gui.main`."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "app.gui.main", *args]


def command_line(parts: Sequence[str]) -> str:
    """O linie de comanda Windows, cu ghilimele unde trebuie."""
    return subprocess.list2cmdline([str(p) for p in parts])


# V-021
def set_run_at_startup(registry: Registry, enabled: bool,
                       command: Sequence[str] | None = None) -> None:
    """`Run at Startup`: Screenshot Reader porneste la logarea utilizatorului."""
    if enabled:
        registry.set(RUN_KEY, SCREENSHOT_RUN_NAME,
                     command_line(command or launch_command(["--screenshot-reader"])))
    else:
        registry.delete_value(RUN_KEY, SCREENSHOT_RUN_NAME)


def runs_at_startup(registry: Registry) -> bool:
    return registry.get(RUN_KEY, SCREENSHOT_RUN_NAME) is not None


def exists(path: str | Path) -> bool:
    return Path(path).exists()


# --- meniul contextual Explorer (W-001…W-017, faza_15_pasi.md decizia 7) -------------------

SHELL_ROOT = r"Software\Classes\SystemFileAssociations\{ext}\shell\DocuLens"

PDF_EXTENSIONS = (".pdf",)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".pcx", ".dcx",
                    ".djvu", ".djv", ".jp2", ".jbig2", ".jb2", ".webp")
EDITABLE_EXTENSIONS = (".docx", ".xlsx", ".pptx", ".rtf", ".txt", ".odt", ".html", ".htm")
"""W-012: formatele editabile din cerinta."""

CONVERT_COMMANDS = ("convert_searchable_pdf", "convert_image_pdf", "convert_word",
                    "convert_excel", "convert_other")
"""W-003…W-007: submeniul `Convert with ...` (W-002)."""


def shell_commands(ext: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """W-016: (comenzile directe, comenzile din submeniul de conversie), dupa tipul
    fisierului."""
    ext = ext.lower()
    common = ("compare_with", "compare", "combine")  # W-009…W-011
    if ext in PDF_EXTENSIONS:
        return ("edit", "ocr", *common), CONVERT_COMMANDS  # W-001, W-008
    if ext in IMAGE_EXTENSIONS:
        return ("ocr", *common), CONVERT_COMMANDS
    if ext in EDITABLE_EXTENSIONS:
        return ("to_pdf", "to_pdf_send", *common), ()  # W-012, W-013
    return (), ()


def shell_entries(executable: Sequence[str], tr: Callable[..., str]
                  ) -> dict[str, dict[str, str]]:
    """Cheile din registru (relative la HKCU) pentru toate extensiile.

    Fiecare extensie primeste submeniul „DocuLens” (`SubCommands` gol = comenzile
    sunt subcheile `shell`); conversiile sunt intr-un submeniu propriu (W-002).
    `MultiSelectModel = Player`: comanda apare si pentru mai multe fisiere alese
    (W-015, W-016)."""
    icon = str(executable[0])
    entries: dict[str, dict[str, str]] = {}
    for ext in (*PDF_EXTENSIONS, *IMAGE_EXTENSIONS, *EDITABLE_EXTENSIONS):
        direct, convert = shell_commands(ext)
        root = SHELL_ROOT.format(ext=ext)
        entries[root] = {"MUIVerb": tr("integration.menu"), "SubCommands": "", "Icon": icon}
        for command in direct:
            key = f"{root}\\shell\\{command}"
            entries[key] = {"MUIVerb": tr(f"integration.command.{command}"),
                            "MultiSelectModel": "Player"}
            entries[f"{key}\\command"] = {"": command_line(
                [*executable, "--action", command]) + ' "%1"'}
        if convert:
            group = f"{root}\\shell\\convert"
            entries[group] = {"MUIVerb": tr("integration.command.convert"), "SubCommands": ""}
            for command in convert:
                key = f"{group}\\shell\\{command}"
                entries[key] = {"MUIVerb": tr(f"integration.command.{command}"),
                                "MultiSelectModel": "Player"}
                entries[f"{key}\\command"] = {"": command_line(
                    [*executable, "--action", command]) + ' "%1"'}
    return entries


FOLDER_COMMAND = r"Software\Classes\Directory\shell\DocuLens.OpenProject"
"""J-033: `Open OCR project in DocuLens`, pe folderul unui proiect."""


def register_shell_menu(registry: Registry, executable: Sequence[str],
                        tr: Callable[..., str]) -> int:
    """X-005, W-017: (re)scrie comenzile; intoarce numarul de chei."""
    unregister_shell_menu(registry)
    entries = shell_entries(executable, tr)
    entries[FOLDER_COMMAND] = {"MUIVerb": tr("integration.command.open_project"),
                               "Icon": str(executable[0])}
    entries[f"{FOLDER_COMMAND}\\command"] = {
        "": command_line([*executable, "--action", "open_project"]) + ' "%1"'}
    for key, values in entries.items():
        for name, value in values.items():
            registry.set(key, name, value)
    return len(entries)


def unregister_shell_menu(registry: Registry) -> None:
    """X-005: setarea oprita scoate DocuLens din meniul contextual."""
    for ext in (*PDF_EXTENSIONS, *IMAGE_EXTENSIONS, *EDITABLE_EXTENSIONS):
        registry.delete_tree(SHELL_ROOT.format(ext=ext))
    registry.delete_tree(FOLDER_COMMAND)


# --- PDF-ul implicit si asocierile (W-090, W-204, decizia 8) ---------------------------------

PROG_ID = "DocuLens.PDF"
IMAGE_PROG_ID = "DocuLens.Image"
CAPABILITIES = r"Software\DocuLens\Capabilities"
REGISTERED_APPS = r"Software\RegisteredApplications"


def register_file_types(registry: Registry, executable: Sequence[str],
                        tr: Callable[..., str]) -> None:
    """W-090, W-204: DocuLens apare in „Deschide cu” si in Setarile Windows pentru
    PDF si imagini. Programul implicit il alege utilizatorul in Setari (Windows
    10/11 nu permite programelor sa se faca singure implicite)."""
    open_command = command_line(executable) + ' "%1"'
    for prog_id, name_key, exts in ((PROG_ID, "integration.type.pdf", PDF_EXTENSIONS),
                                    (IMAGE_PROG_ID, "integration.type.image",
                                     IMAGE_EXTENSIONS)):
        base = f"Software\\Classes\\{prog_id}"
        registry.set(base, "", tr(name_key))
        registry.set(f"{base}\\DefaultIcon", "", f"{executable[0]},0")
        registry.set(f"{base}\\shell\\open\\command", "", open_command)
        for ext in exts:
            registry.set(f"Software\\Classes\\{ext}\\OpenWithProgids", prog_id, "")
            registry.set(f"{CAPABILITIES}\\FileAssociations", ext, prog_id)
    registry.set(CAPABILITIES, "ApplicationName", APP_NAME)
    registry.set(CAPABILITIES, "ApplicationDescription", tr("integration.description"))
    registry.set(REGISTERED_APPS, APP_NAME, CAPABILITIES)


def unregister_file_types(registry: Registry) -> None:
    for prog_id, exts in ((PROG_ID, PDF_EXTENSIONS), (IMAGE_PROG_ID, IMAGE_EXTENSIONS)):
        registry.delete_tree(f"Software\\Classes\\{prog_id}")
        for ext in exts:
            registry.delete_value(f"Software\\Classes\\{ext}\\OpenWithProgids", prog_id)
    registry.delete_tree(r"Software\DocuLens")
    registry.delete_value(REGISTERED_APPS, APP_NAME)


DEFAULT_APPS_URI = "ms-settings:defaultapps"
"""W-090: pagina Setarilor Windows in care utilizatorul alege programul implicit."""


def unregister_all(registry: Registry) -> None:
    """La dezinstalare (`--unregister-integration`): nu raman chei DocuLens."""
    unregister_shell_menu(registry)
    unregister_file_types(registry)
    set_run_at_startup(registry, False)
