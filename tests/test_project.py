"""Teste pentru app/core/project.py si app/core/context.py (faza 1, pasul 1c)."""

from __future__ import annotations

import io
import os
import sys

import pytest
from _pdfgen import A4, BLACK, RED, make_pdf
from PIL import Image

from app.core import context as ctxmod
from app.core.context import AppContext
from app.core.errors import (
    FileCorruptError,
    InvalidProjectError,
    NoWritePermissionError,
    OperationCancelledError,
    PasswordRequiredError,
    ProjectVersionError,
    UnsupportedFormatError,
)
from app.core.images.loader import ImageLoader
from app.core.model import ColorMode, LayoutMode, PageStatus
from app.core.paths import AppPaths
from app.core.project import THUMBNAIL_SIZE, OcrProject

DEAD = "999999999-deadbeef0000"


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    Image.new("L", (300, 200), 255).save(d / "alb.png", dpi=(300, 300))
    Image.new("RGB", (120, 90), (10, 120, 200)).save(d / "foto.jpg", dpi=(200, 200), quality=90)
    frames = [Image.new("L", (100, 60), v) for v in (0, 128, 255)]
    frames[0].save(d / "trei.tif", save_all=True, append_images=frames[1:], dpi=(300, 300))
    make_pdf(d / "doua.pdf", [(*A4, BLACK), (*A4, RED)])
    (d / "desen.svg").write_text("<svg/>")
    return d


@pytest.fixture
def project(ctx):
    p = OcrProject.create(context=ctx)
    yield p
    p.close()


def _numbers(p):
    return [pg.page_number for pg in p.pages]


def _sources(p):
    return [(pg.source_file.name, pg.source_page) for pg in p.pages]


# =============================================================================
# Contextul
# =============================================================================


def test_context_shares_session_between_temp_and_recovery(ctx):
    assert ctx.health.session_id == ctx.recovery.session_id
    assert ctx.paths.app_db.is_file()


def test_current_context_must_be_configured(ctx):
    ctxmod._current = None
    with pytest.raises(RuntimeError):
        OcrProject.create()
    ctxmod.configure(ctx)
    p = OcrProject.create()
    p.close()
    ctx.close()
    ctx.close()  # a doua oara nu strica nimic
    assert ctxmod._current is None


def test_context_close_cleans_session_temp(ctx):
    """La iesire, proiectele ramase deschise se inchid inainte de curatare,
    altfel pe Windows project.db deschis nu s-ar putea sterge."""
    p = OcrProject.create(context=ctx)
    work = p._work
    assert work.exists() and p in ctx.open_documents
    ctx.close()
    assert not work.exists()
    with pytest.raises(ValueError):
        _ = p.pages  # proiectul a fost inchis


def test_closed_project_leaves_open_documents(ctx):
    p = OcrProject.create(context=ctx)
    p.close()
    assert p not in ctx.open_documents


# =============================================================================
# J-030: proiect nou
# =============================================================================


def test_T_J030_2_new_project_is_empty_and_untitled(ctx):
    """T-J030.2: proiect gol, fara titlu, numerotat pentru `Untitled project N`."""
    a = OcrProject.create(context=ctx)
    b = OcrProject.create(context=ctx)
    assert a.pages == () and a.path is None and a.name == ""
    assert b.untitled_number == a.untitled_number + 1
    assert a.is_modified is False
    named = OcrProject.create("Cerere finantare", context=ctx)
    assert named.name == "Cerere finantare" and named.untitled_number is None
    for p in (a, b, named):
        p.close()


def test_defaults_from_schema(project):
    assert project.languages == ("ron", "eng")
    assert project.layout_mode is LayoutMode.EDITABLE
    assert project.metadata == {"title": None, "author": None, "subject": None, "keywords": None}


# =============================================================================
# J-050, J-066: adaugarea paginilor
# =============================================================================


def test_T_J050_4_add_images_copies_into_project(project, src):
    """T-J050.4: paginile se copiaza in folderul proiectului; nesuportatele se raporteaza."""
    added, skipped = project.add_images(
        [src / "alb.png", src / "doua.pdf", src / "desen.svg", src / "trei.tif"])
    assert _numbers(project) == [1, 2, 3, 4, 5, 6]
    assert [pg.page_number for pg in added] == [1, 2, 3, 4, 5, 6]
    assert _sources(project) == [("alb.png", 1), ("doua.pdf", 1), ("doua.pdf", 2),
                                 ("trei.tif", 1), ("trei.tif", 2), ("trei.tif", 3)]
    (path, err), = skipped
    assert path.name == "desen.svg" and isinstance(err, UnsupportedFormatError)
    for pg in project.pages:
        assert pg.image_path.is_file() and project._work in pg.image_path.parents
        assert pg.status is PageStatus.IMPORTED
        assert pg.image_path == pg.original_path  # se despart abia la preprocesare
        with Image.open(pg.image_path) as im:
            assert im.size == (pg.width_px, pg.height_px)
    assert project.is_modified


