"""Teste pentru app/core/applog.py: jurnalul (Y-024) si raportul de eroare (Y-025)."""

from __future__ import annotations

import logging
import re

import pytest

from app.core import applog
from app.core.applog import (
    LOG_FILE_NAME,
    LOGGER_NAME,
    configure_logging,
    get_logger,
    record_unexpected_error,
    shutdown_logging,
)


@pytest.fixture(autouse=True)
def _close_log():
    yield
    shutdown_logging()


def _boom():
    raise RuntimeError("ceva s-a stricat")


def _caught():
    try:
        _boom()
    except RuntimeError as exc:
        return exc
    raise AssertionError


def test_T_Y024_1_log_file_with_levels_and_utc_time(tmp_path):
    """T-Y024.1: fisier in folderul de jurnal, cu niveluri si timp UTC."""
    log_file = configure_logging(tmp_path, "INFO")
    assert log_file == tmp_path / LOG_FILE_NAME
    get_logger("core.test").debug("nu apare")
    get_logger("core.test").info("Șoseaua Țării și ştiinţă")
    get_logger("core.test").warning("atentie")
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ INFO doculens\.core\.test Șoseaua", lines[0])
    assert " WARNING " in lines[1]


def test_level_can_be_changed_without_duplicate_handlers(tmp_path):
    configure_logging(tmp_path, "WARNING")
    configure_logging(tmp_path, "debug")
    ours = [h for h in logging.getLogger(LOGGER_NAME).handlers if getattr(h, "_doculens", False)]
    assert len(ours) == 1
    get_logger().debug("acum apare")
    assert "acum apare" in (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")


def test_unknown_level_is_refused(tmp_path):
    with pytest.raises(ValueError):
        configure_logging(tmp_path, "VERBOSE")


def test_T_Y024_2_log_rotates(tmp_path, monkeypatch):
    """T-Y024.2: jurnalul e rotativ si nu creste nelimitat."""
    monkeypatch.setattr(applog, "MAX_BYTES", 2000)
    monkeypatch.setattr(applog, "BACKUP_COUNT", 2)
    configure_logging(tmp_path)
    for i in range(500):
        get_logger().info("rand %d %s", i, "x" * 50)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == [LOG_FILE_NAME, f"{LOG_FILE_NAME}.1", f"{LOG_FILE_NAME}.2"]
    assert all((tmp_path / f).stat().st_size <= 2200 for f in files)


def test_core_logger_does_not_write_to_console(tmp_path, capsys):
    configure_logging(tmp_path)
    get_logger().error("doar in fisier")
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_T_Y025_1_unexpected_error_is_logged_and_saved(tmp_path):
    """T-Y025.1: eroarea, cu urma stivei, ajunge in jurnal si intr-un raport salvat."""
    configure_logging(tmp_path)
    get_logger().info("inainte de eroare")
    report = record_unexpected_error(_caught(), tmp_path, app_version="0.1.0", context="export")
    assert report.error_type == "RuntimeError"
    assert report.message == "ceva s-a stricat"
    assert "_boom" in report.traceback_text
    text = report.report_path.read_text(encoding="utf-8")
    assert "DocuLens 0.1.0" in text and "context: export" in text
    assert "RuntimeError: ceva s-a stricat" in text
    assert "inainte de eroare" in text  # coada jurnalului
    log = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "CRITICAL" in log and "_boom" in log


def test_record_works_without_configured_log(tmp_path):
    report = record_unexpected_error(_caught(), tmp_path / "jurnal")
    assert report.report_path is not None and report.report_path.is_file()


def test_record_never_raises_even_if_report_cannot_be_written(tmp_path):
    blocker = tmp_path / "fisier"
    blocker.write_text("nu e folder")
    report = record_unexpected_error(_caught(), blocker / "jurnal")
    assert report.report_path is None
    assert report.error_type == "RuntimeError"
