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
from collections.abc import Sequence
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
