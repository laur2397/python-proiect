"""Teste pentru app/core/health.py: fisierele temporare (Y-023) si pornirea."""

from __future__ import annotations

import os

import pytest

from app.core import db, health
from app.core.errors import DiskFullError, NoWritePermissionError
from app.core.health import SESSION_PREFIX, ApplicationHealth
from app.core.paths import AppPaths
from app.core.settings import AppSettingsStore

DEAD = "999999999-deadbeef0000"  # PID care nu exista


@pytest.fixture
def paths(tmp_path):
    p = AppPaths.portable(tmp_path)
    p.ensure()
    return p


def _session_dir(root, sid, size=1000):
    d = root / f"{SESSION_PREFIX}{sid}"
    (d / "sub").mkdir(parents=True)
    (d / "pagina.png").write_bytes(b"x" * size)
    (d / "sub" / "tmp.bin").write_bytes(b"y" * size)
    return d


def test_temp_folder_is_per_session(paths):
    a = ApplicationHealth(paths)
    b = ApplicationHealth(paths)
    assert a.temp_folder() != b.temp_folder()
    assert a.temp_folder().is_dir()
    assert a.temp_folder().parent == paths.temp_root


def test_T_X150_1_temp_folder_setting_is_respected(tmp_path, paths):
    con = db.open_app_db(paths.app_db)
    settings = AppSettingsStore(con)
    settings.set("app.temp_folder", str(tmp_path / "ales"))
    h = ApplicationHealth(paths, settings)
    assert (tmp_path / "ales") in h.temp_folder().parents
    con.close()


def test_T_Y023_1_startup_removes_crash_leftovers(paths):
    """T-Y023.1: la pornire se sterg resturile unei sesiuni cazute."""
    dead = _session_dir(paths.temp_root, DEAD)
    h = ApplicationHealth(paths)
    freed = h.cleanup_temp()
    assert freed == 2000
    assert not dead.exists()


def test_T_Y023_2_close_removes_own_session(paths):
    """T-Y023.2: la inchiderea normala se sterge si folderul sesiunii curente."""
    h = ApplicationHealth(paths)
    (h.temp_folder() / "a.tmp").write_bytes(b"z" * 10)
    assert h.cleanup_temp() == 0  # la pornire, propriul folder ramane
    assert h.temp_folder().exists()
    assert h.cleanup_temp(include_current=True) == 10
    assert not (paths.temp_root / f"{SESSION_PREFIX}{h.session_id}").exists()


def test_running_instance_is_not_touched(paths):
    """O alta instanta pornita in paralel (PID viu) isi pastreaza temporarele."""
    alive = _session_dir(paths.temp_root, f"{os.getpid()}-other0000000")
    ApplicationHealth(paths).cleanup_temp()
    assert alive.exists()


def test_cleanup_never_touches_foreign_files(tmp_path, paths):
    """Daca X-150 arata spre un folder al utilizatorului, nimic strain nu se sterge."""
    (paths.temp_root / "document.docx").write_bytes(b"important")
    (paths.temp_root / "folder-personal").mkdir()
    (paths.temp_root / "folder-personal" / "poza.jpg").write_bytes(b"x")
    ApplicationHealth(paths).cleanup_temp()
    assert (paths.temp_root / "document.docx").exists()
    assert (paths.temp_root / "folder-personal" / "poza.jpg").exists()


def test_cleanup_with_missing_temp_root(tmp_path):
    h = ApplicationHealth(AppPaths.portable(tmp_path / "nimic"))
    assert h.cleanup_temp() == 0


def test_free_space_and_log_folder(paths):
    h = ApplicationHealth(paths)
    assert h.free_space_bytes() > 0
    assert h.log_folder() == paths.log_dir


def test_check_startup_ok(paths):
    assert ApplicationHealth(paths).check_startup() == []


def test_check_startup_reports_low_disk(paths, monkeypatch):
    monkeypatch.setattr(health, "MIN_FREE_BYTES", 10**30)
    problems = ApplicationHealth(paths).check_startup()
    assert len(problems) == 1 and isinstance(problems[0], DiskFullError)
    assert problems[0].params["required_bytes"] == 10**30


def test_check_startup_reports_unwritable_temp(paths, monkeypatch):
    def boom(*a, **k):
        raise PermissionError("acces refuzat")

    monkeypatch.setattr(health.tempfile, "NamedTemporaryFile", boom)
    problems = ApplicationHealth(paths).check_startup()
    assert len(problems) == 1 and isinstance(problems[0], NoWritePermissionError)
