"""Teste pentru app/core/paths.py si app/core/process.py (pasul 0c)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.core import paths as paths_mod
from app.core.paths import APP_NAME, AppPaths
from app.core.process import new_session_id, pid_alive, session_pid


def test_default_paths_are_per_user_and_named_for_the_app():
    p = AppPaths.default()
    home = Path.home()
    for folder in (p.data_dir, p.log_dir):
        assert APP_NAME in folder.parts
        if sys.platform != "win32":
            assert home in folder.parents
    assert p.app_db == p.data_dir / "app.db"


def test_recovery_is_not_inside_temp():
    """Curatarea temporarelor (Y-023) nu are voie sa stearga recuperarea (Y-026)."""
    p = AppPaths.default()
    assert p.temp_root not in p.recovery_dir.parents


def test_T_Y010_1_portable_keeps_everything_in_one_folder(tmp_path):
    p = AppPaths.portable(tmp_path)
    for folder in (p.data_dir, p.log_dir, p.temp_root, p.recovery_dir, p.dictionaries_dir):
        assert tmp_path in folder.parents


def test_ensure_creates_folders(tmp_path):
    p = AppPaths.portable(tmp_path / "x")
    p.ensure()
    assert p.data_dir.is_dir() and p.log_dir.is_dir()
    assert p.temp_root.is_dir() and p.recovery_dir.is_dir()


def test_paths_module_uses_no_hardcoded_os_folders():
    src = Path(paths_mod.__file__).read_text(encoding="utf-8")
    assert "AppData" not in src.replace("%APPDATA%", "").replace("%LOCALAPPDATA%", "")
    assert "/Users/" not in src and "C:\\\\" not in src


def test_session_id_carries_current_pid():
    sid = new_session_id()
    assert session_pid(sid) == os.getpid()
    assert new_session_id() != sid


def test_session_pid_rejects_malformed_ids():
    assert session_pid("abc") is None
    assert session_pid("abc-123") is None
    assert session_pid("") is None


def test_pid_alive():
    assert pid_alive(os.getpid()) is True
    assert pid_alive(0) is False
    assert pid_alive(-5) is False
    assert pid_alive(2**22 + 12345) is False  # peste limita obisnuita de PID