def test_single_raster_is_copied_byte_for_byte(project, src):
    project.add_images([src / "foto.jpg"])
    stored = project.page(1).image_path
    assert stored.suffix == ".jpg"
    assert stored.read_bytes() == (src / "foto.jpg").read_bytes()  # fara recomprimare


def test_multipage_and_pdf_pages_are_stored_as_png(project, src):
    project.add_images([src / "trei.tif", src / "doua.pdf"])
    assert {pg.image_path.suffix for pg in project.pages} == {".png"}
    pdf_page = project.page(4)
    assert (pdf_page.width_px, pdf_page.height_px, pdf_page.dpi_x) == (2480, 3509, 300)
    assert pdf_page.color_mode is ColorMode.GRAY


def test_exif_rotated_photo_is_stored_upright(project, tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "telefon.jpg"
    Image.new("RGB", (300, 200), (200, 10, 10)).save(path, exif=exif.tobytes())
    project.add_images([path])
    pg = project.page(1)
    assert (pg.width_px, pg.height_px) == (200, 300)
    assert pg.image_path.suffix == ".png"


def test_thumbnail_is_saved(project, src):
    project.add_images([src / "doua.pdf"])
    (blob,) = project._con.execute("SELECT thumbnail_blob FROM page WHERE page_number=1").fetchone()
    thumb = Image.open(io.BytesIO(blob))
    assert max(thumb.size) <= THUMBNAIL_SIZE


def test_T_J066_1_insert_in_the_middle_renumbers(project, src):
    """T-J066.1: inserarea renumeroteaza paginile urmatoare."""
    project.add_images([src / "trei.tif"])
    added, _ = project.add_images([src / "alb.png"], at=2)
    assert added[0].page_number == 2
    assert _sources(project) == [("trei.tif", 1), ("alb.png", 1), ("trei.tif", 2), ("trei.tif", 3)]
    project.add_images([src / "foto.jpg"], at=1)
    assert _numbers(project) == [1, 2, 3, 4, 5]
    assert project.page(1).source_file.name == "foto.jpg"


@pytest.mark.parametrize("at", [0, 3, -1])
def test_insert_position_is_validated(project, src, at):
    project.add_images([src / "alb.png"])
    with pytest.raises(ValueError):
        project.add_images([src / "alb.png"], at=at)


def test_a_file_is_added_whole_or_not_at_all(project, src, monkeypatch):
    real = ImageLoader.open_pixels

    def fail_on_page_2(self, image):
        if image.source_page == 2:
            raise FileCorruptError("stricata", path=str(image.path), page=2)
        return real(self, image)

    monkeypatch.setattr(ImageLoader, "open_pixels", fail_on_page_2)
    project.add_images([src / "alb.png"])
    added, skipped = project.add_images([src / "trei.tif"])
    assert added == [] and skipped[0][0].name == "trei.tif"
    assert _numbers(project) == [1]
    assert len(list((project._work / "images").iterdir())) == 1  # nicio imagine ramasa


def test_T_J052_2_password_pdf_in_batch(project, tmp_path, src):
    """T-J052.2: PDF cu parola: se cere; refuzul doar il sare din lot."""
    secret = make_pdf(tmp_path / "secret.pdf", [(*A4, BLACK)], user_password="p")
    added, skipped = project.add_images([secret, src / "alb.png"])
    assert len(added) == 1 and isinstance(skipped[0][1], PasswordRequiredError)
    added, skipped = project.add_images([secret], password=lambda _: "p")
    assert len(added) == 1 and skipped == []


def test_missing_file_is_reported(project, tmp_path):
    added, skipped = project.add_images([tmp_path / "lipsa.png"])
    assert added == [] and skipped[0][1].params["detail"] == "not_found"


def test_progress_and_cancel(project, src):
    seen = []
    project.add_images([src / "alb.png", src / "foto.jpg"], progress=seen.append)
    assert [(p.current, p.total) for p in seen] == [(0, 2), (1, 2), (2, 2)]
    assert seen[0].stage == "stage.adding_pages"
    answers = iter([False, False, True])
    with pytest.raises(OperationCancelledError):
        project.add_images([src / "alb.png", src / "trei.tif", src / "foto.jpg"],
                           cancel=lambda: next(answers, True))
    assert len(project.pages) == 3  # cele adaugate inainte de anulare raman


# =============================================================================
# J-034, J-031: salvare si deschidere
# =============================================================================


def test_T_J034_1_save_and_reopen_keeps_everything(ctx, project, src, tmp_path):
    """T-J034.1: imaginile, textul, setarile se salveaza si se redeschid identic."""
    project.add_images([src / "alb.png", src / "doua.pdf"])
    project.set_metadata(title="Cerere", author="Ana", keywords="finantare")
    project.languages = ["ron"]
    project.layout_mode = LayoutMode.FORMATTED
    project.settings().set("ocr.quality", "fast")
    target = tmp_path / "Dosare" / "Cerere 2026"
    project.save(target)
    assert project.path == target.resolve() and project.is_modified is False
    assert project.name == "Cerere 2026"  # fara titlu -> numele folderului
    assert sorted(x.name for x in target.iterdir()) == ["images", "project.db"]
    assert not list(target.glob("*-wal")) and not list(target.glob("*-shm"))

    again = OcrProject.open(target, context=ctx)
    assert _sources(again) == _sources(project)
    assert again.metadata["title"] == "Cerere" and again.metadata["subject"] is None
    assert again.languages == ("ron",) and again.layout_mode is LayoutMode.FORMATTED
    assert again.settings().get("ocr.quality") == "fast"
    assert ctx.settings.get("ocr.quality") == "thorough"  # globalul neatins (J-039)
    assert again.is_modified is False
    again.close()


def test_T_J040_1_disk_unchanged_until_save(ctx, project, src, tmp_path):
    """T-J040.1: modificarile nesalvate nu ating proiectul de pe disc."""
    target = tmp_path / "P"
    project.add_images([src / "alb.png"])
    project.save(target)
    project.add_images([src / "foto.jpg"])
    assert project.is_modified
    assert len(list((target / "images").iterdir())) == 1
    project.save()  # Save, in acelasi loc
    assert len(list((target / "images").iterdir())) == 2
    assert not [x for x in tmp_path.iterdir() if x.name.startswith(".P.")]  # fara resturi


def test_first_save_needs_a_path(project):
    with pytest.raises(ValueError):
        project.save()


def test_save_refuses_folder_with_foreign_files(project, tmp_path):
    folder = tmp_path / "Documente"
    folder.mkdir()
    (folder / "personal.docx").write_text("important")
    with pytest.raises(FileExistsError):
        project.save(folder)
    assert (folder / "personal.docx").read_text() == "important"


def test_save_into_empty_folder_is_allowed(project, tmp_path):
    (tmp_path / "gol").mkdir()
    project.save(tmp_path / "gol")
    assert (tmp_path / "gol" / "project.db").is_file()


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="permisiunile POSIX nu se aplica")
def test_save_without_write_permission(project, tmp_path):
    locked = tmp_path / "blocat"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(NoWritePermissionError):
            project.save(locked / "Proiect")
    finally:
        locked.chmod(0o700)


