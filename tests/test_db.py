"""Teste pentru app/core/db.py: crearea si deschiderea app.db si project.db (SPEC_04)."""

from __future__ import annotations

import sqlite3

import pytest

from app.core import db
from app.core.errors import CoreError, InvalidProjectError, ProjectVersionError


def _objects(con: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }


@pytest.fixture
def app_db(tmp_path):
    con = db.open_app_db(tmp_path / "app.db")
    yield con
    con.close()


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "Dosar" / "project.db"
    con = db.create_project_db(path, "Dosar test", "0.1.0")
    yield path, con
    con.close()


# --- conexiunea ----------------------------------------------------------------


def test_connection_has_foreign_keys_and_wal(app_db):
    assert app_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert app_db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_reopened_connection_still_has_foreign_keys(tmp_path):
    db.open_app_db(tmp_path / "app.db").close()
    con = db.open_app_db(tmp_path / "app.db")
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    con.close()


# --- app.db --------------------------------------------------------------------


def test_app_db_has_part_one_only(app_db):
    names = _objects(app_db)
    assert {"schema_version", "setting", "ocr_language", "automated_task", "recovery_entry"} <= names
    assert "project" not in names and "page" not in names


def test_app_db_schema_version(app_db):
    assert app_db.execute("SELECT version FROM schema_version").fetchone()[0] == db.SCHEMA_VERSION


def test_app_db_reopen_keeps_data(tmp_path):
    path = tmp_path / "app.db"
    con = db.open_app_db(path)
    with con:
        con.execute(
            "INSERT INTO recent_comparison (path_left, path_right, language_codes, compared_at)"
            " VALUES ('a.pdf', 'b.pdf', '[\"ron\"]', '2026-01-01T00:00:00Z')"
        )
    con.close()
    con = db.open_app_db(path)
    assert con.execute("SELECT COUNT(*) FROM recent_comparison").fetchone()[0] == 1
    con.close()


def test_app_db_newer_version_is_refused(tmp_path):
    path = tmp_path / "app.db"
    con = db.open_app_db(path)
    with con:
        con.execute("UPDATE schema_version SET version = ?", (db.SCHEMA_VERSION + 1,))
    con.close()
    with pytest.raises(CoreError) as info:
        db.open_app_db(path)
    assert info.value.params["found"] == db.SCHEMA_VERSION + 1


def test_app_db_garbage_file_is_refused(tmp_path):
    path = tmp_path / "app.db"
    path.write_bytes(b"nu e sqlite" * 100)
    with pytest.raises(CoreError):
        db.open_app_db(path)


def test_app_db_creates_parent_folder(tmp_path):
    con = db.open_app_db(tmp_path / "profil" / "DocuLens" / "app.db")
    con.close()
    assert (tmp_path / "profil" / "DocuLens" / "app.db").is_file()


# --- project.db ----------------------------------------------------------------


def test_project_db_has_part_two_only(project):
    _, con = project
    names = _objects(con)
    assert {"project", "page", "area", "word", "v_project_status", "v_page_text"} <= names
    assert "setting" not in names and "schema_version" not in names


def test_project_header_is_written(project):
    _, con = project
    name, version, app_version, created, updated = con.execute(
        "SELECT name, schema_version, app_version, created_at, updated_at FROM project"
    ).fetchone()
    assert (name, version, app_version) == ("Dosar test", db.SCHEMA_VERSION, "0.1.0")
    assert created == updated
    assert len(created) == 20 and created.endswith("Z") and created[10] == "T"


def test_project_defaults_from_spec04(project):
    _, con = project
    langs, mode = con.execute("SELECT language_codes, layout_mode FROM project").fetchone()
    assert langs == '["ron","eng"]'
    assert mode == "editable"


def test_project_db_round_trip(project):
    path, con = project
    con.close()
    con = db.open_project_db(path)
    assert con.execute("SELECT name FROM project").fetchone()[0] == "Dosar test"
    con.close()


def test_create_project_refuses_existing_file(project):
    path, _ = project
    with pytest.raises(FileExistsError):
        db.create_project_db(path, "Alt proiect", "0.1.0")


def test_create_project_refuses_empty_name(tmp_path):
    with pytest.raises(ValueError):
        db.create_project_db(tmp_path / "project.db", "   ", "0.1.0")
    assert not (tmp_path / "project.db").exists()


def test_T_J003_1_missing_project_is_invalid(tmp_path):
    """T-J003.1 (ID din SPEC_05): folderul nu e un proiect valid."""
    with pytest.raises(InvalidProjectError) as info:
        db.open_project_db(tmp_path / "nu-exista" / "project.db")
    assert info.value.code == "INVALID_PROJECT"
    assert not (tmp_path / "nu-exista").exists()  # deschiderea nu creeaza nimic


def test_garbage_file_is_invalid_project(tmp_path):
    path = tmp_path / "project.db"
    path.write_bytes(b"\x00\x01 nu e sqlite " * 200)
    with pytest.raises(InvalidProjectError):
        db.open_project_db(path)


def test_app_db_is_not_a_project(tmp_path):
    db.open_app_db(tmp_path / "app.db").close()
    with pytest.raises(InvalidProjectError):
        db.open_project_db(tmp_path / "app.db")


def test_project_without_header_row_is_invalid(project):
    path, con = project
    with con:
        con.execute("DELETE FROM project")
    con.close()
    with pytest.raises(InvalidProjectError):
        db.open_project_db(path)


def test_T_P029_1_newer_project_version_is_refused(project):
    """T-P029.1 (ID din SPEC_05): proiect dintr-o versiune mai noua."""
    path, con = project
    with con:
        con.execute("UPDATE project SET schema_version = ?", (db.SCHEMA_VERSION + 1,))
    con.close()
    with pytest.raises(ProjectVersionError) as info:
        db.open_project_db(path)
    assert dict(info.value.params) == {"found": db.SCHEMA_VERSION + 1, "supported": db.SCHEMA_VERSION}


# --- regulile din schema functioneaza prin conexiunea noastra --------------------


def _add_page(con: sqlite3.Connection, n: int) -> int:
    cur = con.execute(
        "INSERT INTO page (page_number, image_path, original_path, width_px, height_px,"
        " dpi_x, dpi_y, color_mode) VALUES (?, ?, ?, 100, 100, 300, 300, 'gray')",
        (n, f"images/{n}.png", f"images/{n}.orig.png"),
    )
    return cur.lastrowid


def test_foreign_keys_are_enforced(project):
    _, con = project
    with pytest.raises(sqlite3.IntegrityError), con:
        con.execute(
            "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
            " bbox_h, polygon) VALUES (999, 0, 'text', 0, 0, 50, 20, '[]')"
        )


def test_T_M008_1_area_under_8px_refused(project):
    """T-M008.1: zona prea mica nu se creeaza (impus in schema)."""
    _, con = project
    with con:
        page = _add_page(con, 1)
    with pytest.raises(sqlite3.IntegrityError), con:
        con.execute(
            "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
            " bbox_h, polygon) VALUES (?, 0, 'text', 0, 0, 4, 4, '[]')",
            (page,),
        )


def test_T_J055_1_last_page_cannot_be_deleted(project):
    """T-J055.1: proiectul trebuie sa pastreze cel putin o pagina."""
    _, con = project
    with con:
        _add_page(con, 1)
        _add_page(con, 2)
    with con:
        con.execute("DELETE FROM page WHERE page_number = 2")
    with pytest.raises(sqlite3.DatabaseError), con:
        con.execute("DELETE FROM page WHERE page_number = 1")
