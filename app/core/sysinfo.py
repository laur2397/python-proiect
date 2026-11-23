"""Versiunea, numarul de build si raportul de sistem (faza 16, pasul 16.2):
Y-014 (`Help > About > System Info... > Save...`), Y-015 (numarul de build).

Numarul de build vine din `app/core/data/build.txt`, scris de scriptul de
construire (data si commit-ul); din sursa e `dev`. Raportul nu contine date
personale in afara cailor folderelor aplicatiei si nicio cerere de retea (Y-001).
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

BUILD_FILE = Path(__file__).resolve().parent / "data" / "build.txt"


def build_number() -> str:
    """Y-015: `2026.11.24-4c794b7` in pachet; `dev` din sursa."""
    try:
        text = BUILD_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"
    return text or "dev"


def system_info(context: Any) -> list[tuple[str, str]]:
    """Y-014: (cheia textului, valoarea). Cheile se traduc in interfata
    (`sysinfo.<cheie>`)."""
    from app.core.context import APP_VERSION
    from app.core.ocr.engine import find_tesseract
    from app.core.ocr.languages import LanguageRegistry

    tesseract = find_tesseract()
    try:
        languages = len(LanguageRegistry(con=context.app_db).all())
    except Exception:  # noqa: BLE001 - raportul nu trebuie sa cada
        languages = 0
    temp = context.health.temp_root()
    probe = temp if temp.exists() else Path(temp.anchor or "/")
    free = shutil.disk_usage(probe).free
    rows: list[tuple[str, str]] = [
        ("version", APP_VERSION),
        ("build", build_number()),
        ("os", f"{platform.system()} {platform.release()} ({platform.version()})"),
        ("machine", platform.machine()),
        ("processors", str(os.cpu_count() or 1)),
        ("python", sys.version.split()[0]),
        ("frozen", "yes" if getattr(sys, "frozen", False) else "no"),
        ("tesseract", str(tesseract) if tesseract else "-"),
        ("languages", str(languages)),
        ("data_dir", str(context.paths.data_dir)),
        ("log_dir", str(context.paths.log_dir)),
        ("temp_dir", str(temp)),
        ("free_space", f"{free / 1024 ** 3:.1f} GB"),
        ("ui_language", str(context.settings.get("ui.language") or "")),
    ]
    try:
        from PySide6 import __version__ as pyside

        rows.insert(6, ("qt", pyside))
    except ImportError:
        pass
    return rows


def write_report(context: Any, target: Path, labels: dict[str, str] | None = None) -> Path:
    """`System Info... > Save...`: raportul ca text (cheie: valoare)."""
    labels = labels or {}
    lines = [f"{labels.get(key, key)}: {value}" for key, value in system_info(context)]
    Path(target).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(target)