def test_open_accepts_project_db_path(ctx, project, tmp_path):
    project.save(tmp_path / "P")
    p = OcrProject.open(tmp_path / "P" / "project.db", context=ctx)
    assert p.path == (tmp_path / "P").resolve()
    p.close()


def test_T_J031_2_broken_structure_is_refused(ctx, project, src, tmp_path):
    """T-J031.2: structura stricata -> InvalidProjectError."""
    with pytest.raises(InvalidProjectError):
        OcrProject.open(tmp_path / "nu-exista", context=ctx)
    project.add_images([src / "alb.png"])
    project.save(tmp_path / "P")
    for img in (tmp_path / "P" / "images").iterdir():
        img.unlink()
    with pytest.raises(InvalidProjectError) as info:
        OcrProject.open(tmp_path / "P", context=ctx)
    assert info.value.params["pages"] == [1]


def test_T_J032_1_newer_project_is_refused(ctx, project, tmp_path):
    """T-J032.1: un proiect dintr-o versiune mai noua nu se deschide."""
    import sqlite3

    project.save(tmp_path / "P")
    con = sqlite3.connect(tmp_path / "P" / "project.db")
    con.execute("UPDATE project SET schema_version = 99")
    con.commit()
    con.close()
    with pytest.raises(ProjectVersionError):
        OcrProject.open(tmp_path / "P", context=ctx)


