"""Faza 6c, pasul 6c.1: documentele recente (A-102…A-105)."""

from __future__ import annotations

import pytest

from app.core.context import AppContext
from app.core.paths import AppPaths
from app.core.recent import RecentDocuments


@pytest.fixture
def recent(tmp_path):
    ctx = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield RecentDocuments(ctx.app_db)
    ctx.close()


def test_T_A102_1_newest_first_and_reopen_moves_up(recent, tmp_path):
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (tmp_path / name).write_bytes(b"%PDF")
        recent.add(tmp_path / name, "pdf", page_count=2)
    assert [d.display_name for d in recent.list()] == ["c.pdf", "b.pdf", "a.pdf"]
    recent.add(tmp_path / "a.pdf", "pdf", last_page=5)
    docs = recent.list()
    assert docs[0].display_name == "a.pdf" and docs[0].last_page == 5
    assert len(docs) == 3  # aceeasi cale nu se dubleaza


def test_T_A102_2_missing_file_is_marked(recent, tmp_path):
    (tmp_path / "x.pdf").write_bytes(b"%PDF")
    recent.add(tmp_path / "x.pdf", "pdf")
    assert recent.list()[0].exists
    (tmp_path / "x.pdf").unlink()
    assert not recent.list()[0].exists  # ramane in lista, marcat


def test_T_A103_1_search_ignores_diacritics_and_case(recent, tmp_path):
    recent.add(tmp_path / "Cerere finanțare Brașov.pdf", "pdf")
    recent.add(tmp_path / "Ofertă.docx", "office")
    recent.add(tmp_path / "proiect" / "Dosar", "ocr_project", display_name="Dosar")
    assert [d.display_name for d in recent.list(query="brasov")] == [
        "Cerere finanțare Brașov.pdf"]
    assert [d.display_name for d in recent.list(query="OFERTA")] == ["Ofertă.docx"]
    assert [d.display_name for d in recent.list(query="proiect")] == ["Dosar"]  # in cale
    assert recent.last("ocr_project").display_name == "Dosar"
    assert recent.last("image") is None


def test_T_A104_1_and_A105_1_remove_and_clear(recent, tmp_path):
    (tmp_path / "pastrat.pdf").write_bytes(b"%PDF")
    recent.add(tmp_path / "pastrat.pdf", "pdf")
    recent.add(tmp_path / "altul.pdf", "pdf")
    recent.remove(tmp_path / "pastrat.pdf")
    assert [d.display_name for d in recent.list()] == ["altul.pdf"]
    assert (tmp_path / "pastrat.pdf").exists()  # fisierul nu se atinge
    recent.clear()
    assert recent.list() == []


def test_list_is_capped_at_50(recent, tmp_path):
    for n in range(55):
        recent.add(tmp_path / f"d{n}.pdf", "pdf")
    assert len(recent.list()) == 50


def test_unknown_kind_is_refused(recent, tmp_path):
    with pytest.raises(ValueError):
        recent.add(tmp_path / "x", "video")
