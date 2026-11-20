"""Crearea si deschiderea bazelor de date SQLite.

Implementeaza SPEC_04_schema_bd.sql. Doua baze separate:

- app.db      — globala, in profilul utilizatorului (PARTEA I din SPEC_04)
- project.db  — una per proiect OCR, in folderul proiectului (PARTEA II)

Schema se citeste din SPEC_04 la rulare, nu se copiaza in cod, ca sa nu poata
iesi din sincronizare. Fiecare conexiune are `PRAGMA foreign_keys = ON` si
jurnal WAL, cum cer conventiile din SPEC_04.

Unde stau fisierele pe disc nu se decide aici: apelantul da calea
(folderul de date al aplicatiei vine in pasul 0c, Y-022..Y-026).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import CoreError, InvalidProjectError, ProjectVersionError

SCHEMA_VERSION = 1
"""Versiunea schemei din SPEC_04 pe care o intelege aceasta versiune a aplicatiei."""

SCHEMA_FILE = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "spec" / "SPEC_04_schema_bd.sql"
)

_PART_II_MARKER = "-- PARTEA II - project.db"


def _utc_now() -> str:
    """Timestamp ISO 8601 UTC, formatul din conventiile SPEC_04."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# SPEC_04: cele doua parti ale schemei
def _schema_parts() -> tuple[str, str]:
    """Imparte SPEC_04 in (sql pentru app.db, sql pentru project.db)."""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    marker = sql.find(_PART_II_MARKER)
    if marker < 0:
        raise RuntimeError(f"{SCHEMA_FILE.name}: lipseste marcajul '{_PART_II_MARKER}'")
    # Taiem la linia de '#' de deasupra titlului PARTEA II.
    cut = sql.rfind("-- ####", 0, marker)
    return sql[:cut], sql[cut:]


# SPEC_04 conventii: foreign_keys ON la fiecare conexiune, WAL
def connect(path: Path, *, create: bool = False) -> sqlite3.Connection:
    """Deschide o conexiune cu setarile cerute de SPEC_04.

    Cu `create=False` fisierul trebuie sa existe; SQLite nu creeaza unul gol.
    """
    path = Path(path)
    mode = "rwc" if create else "rw"
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode={mode}", uri=True)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        con.close()
        raise
    return con


def _remove_db_files(path: Path) -> None:
    """Sterge baza si fisierele WAL/SHM de langa ea."""
    for leftover in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        leftover.unlink(missing_ok=True)


def _create(path: Path, sql: str) -> sqlite3.Connection:
    """Creeaza baza din `sql`. La esec nu lasa un fisier pe jumatate scris."""
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = connect(path, create=True)
    try:
        con.executescript(sql)
        con.execute("PRAGMA foreign_keys = ON")  # executescript nu o schimba, dar e explicit
        return con
    except BaseException:
        con.close()
        _remove_db_files(path)
        raise


# --- app.db --------------------------------------------------------------------


# SPEC_04 PARTEA I — app.db, globala per utilizator
def open_app_db(path: Path) -> sqlite3.Connection:
    """Deschide app.db; daca nu exista, o creeaza din SPEC_04 PARTEA I.

    Raises:
        CoreError: fisierul exista dar nu e o baza app.db valida, sau e
            dintr-o versiune mai noua a aplicatiei (params: path, found, supported).
    """
    path = Path(path)
    if not path.exists():
        return _create(path, _schema_parts()[0])

    try:
        con = connect(path)
    except sqlite3.DatabaseError as exc:
        raise CoreError("app.db nu poate fi deschisa", path=str(path), detail=str(exc)) from exc
    try:
        row = con.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    except sqlite3.DatabaseError as exc:
        con.close()
        raise CoreError("app.db nu are tabela schema_version", path=str(path), detail=str(exc)) from exc
    if row is None or row[0] > SCHEMA_VERSION:
        con.close()
        raise CoreError(
            "app.db e dintr-o versiune mai noua",
            path=str(path),
            found=None if row is None else row[0],
            supported=SCHEMA_VERSION,
        )
    return con


# --- project.db ----------------------------------------------------------------


# SPEC_04 PARTEA II — project.db, antetul proiectului (tabela project)
def create_project_db(path: Path, name: str, app_version: str) -> sqlite3.Connection:
    """Creeaza project.db din SPEC_04 PARTEA II si scrie antetul proiectului.

    Un nume gol inseamna proiect fara titlu (J-030): GUI-ul afiseaza
    `Untitled project N`, tradus; la prima salvare primeste numele folderului.

    Raises:
        FileExistsError: exista deja un fisier la `path`.
    """
    name = name.strip()
    path = Path(path)
    con = _create(path, _schema_parts()[1])
    try:
        now = _utc_now()
        with con:
            con.execute(
                "INSERT INTO project (id, name, schema_version, app_version, created_at, updated_at)"
                " VALUES (1, ?, ?, ?, ?, ?)",
                (name, SCHEMA_VERSION, app_version, now, now),
            )
    except BaseException:
        con.close()
        _remove_db_files(path)
        raise
    return con


# J-003 (proiect invalid), P-029 (proiect din versiune mai noua) — ID-urile din SPEC_05
def open_project_db(path: Path) -> sqlite3.Connection:
    """Deschide un project.db existent.

    Raises:
        InvalidProjectError: fisierul lipseste, nu e SQLite sau nu are antet
            de proiect (params: path, detail).
        ProjectVersionError: proiectul vine dintr-o versiune mai noua
            (params: found, supported).
    """
    path = Path(path)
    if not path.is_file():
        raise InvalidProjectError("project.db lipseste", path=str(path), detail="missing")
    try:
        con = connect(path)
    except sqlite3.DatabaseError as exc:
        raise InvalidProjectError("project.db nu se deschide", path=str(path), detail=str(exc)) from exc
    try:
        row = con.execute("SELECT schema_version FROM project WHERE id = 1").fetchone()
    except sqlite3.DatabaseError as exc:
        con.close()
        raise InvalidProjectError("project.db fara antet", path=str(path), detail=str(exc)) from exc
    if row is None:
        con.close()
        raise InvalidProjectError("project.db fara antet", path=str(path), detail="no project row")
    if row[0] > SCHEMA_VERSION:
        con.close()
        raise ProjectVersionError(
            "proiect dintr-o versiune mai noua", found=row[0], supported=SCHEMA_VERSION
        )
    return con