def test_closed_project_is_refused(ctx):
    p = OcrProject.create(context=ctx)
    work = p._work
    p.close()
    p.close()
    assert not work.exists()
    with pytest.raises(ValueError):
        _ = p.pages
    with pytest.raises(ValueError):
        p.save()


def test_page_lookup(project, src):
    project.add_images([src / "trei.tif"])
    assert project.page(3).source_page == 3
    for bad in (0, 4):
        with pytest.raises(ValueError):
            project.page(bad)


# =============================================================================
# J-038, J-039: metadate si setari de proiect
# =============================================================================


def test_T_J038_1_metadata(project):
    """T-J038.1: nume, autor, subiect, cuvinte cheie."""
    project.set_metadata(title="T", author="A", subject="S", keywords="k1, k2")
    assert project.metadata == {"title": "T", "author": "A", "subject": "S", "keywords": "k1, k2"}
    project.set_metadata(author="")
    assert project.metadata["author"] is None
    with pytest.raises(ValueError):
        project.set_metadata(publisher="X")


def test_T_J039_1_project_settings_override_and_mark_modified(ctx, project, tmp_path):
    """T-J039.1: setarile de proiect suprascriu globalele si sunt modificari."""
    project.save(tmp_path / "P")
    assert project.is_modified is False
    project.settings().set("image.deskew", False)
    assert project.is_modified is True
    assert ctx.settings.get("image.deskew") is True


def test_languages_are_validated(project):
    for bad in ([], ["ron", "ron"], [""]):
        with pytest.raises(ValueError):
            project.languages = bad


# =============================================================================
# J-036, J-037: salvare automata si recuperare
# =============================================================================


def test_T_J036_1_autosave_only_when_modified(project, src):
    """T-J036.1: copia de siguranta se face doar daca exista modificari."""
    assert project.autosave() is None
    project.add_images([src / "alb.png"])
    first = project.autosave()
    assert (first / "project.db").is_file() and len(list((first / "images").iterdir())) == 1
    assert project.autosave() == first  # nimic nou -> aceeasi copie
    project.add_images([src / "foto.jpg"])
    second = project.autosave()
    assert second != first and not first.exists()  # copia veche se inlocuieste


def test_save_and_close_remove_the_safety_copy(project, src, tmp_path):
    project.add_images([src / "alb.png"])
    snap = project.autosave()
    project.save(tmp_path / "P")
    assert not snap.exists()


def test_T_J037_1_recovery_after_crash(tmp_path, src):
    """T-J037.1: dupa o cadere, la pornire se ofera proiectul; se recupereaza."""
    paths = AppPaths.portable(tmp_path / "app")
    crashed = AppContext.start(paths)
    p = OcrProject.create(context=crashed)
    p.add_images([src / "doua.pdf"])
    p.save(tmp_path / "Salvat")
    p.add_images([src / "alb.png"])  # modificare nesalvata
    snap = p.autosave()
    # caderea: sesiunea nu se inchide, iar procesul ei nu mai exista
    with crashed.app_db:
        crashed.app_db.execute("UPDATE recovery_entry SET session_id = ?", (DEAD,))
    crashed.app_db.close()

    fresh = AppContext.start(paths)
    found = OcrProject.find_recovery(context=fresh)
    assert found == [(snap, (tmp_path / "Salvat").resolve())]
    rec = OcrProject.recover(snap, context=fresh)
    assert len(rec.pages) == 3 and rec.is_modified is True
    assert rec.path == (tmp_path / "Salvat").resolve()
    assert OcrProject.find_recovery(context=fresh) == []
    rec.save()
    assert len(list((tmp_path / "Salvat" / "images").iterdir())) == 3
    rec.close()
    fresh.close()


def test_recover_unknown_copy_is_refused(ctx, tmp_path):
    with pytest.raises(InvalidProjectError):
        OcrProject.recover(tmp_path / "nimic.dlproj", context=ctx)


def test_clean_exit_leaves_nothing_to_recover(tmp_path, src):
    paths = AppPaths.portable(tmp_path / "app")
    first = AppContext.start(paths)
    p = OcrProject.create(context=first)
    p.add_images([src / "alb.png"])
    p.autosave()
    first.close()
    second = AppContext.start(paths)
    assert OcrProject.find_recovery(context=second) == []
    second.close()


def test_autosave_notices_settings_only_changes(project, src):
    project.add_images([src / "alb.png"])
    first = project.autosave()
    project.settings().set("ocr.quality", "fast")
    second = project.autosave()
    assert second is not None and second != first
