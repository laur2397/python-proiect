"""Jurnalul aplicatiei si raportul unei erori neasteptate.

Y-024: fisier rotativ, cu niveluri, in folderul de jurnal al aplicatiei.
Y-025, partea de nucleu: captarea erorii si salvarea jurnalului. Dialogul cu
mesajul si urma stivei copiabila vine in faza GUI; el primeste un
`CrashReport` de la `record_unexpected_error`.

Nucleul nu scrie la consola: singura destinatie e fisierul.
"""

from __future__ import annotations

import logging
import platform
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "doculens"
LOG_FILE_NAME = "doculens.log"
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

MAX_BYTES = 1_000_000
"""[DECIZIE] Un fisier de jurnal are cel mult ~1 MB."""
BACKUP_COUNT = 5
"""[DECIZIE] Se pastreaza 5 fisiere vechi: maximum ~6 MB de jurnal."""
CRASH_LOG_TAIL = 200
"""Cate randuri din jurnal se copiaza in raportul de eroare."""

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _UtcFormatter(logging.Formatter):
    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", self.converter(record.created))


def _is_ours(handler: logging.Handler) -> bool:
    return getattr(handler, "_doculens", False)


# Y-024
def configure_logging(log_dir: Path, level: str = "INFO") -> Path:
    """Porneste jurnalul rotativ in `log_dir`. Se poate apela din nou (de exemplu
    cu alt nivel): inlocuieste configurarea anterioara. Intoarce calea fisierului.

    Raises:
        ValueError: nivelul nu e unul din LEVELS.
    """
    level = level.upper()
    if level not in LEVELS:
        raise ValueError(f"nivel de jurnal necunoscut: {level!r}; permise: {LEVELS}")
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME

    logger = logging.getLogger(LOGGER_NAME)
    shutdown_logging()
    handler = RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler._doculens = True  # type: ignore[attr-defined]
    handler.setFormatter(_UtcFormatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return log_file


def shutdown_logging() -> None:
    """Inchide fisierul de jurnal (la iesire, sau inainte de reconfigurare)."""
    logger = logging.getLogger(LOGGER_NAME)
    for h in [h for h in logger.handlers if _is_ours(h)]:
        logger.removeHandler(h)
        h.close()


def get_logger(name: str = "") -> logging.Logger:
    """Logger-ul unui modul: get_logger('core.ocr') -> 'doculens.core.ocr'."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


# Y-025, partea de nucleu
@dataclass(frozen=True, slots=True)
class CrashReport:
    error_type: str
    message: str
    traceback_text: str
    """Urma stivei, gata de copiat din dialog."""
    report_path: Path | None
    """Fisierul salvat, sau None daca nu s-a putut scrie (de exemplu disc plin)."""


def record_unexpected_error(
    exc: BaseException, log_dir: Path, *, app_version: str = "", context: str = ""
) -> CrashReport:
    """Scrie eroarea in jurnal si salveaza un raport separat, cu ultimele randuri
    din jurnal. Nu arunca niciodata: e apelata chiar cand ceva a mers prost.

    Decizia daca aplicatia continua (Y-025: nu se inchide daca starea
    documentului se poate salva) apartine apelantului.
    """
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    error_type = type(exc).__name__
    message = str(exc)
    try:
        get_logger().critical(
            "eroare neasteptata%s", f" ({context})" if context else "",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        for h in logging.getLogger(LOGGER_NAME).handlers:
            h.flush()
    except Exception:  # noqa: BLE001, S110 — raportarea nu are voie sa cada
        pass

    report_path: Path | None = None
    try:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        report_path = log_dir / f"crash-{stamp}.txt"
        report_path.write_text(
            _report_text(error_type, message, tb_text, log_dir, app_version, context),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 — raportarea nu are voie sa cada
        report_path = None
    return CrashReport(error_type, message, tb_text, report_path)


def _report_text(
    error_type: str, message: str, tb_text: str, log_dir: Path, app_version: str, context: str
) -> str:
    lines = [
        f"DocuLens {app_version}".rstrip(),
        f"timp (UTC): {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"sistem: {platform.platform()}; Python {sys.version.split()[0]}",
    ]
    if context:
        lines.append(f"context: {context}")
    lines += ["", f"{error_type}: {message}", "", tb_text.rstrip(), "",
              f"--- ultimele {CRASH_LOG_TAIL} randuri din jurnal ---"]
    log_file = log_dir / LOG_FILE_NAME
    if log_file.is_file():
        tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        lines += tail[-CRASH_LOG_TAIL:]
    return "\n".join(lines) + "\n"
