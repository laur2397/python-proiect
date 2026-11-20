"""Teste pentru app/core/recovery.py: fisierele de siguranta (Y-026)."""

from __future__ import annotations

import os

import pytest

from app.core import db
from app.core.recovery import RecoveryRegistry

DEAD = "999999999-deadbeef0000"


@pytest.fixture
def con(tmp_path):
    c = db.open_app_db(tmp_path / "app.db")
    yield c
    c.close()


@pytest.fixture
def rdir(tmp_path):
    return tmp_path / "recovery"


def _crashed_session(con, rdir, kind="ocr_project", original="/dosare/cerere.pdf"):
    """Simuleaza o sesiune care a salvat un fisier de siguranta si a cazut."""
    old = RecoveryRegistry(con, rdir, session_id=DEAD)
    path = old.new_recovery_path(kind, ".dlproj")
    path.write_bytes(b"continut")
    old.register(path, original, kind)
    return path


def test_T_Y026_1_crashed_session_is_offered_for_recovery(con, rdir):
    """T-Y026.1: la pornire se ofera fisierele de siguranta ale unei sesiuni cazute."""
    path = _crashed_session(con, rdir)
    pending = RecoveryRegistry(con, rdir).find_pending()
    assert len(pending) == 1
    e = pending[0]
    assert e.recovery_path == path
    assert str(e.original_path).endswith("cerere.pdf")
    assert (e.doc_kind, e.session_id) == ("ocr_project", DEAD)
    assert e.saved_at.endswith("Z")


def test_unsaved_document_has_no_original_path(con, rdir):
    _crashed_session(con, rdir, kind="pdf", original=None)
    (e,) = RecoveryRegistry(con, rdir).find_pending()
    assert e.original_path is None


def test_clean_exit_leaves_nothing_to_recover(con, rdir):
    first = RecoveryRegistry(con, rdir)
    path = first.new_recovery_path("pdf", "pdf")
    path.write_bytes(b"x")
    first.register(path, None, "pdf")
    first.mark_clean_exit()
    assert not path.exists()
    assert RecoveryRegistry(con, rdir).find_pending() == []


def test_own_and_running_sessions_are_not_offered(con, rdir):
    me = RecoveryRegistry(con, rdir)
    p1 = me.new_recovery_path("pdf", "pdf")
    p1.write_bytes(b"x")
    me.register(p1, None, "pdf")
    assert me.find_pending() == []  # propria sesiune
    other_alive = RecoveryRegistry(con, rdir, session_id=f"{os.getpid()}-alta00000000")
    assert other_alive.find_pending() == []  # sesiunea `me` e a unui proces viu


def test_missing_files_are_pruned(con, rdir):
    path = _crashed_session(con, rdir)
    path.unlink()
    assert RecoveryRegistry(con, rdir).find_pending() == []
    assert con.execute("SELECT COUNT(*) FROM recovery_entry").fetchone()[0] == 0


def test_discard_removes_file_and_row(con, rdir):
    _crashed_session(con, rdir)
    reg = RecoveryRegistry(con, rdir)
    (e,) = reg.find_pending()
    reg.discard(e)
    assert not e.recovery_path.exists()
    assert reg.find_pending() == []


def test_register_again_refreshes_the_entry(con, rdir):
    reg = RecoveryRegistry(con, rdir)
    path = reg.new_recovery_path("pdf", "pdf")
    path.write_bytes(b"x")
    reg.register(path, None, "pdf")
    reg.register(path, "/acum/salvat.pdf", "pdf")
    rows = con.execute("SELECT original_path FROM recovery_entry").fetchall()
    assert rows == [("/acum/salvat.pdf",)]


def test_forget_after_normal_save(con, rdir):
    reg = RecoveryRegistry(con, rdir)
    path = reg.new_recovery_path("ocr_project", "dlproj")
    path.write_bytes(b"x")
    reg.register(path, None, "ocr_project")
    reg.forget(path)
    assert not path.exists()
    assert con.execute("SELECT COUNT(*) FROM recovery_entry").fetchone()[0] == 0


def test_newest_first(con, rdir):
    a = _crashed_session(con, rdir)
    b = _crashed_session(con, rdir)
    with con:
        con.execute("UPDATE recovery_entry SET saved_at = '2026-01-01T00:00:00Z'"
                    " WHERE recovery_path = ?", (str(a),))
    pending = RecoveryRegistry(con, rdir).find_pending()
    assert [e.recovery_path for e in pending] == [b, a]


def test_unknown_doc_kind_is_refused(con, rdir):
    reg = RecoveryRegistry(con, rdir)
    with pytest.raises(ValueError):
        reg.new_recovery_path("docx", "docx")
    with pytest.raises(ValueError):
        reg.register(rdir / "x", None, "docx")


def test_recovery_paths_are_unique_and_in_recovery_dir(con, rdir):
    reg = RecoveryRegistry(con, rdir)
    a, b = reg.new_recovery_path("pdf", ".pdf"), reg.new_recovery_path("pdf", "pdf")
    assert a != b and a.parent == rdir and a.suffix == ".pdf"
    assert a.name.startswith(reg.session_id)
